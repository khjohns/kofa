# KOFA MCP Server

MCP-server for KOFA-avgjørelser (Klagenemnda for offentlige anskaffelser). Gir Claude/LLM tilgang til ~5000 avgjørelser via Model Context Protocol.

## Prosjektstruktur

```
src/kofa/
  __init__.py              # Eksporterer MCPServer, KofaService
  server.py                # MCP JSON-RPC server, verktøydefinisjoner, SERVER_INSTRUCTIONS
  service.py               # Forretningslogikk, formatering, alias-normalisering
  supabase_backend.py      # Database-operasjoner mot Supabase PostgreSQL
  pdf_extractor.py         # PDF → strukturert tekst med seksjonering
  reference_extractor.py   # Regex-ekstraksjon av lov/saks/EU/domstolsreferanser
  eurlex_fetcher.py        # Henting og parsing av EU-dommer fra EUR-Lex HTML
  vector_search.py         # Hybrid vektor+FTS søk (KofaVectorSearch)
  scraper.py               # HTML-scraping av metadata fra kofa.no
  cli.py                   # CLI: kofa serve|sync|status
  web.py                   # Flask blueprint for HTTP MCP-transport
  _supabase_utils.py       # Delt: retry-dekorator, klient, feilklassifisering
scripts/
  embed_kofa.py            # Embedding-generering med Gemini API
docs/
  ADR-001.md               # Arkitekturbeslutninger (les denne for full kontekst)
  metode-rettslig-analyse.md # Arbeidsmetodikk for rettslig analyse (to-lagsmodellen)
  notat-*.md               # Problemdrevne rettslige notater
  kommentar-foa-*.md       # Lovkommentarer per bestemmelse
```

## Arkitektur

Tre-lags med klar ansvarsfordeling:
```
CLI/MCP Server → Service → Supabase Backend
```

Deler Supabase-prosjekt med `../paragraf/` (Lovdata MCP). Alle tabeller prefikset `kofa_`.

## Kommandoer

```bash
# Utvikling
./venv/bin/python -m kofa serve          # stdio MCP server
./venv/bin/python -m kofa status         # Vis sync-status

# Sync pipeline (krever SUPABASE_URL + SUPABASE_KEY)
kofa sync                                # WP API → kofa_cases
kofa sync --scrape                       # HTML → metadata
kofa sync --pdf                          # PDF → kofa_decision_text
kofa sync --references                   # Regex → kofa_law/case/eu_references
kofa sync --eu-cases                     # EUR-Lex → kofa_eu_case_law
kofa sync --embeddings                   # Gemini → embeddings

# Linting
./venv/bin/ruff check src/
```

## Databasetabeller (Supabase)

- `kofa_cases` — Saker med metadata og vektet FTS. PK: `sak_nr`. Nøkkelkolonner: `saken_gjelder`, `innklaget`, `klager`, `sakstype`, `regelverk`, `summary`, `pdf_url`
- `kofa_decision_text` — Avgjørelsestekst per avsnitt. PK: `id`. Nøkkelkolonner: `sak_nr`, `paragraph_number`, `section`, `text`, `search_vector`, `embedding`
- `kofa_law_references` — Lovhenvisninger. PK: `id`. Nøkkelkolonner: `sak_nr`, `law_name`, `law_section`, `raw_text`, `context`, `regulation_version`
- `kofa_case_references` — KOFA-kryssreferanser. Nøkkelkolonner: `from_sak_nr`, `to_sak_nr`, `context`
- `kofa_eu_references` — EU-domstolsreferanser. Nøkkelkolonner: `sak_nr`, `eu_case_id`, `eu_case_name`, `context`
- `kofa_eu_case_law` — Fulltekst EU-dommer fra EUR-Lex. PK: `eu_case_id`. Nøkkelkolonner: `celex`, `case_name`, `full_text`, `char_count` (generated), `language`
- `kofa_court_references` — Norske domstolsreferanser. Nøkkelkolonner: `sak_nr`, `court_case_id`, `court_level`, `court_name`, `context`
- `kofa_sync_meta` — Sync-status og cursors. PK: `source`

## Seksjoner i avgjørelsestekst

KOFA-avgjørelser følger fast rekkefølge: `bakgrunn` → `anfoersler` → `vurdering` (evt. `innledning` før, `konklusjon` etter). Seksjonsklassifisering skjer i `pdf_extractor.py:_assign_sections()`.

Viktig: enkeltord-nøkkelord (bakgrunn, anførsler) krever kolon i regex for å unngå falske seksjonsgrenser fra PDF-linjeskift.

## Supabase-prosjekt

Prosjektnavn: `unified-timeline` (delt med paragraf og andre Catenda-prosjekter).

## Konvensjoner

- Språk: Python 3.11+, norske variabelnavn i domenelag, engelske i infrastruktur
- Formatering: ruff, line-length 100
- Arkitektur: Aldri kall Supabase direkte fra server.py — gå via service.py → supabase_backend.py
- MCP-verktøy: Norske navn (sok, hent_sak, finn_praksis) med norske beskrivelser
- SQL-migrasjoner: Kjøres via Supabase MCP `apply_migration`, ikke lokale filer
- Referansekode: `../paragraf/` har tilsvarende arkitektur for Lovdata — bruk som mal

## Rettslig analyse — to-lagsmodell

Prosjektet produserer rettslig analyse i to lag (se `docs/metode-rettslig-analyse.md` for full metodebeskrivelse):

1. **Problemdrevne notater** (`docs/notat-*.md`) — dybdeanalyse av konkrete rettsspørsmål. Systematisk søk → kategorisering → analyse → funn. Selvstendig lesbare.
2. **Lovkommentarer** (`docs/kommentar-foa-*.md`) — akkumulerende referansestruktur per bestemmelse. Oppdateres med funn fra notatene.

Etter hver problemutforskning: deponer funn i relevante lovkommentarer. Skille alltid tydelig mellom gjeldende rett, rimelig tolkning og analytiske konstruksjoner.

## Vedlikehold av denne filen

Vurder om CLAUDE.md bør oppdateres når du gjør endringer som påvirker prosjektstruktur, arkitektur, konvensjoner eller arbeidsflyt. Foreslå oppdatering for brukeren ved behov.
