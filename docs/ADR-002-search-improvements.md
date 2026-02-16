# ADR-002: Forbedringer basert på juridisk søkeøvelse

Dato: 2026-02-09

## Kontekst

Under en juridisk søkeøvelse kartla vi om en leverandør kan støtte seg på en annen
virksomhets kvalitetsstyringssystem for å oppfylle kvalifikasjonskrav etter FOA § 16-7.

Konklusjonen var klar fra lovteksten: § 16-10(1) viser kun til § 16-3 (økonomisk
kapasitet) og § 16-5 (tekniske kvalifikasjoner), ikke § 16-7 (kvalitetssikrings-
standarder). Tilsvarende i EU-direktivet: artikkel 63 viser til artikkel 58(3) og 58(4),
ikke artikkel 62. Ingen KOFA-sak drøfter spørsmålet eksplisitt.

Øvelsen avdekket fem forbedringsmuligheter i MCP-verktøyene, et robusthetsproblem
i paragraf MCP, og en strategi for 322 raw-only saker i KOFA-pipelinen.

## Observasjon 1: Lovhenvisning-filtrering i KOFA-søk

**Problem:** `finn_praksis` støtter fritekst og metadata-filtre, men ikke filtrering på
lovhenvisninger. Under øvelsen var den mest effektive søkestrategien «finn saker som
refererer § 16-10» — dette krevde rå SQL mot `kofa_law_references`.

**Forslag:** Legg til valgfri parameter `paragraf` i `finn_praksis` som filtrerer på
`kofa_law_references.law_section`. Eksempler:

- `paragraf: "§ 16-10"` — alle saker som refererer § 16-10
- `paragraf: ["§ 16-10", "§ 16-7"]` — saker som refererer begge (AND)
- Kombinert med fritekst: `query: "kvalitetssikring", paragraf: "§ 16-10"`

**Implementering:**
- `supabase_backend.py`: Utvid `search_cases()` med JOIN mot `kofa_law_references`
- `service.py`: Normaliser paragraf-input (fjern «§», håndter aliaser)
- `server.py`: Legg til parameter i `finn_praksis`-verktøyet
- Indeks: `kofa_law_references(law_section, sak_nr)` finnes allerede

**Kompleksitet:** Lav. Lovhenvisninger er allerede ekstrahert og lagret.

## Observasjon 2: Kryssreferanser mellom lovbestemmelser (paragraf MCP)

**Problem:** Det viktigste funnet i øvelsen — at § 16-10 ikke viser til § 16-7 — krevde
manuell lesing av lovteksten. Paragraf MCP har lovteksten i `lovdata_sections`, men
ingen strukturert kobling mellom bestemmelser.

**Forslag:** Ekstraher og lagr interne kryssreferanser fra lovtekst.

**Mulige verktøy:**
- `finn_kryssreferanser(paragraf)` — «hvilke bestemmelser refererer § 16-10 til?»
- `finn_referert_av(paragraf)` — «hvilke bestemmelser refererer til § 16-7?»

**Implementering:**
- Ny tabell `lovdata_cross_references(from_doc_id, from_section_id, to_doc_id, to_section_id, raw_text)`
- Regex-ekstraksjon fra `lovdata_sections.content` (tilsvarende KOFAs referanseekstraksjon)
- Utfordring: Referanser mellom ulike lover (FOA → anskaffelsesloven → EU-direktiv)

**Kompleksitet:** Middels. Krever regex for å parse «jf. § X-Y», «som nevnt i § X»,
«jf. artikkel X» osv. Kryssreferanser mellom lover er mer komplekst enn innen én lov.

## Observasjon 3: EU-direktiver og forordninger

**Problem:** For anskaffelsesrett er EU-direktiv 2014/24/EU den primære rettskilden
bak den norske forskriften. Under øvelsen måtte vi hente direktivteksten fra web for
å verifisere at § 16-10/artikkel 63 ikke dekker § 16-7/artikkel 62.

**Tilgjengelige API-er:**

| Kilde | Type | Auth | Merknad |
|---|---|---|---|
| CELLAR SPARQL | `http://publications.europa.eu/webapi/rdf/sparql` | Nei | Full metadata + relasjoner, RDF/SPARQL |
| CELLAR REST | `https://publications.europa.eu/resource/cellar/{uuid}` | Nei | Innhold per dokument (HTML/PDF/Formex) |
| EUR-Lex Web Service | SOAP | Registrering | Søk tilsvarende expert search, XML-svar |
| EUR-Lex Data Dump | Bulk | EU Login | Alle gjeldende rettsakter per språk |
| legislation.gov.uk | HTML per artikkel | Nei | Rene enkeltsider, men UK post-Brexit |

