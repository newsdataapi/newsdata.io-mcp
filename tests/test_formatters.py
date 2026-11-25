"""Unit tests for the pure-text rendering layer.

`formatters` has no network or framework dependencies; these tests are
synthetic-data only. Fixtures follow the API response objects.
"""
from newsdata_mcp.formatters import (
    _FULL_TEXT_HINT,
    _append_field,
    _clean_text,
    _format_article_item,
    _format_code_names,
    _format_error,
    _format_recommendation,
    _format_sentiment,
    _get_path,
    _is_plan_notice,
    format_articles,
    format_counts,
    format_sources,
    format_stream,
)

ARTICLE = {
    "id": "9f8e7d6c5b4a39281706f5e4d3c2b1a0",
    "title": "Central bank holds rates steady as inflation cools",
    "meta_description": "The central bank kept its key rate unchanged on Wednesday.",
    "content": "Full article text...",
    "url": "https://www.example.com/business/central-bank-holds-rates",
    "published_at": "2026-10-22T06:15:00Z",
    "fetched_at": "2026-10-22T06:18:42Z",
    "datatype": "news",
    "language": "english",
    "country": ["india"],
    "category": ["business"],
    "keyword": ["interest rates", "inflation"],
    "creator": ["Jane Doe"],
    "duplicate": False,
    "media": {"image_url": "https://www.example.com/images/rates.jpg", "video_url": None},
    "source": {
        "name": "Example News",
        "url": "https://www.example.com",
        "icon_url": "https://www.example.com/icon.png",
        "priority": 1520,
    },
    "ai": {
        "summary": "The central bank left its policy rate unchanged.",
        "sentiment": {"label": "neutral", "score": {"negative": 4.12, "neutral": 90.33, "positive": 5.55}},
        "tag": ["banking and finance", "economy"],
        "region": ["mumbai,maharashtra,india", "delhi,india"],
        "organization": ["reserve bank of india"],
    },
}

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


# ---------- _get_path ----------

def test_get_path_top_level_and_grouped():
    assert _get_path(ARTICLE, "title") == ARTICLE["title"]
    assert _get_path(ARTICLE, "source.name") == "Example News"
    assert _get_path(ARTICLE, "ai.summary") == "The central bank left its policy rate unchanged."


def test_get_path_missing_field_or_group_is_none():
    assert _get_path({}, "title") is None
    assert _get_path({}, "ai.summary") is None
    # A group that was left out with `exclude_field` or is not an object.
    assert _get_path({"ai": None}, "ai.summary") is None
    assert _get_path({"ai": "text"}, "ai.summary") is None


# ---------- _format_sentiment ----------

def test_sentiment_renders_label_and_score():
    out = _format_sentiment({"label": "neutral", "score": {"negative": 4.12, "neutral": 90.33, "positive": 5.55}})
    assert out == "neutral (negative=4.12, neutral=90.33, positive=5.55)"


def test_sentiment_label_only():
    assert _format_sentiment({"label": "positive", "score": None}) == "positive"


def test_sentiment_score_only():
    assert _format_sentiment({"label": None, "score": {"positive": 100.0}}) == "positive=100.0"


def test_sentiment_empty_or_non_dict_is_none():
    assert _format_sentiment({}) is None
    assert _format_sentiment({"label": None, "score": None}) is None
    assert _format_sentiment(None) is None
    assert _format_sentiment("not a dict") is None


# ---------- _is_plan_notice ----------

def test_plan_notice_detected():
    assert _is_plan_notice("ONLY AVAILABLE IN PAID PLANS")
    assert _is_plan_notice("ONLY AVAILABLE IN PROFESSIONAL AND CORPORATE PLANS")
    assert _is_plan_notice("ONLY AVAILABLE IN CORPORATE PLANS")


def test_real_values_are_not_plan_notices():
    assert not _is_plan_notice("Full article text...")
    assert not _is_plan_notice(None)
    assert not _is_plan_notice(["a"])
    assert not _is_plan_notice({"label": "neutral"})


# ---------- _format_code_names ----------

