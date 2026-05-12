"""The shared ``FastMCP`` instance and module-wide tool annotations.

Lives in its own module so each `tools/*.py` file can decorate handlers
against the same ``mcp`` singleton without creating a circular import
with the CLI entry point (``server.py``).
"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .http import close_client

# Every NewsData tool is read-only (no upstream mutation), idempotent
# (same inputs yield the same answer within NewsData's time window),
# and touches an external system (newsdata.io). Sharing one constant
# keeps all eight `@mcp.tool()` decorators consistent.
READ_ONLY_TOOL = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)


@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    """Setup/teardown that runs around the server's lifetime.

    Startup does nothing proactive — the httpx client is lazy by
    design. Shutdown closes the singleton client so the connection
    pool is released cleanly instead of leaking until process exit.
    """
    try:
        yield {}
    finally:
        await close_client()


mcp = FastMCP(
    name="newsdata",
    lifespan=_lifespan,
    instructions="""
        Real-time and historical news via newsdata.io.

        Article-content tools (return article text, metadata, links):
        - `get_latest_news`   → real-time news from last 48 hours. Use for "latest", "recent", "today" queries.
        - `get_archive_news`  → historical news older than 48 hours. Use when a date range is given.
        - `get_crypto_news`   → crypto-only news. Use when query is about bitcoin, ethereum, or any coin.
        - `get_market_news`   → stock/financial news. Use when query is about stocks, tickers, or companies.

        Aggregate-count tools (return per-bucket article counts over a date range, NOT article content):
        - `get_news_counts`    → general article counts. Use when the user asks how many articles per day/week/month.
        - `get_crypto_counts`  → crypto article counts.
        - `get_market_counts`  → market/financial article counts.

        Source-discovery tool:
        - `get_news_sources`  → discover available sources. Use when user wants to explore what sources exist.

        Strict rules — enforced locally on every tool (where applicable).
        Violating any of these returns "Error: ..." without contacting the API:
        - Use only ONE of `q`, `q_in_title`, or `q_in_meta` per request.
        - Do NOT combine `country` with `exclude_country`.
        - Do NOT combine `category` with `exclude_category`.
        - Do NOT combine `language` with `exclude_language`.
        - Do NOT combine `domain`, `domainurl`, and/or `exclude_domain` with each other.
        - `sentiment_score` (where present) requires `sentiment` to also be set.

        Other guidance (advisory; not locally enforced):
        - Never pass None, null, or empty string — omit optional parameters entirely.
        - Multi-value filters (country, exclude_country, language, exclude_language,
          category, exclude_category, tag, region, domain, exclude_domain, domainurl,
          coin, symbol, organization, article_id, creator, datatype, excludefield)
          accept EITHER a Python list `['us', 'gb']` OR a comma-separated string `'us,gb'`.
          Lists are preferred for clarity.
        - Boolean flags (image, video, full_content, removeduplicate) accept True/False (preferred)
          or 1/0. For removeduplicate, pass True to enable; pass False or omit to disable
          (the API rejects 0).
        - timeframe accepts plain integers for hours (e.g. `24`) or strings with `m` suffix
          for minutes (e.g. `90m`).
    """
)
