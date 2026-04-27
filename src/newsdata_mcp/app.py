from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    name="newsdata",
    instructions="""
        Real-time and historical news via newsdata.io.

        Available tools and when to use them:
        - `get_latest_news`   → real-time news from last 48 hours. Use for "latest", "recent", "today" queries.
        - `get_archive_news`  → historical news older than 48 hours. Use when a date range is given.
        - `get_crypto_news`   → crypto-only news. Use when query is about bitcoin, ethereum, or any coin.
        - `get_market_news`   → stock/financial news. Use when query is about stocks, tickers, or companies.
        - `get_news_sources`  → discover available sources. Use when user wants to explore what sources exist.

        Global rules that apply to ALL tools:
        - Never pass None, null, or empty string — omit optional parameters entirely.
        - Never combine an include and its exclude for the same field (e.g. country + exclude_country).
        - Always use only ONE of q, q_in_title, or q_in_meta per request.
        - Comma-separated filters must have no spaces around commas.
        - Boolean flags use 1 or 0, not True or False.
    """
)