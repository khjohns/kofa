-- KOFA Phase 3: Forarbeider (legislative preparatory works)
-- Stores propositions (Prop.) and NOUs chunked by PDF TOC entries

-- ============================================================
-- Table: kofa_forarbeider — Document metadata
-- ============================================================
CREATE TABLE IF NOT EXISTS kofa_forarbeider (
    doc_id TEXT PRIMARY KEY,              -- "prop-51-l-2015-2016", "nou-2023-26"
    doc_type TEXT NOT NULL,               -- "prop", "nou"
    title TEXT NOT NULL,                  -- "Prop. 51 L (2015–2016)"
    full_title TEXT,                      -- Full title with description
    session TEXT,                         -- "2015–2016"
    page_count INT,
    char_count INT,
    section_count INT,
    source_url TEXT,
    source_file TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE kofa_forarbeider IS
    'Legislative preparatory works (forarbeider) for Norwegian procurement law';

-- ============================================================
-- Table: kofa_forarbeider_sections — TOC-based chunks with text and embeddings
-- ============================================================
CREATE TABLE IF NOT EXISTS kofa_forarbeider_sections (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doc_id TEXT NOT NULL REFERENCES kofa_forarbeider(doc_id),
    section_number TEXT NOT NULL,         -- "4.1.2" from TOC
    title TEXT NOT NULL,                  -- Section heading
    level INT NOT NULL,                   -- TOC level (1-4)
    page_start INT,                       -- Starting page in PDF
    parent_path TEXT,                     -- "4 > 4.1 > 4.1.2"
    sort_order INT NOT NULL,             -- Order in document
    text TEXT NOT NULL DEFAULT '',        -- Section content
    char_count INT GENERATED ALWAYS AS (LENGTH(text)) STORED,
    search_vector TSVECTOR,
    embedding VECTOR(1536),              -- Gemini embedding-001
    content_hash TEXT,                   -- For change detection
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(doc_id, section_number)
);

COMMENT ON TABLE kofa_forarbeider_sections IS
    'TOC-based sections from forarbeider PDFs with text, FTS, and embeddings';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_kofa_forarbeider_sections_doc
    ON kofa_forarbeider_sections(doc_id);
CREATE INDEX IF NOT EXISTS idx_kofa_forarbeider_sections_doc_sort
    ON kofa_forarbeider_sections(doc_id, sort_order);
CREATE INDEX IF NOT EXISTS idx_kofa_forarbeider_sections_search
    ON kofa_forarbeider_sections USING GIN(search_vector);

-- ============================================================
-- Table: kofa_forarbeider_law_refs — Law references from forarbeider
-- ============================================================
CREATE TABLE IF NOT EXISTS kofa_forarbeider_law_refs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doc_id TEXT NOT NULL REFERENCES kofa_forarbeider(doc_id),
    section_number TEXT NOT NULL,
    law_name TEXT NOT NULL,
    law_section TEXT,
    context TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE kofa_forarbeider_law_refs IS
    'Law references extracted from forarbeider text';

CREATE INDEX IF NOT EXISTS idx_kofa_forarbeider_law_refs_doc
    ON kofa_forarbeider_law_refs(doc_id);
CREATE INDEX IF NOT EXISTS idx_kofa_forarbeider_law_refs_law
    ON kofa_forarbeider_law_refs(law_name, law_section);

-- ============================================================
-- Table: kofa_forarbeider_eu_refs — EU case references from forarbeider
-- ============================================================
CREATE TABLE IF NOT EXISTS kofa_forarbeider_eu_refs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doc_id TEXT NOT NULL REFERENCES kofa_forarbeider(doc_id),
    section_number TEXT NOT NULL,
    eu_case_id TEXT NOT NULL,
    context TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE kofa_forarbeider_eu_refs IS
    'EU case references extracted from forarbeider text';

CREATE INDEX IF NOT EXISTS idx_kofa_forarbeider_eu_refs_doc
    ON kofa_forarbeider_eu_refs(doc_id);
CREATE INDEX IF NOT EXISTS idx_kofa_forarbeider_eu_refs_case
    ON kofa_forarbeider_eu_refs(eu_case_id);

-- ============================================================
-- FTS trigger: title weighted A, text weighted B
-- ============================================================
CREATE OR REPLACE FUNCTION kofa_forarbeider_sections_search_trigger()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('norwegian', coalesce(NEW.title, '')), 'A') ||
        setweight(to_tsvector('norwegian', coalesce(NEW.text, '')), 'B');
    RETURN NEW;
END;
$$;

CREATE TRIGGER kofa_forarbeider_sections_search_update
    BEFORE INSERT OR UPDATE OF title, text
    ON kofa_forarbeider_sections
    FOR EACH ROW
    EXECUTE FUNCTION kofa_forarbeider_sections_search_trigger();

-- ============================================================
-- RPC: FTS search
-- ============================================================
CREATE OR REPLACE FUNCTION search_kofa_forarbeider(
    search_query TEXT,
    doc_filter TEXT DEFAULT NULL,
    max_results INT DEFAULT 20
)
RETURNS TABLE(
    doc_id TEXT,
    doc_title TEXT,
    section_number TEXT,
    title TEXT,
    level INT,
    text TEXT,
    char_count INT,
    rank REAL
)
LANGUAGE plpgsql
SET search_path = ''
AS $$
DECLARE
    tsq tsquery;
BEGIN
    SET search_path = '';
    tsq := websearch_to_tsquery('norwegian', search_query);

    RETURN QUERY
    SELECT
        s.doc_id,
        d.title AS doc_title,
        s.section_number,
        s.title,
        s.level,
        s.text,
        s.char_count,
        ts_rank(s.search_vector, tsq) AS rank
    FROM public.kofa_forarbeider_sections s
    JOIN public.kofa_forarbeider d ON d.doc_id = s.doc_id
    WHERE s.search_vector @@ tsq
      AND (doc_filter IS NULL OR s.doc_id = doc_filter)
      AND LENGTH(s.text) > 0
    ORDER BY rank DESC
    LIMIT max_results;
