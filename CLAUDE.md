# KOFA MCP Server

MCP-server for KOFA-avgjørelser (Klagenemnda for offentlige anskaffelser). Gir Claude/LLM tilgang til ~5000 avgjørelser via Model Context Protocol.

## Arkitektur

Tre-lags med klar ansvarsfordeling:
```
CLI/MCP Server → Service → Supabase Backend
```

Deler Supabase-prosjekt (`unified-timeline`) med `../paragraf/` (Lovdata MCP). Alle tabeller prefikset `kofa_`.

## Kommandoer

```bash
# MCP-server
./venv/bin/python -m kofa serve          # stdio MCP server
./venv/bin/python -m kofa status         # Vis sync-status

# Sync pipeline
kofa sync                                # WP API → kofa_cases
kofa sync --scrape                       # HTML → metadata
kofa sync --pdf                          # PDF → kofa_decision_text
kofa sync --references                   # Regex → kofa_law/case/eu_references
kofa sync --eu-cases                     # EUR-Lex → kofa_eu_case_law
kofa sync --embeddings                   # Gemini → embeddings

# Kvalitet
./venv/bin/ruff check src/               # Linting
./venv/bin/pyright src/                   # Type-checking
```

## Testing

- Ingen test-suite — verifisering skjer via direkte SQL mot Supabase (MCP `execute_sql`)
- Lint: `ruff check src/`
- Types: `pyright src/`

## Miljøvariabler

- `SUPABASE_URL` — Supabase-prosjektets URL (kreves for sync og MCP-server)
- `SUPABASE_KEY` — Service role-nøkkel (kreves for skriveoperasjoner)
- `GEMINI_API_KEY` — Google Gemini API (kreves kun for `--embeddings`)

## Konvensjoner

- Språk: Python 3.11+, norske variabelnavn i domenelag, engelske i infrastruktur
- Formatering: ruff, line-length 100
- Arkitektur: Aldri kall Supabase direkte fra server.py — gå via service.py → supabase_backend.py
- MCP-verktøy: Norske navn (sok, hent_sak, finn_praksis) med norske beskrivelser
- Referansekode: `../paragraf/` har tilsvarende arkitektur for Lovdata — bruk som mal
