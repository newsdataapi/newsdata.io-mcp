import httpx
from typing import Any, Optional


from .config import (
    ARTICLE_IDS,
    CATEGORY_FILTER,
    COIN_FILTER,
    COUNTRY_FILTER,
    DATE_OR_DATETIME,
    DOMAIN_FILTER,
    DOMAIN_URL_FILTER,
    EXCLUDE_FIELD_FILTER,
    FLAG,
    LANGUAGE_FILTER,
    NEWSDATA_API_KEY,
    NEWSDATA_BASE_URL,
    ORGANIZATION_FILTER,
    PAGE,
    PRIORITY_DOMAIN,
    QUERY,
    REGION_FILTER,
    REMOVE_DUPLICATE,
    REQUEST_TIMEOUT,
    SENTIMENT,
    SIZE,
    SORT,
    SYMBOL_FILTER,
    TAG_FILTER,
    TIMEFRAME,
    TIMEZONE,
    URL,
)
from .app import mcp


async def fetch(endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
    clean = {key: value for key, value in params.items() if value is not None}
    clean["apikey"] = NEWSDATA_API_KEY

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.get(f"{NEWSDATA_BASE_URL}/{endpoint}", params=clean)
            response.raise_for_status()
            data = response.json()

        if data.get("status") == "success":
            return {'status': 'success', 'data': data}

        return {'status': 'error', 'message': f"Something went wrong. Error details: {response.text}"}

    except httpx.TimeoutException:
        return {'status': 'error', 'message': f"Request timed out after {REQUEST_TIMEOUT} seconds. The Newsdata.io API may be experiencing delays."}
    except httpx.ConnectError:
        return {'status': 'error', 'message': "Failed to connect to Newsdata.io API. Please check your internet connection."}
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        if code == 401:
            return {'status': 'error', 'message': "Unauthorized. API key is invalid."}
        elif code == 422:
            return {'status': 'error', 'message': "Invalid parameters provided. Please check your request."}
        elif code == 429:
            return {'status': 'error', 'message': "Rate limit exceeded. Try again later."}
        return {'status': 'error', 'message': f"HTTP error occurred with Newsdata.io API: {str(e)} - Response: {e.response.text}"}
    except Exception as e:
        return {'status': 'error', 'message': f"Unexpected error occurred with Newsdata.io API: {str(e)}"}


def _format_sentiment_stats(value: Any) -> Optional[str]:
    if not isinstance(value, dict) or not value:
        return None

    sentiment_stats = []
    for key, val in value.items():
        sentiment_stats.append(f"{key}={val}")
    
    return ", ".join(sentiment_stats)


def _append_field(lines: list[str], label: str, value: Any) -> None:
    if value is None:
        return

    if isinstance(value, bool):
        rendered = "true" if value else "false"
    elif isinstance(value, list):
        rendered = ", ".join([str(item) for item in value if item])
    else:
        rendered = str(value)

    lines.append(f"{label}: {rendered}")


def _format_article_item(article: dict[str, Any]) -> list[str]:
    lines = []
    _append_field(lines, "article_id", article.get("article_id"))
    _append_field(lines, "url", article.get("link"))
    _append_field(lines, "title", article.get("title"))
    _append_field(lines, "description", article.get("description"))
    _append_field(lines, "content", article.get("content"))
    _append_field(lines, "published_at", article.get("pubDate"))
    _append_field(lines, "published_timezone", article.get("pubDateTZ"))
    _append_field(lines, "fetched_at", article.get("fetched_at"))
    _append_field(lines, "source_name", article.get("source_name"))
    _append_field(lines, "source_id", article.get("source_id"))
    _append_field(lines, "source_url", article.get("source_url"))
    _append_field(lines, "source_icon", article.get("source_icon"))
    _append_field(lines, "source_priority", article.get("source_priority"))
    _append_field(lines, "language", article.get("language"))
    _append_field(lines, "countries", article.get("country"))
    _append_field(lines, "categories", article.get("category"))
    _append_field(lines, "datatype", article.get("datatype"))
    _append_field(lines, "creators", article.get("creator"))
    _append_field(lines, "keywords", article.get("keywords"))
    _append_field(lines, "coins", article.get("coin"))
    _append_field(lines, "symbols", article.get("symbol"))
    _append_field(lines, "sentiment", article.get("sentiment"))
    _append_field(lines, "sentiment_stats", _format_sentiment_stats(article.get("sentiment_stats")))
    _append_field(lines, "ai_tags", article.get("ai_tag"))
    _append_field(lines, "ai_regions", article.get("ai_region"))
    _append_field(lines, "ai_orgs", article.get("ai_org"))
    _append_field(lines, "image_url", article.get("image_url"))
    _append_field(lines, "video_url", article.get("video_url"))
    _append_field(lines, "duplicate", article.get("duplicate"))
    _append_field(lines, "summary", article.get("summary"))
    
    return lines


def _format_articles(data: dict[str, Any], endpoint_name: str) -> str:
      
    if data.get("status") != 'success':
        return f"Error: {data.get('message', 'Unknown error')}"

    data = data.get("data", {}) or {}
    articles = data.get("results") or []
    if not articles:
        return f"No {endpoint_name} articles found matching your query."
    
    total = data.get("totalResults", len(articles))
    next_page = data.get("nextPage")
    
    lines = [
        f"endpoint: {endpoint_name}",
        f"total_results: {total}",
        f"returned_results: {len(articles)}",
        f"next_page: {next_page or 'none'}",
        "",
    ]

    for index, article in enumerate(articles, 1):
        lines.append(f"Article {index}:")
        lines.extend(_format_article_item(article))
        lines.append("")

    return "\n".join(lines)


def _format_sources(data: dict[str, Any]) -> str:
    if data.get("status") != 'success':
        return f"Error: {data.get('message', 'Unknown error')}"

    data = data.get("data", {}) or {}
    sources = data.get("results") or []
    if not sources:
        return "No source found matching your query."

    lines = [
        "endpoint: sources",
        f"returned_results: {len(sources)}",
        "",
    ]

    for index, source in enumerate(sources, 1):
        lines.append(f"Source {index}:")
        _append_field(lines, "source_id", source.get("id"))
        _append_field(lines, "url", source.get("url"))
        _append_field(lines, "description", source.get("description"))
        _append_field(lines, "icon", source.get("icon"))
        _append_field(lines, "priority", source.get("priority"))
        _append_field(lines, "languages", source.get("language"))
        _append_field(lines, "countries", source.get("country"))
        _append_field(lines, "categories", source.get("category"))
        _append_field(lines, "total_article", source.get("total_article"))
        _append_field(lines, "last_fetch", source.get("last_fetch"))
        lines.append("")

    return "\n".join(lines)


@mcp.tool()
async def get_latest_news(
    q: Optional[QUERY] = None,
    q_in_title: Optional[QUERY] = None,
    q_in_meta: Optional[QUERY] = None,
    country: Optional[COUNTRY_FILTER] = None,
    exclude_country: Optional[COUNTRY_FILTER] = None,
    category: Optional[CATEGORY_FILTER] = None,
    exclude_category: Optional[CATEGORY_FILTER] = None,
    language: Optional[LANGUAGE_FILTER] = None,
    exclude_language: Optional[LANGUAGE_FILTER] = None,
    domain: Optional[DOMAIN_FILTER] = None,
    domainurl: Optional[DOMAIN_URL_FILTER] = None,
    exclude_domain: Optional[DOMAIN_FILTER] = None,
    timeframe: Optional[TIMEFRAME] = None,
    size: Optional[SIZE] = None,
    timezone: Optional[TIMEZONE] = None,
    full_content: Optional[FLAG] = None,
    image: Optional[FLAG] = None,
    video: Optional[FLAG] = None,
    priority_domain: Optional[PRIORITY_DOMAIN] = None,
    page: Optional[PAGE] = None,
    tag: Optional[TAG_FILTER] = None,
    sentiment: Optional[SENTIMENT] = None,
    region: Optional[REGION_FILTER] = None,
    excludefield: Optional[EXCLUDE_FIELD_FILTER] = None,
    removeduplicate: Optional[REMOVE_DUPLICATE] = None,
    article_id: Optional[ARTICLE_IDS] = None,
    organization: Optional[ORGANIZATION_FILTER] = None,
    url: Optional[URL] = None,
    sort: Optional[SORT] = None,
) -> str:
    """
    Use this tool to fetch REAL-TIME or RECENT news articles (last 48 hours max).
    For older articles, use `get_archive_news` instead.
    For crypto-specific news, use `get_crypto_news`.
    For stock/market news, use `get_market_news`.

    Key rules:
    - Use only ONE of `q`, `q_in_title`, or `q_in_meta` per request.
    - `q` searches full content. `q_in_title` restricts to title only. `q_in_meta` searches metadata.
    - Do NOT combine include/exclude for the same field (e.g. `country` + `exclude_country`).
    - Use `timeframe` to restrict to last N hours/minutes. Omit for latest articles with no time filter.
    - `article_id` and `url` are for fetching one specific known article, not for search.
    - `tag` filters by AI-generated topic tags (e.g. "blockchain", "climate").
    - `region` filters by city-country pairs (e.g. "delhi-india").
    - `organization` filters by company/org name mentions in articles.

    Examples:
    - `q="(bitcoin OR ethereum) AND regulation", country="us", language="en", size=10`
    - `category="technology", priority_domain="top", sort="relevancy"`
    - `q="apple earnings", organization="apple", timeframe="24"`
    - `category="sports", country="in", language="hi"`
    """
    data = await fetch(
        "latest",
        {
            "q": q,
            "qInTitle": q_in_title,
            "qInMeta": q_in_meta,
            "country": country,
            "excludecountry": exclude_country,
            "category": category,
            "excludecategory": exclude_category,
            "language": language,
            "excludelanguage": exclude_language,
            "domain": domain,
            "domainurl": domainurl,
            "excludedomain": exclude_domain,
            "timeframe": timeframe,
            "size": size,
            "timezone": timezone,
            "full_content": full_content,
            "image": image,
            "video": video,
            "prioritydomain": priority_domain,
            "page": page,
            "tag": tag,
            "sentiment": sentiment,
            "region": region,
            "excludefield": excludefield,
            "removeduplicate": removeduplicate,
            "id": article_id,
            "organization": organization,
            "url": url,
            "sort": sort,
        },
    )
    return _format_articles(data, "latest")


@mcp.tool()
async def get_archive_news(
    q: Optional[QUERY] = None,
    q_in_title: Optional[QUERY] = None,
    q_in_meta: Optional[QUERY] = None,
    country: Optional[COUNTRY_FILTER] = None,
    exclude_country: Optional[COUNTRY_FILTER] = None,
    category: Optional[CATEGORY_FILTER] = None,
    exclude_category: Optional[CATEGORY_FILTER] = None,
    language: Optional[LANGUAGE_FILTER] = None,
    exclude_language: Optional[LANGUAGE_FILTER] = None,
    domain: Optional[DOMAIN_FILTER] = None,
    domainurl: Optional[DOMAIN_URL_FILTER] = None,
    exclude_domain: Optional[DOMAIN_FILTER] = None,
    size: Optional[SIZE] = None,
    timezone: Optional[TIMEZONE] = None,
    full_content: Optional[FLAG] = None,
    image: Optional[FLAG] = None,
    video: Optional[FLAG] = None,
    priority_domain: Optional[PRIORITY_DOMAIN] = None,
    page: Optional[PAGE] = None,
    from_date: Optional[DATE_OR_DATETIME] = None,
    to_date: Optional[DATE_OR_DATETIME] = None,
    excludefield: Optional[EXCLUDE_FIELD_FILTER] = None,
    article_id: Optional[ARTICLE_IDS] = None,
    url: Optional[URL] = None,
    sort: Optional[SORT] = None,
    removeduplicate: Optional[REMOVE_DUPLICATE] = None,
) -> str:
    """
    Use this tool to search HISTORICAL news articles older than 48 hours.
    For real-time/recent news, use `get_latest_news` instead.

    Key rules:
    - Use `from_date` and/or `to_date` to define the historical date range.
    - Dates can be `YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS` for precision.
    - `timeframe` is NOT available on this endpoint — use date range instead.
    - Use only ONE of `q`, `q_in_title`, or `q_in_meta` per request.
    - Do NOT combine include/exclude for the same field.
    - `article_id` or `url` can fetch a single specific historical article.

    Examples:
    - `q="(ukraine war) AND (russia OR putin)", from_date="2024-01-01", to_date="2024-01-31", language="en"`
    - `category="politics", country="us", from_date="2024-11-01", to_date="2024-11-30"`
    - `q="IPO", from_date="2025-01-01 00:00:00", sort="relevancy"`
    """
    data = await fetch(
        "archive",
        {
            "q": q,
            "qInTitle": q_in_title,
            "qInMeta": q_in_meta,
            "country": country,
            "excludecountry": exclude_country,
            "category": category,
            "excludecategory": exclude_category,
            "language": language,
            "excludelanguage": exclude_language,
            "domain": domain,
            "domainurl": domainurl,
            "excludedomain": exclude_domain,
            "size": size,
            "timezone": timezone,
            "full_content": full_content,
            "image": image,
            "video": video,
            "prioritydomain": priority_domain,
            "page": page,
            "from_date": from_date,
            "to_date": to_date,
            "excludefield": excludefield,
            "id": article_id,
            "url": url,
            "sort": sort,
            "removeduplicate": removeduplicate,
        },
    )
    return _format_articles(data, "archive")


@mcp.tool()
async def get_crypto_news(
    q: Optional[QUERY] = None,
    q_in_title: Optional[QUERY] = None,
    q_in_meta: Optional[QUERY] = None,
    language: Optional[LANGUAGE_FILTER] = None,
    exclude_language: Optional[LANGUAGE_FILTER] = None,
    domain: Optional[DOMAIN_FILTER] = None,
    domainurl: Optional[DOMAIN_URL_FILTER] = None,
    exclude_domain: Optional[DOMAIN_FILTER] = None,
    timeframe: Optional[TIMEFRAME] = None,
    size: Optional[SIZE] = None,
    timezone: Optional[TIMEZONE] = None,
    full_content: Optional[FLAG] = None,
    image: Optional[FLAG] = None,
    video: Optional[FLAG] = None,
    priority_domain: Optional[PRIORITY_DOMAIN] = None,
    page: Optional[PAGE] = None,
    tag: Optional[TAG_FILTER] = None,
    sentiment: Optional[SENTIMENT] = None,
    coin: Optional[COIN_FILTER] = None,
    excludefield: Optional[EXCLUDE_FIELD_FILTER] = None,
    from_date: Optional[DATE_OR_DATETIME] = None,
    to_date: Optional[DATE_OR_DATETIME] = None,
    removeduplicate: Optional[REMOVE_DUPLICATE] = None,
    article_id: Optional[ARTICLE_IDS] = None,
    url: Optional[URL] = None,
    sort: Optional[SORT] = None,
) -> str:
    """
    Use this tool for CRYPTOCURRENCY news only. It searches a crypto-focused article index.
    For general financial/stock news, use `get_market_news` instead.
    For general news, use `get_latest_news`.

    Key rules:
    - Use `coin` to filter by crypto ticker symbols (e.g. `btc`, `eth,sol`).
    - Use `q` for keyword search on top of coin filter, or alone if no specific coin.
    - `coin` and `q` can be combined: `coin="btc", q="ETF"`.
    - Use only ONE of `q`, `q_in_title`, or `q_in_meta` per request.
    - `country` and `category` are NOT available on this endpoint.
    - Use `timeframe` OR `from_date`/`to_date`, not both.
    - `sentiment` is useful here: `positive` for bullish news, `negative` for bearish.

    Examples:
    - `coin="btc,eth", language="en", sentiment="positive"`
    - `q="ETF approval", coin="btc", timeframe="24"`
    - `coin="sol", from_date="2025-01-01", to_date="2025-01-31"`
    """
    data = await fetch(
        "crypto",
        {
            "q": q,
            "qInTitle": q_in_title,
            "qInMeta": q_in_meta,
            "language": language,
            "excludelanguage": exclude_language,
            "domain": domain,
            "domainurl": domainurl,
            "excludedomain": exclude_domain,
            "timeframe": timeframe,
            "size": size,
            "timezone": timezone,
            "full_content": full_content,
            "image": image,
            "video": video,
            "prioritydomain": priority_domain,
            "page": page,
            "tag": tag,
            "sentiment": sentiment,
            "coin": coin,
            "excludefield": excludefield,
            "from_date": from_date,
            "to_date": to_date,
            "removeduplicate": removeduplicate,
            "id": article_id,
            "url": url,
            "sort": sort,
        },
    )
    return _format_articles(data, "crypto")


@mcp.tool()
async def get_market_news(
    q: Optional[QUERY] = None,
    q_in_title: Optional[QUERY] = None,
    q_in_meta: Optional[QUERY] = None,
    from_date: Optional[DATE_OR_DATETIME] = None,
    to_date: Optional[DATE_OR_DATETIME] = None,
    domain: Optional[DOMAIN_FILTER] = None,
    language: Optional[LANGUAGE_FILTER] = None,
    page: Optional[PAGE] = None,
    full_content: Optional[FLAG] = None,
    image: Optional[FLAG] = None,
    video: Optional[FLAG] = None,
    timeframe: Optional[TIMEFRAME] = None,
    priority_domain: Optional[PRIORITY_DOMAIN] = None,
    timezone: Optional[TIMEZONE] = None,
    size: Optional[SIZE] = None,
    domainurl: Optional[DOMAIN_URL_FILTER] = None,
    exclude_domain: Optional[DOMAIN_FILTER] = None,
    tag: Optional[TAG_FILTER] = None,
    sentiment: Optional[SENTIMENT] = None,
    article_id: Optional[ARTICLE_IDS] = None,
    excludefield: Optional[EXCLUDE_FIELD_FILTER] = None,
    removeduplicate: Optional[REMOVE_DUPLICATE] = None,
    exclude_language: Optional[LANGUAGE_FILTER] = None,
    organization: Optional[ORGANIZATION_FILTER] = None,
    url: Optional[URL] = None,
    sort: Optional[SORT] = None,
    symbol: Optional[SYMBOL_FILTER] = None,
    country: Optional[COUNTRY_FILTER] = None,
    exclude_country: Optional[COUNTRY_FILTER] = None,
) -> str:
    """
    Use this tool for STOCK MARKET and FINANCIAL news.
    For crypto news, use `get_crypto_news` instead.
    For general news, use `get_latest_news`.

    Key rules:
    - Use `symbol` for stock/market tickers (e.g. `AAPL`, `TSLA,NVDA`).
    - Use `organization` for company name filtering (e.g. `tesla,apple`).
    - `symbol` and `organization` can be combined for precision.
    - Use only ONE of `q`, `q_in_title`, or `q_in_meta` per request.
    - `category` is NOT available on this endpoint.
    - Do NOT combine `country` with `exclude_country`.
    - Use `timeframe` OR `from_date`/`to_date`, not both.

    Examples:
    - `symbol="AAPL,MSFT", language="en", sort="relevancy"`
    - `organization="tesla,nvidia", timeframe="48", sentiment="positive"`
    - `q="earnings beat", symbol="NVDA", from_date="2025-01-01"`
    - `country="us", priority_domain="top", sort="pubdateasc"`
    """
    data = await fetch(
        "market",
        {
            "q": q,
            "qInTitle": q_in_title,
            "qInMeta": q_in_meta,
            "from_date": from_date,
            "to_date": to_date,
            "domain": domain,
            "language": language,
            "page": page,
            "full_content": full_content,
            "image": image,
            "video": video,
            "timeframe": timeframe,
            "prioritydomain": priority_domain,
            "timezone": timezone,
            "size": size,
            "domainurl": domainurl,
            "excludedomain": exclude_domain,
            "tag": tag,
            "sentiment": sentiment,
            "id": article_id,
            "excludefield": excludefield,
            "removeduplicate": removeduplicate,
            "excludelanguage": exclude_language,
            "organization": organization,
            "url": url,
            "sort": sort,
            "symbol": symbol,
            "country": country,
            "excludecountry": exclude_country,
        },
    )
    return _format_articles(data, "market")


@mcp.tool()
async def get_news_sources(
    country: Optional[COUNTRY_FILTER] = None,
    category: Optional[CATEGORY_FILTER] = None,
    language: Optional[LANGUAGE_FILTER] = None,
    priority_domain: Optional[PRIORITY_DOMAIN] = None,
    domainurl: Optional[DOMAIN_URL_FILTER] = None,
) -> str:
    """
    Use this tool to DISCOVER available news sources, not to fetch articles.
    Use this when the user wants to:
    - Find which sources are available for a country or language.
    - Get source IDs to use in `domain` filter in other tools.
    - Explore what categories a source covers.

    Key rules:
    - All parameters are optional — omit to get all available sources.
    - Returns source metadata: id, url, priority, languages, countries, categories.
    - Use the returned `source_id` values as input to `domain` in other tools.
    - No pagination — returns all matching sources in one call.

    Examples:
    - `country="in", language="hi"` → Hindi sources in India
    - `category="technology", priority_domain="top"` → top tech sources
    - `domainurl="reuters.com,bbc.com"` → check if specific domains are available
    """
    data = await fetch(
        "sources",
        {
            "country": country,
            "category": category,
            "language": language,
            "prioritydomain": priority_domain,
            "domainurl": domainurl,
        },
    )
    return _format_sources(data)
