"""End-to-end tests that call the @mcp.tool() functions with a mocked
NewsData API. These check that each tool hits its own endpoint, that
arguments reach the wire under the API's own names, and that the right
formatter is wired per endpoint.
"""
import httpx
import respx

from newsdata_mcp.tools.count import get_news_counts
from newsdata_mcp.tools.crypto import get_crypto_news
from newsdata_mcp.tools.crypto_count import get_crypto_counts
from newsdata_mcp.tools.market import get_market_news
from newsdata_mcp.tools.market_count import get_market_counts
from newsdata_mcp.tools.news import get_news
from newsdata_mcp.tools.sources import get_news_sources

API = "https://newsdata.io/api/2"
EMPTY = {"status": "success", "total_results": 0, "results": [], "next_page": None}

# What an article tool adds to a search when the caller passes neither `size`
# nor `content=true`: a short list, with the full text left out.
LIST_DEFAULTS = {"size": "10", "exclude_field": "content"}


def _mock_empty(path: str) -> respx.Route:
    return respx.get(f"{API}/{path}").mock(return_value=httpx.Response(200, json=EMPTY))


def _query(route: respx.Route, call: int = 0) -> dict[str, str]:
    return dict(route.calls[call].request.url.params)


# ---------------------------------------------------------------------------
# Each tool → its endpoint, its formatter.
# ---------------------------------------------------------------------------


@respx.mock
async def test_news_renders_text():
    respx.get(f"{API}/news").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "total_results": 1,
                "results": [
                    {
                        "id": "a1",
                        "title": "Latest title",
                        "url": "https://x",
                        "source": {"name": "Example News", "url": "https://example.com"},
                    }
                ],
                "next_page": None,
            },
        )
    )
    out = await get_news(q="bitcoin", country="us", size=10)
    assert out.startswith("endpoint: news")
    assert "title: Latest title" in out
    assert "url: https://x" in out
    assert "source.name: Example News" in out


@respx.mock
async def test_news_sends_the_arguments_passed_plus_the_list_defaults():
    """Every unset argument is None and must stay off the wire; the only
    additions are the two list defaults."""
    route = _mock_empty("news")
    await get_news(q="bitcoin")
    assert _query(route) == {"q": "bitcoin", **LIST_DEFAULTS}


@respx.mock
async def test_news_sends_arguments_under_the_api_names():
    route = _mock_empty("news")
    await get_news(
        q_in_title="apple",
        exclude_country="cn",
        exclude_category="sports",
        exclude_language="fr",
        source_url="bbc.com",
        source_priority="top",
        content=True,
        remove_duplicate=True,
        exclude_field="content,ai.summary",
    )
    qs = _query(route)
    assert qs == {
        "q_in_title": "apple",
        "exclude_country": "cn",
        "exclude_category": "sports",
        "exclude_language": "fr",
        "source_url": "bbc.com",
        "source_priority": "top",
        "content": "1",
        "remove_duplicate": "1",
        "exclude_field": "content,ai.summary",
        "size": "10",
    }


@respx.mock
async def test_news_covers_recent_and_historical_ranges():
    """One tool for both: dates for a range, timeframe for the last N hours."""
    route = _mock_empty("news")
    out = await get_news(q="war", from_date="2026-06-01", to_date="2026-06-30")
    qs = _query(route)
    assert qs["from_date"] == "2026-06-01"
    assert qs["to_date"] == "2026-06-30"
    assert out == "No news articles found matching your query."

    await get_news(q="war", timeframe=24)
    assert _query(route, 1)["timeframe"] == "24"

    await get_news(q="war", timeframe="90m")
    assert _query(route, 2)["timeframe"] == "90m"


@respx.mock
async def test_news_id_lookup_with_dates():
    route = _mock_empty("news")
    await get_news(
        id=["aabbccddeeff00112233445566778899", "99887766554433221100ffeeddccbbaa"],
        from_date="2026-06-01",
        to_date="2026-06-30",
    )
    assert _query(route) == {
        "id": "aabbccddeeff00112233445566778899,99887766554433221100ffeeddccbbaa",
        "from_date": "2026-06-01",
        "to_date": "2026-06-30",
    }


@respx.mock
async def test_crypto_news_uses_crypto_endpoint_and_passes_coin():
    route = _mock_empty("crypto")
    out = await get_crypto_news(coin="btc,eth", sentiment="positive", tag="blockchain")
    assert _query(route) == {"coin": "btc,eth", "sentiment": "positive", "tag": "blockchain", **LIST_DEFAULTS}
    assert out == "No crypto articles found matching your query."


