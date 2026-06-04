from .._mcp import READ_ONLY_TOOL, mcp
from ..formatters import format_articles
from ..http import fetch
from ..params import (
    ARTICLE_IDS,
    CATEGORY_FILTER,
    COUNTRY_FILTER,
    CREATOR_FILTER,
    DATATYPE_FILTER,
    DOMAIN_FILTER,
    DOMAIN_URL_FILTER,
    EXCLUDE_FIELD_FILTER,
    FLAG,
    LANGUAGE_FILTER,
    ORGANIZATION_FILTER,
    PAGE,
    PRIORITY_DOMAIN,
    QUERY,
    REGION_FILTER,
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
async def get_latest_news(
    q: QUERY | None = None,
    q_in_title: QUERY | None = None,
    q_in_meta: QUERY | None = None,
    country: COUNTRY_FILTER | None = None,
    exclude_country: COUNTRY_FILTER | None = None,
    category: CATEGORY_FILTER | None = None,
    exclude_category: CATEGORY_FILTER | None = None,
    language: LANGUAGE_FILTER | None = None,
    exclude_language: LANGUAGE_FILTER | None = None,
    domain: DOMAIN_FILTER | None = None,
    domainurl: DOMAIN_URL_FILTER | None = None,
    exclude_domain: DOMAIN_FILTER | None = None,
    timeframe: TIMEFRAME | None = None,
    size: SIZE | None = None,
    timezone: TIMEZONE | None = None,
    full_content: FLAG | None = None,
    image: FLAG | None = None,
    video: FLAG | None = None,
    priority_domain: PRIORITY_DOMAIN | None = None,
    page: PAGE | None = None,
    tag: TAG_FILTER | None = None,
    sentiment: SENTIMENT | None = None,
    region: REGION_FILTER | None = None,
    excludefield: EXCLUDE_FIELD_FILTER | None = None,
    removeduplicate: REMOVE_DUPLICATE | None = None,
    article_id: ARTICLE_IDS | None = None,
    organization: ORGANIZATION_FILTER | None = None,
    url: URL | None = None,
    sort: SORT | None = None,
    creator: CREATOR_FILTER | None = None,
    datatype: DATATYPE_FILTER | None = None,
    sentiment_score: SENTIMENT_SCORE | None = None,
) -> str:
    """
    Use this tool to fetch REAL-TIME or RECENT news articles (last 48 hours max).
    For older articles, use `get_archive_news` instead.
    For crypto-specific news, use `get_crypto_news`.
    For stock/market news, use `get_market_news`.

    Strict rules (this tool returns Error before any API call if violated):
    - Use only ONE of `q`, `q_in_title`, or `q_in_meta`.
    - Do NOT combine `country` with `exclude_country`.
    - Do NOT combine `category` with `exclude_category`.
    - Do NOT combine `language` with `exclude_language`.
    - Do NOT combine `domain`, `domainurl`, and/or `exclude_domain` with each other.
    - `sentiment_score` requires `sentiment` to also be set.

    Other guidance:
    - `q` searches full content. `q_in_title` restricts to title only. `q_in_meta` searches metadata.
    - Use `timeframe` to restrict to last N hours/minutes. Omit for latest articles with no time filter.
    - `article_id` and `url` are for fetching one specific known article, not for search.
    - `tag` filters by AI-generated topic tags (e.g. "blockchain", "climate").
    - `region` filters by city-country pairs (e.g. "delhi-india").
    - `organization` filters by company/org name mentions in articles.
    - `creator` filters by author/byline name(s).
    - `datatype` filters by content type (e.g. "article").
    - `sentiment_score` is a minimum confidence percentage (0–100) for the chosen
      `sentiment` label, e.g. `sentiment="positive", sentiment_score=50` keeps
      only articles whose positive-sentiment score is at least 50.

    Examples:
    - `q="(bitcoin OR ethereum) AND regulation", country="us", language="en", size=10`
    - `category="technology", priority_domain="top", sort="relevancy"`
    - `q="apple earnings", organization="apple", timeframe="24"`
    - `category="sports", country="in", language="hi"`
    - `sentiment="positive", sentiment_score=70, q="elections"`
    """
    error = (
        check_mutex_groups(locals())
        or check_sentiment_score_requires_sentiment(locals())
    )
    if error:
        return f"Error: {error}"

    data = await fetch(
        "latest",
        {
            "q": q,
            "qintitle": q_in_title,
            "qinmeta": q_in_meta,
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
            "creator": creator,
            "datatype": datatype,
            "sentiment_score": sentiment_score,
        },
    )
    return format_articles(data, "latest")
