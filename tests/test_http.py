"""Tests for the HTTP layer.

Mocks the network with `respx` so no real NewsData calls are made.
"""
from datetime import UTC

import httpx
import respx

from newsdata_mcp import http


@respx.mock
async def test_fetch_success_wraps_payload():
    respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(
            200,
            json={"status": "success", "totalResults": 1, "results": [{"article_id": "x"}]},
        )
    )
    result = await http.fetch("latest", {"q": "test"})
    assert result["status"] == "success"
    assert result["data"]["results"][0]["article_id"] == "x"


@respx.mock
async def test_fetch_drops_none_params():
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await http.fetch("latest", {"q": "btc", "country": None, "size": 5})
    request = route.calls[0].request
    qs = dict(request.url.params)
    assert qs == {"q": "btc", "size": "5"}


@respx.mock
async def test_fetch_401_friendly_message():
    respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(401, text="Unauthorized")
    )
    result = await http.fetch("latest", {})
    assert result["status"] == "error"
    assert result["message"] == "Unauthorized. API key is invalid."


@respx.mock
async def test_fetch_422_friendly_message():
    respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(422, text="Bad")
    )
    result = await http.fetch("latest", {})
    assert "Invalid parameters" in result["message"]


@respx.mock
async def test_fetch_429_friendly_message():
    respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(429, text="Too many")
    )
    result = await http.fetch("latest", {})
    assert "Rate limit" in result["message"]


@respx.mock
async def test_fetch_500_truncates_body():
    long_body = "X" * 10_000
    respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(500, text=long_body)
    )
    result = await http.fetch("latest", {})
    assert "HTTP 500" in result["message"]
    assert "…" in result["message"]
    # Prefix "HTTP 500 from Newsdata.io: " is 27 chars, body 500, ellipsis 1
    assert len(result["message"]) == 528


@respx.mock
async def test_fetch_short_5xx_body_not_truncated():
    respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(502, text="Bad Gateway")
    )
    result = await http.fetch("latest", {})
    assert result["message"] == "HTTP 502 from Newsdata.io: Bad Gateway"


@respx.mock
async def test_fetch_soft_error_results_message():
    respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(
            200,
            json={"status": "error", "results": {"code": "X", "message": "Soft fail"}},
        )
    )
    result = await http.fetch("latest", {})
    assert result["status"] == "error"
    assert result["message"] == "Soft fail"


@respx.mock
async def test_fetch_soft_error_top_level_message():
    respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(
            200,
            json={"status": "error", "message": "Top-level message"},
        )
    )
    result = await http.fetch("latest", {})
    assert result["message"] == "Top-level message"


@respx.mock
async def test_fetch_soft_error_unknown_falls_back():
    respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(200, json={"status": "error"})
    )
    result = await http.fetch("latest", {})
    assert result["message"] == "Unknown API error."


@respx.mock
async def test_fetch_non_json_response():
    respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(200, text="<html>not json</html>")
    )
    result = await http.fetch("latest", {})
    assert result["status"] == "error"
    assert "non-JSON" in result["message"]


@respx.mock
async def test_fetch_timeout():
    respx.get("https://newsdata.io/api/1/latest").mock(
        side_effect=httpx.TimeoutException("timed out")
    )
    result = await http.fetch("latest", {})
    assert "timed out" in result["message"].lower()


@respx.mock
async def test_fetch_connect_error():
    respx.get("https://newsdata.io/api/1/latest").mock(
        side_effect=httpx.ConnectError("nope")
    )
    result = await http.fetch("latest", {})
    assert "Failed to connect" in result["message"]


async def test_fetch_missing_api_key_short_circuits(monkeypatch):
    monkeypatch.setattr(http, "NEWSDATA_API_KEY", None)
    result = await http.fetch("latest", {"q": "anything"})
    assert result["status"] == "error"
    assert "not configured" in result["message"]


@respx.mock
async def test_fetch_uses_header_auth_not_query_string():
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await http.fetch("latest", {"q": "x"})
    request = route.calls[0].request
    # Auth comes via header, NOT as `apikey=...` in the URL.
    assert request.headers["X-ACCESS-KEY"] == "test_key_not_real"
    assert "apikey" not in dict(request.url.params)


