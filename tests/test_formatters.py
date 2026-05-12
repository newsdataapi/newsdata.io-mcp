"""Unit tests for the pure-text rendering layer.

`formatters` has no network or framework dependencies; these tests are
synthetic-data only.
"""
from newsdata_mcp.formatters import (
    _append_field,
    _clean_text,
    _format_article_item,
    _format_error,
    _format_sentiment_stats,
    format_articles,
    format_counts,
    format_sources,
)

# ---------- _clean_text ----------

def test_clean_text_strips_whitespace():
    assert _clean_text("  hello  ") == "hello"


def test_clean_text_whitespace_only_is_none():
    assert _clean_text("   ") is None


def test_clean_text_none_input_is_none():
    assert _clean_text(None) is None


def test_clean_text_non_string_is_none():
    assert _clean_text(123) is None
    assert _clean_text([1, 2]) is None


# ---------- _format_sentiment_stats ----------

def test_sentiment_stats_renders_dict():
    out = _format_sentiment_stats({"positive": 70, "neutral": 20, "negative": 10})
    assert "positive=70" in out
    assert "neutral=20" in out
    assert "negative=10" in out


def test_sentiment_stats_empty_dict_is_none():
    assert _format_sentiment_stats({}) is None


def test_sentiment_stats_none_is_none():
    assert _format_sentiment_stats(None) is None


def test_sentiment_stats_non_dict_is_none():
    assert _format_sentiment_stats("not a dict") is None


# ---------- _append_field ----------

def test_append_field_skips_none():
    lines = []
    _append_field(lines, "test", None)
    assert lines == []


def test_append_field_renders_bool_lowercase():
    lines = []
    _append_field(lines, "duplicate", True)
    _append_field(lines, "duplicate", False)
    assert lines == ["duplicate: true", "duplicate: false"]


def test_append_field_renders_list_joined():
    lines = []
    _append_field(lines, "categories", ["a", "b", "c"])
    assert lines == ["categories: a, b, c"]


def test_append_field_drops_falsy_list_items():
    lines = []
    _append_field(lines, "x", ["a", None, "", "b"])
    assert lines == ["x: a, b"]


def test_append_field_str_passthrough():
    lines = []
    _append_field(lines, "title", "hello")
    assert lines == ["title: hello"]


# ---------- _format_article_item ----------

def test_format_article_item_omits_missing_fields():
    lines = _format_article_item({"article_id": "x", "title": "hi"})
    assert any(line.startswith("article_id:") for line in lines)
    assert any(line.startswith("title:") for line in lines)
    # No description in the input, so no description line should be emitted.
    assert not any(line.startswith("description:") for line in lines)


# ---------- format_articles ----------

def test_format_articles_error_envelope():
    out = format_articles({"status": "error", "message": "bad"}, "latest")
    assert out == "Error: bad"


def test_format_articles_error_with_status_code():
    out = format_articles(
        {"status": "error", "message": "Unauthorized.", "status_code": 401},
        "latest",
    )
    assert out == "Error (HTTP 401): Unauthorized."


def test_format_articles_error_with_status_code_and_retry_after():
    out = format_articles(
        {
            "status": "error",
            "message": "Rate limit exceeded.",
            "status_code": 429,
            "retry_after": 30,
        },
        "latest",
    )
    assert out == "Error (HTTP 429, retry after 30s): Rate limit exceeded."


def test_format_articles_empty():
    out = format_articles(
        {"status": "success", "data": {"results": []}}, "latest"
    )
    assert out == "No latest articles found matching your query."


def test_format_articles_populated_headers_and_body():
    out = format_articles(
        {
            "status": "success",
            "data": {
                "totalResults": 2,
                "nextPage": "next_token_abc",
                "results": [
                    {
                        "article_id": "abc",
                        "title": "Hello world",
                        "link": "https://example.com/",
                        "pubDate": "2026-05-08",
                    },
                    {"article_id": "def", "title": "Second"},
                ],
            },
        },
        "latest",
    )
    assert "endpoint: latest" in out
    assert "total_results: 2" in out
    assert "returned_results: 2" in out
    assert "next_page: next_token_abc" in out
    assert "title: Hello world" in out
    assert "title: Second" in out
    assert "url: https://example.com/" in out


# ---------- format_sources ----------

def test_format_sources_error_envelope():
    out = format_sources({"status": "error", "message": "auth fail"})
    assert out == "Error: auth fail"


def test_format_sources_error_with_status_code():
    out = format_sources(
        {"status": "error", "message": "Unauthorized.", "status_code": 401}
    )
    assert out == "Error (HTTP 401): Unauthorized."


def test_format_sources_empty():
    out = format_sources({"status": "success", "data": {"results": []}})
    assert out == "No sources found matching your filters."


