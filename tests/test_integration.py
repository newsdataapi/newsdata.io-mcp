"""Integration tests — hit the live NewsData.io API.

These tests are SKIPPED by default. Run them explicitly with::

    NEWSDATA_INTEGRATION_KEY=<key> uv run pytest -m integration

Or run unit + integration together with ``-m ""``.

Each test:
- Reads ``NEWSDATA_INTEGRATION_KEY`` from the environment (skips if unset).
- Patches the singleton http client and the module-level API key so the
  call goes out with the real credential (the unit conftest sets a fake
  key, which we override here).
- Asserts a minimal contract: status==success, results is a list, basic
  shape. We deliberately do not assert on counts or content — those vary.
"""
import os

import pytest

from newsdata_mcp import http
from newsdata_mcp.tools.archive import get_archive_news
from newsdata_mcp.tools.count import get_news_counts
from newsdata_mcp.tools.crypto import get_crypto_news
from newsdata_mcp.tools.crypto_count import get_crypto_counts
from newsdata_mcp.tools.latest import get_latest_news
from newsdata_mcp.tools.market import get_market_news
from newsdata_mcp.tools.market_count import get_market_counts
from newsdata_mcp.tools.sources import get_news_sources

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def real_api_key():
    """Inject the real API key for the duration of each test, then
    restore the placeholder so unit tests in the same session stay
    isolated.
    """
    key = os.environ.get("NEWSDATA_INTEGRATION_KEY")
    if not key:
        pytest.skip("NEWSDATA_INTEGRATION_KEY env var not set")

    saved = http.NEWSDATA_API_KEY
    saved_client = http._client
    http.NEWSDATA_API_KEY = key
    http._client = None
    try:
        yield
    finally:
        if http._client is not None:
            await http._client.aclose()
        http._client = saved_client
        http.NEWSDATA_API_KEY = saved


def _assert_renders_endpoint(out: str, endpoint_name: str) -> None:
    """A successful tool call always starts with ``endpoint: <name>`` or
    with a 'no results' / 'no counts' line; both are acceptable for an
    integration test (we're verifying connectivity, not content)."""
    if not (out.startswith(f"endpoint: {endpoint_name}") or "No " in out.splitlines()[0]):
        pytest.fail(f"Unexpected output for {endpoint_name}:\n{out[:300]}")


async def test_live_get_news_sources():
    out = await get_news_sources(country="us", language="en")
    _assert_renders_endpoint(out, "sources")


async def test_live_get_latest_news():
    out = await get_latest_news(q="bitcoin", size=1)
    _assert_renders_endpoint(out, "latest")


async def test_live_get_archive_news():
    out = await get_archive_news(
        from_date="2024-01-01",
        to_date="2024-01-07",
        q="elections",
        size=1,
    )
    _assert_renders_endpoint(out, "archive")


async def test_live_get_crypto_news():
    out = await get_crypto_news(coin="btc", size=1)
    _assert_renders_endpoint(out, "crypto")


async def test_live_get_market_news():
    out = await get_market_news(symbol="AAPL", size=1)
    _assert_renders_endpoint(out, "market")


async def test_live_get_news_counts():
    out = await get_news_counts(from_date="2024-01-01", to_date="2024-01-07", q="bitcoin")
    _assert_renders_endpoint(out, "count")


async def test_live_get_crypto_counts():
    out = await get_crypto_counts(from_date="2024-01-01", to_date="2024-01-07", coin="btc")
    _assert_renders_endpoint(out, "crypto/count")


async def test_live_get_market_counts():
    out = await get_market_counts(from_date="2024-01-01", to_date="2024-01-07", symbol="AAPL")
    _assert_renders_endpoint(out, "market/count")
