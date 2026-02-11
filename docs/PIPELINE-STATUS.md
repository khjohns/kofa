# KOFA Pipeline Status

Sist oppdatert: 2026-02-11

## Oversikt

| Steg | Antall | Av total | % | Merknad |
|---|---|---|---|---|
| Saker totalt | 4 652 | — | — | Fra WordPress API |
| Scraped (metadata) | 4 652 | 4 652 | 100% | |
| Har PDF-URL | 3 730 | 4 652 | 80% | |
| PDF-tekst ekstrahert | 3 670 | 4 652 | 79% | 98% av de med PDF-URL |
| Seksjonsinndelt | 3 348 | 3 670 | 91% | |
| Raw-only | 322 | 3 670 | 9% | Hovedsakelig pre-2013 |
| Referanser: lov | 3 314 | 3 670 | 90% | 25 901 enkeltref |
| Referanser: KOFA-saker | 2 435 | 3 670 | 66% | 6 602 enkeltref |
| Referanser: EU-dommer | 1 005 | 3 670 | 27% | 1 867 enkeltref, 213 unike EU-saker |
| Paragrafer (non-raw) | 139 216 | — | — | |
| Embeddings | 139 216 | 139 216 | 100% | Gemini text-embedding-004 |

## Gapanalyse

### 1. Saker uten PDF-URL: 922 saker

| Kategori | Antall |
|---|---|
| Trukket | ~300 |
| Pågående (ingen avgjørelse) | ~82 |
| Avgjort uten PDF | ~17 |
| Eldre uten PDF (2003–2005) | ~523 |

**Tiltak:** Trukne/pågående er forventet. Eldre saker fra 2003–2005 ble publisert uten PDF. Ingen handling nødvendig.

### 2. PDF med mislykket ekstraksjon: 60 saker

60 saker har `pdf_url` men ingen rader i `kofa_decision_text`. Årsfordeling: 2003–2017, med tyngde i 2008–2010.

| Utfall | Antall |
|---|---|
| Avvist | 27 |
| Brudd på regelverket | 26 |
| Ikke brudd på regelverket | 7 |

**Årsak:** Sannsynligvis skannede bilde-PDFer uten tekstlag (verifisert stikkprøve: "Amyuni PDF Converter" genererte bilde-PDF).

**Tiltak:** Krever OCR for ekstraksjon. Lav prioritet — 33 substansielle saker.

### 3. Raw-only: 322 saker med PDF men uten seksjonsinndeling

Saker der PDF-tekst ble ekstrahert, men `_split_into_paragraphs()` eller `_assign_sections()` ikke klarte å dele teksten i avsnitt med seksjoner. Kun `raw_full_text` er lagret.

**Årsfordeling:**

| År | Antall | Merknad |
|---|---|---|
| 2003 | 83 | Eldre brevformat med header/adresseblokk |
| 2004–2009 | ~35 | Blandet |
| 2010–2012 | 105 | Overgang til nyere format |
| 2013+ | ~25 | Korte avvisningssaker |

**Utfallsfordeling:**

| Utfall | Antall | Snitt tekstlengde |
|---|---|---|
| Avvist | 223 | ~7 400 tegn |
| Brudd på regelverket | 69 | ~14 900 tegn |
| Ikke brudd på regelverket | 30 | ~14 500 tegn |

**Funn:** De substansielle sakene (brudd/ikke brudd, 99 stk) HAR seksjons-nøkkelord i teksten (bakgrunn, anførsler, vurdering), men eldre PDF-format med brevhoder og manglende nummererte avsnitt gjør at splittingen feiler. Avviste saker (223 stk) mangler typisk strukturerte seksjoner.

**Tiltak:** Akseptabelt for nå. Embed-skriptet filtrerer allerede `section != 'raw'`. Mulig forbedring: fallback-seksjonering for eldre format, eller tilordne hele teksten som `vurdering`.

### 4. Referansedekning (etter full ekstraksjon)

Referanser er nå ekstrahert for alle 3 670 saker med PDF-tekst (årsfilter fjernet 2026-02-09).

**Reguleringsversjon:**

| Versjon | Antall | % |
|---|---|---|
| old (pre-2017 forskrift) | 3 348 | 45.3% |
| new (2016-forskriften) | 4 039 | 54.7% |

Integritetskontroll bestått: 0 selv-referanser, 0 `new` på pre-2016 saker, 367 dangling cross-refs (forventet).

## Neste steg

1. ~~**Embeddings**~~ — Ferdig (139 216 paragrafer, 2026-02-11)
2. ~~**IVFFlat-indeks**~~ — Ferdig (lists=100, vector_cosine_ops, 1 088 MB, 2026-02-11)
3. **Vurdere OCR** — for 60 skannede PDFer (lav prioritet)
4. **Vurdere forbedret seksjonering** — for 99 substansielle raw-only saker (lav prioritet)