@respx.mock
async def test_market_news_uses_market_endpoint_and_passes_market_id():
    route = _mock_empty("market")
    out = await get_market_news(market_id="aapl-us-vy,msft-us-vy", country="us")
    qs = _query(route)
    assert qs == {"market_id": "aapl-us-vy,msft-us-vy", "country": "us", **LIST_DEFAULTS}
    assert out == "No market articles found matching your query."


@respx.mock
async def test_market_news_renders_ticker_and_market_id():
    respx.get(f"{API}/market").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "total_results": 1,
                "results": [
                    {
                        "id": "m1",
                        "title": "Apple beats estimates",
                        "ticker": ["AAPL"],
                        "market_id": ["AAPL-US-VY"],
                    }
                ],
                "next_page": None,
            },
        )
    )
    out = await get_market_news(q="apple")
    assert out.startswith("endpoint: market")
    assert "ticker: AAPL" in out
    assert "market_id: AAPL-US-VY" in out


@respx.mock
async def test_news_sources_renders_source_metadata():
    route = respx.get(f"{API}/sources").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "total_results": 1,
                "results": [
                    {
                        "name": "BBC",
                        "url": "https://www.bbc.com",
                        "priority": 105,
                        "language": [{"code": "en", "name": "english"}],
                        "country": [{"code": "gb", "name": "united kingdom"}],
                        "category": ["top", "world"],
                    }
                ],
            },
        )
    )
    out = await get_news_sources(country="gb", source_priority="top")
    assert _query(route) == {"country": "gb", "source_priority": "top"}
    assert out.startswith("endpoint: sources")
    assert "Source 1:" in out
    assert "name: BBC" in out
    assert "url: https://www.bbc.com" in out
    assert "language: en (english)" in out


@respx.mock
async def test_news_sources_surfaces_api_error():
    respx.get(f"{API}/sources").mock(return_value=httpx.Response(401, text="bad"))
    out = await get_news_sources()
    assert out.startswith("Error (HTTP 401):")
    assert "Unauthorized" in out


@respx.mock
async def test_tool_passes_on_the_api_error_with_suggested_values():
    """The message, the error code and the suggested values come from the
    API and reach the model unchanged, so it can fix its own call."""
    respx.get(f"{API}/news").mock(
        return_value=httpx.Response(
            422,
            json={
                "status": "error",
                "results": {
                    "message": 'The country "usa" doesn\'t exist in our database.',
                    "code": "UnsupportedFilter",
                    "invalid_country": "usa",
                    "recommendations": {"usa": [{"code": "us", "name": "united states of america"}]},
                },
            },
        )
    )
    out = await get_news(country="usa")
    assert out.splitlines() == [
        'Error (HTTP 422, UnsupportedFilter): The country "usa" doesn\'t exist in our database.',
        'Valid values close to "usa": us (united states of america)',
    ]


# ---------------------------------------------------------------------------
# Mutex validation runs at the tool boundary, *before* fetch() is called.
# These tests use respx.mock without registering any routes — if a tool
# attempts a network call despite a mutex violation, respx fails the test.
# ---------------------------------------------------------------------------


@respx.mock(assert_all_called=False)
async def test_news_mutex_q_and_q_in_title_short_circuits():
    out = await get_news(q="bitcoin", q_in_title="ethereum")
    assert out.startswith("Error:")
    assert "'q'" in out
    assert "'q_in_title'" in out
    assert "mutually exclusive" in out
    # No network call was made.
    assert len(respx.calls) == 0


@respx.mock(assert_all_called=False)
async def test_news_mutex_country_and_exclude_country_short_circuits():
    out = await get_news(country="us", exclude_country="gb")
    assert out.startswith("Error:")
    assert "'country'" in out
    assert "'exclude_country'" in out
    assert len(respx.calls) == 0


@respx.mock(assert_all_called=False)
async def test_news_mutex_source_url_and_exclude_source_url_short_circuits():
    out = await get_news(source_url="bbc.com", exclude_source_url="reuters.com")
    assert out.startswith("Error:")
    assert "'source_url'" in out
    assert "'exclude_source_url'" in out
    assert len(respx.calls) == 0


@respx.mock(assert_all_called=False)
async def test_crypto_mutex_language_and_exclude_language_short_circuits():
    out = await get_crypto_news(language="en", exclude_language="fr")
    assert out.startswith("Error:")
    assert "'language'" in out
    assert "'exclude_language'" in out
    assert len(respx.calls) == 0


