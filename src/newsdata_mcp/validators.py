"""Client-side parameter validation for NewsData MCP tools.

The NewsData REST API enforces several "use only one of" constraints
server-side and returns HTTP 422 when they're violated. We mirror those
checks at the tool boundary so the LLM gets a fast, specific error
message instead of a generic "Invalid parameters" after a wasted
round-trip — and so the message references the *Python kwarg names*
the LLM actually passed, not NewsData's wire names.

`MUTEX_GROUPS` is the single source of truth for these constraints; see
the official `newsdataapi` SDK's `_MUTEX_GROUPS` for the upstream
equivalent.
"""
from collections.abc import Mapping
from typing import Any

# Mutually-exclusive parameter groups, using Python kwarg names (what
# the tool function receives), not NewsData's wire names. Setting more
# than one entry from any group in the same call returns an error from
# `check_mutex_groups` before any HTTP call goes out.
MUTEX_GROUPS: tuple[tuple[str, ...], ...] = (
    ("q", "q_in_title", "q_in_meta"),
    ("country", "exclude_country"),
    ("category", "exclude_category"),
    ("language", "exclude_language"),
    ("domain", "domainurl", "exclude_domain"),
)


def check_mutex_groups(kwargs: Mapping[str, Any]) -> str | None:
    """Return an LLM-readable error message if any mutex group has more
    than one non-None member set, else None.

    `kwargs` should be the Python kwargs the tool received (typically
    ``locals()`` called at the top of the tool function, before any
    local variables are introduced). Missing keys are treated as not
    set; unknown keys are ignored.

    The returned string is designed to be useful to an LLM reading the
    tool's error output: it names the conflicting parameters in
    single-quoted form, lists the full mutex group so the LLM knows
    what its options are, and ends with the explicit fix ("Omit the
    others.").
    """
    for group in MUTEX_GROUPS:
        set_in_group = [name for name in group if kwargs.get(name) is not None]
        if len(set_in_group) > 1:
            conflict = ", ".join(repr(name) for name in set_in_group)
            allowed = ", ".join(repr(name) for name in group)
            return (
                f"Cannot combine mutually exclusive parameters: {conflict}. "
                f"Pass only one of: {allowed}. Omit the others."
            )
    return None


def check_sentiment_score_requires_sentiment(
    kwargs: Mapping[str, Any],
) -> str | None:
    """Return an error if ``sentiment_score`` is set but ``sentiment`` is not.

    NewsData's ``sentiment_score`` is a confidence threshold that only
    makes sense when paired with a ``sentiment`` label (positive /
    negative / neutral) — the API rejects ``sentiment_score`` alone
    with a 422. We mirror the check client-side so the LLM gets the
    specific guidance (set ``sentiment`` too) instead of a generic
    "Invalid parameters" after a wasted round-trip.
    """
    if kwargs.get("sentiment_score") is not None and kwargs.get("sentiment") is None:
        return (
            "Parameter 'sentiment_score' requires 'sentiment' to also be set. "
            "Pass `sentiment='positive'`, `'negative'`, or `'neutral'` alongside "
            "`sentiment_score`, or omit `sentiment_score`."
        )
    return None
