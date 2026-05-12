"""CLI entry point for the NewsData MCP server.

Parses ``--transport`` (``stdio`` or ``streamable-http``), ``--host``,
``--port``, and ``--version``, then hands off to ``FastMCP.run``. The
side-effect ``from . import tools`` triggers every `@mcp.tool()`
decorator so all eight tools are registered before the server starts.
"""
import argparse
import logging
import sys

from . import (
    __version__,
    tools,  # noqa: F401 — side-effect: registers @mcp.tool() handlers
)
from ._mcp import mcp

logging.basicConfig(level=logging.INFO, stream=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(prog="newsdata-mcp")
    parser.add_argument(
        "--version",
        action="version",
        version=f"newsdata-mcp {__version__}",
    )
    parser.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    parser.add_argument("--host", default=mcp.settings.host)
    parser.add_argument("--port", type=int, default=mcp.settings.port)
    args = parser.parse_args()

    if args.transport == "streamable-http":
        mcp.settings.host = args.host
        mcp.settings.port = args.port

    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
