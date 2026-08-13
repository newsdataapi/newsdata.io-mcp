from .._mcp import READ_ONLY_TOOL, mcp
from ..formatters import format_articles
from ..http import fetch
from ..params import (
    ARTICLE_IDS,
    COUNTRY_FILTER,
    CREATOR_FILTER,
    DATATYPE_FILTER,
    DATE_OR_DATETIME,
    DOMAIN_FILTER,
    DOMAIN_URL_FILTER,
    EXCLUDE_FIELD_FILTER,
    FLAG,
    LANGUAGE_FILTER,
    MARKET_ID_FILTER,
    ORGANIZATION_FILTER,
    PAGE,
    PRIORITY_DOMAIN,
    QUERY,
    REMOVE_DUPLICATE,
    SENTIMENT,
    SENTIMENT_SCORE,
    SIZE,
    SORT,
    TAG_FILTER,
    TIMEFRAME,
    TIMEZONE,
    URL,
)
from ..validators import (
    check_mutex_groups,
    check_sentiment_score_requires_sentiment,
)


@mcp.tool(annotations=READ_ONLY_TOOL)
async def get_market_news(
    q: QUERY | None = None,
    q_in_title: QUERY | None = None,
    q_in_meta: QUERY | None = None,
    from_date: DATE_OR_DATETIME | None = None,
    to_date: DATE_OR_DATETIME | None = None,
    domain: DOMAIN_FILTER | None = None,
    language: LANGUAGE_FILTER | None = None,
    page: PAGE | None = None,
    full_content: FLAG | None = None,
    image: FLAG | None = None,
    video: FLAG | None = None,
    timeframe: TIMEFRAME | None = None,
    priority_domain: PRIORITY_DOMAIN | None = None,
    timezone: TIMEZONE | None = None,
    size: SIZE | None = None,
    domainurl: DOMAIN_URL_FILTER | None = None,
    exclude_domain: DOMAIN_FILTER | None = None,
    tag: TAG_FILTER | None = None,
    sentiment: SENTIMENT | None = None,
    article_id: ARTICLE_IDS | None = None,
    excludefield: EXCLUDE_FIELD_FILTER | None = None,
    removeduplicate: REMOVE_DUPLICATE | None = None,
    exclude_language: LANGUAGE_FILTER | None = None,
    organization: ORGANIZATION_FILTER | None = None,
    url: URL | None = None,
    sort: SORT | None = None,
    market_id: MARKET_ID_FILTER | None = None,
    country: COUNTRY_FILTER | None = None,
    exclude_country: COUNTRY_FILTER | None = None,
    creator: CREATOR_FILTER | None = None,
    datatype: DATATYPE_FILTER | None = None,
    sentiment_score: SENTIMENT_SCORE | None = None,
) -> str:
    """
    Use this tool for STOCK MARKET and FINANCIAL news.
    For crypto news, use `get_crypto_news` instead.
    For general news, use `get_latest_news`.

    Strict rules (this tool returns Error before any API call if violated):
    - Use only ONE of `q`, `q_in_title`, or `q_in_meta`.
    - Do NOT combine `country` with `exclude_country`.
    - Do NOT combine `language` with `exclude_language`.
    - Do NOT combine `domain`, `domainurl`, and/or `exclude_domain` with each other.
    - `sentiment_score` requires `sentiment` to also be set.

    Other guidance:
    - Use `market_id` for stock/market tickers (e.g. `AAPL`, `TSLA,NVDA`).
    - Use `organization` for company name filtering (e.g. `tesla,apple`).
    - `market_id` and `organization` can be combined for precision.
    - `category` is NOT available on this endpoint.
    - Use `timeframe` OR `from_date`/`to_date`, not both.
    - `creator` filters by author/byline name(s).
    - `datatype` filters by content type (e.g. "article").
    - `sentiment_score` is a minimum confidence percentage (0–100) for the chosen
      `sentiment` label, e.g. `sentiment="positive", sentiment_score=80` keeps
      only articles whose positive-sentiment score is at least 80.

    Examples:
    - `market_id="AAPL,MSFT", language="en", sort="relevancy"`
    - `organization="tesla,nvidia", timeframe="48", sentiment="positive"`
    - `q="earnings beat", market_id="NVDA", from_date="2025-01-01"`
    - `country="us", priority_domain="top", sort="pubdateasc"`
    - `sentiment="positive", sentiment_score=80, market_id="NVDA"`
    """
    error = (
        check_mutex_groups(locals())
        or check_sentiment_score_requires_sentiment(locals())
    )
    if error:
        return f"Error: {error}"

    data = await fetch(
        "market",
        {
            "q": q,
            "qintitle": q_in_title,
            "qinmeta": q_in_meta,
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
            "market_id": market_id,
            "country": country,
            "excludecountry": exclude_country,
            "creator": creator,
            "datatype": datatype,
            "sentiment_score": sentiment_score,
        },
    )
    return format_articles(data, "market")
