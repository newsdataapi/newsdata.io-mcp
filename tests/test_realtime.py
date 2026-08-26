"""Tests for the real-time WebSocket tools.

The management tools go through `respx` like every other endpoint. The
streaming tool is exercised against a fake `connect()` so no live socket
(or server) is needed.
"""
import json
from typing import Any

import httpx
import pytest
import respx

from newsdata_mcp.tools import realtime
from newsdata_mcp.tools.realtime import (
    delete_realtime_query,
    list_realtime_queries,
    register_realtime_query,
    stream_news,
)


def article_frame(article_id: str, title: str) -> str:
    return json.dumps(
        {
            "status": "success",
            "totalResults": 1,
            "results": [{"article_id": article_id, "title": title}],
        }
    )


class FakeWebSocket:
    """Async-iterable stand-in for a live websockets connection."""

    def __init__(self, messages: list[Any], hang: bool = False):
        self._messages = list(messages)
        self._hang = hang

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._messages:
            return self._messages.pop(0)
        if self._hang:
            # Simulate a quiet feed: never yields, so the tool's own
            # timeout decides when to return.
            import asyncio

            await asyncio.sleep(3600)
        raise StopAsyncIteration


class FakeConnect:
    """Stands in for `websockets.asyncio.client.connect`."""

    def __init__(self, socket=None, error: Exception | None = None):
        self.socket = socket
        self.error = error
        self.url: str | None = None

    def __call__(self, url: str, **kwargs):
        self.url = url
        return self

    async def __aenter__(self):
        if self.error is not None:
            raise self.error
        return self.socket

    async def __aexit__(self, *exc):
        return False


@pytest.fixture(autouse=True)
def api_key(monkeypatch):
    """Every tool needs a key configured."""
    monkeypatch.setattr(realtime, "NEWSDATA_API_KEY", "test-key")
    monkeypatch.setattr(realtime, "NEWSDATA_WS_URL", "wss://ws.example.test/ws/event")


# ---- register -----------------------------------------------------------


@respx.mock
async def test_register_posts_with_news_type():
    route = respx.post("https://newsdata.io/api/1/websocket/register").mock(
        return_value=httpx.Response(
            200,
            json={"status": "success", "results": {"registration_id": "9b2d1e8a7c4f4b6e9d3a5c7e1f2a4b6c"}},
        )
    )
    out = await register_realtime_query(q="bitcoin", language="en")

    assert route.called
    qs = dict(route.calls[0].request.url.params)
    assert qs["news_type"] == "latest"
    assert qs["q"] == "bitcoin"
    assert qs["language"] == "en"
    assert route.calls[0].request.method == "POST"
    assert "registration_id: 9b2d1e8a7c4f4b6e9d3a5c7e1f2a4b6c" in out


@respx.mock
async def test_register_rejects_mutually_exclusive_filters():
    out = await register_realtime_query(q="a", q_in_title="b")
    assert out.startswith("Error:")
    assert not respx.calls  # short-circuits before any request


@respx.mock
async def test_register_requires_sentiment_for_sentiment_score():
    out = await register_realtime_query(sentiment_score=80)
    assert out.startswith("Error:")
    assert "'sentiment'" in out


@respx.mock
async def test_register_surfaces_409_conflict():
    respx.post("https://newsdata.io/api/1/websocket/register").mock(
        return_value=httpx.Response(
            409,
            json={"status": "error", "results": {"message": "already registered"}},
        )
    )
    out = await register_realtime_query(q="bitcoin")
    assert "Error (HTTP 409)" in out
    assert "already registered" in out


# ---- list ---------------------------------------------------------------


@respx.mock
async def test_list_renders_registered_queries():
    respx.get("https://newsdata.io/api/1/websocket/fetch").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "results": {
                    "queries": [
                        {"registration_id": "1111111122223333444455556666aaaa", "q": "bitcoin"},
                        {"registration_id": "2222222233334444555566667777bbbb", "q": "ethereum"},
                    ]
                },
            },
        )
    )
    out = await list_realtime_queries()
    assert "registered_queries: 2" in out
    assert "registration_id: 1111111122223333444455556666aaaa" in out
    assert "registration_id: 2222222233334444555566667777bbbb" in out


@respx.mock
async def test_list_handles_no_registrations():
    respx.get("https://newsdata.io/api/1/websocket/fetch").mock(
        return_value=httpx.Response(
            200, json={"status": "success", "results": {"queries": []}}
        )
    )
    out = await list_realtime_queries()
    assert "No real-time queries are registered" in out


# ---- delete -------------------------------------------------------------


