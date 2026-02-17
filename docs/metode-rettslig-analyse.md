# Arbeidsmetodikk: Rettslig analyse med KOFA-databasen

**Dato:** 2026-02-10
**Status:** Levende dokument — oppdateres etter hvert som metoden modnes

## 1. To-lagsmodellen

Arbeidet produserer to typer dokumenter med ulike formål:

### Lag 1: Problemdrevne notater (juridisk teori)

Selvstendige analytiske arbeider som utforsker en konkret rettslig problemstilling i dybden. Hvert notat er et komplett forskningsprodukt.

**Eksempel:** `notat-radighet-forpliktelseserklaring.md` — utforsker forholdet mellom ESPD, forpliktelseserklæring og rådighet under FOA § 16-10.

**Kjennetegn:**
- Problemdrevet, ikke bestemmelsesdrevet
- Systematisk søk i databasen — ikke selektiv sitering
- Identifiserer mønstre, hull og uavklarte spørsmål i praksis
- Skiller tydelig mellom gjeldende rett, rimelig tolkning og analytiske konstruksjoner
- Selvstendig lesbart — kan stå alene

### Lag 2: Lovkommentar per bestemmelse (referansestruktur)

Akkumulerende kommentar til enkeltbestemmelser i anskaffelsesforskriften. Vokser organisk etter hvert som problemdrevne notater utforsker nye spørsmål.

**Kjennetegn:**
- Bestemmelsesdrevet — organisert etter paragraf og ledd
- Destillerer rettssetninger fra de problemdrevne notatene
- Kryssrefererer til notatene for dybdeanalyse
- Kryssrefererer mellom bestemmelser
- Praktisk oppslagsverk, ikke selvstendig analyse

### Samspillet

```
Problemstilling → Systematisk søk → Analyse → Problemdrevet notat
                                                      ↓
                                              Deponer funn i
                                              lovkommentar(er)
```

Etter hver problemutforskning oppdateres kommentarene til de berørte bestemmelsene med funn og rettssetninger. Kommentaren refererer tilbake til notatet for fullstendig analyse.

## 2. Arbeidsmetodikk for problemdrevne notater

### Steg 1: Formuler problemstillingen

Konkret, avgrenset, praktisk relevant. Eksempel: «Er ESPD fra støttende virksomhet tilstrekkelig til å dokumentere rådighet, eller må forpliktelseserklæring foreligge ved tilbudsfrist?»

### Steg 2: Systematisk søk (to faser)

Søket gjennomføres i to faser: primærsøk for bred fangst, deretter ettersøk etter at analysen har identifisert hull.

#### Fase 1: Primærsøk — interseksjonsbasert fangst

Mål: gå fra null til en prioritert kandidatliste *uten å lese noen saker*. Fremgangsmåte:

1. **Referansetabell** — finn alle saker som refererer til primærbestemmelsen (f.eks. § 16-10). Dette er kjernesettet.
2. **Interseksjonsutvidelse** — finn saker som refererer til *flere* relevante bestemmelser (f.eks. § 16-10 ∩ § 17-1). Interseksjonen gir de mest presise treffene.
3. **FTS-supplement** — fulltekstsøk etter spesifikke begreper (f.eks. «forpliktelseserklæring»). FTS fanger saker der referansetabellen mangler treff — enten fordi bestemmelsen diskuteres uten formell paragrafhenvisning, eller fordi saken bruker alternativ terminologi.
4. **Interseksjonsrangering** — kombiner og ranger etter kildeoverlapp:
   - **A** = referansetabell(primær) ∩ referansetabell(sekundær) ∩ FTS(nøkkelbegrep) → mest relevant
   - **B** = referansetabell(primær) ∩ FTS(nøkkelbegrep) → relevant
   - **C** = FTS(nøkkelbegrep) alene → variabel relevans, men kan inneholde avgrensningspraksis
