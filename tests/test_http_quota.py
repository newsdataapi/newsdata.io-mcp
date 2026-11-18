"""A 429 covers a burst limit, a rate limit, and exhausted API credits.

Only the first two are worth retrying — waiting out the backoff cannot
conjure more credits, so an exhausted quota is a permanent failure.
"""
import httpx
import pytest
import respx

from newsdata_mcp.http import fetch
from newsdata_mcp.settings import QUOTA_EXHAUSTED_CODES

NEWS = "https://newsdata.io/api/2/news"


def _body(code: str) -> dict:
    return {"status": "error", "results": {"message": "limit", "code": code}}


def test_quota_codes_are_the_documented_ones():
    # ApiLimitExceeded is in the spec's ErrorCode enum; the key-scoped variant
    # is accepted too because the spec is not exhaustive.
    assert "ApiLimitExceeded" in QUOTA_EXHAUSTED_CODES
    assert "ApiKeyLimitExceeded" in QUOTA_EXHAUSTED_CODES
    # The real-time registration limit is the same kind of answer: only
    # deleting a registration changes it, waiting does not.
    assert "RegistrationLimitExceeded" in QUOTA_EXHAUSTED_CODES
    # Transient codes must stay out of the set or they would stop retrying.
    assert "RateLimitExceeded" not in QUOTA_EXHAUSTED_CODES
    assert "TooManyRequests" not in QUOTA_EXHAUSTED_CODES


@pytest.mark.parametrize("code", sorted(QUOTA_EXHAUSTED_CODES))
@respx.mock
async def test_exhausted_quota_is_not_retried(code, monkeypatch):
    monkeypatch.setattr("newsdata_mcp.http.NEWSDATA_API_KEY", "test-key")
    route = respx.get(NEWS).mock(return_value=httpx.Response(429, json=_body(code)))

    envelope = await fetch("news", {"q": "x"})

    assert envelope["status"] == "error"
    assert envelope["status_code"] == 429
    # The API's own message and code are passed on to the model as they are.
    assert envelope["message"] == "limit"
    assert envelope["error_code"] == code
    assert route.call_count == 1, "exhausted quota must not retry"


@respx.mock
async def test_transient_429_still_retries(monkeypatch):
    monkeypatch.setattr("newsdata_mcp.http.NEWSDATA_API_KEY", "test-key")
    monkeypatch.setattr("newsdata_mcp.http.RETRY_BACKOFF", 0.001)
    monkeypatch.setattr("newsdata_mcp.http.RETRY_BACKOFF_MAX", 0.001)
    route = respx.get(NEWS).mock(
        side_effect=[
            httpx.Response(429, json=_body("RateLimitExceeded")),
            httpx.Response(200, json={"status": "success", "results": []}),
        ]
    )

    envelope = await fetch("news", {"q": "x"})

    assert envelope["status"] == "success"
    assert route.call_count == 2, "a transient rate limit should still retry"


@respx.mock
async def test_429_without_a_code_still_retries(monkeypatch):
    """No error code at all is treated as transient, as before."""
    monkeypatch.setattr("newsdata_mcp.http.NEWSDATA_API_KEY", "test-key")
    monkeypatch.setattr("newsdata_mcp.http.RETRY_BACKOFF", 0.001)
    monkeypatch.setattr("newsdata_mcp.http.RETRY_BACKOFF_MAX", 0.001)
    route = respx.get(NEWS).mock(
        side_effect=[
            httpx.Response(429, json={"status": "error"}),
            httpx.Response(200, json={"status": "success", "results": []}),
        ]
    )

    envelope = await fetch("news", {"q": "x"})

    assert envelope["status"] == "success"
    assert route.call_count == 2
