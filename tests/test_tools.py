"""End-to-end tests that exercise the @mcp.tool() functions with a
mocked NewsData API. These validate the snake-case → camelCase param
mapping and that the formatter is correctly wired per endpoint.
"""
import httpx
import respx

from newsdata_mcp.tools.archive import get_archive_news
from newsdata_mcp.tools.count import get_news_counts
from newsdata_mcp.tools.crypto import get_crypto_news
from newsdata_mcp.tools.crypto_count import get_crypto_counts
from newsdata_mcp.tools.latest import get_latest_news
from newsdata_mcp.tools.market import get_market_news
from newsdata_mcp.tools.market_count import get_market_counts
from newsdata_mcp.tools.sources import get_news_sources


@respx.mock
async def test_latest_news_renders_text():
    respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "totalResults": 1,
                "results": [
                    {"article_id": "a1", "title": "Latest title", "link": "https://x"}
                ],
            },
        )
    )
    out = await get_latest_news(q="bitcoin", country="us", size=10)
    assert "endpoint: latest" in out
    assert "title: Latest title" in out
    assert "url: https://x" in out


@respx.mock
async def test_latest_news_maps_snake_case_to_wire_names():
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await get_latest_news(
        q_in_title="apple",
        exclude_country="cn",
        priority_domain="top",
        article_id="aabbccddeeff00112233445566778899",
    )
    qs = dict(route.calls[0].request.url.params)
    # snake_case in Python → NewsData's lowercase wire names (the API is
    # case-insensitive but the canonical form across our SDKs is lowercase).
    assert qs["qintitle"] == "apple"
    assert qs["excludecountry"] == "cn"
    assert qs["prioritydomain"] == "top"
    assert qs["id"] == "aabbccddeeff00112233445566778899"
    # And no leak of the Python kwarg names.
    assert "q_in_title" not in qs
    assert "exclude_country" not in qs


@respx.mock
async def test_archive_news_uses_archive_endpoint():
    route = respx.get("https://newsdata.io/api/1/archive").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    out = await get_archive_news(q="war", from_date="2024-01-01", to_date="2024-01-31")
    assert route.called
    qs = dict(route.calls[0].request.url.params)
    assert qs["from_date"] == "2024-01-01"
    assert qs["to_date"] == "2024-01-31"
    # Empty result on the archive endpoint says "archive" not "latest".
    assert "archive" in out


@respx.mock
async def test_crypto_news_uses_crypto_endpoint_and_passes_coin():
    route = respx.get("https://newsdata.io/api/1/crypto").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await get_crypto_news(coin="btc,eth", sentiment="positive")
    qs = dict(route.calls[0].request.url.params)
    assert qs["coin"] == "btc,eth"
    assert qs["sentiment"] == "positive"


@respx.mock
async def test_market_news_uses_market_endpoint_and_passes_symbol():
    route = respx.get("https://newsdata.io/api/1/market").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await get_market_news(symbol="AAPL,NVDA", country="us")
    qs = dict(route.calls[0].request.url.params)
    assert qs["symbol"] == "AAPL,NVDA"
    assert qs["country"] == "us"


@respx.mock
async def test_news_sources_renders_source_metadata():
    """Regression: with the original bug this returned 'No sources found'
    even on a successful response. After the fix the body is rendered."""
    respx.get("https://newsdata.io/api/1/sources").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "results": [
                    {
                        "id": "bbc",
                        "name": "BBC",
                        "url": "https://bbc.com",
                        "language": ["english"],
                    }
                ],
            },
        )
    )
    out = await get_news_sources(country="gb")
    assert "[1] BBC" in out
    assert "source_id: bbc" in out
    assert out != "No sources found matching your filters."