def test_code_names_renders_code_and_name():
    out = _format_code_names([{"code": "en", "name": "english"}, {"code": "hi", "name": "hindi"}])
    assert out == "en (english), hi (hindi)"


def test_code_names_handles_partial_items_and_plain_strings():
    assert _format_code_names([{"code": "en"}, {"name": "hindi"}, "spanish"]) == "en, hindi, spanish"


def test_code_names_empty_or_non_list_is_none():
    assert _format_code_names([]) is None
    assert _format_code_names(None) is None
    assert _format_code_names("english") is None


# ---------- _append_field ----------

def test_append_field_skips_none():
    lines = []
    _append_field(lines, "test", None)
    assert lines == []


def test_append_field_skips_blank_string_and_empty_list():
    lines = []
    _append_field(lines, "title", "   ")
    _append_field(lines, "keyword", [])
    _append_field(lines, "creator", [None, ""])
    assert lines == []


def test_append_field_renders_bool_lowercase():
    lines = []
    _append_field(lines, "duplicate", True)
    _append_field(lines, "duplicate", False)
    assert lines == ["duplicate: true", "duplicate: false"]


def test_append_field_renders_list_joined():
    lines = []
    _append_field(lines, "category", ["a", "b", "c"])
    assert lines == ["category: a, b, c"]


def test_append_field_custom_separator():
    lines = []
    _append_field(lines, "ai.region", ["paris,france", "delhi,india"], "; ")
    assert lines == ["ai.region: paris,france; delhi,india"]


def test_append_field_drops_falsy_list_items():
    lines = []
    _append_field(lines, "x", ["a", None, "", "b"])
    assert lines == ["x: a, b"]


def test_append_field_str_passthrough():
    lines = []
    _append_field(lines, "title", "hello")
    assert lines == ["title: hello"]


def test_append_field_keeps_zero():
    lines = []
    _append_field(lines, "count", 0)
    assert lines == ["count: 0"]


# ---------- _format_article_item ----------

def test_format_article_item_omits_missing_fields():
    lines = _format_article_item({"id": "x", "title": "hi"}, [])
    assert lines == ["title: hi", "id: x"]


def test_format_article_item_full_article_in_reading_order():
    not_in_plan: list[str] = []
    lines = _format_article_item(ARTICLE, not_in_plan)
    assert lines == [
        "title: Central bank holds rates steady as inflation cools",
        "url: https://www.example.com/business/central-bank-holds-rates",
        "source.name: Example News",
        "published_at: 2026-10-22T06:15:00Z",
        "meta_description: The central bank kept its key rate unchanged on Wednesday.",
        "ai.summary: The central bank left its policy rate unchanged.",
        "content: Full article text...",
        "language: english",
        "country: india",
        "category: business",
        "datatype: news",
        "keyword: interest rates, inflation",
        "creator: Jane Doe",
        "ai.sentiment: neutral (negative=4.12, neutral=90.33, positive=5.55)",
        "ai.tag: banking and finance, economy",
        "ai.region: mumbai,maharashtra,india; delhi,india",
        "ai.organization: reserve bank of india",
        "media.image_url: https://www.example.com/images/rates.jpg",
        "source.url: https://www.example.com",
        "source.priority: 1520",
        "fetched_at: 2026-10-22T06:18:42Z",
        "duplicate: false",
        "id: 9f8e7d6c5b4a39281706f5e4d3c2b1a0",
    ]
    assert not_in_plan == []


def test_format_article_item_does_not_show_icon_url():
    lines = _format_article_item(ARTICLE, [])
    assert not any("icon" in line for line in lines)


def test_format_article_item_market_and_crypto_fields():
    lines = _format_article_item(
        {"id": "m1", "ticker": ["AAPL", "MSFT"], "market_id": ["AAPL-US-VY", "MSFT-US-VY"], "coin": ["BTC"]},
        [],
    )
    assert "ticker: AAPL, MSFT" in lines
    assert "market_id: AAPL-US-VY, MSFT-US-VY" in lines
    assert "coin: BTC" in lines


