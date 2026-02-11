-- KOFA Phase 2d: EU Court of Justice case references
-- Stores references to EU cases like C-19/00 SIAC Construction

CREATE TABLE IF NOT EXISTS kofa_eu_references (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sak_nr TEXT NOT NULL REFERENCES kofa_cases(sak_nr),
    eu_case_id TEXT NOT NULL,           -- "C-19/00"
    eu_case_name TEXT,                  -- "SIAC Construction" (may be NULL)
    paragraph_number INT,
    context TEXT,                       -- Surrounding text
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Find all KOFA cases citing a specific EU case
CREATE INDEX IF NOT EXISTS idx_kofa_eu_refs_case_id
    ON kofa_eu_references(eu_case_id);

-- Find all EU refs for a KOFA case
CREATE INDEX IF NOT EXISTS idx_kofa_eu_refs_sak
    ON kofa_eu_references(sak_nr);

-- RLS: public read, service_role write
ALTER TABLE kofa_eu_references ENABLE ROW LEVEL SECURITY;

CREATE POLICY "kofa_eu_references_public_read"
    ON kofa_eu_references FOR SELECT
    USING (true);

CREATE POLICY "kofa_eu_references_service_write"
    ON kofa_eu_references FOR INSERT
    WITH CHECK ((select auth.role()) = 'service_role');
CREATE POLICY "kofa_eu_references_update"
    ON kofa_eu_references FOR UPDATE
    USING ((select auth.role()) = 'service_role')
    WITH CHECK ((select auth.role()) = 'service_role');
CREATE POLICY "kofa_eu_references_delete"
    ON kofa_eu_references FOR DELETE
    USING ((select auth.role()) = 'service_role');

COMMENT ON TABLE kofa_eu_references IS
    'EU Court of Justice case references extracted from KOFA decision text';