@respx.mock
async def test_news_sources_surfaces_api_error():
    respx.get("https://newsdata.io/api/1/sources").mock(
        return_value=httpx.Response(401, text="bad")
    )
    out = await get_news_sources()
    # Step 5: error envelope now carries status_code; formatter renders
    # `Error (HTTP 401): ...` instead of plain `Error: ...`.
    assert out.startswith("Error (HTTP 401):")
    assert "Unauthorized" in out


# ---------------------------------------------------------------------------
# Mutex validation runs at the tool boundary, *before* fetch() is called.
# These tests use respx.mock without registering any routes — if a tool
# attempts a network call despite a mutex violation, respx fails the test.
# ---------------------------------------------------------------------------


@respx.mock(assert_all_called=False)
async def test_latest_mutex_q_and_q_in_title_short_circuits():
    out = await get_latest_news(q="bitcoin", q_in_title="ethereum")
    assert out.startswith("Error:")
    assert "'q'" in out
    assert "'q_in_title'" in out
    assert "mutually exclusive" in out
    # No network call was made.
    assert len(respx.calls) == 0


@respx.mock(assert_all_called=False)
async def test_latest_mutex_country_and_exclude_country_short_circuits():
    out = await get_latest_news(country="us", exclude_country="gb")
    assert out.startswith("Error:")
    assert "'country'" in out
    assert "'exclude_country'" in out
    assert len(respx.calls) == 0


@respx.mock(assert_all_called=False)
async def test_archive_mutex_three_way_domain_short_circuits():
    out = await get_archive_news(
        domain="bbc",
        domainurl="bbc.com",
        exclude_domain="reuters",
    )
    assert out.startswith("Error:")
    assert "'domain'" in out
    assert "'domainurl'" in out
    assert "'exclude_domain'" in out
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
    respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    out = await get_latest_news(
        q="bitcoin",
        country="us",
        category="technology",
        language="en",
        domain="reuters.com",
    )
    assert "endpoint: latest" in out or "No latest articles" in out


# ---------------------------------------------------------------------------
# Step 2 — tool-level acceptance of LLM-natural input forms.
# Schema widening only matters if a tool actually accepts and forwards
# the new shapes. These tests verify each tool entry-point.
# ---------------------------------------------------------------------------


@respx.mock
async def test_latest_news_accepts_bool_for_flags():
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await get_latest_news(image=True, video=False, full_content=True)
    qs = dict(route.calls[0].request.url.params)
    assert qs["image"] == "1"
    assert qs["video"] == "0"
    assert qs["full_content"] == "1"


@respx.mock
async def test_latest_news_accepts_bool_for_removeduplicate():
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await get_latest_news(removeduplicate=True)
    qs = dict(route.calls[0].request.url.params)
    assert qs["removeduplicate"] == "1"


@respx.mock
async def test_latest_news_removeduplicate_false_dropped():
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await get_latest_news(removeduplicate=False)
    qs = dict(route.calls[0].request.url.params)
    assert "removeduplicate" not in qs


@respx.mock
async def test_latest_news_accepts_list_for_country():
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await get_latest_news(country=["us", "gb", "in"])
    qs = dict(route.calls[0].request.url.params)
    assert qs["country"] == "us,gb,in"


@respx.mock
async def test_latest_news_accepts_list_for_category():
    """CATEGORY_FILTER uses `list[CATEGORY_CODE]` so each item is
    validated against the enum."""
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await get_latest_news(category=["technology", "science"])
    qs = dict(route.calls[0].request.url.params)
    assert qs["category"] == "technology,science"


@respx.mock
async def test_latest_news_accepts_int_for_timeframe():
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await get_latest_news(timeframe=24)
    qs = dict(route.calls[0].request.url.params)
    assert qs["timeframe"] == "24"


@respx.mock
async def test_latest_news_accepts_string_for_timeframe_minutes():
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await get_latest_news(timeframe="90m")
    qs = dict(route.calls[0].request.url.params)
    assert qs["timeframe"] == "90m"


