"""Tests for the real-time WebSocket tools.

The management tools go through `respx` like every other endpoint. The
streaming tool is exercised against a fake `connect()` so no live socket
(or server) is needed.
"""
import json
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import respx
from websockets.exceptions import ConnectionClosedError, InvalidURI
from websockets.frames import Close
from websockets.uri import parse_uri

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
            "total_results": 1,
            "results": [{"id": article_id, "title": title}],
        }
    )


def error_frame(message: str, code: str) -> str:
    """The frame the service sends right before it closes a connection it
    refuses or has to end."""
    return json.dumps({"status": "error", "results": {"message": message, "code": code}})


def closed_by_server(code: int, reason: str) -> ConnectionClosedError:
    """What iterating a connection raises once the service has closed it with
    anything but a normal close code."""
    return ConnectionClosedError(Close(code, reason), None)


class FakeWebSocket:
    """Async-iterable stand-in for a live websockets connection."""

    def __init__(self, messages: list[Any], hang: bool = False, close: Exception | None = None):
        self._messages = list(messages)
        self._hang = hang
        self._close = close

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._messages:
            return self._messages.pop(0)
        if self._close is not None:
            raise self._close
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
        self.kwargs: dict[str, Any] = {}

    def __call__(self, url: str, **kwargs):
        self.url = url
        self.kwargs = kwargs
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
    # Pinned so that a NEWSDATA_WS_API_URL in the shell or in `.env` cannot send a
    # test to an address that is not mocked.
    monkeypatch.setattr(realtime, "NEWSDATA_WS_API_URL", "https://newsdata.io/api/2")


# ---- register -----------------------------------------------------------


@respx.mock
async def test_register_posts_with_news_type():
    route = respx.post("https://newsdata.io/api/2/websocket/register").mock(
        return_value=httpx.Response(
            200,
            json={"status": "success", "results": {"registration_id": "9b2d1e8a7c4f4b6e9d3a5c7e1f2a4b6c"}},
        )
    )
    out = await register_realtime_query(q="bitcoin", language="en")

    assert route.called
    qs = dict(route.calls[0].request.url.params)
    assert qs["news_type"] == "news"
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
    respx.post("https://newsdata.io/api/2/websocket/register").mock(
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
    respx.get("https://newsdata.io/api/2/websocket/fetch").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "total_results": 2,
                "results": [
                    {"registration_id": "1111111122223333444455556666aaaa", "query": {"q": "bitcoin"}},
                    {"registration_id": "2222222233334444555566667777bbbb", "query": {"q": "ethereum"}},
                ],
            },
        )
    )
    out = await list_realtime_queries()
    assert "registered_queries: 2" in out
    assert "registration_id: 1111111122223333444455556666aaaa" in out
    assert "registration_id: 2222222233334444555566667777bbbb" in out


@respx.mock
async def test_list_handles_no_registrations():
    respx.get("https://newsdata.io/api/2/websocket/fetch").mock(
        return_value=httpx.Response(
            200, json={"status": "success", "total_results": 0, "results": []}
        )
    )
    out = await list_realtime_queries()
    assert "No real-time queries are registered" in out


# ---- delete -------------------------------------------------------------