@respx.mock(assert_all_called=False)
async def test_market_mutex_q_in_meta_and_q_short_circuits():
    out = await get_market_news(q="apple", q_in_meta="earnings")
    assert out.startswith("Error:")
    assert "'q'" in out
    assert "'q_in_meta'" in out
    assert len(respx.calls) == 0


@respx.mock
async def test_valid_one_per_group_still_passes_through_to_api():
    """Sanity check: a valid combination (one member per group) reaches
    fetch() as before. Catches accidental over-zealous blocking."""
    route = _mock_empty("news")
    out = await get_news(
        q="bitcoin",
        country="us",
        category="technology",
        language="en",
        source_url="reuters.com",
    )
    assert route.called
    assert not out.startswith("Error")


@respx.mock
async def test_blank_arguments_do_not_count_as_set():
    """A model that sends "" or [] for a parameter it does not use must
    not trip a mutex rule, and the blank value must not reach the API."""
    route = _mock_empty("news")
    out = await get_news(q="bitcoin", q_in_title="", country=[], exclude_country="cn")
    assert not out.startswith("Error")
    assert _query(route) == {"q": "bitcoin", "exclude_country": "cn", **LIST_DEFAULTS}


# ---------------------------------------------------------------------------
# Tool-level acceptance of the input shapes models produce.
# ---------------------------------------------------------------------------


@respx.mock
async def test_news_accepts_bool_for_flags():
    route = _mock_empty("news")
    await get_news(image=True, video=False, content=True)
    assert _query(route) == {"image": "1", "video": "0", "content": "1", "size": "10"}


@respx.mock
async def test_news_accepts_one_and_zero_for_flags():
    route = _mock_empty("news")
    await get_news(image=1, video=0)
    assert _query(route) == {"image": "1", "video": "0", **LIST_DEFAULTS}


@respx.mock
async def test_news_remove_duplicate_false_dropped():
    route = _mock_empty("news")
    await get_news(q="x", remove_duplicate=False)
    assert _query(route) == {"q": "x", **LIST_DEFAULTS}


@respx.mock
async def test_news_accepts_list_for_multi_value_filters():
    route = _mock_empty("news")
    await get_news(
        country=["us", "gb", "in"],
        category=["technology", "science"],
        creator=["john smith", "jane doe"],
        datatype=["news", "blog"],
        tag=["elections", "artificial_intelligence"],
    )
    assert _query(route) == {
        "country": "us,gb,in",
        "category": "technology,science",
        "creator": "john smith,jane doe",
        "datatype": "news,blog",
        "tag": "elections,artificial_intelligence",
        **LIST_DEFAULTS,
    }


@respx.mock
async def test_crypto_news_accepts_list_for_coin():
    route = _mock_empty("crypto")
    await get_crypto_news(coin=["btc", "eth", "sol"])
    assert _query(route)["coin"] == "btc,eth,sol"


@respx.mock
async def test_market_news_accepts_list_for_market_id():
    route = _mock_empty("market")
    await get_market_news(market_id=["aapl-us-vy", "msft-us-vy"])
    assert _query(route)["market_id"] == "aapl-us-vy,msft-us-vy"


@respx.mock
async def test_news_sources_accepts_list_for_country():
    route = _mock_empty("sources")
    await get_news_sources(country=["us", "gb"])
    assert _query(route)["country"] == "us,gb"


@respx.mock
async def test_news_mixed_realistic_llm_call():
    """An LLM-style call: bools, lists, ints, all together."""
    route = _mock_empty("news")
    await get_news(
        q="bitcoin OR ethereum",
        country=["us", "gb"],
        language=["en"],
        category=["technology", "business"],
        image=True,
        content=True,
        size=10,
        timeframe=24,
        remove_duplicate=True,
        source_priority="top",
        region="new york-united states of america",
        organization=["tesla", "apple"],
    )
    assert _query(route) == {
        "q": "bitcoin OR ethereum",
        "country": "us,gb",
        "language": "en",
        "category": "technology,business",
        "image": "1",
        "content": "1",
        "size": "10",
        "timeframe": "24",
        "remove_duplicate": "1",
        "source_priority": "top",
        "region": "new york-united states of america",
        "organization": "tesla,apple",
    }


# ---------------------------------------------------------------------------
# sentiment_score requires sentiment. Wired on news, market and the two
# count tools that take sentiment_score.
# ---------------------------------------------------------------------------


@respx.mock
async def test_news_sentiment_score_with_sentiment_passes():
    route = _mock_empty("news")
    await get_news(sentiment="positive", sentiment_score=70)
    assert _query(route) == {"sentiment": "positive", "sentiment_score": "70", **LIST_DEFAULTS}


