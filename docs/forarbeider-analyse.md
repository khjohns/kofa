# Forarbeider — dataanalyse og sammenhenger

Dato: 2026-02-12

## Datasett

4 forarbeider importert via TOC-basert PDF-ekstraksjon:

| Dokument | Seksjoner | Tegn | Lovrefs | EU-refs |
|---|---|---|---|---|
| Prop. 51 L (2015–2016) — gjeldende anskaffelseslov | 88 | 387k | 100 | 2 |
| Prop. 147 L (2024–2025) — ny anskaffelseslov | 161 | 461k | 142 | 4 |
| NOU 2023: 26 — ny anskaffelseslov (utredning) | 385 | 2.1M | 589 | 481 |
| NOU 2024: 9 — ny anskaffelseslov (utredning) | 552 | 1.8M | 803 | 202 |
| **Totalt** | **1186** | **4.7M** | **1634** | **689** |

## Lovhenvisninger — fordeling

| Lov | Referanser | Unike §§ | Dokumenter |
|---|---|---|---|
| Anskaffelsesforskriften (FOA) | 936 | 578 | 4 |
| Anskaffelsesloven (LOA) | 299 | 56 | 4 |
| Forvaltningsloven | 212 | 160 | 3 |
| Tvisteloven | 105 | 85 | 1 (NOU 2023:26) |
| Klagenemndsforskriften | 32 | 18 | 2 |
| Sikkerhetsloven | 21 | 18 | 2 |
| Forsyningsforskriften | 16 | 14 | 3 |
| Konkurranseloven | 8 | 6 | 2 |
| Konsesjonskontraktforskriften | 4 | 3 | 1 |
| Offentleglova | 1 | 1 | 1 |

Mest refererte enkeltparagrafer:
- LOA § 5 (grunnprinsippene) — 34 refs i alle 4 dokumenter
- LOA § 4 (prinsipper) — 26 refs i alle 4 dokumenter
- LOA § 3 (virkeområde) — 17 refs i 3 dokumenter
- FOA § 24-2 (avvisning) — 14 refs i 1 dokument
- FOA § 7 — 14 refs i 3 dokumenter

## Kryssreferanser: forarbeider × KOFA-praksis

### Lovparagrafer drøftet i BÅDE forarbeider og KOFA

| Paragraf | Forarbeider-docs | KOFA-saker | Betydning |
|---|---|---|---|
| Klagenemndsforskriften § 6 | 1 | 2373 | Klagefrister/prosedyre |
| FOA § 5-1 | 1 | 982 | Kunngjøringsplikt |
| **LOA § 5** | **4** | **800** | **Grunnleggende prinsipper** |
| Klagenemndsforskriften § 9 | 2 | 764 | Klagebehandling |
| FOA § 2-1 | 2 | 710 | Terskelverdier |
| **LOA § 4** | **4** | **695** | **Anskaffelsesprinsipper** |
| LOA § 7 | 4 | 243 | Unntak |
| FOA § 9-1 | 1 | 179 | Kunngjøring |
| FOA § 3-1 | 1 | 177 | Beregning av verdi |
| LOA § 12 | 3 | 190 | Karensperiode |

LOA § 5 og § 4 skiller seg ut: drøftet i alle 4 forarbeider OG tema i
hhv. 800 og 695 KOFA-saker. Dette er kjernebestemmelsene i anskaffelsesretten.

### EU-saker sitert i BÅDE forarbeider og KOFA

| EU-sak | Forarbeider | KOFA-saker | Tema |
|---|---|---|---|
| C-19/00 (SIAC Construction) | 1 | 219 | Tildelingskriterier |
| C-448/01 | 2 | 108 | |
| C-454/06 | 2 | 93 | |
| C-368/10 | 1 | 55 | |
| C-27/15 | 2 | 36 | |
| C-27/98 (Fracasso) | 1 | 33 | Eneste tilbyder |
| C-360/96 (BFI Holding) | 1 | 29 | Offentligrettslig organ |
| C-513/99 (Concordia Bus) | 1 | 26 | Miljøkriterier |
| C-26/03 | 2 | 25 | |
| C-451/08 | 2 | 25 | |

