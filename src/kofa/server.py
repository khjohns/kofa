"""
MCP Server implementation for KOFA tools.

Implements the Model Context Protocol (MCP) JSON-RPC interface
for exposing KOFA decision lookup tools to AI assistants.
"""

from typing import Any

from kofa.service import KofaService

import logging

logger = logging.getLogger(__name__)


# MCP Protocol version
PROTOCOL_VERSION = "2025-06-18"

# Server info
SERVER_INFO = {
    "name": "kofa",
    "version": "0.1.0",
}

# Server instructions - shown to connecting clients
SERVER_INSTRUCTIONS = """
# KOFA - Klagenemnda for offentlige anskaffelser

Tilgang til ~5000 avgjørelser fra KOFA (Klagenemnda for offentlige anskaffelser).
KOFA behandler klager på brudd på anskaffelsesregelverket (lov og forskrift om
offentlige anskaffelser). Avgjørelsene er enten rådgivende uttalelser eller
gebyrsaker (overtredelsesgebyr ved ulovlige direkte anskaffelser).

## Verktøy

| Verktøy | Bruk |
|---------|------|
| `sok(query, limit?)` | Fulltekstsøk i KOFA-saker |
| `hent_sak(sak_nr)` | Hent en spesifikk sak med alle detaljer |
| `hent_avgjoerelse(sak_nr, seksjon?)` | Hent avgjørelsestekst (innledning, bakgrunn, anførsler, vurdering, konklusjon) |
| `siste_saker(limit?, sakstype?, avgjoerelse?, innklaget?)` | Siste avgjørelser med filtre |
| `finn_praksis(lov, paragraf?, limit?)` | Finn saker som refererer til en bestemt lovparagraf (2017+) |
| `relaterte_saker(sak_nr)` | Kryssreferanser: saker denne saken siterer og saker som siterer denne |
| `mest_siterte(limit?)` | De mest siterte/prinsipielle KOFA-sakene |
| `eu_praksis(eu_case_id, limit?)` | Finn KOFA-saker som refererer til en bestemt EU-dom |
| `mest_siterte_eu(limit?)` | De mest siterte EU-dommene i KOFA |
| `statistikk(aar?, gruppering?)` | Aggregert statistikk |

## Velg riktig verktøy

| Brukersituasjon | Bruk | Hvorfor |
|-----------------|------|---------|
| Spør om en bestemt lovparagraf | `finn_praksis(lov, paragraf)` | Direkte oppslag i referansetabeller |
| Spør om et tema/problemstilling | `sok("tildelingskriterier")` | FTS i metadata og sammendrag |
| Kjenner saksnummer | `hent_sak("2023/1099")` | Direkte oppslag |
| Vil lese avgjørelsens begrunnelse | `hent_avgjoerelse("2023/1099", seksjon="vurdering")` | Full vurderingstekst |
| Vil se faktum i en sak | `hent_avgjoerelse("2023/1099", seksjon="bakgrunn")` | Sakens bakgrunn |
| Vil se trender/oversikt | `statistikk()` | Aggregert data |
| Spør om en bestemt kommune/virksomhet | `sok("Bergen kommune")` eller `siste_saker(innklaget="Bergen")` | Navnesøk |
| Leser en sak og vil se kontekst | `relaterte_saker("2023/1099")` | Finner saker den bygger på + saker som bygger på den |
| Vil se prinsipielle avgjørelser | `mest_siterte(limit=10)` | De viktigste/mest refererte sakene |
| Spør om en EU-dom | `eu_praksis(eu_case_id="C-19/00")` | KOFA-saker som anvender EU-dommen |
| Vil se viktigste EU-dommer | `mest_siterte_eu(limit=10)` | De mest refererte EU-dommene i KOFA |

**Kjerneforskjell mellom `sok` og `finn_praksis`:**
- `sok` søker i sakens metadata (parter, tema, sammendrag)
- `finn_praksis` søker i **lovhenvisninger ekstrahert fra avgjørelsesteksten** (f.eks. "alle saker som drøfter FOA § 8-3")

## Anbefalt arbeidsflyt

1. **Finn relevant praksis** → `finn_praksis(lov, paragraf)` eller `sok(tema)`
2. **Hent detaljer** → `hent_sak(sak_nr)` for å lese sammendrag og se utfall
3. **Les avgjørelsen** → `hent_avgjoerelse(sak_nr)` for innholdsfortegnelse, deretter `hent_avgjoerelse(sak_nr, seksjon="vurdering")` for begrunnelsen
4. **Se kontekst** → `relaterte_saker(sak_nr)` for å se hva saken bygger på og hvem som bygger videre
5. **Slå opp lovhjemmel** → Bruk Paragraf MCP (`lov("anskaffelsesforskriften", "8-3")`) for å se selve lovteksten
6. **Tilby videre utforskning** → Se under

## VIKTIG: Tilby videre utforskning

**ALLTID** etter å ha besvart et KOFA-spørsmål, tilby brukeren mer:

```
---
**Vil du utforske videre?**
- Se flere saker om [samme paragraf/tema]?
- Slå opp lovteksten i [paragraf X]? (via Paragraf MCP)
- Se saker med motsatt utfall?
```

**Hvorfor dette er kritisk:**
- KOFA-praksis er nyansert — utfallet avhenger av faktum i den enkelte sak
- Brukere trenger ofte flere saker for å se mønsteret
- Lovtekst + KOFA-praksis sammen gir mye bedre svar enn hver for seg

**Eksempel:** Bruker spør "Kan man avvise et tilbud som mangler en ESPD?"
1. `finn_praksis(lov="anskaffelsesforskriften", paragraf="24-2")` → finner avvisningssaker
2. `hent_sak("2023/XXX")` → leser sammendrag og utfall
3. Du presenterer funn og avslutter med: "Vil du se lovteksten i FOA § 24-2, eller flere saker om avvisning?"

## Søketips

- Søk på innklaget virksomhet: `sok("Oslo kommune")`
- Søk på tema: `sok("rammeavtale")`
- Søk på regelverk: `sok("anskaffelsesforskriften del III")`
- Eksakt frase: `sok('"ulovlig direkte anskaffelse"')`

## Filtre for siste_saker

- **sakstype**: "Rådgivende sak", "Gebyrsak", "Overtredelsesgebyr"
- **avgjoerelse**: "Brudd på regelverket", "Ikke brudd", "Avvist"
- **innklaget**: Navn på innklaget virksomhet (delvis match)

## finn_praksis — lovhenvisninger

Basert på lovhenvisninger ekstrahert fra avgjørelsestekst (2017+).
Hvert resultat er merket med reguleringsversjon: ny (2016-forskriften) eller gammel (pre-2017).

**Støttede lovnavn og aliaser:**

| Lov | Aliaser |
|-----|---------|
| anskaffelsesforskriften | `forskriften`, `foa` |
| anskaffelsesloven | `loven`, `loa` |
| klagenemndsforskriften | |
| forsyningsforskriften | |
| forvaltningsloven | |
| offentleglova | `offentlighetsloven` |
| konkurranseloven | |

**Eksempler:**
- `finn_praksis(lov="anskaffelsesforskriften", paragraf="8-3")` → kvalifikasjonskrav
- `finn_praksis(lov="foa", paragraf="24-2")` → avvisning av tilbud
- `finn_praksis(lov="loa", paragraf="4")` → grunnleggende prinsipper
- `finn_praksis(lov="forvaltningsloven")` → alle saker som nevner forvaltningsloven

**Merk:** Saker merket «gammel forskrift» bruker anskaffelsesloven 1999 / forskriften 2006.
Paragrafnumre i gammel og ny forskrift kan ha ulik betydning.

## Statistikk

- `statistikk(gruppering="avgjoerelse")` → fordeling av utfall
- `statistikk(gruppering="sakstype")` → fordeling av sakstyper
- `statistikk(aar=2024)` → statistikk for et bestemt år

## Samspill med Paragraf MCP

KOFA MCP og Paragraf MCP utfyller hverandre:

| Spørsmål | KOFA | Paragraf |
|----------|------|----------|
| "Hva sier FOA § 8-3?" | | `lov("anskaffelsesforskriften", "8-3")` |
| "Hvordan tolkes FOA § 8-3 i praksis?" | `finn_praksis(lov="foa", paragraf="8-3")` | |
| "Kan man stille krav om lokal tilknytning?" | `sok("lokal tilknytning")` | `sok("tildelingskriterier")` |

**Beste praksis:** Kombiner lovtekst (Paragraf) med KOFA-praksis for fullstendige svar.

## Begrensninger

- **Kun metadata for eldre saker:** Saker før 2017 har kun parter/tema/utfall, ikke lovhenvisninger
- **Ikke rettsavgjørelser:** KOFA er forvaltningsorgan, ikke domstol — avgjørelsene er ikke bindende rettspraksis
- **Avgjørelsestekst:** `hent_avgjoerelse` gir tilgang til fulltekst for ~2000 saker (2017+). Eldre saker har kun sammendrag
- **Seksjoner i avgjørelsestekst:** `innledning`, `bakgrunn` (faktum), `anfoersler` (partenes argumenter), `vurdering` (nemndas begrunnelse), `konklusjon`
"""


