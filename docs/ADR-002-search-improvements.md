# ADR-002: Forbedringer basert på juridisk søkeøvelse

Dato: 2026-02-09

## Kontekst

Under en juridisk søkeøvelse kartla vi om en leverandør kan støtte seg på en annen
virksomhets kvalitetsstyringssystem for å oppfylle kvalifikasjonskrav etter FOA § 16-7.

Konklusjonen var klar fra lovteksten: § 16-10(1) viser kun til § 16-3 (økonomisk
kapasitet) og § 16-5 (tekniske kvalifikasjoner), ikke § 16-7 (kvalitetssikrings-
standarder). Tilsvarende i EU-direktivet: artikkel 63 viser til artikkel 58(3) og 58(4),
ikke artikkel 62. Ingen KOFA-sak drøfter spørsmålet eksplisitt.

Øvelsen avdekket fire forbedringsmuligheter i MCP-verktøyene.

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

## Observasjon 4: Negativt søk / fravær av praksis

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

## Prioritering

| # | Tiltak | Kompleksitet | Verdi | Anbefaling |
|---|---|---|---|---|
| 1 | Lovhenvisning-filter i `finn_praksis` | Lav | Høy | Gjør først |
| 4 | Berik «ingen treff»-respons | Lav | Middels | Gjør sammen med #1 |
| 3a | EU-direktivtekst (uten kobling) | Lav | Middels | Gjør når paragraf utvides |
| 3b | Kobling norsk rett ↔ EU-artikler | Høy (manuell) | Høy | Vurder for FOA alene først |
| 2 | Kryssreferanser i lovdata | Middels | Høy | Større oppgave, planlegg separat |