Disse er rettskilder som er viktige nok til å omtales i forarbeidene **og**
brukes aktivt av KOFA i praksis.

## Nye EU-saker fra forarbeidene

**124 EU-saker** refereres i forarbeidene men finnes ikke i `kofa_eu_case_law`
(hverken sitert av KOFA eller allerede hentet fra EUR-Lex).

Mest refererte blant disse:

| EU-sak | Forarbeider-docs | Referanser |
|---|---|---|
| C-927/19 | 2 | 10 |
| C-395/18 | 2 | 9 |
| C-260/17 | 2 | 6 |
| C-92/00 | 2 | 6 |
| C-187/16 | 2 | 5 |
| C-697/17 | 1 | 5 |
| C-295/20 | 2 | 5 |
| C-213/07 | 2 | 5 |
| C-521/18 | 2 | 5 |
| C-66/22 | 1 | 5 |

Dette er nyere EU-praksis som lovgiver har vurdert i forberedelsen av ny
anskaffelseslov, men som KOFA ennå ikke har fått saker om. Potensielt
relevant for fremtidig KOFA-praksis.

**Estimert datamengde:** ~4 MB tekst (124 × ~34k tegn snitt). Neglisjerbart
for databasen.

## Rettskilde-triangulering

Med forarbeidene på plass kan vi nå triangulere for en gitt lovparagraf:

```
                    ┌─────────────┐
                    │  Lovtekst   │  ← Paragraf MCP
                    │  (gjeldende │
                    │   rett)     │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            │            ▼
     ┌────────────┐        │     ┌────────────┐
     │ Forarbeider│        │     │ EU-praksis │  ← EUR-Lex
     │ (lovgivers │        │     │ (EU-domst.)│
     │  vilje)    │        │     └─────┬──────┘
     └─────┬──────┘        │           │
           │               │           │
           └───────┐       │    ┌──────┘
                   ▼       ▼    ▼
              ┌─────────────────────┐
              │    KOFA-praksis     │  ← KOFA MCP
              │  (norsk anvendelse) │
              └─────────────────────┘
```

Eksempel for LOA § 5 (grunnprinsippene):
- **Lovtekst**: `lov("anskaffelsesloven", "5")` → selve bestemmelsen
- **Forarbeider**: `finn_forarbeider(lov="loa", paragraf="5")` → lovgivers intensjon (alle 4 docs)
- **KOFA-praksis**: `finn_praksis(lov="loa", paragraf="5")` → 800 saker med konkret anvendelse
- **EU-praksis**: Via KOFA-sakenes EU-referanser → EU-dimensjonen

## Forvaltningsrett-broen

212 forvaltningslov-referanser i forarbeidene viser samspillet mellom
anskaffelsesrett og forvaltningsrett. Tvisteloven (105 refs i NOU 2023:26)
tyder på at utredningen drøfter prosessuelle spørsmål grundig.

## Ny vs. gjeldende lov

Prop. 147 L (2024–2025) handler om den **nye** anskaffelsesloven som ennå
ikke er trådt i kraft. Vi har dermed forarbeidene til fremtidig rett — nyttig
for å forstå endringene som kommer.

## Plassbruk i Supabase

| Tabell | Størrelse |
|---|---|
| `kofa_decision_text` (embeddings) | 2.5 GB |
| `lovdata_sections` (embeddings) | 2.2 GB |
| Forarbeider (4 tabeller) | 14 MB |
| Øvrige kofa-tabeller | ~45 MB |
| **Total database** | **4.8 GB** |

Embeddings dominerer plassbruken. Forarbeider-embeddings (1186 seksjoner)
vil legge til anslagsvis 50–100 MB med indekser.

124 nye EU-dommer fra forarbeidene: ~4 MB tekst.