@respx.mock
async def test_delete_uses_delete_method():
    route = respx.delete("https://newsdata.io/api/2/websocket/delete").mock(
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
    respx.delete("https://newsdata.io/api/2/websocket/delete").mock(
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


async def test_stream_url_keeps_url_characters_in_the_registration_id(monkeypatch):
    """A `#` or `&` in `registration_id` must stay part of the value. Pasted in
    raw, a `#` starts a fragment, which the WebSocket library refuses with an
    error whose text is the whole URL, API key included."""
    fake = FakeConnect(FakeWebSocket([article_frame("a1", "one")]))
    monkeypatch.setattr(realtime.ws_client, "connect", fake)
    registration_id = "a" * 29 + "#&b"  # 32 characters, like a real id

    await stream_news(registration_id=registration_id, max_articles=1, wait_seconds=5)

    parse_uri(fake.url)  # raises InvalidURI for a URL the library refuses
    assert parse_qs(urlsplit(fake.url).query) == {"apikey": ["test-key"], "registration_id": [registration_id]}


async def test_stream_library_errors_do_not_show_the_url_or_the_key(monkeypatch, caplog):
    """Errors of the WebSocket library can carry the request URL in their
    text, and that URL holds the API key: only the error's name is shown."""
    url = "wss://ws.example.test/ws/event?apikey=test-key&registration_id=x#y"
    error = InvalidURI(url, "fragment identifier is meaningless")
    monkeypatch.setattr(realtime.ws_client, "connect", FakeConnect(error=error))

    with caplog.at_level("WARNING", logger="newsdata_mcp.tools.realtime"):
        out = await stream_news(registration_id="1111111122223333444455556666aaaa", max_articles=1, wait_seconds=5)

    assert out == "Error: could not open the real-time connection (InvalidURI)."
    assert not any("test-key" in record.getMessage() for record in caplog.records)


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


# ---- how the real-time tools sit next to the news tools ------------------


@respx.mock
async def test_management_calls_use_the_realtime_api_root_not_the_news_one(monkeypatch):
    """The real-time management calls go to `NEWSDATA_WS_API_URL`, which can
    point somewhere other than the news tools' root (`NEWSDATA_BASE_URL`)."""
    monkeypatch.setattr(realtime, "NEWSDATA_WS_API_URL", "https://rt.example.test/api/2")
    register = respx.post("https://rt.example.test/api/2/websocket/register").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": {"registration_id": "a" * 32}})
    )
    listing = respx.get("https://rt.example.test/api/2/websocket/fetch").mock(
        return_value=httpx.Response(200, json={"status": "success", "total_results": 0, "results": []})
    )
    delete = respx.delete("https://rt.example.test/api/2/websocket/delete").mock(
        return_value=httpx.Response(200, json={"status": "success"})
    )

    await register_realtime_query(q="bitcoin")
    await list_realtime_queries()
    await delete_realtime_query(registration_id="a" * 32)

    assert register.called
    assert listing.called
    assert delete.called


@respx.mock
async def test_register_sends_the_api_parameter_names():
    route = respx.post("https://newsdata.io/api/2/websocket/register").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": {"registration_id": "a" * 32}})
    )
    await register_realtime_query(
        q_in_title="apple",
        exclude_country="cn",
        source_url="bbc.com",
        source_priority="top",
        content=True,
        image=False,
        remove_duplicate=True,
        exclude_field=["content", "ai.summary"],
    )
    assert dict(route.calls[0].request.url.params) == {
        "q_in_title": "apple",
        "exclude_country": "cn",
        "source_url": "bbc.com",
        "source_priority": "top",
        "content": "1",
        "image": "0",
        "remove_duplicate": "1",
        "exclude_field": "content,ai.summary",
        "news_type": "news",
    }


@respx.mock
async def test_register_remove_duplicate_false_is_not_sent():
    route = respx.post("https://newsdata.io/api/2/websocket/register").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": {"registration_id": "a" * 32}})
    )
    await register_realtime_query(q="bitcoin", remove_duplicate=False)
    assert dict(route.calls[0].request.url.params) == {"q": "bitcoin", "news_type": "news"}


@respx.mock
async def test_register_rejects_conflicting_source_filters():
    out = await register_realtime_query(source_url="bbc.com", exclude_source_url="cnn.com")
    assert out.startswith("Error:")
    assert "'source_url'" in out
    assert "'exclude_source_url'" in out
    assert not respx.calls


@respx.mock
async def test_register_conflict_shows_the_existing_registration_id():
    """The API answers a duplicate registration with 409 and the id of the
    registration that already exists; the model needs that id."""
    respx.post("https://newsdata.io/api/2/websocket/register").mock(
        return_value=httpx.Response(
            409,
            json={
                "status": "error",
                "results": {
                    "message": "This query is already registered.",
                    "code": "Conflict",
                    "registration_id": "9b2d1e8a7c4f4b6e9d3a5c7e1f2a4b6c",
                },
            },
        )
    )
    out = await register_realtime_query(q="bitcoin")
    assert out.splitlines() == [
        "Error (HTTP 409, Conflict): This query is already registered.",
        "registration_id: 9b2d1e8a7c4f4b6e9d3a5c7e1f2a4b6c",
    ]