@respx.mock(assert_all_called=False)
async def test_news_sentiment_score_without_sentiment_short_circuits():
    out = await get_news(sentiment_score=50)
    assert out.startswith("Error:")
    assert "'sentiment_score'" in out
    assert "'sentiment'" in out
    # And the message tells the LLM what concrete fix to apply.
    assert "'positive'" in out
    assert len(respx.calls) == 0


@respx.mock(assert_all_called=False)
async def test_market_news_sentiment_score_without_sentiment_short_circuits():
    out = await get_market_news(sentiment_score=80, market_id="nvda-us-vy")
    assert out.startswith("Error:")
    assert "'sentiment_score'" in out
    assert "'sentiment'" in out
    assert len(respx.calls) == 0


@respx.mock
async def test_market_news_sentiment_pair_passes():
    route = _mock_empty("market")
    await get_market_news(sentiment="positive", sentiment_score=80, market_id="nvda-us-vy")
    assert _query(route) == {
        "sentiment": "positive",
        "sentiment_score": "80",
        "market_id": "nvda-us-vy",
        **LIST_DEFAULTS,
    }


@respx.mock
async def test_sentiment_alone_still_works_without_score():
    """Regression: the validator must not block `sentiment` alone."""
    route = _mock_empty("news")
    out = await get_news(sentiment="positive", q="bitcoin")
    assert not out.startswith("Error:")
    assert _query(route) == {"sentiment": "positive", "q": "bitcoin", **LIST_DEFAULTS}


# ---------------------------------------------------------------------------
# Count tools. Each hits its own /count/* URL, needs no dates, and renders
# the API's total plus one line per bucket.
# ---------------------------------------------------------------------------


@respx.mock
async def test_news_counts_hits_count_news_endpoint():
    route = respx.get(f"{API}/count/news").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "total_results": 15230,
                "results": [
                    {"date_time": "2026-09-30T00:00:00Z", "count": 812},
                    {"date_time": "2026-09-29T00:00:00Z", "count": 744},
                ],
                "next_page": "1790640000000000000",
            },
        )
    )
    out = await get_news_counts(q="inflation", from_date="2026-09-01", to_date="2026-09-30", size=2)
    assert _query(route) == {
        "q": "inflation",
        "from_date": "2026-09-01",
        "to_date": "2026-09-30",
        "size": "2",
    }
    assert out.splitlines() == [
        "endpoint: count/news",
        "total_results: 15230",
        "returned_buckets: 2",
        "next_page: 1790640000000000000",
        "",
        "date_time,count",
        "2026-09-30T00:00:00Z,812",
        "2026-09-29T00:00:00Z,744",
    ]


@respx.mock
async def test_count_tools_work_without_dates():
    """Counts default to the last 30 days: no argument is required."""
    news = _mock_empty("count/news")
    crypto = _mock_empty("count/crypto")
    market = _mock_empty("count/market")

    await get_news_counts(q="x")
    await get_crypto_counts()
    await get_market_counts()

    assert _query(news) == {"q": "x"}
    assert _query(crypto) == {}
    assert _query(market) == {}


@respx.mock
async def test_news_counts_interval_and_timeframe_sent():
    route = _mock_empty("count/news")
    await get_news_counts(country="us", interval="month", timeframe=48, sort="pubdateasc")
    assert _query(route) == {
        "country": "us",
        "interval": "month",
        "timeframe": "48",
        "sort": "pubdateasc",
    }


@respx.mock(assert_all_called=False)
async def test_news_counts_mutex_short_circuits():
    out = await get_news_counts(q="x", q_in_title="y")
    assert out.startswith("Error:")
    assert "'q'" in out
    assert "'q_in_title'" in out
    assert len(respx.calls) == 0


@respx.mock(assert_all_called=False)
async def test_news_counts_sentiment_score_without_sentiment_short_circuits():
    out = await get_news_counts(q="x", sentiment_score=50)
    assert out.startswith("Error:")
    assert "'sentiment_score'" in out
    assert "'sentiment'" in out
    assert len(respx.calls) == 0


@respx.mock
async def test_crypto_counts_hits_count_crypto_endpoint():
    route = respx.get(f"{API}/count/crypto").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "total_results": 42,
                "results": [{"date_time": "2026-10-20T00:00:00Z", "count": 42}],
                "next_page": None,
            },
        )
    )
    out = await get_crypto_counts(coin=["btc", "eth"], interval="hour")
    assert _query(route) == {"coin": "btc,eth", "interval": "hour"}
    assert out.startswith("endpoint: count/crypto")
    assert "2026-10-20T00:00:00Z,42" in out