@respx.mock
async def test_fetch_sets_user_agent_header():
    route = respx.get("https://newsdata.io/api/1/sources").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await http.fetch("sources", {})
    request = route.calls[0].request
    assert request.headers["User-Agent"].startswith("newsdata-mcp/")


@respx.mock
async def test_fetch_reuses_singleton_client():
    respx.get("https://newsdata.io/api/1/sources").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await http.fetch("sources", {})
    first_id = id(http._client)
    await http.fetch("sources", {})
    second_id = id(http._client)
    assert first_id == second_id


# ---------------------------------------------------------------------------
# Step 2 — parameter coercion in _normalize_params.
# These tests confirm the LLM-friendly input forms (bool, list, int) are
# accepted and translated to the wire format NewsData expects.
# ---------------------------------------------------------------------------


def test_normalize_drops_none():
    assert http._normalize_params({"q": "x", "country": None}) == {"q": "x"}


def test_normalize_bool_flag_true_to_one():
    assert http._normalize_params({"image": True}) == {"image": 1}


def test_normalize_bool_flag_false_to_zero():
    assert http._normalize_params({"image": False, "video": False}) == {
        "image": 0,
        "video": 0,
    }


def test_normalize_removeduplicate_true_to_one():
    assert http._normalize_params({"removeduplicate": True}) == {"removeduplicate": 1}


def test_normalize_removeduplicate_false_is_omitted():
    """The API rejects `0`; we drop the key entirely so it's never sent."""
    assert http._normalize_params({"removeduplicate": False}) == {}


def test_normalize_removeduplicate_false_alongside_other_params():
    out = http._normalize_params({"q": "btc", "removeduplicate": False, "size": 5})
    assert out == {"q": "btc", "size": 5}
    assert "removeduplicate" not in out


def test_normalize_list_joins_with_comma_no_spaces():
    assert http._normalize_params({"country": ["us", "gb", "in"]}) == {
        "country": "us,gb,in"
    }


def test_normalize_list_with_single_item():
    assert http._normalize_params({"category": ["technology"]}) == {
        "category": "technology"
    }


def test_normalize_empty_list_is_omitted():
    """An empty list means 'no filter' — drop the key."""
    assert http._normalize_params({"country": []}) == {}


def test_normalize_list_drops_falsy_items():
    """Defensive: empty strings and Nones inside a list are dropped."""
    assert http._normalize_params({"tag": ["food", "", None, "tourism"]}) == {
        "tag": "food,tourism"
    }


def test_normalize_string_csv_passthrough():
    """Legacy form: comma-separated string still works unchanged."""
    assert http._normalize_params({"country": "us,gb"}) == {"country": "us,gb"}


def test_normalize_int_passthrough():
    """ints (size, timeframe-as-int) pass through unchanged."""
    assert http._normalize_params({"size": 10, "timeframe": 24}) == {
        "size": 10,
        "timeframe": 24,
    }


def test_normalize_mixed_inputs_realistic_call():
    """End-to-end shape an LLM would actually produce."""
    out = http._normalize_params({
        "q": "bitcoin",
        "country": ["us", "gb"],
        "language": ["en"],
        "image": True,
        "video": False,
        "removeduplicate": True,
        "size": 10,
        "timeframe": 6,
        "exclude_country": None,
    })
    assert out == {
        "q": "bitcoin",
        "country": "us,gb",
        "language": "en",
        "image": 1,
        "video": 0,
        "removeduplicate": 1,
        "size": 10,
        "timeframe": 6,
    }


@respx.mock
async def test_fetch_sends_bool_true_as_one_on_wire():
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await http.fetch("latest", {"image": True})
    qs = dict(route.calls[0].request.url.params)
    assert qs["image"] == "1"


@respx.mock
async def test_fetch_sends_bool_false_as_zero_on_wire():
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await http.fetch("latest", {"image": False})
    qs = dict(route.calls[0].request.url.params)
    assert qs["image"] == "0"


@respx.mock
async def test_fetch_removeduplicate_false_not_on_wire():
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await http.fetch("latest", {"removeduplicate": False})
    qs = dict(route.calls[0].request.url.params)
    assert "removeduplicate" not in qs


@respx.mock
async def test_fetch_list_joined_with_comma_on_wire():
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await http.fetch("latest", {"country": ["us", "gb", "in"]})
    qs = dict(route.calls[0].request.url.params)
    assert qs["country"] == "us,gb,in"