5. **Vektorsøk** — semantisk søk som supplement for å fange saker der nøkkelbegrepene ikke brukes direkte. Bruker Gemini text-embedding-004 (1536 dim) med hybrid FTS+vektor via `search_kofa_decision_hybrid`. Spesielt verdifullt for konseptuelle søk der terminologien varierer (se validering nedenfor).

Denne kategoriseringen er *mekanisk* — den skjer før innholdet er lest. Den gir en prioritert leseliste der A-saker leses først.

**Konkret eksempel (rådighet/forpliktelseserklæring):**

| Kategori | Definisjon | Antall | Resultat |
|---|---|---|---|
| A | § 16-10 ∩ § 17-1 ∩ FTS(«forpliktelseserklæring») | 3 | Alle direkte relevante |
| B | § 16-10 ∩ FTS(«forpliktelseserklæring») | 24 | ~15 relevante |
| C | FTS(«forpliktelseserklæring») alene (2017+) | 82 | ~5 relevante |

#### Fase 2: Ettersøk — gap-søk og vinkelrotasjon

Etter at primæranalysen er ferdig, identifiserer seksjon «Videre arbeid» konkrete hull. Ettersøket angriper disse direkte:

1. **Gap-søk** — direkte SQL mot identifiserte hull (f.eks. § 16-10 + kvantitative termer)
2. **Vinkelrotasjon** — søk på samme tema fra nye innfallsvinkler med alternativ terminologi (f.eks. «råder over», «støttende virksomhet», «underleverandør + kvalifikasjon»)
3. **Kryssvalidering** — saker som treffer i *flere* uavhengige søk har høyest signal

Dokumenter søkestrategien, antall treff per fase, og hva som er gjennomgått vs. gjenstår.

### Steg 3: Innholdsbasert kategorisering

Etter lesing rekategoriseres sakene etter relevans og bidrag:
- **A:** Direkte relevant, behandler problemstillingen inngående
- **B:** Utfyllende, berører problemstillingen som del av en bredere vurdering
- **C:** Perifer, nevner relevante begreper uten å analysere dem

Merk: innholdsbasert kategorisering kan avvike vesentlig fra interseksjonsrangeringen. En sak i mekanisk kategori C (bare FTS-treff) kan vise seg å være innholdsmessig A — og omvendt.

### Steg 4: Analyse

Identifiser:
- Rettssetninger og formuleringer som går igjen
- Utvikling over tid
- Avvikende/motstridende praksis
- Hull — kombinasjoner av faktum som ikke er behandlet
- Distinksjoner som praksis ikke uttaler eksplisitt men som følger logisk

### Steg 5: Syntese

Skriv notatet. Skille tydelig mellom:
- **Gjeldende rett** — det praksis faktisk sier
- **Rimelig tolkning** — slutninger som følger naturlig av praksis
- **Analytiske konstruksjoner** — logiske slutninger som ikke er uttalt i praksis

### Steg 6: Rettskilder utenfor KOFA-avgjørelsene

Supplere med kilder utover KOFA-praksis — se `docs/rettskildeoversikt.md` for komplett oversikt over hva som er tilgjengelig i systemet og kjente hull. Sentrale kilder:

- **Lovtekst** — Paragraf MCP (`lov("foa", "paragraf")`)
- **Forarbeider** — KOFA MCP (`hent_forarbeide`, `finn_forarbeider`, `sok_forarbeider`)
- **EU-domstolspraksis** — KOFA MCP (`hent_eu_dom`) — 320 dommer i systemet
- **EU-direktiver** — ikke i systemet, krever web-oppslag
- **Norsk rettspraksis** — ikke i systemet, bruk Lovdata/web
- **Juridisk litteratur** — eksterne kilder

### Steg 7: Deponer i lovkommentar

Oppdater kommentarene til berørte bestemmelser med funn og rettssetninger. Hvis kommentaren ikke eksisterer: opprett den etter skjelettet i seksjon 4. Merk ubehandlede ledd med «Ikke behandlet» — kommentaren vokser organisk etter hvert som nye notater utforsker nye spørsmål.

### Steg 8: Kvalitetssikring

