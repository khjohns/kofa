-- KOFA Phase 2c: Regulation version tracking
-- Distinguishes references to old (pre-2017) vs new (2017+) regulations

-- Add regulation_version column
ALTER TABLE kofa_law_references
    ADD COLUMN IF NOT EXISTS regulation_version TEXT
    CHECK (regulation_version IN ('old', 'new'));

-- Index for filtering by version
CREATE INDEX IF NOT EXISTS idx_kofa_law_refs_version
    ON kofa_law_references(regulation_version);

COMMENT ON COLUMN kofa_law_references.regulation_version IS
    'old = pre-2017 regulations (LOA 1999 / FOA 2006), new = current (LOA 2016 / FOA 2016)';
