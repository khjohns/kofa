-- KOFA Phase 2b: Most cited cases function
-- Used by the mest_siterte MCP tool

CREATE OR REPLACE FUNCTION kofa_most_cited(max_results INT DEFAULT 20)
RETURNS TABLE(
    sak_nr TEXT,
    cited_count BIGINT,
    innklaget TEXT,
    avgjoerelse TEXT,
    saken_gjelder TEXT,
    avsluttet DATE
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        cr.to_sak_nr AS sak_nr,
        COUNT(*)::BIGINT AS cited_count,
        c.innklaget,
        c.avgjoerelse,
        c.saken_gjelder,
        c.avsluttet
    FROM kofa_case_references cr
    LEFT JOIN kofa_cases c ON c.sak_nr = cr.to_sak_nr
    GROUP BY cr.to_sak_nr, c.innklaget, c.avgjoerelse, c.saken_gjelder, c.avsluttet
    ORDER BY cited_count DESC
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;
