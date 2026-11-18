"""Integration tests — hit a live NewsData.io API.

These tests are SKIPPED by default. Run them explicitly with::

    NEWSDATA_INTEGRATION_KEY=<key> uv run pytest -m integration

Or run unit + integration together with ``-m ""``.

They call the API root configured in ``NEWSDATA_BASE_URL`` (shell or
``.env``; default ``https://newsdata.io/api/2``), so they can be pointed
at a staging or local API.

Credits: the four article/source tests cost 1 credit each. The three
count tests cost 50 credits each and need a plan with count access; on
other plans the API answers 403 and those tests fail.

Each test:
- Reads ``NEWSDATA_INTEGRATION_KEY`` from the environment (skips if unset).
- Patches the singleton http client, the module-level API key and the API
  root so the call goes out with the real credential to the configured
  API (the unit conftest sets a fake key and pins the root, which we
  override here).
- Asserts a minimal contract: the tool rendered a success header or a
  "no results" line. We deliberately do not assert on counts or content —
  those vary.
"""
import os

import pytest

from newsdata_mcp import http, settings
from newsdata_mcp.tools.count import get_news_counts
from newsdata_mcp.tools.crypto import get_crypto_news
from newsdata_mcp.tools.crypto_count import get_crypto_counts
from newsdata_mcp.tools.market import get_market_news
from newsdata_mcp.tools.market_count import get_market_counts
from newsdata_mcp.tools.news import get_news
from newsdata_mcp.tools.sources import get_news_sources

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def real_api(reset_http_client):
    """Inject the real API key and the configured API root for the
    duration of each test, then restore the unit-test values so unit
    tests in the same session stay isolated.

    Depends on ``reset_http_client`` so that it runs after the conftest
    fixture has pinned the fake key and the mocked root.
    """
    key = os.environ.get("NEWSDATA_INTEGRATION_KEY")
    if not key:
        pytest.skip("NEWSDATA_INTEGRATION_KEY env var not set")

    saved_key = http.NEWSDATA_API_KEY
    saved_root = http.NEWSDATA_BASE_URL
    saved_client = http._client
    http.NEWSDATA_API_KEY = key
    http.NEWSDATA_BASE_URL = settings.NEWSDATA_BASE_URL
    http._client = None
    try:
        yield
    finally:
        if http._client is not None:
            await http._client.aclose()
        http._client = saved_client
        http.NEWSDATA_API_KEY = saved_key
        http.NEWSDATA_BASE_URL = saved_root


def _assert_renders_endpoint(out: str, endpoint_name: str) -> None:
    """A successful tool call always starts with ``endpoint: <name>`` or
    with a 'no results' line; both are acceptable for an integration
    test (we're verifying connectivity, not content)."""
    if not (out.startswith(f"endpoint: {endpoint_name}") or out.startswith("No ")):
        pytest.fail(f"Unexpected output for {endpoint_name}:\n{out[:300]}")


async def test_live_get_news_sources():
    out = await get_news_sources(country="us", language="en")
    _assert_renders_endpoint(out, "sources")


async def test_live_get_news():
    out = await get_news(q="bitcoin", size=1)
    _assert_renders_endpoint(out, "news")


async def test_live_get_crypto_news():
    out = await get_crypto_news(coin="btc", size=1)
    _assert_renders_endpoint(out, "crypto")


async def test_live_get_market_news():
    out = await get_market_news(q="earnings", size=1)
    _assert_renders_endpoint(out, "market")


async def test_live_get_news_counts():
    out = await get_news_counts(q="bitcoin", size=2)
    _assert_renders_endpoint(out, "count/news")


async def test_live_get_crypto_counts():
    out = await get_crypto_counts(coin="btc", size=2)
    _assert_renders_endpoint(out, "count/crypto")


async def test_live_get_market_counts():
    out = await get_market_counts(q="earnings", size=2)
    _assert_renders_endpoint(out, "count/market")
