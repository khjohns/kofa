---
name: rettslig-analyse
description: Bruk ved rettslig analyse av KOFA-avgjørelser. Aktiveres når bruker ber om analyse av rettsspørsmål, utarbeiding av notater, eller oppdatering av lovkommentarer.
---

# Rettslig analyse — to-lagsmodell

Prosjektet produserer rettslig analyse i to lag (se `docs/metode-rettslig-analyse.md` for full metodebeskrivelse):

1. **Problemdrevne notater** (`docs/notat-*.md`) — dybdeanalyse av konkrete rettsspørsmål. Systematisk søk → kategorisering → analyse → funn. Selvstendig lesbare.
2. **Lovkommentarer** (`docs/kommentar-foa-*.md`) — akkumulerende referansestruktur per bestemmelse. Oppdateres med funn fra notatene.

## Prosess

Ved rettslig analyse: følg metodikken i `docs/metode-rettslig-analyse.md` (skjelett, to-fase søk, søkestrategi-seksjon, søkeeffektivitetstabell). Oppdater metodedokumentet med nye observasjoner og søkeeffektivitetsrad etter hvert notat.

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
