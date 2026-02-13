"""
KOFA CLI - MCP server for Norwegian public procurement decisions.

Usage:
    kofa serve                  # stdio MCP server
    kofa serve --http           # HTTP MCP server (Flask)
    kofa sync                   # Sync from KOFA WordPress API
    kofa sync --scrape          # Also scrape HTML metadata
    kofa sync --scrape --limit 100 --max-time 30   # Scrape 100 cases, max 30 min
    kofa sync --force           # Force full re-sync
    kofa status                 # Show sync status
"""

import argparse
import json
import logging
import os
import sys


def cmd_serve(args):
    """Start MCP server (stdio or HTTP)."""
    from kofa import KofaService, MCPServer

    if args.http:
        try:
            from flask import Flask

            from kofa.web import create_mcp_blueprint
        except ImportError:
            print("Flask not installed. Run: pip install kofa[http]", file=sys.stderr)
            sys.exit(1)

        app = Flask(__name__)
        app.register_blueprint(create_mcp_blueprint(), url_prefix="/mcp")

        host = args.host or "0.0.0.0"
        port = args.port or 8000
        print(f"Starting KOFA MCP server on http://{host}:{port}/mcp/")
        app.run(host=host, port=port, debug=args.debug)
    else:
        server = MCPServer(KofaService())
        print("KOFA MCP server (stdio mode). Send JSON-RPC requests via stdin.", file=sys.stderr)

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = server.handle_request(request)
                print(json.dumps(response), flush=True)
            except json.JSONDecodeError as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {e}"},
                }
                print(json.dumps(error_response), flush=True)


def cmd_sync(args):
    """Sync KOFA data."""
    if args.embeddings:
        # Delegate to embedding script
        cmd_embed(args)
        return

    from kofa.service import KofaService

    service = KofaService()
    result = service.sync(
        scrape=args.scrape,
        pdf=args.pdf,
        references=args.references,
        eu_cases=args.eu_cases,
        forarbeider=args.forarbeider,
        force=args.force,
        limit=args.limit,
        max_time=args.max_time,
        delay=args.delay,
        max_errors=args.max_errors,
        verbose=True,
        refresh_pending=args.refresh_pending,
    )
    print(result)


def cmd_embed(args):
    """Generate embeddings for decision text."""
    import subprocess

    script = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "embed_kofa.py")
    script = os.path.normpath(script)

    cmd = [sys.executable, script]
    if args.dry_run:
        cmd.append("--dry-run")
    if args.force:
        cmd.append("--force")
    if args.limit:
        cmd.extend(["--limit", str(args.limit)])
    if args.max_time:
        cmd.extend(["--max-time", str(args.max_time)])
    if hasattr(args, "workers") and args.workers:
        cmd.extend(["--workers", str(args.workers)])

    subprocess.run(cmd)


def cmd_status(args):
    """Show sync status."""
    from kofa.service import KofaService

    service = KofaService()
    print(service.get_status())


def main():
    parser = argparse.ArgumentParser(
        prog="kofa",
        description="MCP server for KOFA decisions (offentlige anskaffelser)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")

    subparsers = parser.add_subparsers(dest="command")

    # serve
    serve_parser = subparsers.add_parser("serve", help="Start MCP server")
    serve_parser.add_argument("--http", action="store_true", help="Use HTTP transport (Flask)")
    serve_parser.add_argument("--host", default=None, help="HTTP host (default: 0.0.0.0)")
    serve_parser.add_argument("--port", type=int, default=None, help="HTTP port (default: 8000)")
    serve_parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")

    # sync
    sync_parser = subparsers.add_parser("sync", help="Sync data from KOFA")
    sync_parser.add_argument("--scrape", action="store_true", help="Also scrape HTML metadata")
    sync_parser.add_argument("--pdf", action="store_true", help="Extract text from decision PDFs")
    sync_parser.add_argument(
        "--references",
        action="store_true",
        help="Extract law/case references from decision text",
    )
    sync_parser.add_argument("--force", "-f", action="store_true", help="Force full re-sync")
    sync_parser.add_argument("--limit", type=int, default=None, help="Max cases to scrape")
    sync_parser.add_argument(
        "--max-time", type=int, default=0, help="Stop after N minutes (0=unlimited)"
    )
    sync_parser.add_argument(
        "--delay", type=float, default=1.0, help="Delay between scrape requests (seconds)"
    )
    sync_parser.add_argument(
        "--max-errors", type=int, default=20, help="Stop after N consecutive errors"
    )
    sync_parser.add_argument(
        "--refresh-pending", action="store_true", help="Re-scrape cases with no decision yet"
    )
    sync_parser.add_argument(
        "--eu-cases",
        action="store_true",
        help="Fetch EU Court judgment text from EUR-Lex",
    )
    sync_parser.add_argument(
        "--forarbeider",
        action="store_true",
        help="Import forarbeider (forarbeids-dokumenter) from PDFs",
    )
    sync_parser.add_argument(
        "--embeddings", action="store_true", help="Generate embeddings for decision text"
    )
    sync_parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done (with --embeddings)"
    )
    sync_parser.add_argument(
        "--workers", type=int, default=1, help="Parallel workers for embedding (default: 1)"
    )

    # status
    subparsers.add_parser("status", help="Show sync status")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if args.command == "serve":
        cmd_serve(args)
    elif args.command == "sync":
        cmd_sync(args)
    elif args.command == "status":
        cmd_status(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
