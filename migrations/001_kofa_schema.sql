-- KOFA Schema: Tables, indexes, FTS, search function, RLS
-- Prefix: kofa_ (shares Supabase project with paragraf)

-- =============================================================================
-- Enable extensions
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- =============================================================================
-- Table: kofa_cases
-- =============================================================================

CREATE TABLE IF NOT EXISTS kofa_cases (
    sak_nr TEXT PRIMARY KEY,             -- e.g. "2023/1099"
    slug TEXT,                            -- URL slug from WordPress
    page_url TEXT,                        -- Full URL to case page
    wp_id INTEGER,                        -- WordPress post ID
    wp_modified TEXT,                     -- WordPress modified timestamp

    -- From WP API
    summary TEXT,                         -- Excerpt/summary
    published TEXT,                       -- Publication date

    -- From HTML scraping
    innklaget TEXT,                       -- Respondent
    klager TEXT,                          -- Complainant
    sakstype TEXT,                        -- Case type
    avgjoerelse TEXT,                     -- Decision/outcome
    saken_gjelder TEXT,                   -- Subject matter
    regelverk TEXT,                       -- Applicable regulations
    konkurranseform TEXT,                 -- Competition type
    prosedyre TEXT,                       -- Procedure
    avsluttet DATE,                       -- Decision date
    pdf_url TEXT,                         -- URL to PDF decision

    -- Full-text search
    fts tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('norwegian', coalesce(sak_nr, '')), 'A') ||
        setweight(to_tsvector('norwegian', coalesce(innklaget, '')), 'A') ||
        setweight(to_tsvector('norwegian', coalesce(klager, '')), 'A') ||
        setweight(to_tsvector('norwegian', coalesce(saken_gjelder, '')), 'B') ||
        setweight(to_tsvector('norwegian', coalesce(summary, '')), 'C')
    ) STORED,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- FTS index
CREATE INDEX IF NOT EXISTS idx_kofa_cases_fts ON kofa_cases USING gin(fts);