END;
$$;

-- ============================================================
-- RPC: Hybrid vector+FTS search
-- ============================================================
CREATE OR REPLACE FUNCTION search_kofa_forarbeider_hybrid(
    query_text TEXT,
    query_embedding VECTOR,
    doc_filter TEXT DEFAULT NULL,
    match_count INT DEFAULT 10,
    fts_weight FLOAT DEFAULT 0.3,
    ivfflat_probes INT DEFAULT 10
)
RETURNS TABLE(
    doc_id TEXT,
    doc_title TEXT,
    section_number TEXT,
    title TEXT,
    level INT,
    text TEXT,
    char_count INT,
    similarity FLOAT,
    fts_rank FLOAT,
    combined_score FLOAT
)
LANGUAGE plpgsql
SET search_path = ''
AS $$
DECLARE
    tsq tsquery;
BEGIN
    SET search_path = '';
    EXECUTE format('SET LOCAL ivfflat.probes = %s', ivfflat_probes);

    tsq := websearch_to_tsquery('norwegian', query_text);

    RETURN QUERY
    SELECT
        s.doc_id,
        d.title AS doc_title,
        s.section_number,
        s.title,
        s.level,
        s.text,
        s.char_count,
        (1 - (s.embedding <=> query_embedding))::FLOAT AS similarity,
        COALESCE(ts_rank(s.search_vector, tsq), 0)::FLOAT AS fts_rank,
        (
            (1 - fts_weight) * (1 - (s.embedding <=> query_embedding)) +
            fts_weight * COALESCE(ts_rank(s.search_vector, tsq), 0)
        )::FLOAT AS combined_score
    FROM public.kofa_forarbeider_sections s
    JOIN public.kofa_forarbeider d ON d.doc_id = s.doc_id
    WHERE s.embedding IS NOT NULL
      AND LENGTH(s.text) > 0
      AND (doc_filter IS NULL OR s.doc_id = doc_filter)
    ORDER BY combined_score DESC
    LIMIT match_count;
END;
$$;

-- ============================================================
-- RLS: public read, service_role write (all 4 tables)
-- ============================================================

-- kofa_forarbeider
ALTER TABLE kofa_forarbeider ENABLE ROW LEVEL SECURITY;
CREATE POLICY "kofa_forarbeider_read" ON kofa_forarbeider FOR SELECT USING (true);
CREATE POLICY "kofa_forarbeider_write" ON kofa_forarbeider FOR INSERT
    WITH CHECK ((select auth.role()) = 'service_role');
CREATE POLICY "kofa_forarbeider_update" ON kofa_forarbeider FOR UPDATE
    USING ((select auth.role()) = 'service_role')
    WITH CHECK ((select auth.role()) = 'service_role');
CREATE POLICY "kofa_forarbeider_delete" ON kofa_forarbeider FOR DELETE
    USING ((select auth.role()) = 'service_role');

-- kofa_forarbeider_sections
ALTER TABLE kofa_forarbeider_sections ENABLE ROW LEVEL SECURITY;
CREATE POLICY "kofa_forarbeider_sections_read" ON kofa_forarbeider_sections FOR SELECT USING (true);
CREATE POLICY "kofa_forarbeider_sections_write" ON kofa_forarbeider_sections FOR INSERT
    WITH CHECK ((select auth.role()) = 'service_role');
CREATE POLICY "kofa_forarbeider_sections_update" ON kofa_forarbeider_sections FOR UPDATE
    USING ((select auth.role()) = 'service_role')
    WITH CHECK ((select auth.role()) = 'service_role');
CREATE POLICY "kofa_forarbeider_sections_delete" ON kofa_forarbeider_sections FOR DELETE
    USING ((select auth.role()) = 'service_role');

-- kofa_forarbeider_law_refs
ALTER TABLE kofa_forarbeider_law_refs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "kofa_forarbeider_law_refs_read" ON kofa_forarbeider_law_refs FOR SELECT USING (true);
CREATE POLICY "kofa_forarbeider_law_refs_write" ON kofa_forarbeider_law_refs FOR INSERT
    WITH CHECK ((select auth.role()) = 'service_role');
CREATE POLICY "kofa_forarbeider_law_refs_update" ON kofa_forarbeider_law_refs FOR UPDATE
    USING ((select auth.role()) = 'service_role')
    WITH CHECK ((select auth.role()) = 'service_role');
CREATE POLICY "kofa_forarbeider_law_refs_delete" ON kofa_forarbeider_law_refs FOR DELETE
    USING ((select auth.role()) = 'service_role');

-- kofa_forarbeider_eu_refs
ALTER TABLE kofa_forarbeider_eu_refs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "kofa_forarbeider_eu_refs_read" ON kofa_forarbeider_eu_refs FOR SELECT USING (true);
CREATE POLICY "kofa_forarbeider_eu_refs_write" ON kofa_forarbeider_eu_refs FOR INSERT
    WITH CHECK ((select auth.role()) = 'service_role');
CREATE POLICY "kofa_forarbeider_eu_refs_update" ON kofa_forarbeider_eu_refs FOR UPDATE
    USING ((select auth.role()) = 'service_role')
    WITH CHECK ((select auth.role()) = 'service_role');
CREATE POLICY "kofa_forarbeider_eu_refs_delete" ON kofa_forarbeider_eu_refs FOR DELETE
    USING ((select auth.role()) = 'service_role');
