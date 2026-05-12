"""Shared test fixtures.

Tests must not require a real API key; we set a placeholder before any
of the package modules are imported so the missing-key warning doesn't
fire and so `fetch()` doesn't short-circuit. Real network calls are
mocked via `respx`.
"""
import os

os.environ.setdefault("NEWSDATA_API_KEY", "test_key_not_real")
# Tests assert on retry behavior but must run fast: 3 attempts at sub-ms
# sleep instead of the production 5 attempts at 2s-60s.
os.environ.setdefault("NEWSDATA_MAX_RETRIES", "3")
os.environ.setdefault("NEWSDATA_RETRY_BACKOFF", "0.001")
os.environ.setdefault("NEWSDATA_RETRY_BACKOFF_MAX", "0.01")

import pytest  # noqa: E402

from newsdata_mcp import http  # noqa: E402


@pytest.fixture(autouse=True)
async def reset_http_client(monkeypatch):
    """Force a fresh singleton `httpx.AsyncClient` per test so the
    in-process client picks up the patched API key and mocked
    transport."""
    # Make sure http.NEWSDATA_API_KEY reflects whatever the test set
    # (the conftest default is enough for most tests).
    monkeypatch.setattr(http, "NEWSDATA_API_KEY", os.environ["NEWSDATA_API_KEY"])

    # Reset the singleton before the test runs.
    if http._client is not None:
        await http._client.aclose()
    http._client = None

    yield

    # Tear down after the test so the next one gets a clean client.
    if http._client is not None:
        await http._client.aclose()
        http._client = None
