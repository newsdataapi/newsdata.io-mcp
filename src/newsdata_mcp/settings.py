"""Runtime configuration read from environment variables.

Loaded once at import time. Restart the server after changing env vars.
"""
import os
import warnings

from dotenv import load_dotenv

load_dotenv()

NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY")
NEWSDATA_BASE_URL = os.getenv("NEWSDATA_BASE_URL", "https://newsdata.io/api/1")

try:
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
except (ValueError, TypeError):
    warnings.warn(
        "REQUEST_TIMEOUT must be an integer; falling back to 30",
        stacklevel=2,
    )
    REQUEST_TIMEOUT = 30

# Retry policy (network errors, 5xx, 429). Defaults sleep about a minute
# total across all attempts (2s → 4s → 8s → 16s → 32s, capped at 60s).
try:
    MAX_RETRIES = int(os.getenv("NEWSDATA_MAX_RETRIES", "5"))
except (ValueError, TypeError):
    warnings.warn(
        "NEWSDATA_MAX_RETRIES must be an integer; falling back to 5",
        stacklevel=2,
    )
    MAX_RETRIES = 5

try:
    RETRY_BACKOFF = float(os.getenv("NEWSDATA_RETRY_BACKOFF", "2.0"))
except (ValueError, TypeError):
    warnings.warn(
        "NEWSDATA_RETRY_BACKOFF must be a number; falling back to 2.0",
        stacklevel=2,
    )
    RETRY_BACKOFF = 2.0

try:
    RETRY_BACKOFF_MAX = float(os.getenv("NEWSDATA_RETRY_BACKOFF_MAX", "60.0"))
except (ValueError, TypeError):
    warnings.warn(
        "NEWSDATA_RETRY_BACKOFF_MAX must be a number; falling back to 60.0",
        stacklevel=2,
    )
    RETRY_BACKOFF_MAX = 60.0

# Error codes on a 429 meaning the account's API credits are exhausted rather
# than a transient rate limit. These are never retried — waiting out the
# backoff cannot conjure more credits.
#
# `ApiLimitExceeded` is the documented code (see the ErrorCode enum in
# https://newsdata.io/openapi.json); `ApiKeyLimitExceeded` is accepted too
# because the API has been observed to send it and the spec is not exhaustive.
QUOTA_EXHAUSTED_CODES = frozenset({"ApiLimitExceeded", "ApiKeyLimitExceeded"})

# Real-time WebSocket endpoint used by the `stream_news` tool.
NEWSDATA_WS_URL = os.getenv("NEWSDATA_WS_URL", "wss://ws.newsdata.io/ws/event")

# The feed a registered query matches against.
WS_NEWS_TYPE = "latest"

# Close code the server uses for a permanent connection rejection.
WS_POLICY_VIOLATION = 1008

# Hard ceilings for `stream_news`, which must return within a tool call.
try:
    WS_MAX_WAIT_SECONDS = float(os.getenv("NEWSDATA_WS_MAX_WAIT", "120"))
except (ValueError, TypeError):
    warnings.warn(
        "NEWSDATA_WS_MAX_WAIT must be a number; falling back to 120",
        stacklevel=2,
    )
    WS_MAX_WAIT_SECONDS = 120.0

WS_MAX_ARTICLES = 50

if not NEWSDATA_API_KEY:
    warnings.warn("NEWSDATA_API_KEY is not set", stacklevel=2)
