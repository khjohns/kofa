"""
Flask blueprint factory for KOFA MCP server.

Usage:
    from kofa.web import create_mcp_blueprint
    app.register_blueprint(create_mcp_blueprint(), url_prefix="/mcp")
"""


def create_mcp_blueprint():
    """Create and return Flask MCP blueprint."""
    from flask import Blueprint, Response, jsonify, request

    from kofa import MCPServer, KofaService

    mcp_bp = Blueprint("kofa_mcp", __name__)

    _mcp_server = None

    def get_mcp_server():
        nonlocal _mcp_server
        if _mcp_server is None:
            _mcp_server = MCPServer(KofaService())
        return _mcp_server

    @mcp_bp.route("/", methods=["HEAD"])
    def mcp_head():
        return Response(
            status=200,
            headers={"MCP-Protocol-Version": "2025-06-18", "Content-Type": "application/json"},
        )

    @mcp_bp.route("/", methods=["POST"])
    def mcp_post():
        body = request.get_json()
        if not body:
            return jsonify(
                {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Empty body"}}
            ), 400
        server = get_mcp_server()
        response = server.handle_request(body)
        return jsonify(response)

    @mcp_bp.route("/health", methods=["GET"])
    def mcp_health():
        return jsonify({"status": "ok", "server": "kofa", "version": "0.1.0"})

    return mcp_bp