async def test_stream_renders_articles_like_the_news_tools(monkeypatch):
    frame = json.dumps(
        {
            "status": "success",
            "total_results": 1,
            "results": [
                {
                    "id": "a1",
                    "title": "one",
                    "url": "https://example.com/one",
                    "published_at": "2026-11-16T06:15:00Z",
                    "source": {"name": "Example News"},
                }
            ],
        }
    )
    monkeypatch.setattr(realtime.ws_client, "connect", FakeConnect(FakeWebSocket([frame])))

    out = await stream_news(registration_id="1111111122223333444455556666aaaa", max_articles=1, wait_seconds=5)

    assert "url: https://example.com/one" in out
    assert "published_at: 2026-11-16T06:15:00Z" in out
    assert "source.name: Example News" in out
    assert "id: a1" in out


# ---- the key on the list and delete endpoints ----------------------------


@respx.mock
async def test_list_and_delete_send_the_key_as_a_query_parameter():
    """These two calls send the key as `apikey` in the query string."""
    listing = respx.get("https://newsdata.io/api/2/websocket/fetch").mock(
        return_value=httpx.Response(200, json={"status": "success", "total_results": 0, "results": []})
    )
    delete = respx.delete("https://newsdata.io/api/2/websocket/delete").mock(
        return_value=httpx.Response(200, json={"status": "success"})
    )

    await list_realtime_queries()
    await delete_realtime_query(registration_id="a" * 32)

    assert dict(listing.calls[0].request.url.params) == {"apikey": "test-key"}
    assert dict(delete.calls[0].request.url.params) == {"apikey": "test-key", "registration_id": "a" * 32}


@respx.mock
async def test_register_keeps_the_key_out_of_the_query_string():
    """Registration accepts the header, so the key stays out of the URL there."""
    route = respx.post("https://newsdata.io/api/2/websocket/register").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": {"registration_id": "a" * 32}})
    )
    await register_realtime_query(q="bitcoin")
    assert "apikey" not in dict(route.calls[0].request.url.params)


@respx.mock
async def test_the_key_in_a_request_url_is_not_written_to_the_log(caplog):
    """httpx logs every request URL at INFO level. The list and delete calls
    carry the key in the URL, so it has to be masked in that log line."""
    respx.get("https://newsdata.io/api/2/websocket/fetch").mock(
        return_value=httpx.Response(200, json={"status": "success", "total_results": 0, "results": []})
    )
    with caplog.at_level("INFO", logger="httpx"):
        await list_realtime_queries()

    logged = [record.getMessage() for record in caplog.records if record.name == "httpx"]
    assert any("websocket/fetch?apikey=***" in message for message in logged), logged
    assert not any("test-key" in message for message in logged)


@respx.mock
async def test_a_full_registration_list_is_reported_at_once(monkeypatch):
    """`RegistrationLimitExceeded` comes as a 429, but waiting does not free a
    registration, so it must not go through the retry loop."""
    monkeypatch.setattr("newsdata_mcp.http.RETRY_BACKOFF", 30.0)  # a retry would hang the test
    route = respx.post("https://newsdata.io/api/2/websocket/register").mock(
        return_value=httpx.Response(
            429,
            json={
                "status": "error",
                "results": {"message": "You have reached the maximum number of registered queries.", "code": "RegistrationLimitExceeded"},
            },
        )
    )
    out = await register_realtime_query(q="bitcoin")

    assert route.call_count == 1
    assert out == "Error (HTTP 429, RegistrationLimitExceeded): You have reached the maximum number of registered queries."


# ---- a stream the service refuses or ends --------------------------------
#
# The service accepts the connection, sends one error frame
# `{"status": "error", "results": {"message", "code"}}` and closes with the
# code as the close reason (1008, or 1011 when the service itself failed).
# An older server sent no frame, only a close whose reason is a sentence.