# ---------------------------------------------------------------------------
# Step 5 — _parse_retry_after, _compute_backoff, retry loop, error envelope.
# ---------------------------------------------------------------------------


# _parse_retry_after — integer-seconds form

def test_parse_retry_after_integer():
    assert http._parse_retry_after("30") == 30


def test_parse_retry_after_zero():
    assert http._parse_retry_after("0") == 0


def test_parse_retry_after_negative_clamped_to_zero():
    assert http._parse_retry_after("-5") == 0


def test_parse_retry_after_with_whitespace():
    assert http._parse_retry_after("  42  ") == 42


# _parse_retry_after — HTTP-date form (RFC 7231)

def test_parse_retry_after_http_date_in_future():
    """An HTTP-date 30 seconds in the future parses to ~30s."""
    from datetime import datetime, timedelta
    from email.utils import format_datetime
    future = datetime.now(tz=UTC) + timedelta(seconds=30)
    seconds = http._parse_retry_after(format_datetime(future, usegmt=True))
    # Some jitter expected; should be in [28, 31] range.
    assert seconds is not None
    assert 28 <= seconds <= 31


def test_parse_retry_after_http_date_in_past_clamped_to_zero():
    from datetime import datetime, timedelta
    from email.utils import format_datetime
    past = datetime.now(tz=UTC) - timedelta(seconds=30)
    assert http._parse_retry_after(format_datetime(past, usegmt=True)) == 0


# _parse_retry_after — invalid inputs

def test_parse_retry_after_none_returns_none():
    assert http._parse_retry_after(None) is None


def test_parse_retry_after_empty_string_returns_none():
    assert http._parse_retry_after("") is None
    assert http._parse_retry_after("   ") is None


def test_parse_retry_after_garbage_returns_none():
    assert http._parse_retry_after("not a thing") is None


# _compute_backoff

def test_compute_backoff_doubles_each_attempt(monkeypatch):
    """Base 2.0s: 2 → 4 → 8 → 16 ... up to the cap."""
    monkeypatch.setattr(http, "RETRY_BACKOFF", 2.0)
    monkeypatch.setattr(http, "RETRY_BACKOFF_MAX", 60.0)
    assert http._compute_backoff(1) == 2.0
    assert http._compute_backoff(2) == 4.0
    assert http._compute_backoff(3) == 8.0
    assert http._compute_backoff(4) == 16.0
    assert http._compute_backoff(5) == 32.0


def test_compute_backoff_capped(monkeypatch):
    """Cap kicks in once the doubled value exceeds RETRY_BACKOFF_MAX."""
    monkeypatch.setattr(http, "RETRY_BACKOFF", 2.0)
    monkeypatch.setattr(http, "RETRY_BACKOFF_MAX", 60.0)
    assert http._compute_backoff(6) == 60.0  # 2 * 32 = 64, capped to 60.
    assert http._compute_backoff(10) == 60.0  # any later attempt = cap.


# Retry loop — happy paths

@respx.mock
async def test_retry_recovers_after_500_then_200():
    """First call returns 500; second returns 200. fetch() returns success."""
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        side_effect=[
            httpx.Response(503, text="upstream is down"),
            httpx.Response(200, json={"status": "success", "results": []}),
        ]
    )
    result = await http.fetch("latest", {})
    assert result["status"] == "success"
    assert route.call_count == 2


@respx.mock
async def test_retry_recovers_after_timeout_then_200():
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        side_effect=[
            httpx.TimeoutException("first call hung"),
            httpx.Response(200, json={"status": "success", "results": []}),
        ]
    )
    result = await http.fetch("latest", {})
    assert result["status"] == "success"
    assert route.call_count == 2


@respx.mock
async def test_retry_recovers_after_connect_error_then_200():
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        side_effect=[
            httpx.ConnectError("dns failure"),
            httpx.Response(200, json={"status": "success", "results": []}),
        ]
    )
    result = await http.fetch("latest", {})
    assert result["status"] == "success"
    assert route.call_count == 2


# Retry loop — exhaustion

