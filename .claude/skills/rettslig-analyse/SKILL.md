---
name: rettslig-analyse
description: Bruk ved rettslig analyse av KOFA-avgjørelser. Aktiveres når bruker ber om analyse av rettsspørsmål, utarbeiding av notater, eller oppdatering av lovkommentarer.
---

# Rettslig analyse — to-lagsmodell

Prosjektet produserer rettslig analyse i to lag (se `docs/metode-rettslig-analyse.md` for full metodebeskrivelse):

1. **Problemdrevne notater** (`docs/notat-*.md`) — dybdeanalyse av konkrete rettsspørsmål. Systematisk søk → kategorisering → analyse → funn. Selvstendig lesbare.
2. **Lovkommentarer** (`docs/kommentar-foa-*.md`) — akkumulerende referansestruktur per bestemmelse. Oppdateres med funn fra notatene.

## Operasjonell arbeidsflyt

Rettslig analyse utføres som en **batch-drevet prosess** med varige artefakter. Se `docs/metode-rettslig-analyse.md` for full metodebeskrivelse og `docs/rettskildeoversikt.md` for tilgjengelige kilder.

### Forskningsmappe

Opprett alltid `docs/research/{problem}/` med `00-plan.md` før søk starter. Alle mellomresultater skrives hit — dette er eksternt minne som overlever kontekstbytter.

### Batches

| Batch | Artefakt | Sjekkpunkt |
|---|---|---|
| 0. Scoping | `00-plan.md` | Bruker godkjenner retning (valgfritt) |
| 1. Søk | `01-` til `04-` (subagenter + hovedkontekst) | — |
| 2. Konsolidering | `05-kandidatliste.md` | **Stopp:** Bruker ser kandidatliste |
| 3. Screening | `06-screening-*` (subagenter → resultater) | **Stopp:** Kontekst-sjekk |
| 4. Syntese | `docs/notat-{problem}.md` | — |
| 5. QA | Korreksjoner i notatet (ny kontekst) | **Stopp:** Bruker review |
| 6. Deponering | `docs/kommentar-foa-*.md` | — |

### Sjekkpunkt-protokoll

- **Stopp ved sjekkpunkter** og avvent tilbakemelding.
- **Stopp også mellom batches** hvis konteksten er merkbart forbrukt.
- **Oppdater fremdrift** i `00-plan.md` ved hvert stopp — ny instans leser denne for å fortsette.

### Nøkkelregler

- Subagenter for søk (3–4 parallelle) og screening (2–4 parallelle, 3–5 saker per batch).
- Alle søketyper inkl. vektorsøk kan delegeres til subagenter via MCP-verktøy (`semantisk_sok_kofa`, `finn_praksis`, `sok_avgjoerelse`) eller direkte SQL via Supabase MCP.
- **Ved subagent-feil: STOPP.** Ikke utfør oppgaven selv fra hovedkonteksten — det spiser kontekst som trengs til syntese. Meld feilen til bruker.
- `06-screening-resultater.md` er kompresjonslaget — syntetiser alle batches hit. Ny instans trenger bare denne + plan.
- Oppdater søkeeffektivitetstabellen i metodedokumentet etter hvert notat.

## Sitater og kildehenvisninger

- **Verifiser mot databasen.** Hent avgjørelsestekst med `hent_avgjoerelse` og EU-dommer med `hent_eu_dom`. Sammenlign ordrett.
- **Ikke trunker bort kvalifikasjoner.** Hvis originalteksten inneholder en kvalifikasjon som begrenser eller presiserer utsagnet (f.eks. «as regards the technical evaluation», «and thus do not meet the needs of the contracting authority»), skal den med i sitatet. Trunkering som fjerner kontekst uten å endre kjerneinnholdet er akseptabelt — trunkering som fjerner vilkår eller begrunnelse er det ikke.
- **Presise kildehenvisninger i tabeller.** Når en tabell oppgir rettsgrunnlag, skal henvisningen bære den spesifikke påstanden. Generelle prinsipper (f.eks. «transparensprinsippet») er ikke tilstrekkelig alene — kombiner med den konkrete bestemmelsen (f.eks. «FOA § 14-1 (forutberegnelighet), jf. dir. art. 18»).
- **Ordlyden er fasit.** KOFA-avgjørelser kan selv ha feil paragrafhenvisninger. Ved motstrid: stol på ordlyden, flagg feilen.

## Argumentasjonskvalitet

- **Flagg analogier eksplisitt.** Når praksis fra én kontekst (f.eks. trinnvis evaluering mellom faser) overføres til en annen (f.eks. tilgang til evalueringsarenaer), må det synliggjøres at dette er en analogi — ikke direkte anvendelse. Forklar *hvorfor* analogien holder: hva er det underliggende hensynet som er felles?
- **Adresser motargumenter systematisk.** Identifiser de sterkeste motargumentene og avfei dem i vurderingen. Et uadressert motargument svekker konklusjonen mer enn et adressert og avfeid motargument. Spesielt: unntak i praksis som *kunne* støtte motparten, og selvstendige prinsippargumenter (proporsjonalitet, metodefrihet).
- **Skill mellom rettskildenivåer.** Gjeldende rett (det praksis faktisk sier) → rimelig tolkning (slutninger som følger naturlig) → analytiske konstruksjoner (logiske sprang). Merk overgangene eksplisitt.

## Deponering i lovkommentarer

Etter hver problemutforskning: deponer funn i relevante lovkommentarer. Hvis lovkommentaren ikke eksisterer: **opprett den** etter skjelettet i `docs/metode-rettslig-analyse.md`. Ikke utsett deponering fordi filen mangler.

## Kvalitetssikring

Før et notat anses som ferdig:

1. **Sitatverifisering.** Verifiser de viktigste sitatene (minimum 3–5) mot databasen med `hent_avgjoerelse`/`hent_eu_dom`. Se etter trunkering som fjerner kvalifikasjoner.
2. **Logisk konsistens.** Sjekk at konklusjonen følger av den gjennomgåtte praksisen. Er det sprang i argumentasjonen? Er analogier flagget?
3. **Motargumenter.** Er de sterkeste motargumentene adressert i vurderingen — ikke bare i «argumenter for»-seksjonen?
4. **Dekning.** Er det A-kandidater fra kandidatlisten som ikke er behandlet? Er utelatelsen begrunnet?
5. **Deponering.** Er funn deponert i relevante lovkommentarer (opprett ved behov)?