Separat pass — helst i ny kontekst for å unngå bekreftelsesbias. Sjekkliste:

1. **Sitatverifisering.** Verifiser de viktigste sitatene (minimum 3–5) mot databasen. Se etter trunkering som fjerner kvalifikasjoner.
2. **Logisk konsistens.** Følger konklusjonen av praksisen? Er analogier eksplisitt flagget som analogier?
3. **Motargumenter.** Er de sterkeste motargumentene adressert i *vurderingen* — ikke bare opplistet under «argumenter for»?
4. **Dekning.** Er det A-kandidater fra kandidatlisten som ikke er behandlet uten begrunnelse?
5. **Kildehenvisninger i tabeller.** Bærer hver henvisning den spesifikke påstanden, eller er den for generell?

## Operasjonell arbeidsflyt: batch-drevet prosess

Rettslig analyse sprenger typisk én kontekst. For å bevare tilstand brukes et batch-mønster der hvert steg produserer varige artefakter i en forskningsmappe. Artefaktene fungerer som eksternt minne — hvis konteksten dør, kan en ny instans lese filene og fortsette.

### Forskningsmappe

```
docs/research/{problem}/
  00-plan.md                    # Scoping: problemstilling, søkestrategi, fremdrift
  01-referansetabell.md         # Subagent: paragraf-interseksjoner
  02-fts-sok.md                 # Subagent: FTS-batteri
  03-semantisk-sok.md           # Subagent: vektorsøk via MCP
  04-rettskilder.md             # Subagent: lovtekst, forarbeider, EU-rett
  05-kandidatliste.md           # Hovedkontekst: konsolidering + prioritering
  06-screening-batch{N}.md      # Subagenter: per-batch oppsummeringer
  06-screening-resultater.md    # Hovedkontekst: syntese av screening
```

Ferdig notat skrives til `docs/notat-{problem}.md`. QA og deponering er egne steg.

### Batches og sjekkpunkter

| Batch | Steg | Artefakt | Utfører | Sjekkpunkt |
|---|---|---|---|---|
| 0 | Scoping — formuler problemstilling, søkestrategi | `00-plan.md` | Hovedkontekst | Bruker godkjenner retning (valgfritt) |
| 1 | Søk — referansetabell, FTS, vektorsøk, rettskilder | `01-` til `04-` | Subagenter (parallelle) | — |
| 2 | Konsolidering — kombiner søk, ranger A/B/C | `05-kandidatliste.md` | Hovedkontekst | **Sjekkpunkt 1:** Bruker ser kandidatliste |
| 3 | Screening — les og oppsummer kandidater | `06-screening-*` | Subagenter + hovedkontekst | **Sjekkpunkt 2:** Kontekst-sjekk |
| 4 | Syntese — skriv notatet | `docs/notat-{problem}.md` | Hovedkontekst | — |
| 5 | QA — verifiser sitater, logikk, motargumenter | Korreksjoner i notatet | Ny kontekst | **Sjekkpunkt 3:** Bruker review |
| 6 | Deponering — oppdater lovkommentarer | `docs/kommentar-foa-*.md` | Hovedkontekst | — |

### Sjekkpunkter

Sjekkpunktene er obligatoriske pausepunkter der Claude stopper og avventer tilbakemelding:

1. **Sjekkpunkt 1 (etter konsolidering):** Bruker ser kandidatlisten og kan justere søkestrategi, legge til/fjerne kandidater, eller bekrefte retning.
2. **Sjekkpunkt 2 (etter screening):** Naturlig punkt for kontekst-sjekk. Hvis konteksten nærmer seg full, oppsummer tilstand, oppdater fremdrift i `00-plan.md`, og overlever til ny instans.
3. **Sjekkpunkt 3 (etter QA):** Bruker reviewer notatet etter kvalitetssikring.

Claude skal *også* stoppe mellom batches hvis konteksten er merkbart forbrukt, selv om det ikke er et formelt sjekkpunkt. Oppdater fremdrift i `00-plan.md` og beskriv hva som gjenstår.