def test_format_article_item_collects_plan_notices_instead_of_printing_them():
    article = {
        "id": "x",
        "title": "hi",
        "content": "ONLY AVAILABLE IN PAID PLANS",
        "ai": {
            "summary": "ONLY AVAILABLE IN PAID PLANS",
            "sentiment": "ONLY AVAILABLE IN PROFESSIONAL AND CORPORATE PLANS",
            "tag": ["economy"],
            "region": "ONLY AVAILABLE IN CORPORATE PLANS",
            "organization": "ONLY AVAILABLE IN CORPORATE PLANS",
        },
    }
    not_in_plan: list[str] = []
    lines = _format_article_item(article, not_in_plan)
    assert lines == ["title: hi", "ai.tag: economy", "id: x"]
    assert not_in_plan == ["ai.summary", "content", "ai.sentiment", "ai.region", "ai.organization"]

    # A second article with the same notices adds nothing new.
    _format_article_item(article, not_in_plan)
    assert not_in_plan == ["ai.summary", "content", "ai.sentiment", "ai.region", "ai.organization"]


# ---------- format_articles ----------

def test_format_articles_error_envelope():
    out = format_articles({"status": "error", "message": "bad"}, "news")
    assert out == "Error: bad"


def test_format_articles_error_with_status_code():
    out = format_articles(
        {"status": "error", "message": "Unauthorized.", "status_code": 401},
        "news",
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
        "news",
    )
    assert out == "Error (HTTP 429, retry after 30s): Rate limit exceeded."


def test_format_articles_empty():
    out = format_articles(
        {"status": "success", "data": {"total_results": 0, "results": [], "next_page": None}}, "news"
    )
    assert out == "No news articles found matching your query."


def test_format_articles_results_not_a_list_is_treated_as_empty():
    out = format_articles({"status": "success", "data": {"results": {"unexpected": 1}}}, "crypto")
    assert out == "No crypto articles found matching your query."


def test_format_articles_populated_headers_and_body():
    out = format_articles(
        {
            "status": "success",
            "data": {
                "total_results": 2841,
                "next_page": "1792649700000000000",
                "results": [
                    {
                        "id": "abc",
                        "title": "Hello world",
                        "url": "https://example.com/",
                        "published_at": "2026-05-08T10:00:00Z",
                    },
                    {"id": "def", "title": "Second"},
                ],
            },
        },
        "news",
    )
    assert out.splitlines() == [
        "endpoint: news",
        "total_results: 2841",
        "returned_results: 2",
        "next_page: 1792649700000000000",
        "",
        "Article 1:",
        "title: Hello world",
        "url: https://example.com/",
        "published_at: 2026-05-08T10:00:00Z",
        "id: abc",
        "",
        "Article 2:",
        "title: Second",
        "id: def",
    ]


def test_format_articles_last_page_says_none():
    out = format_articles(
        {"status": "success", "data": {"total_results": 1, "next_page": None, "results": [{"id": "a"}]}},
        "news",
    )
    assert "next_page: none" in out


def test_format_articles_reports_plan_notices_once_in_the_header():
    free_plan_article = {
        "id": "a",
        "title": "T",
        "content": "ONLY AVAILABLE IN PAID PLANS",
        "ai": {"summary": "ONLY AVAILABLE IN PAID PLANS", "tag": ["economy"]},
    }
    out = format_articles(
        {
            "status": "success",
            "data": {
                "total_results": 2,
                "next_page": None,
                "results": [free_plan_article, {**free_plan_article, "id": "b"}],
            },
        },
        "news",
    )
    assert "ONLY AVAILABLE" not in out
    assert out.count("not_in_your_plan: ai.summary, content") == 1
    # The header line sits before the first article.
    assert out.index("not_in_your_plan:") < out.index("Article 1:")


def test_format_articles_no_plan_line_when_nothing_is_withheld():
    out = format_articles(
        {"status": "success", "data": {"total_results": 1, "results": [ARTICLE]}}, "news"
    )
    assert "not_in_your_plan" not in out