@respx.mock(assert_all_called=False)
async def test_crypto_counts_mutex_language_short_circuits():
    out = await get_crypto_counts(language="en", exclude_language="fr")
    assert out.startswith("Error:")
    assert "'language'" in out
    assert "'exclude_language'" in out
    assert len(respx.calls) == 0


@respx.mock
async def test_market_counts_hits_count_market_endpoint():
    route = respx.get(f"{API}/count/market").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "total_results": 12,
                "results": [{"date_time": "2026-09-01T00:00:00Z", "count": 12}],
                "next_page": None,
            },
        )
    )
    out = await get_market_counts(market_id="aapl-us-vy", interval="day")
    qs = _query(route)
    assert qs == {"market_id": "aapl-us-vy", "interval": "day"}
    assert out.startswith("endpoint: count/market")


@respx.mock(assert_all_called=False)
async def test_market_counts_sentiment_score_without_sentiment_short_circuits():
    out = await get_market_counts(sentiment_score=80)
    assert out.startswith("Error:")
    assert len(respx.calls) == 0


@respx.mock
async def test_count_tool_surfaces_plan_error_from_api():
    """Count endpoints need a paid plan; the API's own 403 message is shown."""
    respx.get(f"{API}/count/news").mock(
        return_value=httpx.Response(
            403,
            json={
                "status": "error",
                "results": {
                    "message": "Access denied! You need to upgrade your plan in order to access the count endpoint.",
                    "code": "AccessDenied",
                },
            },
        )
    )
    out = await get_news_counts(q="x")
    assert out == (
        "Error (HTTP 403, AccessDenied): Access denied! You need to upgrade your plan "
        "in order to access the count endpoint."
    )


# ---------------------------------------------------------------------------
# List defaults. A search returns a short list without the full text; a
# lookup by id or url, or content=true, returns the full text.
# ---------------------------------------------------------------------------

ARTICLE_WITH_TEXT = {
    "id": "a1",
    "title": "Hello",
    "meta_description": "Short description.",
    "content": "The whole article text.",
}


def _mock_one_article(path: str) -> respx.Route:
    return respx.get(f"{API}/{path}").mock(
        return_value=httpx.Response(
            200,
            json={"status": "success", "total_results": 1, "results": [ARTICLE_WITH_TEXT], "next_page": None},
        )
    )


@respx.mock
async def test_search_leaves_full_text_out_and_says_how_to_get_it():
    """The request asks the API to leave `content` out, and even if the
    API sent it anyway a list does not print it."""
    route = _mock_one_article("news")
    out = await get_news(q="hello")
    assert _query(route) == {"q": "hello", **LIST_DEFAULTS}
    assert "The whole article text." not in out
    assert "meta_description: Short description." in out
    assert "full_text: left out of this list." in out


@respx.mock
async def test_lookup_by_id_returns_full_text_and_adds_nothing_to_the_request():
    """The API accepts nothing next to `id` except dates, so no default
    may be added to a lookup."""
    route = _mock_one_article("news")
    out = await get_news(id="a1")
    assert _query(route) == {"id": "a1"}
    assert "content: The whole article text." in out
    assert "full_text:" not in out


@respx.mock
async def test_lookup_by_url_returns_full_text_and_adds_nothing_to_the_request():
    route = _mock_one_article("crypto")
    out = await get_crypto_news(url="https://example.com/a1")
    assert _query(route) == {"url": "https://example.com/a1"}
    assert "content: The whole article text." in out
    assert "full_text:" not in out


@respx.mock
async def test_content_true_returns_full_text():
    route = _mock_one_article("market")
    out = await get_market_news(q="hello", content=True)
    assert _query(route) == {"q": "hello", "content": "1", "size": "10"}
    assert "content: The whole article text." in out
    assert "full_text:" not in out


@respx.mock
async def test_size_and_exclude_field_from_the_caller_are_kept():
    route = _mock_empty("news")
    await get_news(q="hello", size=25, exclude_field=["media", "ai"])
    assert _query(route) == {"q": "hello", "size": "25", "exclude_field": "media,ai,content"}

    # Already excluded by the caller (any letter case): not added twice.
    await get_news(q="hello", exclude_field="Content,keyword")
    assert _query(route, 1) == {"q": "hello", "size": "10", "exclude_field": "Content,keyword"}


@respx.mock
async def test_count_and_source_tools_get_no_list_defaults():
    counts = _mock_empty("count/news")
    sources = _mock_empty("sources")
    await get_news_counts(q="x")
    await get_news_sources(country="in")
    assert _query(counts) == {"q": "x"}
    assert _query(sources) == {"country": "in"}
