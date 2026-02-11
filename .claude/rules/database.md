---
paths:
  - "src/kofa/supabase_backend.py"
  - "src/kofa/vector_search.py"
  - "src/kofa/service.py"
  - "migrations/**"
---

# Supabase-database

Prosjektnavn: `unified-timeline` (delt med paragraf og andre Catenda-prosjekter). Prosjekt-ID: `iyetsvrteyzpirygxenu`.

## Tabeller (alle prefikset `kofa_`)

- `kofa_cases` — Saker med metadata og vektet FTS. PK: `sak_nr`. Nøkkelkolonner: `saken_gjelder`, `innklaget`, `klager`, `sakstype`, `regelverk`, `summary`, `pdf_url`
- `kofa_decision_text` — Avgjørelsestekst per avsnitt. PK: `id`. Nøkkelkolonner: `sak_nr`, `paragraph_number`, `section`, `text`, `search_vector`, `embedding`
- `kofa_law_references` — Lovhenvisninger. PK: `id`. Nøkkelkolonner: `sak_nr`, `law_name`, `law_section`, `raw_text`, `context`, `regulation_version`
- `kofa_case_references` — KOFA-kryssreferanser. Nøkkelkolonner: `from_sak_nr`, `to_sak_nr`, `context`
- `kofa_eu_references` — EU-domstolsreferanser. Nøkkelkolonner: `sak_nr`, `eu_case_id`, `eu_case_name`, `context`
- `kofa_eu_case_law` — Fulltekst EU-dommer fra EUR-Lex. PK: `eu_case_id`. Nøkkelkolonner: `celex`, `case_name`, `full_text`, `char_count` (generated), `language`
- `kofa_court_references` — Norske domstolsreferanser. Nøkkelkolonner: `sak_nr`, `court_case_id`, `court_level`, `court_name`, `context`
- `kofa_sync_meta` — Sync-status og cursors. PK: `source`

## RLS-mønster

- Separate policies for SELECT (public read) og INSERT/UPDATE/DELETE (service_role write)
- Aldri bruk `FOR ALL` (overlapper SELECT og gir multiple_permissive_policies-advarsel)
- Wrap `auth.role()` i subselect: `(select auth.role()) = 'service_role'`

## SQL-funksjoner

- Alltid `SET search_path = ''` og bruk `public.`-prefikser på tabellreferanser
- Migrasjoner kjøres via Supabase MCP `apply_migration`, lokale filer i `migrations/` holdes oppdatert som referanse

## Seksjoner i avgjørelsestekst

KOFA-avgjørelser følger fast rekkefølge: `bakgrunn` → `anfoersler` → `vurdering` (evt. `innledning` før, `konklusjon` etter). Seksjonsklassifisering skjer i `pdf_extractor.py:_assign_sections()`.

Viktig: enkeltord-nøkkelord (bakgrunn, anførsler) krever kolon i regex for å unngå falske seksjonsgrenser fra PDF-linjeskift.