@respx.mock
async def test_crypto_news_accepts_list_for_coin():
    route = respx.get("https://newsdata.io/api/1/crypto").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await get_crypto_news(coin=["btc", "eth", "sol"])
    qs = dict(route.calls[0].request.url.params)
    assert qs["coin"] == "btc,eth,sol"


@respx.mock
async def test_market_news_accepts_list_for_symbol():
    route = respx.get("https://newsdata.io/api/1/market").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await get_market_news(symbol=["AAPL", "MSFT"])
    qs = dict(route.calls[0].request.url.params)
    assert qs["symbol"] == "AAPL,MSFT"


@respx.mock
async def test_news_sources_accepts_list_for_country():
    route = respx.get("https://newsdata.io/api/1/sources").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await get_news_sources(country=["us", "gb"])
    qs = dict(route.calls[0].request.url.params)
    assert qs["country"] == "us,gb"


@respx.mock
async def test_latest_news_mixed_realistic_llm_call():
    """An LLM-style call: bools, lists, ints, all together."""
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await get_latest_news(
        q="bitcoin OR ethereum",
        country=["us", "gb"],
        language=["en"],
        category=["technology", "business"],
        image=True,
        full_content=True,
        size=10,
        timeframe=24,
        removeduplicate=True,
        priority_domain="top",
    )
    qs = dict(route.calls[0].request.url.params)
    assert qs["q"] == "bitcoin OR ethereum"
    assert qs["country"] == "us,gb"
    assert qs["language"] == "en"
    assert qs["category"] == "technology,business"
    assert qs["image"] == "1"
    assert qs["full_content"] == "1"
    assert qs["size"] == "10"
    assert qs["timeframe"] == "24"
    assert qs["removeduplicate"] == "1"
    assert qs["prioritydomain"] == "top"


# ---------------------------------------------------------------------------
# Step 3 — creator, datatype, sentiment_score, and the sentiment_score
# requires sentiment validator. Wired across latest, archive, market.
# ---------------------------------------------------------------------------


@respx.mock
async def test_latest_news_accepts_creator_string_and_list():
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await get_latest_news(creator="jane doe")
    assert dict(route.calls[0].request.url.params)["creator"] == "jane doe"

    await get_latest_news(creator=["john smith", "jane doe"])
    assert dict(route.calls[1].request.url.params)["creator"] == "john smith,jane doe"


@respx.mock
async def test_latest_news_accepts_datatype():
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await get_latest_news(datatype=["article", "video"])
    qs = dict(route.calls[0].request.url.params)
    assert qs["datatype"] == "article,video"


@respx.mock
async def test_latest_news_sentiment_score_with_sentiment_passes():
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await get_latest_news(sentiment="positive", sentiment_score=70)
    qs = dict(route.calls[0].request.url.params)
    assert qs["sentiment"] == "positive"
    assert qs["sentiment_score"] == "70"


@respx.mock(assert_all_called=False)
async def test_latest_news_sentiment_score_without_sentiment_short_circuits():
    out = await get_latest_news(sentiment_score=50)
    assert out.startswith("Error:")
    assert "'sentiment_score'" in out
    assert "'sentiment'" in out
    # And the message tells the LLM what concrete fix to apply.
    assert "'positive'" in out
    assert len(respx.calls) == 0


@respx.mock(assert_all_called=False)
async def test_archive_news_sentiment_score_without_sentiment_short_circuits():
    out = await get_archive_news(sentiment_score=50, from_date="2024-01-01")
    assert out.startswith("Error:")
    assert "'sentiment_score'" in out
    assert "'sentiment'" in out
    assert len(respx.calls) == 0


@respx.mock
async def test_archive_news_sentiment_pair_passes():
    """archive previously lacked `sentiment` entirely; verify it now
    accepts and forwards both halves of the pair."""
    route = respx.get("https://newsdata.io/api/1/archive").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await get_archive_news(
        sentiment="negative",
        sentiment_score=60,
        from_date="2024-01-01",
    )
    qs = dict(route.calls[0].request.url.params)
    assert qs["sentiment"] == "negative"
    assert qs["sentiment_score"] == "60"