@respx.mock
async def test_retry_exhausted_on_5xx_returns_last_error(monkeypatch):
    """All MAX_RETRIES attempts get 5xx; final result includes status_code."""
    monkeypatch.setattr(http, "MAX_RETRIES", 3)
    respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(503, text="still down")
    )
    result = await http.fetch("latest", {})
    assert result["status"] == "error"
    assert result["status_code"] == 503
    assert "HTTP 503" in result["message"]


# Retry loop — never retry on permanent failures

@respx.mock
async def test_401_no_retry():
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(401, text="bad key")
    )
    result = await http.fetch("latest", {})
    assert result["status"] == "error"
    assert result["status_code"] == 401
    # Permanent failure: exactly one call, not MAX_RETRIES.
    assert route.call_count == 1


@respx.mock
async def test_422_no_retry():
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(422, text="bad params")
    )
    result = await http.fetch("latest", {})
    assert result["status"] == "error"
    assert result["status_code"] == 422
    assert route.call_count == 1


@respx.mock
async def test_other_4xx_no_retry():
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(404, text="not found")
    )
    result = await http.fetch("latest", {})
    assert result["status"] == "error"
    assert result["status_code"] == 404
    assert route.call_count == 1


@respx.mock
async def test_non_json_2xx_no_retry():
    """Non-JSON 200 is treated as permanent (some maintenance pages)."""
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(200, text="<html>maintenance</html>")
    )
    result = await http.fetch("latest", {})
    assert result["status"] == "error"
    assert "non-JSON" in result["message"]
    assert route.call_count == 1


@respx.mock
async def test_soft_error_200_no_retry():
    """200 OK with status=error is a user-side issue (e.g. bad date).
    No retry; status_code captured as 200."""
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(
            200,
            json={"status": "error", "results": {"message": "Bad date"}},
        )
    )
    result = await http.fetch("latest", {})
    assert result["status"] == "error"
    assert result["status_code"] == 200
    assert result["message"] == "Bad date"
    assert route.call_count == 1


# Retry loop — 429 honoring Retry-After

@respx.mock
async def test_429_with_retry_after_integer_honored():
    """429 first, then 200. Retry-After=0 lets the test fly past the sleep."""
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}, text="too many"),
            httpx.Response(200, json={"status": "success", "results": []}),
        ]
    )
    result = await http.fetch("latest", {})
    assert result["status"] == "success"
    assert route.call_count == 2


@respx.mock
async def test_429_exhausted_includes_retry_after_in_envelope(monkeypatch):
    """Retry-After from the server is preserved in the final envelope.
    We patch asyncio.sleep to no-op so the test doesn't actually wait the
    30s the header asks for — production-side behaviour (honoring the
    server's request) is covered by `test_429_with_retry_after_integer_honored`."""
    import asyncio as _asyncio

    async def _no_sleep(seconds):
        return None

    monkeypatch.setattr(_asyncio, "sleep", _no_sleep)
    monkeypatch.setattr(http, "MAX_RETRIES", 2)
    respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(429, headers={"Retry-After": "30"}, text="too many")
    )
    result = await http.fetch("latest", {})
    assert result["status"] == "error"
    assert result["status_code"] == 429
    assert result["retry_after"] == 30


# Error envelope shape — every error path includes status_code

@respx.mock
async def test_error_envelope_carries_status_code(monkeypatch):
    """Every error path returns a `status_code` field (None for non-HTTP).
    The LLM (and formatters) rely on this to render HTTP context."""
    monkeypatch.setattr(http, "MAX_RETRIES", 1)
    cases = [
        (httpx.Response(401, text="x"), 401),
        (httpx.Response(422, text="x"), 422),
        (httpx.Response(429, text="x"), 429),
        (httpx.Response(403, text="x"), 403),
        (httpx.Response(503, text="x"), 503),
    ]
    for response, expected_code in cases:
        respx.get("https://newsdata.io/api/1/latest").mock(return_value=response)
        result = await http.fetch("latest", {})
        assert result["status_code"] == expected_code, (
            f"expected status_code {expected_code}, got {result.get('status_code')}"
        )
        respx.reset()


async def test_missing_api_key_envelope_shape(monkeypatch):
    monkeypatch.setattr(http, "NEWSDATA_API_KEY", None)
    result = await http.fetch("latest", {})
    assert result["status"] == "error"
    assert result["status_code"] is None
    assert "not configured" in result["message"]
