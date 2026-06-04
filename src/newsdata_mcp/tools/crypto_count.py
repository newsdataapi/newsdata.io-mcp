from .._mcp import READ_ONLY_TOOL, mcp
from ..formatters import format_counts
from ..http import fetch
from ..params import (
    COIN_FILTER,
    DATE_OR_DATETIME,
    DOMAIN_FILTER,
    DOMAIN_URL_FILTER,
    FLAG,
    INTERVAL,
    LANGUAGE_FILTER,
    PAGE,
    PRIORITY_DOMAIN,
    QUERY,
    REMOVE_DUPLICATE,
    SENTIMENT,
    SIZE,
    SORT,
    TAG_FILTER,
)
from ..validators import check_mutex_groups


@mcp.tool(annotations=READ_ONLY_TOOL)
async def get_crypto_counts(
    from_date: DATE_OR_DATETIME,
    to_date: DATE_OR_DATETIME,
    q: QUERY | None = None,
    q_in_title: QUERY | None = None,
    q_in_meta: QUERY | None = None,
    language: LANGUAGE_FILTER | None = None,
    exclude_language: LANGUAGE_FILTER | None = None,
    coin: COIN_FILTER | None = None,
    domain: DOMAIN_FILTER | None = None,
    domainurl: DOMAIN_URL_FILTER | None = None,
    exclude_domain: DOMAIN_FILTER | None = None,
    full_content: FLAG | None = None,
    image: FLAG | None = None,
    video: FLAG | None = None,
    priority_domain: PRIORITY_DOMAIN | None = None,
    page: PAGE | None = None,
    sentiment: SENTIMENT | None = None,
    size: SIZE | None = None,
    sort: SORT | None = None,
    tag: TAG_FILTER | None = None,
    interval: INTERVAL | None = None,
    removeduplicate: REMOVE_DUPLICATE | None = None,
) -> str:
    """
    Use this tool to fetch AGGREGATE CRYPTO ARTICLE COUNTS over a date range.
    With `interval="hour"` or `"day"` returns per-bucket counts; with
    `interval="all"` (or when `interval` is omitted) returns a single
    aggregate count for the range.

    For actual crypto article content, use `get_crypto_news` instead.

    Strict rules (this tool returns Error before any API call if violated):
    - Use only ONE of `q`, `q_in_title`, or `q_in_meta`.
    - Do NOT combine `language` with `exclude_language`.
    - Do NOT combine `domain`, `domainurl`, and/or `exclude_domain` with each other.

    Other guidance:
    - `from_date` and `to_date` are REQUIRED.
    - Date format: `YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS`.
    - `country` and `category` are NOT available on this endpoint.
    - `interval` chooses the bucket size: `hour` (per-hour buckets), `day`
      (per-day buckets), or `all` (single aggregate total, no buckets).
    - Use `coin` to narrow to specific coin ticker(s).

    Examples:
    - `from_date="2024-01-01", to_date="2024-01-31", coin="btc", interval="day"`
      → daily BTC counts.
    - `from_date="2024-11-01", to_date="2024-11-30", interval="hour", coin=["btc", "eth"]`
      → hourly BTC/ETH counts.
    - `from_date="2024-01-01", to_date="2024-12-31", interval="all", sentiment="positive"`
      → a single aggregate count of bullish crypto articles for the year.
    """
    error = check_mutex_groups(locals())
    if error:
        return f"Error: {error}"

    data = await fetch(
        "crypto/count",
        {
            "from_date": from_date,
            "to_date": to_date,
            "q": q,
            "qintitle": q_in_title,
            "qinmeta": q_in_meta,
            "language": language,
            "excludelanguage": exclude_language,
            "coin": coin,
            "domain": domain,
            "domainurl": domainurl,
            "excludedomain": exclude_domain,
            "full_content": full_content,
            "image": image,
            "video": video,
            "prioritydomain": priority_domain,
            "page": page,
            "sentiment": sentiment,
            "size": size,
            "sort": sort,
            "tag": tag,
            "interval": interval,
            "removeduplicate": removeduplicate,
        },
    )
    return format_counts(data, "crypto/count")
