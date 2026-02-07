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

## Verktøy

| Verktøy | Bruk |
|---------|------|
| `sok(query, limit?)` | Fulltekstsøk i KOFA-saker |
| `hent_sak(sak_nr)` | Hent en spesifikk sak med alle detaljer |
| `siste_saker(limit?, sakstype?, avgjoerelse?, innklaget?)` | Siste avgjørelser med filtre |
| `finn_praksis(lov, paragraf?, limit?)` | Finn saker som refererer til en bestemt lovparagraf |
| `statistikk(aar?, gruppering?)` | Aggregert statistikk |

## Søketips

- Søk på innklaget virksomhet: `sok("Oslo kommune")`
- Søk på tema: `sok("rammeavtale")`
- Søk på regelverk: `sok("anskaffelsesforskriften del III")`
- Eksakt frase: `sok('"ulovlig direkte anskaffelse"')`
- Saksnummer: `hent_sak("2023/1099")`

## Filtre for siste_saker

- **sakstype**: "Rådgivende sak", "Gebyrsak", "Overtredelsesgebyr"
- **avgjoerelse**: "Brudd på regelverket", "Ikke brudd", "Avvist"
- **innklaget**: Navn på innklaget virksomhet (delvis match)

## Finn praksis (lovhenvisninger)

- `finn_praksis(lov="anskaffelsesforskriften", paragraf="2-4")` → saker som refererer til foa § 2-4
- `finn_praksis(lov="anskaffelsesloven", paragraf="4")` → saker som refererer til loa § 4
- `finn_praksis(lov="forvaltningsloven")` → alle saker som refererer til forvaltningsloven
- Dekker saker fra 2020+

## Statistikk

- `statistikk(gruppering="avgjoerelse")` → fordeling av utfall
- `statistikk(gruppering="sakstype")` → fordeling av sakstyper
- `statistikk(aar=2024)` → statistikk for et bestemt år

## Tips

- Bruk `sok()` for å finne relevante saker
- Bruk `hent_sak()` for å se alle detaljer inkl. PDF-lenke
- Kombiner med Paragraf MCP for å slå opp lovhjemler som KOFA refererer til
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
                    "Dekker saker fra 2020+. "
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
