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
5. **Vektorsøk** (når tilgjengelig) — semantisk søk som supplement for å fange saker der nøkkelbegrepene ikke brukes direkte. *Ikke implementert per 2026-02 — planlagt.*

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

### Steg 6: Rettskilder utenfor databasen

Supplere med kilder som ikke er i KOFA-databasen:
- Lagmannsrettsdommer og høyesterettsdommer (Lovdata)
- EU-domstolen (direktivtolkning)
- Forarbeider (NOU, Prop.)
- Juridisk litteratur

### Steg 7: Deponer i lovkommentar

Oppdater kommentarene til berørte bestemmelser med funn og rettssetninger.

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
  notat-[tema].md                     # Problemdrevne notater
  kommentar-foa-[paragraf].md         # Lovkommentarer per bestemmelse
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

### Søkeeffektivitet per notat

*Akkumulerende tabell — oppdateres etter hvert notat for å identifisere mønstre.*

| Notat | Primær (A+B) | Screenet | Inkl. primær | Ettersøk nye | Presisjon A | Presisjon B | Totalt analysert |
|---|---|---|---|---|---|---|---|
| Rådighet/forpliktelseserklæring | 27 | 27 | ~18 | 7 | 3/3 (100%) | ~15/24 (63%) | 20 KOFA + 6 retts. |
| Grensedragning § 16-10 | *avledet fra ettersøk* | — | — | — | — | — | 11 KOFA |
| NF-doktrinens grenser | 20 | 20 | 17 | 2 | 15/17 (88%) | 2/3 (67%) | 19 KOFA + 2 retts. |

**Foreløpige observasjoner:**
- A-kategorien (trippel interseksjon) har 100% presisjon — bekrefter at interseksjon er en sterk relevansprediktor
- B-kategorien har ~63% presisjon — en tredjedel faller utenfor problemstillingen etter lesing
- Ettersøket øker dekningen med ~28% (7/25) — vesentlig, men med fallende marginalnytte
- Ettersøk produserer materiale for *andre* dokumenter (5 av 7 funn gikk til kommentar/nytt notat) — bør gjøres med hele porteføljen i tankene

### Fra kartlegging av NF-doktrinens grenser (2026-02-11)

**Motpraksis krever alternativ terminologi.** FTS på doktrine­begrepet («naturlig forståelse») gir høy presisjon for bekreftelser (88%), men fanger dårlig motpraksis — saker der oppdragsgiver har gått *utenfor*. Disse bruker sjelden doktrinebegrepet og konstaterer i stedet at noe er «utenfor tildelingskriteriets rammer» eller at oppdragsgiver har «gått utenfor». Ettersøk med alternativ terminologi fanget 2 av 3 motpraksiskandidater.

**Implikasjon for søkestrategi:** Ved doktrine-kartlegging bør primærsøket suppleres med FTS på *konklusjonstermene* (brudd, utenfor, ikke innenfor) — ikke bare doktrinens egne begreper.
