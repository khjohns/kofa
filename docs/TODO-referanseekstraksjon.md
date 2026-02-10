# TODO: Referanseekstraksjon — kjente gap

**Dato:** 2026-02-10

## Bakgrunn

Regex-fix (`ad13962`) løste tre problemer (A/B/C) i `reference_extractor.py` som fanget bare kortformer, `del III`-mønster og parentes uten mellomrom. Dekningen for sentrale FOA-bestemmelser gikk fra 5-30% til 89-95%.

Gjenstående gap og forbedringsmuligheter er dokumentert under.

## 1. Problem D: Bare §-referanser uten lovnavn

**Eksempel:** `jf. § 16-10 (2)`, `se § 24-8 første ledd`

Disse forekommer hyppig i KOFA-avgjørelser og fanges ikke i dag. Målt gap etter fix A+B+C:

| Section | ref_count | fulltext_count | Gap |
|---------|-----------|----------------|-----|
| 16-1    | 30        | 97             | 69% |
| 14-1    | 78        | 122            | 36% |
| 8-4     | 47        | 72             | 35% |
| 16-3    | 18        | 52             | 65% |
| 28-1    | 44        | 65             | 32% |

Merk: fulltext_count er en overestimering (teller alle `§ X-Y` uavhengig av kontekst), men gapet indikerer at kontekstuell parsing har potensial.

### Mulige tilnærminger

1. **Lovnavn-propagering:** Hold styr på sist nevnte lovnavn per avsnitt. Når `§ X-Y` forekommer uten lovnavn, arv fra forrige navngitte referanse i samme avsnitt/seksjon.
2. **KOFA-heuristikk:** Paragrafformat X-Y (med bindestrek) er nesten alltid FOA i KOFA-kontekst. Kan brukes som fallback.
3. **Avsnittskontekst:** Parse hele avsnittet, finn alle §-referanser, tilordne lovnavn basert på nærmeste navngitte referanse.

### Risiko

- False positives for andre lover (forvaltningsloven, tvisteloven etc. har enkle paragrafnumre)
- Heuristikk 2 fungerer bare for FOA (bindestrek-format), ikke for LOA eller andre lover

### Anbefaling

Start med tilnærming 1 (lovnavn-propagering). Mest generell og lavest risiko for false positives.

## 2. Kvalitetskontroll: KOFA-sakskryssreferanser

Kryssreferanser til andre KOFA-saker (`sak 2019/491`, `KOFA 2020/172`) fanges av `_CASE_REF_RE`. Ikke verifisert om det er gap tilsvarende lovhenvisninger.

### Oppgaver

- [ ] Sammenlign antall ekstraherte kryssreferanser mot fulltekstsøk på `sak \d{4}/\d+`
- [ ] Sjekk om varianter som `klagenemndas avgjørelse 2019/491` (uten "sak") forekommer
- [ ] Verifiser at `sak_nr` i kryssreferanser matcher faktiske saker i `kofa_cases`

## 3. Kvalitetskontroll: EU-domstolsreferanser

EU-referanser (`C-19/00`, `C-368/10 Max Havelaar`) fanges av `_EU_CASE_RE`. Ikke systematisk verifisert.

### Oppgaver

- [ ] Sammenlign antall ekstraherte EU-referanser mot fulltekstsøk på `C-\d+/\d+`
- [ ] Sjekk om saksnavn fanges korrekt (parentes vs direkte etter case-ID)
- [ ] Verifiser at EU-referanser i eldre saker (pre-2017) også fanges
- [ ] Sjekk om T-saker (General Court, f.eks. `T-258/06`) bør inkluderes
