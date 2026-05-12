from .._mcp import READ_ONLY_TOOL, mcp
from ..formatters import format_articles
from ..http import fetch
from ..params import (
    ARTICLE_IDS,
    COIN_FILTER,
    DATE_OR_DATETIME,
    DOMAIN_FILTER,
    DOMAIN_URL_FILTER,
    EXCLUDE_FIELD_FILTER,
    FLAG,
    LANGUAGE_FILTER,
    PAGE,
    PRIORITY_DOMAIN,
    QUERY,
    REMOVE_DUPLICATE,
    SENTIMENT,
    SIZE,
    SORT,
    TAG_FILTER,
    TIMEFRAME,
    TIMEZONE,
    URL,
)
from ..validators import check_mutex_groups


@mcp.tool(annotations=READ_ONLY_TOOL)
async def get_crypto_news(
    q: QUERY | None = None,
    q_in_title: QUERY | None = None,
    q_in_meta: QUERY | None = None,
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
    coin: COIN_FILTER | None = None,
    excludefield: EXCLUDE_FIELD_FILTER | None = None,
    from_date: DATE_OR_DATETIME | None = None,
    to_date: DATE_OR_DATETIME | None = None,
    removeduplicate: REMOVE_DUPLICATE | None = None,
    article_id: ARTICLE_IDS | None = None,
    url: URL | None = None,
    sort: SORT | None = None,
) -> str:
    """
    Use this tool for CRYPTOCURRENCY news only. It searches a crypto-focused article index.
    For general financial/stock news, use `get_market_news` instead.
    For general news, use `get_latest_news`.

    Strict rules (this tool returns Error before any API call if violated):
    - Use only ONE of `q`, `q_in_title`, or `q_in_meta`.
    - Do NOT combine `language` with `exclude_language`.
    - Do NOT combine `domain`, `domainurl`, and/or `exclude_domain` with each other.

    Other guidance:
    - Use `coin` to filter by crypto ticker symbols (e.g. `btc`, `eth,sol`).
    - Use `q` for keyword search on top of coin filter, or alone if no specific coin.
    - `coin` and `q` can be combined: `coin="btc", q="ETF"`.
    - `country` and `category` are NOT available on this endpoint.
    - Use `timeframe` OR `from_date`/`to_date`, not both.
    - `sentiment` is useful here: `positive` for bullish news, `negative` for bearish.

    Examples:
    - `coin="btc,eth", language="en", sentiment="positive"`
    - `q="ETF approval", coin="btc", timeframe="24"`
    - `coin="sol", from_date="2025-01-01", to_date="2025-01-31"`
    """
    error = check_mutex_groups(locals())
    if error:
        return f"Error: {error}"

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
    return format_articles(data, "crypto")