### Fremdriftssporing

`00-plan.md` inneholder en `## Fremdrift`-seksjon som oppdateres etter hvert steg:

```markdown
## Fremdrift

- [x] 00-plan.md — scoping godkjent
- [x] 01–04 — søkefase (4 subagenter)
- [x] 05-kandidatliste.md — 14 A, 8 B, konsolidert
- [ ] 06-screening — neste: batch 1 (A-saker, 4 stk)
- [ ] Notat
- [ ] QA
- [ ] Deponering
```

Ny instans leser `00-plan.md` → ser fremdrift → leser siste ferdigstilte artefakt → fortsetter.

### Screening-resultater som kompresjonslag

`06-screening-resultater.md` syntetiserer alle screening-batches til ett dokument. Den tjener to formål:

- **Input til notatskriving** — hovedkonteksten leser denne i stedet for alle batch-filer
- **Handoff-artefakt** — ved kontekstbytte er dette det eneste en ny instans trenger fra screeningfasen

Hovedkonteksten skriver den etter å ha lest batch-filene fra subagentene.

### Subagenter

- **Søkefase (batch 1):** 3–4 parallelle subagenter — én per søketype (referansetabell, FTS, vektorsøk, rettskilder). Alle søketyper inkl. vektorsøk kan kjøres via MCP-verktøy (`semantisk_sok_kofa`, `finn_praksis`, `sok_avgjoerelse`) eller direkte SQL via Supabase MCP.
- **Screeningfase (batch 3):** 2–4 parallelle subagenter, 3–5 saker per batch. Gi eksplisitt oppsummeringsmal.
- **Terskel:** 8+ kandidater → bruk subagenter. Under 5 → les direkte.
- **Verktøy:** Subagenter har tilgang til Supabase MCP (SQL), KOFA MCP og Paragraf MCP.
- **Kontekstgevinst:** Screening via subagenter sparer ~40% kontekst.
- **Filskriving:** Subagenter returnerer tekst til hovedkonteksten, som skriver artefaktene til disk.
- **Kvalitetskontroll:** Stikkprøv oppsummeringer mot originaltekst, spesielt for nøkkelsitater.

## 3. Skjelett: Problemdrevet notat

```markdown
# [Tittel — problemstilling i klartekst]

**Dato:** YYYY-MM-DD
**Rettsområde:** [f.eks. Offentlige anskaffelser — FOA del III]
**Bestemmelser:** [primærbestemmelser]

## 1. Problemstilling
Konkret, avgrenset spørsmål. Gjerne nummerert hvis det er flere delspørsmål.

## 2. Rettslig rammeverk
Kort gjennomgang av relevante bestemmelser med ordlyd der nødvendig.

## Søkestrategi

### Inklusjons- og eksklusjonskriterier
- **Inkludert:** [bestemmelser, tidsrom, sakstyper]
- **Ekskludert:** [begrunnelse for avgrensninger]

### Primærsøk
| Trinn | Søk | Treff | Kommentar |
|---|---|---|---|
| 1. Referansetabell | [primærbestemmelse] | n | Kjernesett |
| 2. Interseksjon | [primær ∩ sekundær] | n | Presise treff |
| 3. FTS-supplement | [nøkkelbegrep] | n | Kompenserer for manglende paragrafref. |
| 4. Rangering | A / B / C | n/n/n | Prioritert leseliste |

### Ettersøk
| Søk | Treff | Nye relevante | Kommentar |
|---|---|---|---|
| [gap-søk / vinkelrotasjon / etc.] | n | n | [hva ble funnet] |

### Flyt: identifisert → screenet → inkludert
- Identifisert via primærsøk: n
- Screenet (lest vurdering): n
- Inkludert i analysen: n
- Tilført fra ettersøk: n
- **Totalt analysert: n**

## 3. Praksis
Gjennomgang av relevante avgjørelser, typisk gruppert i kategorier.
Hvert oppslag: faktum → nemndas vurdering → rettssetning.

## 4. Rettslig analyse
Her ligger det analytiske bidraget. Delseksjoner etter tema.
Tydelig markering av hva som er gjeldende rett vs. analytisk konstruksjon.

## 5. Konklusjoner
Oppsummering av funn. Tabellformat for oversikt.

## 6. [Evt. særtemaer — f.eks. del II-anskaffelser]

## 7. Oversikt over analyserte avgjørelser
Tabell med alle gjennomgåtte saker.

## 8. Rettskilder
Gruppert: KOFA → Høyesterett → Lagmannsrettene → EU-domstolen → Litteratur → Forskrift

## 9. Videre arbeid
Eksplisitt om hva som ikke er dekket og bør kartlegges.
```

