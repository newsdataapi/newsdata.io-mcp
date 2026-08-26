"""Tool registrations for the NewsData MCP server.

Importing this package as a side-effect registers every `@mcp.tool()`
decorated function on the shared `mcp` instance from `_mcp.py`. The
entry point (`server.py`) does `from . import tools` for exactly that
reason; the individual modules are not meant to be imported by user
code.
"""
from . import (  # noqa: F401 — registers tools
    archive,
    count,
    crypto,
    crypto_count,
    latest,
    market,
    market_count,
    realtime,
    sources,
)

__all__ = [
    "archive",
    "count",
    "crypto",
    "crypto_count",
    "latest",
    "market",
    "market_count",
    "realtime",
    "sources",
]
