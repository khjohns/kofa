# Rettskildeoversikt

**Dato:** 2026-02-16
**Status:** Levende dokument — oppdateres når pipelinen endres

Oversikt over rettskilder tilgjengelig i systemet og kjente hull. Brukes som referanse under rettslig analyse (se `docs/metode-rettslig-analyse.md`).

## Tilgjengelige kilder

### 1. KOFA-avgjørelser

| | Dekning | Tilgang |
|---|---|---|
| Metadata (parter, tema, utfall) | 4 652 saker (2003–) | `sok`, `hent_sak`, `siste_saker` |
| Avgjørelsestekst (seksjonert) | 3 348 saker | `hent_avgjoerelse` (innledning, bakgrunn, anfoersler, vurdering, konklusjon) |
| Avgjørelsestekst (kun raw) | 322 saker | `hent_avgjoerelse` (kun useksjonert fulltekst) |
| Lovhenvisninger | 25 882 enkeltref fra 3 314 saker | `finn_praksis(lov, paragraf)` |
| KOFA-kryssreferanser | 6 602 enkeltref fra 2 435 saker | `relaterte_saker` |
| EU-dom-referanser | 1 864 enkeltref, 203 unike saker | `eu_praksis` |
| Domstolsreferanser | ~1 564 enkeltref, ~170 unike saker | Ekstrahert, ikke eksponert via MCP ennå |
| Embeddings (vektorsøk) | 139 216 paragrafer | `semantisk_sok_kofa` |

**Søkeverktøy og når de brukes:**

| Verktøy | Hva det søker i | Beste for |
|---|---|---|
| `finn_praksis` | Lovhenvisninger (ekstrahert fra tekst) | "Alle saker som drøfter FOA § 8-3" |
| `sok` | Metadata (parter, tema, sammendrag) | Innklaget virksomhet, temaord |
| `sok_avgjoerelse` | Avgjørelsestekst (FTS) | Eksakte juridiske termer |
| `semantisk_sok_kofa` | Avgjørelsestekst (vektor) | Konseptuelle søk, synonymer |

### 2. EU-domstolspraksis

| | Dekning | Tilgang |
|---|---|---|
| Fulltekst (EUR-Lex) | 320 av 324 refererte dommer | `hent_eu_dom(eu_case_id, seksjon?)` |
| Metadata (parter, emne) | 53 av 320 (eldre format) | Inkludert i `hent_eu_dom` |
| Seksjoner | Sammendrag, begrunnelse, domsslutning | On-the-fly fra tekstmarkører |
| Kobling til KOFA | Via `kofa_eu_references` | `eu_praksis(eu_case_id)` |

**Begrensninger:** 4 dommer genuint mangler fra EUR-Lex (C-188/04, C-456/17, C-469/99, C-574/12). Metadata (parter, emne) kun tilgjengelig for eldre dommer (pre-~2012).

### 3. Forarbeider

| | Dekning | Tilgang |
|---|---|---|
| Prop. 51 L (2015–2016) | 88 seksjoner, 387k tegn | `hent_forarbeide`, `sok_forarbeider` |
| Prop. 147 L (2024–2025) | 161 seksjoner, 461k tegn | `hent_forarbeide`, `sok_forarbeider` |
| NOU 2023: 26 | 385 seksjoner, 2,1M tegn | `hent_forarbeide`, `sok_forarbeider` |
| NOU 2024: 9 | 552 seksjoner, 1,8M tegn | `hent_forarbeide`, `sok_forarbeider` |
| Lovhenvisninger | 1 634 enkeltref | `finn_forarbeider(lov, paragraf)` |
| EU-referanser | 687 enkeltref | Ekstrahert, ikke eksponert separat |
| Embeddings (vektorsøk) | 0 av 1 186 seksjoner | `semantisk_sok_forarbeider` — **ikke tilgjengelig ennå** |

**Begrensninger:** Semantisk søk (`semantisk_sok_forarbeider`) krever embeddings som ikke er generert. FTS (`sok_forarbeider`) og lovoppslag (`finn_forarbeider`) fungerer.

### 4. Lover og forskrifter (Paragraf MCP)

| | Dekning | Tilgang |
|---|---|---|
| Gjeldende lover | 770+ lover, 92 000+ paragrafer | `lov(lov_id, paragraf?)` |
| Gjeldende forskrifter | Sentrale forskrifter | `forskrift(id, paragraf?)` |
| FTS-søk | Alle paragrafer | `sok(query)` |
| Semantisk søk | Alle paragrafer | `semantisk_sok(query)` |
| GDPR/personvernforordningen | Via personopplysningsloven | `lov("personopplysningsloven", "Artikkel 5")` |

**Nøkkeldokumenter for anskaffelsesrett:**

| Dokument | Alias | Eksempel |
|---|---|---|
| Anskaffelsesforskriften (2016) | `foa` | `lov("foa", "16-10")` |
| Anskaffelsesloven | `loa` | `lov("loa", "4")` |
| Forsyningsforskriften | — | `lov("forsyningsforskriften")` |

**Begrensninger:** Opphevede lover kan ligge i databasen — `is_current`-flagg prioriterer gjeldende ved oppslag. Ingen kryssreferanser mellom bestemmelser (planlagt, se ADR-002 obs. 2).

## Kjente hull

### Norsk rettspraksis