-- Trigram indexes for fuzzy matching on party names
CREATE INDEX IF NOT EXISTS idx_kofa_cases_innklaget_trgm ON kofa_cases USING gin(innklaget gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_kofa_cases_klager_trgm ON kofa_cases USING gin(klager gin_trgm_ops);

-- Lookup indexes
CREATE INDEX IF NOT EXISTS idx_kofa_cases_sakstype ON kofa_cases(sakstype);
CREATE INDEX IF NOT EXISTS idx_kofa_cases_avgjoerelse ON kofa_cases(avgjoerelse);
CREATE INDEX IF NOT EXISTS idx_kofa_cases_avsluttet ON kofa_cases(avsluttet DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_kofa_cases_wp_id ON kofa_cases(wp_id);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION kofa_update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
SET search_path = '';

DROP TRIGGER IF EXISTS kofa_cases_updated ON kofa_cases;
CREATE TRIGGER kofa_cases_updated
    BEFORE UPDATE ON kofa_cases
    FOR EACH ROW
    EXECUTE FUNCTION kofa_update_timestamp();

-- =============================================================================
-- Table: kofa_decision_text (Phase 2 - created but not populated)
-- =============================================================================

CREATE TABLE IF NOT EXISTS kofa_decision_text (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sak_nr TEXT NOT NULL REFERENCES kofa_cases(sak_nr),
    paragraph_number INT NOT NULL,
    section TEXT,                          -- "innledning", "bakgrunn", etc.
    text TEXT NOT NULL,
    raw_full_text TEXT,                    -- Full text for FTS (only on first row)

    UNIQUE(sak_nr, paragraph_number)
);

CREATE INDEX IF NOT EXISTS idx_kofa_decision_text_sak ON kofa_decision_text(sak_nr);

-- =============================================================================
-- Table: kofa_sync_meta
-- =============================================================================

CREATE TABLE IF NOT EXISTS kofa_sync_meta (
    source TEXT PRIMARY KEY,              -- "wp_api", "html_scrape", "pdf"
    cursor_value TEXT,                    -- Last sync cursor
    last_count INTEGER DEFAULT 0,
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- Search function with AND->OR fallback
-- =============================================================================

CREATE OR REPLACE FUNCTION search_kofa(
    search_query TEXT,
    max_results INT DEFAULT 20
)
RETURNS TABLE(
    sak_nr TEXT,
    slug TEXT,
    page_url TEXT,
    innklaget TEXT,
    klager TEXT,
    sakstype TEXT,
    avgjoerelse TEXT,
    saken_gjelder TEXT,
    summary TEXT,
    avsluttet DATE,
    pdf_url TEXT,
    rank REAL
) AS $$
DECLARE
    tsquery_and tsquery;
    tsquery_or tsquery;
    result_count INT;
BEGIN
    -- Try AND first
    tsquery_and := plainto_tsquery('norwegian', search_query);

    RETURN QUERY
    SELECT
        c.sak_nr, c.slug, c.page_url,
        c.innklaget, c.klager, c.sakstype,
        c.avgjoerelse, c.saken_gjelder, c.summary,
        c.avsluttet, c.pdf_url,
        ts_rank(c.fts, tsquery_and) AS rank
    FROM public.kofa_cases c
    WHERE c.fts @@ tsquery_and
    ORDER BY rank DESC
    LIMIT max_results;

    GET DIAGNOSTICS result_count = ROW_COUNT;

    -- If no AND results, try OR
    IF result_count = 0 AND search_query ~ '\s' THEN
        -- Build OR query from individual words
        tsquery_or := to_tsquery(
            'norwegian',
            array_to_string(
                array(
                    SELECT quote_literal(word) || ':*'
                    FROM unnest(string_to_array(search_query, ' ')) AS word
                    WHERE length(word) > 1
                ),
                ' | '
            )
        );

        RETURN QUERY
        SELECT
            c.sak_nr, c.slug, c.page_url,
            c.innklaget, c.klager, c.sakstype,
            c.avgjoerelse, c.saken_gjelder, c.summary,
            c.avsluttet, c.pdf_url,
            ts_rank(c.fts, tsquery_or) AS rank
        FROM public.kofa_cases c
        WHERE c.fts @@ tsquery_or
        ORDER BY rank DESC
        LIMIT max_results;
    END IF;
END;
$$ LANGUAGE plpgsql
SET search_path = '';

-- =============================================================================
-- Statistics function
-- =============================================================================

CREATE OR REPLACE FUNCTION kofa_statistics(
    filter_year INT DEFAULT NULL,
    group_by_field TEXT DEFAULT 'avgjoerelse'
)
RETURNS TABLE(label TEXT, count BIGINT) AS $$
BEGIN
    IF group_by_field = 'avgjoerelse' THEN
        RETURN QUERY
        SELECT
            COALESCE(c.avgjoerelse, 'Ukjent') AS label,
            COUNT(*)::BIGINT AS count
        FROM public.kofa_cases c
        WHERE (filter_year IS NULL OR EXTRACT(YEAR FROM c.avsluttet) = filter_year)
        GROUP BY c.avgjoerelse
        ORDER BY count DESC;
    ELSIF group_by_field = 'sakstype' THEN
        RETURN QUERY
        SELECT
            COALESCE(c.sakstype, 'Ukjent') AS label,
            COUNT(*)::BIGINT AS count
        FROM public.kofa_cases c
        WHERE (filter_year IS NULL OR EXTRACT(YEAR FROM c.avsluttet) = filter_year)
        GROUP BY c.sakstype
        ORDER BY count DESC;
    ELSE
        RAISE EXCEPTION 'Unknown grouping: %', group_by_field;
    END IF;
END;
$$ LANGUAGE plpgsql
SET search_path = '';

-- =============================================================================
-- RLS Policies
-- =============================================================================

ALTER TABLE kofa_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE kofa_decision_text ENABLE ROW LEVEL SECURITY;
ALTER TABLE kofa_sync_meta ENABLE ROW LEVEL SECURITY;

-- Public read access
CREATE POLICY kofa_cases_read ON kofa_cases FOR SELECT USING (true);
CREATE POLICY kofa_decision_text_read ON kofa_decision_text FOR SELECT USING (true);
CREATE POLICY kofa_sync_meta_read ON kofa_sync_meta FOR SELECT USING (true);

-- Service role write access (separate INSERT/UPDATE/DELETE to avoid SELECT overlap)
CREATE POLICY kofa_cases_write ON kofa_cases FOR INSERT
    WITH CHECK ((select auth.role()) = 'service_role');
CREATE POLICY kofa_cases_update ON kofa_cases FOR UPDATE
    USING ((select auth.role()) = 'service_role')
    WITH CHECK ((select auth.role()) = 'service_role');
CREATE POLICY kofa_cases_delete ON kofa_cases FOR DELETE
    USING ((select auth.role()) = 'service_role');

CREATE POLICY kofa_decision_text_write ON kofa_decision_text FOR INSERT
    WITH CHECK ((select auth.role()) = 'service_role');
CREATE POLICY kofa_decision_text_update ON kofa_decision_text FOR UPDATE
    USING ((select auth.role()) = 'service_role')
    WITH CHECK ((select auth.role()) = 'service_role');
CREATE POLICY kofa_decision_text_delete ON kofa_decision_text FOR DELETE
    USING ((select auth.role()) = 'service_role');

CREATE POLICY kofa_sync_meta_write ON kofa_sync_meta FOR INSERT
    WITH CHECK ((select auth.role()) = 'service_role');
CREATE POLICY kofa_sync_meta_update ON kofa_sync_meta FOR UPDATE
    USING ((select auth.role()) = 'service_role')
    WITH CHECK ((select auth.role()) = 'service_role');
CREATE POLICY kofa_sync_meta_delete ON kofa_sync_meta FOR DELETE
    USING ((select auth.role()) = 'service_role');