@respx.mock
async def test_delete_uses_delete_method():
    route = respx.delete("https://newsdata.io/api/1/websocket/delete").mock(
        return_value=httpx.Response(
            200, json={"status": "success", "results": {"deleted": True}}
        )
    )
    out = await delete_realtime_query(registration_id="9b2d1e8a7c4f4b6e9d3a5c7e1f2a4b6c")

    assert route.calls[0].request.method == "DELETE"
    assert dict(route.calls[0].request.url.params)["registration_id"] == "9b2d1e8a7c4f4b6e9d3a5c7e1f2a4b6c"
    assert "deleted: yes" in out
    assert "registration_id: 9b2d1e8a7c4f4b6e9d3a5c7e1f2a4b6c" in out


@respx.mock
async def test_delete_accepts_resultless_success():
    respx.delete("https://newsdata.io/api/1/websocket/delete").mock(
        return_value=httpx.Response(200, json={"status": "success"})
    )
    out = await delete_realtime_query(registration_id="9b2d1e8a7c4f4b6e9d3a5c7e1f2a4b6c")
    assert "deleted: yes" in out


# ---- stream -------------------------------------------------------------


async def test_stream_collects_until_max_articles(monkeypatch):
    socket = FakeWebSocket(
        [article_frame("a1", "one"), article_frame("a2", "two"), article_frame("a3", "three")]
    )
    fake = FakeConnect(socket)
    monkeypatch.setattr(realtime.ws_client, "connect", fake)

    out = await stream_news(registration_id="1111111122223333444455556666aaaa", max_articles=2, wait_seconds=5)

    assert "collected_articles: 2" in out
    assert "stopped_because: max_articles" in out
    assert "title: one" in out
    assert "title: two" in out
    assert "three" not in out, "should stop at the cap"


async def test_stream_sends_apikey_and_registration_id(monkeypatch):
    fake = FakeConnect(FakeWebSocket([article_frame("a1", "one")]))
    monkeypatch.setattr(realtime.ws_client, "connect", fake)

    await stream_news(registration_id="42424242333344445555666677778888", max_articles=1, wait_seconds=5)

    assert "apikey=test-key" in fake.url
    assert "registration_id=42424242333344445555666677778888" in fake.url


async def test_stream_skips_malformed_frames(monkeypatch):
    socket = FakeWebSocket(["not json at all", article_frame("a1", "one")])
    monkeypatch.setattr(realtime.ws_client, "connect", FakeConnect(socket))

    out = await stream_news(registration_id="1111111122223333444455556666aaaa", max_articles=1, wait_seconds=5)

    assert "collected_articles: 1" in out
    assert "title: one" in out


async def test_stream_returns_on_timeout_when_feed_is_quiet(monkeypatch):
    # No messages and the socket hangs — only the timeout can end this.
    monkeypatch.setattr(
        realtime.ws_client, "connect", FakeConnect(FakeWebSocket([], hang=True))
    )

    out = await stream_news(registration_id="1111111122223333444455556666aaaa", max_articles=10, wait_seconds=1)

    assert "collected_articles: 0" in out
    assert "stopped_because: timeout" in out
    assert "No matching articles were published" in out


async def test_stream_reports_connection_closed(monkeypatch):
    # The socket ends its iteration without hitting the cap.
    socket = FakeWebSocket([article_frame("a1", "one")])
    monkeypatch.setattr(realtime.ws_client, "connect", FakeConnect(socket))

    out = await stream_news(registration_id="1111111122223333444455556666aaaa", max_articles=10, wait_seconds=5)

    assert "collected_articles: 1" in out
    assert "stopped_because: connection_closed" in out


async def test_stream_reports_rejected_handshake(monkeypatch):
    from websockets.exceptions import InvalidStatus

    class FakeResponse:
        status_code = 401

    monkeypatch.setattr(
        realtime.ws_client,
        "connect",
        FakeConnect(error=InvalidStatus(FakeResponse())),
    )

    out = await stream_news(registration_id="1111111122223333444455556666aaaa", max_articles=1, wait_seconds=5)

    assert out.startswith("Error (HTTP 401)")
    assert "entitlement" in out or "API key" in out


async def test_stream_clamps_out_of_range_arguments(monkeypatch):
    socket = FakeWebSocket([article_frame(f"a{i}", f"t{i}") for i in range(80)])
    monkeypatch.setattr(realtime.ws_client, "connect", FakeConnect(socket))

    # max_articles above the ceiling is clamped to 50.
    out = await stream_news(registration_id="1111111122223333444455556666aaaa", max_articles=999, wait_seconds=5)
    assert "collected_articles: 50" in out


async def test_stream_requires_an_api_key(monkeypatch):
    monkeypatch.setattr(realtime, "NEWSDATA_API_KEY", None)
    out = await stream_news(registration_id="1111111122223333444455556666aaaa")
    assert out.startswith("Error:")
    assert "NEWSDATA_API_KEY" in out
