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
from websockets.frames import Close

from .._mcp import CREATE_TOOL, DESTRUCTIVE_TOOL, READ_ONLY_TOOL, mcp
from ..formatters import (
    format_deletion,
    format_registered_queries,
    format_registration,
    format_stream,
)
from ..http import _api_error_details, fetch
from ..params import (
    CATEGORY_FILTER,
    COUNTRY_FILTER,
    CREATOR_FILTER,
    DATATYPE_FILTER,
    EXCLUDE_FIELD_FILTER,
    LANGUAGE_FILTER,
    ORGANIZATION_FILTER,
    QUERY,
    QUERY_IN_META,
    QUERY_IN_TITLE,
    REALTIME_FLAG,
    REGION_FILTER,
    REGISTRATION_ID,
    REMOVE_DUPLICATE,
    SENTIMENT,
    SENTIMENT_SCORE,
    SOURCE_PRIORITY,
    SOURCE_URL_FILTER,
    STREAM_CONTENT,
    STREAM_MAX_ARTICLES,
    STREAM_WAIT_SECONDS,
    TAG_FILTER,
    TIMEZONE,
)
from ..settings import (
    NEWSDATA_API_KEY,
    NEWSDATA_WS_API_URL,
    NEWSDATA_WS_URL,
    WS_INTERNAL_ERROR,
    WS_MAX_ARTICLES,
    WS_MAX_WAIT_SECONDS,
    WS_NEWS_TYPE,
    WS_POLICY_VIOLATION,
)
from ..validators import check_mutex_groups, check_sentiment_score_requires_sentiment

logger = logging.getLogger(__name__)


