from .._mcp import READ_ONLY_TOOL, mcp
from ..formatters import format_counts
from ..http import fetch
from ..params import (
    CATEGORY_FILTER,
    COUNTRY_FILTER,
    CREATOR_FILTER,
    DATATYPE_FILTER,
    DATE_OR_DATETIME,
    DOMAIN_FILTER,
    DOMAIN_URL_FILTER,
    FLAG,
    INTERVAL,
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
)
from ..validators import (
    check_mutex_groups,
    check_sentiment_score_requires_sentiment,
)


@mcp.tool(annotations=READ_ONLY_TOOL)
async def get_news_counts(
    from_date: DATE_OR_DATETIME,
    to_date: DATE_OR_DATETIME,
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
    full_content: FLAG | None = None,
    image: FLAG | None = None,
    video: FLAG | None = None,
    priority_domain: PRIORITY_DOMAIN | None = None,
    page: PAGE | None = None,
    size: SIZE | None = None,
    sort: SORT | None = None,
    interval: INTERVAL | None = None,
    tag: TAG_FILTER | None = None,
    sentiment: SENTIMENT | None = None,
    sentiment_score: SENTIMENT_SCORE | None = None,
    region: REGION_FILTER | None = None,
    organization: ORGANIZATION_FILTER | None = None,
    creator: CREATOR_FILTER | None = None,
    datatype: DATATYPE_FILTER | None = None,
    removeduplicate: REMOVE_DUPLICATE | None = None,
) -> str:
    """
    Use this tool to fetch AGGREGATE ARTICLE COUNTS over a date range.
    With `interval="hour"` or `"day"` returns per-bucket counts; with
    `interval="all"` (or when `interval` is omitted) returns a single
    aggregate count for the range.

    For actual article content, use `get_archive_news` (older than 48h),
    `get_latest_news` (last 48h), `get_crypto_news`, or `get_market_news`
    instead.

    Strict rules (this tool returns Error before any API call if violated):
    - Use only ONE of `q`, `q_in_title`, or `q_in_meta`.
    - Do NOT combine `country` with `exclude_country`.
    - Do NOT combine `category` with `exclude_category`.
    - Do NOT combine `language` with `exclude_language`.
    - Do NOT combine `domain`, `domainurl`, and/or `exclude_domain` with each other.
    - `sentiment_score` requires `sentiment` to also be set.

    Other guidance:
    - `from_date` and `to_date` are REQUIRED.
    - Date format: `YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS`.
    - `interval` chooses the bucket size: `hour` (per-hour buckets), `day`
      (per-day buckets), or `all` (single aggregate total, no buckets).
    - `sentiment_score` is a minimum confidence percentage (0–100) for the chosen
      `sentiment` label, e.g. `sentiment="positive", sentiment_score=50` filters
      the count to articles whose positive-sentiment score is at least 50.
    - Each returned bucket has its own count, e.g. `{"dateTime": "...", "count": N}`.

    Examples:
    - `from_date="2024-01-01", to_date="2024-01-31", q="bitcoin", interval="day"`
      → daily counts of articles mentioning bitcoin in January.
    - `from_date="2024-11-01", to_date="2024-11-30", interval="hour", country="us"`
      → hourly counts of US articles in November.
    - `from_date="2024-01-01", to_date="2024-12-31", interval="all", category="technology"`
      → a single aggregate count of tech articles for the year.
    """
    error = (
        check_mutex_groups(locals())
        or check_sentiment_score_requires_sentiment(locals())
    )
    if error:
        return f"Error: {error}"

    data = await fetch(
        "count",
        {
            "from_date": from_date,
            "to_date": to_date,
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
            "full_content": full_content,
            "image": image,
            "video": video,
            "prioritydomain": priority_domain,
            "page": page,
            "size": size,
            "sort": sort,
            "interval": interval,
            "tag": tag,
            "sentiment": sentiment,
            "sentiment_score": sentiment_score,
            "region": region,
            "organization": organization,
            "creator": creator,
            "datatype": datatype,
            "removeduplicate": removeduplicate,
        },
    )
    return format_counts(data, "count")