def test_format_sources_populated():
    """Fixture mirrors a real `/sources` response (envelope-level
    `totalResults`, source objects with id/name/url/icon/priority/
    description/category/language/country/total_article/last_fetch)."""
    out = format_sources(
        {
            "status": "success",
            "data": {
                "totalResults": 100,
                "results": [
                    {
                        "id": "computerhoy_20minutos_es",
                        "name": "Computer Hoy",
                        "url": "https://computerhoy.20minutos.es",
                        "icon": "https://n.bytvi.com/computerhoy_20minutos_es.png",
                        "priority": 124675,
                        "description": "Web especializada en noticias y análisis.",
                        "category": ["top"],
                        "language": ["spanish"],
                        "country": ["spain"],
                        "total_article": 1293,
                        "last_fetch": "2026-05-10 18:07:54",
                    }
                ],
            },
        }
    )
    assert "endpoint: sources" in out
    assert "total_results: 100" in out
    assert "returned_results: 1" in out
    assert "[1] Computer Hoy" in out
    assert "source_id: computerhoy_20minutos_es" in out
    assert "url: https://computerhoy.20minutos.es" in out
    assert "icon: https://n.bytvi.com/computerhoy_20minutos_es.png" in out
    assert "priority: 124675" in out
    assert "languages: spanish" in out
    assert "countries: spain" in out
    assert "categories: top" in out
    assert "total_article: 1293" in out
    assert "last_fetch: 2026-05-10 18:07:54" in out
    assert "description: Web especializada en noticias y análisis." in out


# Regression for the original bug: `_format_sources` was reading
# `data.get("results")` directly on the fetch wrapper, so every
# successful call rendered "No sources found".
def test_format_sources_unwraps_fetch_envelope():
    envelope = {
        "status": "success",
        "data": {"results": [{"id": "x", "name": "X"}]},
    }
    out = format_sources(envelope)
    assert "[1] X" in out
    assert out != "No sources found matching your filters."


# ---------- format_counts (new in Step 4) ----------


def test_format_counts_error_envelope():
    out = format_counts({"status": "error", "message": "bad"}, "count")
    assert out == "Error: bad"


def test_format_counts_error_with_status_code():
    out = format_counts(
        {"status": "error", "message": "Server down.", "status_code": 503},
        "count",
    )
    assert out == "Error (HTTP 503): Server down."


# ---------- _format_error (the helper) ----------


def test_format_error_no_extras():
    """No status_code, no retry_after — bare 'Error: ...' format."""
    assert _format_error({"message": "boom"}) == "Error: boom"


def test_format_error_status_code_only():
    assert (
        _format_error({"message": "boom", "status_code": 404})
        == "Error (HTTP 404): boom"
    )


def test_format_error_retry_after_only():
    """retry_after without status_code shouldn't really happen, but the
    helper still renders it cleanly."""
    assert (
        _format_error({"message": "boom", "retry_after": 12})
        == "Error (retry after 12s): boom"
    )


def test_format_error_both_extras_in_stable_order():
    """HTTP code first, retry_after second, comma-separated. Stable
    order matters for any LLM that learns to parse the suffix."""
    assert (
        _format_error({"message": "boom", "status_code": 429, "retry_after": 12})
        == "Error (HTTP 429, retry after 12s): boom"
    )


def test_format_error_missing_message_falls_back():
    assert _format_error({}) == "Error: Unknown error"


def test_format_error_status_code_none_is_omitted():
    """status_code=None means 'not applicable' — don't render '(HTTP None)'."""
    assert (
        _format_error({"message": "network down", "status_code": None})
        == "Error: network down"
    )


def test_format_counts_empty_results():
    out = format_counts({"status": "success", "data": {"results": []}}, "count")
    assert out == "No results found for count over the given range."


def test_format_counts_list_of_buckets():
    """Bucket-list responses sum each bucket's `count` for the rendered
    `total_results` line. Real wire shape: `[{"dateTime": "...", "count": N}, ...]`."""
    out = format_counts(
        {
            "status": "success",
            "data": {
                "nextPage": None,
                "results": [
                    {"dateTime": "2021-01-01 00:00:00", "count": 100},
                    {"dateTime": "2020-12-31 00:00:00", "count": 150},
                ],
            },
        },
        "count",
    )
    assert "endpoint: count" in out
    assert "total_results: 250" in out  # 100 + 150
    assert "buckets: 2" in out
    assert "Bucket 1:" in out
    assert "Bucket 2:" in out
    assert "dateTime: 2021-01-01 00:00:00" in out
    assert "count: 100" in out
    assert "count: 150" in out


def test_format_counts_aggregate_dict():
    """When `interval="all"` or no interval is specified, NewsData returns
    `results` as a single aggregate dict: `{"count": N}`."""
    out = format_counts(
        {
            "status": "success",
            "data": {
                "results": {"count": 190440},
            },
        },
        "count",
    )
    assert "endpoint: count" in out
    assert "total_results: 190440" in out
    assert "aggregate:" in out
    assert "count: 190440" in out


def test_format_counts_renders_next_page_token():
    out = format_counts(
        {
            "status": "success",
            "data": {
                "nextPage": "1605225600000000000",
                "results": [{"dateTime": "2020-11-13 00:00:00", "count": 665}],
            },
        },
        "count",
    )
    assert "next_page: 1605225600000000000" in out


def test_format_counts_endpoint_name_used_in_no_results_message():
    out = format_counts(
        {"status": "success", "data": {"results": []}}, "crypto/count"
    )
    assert "crypto/count" in out