## 4. Skjelett: Lovkommentar per bestemmelse

```markdown
# FOA § [nr] — [korttittel]

## Ordlyd
Fullstendig ordlyd, ledd for ledd.

## Direktivgrunnlag
Tilsvarende bestemmelse i anskaffelsesdirektivet (2014/24/EU).

## Forarbeider
Relevante uttalelser fra NOU og Prop.

## Ledd 1: [beskrivende overskrift]

### Rettssetninger
Oppsummering av gjeldende rett, med kildehenvisning.

### Rettspraksis
- [HR-referanse] — [kort om hva dommen fastslår]
- [Lagmannsrettsreferanse] — [kort]

### Nemndspraksis
- [Sak nr] — [kort om hva saken fastslår]

### Se også
Kryssreferanser til andre bestemmelser og problemdrevne notater.

## Ledd 2: [beskrivende overskrift]
[Tilsvarende struktur]

## Uavklarte spørsmål
Problemstillinger som ikke er behandlet i praksis.
Referanse til problemdrevne notater som utforsker disse.
```

## 5. Filstruktur

```
docs/
  metode-rettslig-analyse.md          # Dette dokumentet
  rettskildeoversikt.md               # Tilgjengelige kilder og hull
  notat-[tema].md                     # Problemdrevne notater (ferdig produkt)
  kommentar-foa-[paragraf].md         # Lovkommentarer per bestemmelse
  research/
    [problem]/                        # Forskningsmappe per problemstilling
      00-plan.md                      # Scoping + fremdrift
      01-referansetabell.md           # Søkeartefakter
      02-fts-sok.md
      03-semantisk-sok.md
      04-rettskilder.md
      05-kandidatliste.md             # Konsolidert kandidatliste
      06-screening-batch{N}.md        # Screening per batch
      06-screening-resultater.md      # Syntese av screening
```

## 6. Kvalitetskriterier

### For problemdrevne notater
- Søkestrategien er dokumentert og reproduserbar
- Skillet mellom gjeldende rett og analytiske konstruksjoner er tydelig
- Hull i praksis er eksplisitt identifisert
- Rettskilder utenfor databasen er integrert der de finnes
- Notatet er selvstendig lesbart

### For lovkommentarer
- Alle ledd er dekket, også der praksis er sparsom
- Rettssetninger er destillert og presise
- Kryssreferanser til notater og andre bestemmelser er på plass
- Uavklarte spørsmål er flagget

## 7. Metodiske observasjoner

*Denne seksjonen oppdateres etter hvert som vi gjør erfaringer.*

### Fra notat om rådighet/forpliktelseserklæring (2026-02-10)
- Systematisk søk avdekker mønstre som ikke er synlige fra enkeltavgjørelser (to-partstesten, binær/kvantitativ-distinksjonen)
- Lagmannsrettspraksis er vesentlig viktigere enn den fremstår i KOFA-avgjørelsene — kobling mellom rettsinstanser bør systematiseres
- HTML-filer fra Lovdata bør strippes til ren tekst før analyse (HTML-markup blåser opp tokenforbruket)
- Agenter er overkill for dokumenter under ~5000 ord — les direkte
- Presumpsjoner i praksis kan identifiseres ved å lete etter hva nemnda *ikke* drøfter eksplisitt

