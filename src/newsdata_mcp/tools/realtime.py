"""Real-time WebSocket tools.

The NewsData real-time service is a two-step flow: register a query
once (`register_realtime_query`), then stream the news it matches
(`stream_news`). MCP tools are request/response, so `stream_news` is
deliberately *bounded* — it listens until it has collected
``max_articles`` or ``wait_seconds`` elapses, then returns what it saw.
Call it again to keep listening; the registration persists until it is
deleted.
"""
import asyncio
import json
import logging
import time
from typing import Any

from websockets.asyncio import client as ws_client
from websockets.exceptions import ConnectionClosed, InvalidStatus

from .._mcp import CREATE_TOOL, DESTRUCTIVE_TOOL, READ_ONLY_TOOL, mcp
from ..formatters import (
    format_deletion,
    format_registered_queries,
    format_registration,
    format_stream,
)
from ..http import fetch
from ..params import (
    CATEGORY_FILTER,
    COUNTRY_FILTER,
    CREATOR_FILTER,
    DATATYPE_FILTER,
    DOMAIN_FILTER,
    DOMAIN_URL_FILTER,
    EXCLUDE_FIELD_FILTER,
    FLAG,
    LANGUAGE_FILTER,
    ORGANIZATION_FILTER,
    PRIORITY_DOMAIN,
    QUERY,
    REGION_FILTER,
    REGISTRATION_ID,
    REMOVE_DUPLICATE,
    SENTIMENT,
    SENTIMENT_SCORE,
    TAG_FILTER,
    TIMEZONE,
)
from ..settings import (
    NEWSDATA_API_KEY,
    NEWSDATA_WS_URL,
    WS_MAX_ARTICLES,
    WS_MAX_WAIT_SECONDS,
    WS_NEWS_TYPE,
    WS_POLICY_VIOLATION,
)
from ..validators import check_mutex_groups, check_sentiment_score_requires_sentiment

logger = logging.getLogger(__name__)


@mcp.tool(annotations=CREATE_TOOL)
async def register_realtime_query(
    q: QUERY | None = None,
    q_in_title: QUERY | None = None,
    q_in_meta: QUERY | None = None,
    country: COUNTRY_FILTER | None = None,
    exclude_country: COUNTRY_FILTER | None = None,
    category: CATEGORY_FILTER | None = None,
    exclude_category: CATEGORY_FILTER | None = None,
    language: LANGUAGE_FILTER | None = None,
    exclude_language: LANGUAGE_FILTER | None = None,
    domain: DOMAIN_FILTER | None = None,
    domainurl: DOMAIN_URL_FILTER | None = None,
    exclude_domain: DOMAIN_FILTER | None = None,
    priority_domain: PRIORITY_DOMAIN | None = None,
    timezone: TIMEZONE | None = None,
    full_content: FLAG | None = None,
    image: FLAG | None = None,
    video: FLAG | None = None,
    removeduplicate: REMOVE_DUPLICATE | None = None,
    tag: TAG_FILTER | None = None,
    sentiment: SENTIMENT | None = None,
    sentiment_score: SENTIMENT_SCORE | None = None,
    region: REGION_FILTER | None = None,
    organization: ORGANIZATION_FILTER | None = None,
    creator: CREATOR_FILTER | None = None,
    datatype: DATATYPE_FILTER | None = None,
    excludefield: EXCLUDE_FIELD_FILTER | None = None,
) -> str:
    """
    Use this tool to SET UP a real-time news feed. It registers a standing
    query on the account and returns a `registration_id`. It does NOT return
    articles — pass the id to `stream_news` for those.

    Register once, then stream many times. Registrations persist across
    sessions; use `list_realtime_queries` to see what already exists before
    creating another.

    Strict rules (this tool returns Error before any API call if violated):
    - Use only ONE of `q`, `q_in_title`, or `q_in_meta`.
    - Do NOT combine `country` with `exclude_country`.
    - Do NOT combine `language` with `exclude_language`.
    - Do NOT combine `domain`, `domainurl`, and/or `exclude_domain` with each other.
    - `sentiment_score` requires `sentiment` to also be set.

    Other guidance:
    - There are NO date or paging filters here: a registered query matches
      news as it is published, not historical news. For historical news use
      `get_archive_news`.
    - Registering the SAME filters twice answers Error (HTTP 409); the
      existing id is in the message. Call `list_realtime_queries` first.
    - Narrow the query. A broad one (no filters) will fire constantly.

    Examples:
    - `q="bitcoin", language="en"` → English bitcoin news as it breaks
    - `category="technology", country="us", priority_domain="top"`
    - `q="earnings beat", organization="tesla,nvidia"`
    """
    error = (
        check_mutex_groups(locals())
        or check_sentiment_score_requires_sentiment(locals())
    )
    if error:
        return f"Error: {error}"

    data = await fetch(
        "websocket/register",
        {
            "q": q,
            "qInTitle": q_in_title,
            "qInMeta": q_in_meta,
            "country": country,
            "excludecountry": exclude_country,
            "category": category,
            "excludecategory": exclude_category,
            "language": language,
            "excludelanguage": exclude_language,
            "domain": domain,
            "domainurl": domainurl,
            "excludedomain": exclude_domain,
            "prioritydomain": priority_domain,
            "timezone": timezone,
            "full_content": full_content,
            "image": image,
            "video": video,
            "removeduplicate": removeduplicate,
            "tag": tag,
            "sentiment": sentiment,
            "sentiment_score": sentiment_score,
            "region": region,
            "organization": organization,
            "creator": creator,
            "datatype": datatype,
            "excludefield": excludefield,
            "news_type": WS_NEWS_TYPE,
        },
        method="POST",
    )
    return format_registration(data)


