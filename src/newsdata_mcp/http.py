"""HTTP layer for the NewsData.io REST API.

Owns a lazy module-level ``httpx.AsyncClient`` so we reuse one
connection pool across tool calls. Authentication (``X-ACCESS-KEY``)
and ``User-Agent`` live on the client. Errors are returned as a
``{"status": "error", "message": ...}`` envelope rather than raised, to
keep tool functions return-type clean (MCP tools must return ``str``).

Retry policy:

- Network errors (``TimeoutException``, ``ConnectError``) → retry with
  exponential backoff.
- HTTP 5xx → retry with exponential backoff.
- HTTP 429 → retry, honoring ``Retry-After`` (integer seconds or
  HTTP-date per RFC 7231) when parseable; falling back to exponential
  backoff otherwise.
- HTTP 401/403/422/other 4xx, non-JSON 2xx, soft 200 errors → permanent
  failure, never retried.

Error envelope::

    {"status": "error", "message": str, "status_code": int | None,
     "retry_after": int | None}

``status_code`` is ``None`` for non-HTTP failures (timeout, missing
key). ``retry_after`` is present only on 429s that included a
parseable header.
"""
import asyncio
import json
import logging
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
    REQUEST_TIMEOUT,
    RETRY_BACKOFF,
    RETRY_BACKOFF_MAX,
)

logger = logging.getLogger(__name__)

# Wire-name keys whose semantics differ from a plain bool→{1,0} mapping.
# `removeduplicate` accepts only `1` server-side (and silently drops the
# call when omitted) — passing `False` means "I don't want the filter",
# which is communicated to NewsData by omitting the parameter, not by
# sending `0`.
_BOOL_TRUTHY_ONLY_KEYS = frozenset({"removeduplicate"})

_client: httpx.AsyncClient | None = None
_client_lock = asyncio.Lock()


def _normalize_params(params: Mapping[str, Any]) -> dict[str, Any]:
    """Coerce user-facing parameter values into the form NewsData expects.

    Centralised here so every tool stays simple and so the LLM can pass
    the most natural Python form (True/False for flags, list for CSVs,
    int for hour counts) without any tool having to translate.
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


async def _get_client() -> httpx.AsyncClient:
    """Lazy singleton so we reuse one connection pool across tool calls.

    Callers must guard against ``NEWSDATA_API_KEY is None`` (``fetch``
    does this at the top); we assert it here so the type-checker is
    satisfied with the non-Optional header dict.
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
    endpoint: str, clean: dict[str, Any]
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
        response = await client.get(
            f"{NEWSDATA_BASE_URL}/{endpoint}",
            params=clean,
        )
        response.raise_for_status()
        data: dict[str, Any] = response.json()

        if data.get("status") == "success":
            return {"status": "success", "data": data}, False

        results = data.get("results")
        soft_error = results if isinstance(results, dict) else {}
        message = (
            soft_error.get("message")
            or data.get("message")
            or "Unknown API error."
        )
        return (
            {"status": "error", "message": message, "status_code": 200},
            False,
        )

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
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        retry_after = _parse_retry_after(e.response.headers.get("Retry-After"))

        if code == 401:
            return (
                {
                    "status": "error",
                    "message": "Unauthorized. API key is invalid.",
                    "status_code": code,
                },
                False,
            )
        if code == 422:
            return (
                {
                    "status": "error",
                    "message": "Invalid parameters provided. Please check your request.",
                    "status_code": code,
                },
                False,
            )
        if code == 429:
            envelope: dict[str, Any] = {
                "status": "error",
                "message": "Rate limit exceeded. Try again later.",
                "status_code": code,
            }
            if retry_after is not None:
                envelope["retry_after"] = retry_after
            return envelope, True

        body = (e.response.text or "").strip()
        if len(body) > 500:
            body = body[:500] + "…"
        envelope = {
            "status": "error",
            "message": f"HTTP {code} from Newsdata.io: {body}",
            "status_code": code,
        }
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


async def fetch(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    """Public entry point: one logical request, with retries.

    Permanent failures (auth, validation, soft errors, JSON decode,
    unexpected exceptions) return immediately. Transient failures
    (network, 5xx, 429) retry up to ``MAX_RETRIES`` times with
    exponential backoff (honoring ``Retry-After`` for 429 when
    parseable).
    """
    if not NEWSDATA_API_KEY:
        return {
            "status": "error",
            "message": "NEWSDATA_API_KEY is not configured.",
            "status_code": None,
        }

    clean = _normalize_params(params)
    logger.info("Newsdata.io GET /%s (%d params)", endpoint, len(clean))

    last_envelope: dict[str, Any] = {
        "status": "error",
        "message": "Retry loop exhausted unexpectedly.",
        "status_code": None,
    }
    for attempt in range(1, MAX_RETRIES + 1):
        envelope, retryable = await _request_once(endpoint, clean)
        if not retryable:
            return envelope
        last_envelope = envelope
        if attempt >= MAX_RETRIES:
            break

        retry_after = envelope.get("retry_after")
        sleep_for = (
            float(retry_after)
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