REFUSED = "We couldn't verify your apikey and registration_id."
NO_CREDITS = "Your account has used all of its API credits, so no more articles can be delivered."


async def test_stream_refused_shows_the_message_and_code_of_the_error_frame(monkeypatch):
    socket = FakeWebSocket([error_frame(REFUSED, "Unauthorized")], close=closed_by_server(1008, "Unauthorized"))
    monkeypatch.setattr(realtime.ws_client, "connect", FakeConnect(socket))

    out = await stream_news(registration_id="1111111122223333444455556666aaaa", max_articles=10, wait_seconds=5)

    assert out == f"Error (Unauthorized): {REFUSED}"


async def test_stream_error_frame_is_never_counted_as_an_article(monkeypatch):
    """With `max_articles=1` the error frame used to fill the one slot and the
    answer read as one collected (empty) article."""
    socket = FakeWebSocket([error_frame(REFUSED, "Unauthorized")], close=closed_by_server(1008, "Unauthorized"))
    monkeypatch.setattr(realtime.ws_client, "connect", FakeConnect(socket))

    out = await stream_news(registration_id="1111111122223333444455556666aaaa", max_articles=1, wait_seconds=5)

    assert out == f"Error (Unauthorized): {REFUSED}"
    assert "collected_articles" not in out


async def test_stream_keeps_delivered_articles_when_the_service_ends_the_stream(monkeypatch):
    """Articles that arrived before the credits ran out were delivered and
    charged; they must not be thrown away with the error."""
    socket = FakeWebSocket(
        [article_frame("a1", "one"), article_frame("a2", "two"), error_frame(NO_CREDITS, "ApiLimitExceeded")],
        close=closed_by_server(1008, "ApiLimitExceeded"),
    )
    monkeypatch.setattr(realtime.ws_client, "connect", FakeConnect(socket))

    out = await stream_news(registration_id="1111111122223333444455556666aaaa", max_articles=10, wait_seconds=5)

    assert "collected_articles: 2" in out
    assert "stopped_because: error" in out
    assert f"stream_ended_with: Error (ApiLimitExceeded): {NO_CREDITS}" in out
    assert "title: one" in out
    assert "title: two" in out


async def test_stream_refused_by_an_older_server_shows_the_close_reason(monkeypatch):
    """No error frame: the close reason is the only explanation there is."""
    socket = FakeWebSocket([], close=closed_by_server(1008, "device limit reached"))
    monkeypatch.setattr(realtime.ws_client, "connect", FakeConnect(socket))

    out = await stream_news(registration_id="1111111122223333444455556666aaaa", max_articles=10, wait_seconds=5)

    assert out == "Error: device limit reached"


async def test_stream_server_error_is_an_error_not_a_quiet_feed(monkeypatch):
    message = "Something went wrong while processing your request. Please try again later."
    socket = FakeWebSocket([error_frame(message, "ServerError")], close=closed_by_server(1011, "ServerError"))
    monkeypatch.setattr(realtime.ws_client, "connect", FakeConnect(socket))

    out = await stream_news(registration_id="1111111122223333444455556666aaaa", max_articles=10, wait_seconds=5)

    assert out == f"Error (ServerError): {message}"


async def test_stream_server_error_close_without_a_frame(monkeypatch):
    socket = FakeWebSocket([], close=closed_by_server(1011, ""))
    monkeypatch.setattr(realtime.ws_client, "connect", FakeConnect(socket))

    out = await stream_news(registration_id="1111111122223333444455556666aaaa", max_articles=10, wait_seconds=5)

    assert out.startswith("Error: The real-time service closed the connection because of an error on its side.")
    assert "try again later" in out