# ---------- format_sources ----------

SOURCE = {
    "name": "Example News",
    "url": "https://www.example.com",
    "icon_url": "https://www.example.com/icon.png",
    "priority": 1520,
    "description": "Business and economy news from India.",
    "language": [{"code": "en", "name": "english"}],
    "country": [{"code": "in", "name": "india"}],
    "category": ["business", "top"],
    "stat": {"article_count": 182340, "last_fetched_at": "2026-10-22T06:10:00Z"},
}


def test_format_sources_error_envelope():
    out = format_sources({"status": "error", "message": "auth fail"})
    assert out == "Error: auth fail"


def test_format_sources_error_with_status_code():
    out = format_sources(
        {"status": "error", "message": "Unauthorized.", "status_code": 401}
    )
    assert out == "Error (HTTP 401): Unauthorized."


def test_format_sources_empty():
    out = format_sources({"status": "success", "data": {"total_results": 0, "results": []}})
    assert out == "No sources found matching your filters."


def test_format_sources_populated():
    out = format_sources({"status": "success", "data": {"total_results": 1, "results": [SOURCE]}})
    assert out.splitlines() == [
        "endpoint: sources",
        "total_results: 1",
        "returned_results: 1",
        "",
        "Source 1:",
        "name: Example News",
        "url: https://www.example.com",
        "priority: 1520",
        "language: en (english)",
        "country: in (india)",
        "category: business, top",
        "description: Business and economy news from India.",
        "stat.article_count: 182340",
        "stat.last_fetched_at: 2026-10-22T06:10:00Z",
    ]


def test_format_sources_missing_optional_fields():
    """`language`, `country`, `category` and `stat` can be null."""
    out = format_sources(
        {
            "status": "success",
            "data": {
                "total_results": 1,
                "results": [{"name": "X", "url": "https://x.example", "language": None, "stat": None}],
            },
        }
    )
    assert out.splitlines() == [
        "endpoint: sources",
        "total_results: 1",
        "returned_results: 1",
        "",
        "Source 1:",
        "name: X",
        "url: https://x.example",
    ]


def test_format_sources_notes_the_100_source_limit():
    sources = [{"name": f"S{i}", "url": f"https://s{i}.example"} for i in range(100)]
    out = format_sources({"status": "success", "data": {"total_results": 100, "results": sources}})
    assert "note: the API returns at most 100 sources" in out
    assert "Source 100:" in out


def test_format_sources_no_limit_note_below_100():
    out = format_sources({"status": "success", "data": {"total_results": 1, "results": [SOURCE]}})
    assert "note:" not in out


# ---------- format_counts ----------

def test_format_counts_error_envelope():
    out = format_counts({"status": "error", "message": "bad"}, "count/news")
    assert out == "Error: bad"


def test_format_counts_error_with_status_code():
    out = format_counts(
        {"status": "error", "message": "Server down.", "status_code": 503},
        "count/news",
    )
    assert out == "Error (HTTP 503): Server down."


def test_format_counts_buckets_and_api_total():
    """`total_results` is the API's total for the whole range, not the
    sum of this page's buckets."""
    out = format_counts(
        {
            "status": "success",
            "data": {
                "total_results": 15230,
                "next_page": "1790640000000000000",
                "results": [
                    {"date_time": "2026-09-30T00:00:00Z", "count": 812},
                    {"date_time": "2026-09-29T00:00:00Z", "count": 0},
                ],
            },
        },
        "count/news",
    )
    assert out.splitlines() == [
        "endpoint: count/news",
        "total_results: 15230",
        "returned_buckets: 2",
        "next_page: 1790640000000000000",
        "",
        "date_time,count",
        "2026-09-30T00:00:00Z,812",
        "2026-09-29T00:00:00Z,0",
    ]


def test_format_counts_page_without_buckets_still_shows_total():
    out = format_counts(
        {"status": "success", "data": {"total_results": 0, "results": [], "next_page": None}},
        "count/crypto",
    )
    assert out.splitlines() == [
        "endpoint: count/crypto",
        "total_results: 0",
        "returned_buckets: 0",
        "next_page: none",
    ]


