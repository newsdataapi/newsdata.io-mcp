"""The shared ``FastMCP`` instance and module-wide tool annotations.

Lives in its own module so each `tools/*.py` file can decorate handlers
against the same ``mcp`` singleton without creating a circular import
with the CLI entry point (``server.py``).
"""
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ContentBlock, TextContent, ToolAnnotations

from . import __version__
from .http import close_client

# Every NewsData tool is read-only (no upstream mutation), idempotent
# (same inputs yield the same answer within NewsData's time window),
# and touches an external system (newsdata.io). Sharing one constant
# keeps every `@mcp.tool()` decorator consistent.
READ_ONLY_TOOL = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)

# Registering a real-time query creates server-side state. It is not
# destructive (nothing is lost) and is idempotent in practice — a second
# identical registration answers 409 with the existing id rather than
# creating a duplicate.
CREATE_TOOL = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)

# Deleting a registered query removes server-side state for good.
DESTRUCTIVE_TOOL = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=True,
    openWorldHint=True,
)


@asynccontextmanager
async def _lifespan(server: FastMCP) -> AsyncGenerator[dict[str, Any], None]:
    """Setup/teardown that runs around the server's lifetime.

    Startup does nothing proactive — the httpx client is lazy by
    design. Shutdown closes the singleton client so the connection
    pool is released cleanly instead of leaking until process exit.
    """
    try:
        yield {}
    finally:
        await close_client()


# Sent to the client at initialization. The MCP spec leaves it to the client
# whether the model ever sees this text, so nothing here is needed to use a
# tool correctly: every rule is also in the tool's own description.
_INSTRUCTIONS = """\
News from NewsData.io: articles, news sources and article counts.

Tools that return articles:
- `get_news`         → news articles, recent or historical. The default tool for any news question.
- `get_crypto_news`  → cryptocurrency news. Use when the question is about a coin or crypto.
- `get_market_news`  → stock-market and financial news. Use when the question is about stocks or listed companies.

Tool that returns sources:
- `get_news_sources` → the publishers NewsData.io collects from. Use to find a `source_url`.

Tools that return numbers only (50 credits per call; use only when counts or trends are asked for):
- `get_news_counts`, `get_crypto_counts`, `get_market_counts` → how many articles match, per month, day or hour.

Tools for real-time news (news as it is published, not past news):
- `register_realtime_query` → set up a standing query once; it returns a `registration_id`.
- `stream_news` → collect the articles a registered query matches, for a limited time.
- `list_realtime_queries`, `delete_realtime_query` → see and remove registered queries.

How to call them:
- Pass only the parameters you need and leave the others out.
- Without dates the article and count tools cover the last 30 days. Dates are UTC: `YYYY-MM-DD` or
  `YYYY-MM-DD HH:MM:SS`.
- Multi-value filters take a comma-separated string (`"us,gb"`) or a list (`["us", "gb"]`).
- Flags (`image`, `video`, `content`, `remove_duplicate`) take true or false.
- Article tools return 10 articles per call without the full text. Pass `size` for more (up to 50). To read an
  article in full, call again with `id` set to its id, or add `content=true` to the search.
- More results: pass the result's `next_page` value as `page` and repeat every other argument unchanged.
- When a value is rejected, the error lists valid values close to it: call again with one of those.
"""


def _unknown_parameter_error(tool_name: str, unknown: list[str], valid: list[str]) -> str:
    """Error text for argument names a tool does not have. It names every
    unknown argument and lists the tool's parameters, so the model can
    pick the right one and call again."""
    noun = "parameter" if len(unknown) == 1 else "parameters"
    names = ", ".join(repr(name) for name in unknown)
    if not valid:
        return f"Error: Unknown {noun} {names} for {tool_name}. This tool takes no parameters."
    return f"Error: Unknown {noun} {names} for {tool_name}. Valid parameters: {', '.join(valid)}."


class NewsDataMCP(FastMCP):
    """``FastMCP`` that refuses argument names a tool does not have.

    FastMCP checks a tool's arguments with a pydantic model, and pydantic
    by default ignores names it does not know. A misspelt or invented
    parameter (``keyword``, ``qInTitle``) would be dropped without a word:
    the tool would run without that filter, and the model would take the
    unfiltered result for the answer to its question. The API does reject
    unknown parameters, but it never sees these, because they are gone
    before the request is built.

    The names are checked here, before the call, instead of being sent on
    to the API: this answer can list the valid names, it costs no request
    against the rate limit, and an ``apikey`` argument from the model can
    never reach the query string.
    """

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Sequence[ContentBlock] | dict[str, Any]:
        tools = await self.list_tools()
        tool = next((candidate for candidate in tools if candidate.name == name), None)
        if tool is not None:
            valid = list(tool.inputSchema.get("properties", {}))
            unknown = [argument for argument in arguments if argument not in valid]
            if unknown:
                return [TextContent(type="text", text=_unknown_parameter_error(name, unknown, valid))]
        # An unknown tool name is left to FastMCP, which reports it.
        return await super().call_tool(name, arguments)


mcp = NewsDataMCP(
    name="newsdata",
    lifespan=_lifespan,
    instructions=_INSTRUCTIONS,
)
# FastMCP has no `version` argument; left unset, clients are told the MCP
# SDK's version as if it were this server's.
mcp._mcp_server.version = __version__