@mcp.tool(annotations=READ_ONLY_TOOL)
async def list_realtime_queries() -> str:
    """
    Use this tool to SEE which real-time queries are already registered on
    the account, with their `registration_id` values and filters.

    Call this before `register_realtime_query` to avoid creating a duplicate
    (which the API rejects with 409), and to recover an id you want to pass
    to `stream_news` or `delete_realtime_query`.

    Strict rules: none. Takes no parameters.
    """
    data = await fetch("websocket/fetch", {})
    return format_registered_queries(data)


@mcp.tool(annotations=DESTRUCTIVE_TOOL)
async def delete_realtime_query(registration_id: REGISTRATION_ID) -> str:
    """
    Use this tool to PERMANENTLY REMOVE a registered real-time query.

    The registration is gone afterwards and `stream_news` will no longer
    accept that `registration_id`. This does not delete any articles — only
    the standing query. Confirm with the user before calling it on an id you
    did not just create.

    Strict rules:
    - `registration_id` is required. Get it from `list_realtime_queries`.
    """
    data = await fetch(
        "websocket/delete",
        {"registration_id": registration_id},
        method="DELETE",
    )
    return format_deletion(data, registration_id)


@mcp.tool(annotations=READ_ONLY_TOOL)
async def stream_news(
    registration_id: REGISTRATION_ID,
    max_articles: int = 10,
    wait_seconds: float = 30,
) -> str:
    """
    Use this tool to COLLECT real-time articles for an already-registered
    query. Register it first with `register_realtime_query`.

    This listens on a live connection and returns as soon as EITHER
    `max_articles` have arrived OR `wait_seconds` elapses — whichever comes
    first. It always returns within `wait_seconds`; it does not run forever.
    The reply says `stopped_because: max_articles | timeout |
    connection_closed`, so you can tell "the cap was hit, there may be more"
    from "the feed was quiet".

    Call it again to keep listening — the registration stays alive, and a new
    call picks up whatever has been published since.

    Strict rules:
    - `registration_id` is required and must already be registered.
    - `max_articles` is clamped to 1..50, `wait_seconds` to 1..120.

    Other guidance:
    - An empty result is NORMAL for a narrow query: it means nothing matched
      during the window, not that anything failed. Do not retry in a tight
      loop; either widen the query or wait longer.
    - COST: every article delivered consumes 1 API credit per connected
      device. A broad query on a long window can burn credits quickly — keep
      `max_articles` no higher than you need.
    - At most 5 devices may stream one `registration_id` at a time; beyond
      that the connection is rejected with "device limit reached".
    - Prefer a longer `wait_seconds` over repeated short calls.
    - A rejected connection (bad key, unknown registration_id, exhausted
      credits, device limit) returns an Error and is not retried.

    Examples:
    - `registration_id="a1b2c3", max_articles=5, wait_seconds=30`
    - `registration_id="a1b2c3", max_articles=50, wait_seconds=120` → widest sweep
    """
    if not NEWSDATA_API_KEY:
        return "Error: NEWSDATA_API_KEY is not configured."

    max_articles = max(1, min(int(max_articles), WS_MAX_ARTICLES))
    wait_seconds = max(1.0, min(float(wait_seconds), WS_MAX_WAIT_SECONDS))

    url = (
        f"{NEWSDATA_WS_URL}?apikey={NEWSDATA_API_KEY}"
        f"&registration_id={registration_id}"
    )

    articles: list[dict[str, Any]] = []
    started = time.monotonic()
    stopped_because = "timeout"

    try:
        # The whole session is bounded, so a slow handshake cannot make the
        # tool outlive its budget.
        async with asyncio.timeout(wait_seconds):
            async with ws_client.connect(url, open_timeout=None) as websocket:
                async for message in websocket:
                    response = _parse(message)
                    if response is None:
                        continue  # skip malformed frames
                    results = response.get("results")
                    if isinstance(results, list):
                        articles.extend(a for a in results if isinstance(a, dict))
                    elif isinstance(results, dict):
                        articles.append(results)
                    if len(articles) >= max_articles:
                        stopped_because = "max_articles"
                        break
                else:
                    # Iteration ended on its own: the server closed the feed
                    # rather than us hitting the cap or the deadline.
                    stopped_because = "connection_closed"
    except TimeoutError:
        stopped_because = "timeout"
    except InvalidStatus as exc:
        status = exc.response.status_code
        if status in (401, 403):
            return (
                f"Error (HTTP {status}): the real-time connection was rejected. "
                "Check the API key, the WebSocket entitlement on the plan, and "
                "that the registration_id exists (list_realtime_queries)."
            )
        return f"Error (HTTP {status}): could not open the real-time connection."
    except ConnectionClosed as exc:
        # The server accepts every handshake and then closes with 1008 on a
        # permanent failure: "invalid credentials or registration not found",
        # "api limit reached", or "device limit reached".
        close = exc.rcvd
        if close is not None and close.code == WS_POLICY_VIOLATION:
            reason = close.reason or "connection rejected"
            return f"Error: {reason}"
        # Any other close — including 1013 "send timeout" — is transient;
        # return whatever was collected before the drop.
        stopped_because = "connection_closed"
    except OSError as exc:
        logger.warning("real-time connection failed: %s", exc)
        if not articles:
            return f"Error: could not reach the real-time service ({exc})."
        stopped_because = "connection_closed"

    del articles[max_articles:]
    waited = time.monotonic() - started
    return format_stream(articles, registration_id, stopped_because, waited)


def _parse(message: Any) -> dict[str, Any] | None:
    """Decode one frame, returning None when it isn't a JSON object."""
    if isinstance(message, bytes | bytearray):
        try:
            message = message.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if not isinstance(message, str):
        return None
    try:
        parsed = json.loads(message)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None