async def test_stream_slow_client_close_is_transient(monkeypatch):
    """1013 (the client read too slowly) carries no error frame and is not a
    refusal: what was collected is returned as a normal result."""
    socket = FakeWebSocket([article_frame("a1", "one")], close=closed_by_server(1013, "SendTimeout"))
    monkeypatch.setattr(realtime.ws_client, "connect", FakeConnect(socket))

    out = await stream_news(registration_id="1111111122223333444455556666aaaa", max_articles=10, wait_seconds=5)

    assert "collected_articles: 1" in out
    assert "stopped_because: connection_closed" in out
    assert "stream_ended_with" not in out


async def test_stream_accepts_deliveries_of_any_size(monkeypatch):
    """One delivery is a batch of full-text articles and can exceed the
    WebSocket library's 1 MiB default, which would drop the connection."""
    fake = FakeConnect(FakeWebSocket([article_frame("a1", "one")]))
    monkeypatch.setattr(realtime.ws_client, "connect", fake)

    await stream_news(registration_id="1111111122223333444455556666aaaa", max_articles=1, wait_seconds=5)

    assert fake.kwargs["max_size"] is None


async def test_stream_shows_the_ai_summary_and_lists_plan_notices_once(monkeypatch):
    paid = {"id": "a1", "title": "one", "ai": {"summary": "A short summary."}, "content": "Full text."}
    free = {
        "id": "a2",
        "title": "two",
        "content": "ONLY AVAILABLE IN PAID PLANS",
        "ai": {
            "summary": "ONLY AVAILABLE IN PAID PLANS",
            "tag": "ONLY AVAILABLE IN PROFESSIONAL AND CORPORATE PLANS",
        },
    }
    frame = json.dumps({"status": "success", "total_results": 3, "results": [paid, free, free]})
    monkeypatch.setattr(realtime.ws_client, "connect", FakeConnect(FakeWebSocket([frame])))

    out = await stream_news(
        registration_id="1111111122223333444455556666aaaa", max_articles=3, wait_seconds=5, content=True
    )

    assert "ai.summary: A short summary." in out
    assert out.count("ONLY AVAILABLE IN") == 0
    assert out.count("not_in_your_plan: ai.summary, content, ai.tag") == 1


# ---- full text is left out of a stream unless asked for -------------------

LONG_TEXT = "Full text of the article. " * 40


def text_frame() -> str:
    return json.dumps(
        {
            "status": "success",
            "total_results": 2,
            "results": [
                {"id": "a1", "title": "one", "ai": {"summary": "Summary one."}, "content": LONG_TEXT},
                {"id": "a2", "title": "two", "ai": {"summary": "Summary two."}, "content": LONG_TEXT},
            ],
        }
    )


async def test_stream_leaves_the_full_text_out_by_default(monkeypatch):
    """Ten live articles were 35,000 to 50,000 characters with their text
    and 15,000 to 18,000 without; a call can return 50."""
    monkeypatch.setattr(realtime.ws_client, "connect", FakeConnect(FakeWebSocket([text_frame()])))

    out = await stream_news(registration_id="1111111122223333444455556666aaaa", max_articles=2, wait_seconds=5)

    assert "content:" not in out
    assert "Full text of the article." not in out
    assert "ai.summary: Summary one." in out, "the summary stays"
    assert out.count("full_text: left out of this result.") == 1
    assert "content=true" in out
    assert "get_news with id=<its id>" in out


async def test_stream_includes_the_full_text_when_asked(monkeypatch):
    monkeypatch.setattr(realtime.ws_client, "connect", FakeConnect(FakeWebSocket([text_frame()])))

    out = await stream_news(
        registration_id="1111111122223333444455556666aaaa", max_articles=2, wait_seconds=5, content=True
    )

    assert out.count("content: Full text of the article.") == 2
    assert "full_text:" not in out


async def test_stream_gives_no_full_text_hint_when_there_was_no_text_to_leave_out(monkeypatch):
    """A registration made with `content=false` or `exclude_field=content`
    delivers no text, so there is nothing to offer."""
    monkeypatch.setattr(realtime.ws_client, "connect", FakeConnect(FakeWebSocket([article_frame("a1", "one")])))

    out = await stream_news(registration_id="1111111122223333444455556666aaaa", max_articles=1, wait_seconds=5)

    assert "full_text:" not in out
