# KOFA MCP Server

MCP server for Norwegian public procurement decisions from KOFA (Klagenemnda for offentlige anskaffelser).

## Install

```bash
pip install kofa[all]
```

## Usage

```bash
kofa sync              # Load cases from KOFA
kofa sync --scrape     # Enrich with HTML metadata
kofa serve --http      # Start HTTP MCP server
kofa status            # Show sync stats
```

## Environment

```bash
cp .env.example .env
# Set SUPABASE_URL and SUPABASE_KEY
```