@respx.mock
async def test_archive_news_accepts_creator_and_datatype():
    route = respx.get("https://newsdata.io/api/1/archive").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await get_archive_news(
        creator=["ana lopez", "bao chen"],
        datatype="article",
        from_date="2024-01-01",
    )
    qs = dict(route.calls[0].request.url.params)
    assert qs["creator"] == "ana lopez,bao chen"
    assert qs["datatype"] == "article"


@respx.mock
async def test_archive_news_accepts_tag_region_organization():
    """Regression: these params existed in the SDK and on the other
    article tools but were missing from `get_archive_news`."""
    route = respx.get("https://newsdata.io/api/1/archive").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await get_archive_news(
        from_date="2024-01-01",
        tag=["climate", "blockchain"],
        region="new york-united states of america",
        organization=["tesla", "apple"],
    )
    qs = dict(route.calls[0].request.url.params)
    assert qs["tag"] == "climate,blockchain"
    assert qs["region"] == "new york-united states of america"
    assert qs["organization"] == "tesla,apple"


@respx.mock(assert_all_called=False)
async def test_market_news_sentiment_score_without_sentiment_short_circuits():
    out = await get_market_news(sentiment_score=80, symbol="NVDA")
    assert out.startswith("Error:")
    assert "'sentiment_score'" in out
    assert "'sentiment'" in out
    assert len(respx.calls) == 0


@respx.mock
async def test_market_news_sentiment_pair_passes():
    route = respx.get("https://newsdata.io/api/1/market").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await get_market_news(
        sentiment="positive",
        sentiment_score=80,
        symbol="NVDA",
    )
    qs = dict(route.calls[0].request.url.params)
    assert qs["sentiment"] == "positive"
    assert qs["sentiment_score"] == "80"
    assert qs["symbol"] == "NVDA"


@respx.mock
async def test_market_news_accepts_creator_and_datatype():
    route = respx.get("https://newsdata.io/api/1/market").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await get_market_news(
        creator="bao chen",
        datatype=["article", "video"],
    )
    qs = dict(route.calls[0].request.url.params)
    assert qs["creator"] == "bao chen"
    assert qs["datatype"] == "article,video"


@respx.mock
async def test_sentiment_alone_still_works_without_score():
    """Regression: the validator must not block `sentiment` alone."""
    route = respx.get("https://newsdata.io/api/1/latest").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    out = await get_latest_news(sentiment="positive", q="bitcoin")
    assert not out.startswith("Error:")
    qs = dict(route.calls[0].request.url.params)
    assert qs["sentiment"] == "positive"
    assert "sentiment_score" not in qs


# ---------------------------------------------------------------------------
# Step 4 — count endpoints. Each tool hits its own URL, accepts date range,
# and renders buckets via format_counts.
# ---------------------------------------------------------------------------


@respx.mock
async def test_news_counts_hits_count_endpoint():
    route = respx.get("https://newsdata.io/api/1/count").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "results": [
                    {"dateTime": "2024-01-01 00:00:00", "count": 100},
                    {"dateTime": "2024-01-02 00:00:00", "count": 150},
                ],
            },
        )
    )
    out = await get_news_counts(from_date="2024-01-01", to_date="2024-01-02", q="bitcoin")
    assert route.called
    qs = dict(route.calls[0].request.url.params)
    assert qs["from_date"] == "2024-01-01"
    assert qs["to_date"] == "2024-01-02"
    assert qs["q"] == "bitcoin"
    assert "endpoint: count" in out
    assert "buckets: 2" in out
    assert "dateTime: 2024-01-01 00:00:00" in out


