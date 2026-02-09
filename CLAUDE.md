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
  reference_extractor.py   # Regex-ekstraksjon av lov/saks/EU-referanser
  vector_search.py         # Hybrid vektor+FTS søk (KofaVectorSearch)
  scraper.py               # HTML-scraping av metadata fra kofa.no
  cli.py                   # CLI: kofa serve|sync|status
  web.py                   # Flask blueprint for HTTP MCP-transport
  _supabase_utils.py       # Delt: retry-dekorator, klient, feilklassifisering
scripts/
  embed_kofa.py            # Embedding-generering med Gemini API
docs/
  ADR-001.md               # Arkitekturbeslutninger (les denne for full kontekst)
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
kofa sync --embeddings                   # Gemini → embeddings

# Linting
./venv/bin/ruff check src/
```

## Databasetabeller (Supabase)

- `kofa_cases` — Saker med metadata og vektet FTS
- `kofa_decision_text` — Avgjørelsestekst per avsnitt med seksjon, FTS og embedding
- `kofa_law_references` — Lovhenvisninger (2017+) med lovdata_doc_id-kobling
- `kofa_case_references` — KOFA-kryssreferanser
- `kofa_eu_references` — EU-domstolsreferanser
- `kofa_sync_meta` — Sync-status og cursors

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