def test_format_counts_no_total_and_no_buckets():
    out = format_counts({"status": "success", "data": {"results": []}}, "count/market")
    assert out == "No results found for count/market over the given range."


# ---------- _format_recommendation ----------

def test_recommendation_plain_string():
    assert _format_recommendation("sports") == "sports"


def test_recommendation_code_and_name():
    assert _format_recommendation({"code": "us", "name": "united states of america"}) == (
        "us (united states of america)"
    )


def test_recommendation_tag_id_and_name():
    assert _format_recommendation({"id": "artificial_intelligence", "name": "artificial intelligence"}) == (
        "artificial_intelligence (artificial intelligence)"
    )


def test_recommendation_market_id_puts_the_id_first():
    item = {"ticker": "AAPL", "country": "USA", "exchangeName": "Cboe BYX", "id": "AAPL-US-VY"}
    assert _format_recommendation(item) == "AAPL-US-VY (AAPL, USA, Cboe BYX)"


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


def test_format_error_with_api_error_code():
    """The API's error code sits between the HTTP status and retry_after."""
    assert (
        _format_error({"message": "boom", "status_code": 422, "error_code": "UnsupportedFilter"})
        == "Error (HTTP 422, UnsupportedFilter): boom"
    )
    assert (
        _format_error(
            {"message": "slow down", "status_code": 429, "error_code": "RateLimitExceeded", "retry_after": 5}
        )
        == "Error (HTTP 429, RateLimitExceeded, retry after 5s): slow down"
    )


def test_format_error_lists_suggested_values():
    out = _format_error(
        {
            "message": 'The category "sprots" doesn\'t exist in our database.',
            "status_code": 422,
            "error_code": "UnsupportedFilter",
            "recommendations": {"sprots": ["sports"], "movie": ["entertainment", "lifestyle"]},
        }
    )
    assert out.splitlines() == [
        'Error (HTTP 422, UnsupportedFilter): The category "sprots" doesn\'t exist in our database.',
        'Valid values close to "sprots": sports',
        'Valid values close to "movie": entertainment; lifestyle',
    ]


def test_format_error_says_when_nothing_close_was_found():
    """An empty suggestion list means the API found no close match."""
    out = _format_error(
        {"message": "bad", "status_code": 422, "recommendations": {"zz_not_a_tag": []}}
    )
    assert out.splitlines() == [
        "Error (HTTP 422): bad",
        'No valid value close to "zz_not_a_tag" was found.',
    ]


def test_format_error_missing_message_falls_back():
    assert _format_error({}) == "Error: Unknown error"


def test_format_error_status_code_none_is_omitted():
    """status_code=None means 'not applicable' — don't render '(HTTP None)'."""
    assert (
        _format_error({"message": "network down", "status_code": None})
        == "Error: network down"
    )


# ---------- lists without the full text ----------


def test_format_article_item_can_skip_full_text():
    lines = _format_article_item(ARTICLE, [], full_text=False)
    assert not any(line.startswith("content:") for line in lines)
    assert "meta_description: The central bank kept its key rate unchanged on Wednesday." in lines
    assert "ai.summary: The central bank left its policy rate unchanged." in lines


def test_skipped_full_text_is_not_reported_as_withheld_by_the_plan():
    """When the list leaves `content` out anyway, a plan notice in that
    field says nothing the model needs."""
    not_in_plan: list[str] = []
    _format_article_item({"id": "x", "content": "ONLY AVAILABLE IN PAID PLANS"}, not_in_plan, full_text=False)
    assert not_in_plan == []


def test_format_articles_list_without_full_text_has_a_hint_line():
    out = format_articles(
        {"status": "success", "data": {"total_results": 1, "next_page": None, "results": [ARTICLE]}},
        "news",
        full_text=False,
    )
    assert out.splitlines()[:5] == [
        "endpoint: news",
        "total_results: 1",
        "returned_results: 1",
        "next_page: none",
        _FULL_TEXT_HINT,
    ]
    assert "Full article text..." not in out


