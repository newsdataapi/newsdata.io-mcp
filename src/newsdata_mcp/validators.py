"""Client-side parameter validation for NewsData MCP tools.

The NewsData API refuses some parameter combinations (HTTP 422
`TooManyQueryFilter`, HTTP 400 `InvalidRequest`). We mirror the two most
common rules at the tool boundary so the model gets a specific message
before any request is sent.

Every other rule (dates with `timeframe`, `id`/`url` with other filters,
`sort="relevancy"` without a query, the minimum filter on `/count/news`)
is left to the API: its own error message names the fix, and
`formatters._format_error` passes it through unchanged.

`MUTEX_GROUPS` holds the same groups the API enforces
(`FILTERS_MAPPING['v2_filter_conflict']` in its `env_file.py`).
"""
from collections.abc import Mapping
from typing import Any

# Parameters that cannot be used together. Tool parameter names are the
# API's own names, so these are both the Python kwarg names and the wire
# names.
MUTEX_GROUPS: tuple[tuple[str, ...], ...] = (
    ("q", "q_in_title", "q_in_meta"),
    ("country", "exclude_country"),
    ("category", "exclude_category"),
    ("language", "exclude_language"),
    ("source_url", "exclude_source_url"),
)


def is_set(value: Any) -> bool:
    """True when a tool argument carries a value.

    `None`, a blank string and an empty list all mean "not passed":
    `http._normalize_params` drops all three, so they must not count
    here either.
    """
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return bool(value)
    return True


def check_mutex_groups(
    kwargs: Mapping[str, Any], groups: tuple[tuple[str, ...], ...] = MUTEX_GROUPS
) -> str | None:
    """Return an LLM-readable error message if any mutex group has more
    than one member set, else None.

    `kwargs` is the mapping of the tool's arguments by name. Missing keys
    are treated as not set; unknown keys are ignored. `groups` defaults to
    `MUTEX_GROUPS`.

    The returned string names the conflicting parameters in single-quoted
    form, lists the full group so the model knows its options, and ends
    with the explicit fix ("Omit the others.").
    """
    for group in groups:
        set_in_group = [name for name in group if is_set(kwargs.get(name))]
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

    ``sentiment_score`` is a confidence threshold for one ``sentiment``
    label (positive / neutral / negative). The API answers
    ``sentiment_score`` alone with HTTP 400; this check gives the same
    answer without a request.
    """
    if is_set(kwargs.get("sentiment_score")) and not is_set(kwargs.get("sentiment")):
        return (
            "Parameter 'sentiment_score' requires 'sentiment' to also be set. "
            "Pass `sentiment='positive'`, `'negative'`, or `'neutral'` alongside "
            "`sentiment_score`, or omit `sentiment_score`."
        )
    return None