### Fra gap-søk og vinkelrotasjon (2026-02-10)

Ettersøksfasen (nå formalisert i Steg 2, Fase 2) avdekket ~10 nye kandidater fra et primærsett på ~20 — hvorav 7 med substansielt ny dekning. Observasjoner:

**Kategori C-saker er verdifulle.** Saker som nevner forpliktelseserklæring uten å ha § 16-10 i referansetabellen inneholder ofte avgrensningspraksis — dvs. saker der nemnda slår fast at § 16-10 *ikke* gjelder. Disse er like viktige som sakene der bestemmelsen anvendes.

**Funn fordeler seg mellom lag.** Av 7 substansielle funn hørte bare 2 hjemme i det eksisterende problemnotatet. De øvrige 5 tilhørte kommentaren eller et nytt notat. Ettersøk etter hull i ett notat produserer altså ofte materiale for *andre* dokumenter. Implikasjon: systematisk ettersøk bør gjøres med hele dokumentporteføljen i tankene, ikke bare det ene notatet.

**Negativt funn er også funn.** Gap 1 (kvantitative bemanningskrav) og Gap 2 (ESPD som eneste holdepunkt) ga null treff — som bekrefter at disse scenariene genuint er utestet i praksis. Denne bekreftelsen styrker notatets konklusjon.

**Nøkkelkolonner i CLAUDE.md.** SQL-spørringer mot Supabase feilet på grunn av feil kolonnenavn (`case_number` vs `sak_nr`, `content` vs `text`). CLAUDE.md bør inneholde nøkkelkolonner for alle tabeller — oppdatert.

### Fra validering av vektorsøk (2026-02-11)

Tre testsøk sammenlignet FTS alene mot hybrid (vektor+FTS) for å validere merverdien av embeddings:

**Test 1: Eksakt juridisk term** («forpliktelseserklæring», seksjon=vurdering)
FTS og hybrid gir omtrent samme resultat. FTS fungerer godt på eksakte termer. Hybrid rerangerer marginalt.

**Test 2: Naturlig språk** («kan oppdragsgiver avvise tilbud som ikke oppfyller kvalifikasjonskrav», seksjon=vurdering)
Hybrid fant 6 treff med fts_rank=0 — alle 6 direkte relevante (100% presisjon). FTS misset dem fordi de bruker synonymer: «kvalifikasjonene» i stedet for «kvalifikasjonskrav», «kvalifikasjonskriterier», «krav satt i konkurransegrunnlaget». Eksempel: 2005/197 («rett, men ikke plikt til å avvise»), 2009/219 (plikt/rett-distinksjonen).

**Test 3: Konseptuelt søk** («tildelingskriterier utenfor det som er relevant for kontrakten», seksjon=vurdering)
Mest dramatisk forskjell. FTS: 7 treff, 1 relevant (14% presisjon) — matchet på «tildelingskriter*» + «utenfor» i irrelevante kontekster. Hybrid: 10 treff, 10 relevante (100% presisjon) — fant NF-doktrine-formuleringer, ulovlige tildelingskriterier, grensedragning kvalifikasjon/tildeling uten å bruke søketermene direkte.

| Søketype | FTS presisjon | Hybrid presisjon | Hybrid-eksklusive |
|---|---|---|---|
| Eksakt term | ~90% | ~90% | Marginal |
| Naturlig språk | ~80% | ~100% | 6 relevante treff FTS misset |
| Konseptuelt | 14% | 100% | Alt relevant kom fra vektor |

**Implikasjon for søkestrategi:** Vektorsøk bør brukes som standard i fase 1 (punkt 5), spesielt for konseptuelle søk og ved vinkelrotasjon i fase 2. FTS beholder sin rolle for eksakte termer og som komponent i hybrid-funksjonen. Interseksjonsmetoden (referansetabell + FTS + vektor) gir tre uavhengige signaler som styrker rangeringen.

### Søkeeffektivitet per notat