| Kilde | Status | Tilgang |
|---|---|---|
| Høyesterett (HR-format, 2008+) | ~14 saker referert fra KOFA. Kan hentes fra domstol.no | Ikke i systemet |
| Høyesterett (Rt.-format, pre-2008) | ~40–50 saker referert. Krever innsynsbegjæring | Ikke i systemet |
| Lagmannsrett | ~110 saker referert. Innsynsbegjæring sendt til 6 lagmannsretter | Avventer svar |
| Tingrett | ~9 saker referert. Lav prioritet | Ikke i systemet |

Referanser er ekstrahert og lagret i `kofa_court_references`, men fulltekst er ikke tilgjengelig. Se ADR-002 obs. 8 for plan og juridisk vurdering (Lovdata-scraping forkastet, innsynsbegjæring valgt).

### EU-direktiver

| Kilde | Status |
|---|---|
| Direktiv 2014/24/EU (klassisk sektor) | Ikke i systemet — brukes via web-oppslag |
| Direktiv 2014/25/EU (forsyningssektoren) | Ikke i systemet |
| Håndhevelsesdirektivet (89/665/EØF) | Ikke i systemet |

Direktivtekst kan hentes fra CELLAR REST API (lav kompleksitet). Kobling mellom norske bestemmelser og EU-artikler er ikke-triviell — se ADR-002 obs. 3.

### Juridisk litteratur

Ikke tilgjengelig i systemet. Henvis til lovdata.no, rettsdata.no, eller fysiske kilder.

## Direkte SQL-tilgang (Supabase MCP)

KOFA og Paragraf MCP-verktøyene dekker vanlige oppslag, men under rettslig analyse er direkte SQL via Supabase MCP (`execute_sql`) ofte mer fleksibelt — spesielt for custom JOINs, interseksjonssøk, og data som ikke er eksponert via MCP-verktøy.

### Tabeller

| Tabell | Innhold | Nøkkelkolonner |
|---|---|---|
| `kofa_cases` | Metadata for alle saker | `sak_nr`, `innklaget`, `klager`, `avgjoerelse`, `sakstype`, `saken_gjelder` |
| `kofa_decision_text` | Avgjørelsestekst (paragrafnivå) | `sak_nr`, `section`, `paragraph_number`, `text`, `embedding` |
| `kofa_law_references` | Lovhenvisninger fra avgjørelser | `sak_nr`, `law_name`, `law_section`, `regulation_version` |
| `kofa_case_references` | KOFA-kryssreferanser | `from_sak_nr`, `to_sak_nr` |
| `kofa_eu_references` | EU-dom-referanser fra avgjørelser | `sak_nr`, `eu_case_id`, `eu_case_name` |
| `kofa_court_references` | Norske domstolsreferanser | `sak_nr`, `court_case_id`, `court_level`, `court_name` |
| `kofa_eu_case_law` | Fulltekst EU-dommer | `eu_case_id`, `celex`, `full_text`, `case_name` |
| `kofa_forarbeider` | Forarbeider-metadata | `doc_id`, `title`, `section_count` |
| `kofa_forarbeider_sections` | Forarbeider-seksjoner | `doc_id`, `section_number`, `title`, `text`, `embedding` |
| `kofa_forarbeider_law_refs` | Lovhenvisninger fra forarbeider | `doc_id`, `section_number`, `law_name`, `law_section` |
| `kofa_forarbeider_eu_refs` | EU-referanser fra forarbeider | `doc_id`, `section_number`, `eu_case_id` |

### RPC-funksjoner

| Funksjon | Bruk |
|---|---|
| `search_kofa(query)` | FTS i metadata |
| `search_kofa_decision_text(query, seksjon?)` | FTS i avgjørelsestekst |
| `search_kofa_decision_hybrid(query, embedding, seksjon?)` | Hybrid vektor+FTS i avgjørelsestekst |
| `search_kofa_forarbeider(query, doc_id?)` | FTS i forarbeider |
| `search_kofa_forarbeider_hybrid(query, embedding, doc_id?)` | Hybrid vektor+FTS i forarbeider |
| `kofa_most_cited()` | Mest siterte KOFA-saker |
| `kofa_most_cited_eu()` | Mest siterte EU-dommer |
| `kofa_statistics(aar?, gruppering?)` | Aggregert statistikk |

### Typiske SQL-mønstre under analyse

**Interseksjonssøk** — saker som refererer flere bestemmelser:
```sql
SELECT lr1.sak_nr
FROM kofa_law_references lr1
JOIN kofa_law_references lr2 ON lr1.sak_nr = lr2.sak_nr
WHERE lr1.law_section LIKE '§ 16-10%'
  AND lr2.law_section LIKE '§ 16-7%';
```

**Avgjørelsestekst med metadata:**
```sql
SELECT c.sak_nr, c.avgjoerelse, dt.text
FROM kofa_cases c
JOIN kofa_decision_text dt ON dt.sak_nr = c.sak_nr
WHERE dt.section = 'vurdering'
  AND dt.text ILIKE '%forpliktelseserklæring%';
```

**Domstolsreferanser** (ikke i MCP):
```sql
SELECT cr.court_case_id, cr.court_level, COUNT(*) AS kofa_refs
FROM kofa_court_references cr
GROUP BY cr.court_case_id, cr.court_level
ORDER BY kofa_refs DESC LIMIT 10;
```

