from .._mcp import READ_ONLY_TOOL, mcp
from ..formatters import format_articles
from ..http import fetch
from ..params import (
    ARTICLE_IDS,
    CATEGORY_FILTER,
    COUNTRY_FILTER,
    CREATOR_FILTER,
    DATATYPE_FILTER,
    DATE_OR_DATETIME,
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
    TIMEZONE,
    URL,
)
from ..validators import (
    check_mutex_groups,
    check_sentiment_score_requires_sentiment,
)


@mcp.tool(annotations=READ_ONLY_TOOL)
async def get_archive_news(
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
    size: SIZE | None = None,
    timezone: TIMEZONE | None = None,
    full_content: FLAG | None = None,
    image: FLAG | None = None,
    video: FLAG | None = None,
    priority_domain: PRIORITY_DOMAIN | None = None,
    page: PAGE | None = None,
    from_date: DATE_OR_DATETIME | None = None,
    to_date: DATE_OR_DATETIME | None = None,
    excludefield: EXCLUDE_FIELD_FILTER | None = None,
    article_id: ARTICLE_IDS | None = None,
    url: URL | None = None,
    sort: SORT | None = None,
    removeduplicate: REMOVE_DUPLICATE | None = None,
    sentiment: SENTIMENT | None = None,
    creator: CREATOR_FILTER | None = None,
    datatype: DATATYPE_FILTER | None = None,
    sentiment_score: SENTIMENT_SCORE | None = None,
    tag: TAG_FILTER | None = None,
    region: REGION_FILTER | None = None,
    organization: ORGANIZATION_FILTER | None = None,
) -> str:
    """
    Use this tool to search HISTORICAL news articles older than 48 hours.
    For real-time/recent news, use `get_latest_news` instead.

    Strict rules (this tool returns Error before any API call if violated):
    - Use only ONE of `q`, `q_in_title`, or `q_in_meta`.
    - Do NOT combine `country` with `exclude_country`.
    - Do NOT combine `category` with `exclude_category`.
    - Do NOT combine `language` with `exclude_language`.
    - Do NOT combine `domain`, `domainurl`, and/or `exclude_domain` with each other.
    - `sentiment_score` requires `sentiment` to also be set.

    Other guidance:
    - Use `from_date` and/or `to_date` to define the historical date range.
    - Dates can be `YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS` for precision.
    - `timeframe` is NOT available on this endpoint — use date range instead.
    - `article_id` or `url` can fetch a single specific historical article.
    - `creator` filters by author/byline name(s).
    - `datatype` filters by content type (e.g. "article").
    - `sentiment_score` is a minimum confidence percentage (0–100) for the chosen
      `sentiment` label, e.g. `sentiment="negative", sentiment_score=70` keeps
      only articles whose negative-sentiment score is at least 70.
    - `tag` filters by AI-generated topic tags (e.g. "blockchain", "climate").
    - `region` filters by city-country pairs (e.g. "delhi-india").
    - `organization` filters by company/org name mentions in articles.

    Examples:
    - `q="(ukraine war) AND (russia OR putin)", from_date="2024-01-01", to_date="2024-01-31", language="en"`
    - `category="politics", country="us", from_date="2024-11-01", to_date="2024-11-30"`
    - `q="IPO", from_date="2025-01-01 00:00:00", sort="relevancy"`
    - `sentiment="negative", sentiment_score=70, from_date="2024-01-01"`
    """
    error = (
        check_mutex_groups(locals())
        or check_sentiment_score_requires_sentiment(locals())
    )
    if error:
        return f"Error: {error}"

    data = await fetch(
        "archive",
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
            "sentiment": sentiment,
            "creator": creator,
            "datatype": datatype,
            "sentiment_score": sentiment_score,
            "tag": tag,
            "region": region,
            "organization": organization,
        },
    )
    return format_articles(data, "archive")