*Akkumulerende tabell — oppdateres etter hvert notat for å identifisere mønstre.*

| Notat | Primær (A+B) | Screenet | Inkl. primær | Ettersøk nye | Presisjon A | Presisjon B | Totalt analysert |
|---|---|---|---|---|---|---|---|
| Rådighet/forpliktelseserklæring | 27 | 27 | ~18 | 7 | 3/3 (100%) | ~15/24 (63%) | 20 KOFA + 6 retts. |
| Grensedragning § 16-10 | *avledet fra ettersøk* | — | — | — | — | — | 11 KOFA |
| NF-doktrinens grenser | 20 | 20 | 17 | 2 | 15/17 (88%) | 2/3 (67%) | 19 KOFA + 2 retts. |
| Akkumulering minimumsomsetning | 12 (A+B) | 12 | 12 | — | 4/4 (100%) | 8/8 (100%) | 12 KOFA + 2 EU |
| Intervju som tildelingskriterium | 16 (A+B) | 12 | 10 | — | 6/8 (75%) | 4/8 (50%) | 10 KOFA + 1 EU |

**Foreløpige observasjoner:**
- A-kategorien (trippel interseksjon) har 100% presisjon — bekrefter at interseksjon er en sterk relevansprediktor
- B-kategorien har ~63% presisjon — en tredjedel faller utenfor problemstillingen etter lesing
- Ettersøket øker dekningen med ~28% (7/25) — vesentlig, men med fallende marginalnytte
- Ettersøk produserer materiale for *andre* dokumenter (5 av 7 funn gikk til kommentar/nytt notat) — bør gjøres med hele porteføljen i tankene

### Fra kartlegging av NF-doktrinens grenser (2026-02-11)

**Motpraksis krever alternativ terminologi.** FTS på doktrine­begrepet («naturlig forståelse») gir høy presisjon for bekreftelser (88%), men fanger dårlig motpraksis — saker der oppdragsgiver har gått *utenfor*. Disse bruker sjelden doktrinebegrepet og konstaterer i stedet at noe er «utenfor tildelingskriteriets rammer» eller at oppdragsgiver har «gått utenfor». Ettersøk med alternativ terminologi fanget 2 av 3 motpraksiskandidater.

**Implikasjon for søkestrategi:** Ved doktrine-kartlegging bør primærsøket suppleres med FTS på *konklusjonstermene* (brudd, utenfor, ikke innenfor) — ikke bare doktrinens egne begreper.

### Fra akkumulering av minimumsomsetning (2026-02-12)

**Parallelle subagenter for søk og screening.** Notatet ble utarbeidet med en ny tilnærming: parallelle Opus-agenter for søkefasen (4 samtidige søkeagenter) og screeningfasen (3 samtidige screeningagenter). Hovedkonteksten koordinerte og utførte syntesen.

**Referansetabell-interseksjon gir smal trakt.** § 16-10 ∩ § 16-3 ga kun 4 saker — nesten alle relevante, men for smalt for å fange bredden. FTS og vektorsøk fant vesentlig flere kandidater. Den smale trakten skyldes at mange saker diskuterer økonomisk kapasitet uten formell paragrafhenvisning til § 16-3.

**Vektorsøk avgjørende for konseptuelle spørsmål.** Alle hybrid-treff hadde fts_rank=0 — FTS matchet ikke fordi søkene var formulert som naturlig språk. Vektorsøket fant 2009/21 (formålet), 2015/46 (direktivtolkning), 2011/191 (del II) som FTS ikke fanget.

**Subagent-begrensninger.** General-purpose-agenter fikk ikke bash-tilgang — hybrid/vektorsøk måtte kjøres fra hovedkonteksten. Bash-agenter fikk heller ikke tilgang. Supabase MCP fungerte for general-purpose-agenter. Implikasjon: subagenter egner seg best for SQL-baserte oppgaver, ikke for oppgaver som krever Python/bash.

