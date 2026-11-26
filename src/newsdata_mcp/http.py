"""HTTP layer for the NewsData.io REST API.

Owns a lazy module-level ``httpx.AsyncClient`` so we reuse one
connection pool across tool calls. Authentication (``X-ACCESS-KEY``),
``User-Agent`` and ``Accept-Language: en`` live on the client. Errors are
returned as a ``{"status": "error", "message": ...}`` envelope rather than
raised, to keep tool functions return-type clean (MCP tools must return
``str``).

Error bodies are passed on, not replaced. NewsData answers a failed
request with ``{"status": "error", "results": {"message": ..., "code":
..., "recommendations": {...}}}``; the message, the code and the suggested
values are what lets a model correct its own call, so they go into the
envelope as they are. A generic message is used only when the body is not
in that shape (a proxy's HTML page, an empty body).

Retry policy:

- Network errors → retry with exponential backoff: a timeout
  (``TimeoutException``), or a connection that could not be opened or
  broke while the request or the response was in transit
  (``NetworkError``, ``RemoteProtocolError``). Setup errors are permanent:
  an illegal header value (``LocalProtocolError``), a proxy that refuses
  (``ProxyError``), a URL scheme httpx cannot send (``UnsupportedProtocol``).
- HTTP 5xx → retry with exponential backoff.
- HTTP 429 ``RateLimitExceeded`` / ``TooManyRequests`` → retry after
  waiting ``Retry-After`` plus one second (integer seconds or HTTP-date
  per RFC 7231) when parseable; falling back to exponential backoff
  otherwise. A ``Retry-After`` longer than ``NEWSDATA_RETRY_BACKOFF_MAX``
  is not waited out: the error is returned at once with the wait in it,
  because a tool call that sleeps for minutes looks dead to the model.
- HTTP 429 ``ApiLimitExceeded`` / ``ApiKeyLimitExceeded`` (credits used
  up) and ``RegistrationLimitExceeded`` (no real-time registration left
  on the plan) → permanent failure: waiting a few seconds changes
  neither.
- HTTP 400/401/403/422/other 4xx, non-JSON 2xx, soft 200 errors →
  permanent failure, never retried.

Error envelope::

    {"status": "error", "message": str, "status_code": int | None,
     "error_code": str, "recommendations": dict, "registration_id": str,
     "retry_after": int}

``status_code`` is ``None`` for non-HTTP failures (timeout, missing
key). ``error_code``, ``recommendations`` and ``registration_id`` are
present only when the API sent them. ``retry_after`` is present only on 429s that included a
parseable header.
"""
import asyncio
import json
import logging
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from . import __version__
from .settings import (
    MAX_RETRIES,
    NEWSDATA_API_KEY,
    NEWSDATA_BASE_URL,
    QUOTA_EXHAUSTED_CODES,
    REQUEST_TIMEOUT,
    RETRY_BACKOFF,
    RETRY_BACKOFF_MAX,
)

logger = logging.getLogger(__name__)

# Wire-name keys whose semantics differ from a plain bool→{1,0} mapping.
# `remove_duplicate` only does something when it is `1`; `False` means
# "I don't want the filter", which is communicated to NewsData by
# omitting the parameter.
_BOOL_TRUTHY_ONLY_KEYS = frozenset({"remove_duplicate"})

# The key normally travels in the `X-ACCESS-KEY` header. Two real-time calls
# (list and delete) send it as the `apikey` query parameter, and httpx writes
# every request URL to its log at INFO level, so without this filter those two
# calls would write the key to the server log.
_APIKEY_IN_URL = re.compile(r"(apikey=)[^&\s\"']+", re.IGNORECASE)