@mcp.tool(annotations=CREATE_TOOL, structured_output=False)
async def register_realtime_query(
    q: QUERY = None,
    q_in_title: QUERY_IN_TITLE = None,
    q_in_meta: QUERY_IN_META = None,
    country: COUNTRY_FILTER = None,
    exclude_country: COUNTRY_FILTER = None,
    category: CATEGORY_FILTER = None,
    exclude_category: CATEGORY_FILTER = None,
    language: LANGUAGE_FILTER = None,
    exclude_language: LANGUAGE_FILTER = None,
    source_url: SOURCE_URL_FILTER = None,
    exclude_source_url: SOURCE_URL_FILTER = None,
    source_priority: SOURCE_PRIORITY = None,
    timezone: TIMEZONE = None,
    content: REALTIME_FLAG = None,
    image: REALTIME_FLAG = None,
    video: REALTIME_FLAG = None,
    remove_duplicate: REMOVE_DUPLICATE = None,
    tag: TAG_FILTER = None,
    sentiment: SENTIMENT = None,
    sentiment_score: SENTIMENT_SCORE = None,
    region: REGION_FILTER = None,
    organization: ORGANIZATION_FILTER = None,
    creator: CREATOR_FILTER = None,
    datatype: DATATYPE_FILTER = None,
    exclude_field: EXCLUDE_FIELD_FILTER = None,
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
    - Do NOT combine `category` with `exclude_category`.
    - Do NOT combine `language` with `exclude_language`.
    - Do NOT combine `source_url` with `exclude_source_url`.
    - `sentiment_score` requires `sentiment` to also be set.

    Other guidance:
    - There are NO date or paging filters here: a registered query matches
      news as it is published, not historical news. For historical news use
      `get_news`.
    - At least ONE of these is required, or the API answers Error (HTTP 400):
      `q`, `q_in_title`, `q_in_meta`, `country`, `category`, `language`,
      `source_url`, `source_priority`, `image`, `video`, `content`.
    - Keep the query narrow: every article it matches costs 1 credit when it
      is streamed.
    - Registering the SAME filters twice answers Error (HTTP 409); the
      existing id is in the message. Call `list_realtime_queries` first.
    - A plan allows a fixed number of registrations. When they are used up
      the answer is Error (HTTP 429, RegistrationLimitExceeded): reuse an id
      from `list_realtime_queries`, or free one with `delete_realtime_query`.

    Examples:
    - `q="bitcoin", language="en"` → English bitcoin news as it breaks
    - `category="technology", country="us", source_priority="top"`
    - `q="earnings beat", organization="tesla,nvidia"`
    """
    # Parameter names are the API's own names, so the arguments are the query
    # parameters. Keep this the first statement: `locals()` must hold only the
    # arguments.
    params = dict(locals())

    error = (
        check_mutex_groups(params)
        or check_sentiment_score_requires_sentiment(params)
    )
    if error:
        return f"Error: {error}"

    data = await fetch(
        "websocket/register",
        {**params, "news_type": WS_NEWS_TYPE},
        method="POST",
        base_url=NEWSDATA_WS_API_URL,
    )
    return format_registration(data)


@mcp.tool(annotations=READ_ONLY_TOOL, structured_output=False)
async def list_realtime_queries() -> str:
    """
    Use this tool to SEE which real-time queries are already registered on
    the account, with their `registration_id` values and filters.

    Call this before `register_realtime_query` to avoid creating a duplicate
    (which the API rejects with 409), and to recover an id you want to pass
    to `stream_news` or `delete_realtime_query`.

    Strict rules: none. Takes no parameters.
    """
    # This call and the delete call send the key as the `apikey` query
    # parameter (the endpoints take it there or in the `X-ACCESS-KEY` header);
    # `http._RedactApiKey` keeps it out of the request log.
    data = await fetch("websocket/fetch", {"apikey": NEWSDATA_API_KEY}, base_url=NEWSDATA_WS_API_URL)
    return format_registered_queries(data)


@mcp.tool(annotations=DESTRUCTIVE_TOOL, structured_output=False)
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
        {"apikey": NEWSDATA_API_KEY, "registration_id": registration_id},
        method="DELETE",
        base_url=NEWSDATA_WS_API_URL,
    )
    return format_deletion(data, registration_id)


@mcp.tool(annotations=READ_ONLY_TOOL, structured_output=False)
async def stream_news(
    registration_id: REGISTRATION_ID,
    max_articles: STREAM_MAX_ARTICLES = 10,
    wait_seconds: STREAM_WAIT_SECONDS = 30,
    content: STREAM_CONTENT = False,
) -> str:
    """
    Use this tool to COLLECT real-time articles for an already-registered
    query. Register it first with `register_realtime_query`.

    This listens on a live connection and returns as soon as EITHER
    `max_articles` have arrived OR `wait_seconds` elapses — whichever comes
    first. It always returns within `wait_seconds`; it does not run forever.
    The reply says `stopped_because: max_articles | timeout |
    connection_closed | error`, so you can tell "the cap was hit, there may be
    more" from "the feed was quiet".

    Call it again to keep listening — the registration stays alive. Only
    articles published WHILE a call is listening are delivered: what is
    published between two calls is not sent later. For past news use
    `get_news`.

    Strict rules:
    - `registration_id` is required and must already be registered.
    - `max_articles` is clamped to 1..50, `wait_seconds` to 1..120.

    Other guidance:
    - An empty result is NORMAL for a narrow query: it means nothing matched
      during the window, not that anything failed. Do not retry in a tight
      loop; either widen the query or wait longer.
    - Full text: left out by default, because it is long. Pass `content=true`
      to include it in a call. An article is delivered only once, so to read
      one that already arrived in full, call `get_news` with `id=<its id>`.
    - COST: every article the service delivers while this tool listens
      consumes 1 API credit per connected device. Articles arrive in batches:
      a batch that goes past `max_articles` is charged in full, and the extra
      articles are not shown and not sent again. A narrow query is what keeps
      the cost down.
    - At most 5 devices may stream one `registration_id` at a time; one more
      is refused with an Error (DeviceLimitExceeded).
    - Prefer a longer `wait_seconds` over repeated short calls.
    - A refused connection (bad key, unknown registration_id, used-up
      credits, device limit) returns an Error and is not retried. If the
      service ends the stream after articles have arrived, they are returned
      with `stopped_because: error` and the reason on a `stream_ended_with:`
      line.

    Examples:
    - `registration_id="9b2d1e8a7c4f4b6e9d3a5c7e1f2a4b6c", max_articles=5, wait_seconds=30`
    - `registration_id="9b2d1e8a7c4f4b6e9d3a5c7e1f2a4b6c", max_articles=50, wait_seconds=120` → widest sweep
    - `registration_id="9b2d1e8a7c4f4b6e9d3a5c7e1f2a4b6c", max_articles=3, content=true` → with full text
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
    # Why the service refused or ended the stream, when it did: the error
    # frame it sent, or failing that what its close code says.
    error: dict[str, Any] | None = None
    started = time.monotonic()
    stopped_because = "timeout"

    try:
        # The whole session is bounded, so a slow handshake cannot make the
        # tool outlive its budget.
        async with asyncio.timeout(wait_seconds):
            # max_size=None: one delivery is a batch of articles with their
            # full text and can be larger than the library's 1 MiB default,
            # which would drop the connection and lose the batch.
            async with ws_client.connect(url, open_timeout=None, max_size=None) as websocket:
                async for message in websocket:
                    response = _parse(message)
                    if response is None:
                        continue  # skip malformed frames
                    if response.get("status") == "error":
                        # Not an article: the service says why it is about to
                        # close the connection (refused, credits used up, ...).
                        error = _frame_error(response)
                        continue
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
        # The service accepts every handshake, then closes the connection it
        # refuses or has to end: 1008 for a permanent reason (bad key or
        # registration, credits used up, device limit), 1011 when it failed
        # itself. Before the close it sends an error frame with the message
        # (read in the loop above); an older server sends only the close, with
        # the reason as its text. Any other close — including 1013, a client
        # that read too slowly — is transient: what was collected is returned.
        stopped_because = "connection_closed"
        if error is None and exc.rcvd_then_sent is not False:
            error = _close_error(exc.rcvd)
    except OSError as exc:
        logger.warning("real-time connection failed: %s", exc)
        if not articles:
            return f"Error: could not reach the real-time service ({exc})."
        stopped_because = "connection_closed"

    del articles[max_articles:]
    waited = time.monotonic() - started
    if error is not None:
        stopped_because = "error"
    return format_stream(articles, registration_id, stopped_because, waited, error, full_text=content)


def _frame_error(frame: dict[str, Any]) -> dict[str, Any]:
    """Error envelope for an error frame, ``{"status": "error", "results":
    {"message": ..., "code": ...}}`` — the shape the REST API's errors have."""
    details = _api_error_details(frame)
    details.setdefault("message", "The real-time service ended the stream without giving a reason.")
    return {"status": "error", "status_code": None, **details}


def _close_error(close: Close | None) -> dict[str, Any] | None:
    """Error envelope for a close that refused or failed the stream, used when
    no error frame arrived. ``None`` for every other close: those are transient."""
    if close is None:
        return None
    if close.code == WS_POLICY_VIOLATION:
        return {"status": "error", "status_code": None, "message": close.reason or "connection rejected"}
    if close.code == WS_INTERNAL_ERROR:
        return {
            "status": "error",
            "status_code": None,
            "message": (
                "The real-time service closed the connection because of an error on its side. "
                "The request itself was not rejected; try again later."
            ),
        }
    return None


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