**Screening via subagenter var effektivt.** 3 parallelle agenter leste og oppsummerte 12 saker + 2 EU-dommer i ~3 minutter. Oppsummeringene var strukturerte og presise nok til å bygge syntese på. Hovedkonteksten slapp å lese ~100 sider avgjørelsestekst direkte.

**72 identifiserte → 12 screenet → 12 inkludert.** Uvanlig høy presisjon (100%) i screeningfasen, men dette skyldes at kandidatlisten allerede var godt filtrert gjennom konsolideringen. Ettersøksfase ble ikke gjennomført — anbefales som oppfølging.

### Fra intervju som tildelingskriterium (2026-02-16)

**Negativt funn som hovedresultat.** Ingen KOFA-avgjørelse behandler spørsmålet om *selektiv* intervjuering i åpen anbudskonkurranse direkte. Analysen måtte bygges på analogi fra tre praksislinjer: (1) lovligheten av intervju, (2) likebehandling i evalueringsarena, (3) trinnvis evaluering. Negativt funn på tvers av alle fire søkemetoder (referansetabell, FTS, vektorsøk, FTS-avgjørelsestekst) styrker konklusjonen om at problemstillingen genuint er ubehandlet.

**Subagenter feilet konsistent på MCP-tilgang.** Alle 8 subagenter (4 søk + 4 screening) fikk tilgangsnekt til kofa-paragraf/claude_ai MCP-verktøy. Hovedkonteksten hadde full tilgang. Implikasjon: MCP-avhengige oppgaver bør kjøres fra hovedkonteksten. Subagenter egner seg for oppgaver uten MCP-avhengighet — eller man må bruke «allow all» tillatelsesmodus.

**Fire parallelle søkeagenter + konsolidering fungerte godt.** Til tross for MCP-begrensningen ga mønsteret (4 agenter med ulike søkestrategier → konsolidert kandidatliste → screening) en bredere fangst enn sekvensiell søking. Vektorsøket (fts_rank=0 for alle treff) avdekket 5 A-kandidater som FTS ikke fanget — konsistent med tidligere validering.

**Presisjon lavere enn tidligere notater.** A-presisjon (75%) og B-presisjon (50%) er lavere enn normalt. Dette skyldes at problemstillingen er konseptuelt bred — mange saker om intervju/likebehandling er relevant for *deler* av analysen men ikke direkte for kjernespørsmålet (selektiv intervjuering). Interseksjonsrangeringen fungerer best for avgrensede paragrafspørsmål, svakere for tverrgående konseptuelle spørsmål.

### Fra kvalitetssikring av intervju-notatet (2026-02-16)

**QA i separat kontekst fanger systematiske feil.** Kvalitetssikring av det ferdige notatet avdekket tre typer feil som forfatterkonteksten ikke fanget: (1) trunkerte sitater som utelot kvalifikasjoner (Montte premiss 32 og 37 manglet «as regards the technical evaluation» og «and thus do not meet the needs of the contracting authority»), (2) en upresis kildehenvisning i konklusjonstabellen (Montte p38 er for generell til å bære påstanden alene), (3) en uflagget analogi (Montte-distinksjonen ble presentert som direkte anvendelse uten å erkjenne at den overføres fra evalueringsfaser til evalueringsarenaer). Alle tre er typiske «bekreftelsesbias»-feil — forfatteren vet hva sitatet *skal* si og leser det inn.

**Motargumenter må adresseres i vurderingen, ikke bare opplistes.** Notatet hadde en «argumenter for»-seksjon og en «argumenter mot»-seksjon, men vurderingen behandlet ikke alle motargumenter eksplisitt. Spesielt: 2006/90-unntaket (asymmetrisk behandling lovlig ved full score) og proporsjonalitetsargumentet ble avfeid for raskt. Etter QA ble begge adressert med substansiell begrunnelse — noe som styrker konklusjonen.

**Implikasjon for arbeidsflyt:** QA bør gjøres i en separat sesjon, ikke som siste steg i samme kontekst. Formalisert som steg 8 i metodikken ovenfor.
