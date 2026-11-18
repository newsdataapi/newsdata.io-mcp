"""Tool registrations for the NewsData MCP server.

Importing this package as a side-effect registers every `@mcp.tool()`
decorated function on the shared `mcp` instance from `_mcp.py`. The
entry point (`server.py`) does `from . import tools` for exactly that
reason; the individual modules are not meant to be imported by user
code.

One module per NewsData API endpoint:

    news.py          get_news           /news
    crypto.py        get_crypto_news    /crypto
    market.py        get_market_news    /market
    sources.py       get_news_sources   /sources
    count.py         get_news_counts    /count/news
    crypto_count.py  get_crypto_counts  /count/crypto
    market_count.py  get_market_counts  /count/market

Plus `realtime.py`, which holds the four real-time (WebSocket) tools:
`register_realtime_query`, `list_realtime_queries`, `delete_realtime_query`
and `stream_news`.
"""
from . import (  # noqa: F401 — registers tools
    count,
    crypto,
    crypto_count,
    market,
    market_count,
    news,
    realtime,
    sources,
)

__all__ = [
    "count",
    "crypto",
    "crypto_count",
    "market",
    "market_count",
    "news",
    "realtime",
    "sources",
]
