# Handoff: Vurdering av verktøy fra Legal-MCP

**Dato:** 2026-03-27
**Kontekst:** Analyse av [Mahender22/legal-mcp](https://github.com/Mahender22/legal-mcp) — en US legal MCP-server — for å identifisere verktøy vi bør innføre i KOFA MCP.

## Bakgrunn

Legal-MCP er en open-source MCP-server for US-juss med 18 verktøy fordelt på tre datakilder:
- **CourtListener** (4M+ US court opinions) — 8 verktøy
- **Clio** (practice management/fakturering) — 7 verktøy
- **PACER** (federal court filings) — 3 verktøy

KOFA MCP har 19 verktøy mot norske anskaffelsesrettskilder (KOFA-avgjørelser, EU-dommer, forarbeider).

Begge kjører som MCP-servere over stdio, men arkitekturen er ulik: Legal-MCP er en **stateless API-proxy** (ingen database), mens KOFA har en **Supabase-backend** med sync-pipeline, embeddings, og referanseekstraksjon.

## Viktig kontekst: Paragraf MCP

Paragraf MCP er et søsterprosjekt som gir tilgang til **alle norske lover og forskrifter** (770+ lover, 92 000+ paragrafer). Den deler Supabase-prosjekt med KOFA. Verktøy:

| Verktøy | Funksjon |
|---------|----------|
| `lov(lov_id, paragraf?)` | Hent lovtekst |
| `forskrift(id, paragraf?)` | Hent forskriftstekst |
| `sok(query)` | Fulltekstsøk i alle paragrafer |
| `semantisk_sok(query)` | Semantisk søk i alle paragrafer |

Paragraf MCP dekker dermed **lovtekst-oppslag** som Legal-MCP ikke har (de lenker bare til eksterne kilder).

## Sammenligning: Verktøy for verktøy

### Allerede godt dekket

| Legal-MCP | KOFA / Paragraf | Kommentar |
|-----------|-----------------|-----------|
| `search_case_law` | `sok`, `sok_avgjoerelse`, `semantisk_sok_kofa` | Vi har tre søkemodi vs. deres én |
| `get_case_details` | `hent_sak`, `hent_avgjoerelse` | Vi har seksjonert tekst, de har raw |
| `find_citing_cases` | `relaterte_saker` | Vi viser begge retninger (siterer + sitert av) |
| `find_cited_cases` | `relaterte_saker` | Dekket i samme verktøy |
| `list_available_courts` | N/A | Ikke relevant — vi har bare KOFA som instans |
| `list_reporter_abbreviations` | N/A | Norsk juss har ikke tilsvarende forkortelsessystem |

### Interessante kandidater

#### 1. `parse_legal_citations` — **Parse referanser fra fritekst**

**Hva det gjør:** Tar inn vilkårlig tekst og returnerer strukturerte juridiske referanser (Bluebook-format i US).

**Relevans for oss:** Vi har allerede referanseparsing i sync-pipelinen (`references.py`) som ekstraher lovhenvisninger, KOFA-saksnumre, EU-dommer og domstolsreferanser med regex. Men denne logikken er **kun tilgjengelig under sync** — ikke eksponert som MCP-verktøy.

**Foreslått verktøy: `parse_referanser`**
- Input: Fritekst (f.eks. et avsnitt fra en kontrakt, et juridisk notat, eller en dom)
- Output: Strukturerte referanser gruppert etter type:
  - Lover/forskrifter (f.eks. "anskaffelsesforskriften § 16-10")
  - KOFA-saker (f.eks. "2023/1099")
  - EU-dommer (f.eks. "C-19/00")
  - Norske domstoler (f.eks. "HR-2019-1801-A")
- Bonus: For hver referanse, inkluder lenke til relevant MCP-verktøy (f.eks. "Bruk `finn_praksis(lov='foa', paragraf='16-10')` for KOFA-praksis")

**Vurdering med Paragraf MCP:** Paragraf MCP gjør at referansene vi finner kan **slås opp umiddelbart** — vi kan ikke bare finne "FOA § 16-10" i teksten, men også hente selve lovteksten via `lov("foa", "16-10")`. Legal-MCP mangler denne koblingen.

**Prioritet:** Middels-høy. Nyttig for brukere som jobber med juridiske tekster og vil raskt identifisere relevante kilder.

#### 2. `get_case_record` — **Komplett saksmappe**

**Hva det gjør:** Returnerer alt om en sak i én visning: parter, dommere, prosesshistorikk, tilknyttede dokumenter.

**Relevans for oss:** `hent_sak` gir metadata og `relaterte_saker` gir kryssreferanser, men de er separate kall. En samlet "saksmappe"-visning kunne gi:
- Metadata (parter, utfall, dato)
- Tidslinje (klage → behandling → avgjørelse)
- Alle lovhenvisninger i saken
- Alle KOFA-kryssreferanser
- Alle EU-dom-referanser
- Innholdsfortegnelse for avgjørelsesteksten

**Prioritet:** Lav-middels. Praktisk, men kan oppnås ved å kalle `hent_sak` + `relaterte_saker` separat. LLM-en gjør dette allerede naturlig.

### Ikke relevant

| Legal-MCP | Hvorfor ikke |
|-----------|-------------|
| Clio-verktøy (7 stk) | Practice management/fakturering — helt annet domene |
| PACER-verktøy (3 stk) | Federal court filings — ingen norsk ekvivalent tilgjengelig |

### Verktøy vi har som Legal-MCP mangler

Det er verdt å merke seg at KOFA MCP allerede har flere avanserte funksjoner Legal-MCP ikke tilbyr:

| KOFA-verktøy | Funksjon | Legal-MCP? |
|--------------|----------|------------|
| `semantisk_sok_kofa` | Vektorsøk med embeddings | Nei |
| `finn_praksis(paragrafer=[...])` | AND-søk på tvers av lovhenvisninger | Nei |
| `mest_siterte` / `mest_siterte_eu` | Autoritetsanalyse | Nei |
| `statistikk` | Aggregert statistikk | Nei |
| `hent_eu_dom` | EU-domstekst integrert | Nei |
| Forarbeider-verktøy (4 stk) | Lovforarbeid-tilgang | Nei |
| Seksjonert tekst | Innledning/bakgrunn/vurdering/konklusjon | Nei |

## Anbefaling

### Gjør nå
Ingenting haster. Legal-MCP bekrefter at vi har god dekning.

### Vurder å bygge
1. **`parse_referanser`** — Eksponere eksisterende regex-logikk som MCP-verktøy. Lav innsats, nyttig for brukere som limer inn juridisk tekst. Spesielt kraftig i kombinasjon med Paragraf MCP som kan slå opp lovteksten direkte.

### Vurder som forbedring
2. **MCP Resources** — Legal-MCP bruker MCP-ressurser (`legal://courts/federal`, `legal://citation-guide`) for statisk referansedata. Vi kunne tilby `kofa://sakstyper`, `kofa://søketips`, `kofa://lov-forkortelser` som kontekstressurser.

### Ikke prioriter
3. Saksmappe-verktøy — LLM-en håndterer dette fint med eksisterende verktøy.
4. Practice management — utenfor scope.

## Neste steg

En ny instans bør:
1. Lese dette dokumentet
2. Se på eksisterende referanselogikk i sync-pipelinen: `src/kofa/references.py`
3. Vurdere om `parse_referanser` bør bygges som et MCP-verktøy
4. Vurdere om Paragraf MCP allerede dekker behovet (brukeren kan jo bare be LLM-en tolke referansene direkte)
5. Se på MCP Resources-spesifikasjonen for statisk kontekstdata