class MCPServer:
    """MCP Server for KOFA decision lookup tools."""

    def __init__(self, service: KofaService | None = None):
        self.service = service or KofaService()
        self.tools = self._define_tools()
        logger.info(f"KOFA MCPServer initialized with {len(self.tools)} tools")

    def _define_tools(self) -> list[dict[str, Any]]:
        """Define available MCP tools with their schemas."""
        return [
            {
                "name": "sok",
                "title": "Søk i KOFA-saker",
                "description": (
                    "Fulltekstsøk i KOFA-avgjørelser. "
                    "Søker i saksnummer, parter, tema og sammendrag. "
                    "Eks: 'rammeavtale', 'Oslo kommune', "
                    "'\"ulovlig direkte anskaffelse\"'"
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "Søketekst. Støtter: OR, \"frase\". "
                                "Eks: 'rammeavtale', 'tildelingskriterier'"
                            ),
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maks antall resultater (standard: 20)",
                            "default": 20,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "hent_sak",
                "title": "Hent KOFA-sak",
                "description": (
                    "Hent en spesifikk KOFA-sak med alle detaljer. "
                    "Bruk saksnummer som '2023/1099'."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "sak_nr": {
                            "type": "string",
                            "description": "Saksnummer (f.eks. '2023/1099')",
                        },
                    },
                    "required": ["sak_nr"],
                },
            },
            {
                "name": "hent_avgjoerelse",
                "title": "Hent avgjørelsestekst",
                "description": (
                    "Hent full avgjørelsestekst fra en KOFA-sak. "
                    "Uten seksjon: viser innholdsfortegnelse med avsnittantall per seksjon. "
                    "Med seksjon: returnerer alle avsnitt i den seksjonen. "
                    "Gyldige seksjoner: 'innledning', 'bakgrunn', 'anfoersler', 'vurdering', 'konklusjon'. "
                    "Eks: hent_avgjoerelse(sak_nr='2023/1099', seksjon='vurdering')"
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "sak_nr": {
                            "type": "string",
                            "description": "Saksnummer (f.eks. '2023/1099')",
                        },
                        "seksjon": {
                            "type": "string",
                            "description": (
                                "Filtrer på seksjon: 'innledning', 'bakgrunn', "
                                "'anfoersler', 'vurdering', 'konklusjon'. "
                                "Utelat for innholdsfortegnelse."
                            ),
                        },
                    },
                    "required": ["sak_nr"],
                },
            },
            {
                "name": "siste_saker",
                "title": "Siste KOFA-saker",
                "description": (
                    "Hent de nyeste KOFA-avgjørelsene med valgfrie filtre. "
                    "Kan filtrere på sakstype, avgjørelse og innklaget."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Antall saker (standard: 20)",
                            "default": 20,
                        },
                        "sakstype": {
                            "type": "string",
                            "description": (
                                "Filtrer på sakstype: "
                                "'Rådgivende sak', 'Gebyrsak', etc."
                            ),
                        },
                        "avgjoerelse": {
                            "type": "string",
                            "description": (
                                "Filtrer på avgjørelse: "
                                "'Brudd på regelverket', 'Ikke brudd', 'Avvist'"
                            ),
                        },
                        "innklaget": {
                            "type": "string",
                            "description": "Filtrer på innklaget (delvis match)",
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "finn_praksis",
                "title": "Finn KOFA-praksis etter lovhenvisning",
                "description": (
                    "Finn KOFA-saker som refererer til en bestemt lov eller forskrift. "
                    "Dekker saker fra 2017+. "
                    "Eks: finn_praksis(lov='anskaffelsesforskriften', paragraf='2-4')"
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "lov": {
                            "type": "string",
                            "description": (
                                "Lovnavn: 'anskaffelsesloven', 'anskaffelsesforskriften', "
                                "'forvaltningsloven', 'konkurranseloven', etc."
                            ),
                        },
                        "paragraf": {
                            "type": "string",
                            "description": "Paragrafnummer (f.eks. '2-4', '12'). Utelat for alle paragrafer.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maks antall resultater (standard: 20)",
                            "default": 20,
                        },
                    },
                    "required": ["lov"],
                },
            },
            {
                "name": "relaterte_saker",
                "title": "Relaterte KOFA-saker",
                "description": (
                    "Finn saker relatert til en gitt KOFA-sak via kryssreferanser. "
                    "Viser både saker denne saken refererer til, og saker som siterer denne. "
                    "Eks: relaterte_saker(sak_nr='2017/147')"
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "sak_nr": {
                            "type": "string",
                            "description": "Saksnummer (f.eks. '2023/1099')",
                        },
                    },
                    "required": ["sak_nr"],
                },
            },
            {
                "name": "mest_siterte",
                "title": "Mest siterte KOFA-saker",
                "description": (
                    "Finn de mest siterte KOFA-sakene. "
                    "Viser prinsipielle avgjørelser som andre saker oftest refererer til. "
                    "Basert på kryssreferanser i avgjørelsestekst (2020+)."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Maks antall resultater (standard: 20)",
                            "default": 20,
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "eu_praksis",
                "title": "Finn EU-domstolspraksis i KOFA",
                "description": (
                    "Finn KOFA-saker som refererer til en bestemt EU-domstolsavgjørelse. "
                    "Eks: eu_praksis(eu_case_id='C-19/00') for SIAC Construction"
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "eu_case_id": {
                            "type": "string",
                            "description": "EU-saksnummer (f.eks. 'C-19/00', 'C-368/10')",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maks antall resultater (standard: 20)",
                            "default": 20,
                        },
                    },
                    "required": ["eu_case_id"],
                },
            },
            {
                "name": "mest_siterte_eu",
                "title": "Mest siterte EU-dommer i KOFA",
                "description": (
                    "Finn de mest siterte EU-domstolsavgjørelsene i KOFA-saker. "
                    "Viser hvilke EU-dommer KOFA oftest refererer til."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Maks antall resultater (standard: 20)",
                            "default": 20,
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "statistikk",
                "title": "KOFA-statistikk",
                "description": (
                    "Aggregert statistikk over KOFA-saker. "
                    "Kan grupperes etter avgjørelse, sakstype, etc. "
                    "Valgfritt filtrere på år."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "aar": {
                            "type": "integer",
                            "description": "Filtrer på år (f.eks. 2024)",
                        },
                        "gruppering": {
                            "type": "string",
                            "description": (
                                "Felt å gruppere på: "
                                "'avgjoerelse', 'sakstype'"
                            ),
                            "default": "avgjoerelse",
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "sync",
                "title": "Synkroniser KOFA-data",
                "description": (
                    "Synkroniser saker fra KOFA. "
                    "Henter saker via WordPress API og beriker med HTML-metadata."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "scrape": {
                            "type": "boolean",
                            "description": "Også skrape HTML-metadata (langsom)",
                            "default": False,
                        },
                        "force": {
                            "type": "boolean",
                            "description": "Tving full re-synkronisering",
                            "default": False,
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maks antall å skrape (kun med scrape=true)",
                        },
                    },
                    "required": [],
                },
            },
            {
                "name": "status",
                "title": "KOFA-status",
                "description": "Vis status for synkronisert KOFA-data.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        ]

    def handle_request(self, body: dict[str, Any]) -> dict[str, Any]:
        """Handle incoming MCP JSON-RPC request."""
        method = body.get("method", "")
        params = body.get("params", {})
        request_id = body.get("id")

        logger.debug(f"MCP request: method={method}, id={request_id}")

        try:
            if method == "initialize":
                result = self.handle_initialize(params)
            elif method == "initialized":
                result = {}
            elif method == "tools/list":
                result = self.handle_tools_list()
            elif method == "tools/call":
                result = self.handle_tools_call(params)
            elif method == "resources/list":
                result = {"resources": []}
            elif method == "resources/read":
                result = {"contents": []}
            elif method == "prompts/list":
                result = {"prompts": []}
            elif method == "ping":
                result = {}
            else:
                logger.warning(f"Unknown MCP method: {method}")
                return self._error_response(request_id, -32601, f"Method not found: {method}")

            return self._success_response(request_id, result)

        except Exception as e:
            logger.exception(f"Error handling MCP request: {e}")
            return self._error_response(request_id, -32603, str(e))

    def handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle initialize request."""
        client_info = params.get("clientInfo", {})
        logger.info(
            f"MCP client connected: {client_info.get('name', 'unknown')} "
            f"v{client_info.get('version', '?')}"
        )

        return {
            "protocolVersion": PROTOCOL_VERSION,
            "serverInfo": SERVER_INFO,
            "capabilities": {
                "tools": {},
                "resources": {},
                "prompts": {},
            },
            "instructions": SERVER_INSTRUCTIONS.strip(),
        }

    def handle_tools_list(self) -> dict[str, Any]:
        """Return list of available tools."""
        return {"tools": self.tools}

    def handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool call."""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        logger.info(f"Tool call: {tool_name} with args: {arguments}")

        try:
            if tool_name == "sok":
                content = self.service.search(
                    arguments.get("query", ""),
                    arguments.get("limit", 20),
                )
            elif tool_name == "hent_sak":
                content = self.service.get_case(arguments.get("sak_nr", ""))
            elif tool_name == "hent_avgjoerelse":
                content = self.service.get_decision_text(
                    sak_nr=arguments.get("sak_nr", ""),
                    section=arguments.get("seksjon"),
                )
            elif tool_name == "siste_saker":
                content = self.service.recent_cases(
                    limit=arguments.get("limit", 20),
                    sakstype=arguments.get("sakstype"),
                    avgjoerelse=arguments.get("avgjoerelse"),
                    innklaget=arguments.get("innklaget"),
                )
            elif tool_name == "finn_praksis":
                content = self.service.finn_praksis(
                    lov=arguments.get("lov", ""),
                    paragraf=arguments.get("paragraf"),
                    limit=arguments.get("limit", 20),
                )
            elif tool_name == "relaterte_saker":
                content = self.service.related_cases(
                    sak_nr=arguments.get("sak_nr", ""),
                )
            elif tool_name == "mest_siterte":
                content = self.service.most_cited(
                    limit=arguments.get("limit", 20),
                )
            elif tool_name == "eu_praksis":
                content = self.service.eu_praksis(
                    eu_case_id=arguments.get("eu_case_id", ""),
                    limit=arguments.get("limit", 20),
                )
            elif tool_name == "mest_siterte_eu":
                content = self.service.mest_siterte_eu(
                    limit=arguments.get("limit", 20),
                )
            elif tool_name == "statistikk":
                content = self.service.statistics(
                    aar=arguments.get("aar"),
                    gruppering=arguments.get("gruppering", "avgjoerelse"),
                )
            elif tool_name == "sync":
                content = self.service.sync(
                    scrape=arguments.get("scrape", False),
                    force=arguments.get("force", False),
                    limit=arguments.get("limit"),
                )
            elif tool_name == "status":
                content = self.service.get_status()
            else:
                content = f"Ukjent verktøy: {tool_name}"
                logger.warning(f"Unknown tool requested: {tool_name}")

            return {
                "content": [{"type": "text", "text": content}]
            }

        except Exception as e:
            logger.exception(f"Tool execution error: {e}")
            return {
                "content": [{"type": "text", "text": f"Feil ved kjøring av {tool_name}: {e}"}],
                "isError": True,
            }

    def _success_response(self, request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
        """Format successful JSON-RPC response."""
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def _error_response(self, request_id: Any, code: int, message: str) -> dict[str, Any]:
        """Format error JSON-RPC response."""
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