@respx.mock
async def test_news_counts_interval_param_sent():
    route = respx.get("https://newsdata.io/api/1/count").mock(
        return_value=httpx.Response(200, json={"status": "success", "results": []})
    )
    await get_news_counts(
        from_date="2024-01-01",
        to_date="2024-01-31",
        interval="hour",
    )
    qs = dict(route.calls[0].request.url.params)
    assert qs["interval"] == "hour"


@respx.mock(assert_all_called=False)
async def test_news_counts_mutex_short_circuits():
    out = await get_news_counts(
        from_date="2024-01-01",
        to_date="2024-01-31",
        q="x",
        q_in_title="y",
    )
    assert out.startswith("Error:")
    assert "'q'" in out
    assert "'q_in_title'" in out
    assert len(respx.calls) == 0


@respx.mock(assert_all_called=False)
async def test_news_counts_sentiment_score_without_sentiment_short_circuits():
    out = await get_news_counts(
        from_date="2024-01-01",
        to_date="2024-01-31",
        sentiment_score=50,
    )
    assert out.startswith("Error:")
    assert "'sentiment_score'" in out
    assert "'sentiment'" in out
    assert len(respx.calls) == 0


@respx.mock
async def test_crypto_counts_hits_crypto_count_endpoint():
    route = respx.get("https://newsdata.io/api/1/crypto/count").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "results": [{"dateTime": "2024-01-01 00:00:00", "count": 42}],
            },
        )
    )
    out = await get_crypto_counts(
        from_date="2024-01-01",
        to_date="2024-01-31",
        coin=["btc", "eth"],
    )
    assert route.called
    qs = dict(route.calls[0].request.url.params)
    assert qs["coin"] == "btc,eth"
    assert "endpoint: crypto/count" in out


@respx.mock(assert_all_called=False)
async def test_crypto_counts_mutex_language_short_circuits():
    out = await get_crypto_counts(
        from_date="2024-01-01",
        to_date="2024-01-31",
        language="en",
        exclude_language="fr",
    )
    assert out.startswith("Error:")
    assert "'language'" in out
    assert "'exclude_language'" in out
    assert len(respx.calls) == 0


@respx.mock
async def test_market_counts_hits_market_count_endpoint():
    route = respx.get("https://newsdata.io/api/1/market/count").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "results": [{"dateTime": "2024-01-01 00:00:00", "count": 12}],
            },
        )
    )
    out = await get_market_counts(
        from_date="2024-01-01",
        to_date="2024-01-31",
        symbol="AAPL",
        interval="day",
    )
    assert route.called
    qs = dict(route.calls[0].request.url.params)
    assert qs["symbol"] == "AAPL"
    assert qs["interval"] == "day"
    assert "endpoint: market/count" in out


@respx.mock(assert_all_called=False)
async def test_market_counts_sentiment_score_without_sentiment_short_circuits():
    out = await get_market_counts(
        from_date="2024-01-01",
        to_date="2024-01-31",
        sentiment_score=80,
    )
    assert out.startswith("Error:")
    assert len(respx.calls) == 0


@respx.mock
async def test_news_counts_renders_aggregate_dict_results():
    """When NewsData returns `results` as a dict (final page of pagination),
    format_counts renders an aggregate block instead of bucket rows."""
    respx.get("https://newsdata.io/api/1/count").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "totalResults": 31,
                "results": {"grand_total": 31000, "avg_per_day": 1000},
            },
        )
    )
    out = await get_news_counts(from_date="2024-01-01", to_date="2024-01-31")
    assert "aggregate:" in out
    assert "grand_total: 31000" in out
    assert "buckets:" not in out


async def test_count_endpoints_require_dates():
    """from_date and to_date are required-by-signature on every count tool.
    Calling without them should raise TypeError before any HTTP layer
    sees the call."""
    import pytest
    with pytest.raises(TypeError):
        await get_news_counts()
    with pytest.raises(TypeError):
        await get_crypto_counts()
    with pytest.raises(TypeError):
        await get_market_counts()