def test_full_text_hint_names_both_ways_to_get_the_text():
    assert _FULL_TEXT_HINT.startswith("full_text: ")
    assert "id=" in _FULL_TEXT_HINT
    assert "content=true" in _FULL_TEXT_HINT


def test_format_articles_shows_full_text_by_default():
    out = format_articles(
        {"status": "success", "data": {"total_results": 1, "next_page": None, "results": [ARTICLE]}}, "news"
    )
    assert "content: Full article text..." in out
    assert "full_text:" not in out


def test_hint_line_comes_before_the_plan_line():
    out = format_articles(
        {
            "status": "success",
            "data": {
                "total_results": 1,
                "next_page": None,
                "results": [{"id": "a", "ai": {"summary": "ONLY AVAILABLE IN PAID PLANS"}}],
            },
        },
        "news",
        full_text=False,
    )
    assert out.splitlines()[4] == _FULL_TEXT_HINT
    assert out.splitlines()[5] == "not_in_your_plan: ai.summary"


def test_format_error_leaves_http_200_out():
    """A soft error arrives with HTTP 200. Printing "HTTP 200" before an
    error could be read as success."""
    assert _format_error({"message": "Bad date", "status_code": 200}) == "Error: Bad date"
    assert (
        _format_error({"message": "Bad syntax", "status_code": 200, "error_code": "MalformedQuery"})
        == "Error (MalformedQuery): Bad syntax"
    )


def test_format_error_shows_the_existing_registration_id():
    """A duplicate real-time registration names the id that already exists."""
    out = _format_error(
        {
            "message": "This query is already registered.",
            "status_code": 409,
            "error_code": "Conflict",
            "registration_id": "9b2d1e8a7c4f4b6e9d3a5c7e1f2a4b6c",
        }
    )
    assert out.splitlines() == [
        "Error (HTTP 409, Conflict): This query is already registered.",
        "registration_id: 9b2d1e8a7c4f4b6e9d3a5c7e1f2a4b6c",
    ]


# ---------- real-time: a streamed article has the article layout ----------

REGISTRATION = "1111111122223333444455556666aaaa"


def test_format_stream_renders_articles_like_the_news_tools():
    article = {
        "id": "x",
        "title": "Hello",
        "url": "https://example.com/a",
        "published_at": "2026-11-16T06:15:00Z",
        "source": {"name": "Example News"},
        "ai": {"summary": "Short.", "tag": ["economy"]},
    }
    lines = format_stream([article], REGISTRATION, "max_articles", 1.0).splitlines()
    assert lines[lines.index("Article 1:") + 1:] == [
        "title: Hello",
        "url: https://example.com/a",
        "source.name: Example News",
        "published_at: 2026-11-16T06:15:00Z",
        "ai.summary: Short.",
        "ai.tag: economy",
        "id: x",
    ]


def test_format_stream_leaves_out_plan_notices_and_reports_their_names_once():
    article = {
        "id": "x",
        "title": "Hello",
        "content": "ONLY AVAILABLE IN PAID PLANS",
        "ai": {
            "sentiment": "ONLY AVAILABLE IN PROFESSIONAL AND CORPORATE PLANS",
            "region": "ONLY AVAILABLE IN CORPORATE PLANS",
        },
    }
    out = format_stream([article, article], REGISTRATION, "max_articles", 1.0)

    assert "ONLY AVAILABLE IN" not in out
    assert out.count("not_in_your_plan: content, ai.sentiment, ai.region") == 1


def test_format_stream_can_leave_the_full_text_out():
    article = {"id": "x", "title": "Hello", "ai": {"summary": "Short."}, "content": "Long text."}
    assert "content: Long text." in format_stream([article], REGISTRATION, "timeout", 1.0)

    out = format_stream([article], REGISTRATION, "timeout", 1.0, full_text=False)
    assert "Long text." not in out
    assert "ai.summary: Short." in out
    assert "get_news with id=<its id>" in out
