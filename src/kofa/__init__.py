"""
KOFA - MCP server for Norwegian public procurement decisions.

Provides access to ~5000 KOFA decisions (Klagenemnda for offentlige anskaffelser)
through the Model Context Protocol (MCP).

Usage:
    # As CLI
    kofa serve           # stdio MCP server
    kofa serve --http    # HTTP MCP server

    # As library
    from kofa import MCPServer, KofaService
"""

from kofa.server import MCPServer
from kofa.service import KofaService

__version__ = "0.1.0"
__all__ = ["MCPServer", "KofaService"]
