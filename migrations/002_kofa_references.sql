-- KOFA Phase 2: Law and case reference tables
-- Extracted from decision text paragraphs

-- =============================================================================
-- Table: kofa_law_references
-- =============================================================================

CREATE TABLE IF NOT EXISTS kofa_law_references (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sak_nr TEXT NOT NULL REFERENCES kofa_cases(sak_nr),
    paragraph_number INT,
    reference_type TEXT NOT NULL,        -- 'lov' | 'forskrift'
    law_name TEXT NOT NULL,              -- Normalized: "anskaffelsesloven"
    law_section TEXT,                    -- "2-4", "12"
    raw_text TEXT,                       -- Original text as found in PDF
    lovdata_doc_id TEXT,                 -- Resolved FK to lovdata_documents.dok_id
    context TEXT,                        -- Surrounding sentence
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_kofa_law_refs_lookup ON kofa_law_references(law_name, law_section);
CREATE INDEX idx_kofa_law_refs_case ON kofa_law_references(sak_nr);
CREATE INDEX idx_kofa_law_refs_doc ON kofa_law_references(lovdata_doc_id);

-- =============================================================================
-- Table: kofa_case_references
-- =============================================================================

CREATE TABLE IF NOT EXISTS kofa_case_references (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    from_sak_nr TEXT NOT NULL REFERENCES kofa_cases(sak_nr),
    to_sak_nr TEXT NOT NULL,             -- TEXT not FK (referenced case may not exist)
    paragraph_number INT,
    context TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_kofa_case_refs_from ON kofa_case_references(from_sak_nr);
CREATE INDEX idx_kofa_case_refs_to ON kofa_case_references(to_sak_nr);

-- =============================================================================
-- RLS Policies
-- =============================================================================

ALTER TABLE kofa_law_references ENABLE ROW LEVEL SECURITY;
ALTER TABLE kofa_case_references ENABLE ROW LEVEL SECURITY;

-- Public read access
CREATE POLICY kofa_law_references_read ON kofa_law_references FOR SELECT USING (true);
CREATE POLICY kofa_case_references_read ON kofa_case_references FOR SELECT USING (true);

-- Service role write access (separate INSERT/UPDATE/DELETE to avoid SELECT overlap)
CREATE POLICY kofa_law_references_write ON kofa_law_references FOR INSERT
    WITH CHECK ((select auth.role()) = 'service_role');
CREATE POLICY kofa_law_references_update ON kofa_law_references FOR UPDATE
    USING ((select auth.role()) = 'service_role')
    WITH CHECK ((select auth.role()) = 'service_role');
CREATE POLICY kofa_law_references_delete ON kofa_law_references FOR DELETE
    USING ((select auth.role()) = 'service_role');

CREATE POLICY kofa_case_references_write ON kofa_case_references FOR INSERT
    WITH CHECK ((select auth.role()) = 'service_role');
CREATE POLICY kofa_case_references_update ON kofa_case_references FOR UPDATE
    USING ((select auth.role()) = 'service_role')
    WITH CHECK ((select auth.role()) = 'service_role');
CREATE POLICY kofa_case_references_delete ON kofa_case_references FOR DELETE
    USING ((select auth.role()) = 'service_role');