**Forslag:** Importer de mest sentrale EU-direktivene for anskaffelsesrett i
`lovdata_sections` (eller ny tabell `eu_legislation_sections`):

- Direktiv 2014/24/EU (klassisk sektor) — ~100 artikler
- Direktiv 2014/25/EU (forsyningssektoren) — ~100 artikler
- Eventuelt: Direktiv 89/665/EØF (håndhevelsesdirektivet)

**Implementeringsstrategi — innhenting av direktivtekst:**
1. Bruk CELLAR REST API for å hente HTML-innhold per CELEX-nummer
2. Parse HTML til artikkel-nivå (tilsvarende lovdata-scraping)
3. Lagre i Supabase med `dok_id = 'directive/2014-24-EU'`, `section_id = '63'`

Kompleksitet: Lav. Volumet er lite (noen hundre artikler). Vedlikehold er lavt —
direktivene endres sjelden.

**Hovedutfordring — kobling mellom norsk rett og EU-rett:**

Selve direktivteksten er enkel å hente. Det vanskelige er å etablere en strukturert
kobling mellom norsk gjennomføringslov/-forskrift og EU-direktivartikler. Det finnes
ingen maskinlesbar kilde for dette:

- **Lovteksten** inneholder ikke referanser til EU-artikler
- **Lovdata API/XML** har ikke seksjon-til-artikkel-mapping
- **EUR-Lex «national transposition»** sporer gjennomføring på lovnivå
  («Norge har gjennomført 2014/24/EU via FOA»), ikke på seksjonsnivå
- **Forarbeidene** (Prop. 51 L (2015-2016), høringsdokumenter) inneholder
  typisk tabeller med «norsk bestemmelse → EU-artikkel», men kun som
  PDF/tekst, ikke strukturert data

Realistiske alternativer:

| Tilnærming | Fordel | Ulempe |
|---|---|---|
| Manuell kurasjon | Presis, pålitelig | Skalerer ikke, krever juridisk kompetanse |
| Semi-automatisk fra forarbeider | Utnytter eksisterende kilde | Forarbeider er PDF, parsing er upresist |
| Strukturlikhet (rekkefølge) | Kan automatiseres | FOA og direktivet er ikke 1:1 |
| LLM-assistert matching | Skalerer bedre | Krever kvalitetskontroll |

**Vurdering:** For et begrenset antall lover (FOA har ~200 paragrafer, direktivet
~100 artikler) er manuell kurasjon realistisk. Men det skalerer dårlig til andre
rettsområder. En pragmatisk mellomløsning er å importere direktivteksten *uten*
kobling, og la LLM-en selv slå opp i direktivet ved behov — tilsvarende det vi
gjorde i søkeøvelsen via web fetch.

**Kompleksitet samlet:** Direktivtekst: lav. Kobling til norsk rett: høy (manuell)
eller middels (uten kobling, LLM slår opp selv).

## Observasjon 4: EU-domstolspraksis referert fra KOFA

**Problem:** KOFA-avgjørelser refererer til 211 unike EU-domstolssaker (1 874
enkelthenvisninger). Disse er kun lagret som referansetekst i `kofa_eu_references`
— selve dommene er ikke tilgjengelige i systemet.

**Tilgjengelige kilder:**