class _RedactApiKey(logging.Filter):
    """Replace the value of an `apikey` query parameter in a log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if "apikey=" in message.lower():
            record.msg = _APIKEY_IN_URL.sub(r"\1***", message)
            record.args = None
        return True


logging.getLogger("httpx").addFilter(_RedactApiKey())

_client: httpx.AsyncClient | None = None
_client_lock = asyncio.Lock()


def _normalize_params(params: Mapping[str, Any]) -> dict[str, Any]:
    """Coerce user-facing parameter values into the form NewsData expects.

    Centralised here so every tool stays simple and so the LLM can pass
    the most natural form (true/false for flags, list for multi-value
    filters, int for hour counts) without any tool having to translate.

    `None`, blank strings and empty lists are all dropped: models differ
    in how they leave an optional parameter out, and the API answers an
    empty value with HTTP 422.
    """
    clean: dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue

        # bool must be checked before int (bool is an int subclass).
        if isinstance(value, bool):
            if key in _BOOL_TRUTHY_ONLY_KEYS:
                if value:
                    clean[key] = 1
                # else: omit — caller meant "I don't want this filter".
                continue
            clean[key] = 1 if value else 0
            continue

        if isinstance(value, str):
            if value.strip():
                clean[key] = value
            # else: omit — a blank string is "not passed".
            continue

        if isinstance(value, list):
            items = [str(item) for item in value if item]
            if not items:
                continue
            clean[key] = ",".join(items)
            continue

        clean[key] = value
    return clean


def _parse_retry_after(value: str | None) -> int | None:
    """Parse a ``Retry-After`` header into an integer seconds value.

    RFC 7231 allows two forms:
    - an integer number of seconds, or
    - an HTTP-date.

    Returns ``None`` for unparseable input so the retry loop falls back
    to exponential backoff.
    """
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None

    # Form 1: integer seconds.
    try:
        seconds = int(value)
    except ValueError:
        pass
    else:
        return max(seconds, 0)

    # Form 2: HTTP-date.
    try:
        target = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if target is None:
        return None
    if target.tzinfo is None:
        target = target.replace(tzinfo=UTC)
    delta = (target - datetime.now(tz=UTC)).total_seconds()
    return max(int(delta), 0)


def _compute_backoff(attempt: int) -> float:
    """Exponential backoff: `RETRY_BACKOFF * 2^(attempt-1)`, capped."""
    delay = RETRY_BACKOFF * (2 ** (attempt - 1))
    return min(delay, RETRY_BACKOFF_MAX)


def _api_error_details(body: Any) -> dict[str, Any]:
    """Pull the useful parts out of a parsed NewsData error body.

    Returns a dict with any of ``message``, ``error_code`` and
    ``recommendations`` that the body carries in the expected shape, and
    an empty dict when the body is not a NewsData error object at all.
    """
    results = body.get("results") if isinstance(body, dict) else None
    if not isinstance(results, dict):
        return {}

    details: dict[str, Any] = {}
    message = results.get("message")
    if isinstance(message, str) and message.strip():
        details["message"] = message.strip()
    error_code = results.get("code")
    if isinstance(error_code, str) and error_code.strip():
        details["error_code"] = error_code.strip()
    recommendations = results.get("recommendations")
    if isinstance(recommendations, dict) and recommendations:
        details["recommendations"] = recommendations
    # A duplicate real-time registration (HTTP 409) names the id that
    # already exists; the model needs it to carry on.
    registration_id = results.get("registration_id")
    if isinstance(registration_id, str) and registration_id.strip():
        details["registration_id"] = registration_id.strip()
    return details


def _fallback_http_message(code: int, text: str) -> str:
    """Message for an HTTP error whose body is not a NewsData error object."""
    if code == 401:
        return "Unauthorized. API key is invalid."
    if code == 422:
        return "Invalid parameters provided. Please check your request."
    if code == 429:
        return "Rate limit exceeded. Try again later."

    body = (text or "").strip()
    if len(body) > 500:
        body = body[:500] + "…"
    return f"HTTP {code} from Newsdata.io: {body}"


async def _get_client() -> httpx.AsyncClient:
    """Lazy singleton so we reuse one connection pool across tool calls.

    Callers must guard against ``NEWSDATA_API_KEY is None`` (``fetch``
    does this at the top); we assert it here so the type-checker is
    satisfied with the non-Optional header dict.

    ``Accept-Language: en`` is sent because the API translates error
    messages, error codes and plan notices for other languages; the retry
    policy compares error codes and the formatters recognise the notices
    by their English text.
    """
    global _client
    if _client is None:
        async with _client_lock:
            if _client is None:
                assert NEWSDATA_API_KEY is not None, (
                    "_get_client called without NEWSDATA_API_KEY set"
                )
                _client = httpx.AsyncClient(
                    timeout=REQUEST_TIMEOUT,
                    headers={
                        "User-Agent": f"newsdata-mcp/{__version__}",
                        "X-ACCESS-KEY": NEWSDATA_API_KEY,
                        "Accept-Language": "en",
                    },
                )
    return _client


async def close_client() -> None:
    """Close the singleton ``httpx.AsyncClient`` if one was created.

    Called from the FastMCP lifespan teardown so we release the
    connection pool cleanly on SIGTERM instead of relying on process
    exit. Safe to call when no client was ever created.
    """
    global _client
    if _client is None:
        return
    async with _client_lock:
        if _client is None:
            return
        try:
            await _client.aclose()
        finally:
            _client = None


async def _request_once(
    endpoint: str, clean: dict[str, Any], method: str = "GET", base_url: str | None = None
) -> tuple[dict[str, Any], bool]:
    """Execute one HTTP attempt.

    Returns a ``(envelope, retryable)`` tuple. ``envelope`` is the
    `{"status": ...}` dict that ``fetch()`` either returns immediately
    (when ``retryable=False``) or sleeps-then-retries (when
    ``retryable=True`` and we have attempts left).
    """
    response: httpx.Response | None = None
    try:
        client = await _get_client()
        response = await client.request(
            method,
            f"{base_url or NEWSDATA_BASE_URL}/{endpoint}",
            params=clean,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()

        if data.get("status") == "success":
            return {"status": "success", "data": data}, False

        details = _api_error_details(data)
        soft_envelope: dict[str, Any] = {"status": "error", "status_code": 200, **details}
        soft_envelope["message"] = (
            details.get("message")
            or data.get("message")
            or "Unknown API error."
        )
        return soft_envelope, False

    except httpx.TimeoutException:
        return (
            {
                "status": "error",
                "message": (
                    f"Request timed out after {REQUEST_TIMEOUT} seconds. "
                    "The Newsdata.io API may be experiencing delays."
                ),
                "status_code": None,
            },
            True,
        )
    except httpx.ConnectError:
        return (
            {
                "status": "error",
                "message": (
                    "Failed to connect to Newsdata.io API. "
                    "Please check your internet connection."
                ),
                "status_code": None,
            },
            True,
        )
    except (httpx.NetworkError, httpx.RemoteProtocolError):
        # The connection broke while the request or the response was in
        # transit: a reset, or a server that closed a kept-alive connection just
        # as the request went out ("Server disconnected without sending a
        # response"). That is as transient as a timeout. `ConnectError` is a
        # `NetworkError` too and is caught above. Setup errors
        # (`LocalProtocolError`, `ProxyError`, `UnsupportedProtocol`) are left
        # to the generic handler below: a retry cannot fix them.
        return (
            {
                "status": "error",
                "message": (
                    "The connection to Newsdata.io API was interrupted "
                    "before the response arrived."
                ),
                "status_code": None,
            },
            True,
        )
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        try:
            error_body: Any = e.response.json()
        except ValueError:
            # Not JSON (a proxy's HTML page, plain text, empty body): there is
            # no API message to pass on, so the fallback message is used.
            error_body = None

        envelope: dict[str, Any] = {
            "status": "error",
            "status_code": code,
            **_api_error_details(error_body),
        }
        if "message" not in envelope:
            envelope["message"] = _fallback_http_message(code, e.response.text)

        if code == 429:
            retry_after = _parse_retry_after(e.response.headers.get("Retry-After"))
            if retry_after is not None:
                envelope["retry_after"] = retry_after
            return envelope, envelope.get("error_code") not in QUOTA_EXHAUSTED_CODES

        # 5xx are transient; other 4xx are permanent (user-side mistakes).
        return envelope, code >= 500
    except json.JSONDecodeError:
        body = (response.text or "").strip()[:200] if response is not None else ""
        return (
            {
                "status": "error",
                "message": (
                    f"Newsdata.io returned a non-JSON response. "
                    f"First 200 chars: {body}"
                ),
                "status_code": None,
            },
            False,
        )
    except Exception:
        logger.exception("Unexpected error calling Newsdata.io")
        return (
            {
                "status": "error",
                "message": (
                    "Unexpected error calling Newsdata.io. "
                    "See server logs for details."
                ),
                "status_code": None,
            },
            False,
        )


async def fetch(
    endpoint: str, params: dict[str, Any], method: str = "GET", base_url: str | None = None
) -> dict[str, Any]:
    """Public entry point: one logical request, with retries.

    ``endpoint`` is the path under ``NEWSDATA_BASE_URL``: ``news``,
    ``market``, ``crypto``, ``sources``, ``count/news``, ``count/market``
    or ``count/crypto``. The real-time tools pass their own ``base_url``
    (``NEWSDATA_WS_API_URL``, which can point at another API root) and
    ``method``: their registration endpoints use POST and DELETE.

    Permanent failures (auth, validation, used-up credits, soft errors,
    JSON decode, unexpected exceptions) return immediately. Transient
    failures (network, 5xx, rate-limit 429) retry up to ``MAX_RETRIES``
    times with exponential backoff (waiting ``Retry-After`` plus one second
    for a 429 when parseable). A 429 whose ``Retry-After`` is longer than
    ``RETRY_BACKOFF_MAX`` is returned at once instead of waited out.
    """
    if not NEWSDATA_API_KEY:
        return {
            "status": "error",
            "message": "NEWSDATA_API_KEY is not configured.",
            "status_code": None,
        }

    clean = _normalize_params(params)
    logger.info("Newsdata.io %s /%s (%d params)", method, endpoint, len(clean))

    last_envelope: dict[str, Any] = {
        "status": "error",
        "message": "Retry loop exhausted unexpectedly.",
        "status_code": None,
    }
    for attempt in range(1, MAX_RETRIES + 1):
        envelope, retryable = await _request_once(endpoint, clean, method, base_url)
        if not retryable:
            return envelope
        last_envelope = envelope
        if attempt >= MAX_RETRIES:
            break

        retry_after = envelope.get("retry_after")
        if retry_after is not None and retry_after > RETRY_BACKOFF_MAX:
            # The API asks for a wait longer than this server holds a tool
            # call open (its rate-limit window can be many minutes away).
            # Sleeping would leave the model with no answer at all, so the
            # error goes back now, with the wait in it.
            return envelope
        # Retry-After is in whole seconds, and the API's value can fall short of
        # the moment its rate-limit window resets (it is 0 in the window's last
        # moments). One second more keeps the retry from arriving just before the
        # reset, where it would get another 429 and use up an attempt.
        sleep_for = (
            float(retry_after) + 1
            if retry_after is not None
            else _compute_backoff(attempt)
        )
        logger.warning(
            "Retryable failure on /%s (attempt %d/%d): %s; sleeping %.2fs",
            endpoint,
            attempt,
            MAX_RETRIES,
            envelope.get("message", ""),
            sleep_for,
        )
        await asyncio.sleep(sleep_for)

    return last_envelope
