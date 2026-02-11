---
description: Kjør verifisering av KOFA-data og kode
allowed-tools: Bash, mcp__plugin_supabase_supabase__execute_sql
---

Kjør følgende verifiseringer og rapporter resultatet samlet:

1. **Lint**: `./venv/bin/ruff check src/`
2. **Type-check**: `./venv/bin/pyright src/`
3. **Data-integritet** (SQL mot Supabase prosjekt `iyetsvrteyzpirygxenu`):
   - Antall saker i `kofa_cases`
   - Antall avsnitt i `kofa_decision_text`
   - Antall saker med PDF-tekst: `SELECT count(DISTINCT sak_nr) FROM kofa_decision_text`
   - Antall saker uten PDF-tekst: `SELECT count(*) FROM kofa_cases WHERE sak_nr NOT IN (SELECT DISTINCT sak_nr FROM kofa_decision_text)`
   - Antall referanser per type: law, case, eu, court

Presenter resultatet som en kompakt tabell.