| Kilde | Innhold | Tilgang |
|---|---|---|
| CELLAR SPARQL | Metadata, ECLI, relasjoner | Åpen, ingen auth |
| EUR-Lex | Fulltekst dommer (HTML) | Åpen (scraping) |
| [cellar-extractor](https://pypi.org/project/cellar-extractor/) (Python) | Metadata + fulltekst + siteringer | `pip install`, Apache 2.0 |
| CURIA | Offisiell søkemotor | Web, ingen formelt API |

`cellar-extractor` er et ferdig Python-bibliotek (Python 3.9+) som henter
EU-domstolspraksis via CELLAR SPARQL + EUR-Lex scraping. Funksjonalitet:
- Fulltekst av dommer (operative part + grounds)
- Metadata (ECLI, dato, parter, emner, Eurovoc)
- Siteringsnett mellom saker
- Multi-threaded, returnerer DataFrame/CSV/JSON

**Forslag:** Hent fulltekst for de 211 EU-sakene referert fra KOFA-avgjørelser.

**Implementering:**
1. Hent liste over unike EU-saker fra `kofa_eu_references`
2. Bruk `cellar-extractor` for å hente fulltekst + metadata per sak
3. Lagre i ny tabell `eu_case_law(ecli, case_number, date, parties, full_text, ...)`
4. Koble til `kofa_eu_references` via saksnummer/ECLI
5. Gjør tilgjengelig i KOFA MCP — f.eks. «vis EU-dommen KOFA refererer til»

**Fordel vs. EU-direktiver:** Koblingen mellom KOFA og EU-domstolen er allerede
etablert gjennom de ekstraherte referansene i `kofa_eu_references`. Det er ingen
mappingutfordring — vi vet nøyaktig hvilke 211 saker det gjelder.

**Kompleksitet:** Lav. Volumet er lite (211 saker), Python-pakke finnes,
koblingen er allerede på plass.

## Observasjon 5: Negativt søk / fravær av praksis

**Problem:** At vi *ikke* fant noen KOFA-sak som drøfter § 16-10 + § 16-7 var selve
konklusjonen. MCP-verktøyene er designet for å returnere treff, ikke dokumentere
fravær av praksis.

**Vurdering:** Dette er vanskelig å løse generelt. En mulig tilnærming er at
`finn_praksis` returnerer et eksplisitt «0 treff»-resultat med kontekst:

> «Ingen saker funnet som refererer både § 16-10 og § 16-7. Det finnes 15 saker
> med § 16-10 og 1 sak med § 16-7 separat.»

Dette gir brukeren (LLM-en) informasjon om at fraværet er reelt og ikke bare et
søkeproblem.

**Kompleksitet:** Lav. Krever bare at «ingen treff»-responsen berikes med
naboløfter (hva finnes for hver enkelt parameter separat).

## Observasjon 6: Opphevede lover i paragraf MCP

**Problem:** Når en lov erstattes av en ny med samme kortnavn (f.eks. ny
anskaffelsesforskrift), håndterer ikke paragraf MCP dette korrekt.

**Nåværende oppslag-kjede (3 lag):**
1. **Hardkodede aliaser** (`LOV_ALIASES`) — `"foa"` → `"FOR-2016-08-12-974"` — fast,
   men blir utdatert når loven erstattes
2. **`_find_document()`** — søker `lovdata_documents` på `dok_id` (eksakt), deretter
   `short_title` (ILIKE) — ved to treff (gammel + ny) velger `_best_title_match()`
   basert på tittel-score, men vet ikke hvilken som er gjeldende
3. **Fuzzy matching** (`pg_trgm`) — fallback for skrivefeil

**Hvorfor opphevede lover ikke fjernes:**
- Lovdata public API leverer `gjeldende-lover.tar.bz2` og
  `gjeldende-sentrale-forskrifter.tar.bz2` — kun gjeldende lover
- Sync-prosessen gjør **upsert** — nye dokumenter legges til, men gamle slettes
  aldri og markeres ikke som opphevet
- Resultat: Opphevet lov ligger i databasen side om side med den nye

**Ingen opphevelsesstatus i datamodellen:** `lovdata_documents` har `date_in_force`
men ingen `date_repealed`, `is_current`, eller tilsvarende.

**Forslag:**

1. **Legg til `is_current boolean DEFAULT true`** på `lovdata_documents`
2. **Ved sync:** Før upsert, sett `is_current = false` for alle dokumenter av
   aktuell `doc_type`. Etter upsert fra gjeldende-pakken er alle dokumenter i
   filen `is_current = true` (via upsert). Dokumenter som ikke lenger er i filen
   forblir `is_current = false`.
3. **Oppdater `_find_document()`**: Prioriter `is_current = true` ved flere treff
   på `short_title`
4. **Oppdater `_best_title_match()`**: Gi høyere score til gjeldende lover
5. **Eventuelt:** Vis `(opphevet)` i MCP-respons for gamle lover, slik at
   LLM-en kan informere brukeren

**Aliaser:** `LOV_ALIASES` bør ideelt sett erstattes med et database-oppslag
(`lovdata_documents.short_title` + `is_current`), men hardkodede aliaser fungerer
som fallback og er enkle å oppdatere manuelt. Kan beholdes som cache.

**Kompleksitet:** Lav. Endring i sync-logikk + ny kolonne + prioritering i oppslag.

## Observasjon 7: Fallback-seksjonering for raw-only saker

**Problem:** 322 saker har ekstrahert PDF-tekst men kun `raw_full_text` — seksjonsinndelingen
feilet. Embed-skriptet filtrerer `section != 'raw'`, så disse sakene blir ikke embeddet.

**Fordeling:**

| Kategori | Antall | Merknad |
|---|---|---|
| Avvist | 223 | Typisk korte, mangler strukturerte seksjoner |
| Brudd på regelverket | 69 | Substansielle, ~14 900 tegn snitt |
| Ikke brudd på regelverket | 30 | Substansielle, ~14 500 tegn snitt |

De 99 substansielle sakene (brudd/ikke brudd) **har** seksjons-nøkkelord i teksten
(«bakgrunn», «anførsler», «vurdering»), men eldre PDF-format med brevhoder og
manglende nummererte avsnitt gjør at `_split_into_paragraphs()` / `_assign_sections()`
feiler. Årsfordeling: hovedsakelig 2003–2012.

**Beslutning:** Alternativ 2 — fallback-seksjonering med nøkkelorddeteksjon.

**Implementering:**
1. Legg til fallback i `pdf_extractor.py` for saker der vanlig seksjonering feiler
2. Bruk regex for å finne seksjons-nøkkelord (bakgrunn, anførsler, vurdering) i
   `raw_full_text` og del teksten på disse punktene
3. Tilordne tekst mellom nøkkelord til riktig seksjon
4. For avviste saker (223 stk) uten nøkkelord: behold som `raw` — disse er korte
   og har begrenset substansielt innhold
5. Kjør etter hoved-embedding-kjøringen (~120 000 paragrafer), som eget steg

**Forventet resultat:** ~99 substansielle saker får seksjonsinndeling og kan embeddes.
223 avviste saker forblir `raw` (akseptabelt — kort tekst, lite substansielt innhold).

**Kompleksitet:** Lav. Nøkkelordene er kjente, regex-logikk tilsvarende eksisterende
`_assign_sections()`. Hovedforskjellen er at teksten ikke allerede er delt i avsnitt.

## Observasjon 8: Norsk rettspraksis referert fra KOFA

**Problem:** KOFA-avgjørelser refererer hyppig til norsk rettspraksis — særlig
Høyesterett og lagmannsrettene. Disse referansene er verken ekstrahert eller
lagret strukturert, og selve rettsavgjørelsene er ikke tilgjengelige i systemet.

**Omfang — kartlagt fra `kofa_decision_text`:**

| Domstolsnivå | Unike saker | Totale referanser | Referanseformat |
|---|---|---|---|
| Lagmannsrett | 110 | 644 | `L[A-H]-ÅÅÅÅ-NNNNN` |
| Høyesterett (gammel) | ~40-50 | 610 | `Rt. ÅÅÅÅ s. NNNN` / `Rt-ÅÅÅÅ-NNNN` |
| Høyesterett (ny) | 14 | 294 | `HR-ÅÅÅÅ-NNNN-X` |
| Tingrett | 9 | 16 | `T[XXXX]-ÅÅÅÅ-NNNNN` |
| **Totalt** | **~170** | **~1 564** | |

560 KOFA-saker (av ~4 650) inneholder minst én domstolsreferanse.

**Fordeling lagmannsrett per domstol:**

| Lagmannsrett | Unike saker | Mest siterte |
|---|---|---|
| Borgarting (LB) | 50 | LB-2019-85112 (71 KOFA-saker) |
| Hålogaland (LH) | 28 | LH-2018-99424 (13) |
| Eidsivating (LE) | 14 | LE-2005-183161 (23) |
| Agder (LA) | 7 | LA-2012-85717 (12) |
| Gulating (LG) | 6 | LG-2017-28938 (10) |
| Frostating (LF) | 5 | LF-2014-32160 (11) |

**Tilgjengelige kilder for fulltekst:**

| Kilde | Dekning | Tilgang | Juridisk status |
|---|---|---|---|
| domstol.no | Kun Høyesterett (PDF) | Åpen, forutsigbar URL | Offentlig organ, offentleglova |
| Lovdata (gratis) | HR 2008+, lagmannsrett 2008+, tingrett 2016+ | HTML, ingen API | Privat stiftelse, men offentlige dokumenter |
| Lovdata API (ny 2025) | Kun lover/forskrifter | Gratis, NLOD 2.0 | Rettsavgjørelser *ikke* inkludert |

For **Høyesterett** ligger PDF-er på domstol.no med forutsigbar URL:
`/globalassets/upload/hret/avgjorelser/{år}/{måned}/{hr-nummer}.pdf`
— men månedsmappen varierer og kan ikke utledes fra saksnummeret.

For **lagmannsrett** er Lovdata eneste realistiske kilde. URL-mønster:
`lovdata.no/dokument/{DOMSTOLKODE}/avgjorelse/{saksnummer}` (f.eks. `LBSIV`, `LBSTR`).

**Juridisk vurdering — Lovdata-scraping forkastet, innsynsbegjæring valgt:**

Opprinnelig plan var å hente lagmannsrettsavgjørelser fra Lovdata med crawl-delay.
Etter nærmere vurdering er dette **forkastet** av tre grunner:

1. **Brukervilkår:** Lovdata forbyr eksplisitt massenedlasting *og* bruk av innhold
   i KI/AI-verktøy (inkl. RAG/MCP). For lover/forskrifter tilbyr de API med
   NLOD 2.0 og inviterer til «eksperimentering og forskning med KI», men
   rettsavgjørelser er uttrykkelig unntatt.
2. **Databasevern:** Høyesterett (HR-2019-1725-A) fastslo i Lovdata vs.
   Rettspraksis.no at Lovdatas databaser er vernet etter åndsverkloven § 24.
   Selv om den saken gjaldt bulk-kopiering av 40 000 avgjørelser, rammer
   bestemmelsen også «gjentatte uttrekk av uvesentlige deler» som til sammen
   utgjør en vesentlig del.
3. **Lovdatas KI-posisjon:** Lovdata har lansert Lovdata Pro 2 med eget KI-søk
   (2025), og inngår kommersielle KI-avtaler med advokatfirmaer. En MCP-tjeneste
   som bruker Lovdata-innhold vil sannsynligvis ses som konkurrerende virksomhet.

**Valgt tilnærming — innsynsbegjæring til lagmannsrettene:**

Rettsavgjørelser er offentlige dokumenter (tvisteloven § 14-2). Ved å innhente
dem direkte fra domstolene via innsynsbegjæring unngår vi Lovdatas brukervilkår
og databasevern fullstendig. Det innhentede materialet kan fritt brukes i KI.

Praktisk gjennomføring:
- Send én samlet innsynsbegjæring per lagmannsrett med liste over saksnumre
- 6 lagmannsretter å kontakte (Borgarting ~50, Hålogaland ~28, Eidsivating ~14,
  Agder ~7, Gulating ~6, Frostating ~5)
- Be om avgjørelsene i digital form (PDF eller tekstformat)
- Eldre Høyesterettsdommer (Rt.-format, pre-2008) kan innhentes fra Høyesterett

**Sammenligning med observasjon 4 (EU-domstolspraksis):**

| | EU-domstol | Norsk rettspraksis |
|---|---|---|
| Unike saker | 211 | ~170 |
| Totale referanser | 1 874 | ~1 564 |
| Kobling til KOFA | Allerede i `kofa_eu_references` | Må ekstraheres først |
| Fulltekstkilde | CELLAR/EUR-Lex (åpent API) | domstol.no (HR) + innsynsbegjæring (lagmannsrett) |
| Python-bibliotek | `cellar-extractor` | Ingen — custom scraper |

**Forslag — tre steg:**

**Steg 1: Ekstraher referanser fra KOFA-tekst (lav kompleksitet)**
1. Utvid `reference_extractor.py` med `CourtReference`-dataklasse
2. Regex for `HR-ÅÅÅÅ-NNNN-X`, `Rt. ÅÅÅÅ s. NNNN`, `L[A-H]-ÅÅÅÅ-NNNNN`,
   `T[XXXX]-ÅÅÅÅ-NNNNN` — med normalisering av Rt-formatvarianter
3. Ny tabell `kofa_court_references(sak_nr, court_case_id, court_name,
   court_level, paragraph_number, context, raw_text)`
4. Kjør referanseekstraksjon på eksisterende `kofa_decision_text`

**Steg 2: Hent fulltekst (middels kompleksitet)**
1. Høyesterett (HR-): Hent PDF fra domstol.no — uproblematisk, ~14 saker
2. Lagmannsrett: Innsynsbegjæring til 6 lagmannsretter — ~110 saker
3. Eldre Høyesterett (Rt.): Innsynsbegjæring til Høyesterett — ~40-50 saker
4. Ny tabell `court_case_law(case_id, court, court_level, date, parties,
   full_text, source_url, fetched_at)`
5. PDF-ekstraksjon med eksisterende `pdf_extractor.py`

**Steg 3: Gjør tilgjengelig via MCP**
1. Nytt verktøy eller utvid eksisterende for å slå opp refererte dommer
2. Koble til `finn_praksis` — «vis rettsavgjørelsene KOFA bygger på»

**Kompleksitet:** Steg 1: lav (tilsvarende EU-referanseekstraksjon). Steg 2:
middels (innsynsbegjæring er manuell prosess, men teknisk enkel når materiale
er mottatt — PDF-ekstraksjon). Steg 3: lav.

## Prioritering

| # | Tiltak | System | Kompleksitet | Verdi | Status |
|---|---|---|---|---|---|
| 6 | Håndtering av opphevede lover | paragraf | Lav | Høy | **Ferdig** — `is_current`-kolonne + sync-logikk (`e0247fb` i paragraf) |
| 1 | Lovhenvisning-filter i `finn_praksis` | kofa | Lav | Høy | **Ferdig** — `paragrafer`-parameter med AND-semantikk |
| 4 | EU-domstolspraksis (211 saker) | kofa | Lav | Høy | **Ferdig** — 191 dommer hentet, 43 feil-IDer løst (joined cases, CO-fallback, korreksjoner). ~8 nye etter neste sync |
| 8a | Norsk rettspraksis — referanseekstraksjon | kofa | Lav | Høy | **Ferdig** — `kofa_court_references`-tabell, regex for HR/Rt/lagmannsrett/tingrett |
| 8b | Norsk rettspraksis — fulltekst (HR + lagmannsrett) | kofa | Middels | Høy | HR fra domstol.no (klar), lagmannsrett via innsynsbegjæring (avventer svar) |
| 7 | Fallback-seksjonering (99 saker) | kofa | Lav | Middels | Etter hoved-embedding |
| 5 | Berik «ingen treff»-respons | kofa | Lav | Middels | **Ferdig** — implementert sammen med #1 |
| 3a | EU-direktivtekst (uten kobling) | paragraf | Lav | Middels | Gjør når paragraf utvides |
| 2 | Kryssreferanser i lovdata | paragraf | Middels | Høy | Større oppgave, planlegg separat |
| 3b | Kobling norsk rett ↔ EU-artikler | paragraf | Høy (manuell) | Høy | Vurder for FOA alene først |

## Gjennomført — endringslogg

### 2026-02-09: Observasjon 1 + 5 — paragraffilter og «ingen treff»

- `finn_praksis` har ny `paragrafer`-parameter med AND-semantikk (`6baf914`)
- «Ingen treff»-respons berikes med naboløfter (hva finnes per enkeltparameter)

### 2026-02-10: Lovhenvisning-regex — kvalitetsforbedring

Tre regex-feil i `reference_extractor.py` førte til at ~65% av lovhenvisninger ble
oversett (`ad13962`):

| Problem | Eksempel | Årsak |
|---|---|---|
| Kortformer uten prefiks | «forskriften § 16-10» | `+` krevde tegn før suffiks, endret til `*` |
| Del-referanser | «forskriften del III § 16-10» | Manglet mønster for romertalls-del |
| Parentes uten mellomrom | «§ 16-10(5)» | Krevde whitespace før parentes |

Målt forbedring: § 16-10-dekning 30%→89%, § 24-2 26%→94%, § 24-8 29%→91%.

Nynorske former (forskrifta, lova) lagt til i `LAW_ALIASES`.

Gjenstående gap dokumentert i `docs/TODO-referanseekstraksjon.md` — hovedsakelig
bare §-referanser uten lovnavn (problem D), der lovnavn-propagering er anbefalt
tilnærming.

### 2026-02-10: Prefiksmatching i finn_praksis

`finn_praksis` brukte eksakt match mot `law_section` — slik at `§ 16-10` kun fant
2 treff i stedet for 15 (som inkluderer `§ 16-10 (1)`, `§ 16-10 første ledd` osv.)
(`fe43bed`). Endret til OR-filter: eksakt match *eller* starts-with-space.

### 2026-02-10: Observasjon 8a — norsk rettspraksis-referanser

Referanseekstraksjon for norske domstolsavgjørelser implementert (`64f6ad2`):

- `CourtReference`-dataklasse i `reference_extractor.py`
- Regex for HR-ÅÅÅÅ-NNNN-X, Rt. ÅÅÅÅ s. NNNN, L[A-H]-ÅÅÅÅ-NNNNN, T[XXXX]-ÅÅÅÅ-NNNNN
- Normalisering av Rt-formatvarianter til kanonisk form
- `kofa_court_references`-tabell med migrasjon
- Integrert i sync-pipeline (`kofa sync --references`)

### 2026-02-10: Observasjon 4 — EU-domstolspraksis fra EUR-Lex

Fulltekst for EU-dommer referert i KOFA hentet fra EUR-Lex HTML (`7d0a219`):

**Resultat:** 191 av 208 unike EU-saker hentet initialt (se oppdatering 2026-02-16
for de resterende 43 som ga 404).

**Designvalg vs. opprinnelig plan:**

| Beslutning | Plan (ADR) | Faktisk |
|---|---|---|
| Kilde | `cellar-extractor` Python-pakke | Direkte EUR-Lex HTML — SPARQL viste seg flaky, cellar-extractor er bulk-API |
| Metadata | CELLAR SPARQL | `<meta name="DC.*">` fra HTML head — kun tilgjengelig i eldre format (pre-~2012) |
| Lagring | Én rad per sak, full tekst | Som planlagt — `kofa_eu_case_law` tabell |
| Seksjonering | Lagret i DB | On-the-fly i service-lag via tekstmarkører |
| Språk | Engelsk, FR fallback | Som planlagt — alle 191 funnet på EN |

**Implementering:**

- `eurlex_fetcher.py` (ny): `case_id_to_celex()` konvertering (C-/T- → CELEX),
  HTML-parsing for begge EUR-Lex-formater (gammel `TexteOnly`-div + ny CSS),
  DC-metadata-ekstraksjon, EN→FR fallback ved 404
- `supabase_backend.py`: `sync_eu_case_law()` (set difference, 10s delay,
  graceful shutdown), `get_eu_case_law()`, pipeline-stats
- `service.py`: `hent_eu_dom(eu_case_id, seksjon?)` med on-the-fly seksjonering
  via "JUDGMENT OF THE COURT" / "Grounds" / "On those grounds" / "Operative part"
- `server.py`: Nytt MCP-verktøy `hent_eu_dom`, oppdatert `SERVER_INSTRUCTIONS`
- `cli.py`: `kofa sync --eu-cases`
- Migrasjon: `kofa_eu_case_law` tabell med RLS

**Metadata-dekning:** 53 av 191 dommer har `case_name` og `subject` (eldre format
med DC-meta-tags). Nyere format (post-~2012) mangler disse — kan eventuelt
berikes fra teksten eller CELLAR SPARQL i fremtiden.

### 2026-02-12: Forarbeider — lovforarbeider som ny rettskilde

Forarbeider (proposisjoner, NOU-er) er sentrale rettskilder for tolkning av
anskaffelsesregelverket. Fire dokumenter importert via PyMuPDF TOC-basert
chunking (`05ba92b`):

| Dokument | Seksjoner | Tegn | Lovrefs | EU-refs |
|---|---|---|---|---|
| Prop. 51 L (2015–2016) — anskaffelsesloven | 88 | 387k | 100 | 2 |
| Prop. 147 L (2024–2025) — ny anskaffelseslov | 161 | 461k | 142 | 4 |
| NOU 2023: 26 — ny anskaffelseslov | 385 | 2.1M | 589 | 481 |
| NOU 2024: 9 — ny anskaffelseslov | 552 | 1.8M | 803 | 202 |
| **Totalt** | **1186** | **4.7M** | **1634** | **689** |

**Designvalg:**

| Beslutning | Valg | Begrunnelse |
|---|---|---|
| Chunking | TOC-entry-nivå | PDFenes innebygde innholdsfortegnelse gir naturlig hierarkisk struktur (3–4 nivåer) |
| Lagring | To tabeller (`kofa_forarbeider` + `kofa_forarbeider_sections`) | Per-seksjon embeddings for semantisk søk over 1186 entries |
| Referanseekstraksjon | Gjenbruk `ReferenceExtractor` | Samme regex som KOFA-avgjørelser — trekker ut lov- og EU-referanser |
| MCP-verktøy | Separate fra KOFA-praksis | `finn_forarbeider` (lovoppslag) adskilt fra `finn_praksis` (KOFA-saker) |

**4 MCP-verktøy:**
- `hent_forarbeide` — browse/les (TOC + seksjonstekst)
- `sok_forarbeider` — fulltekstsøk med norsk stemming
- `semantisk_sok_forarbeider` — hybrid vektor+FTS (krever embeddings)
- `finn_forarbeider` — finn seksjoner som refererer en gitt lovparagraf

**Kobling til observasjon 3b (EU-kobling):** Forarbeidene inneholder tabeller
som mapper norske bestemmelser til EU-artikler. Referanseekstraksjon fanger
lovhenvisninger, men ikke EU-artikkel-koblingen. Dette gjenstår som fremtidig
forbedring — semi-automatisk ekstraksjon fra forarbeider-tekst.

### 2026-02-16: Observasjon 4 — 43 EU-saker med 404 fra EUR-Lex

Undersøkt alle 43 EU-saker som returnerte 404 ved første sync (`390b437`).
Tre rotårsaker identifisert:

| Årsak | Antall | Løsning |
|---|---|---|
| Feil saks-ID fra PDF-ekstraksjon | 12 | `_EU_CASE_CORRECTIONS` i `reference_extractor.py` |
| Joined case (tekst under primær-ID) | 19 | `_JOINED_CASE_MAP` i `eurlex_fetcher.py` |
| Order (CO-suffiks, ikke CJ) | 6 | Automatisk CO-fallback i `fetch()` |
| Genuint mangler | 4 | Logges som skipped |
| Edge cases (ukjent CELEX-format) | 2 | Avventer — C-424/01 og C-574/12 |

**Feil-IDer (12 stk):** PDF-ekstraksjon fra KOFA-avgjørelser ga feil saksnumre
(transponerte siffer, feil årstall, trunkerte år). Korrigert i
`_EU_CASE_CORRECTIONS` som virker ved `kofa sync --references`. Alle 12 korrekte
IDer finnes allerede i `kofa_eu_case_law` fra andre KOFA-saker som siterte riktig.

**Joined cases (19 stk):** EUR-Lex publiserer dommen kun under primær-saksnummer
(laveste nummeret). Ny `_JOINED_CASE_MAP` i `eurlex_fetcher.py` redirecter
sekundær → primær ved henting. 18 av 19 primære IDer allerede i DB.

**Orders (6 stk):** Kjennelser bruker CO-suffiks i CELEX i stedet for CJ.
`fetch()` refaktorert til å prøve CJ først, deretter CO ved 404. Disse 6 er
alle fra forarbeider-referanser og utgjør genuint nytt innhold.

**Ny arkitektur i `eurlex_fetcher.py`:**

```
fetch(eu_case_id)
  ├─ _JOINED_CASE_MAP? → fetch(primary_id), lagre under sekundær-ID
  ├─ case_id_to_celex(CJ) → _fetch_celex()
  ├─ 404? → case_id_to_celex(CO) → _fetch_celex()  (CO-fallback)
  └─ _fetch_celex: 404 EN? → retry FR                (språk-fallback)
```

**Etter neste sync (~8 genuint nye tekster):**

| EU-sak | Type | Kilde |
|---|---|---|
| C-197/11 (Libert) | Primær for joined C-203/11 | kofa |
| C-6/05 (Medipac) | Korrigert fra C-6/0 | kofa |
| C-89/19 (Rieco) | Order (CO) + primær for C-91/19 | forarbeider |
| C-244/02 (Kauppatalo Hansel) | Order (CO) | forarbeider |
| C-54/18 (Coop. Animazione Valdocco) | Order (CO) | forarbeider |
| C-787/21 (Estaleiros Navais) | Order (CO) | forarbeider |
| C-492/06 (Consorzio Elisoccorso) | Order (CO) | forarbeider |
| C-35/15 (Comm. v Vanbreda) | Order (CO) | forarbeider |

Pluss 19 duplikat-rader for joined cases (lagret under sekundær-ID).

**Viktig rekkefølge:** `kofa sync --references` **må** kjøres før `--eu-cases`
for at feil-ID-korreksjoner skal virke. Uten dette vil 6 feil-IDer med gyldige
CELEX-numre (C-91/00, C-57/92, C-20/04, C-458/02, C-394/03, C-448/07) hente
*feil dom* fra EUR-Lex.
