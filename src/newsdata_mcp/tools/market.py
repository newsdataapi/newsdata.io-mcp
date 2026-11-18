from .._mcp import READ_ONLY_TOOL, mcp
from ..defaults import apply_article_defaults
from ..formatters import format_articles
from ..http import fetch
from ..params import (
    ARTICLE_IDS,
    CONTENT_FLAG,
    COUNTRY_FILTER,
    CREATOR_FILTER,
    DATATYPE_FILTER,
    EXCLUDE_FIELD_FILTER,
    FROM_DATE,
    IMAGE_FLAG,
    LANGUAGE_FILTER,
    MARKET_ID_FILTER,
    ORGANIZATION_FILTER,
    PAGE,
    QUERY,
    QUERY_IN_META,
    QUERY_IN_TITLE,
    REMOVE_DUPLICATE,
    SENTIMENT,
    SENTIMENT_SCORE,
    SIZE,
    SORT,
    SOURCE_PRIORITY,
    SOURCE_URL_FILTER,
    TAG_FILTER,
    TIMEFRAME,
    TIMEZONE,
    TO_DATE,
    URL,
    VIDEO_FLAG,
)
from ..validators import (
    check_mutex_groups,
    check_sentiment_score_requires_sentiment,
)


@mcp.tool(annotations=READ_ONLY_TOOL, structured_output=False)
async def get_market_news(
    q: QUERY = None,
    q_in_title: QUERY_IN_TITLE = None,
    q_in_meta: QUERY_IN_META = None,
    market_id: MARKET_ID_FILTER = None,
    country: COUNTRY_FILTER = None,
    exclude_country: COUNTRY_FILTER = None,
    language: LANGUAGE_FILTER = None,
    exclude_language: LANGUAGE_FILTER = None,
    source_url: SOURCE_URL_FILTER = None,
    exclude_source_url: SOURCE_URL_FILTER = None,
    source_priority: SOURCE_PRIORITY = None,
    from_date: FROM_DATE = None,
    to_date: TO_DATE = None,
    timeframe: TIMEFRAME = None,
    timezone: TIMEZONE = None,
    image: IMAGE_FLAG = None,
    video: VIDEO_FLAG = None,
    content: CONTENT_FLAG = None,
    remove_duplicate: REMOVE_DUPLICATE = None,
    sentiment: SENTIMENT = None,
    sentiment_score: SENTIMENT_SCORE = None,
    tag: TAG_FILTER = None,
    organization: ORGANIZATION_FILTER = None,
    creator: CREATOR_FILTER = None,
    datatype: DATATYPE_FILTER = None,
    id: ARTICLE_IDS = None,
    url: URL = None,
    size: SIZE = None,
    page: PAGE = None,
    sort: SORT = None,
    exclude_field: EXCLUDE_FIELD_FILTER = None,
) -> str:
    """
    Search STOCK-MARKET and FINANCIAL NEWS articles. Every article is tagged with the stocks it
    mentions (`ticker` and `market_id`). Returns a list of articles, newest first: 10 per call unless
    you pass `size`, with title, description, AI summary and metadata but not the full text.
    For cryptocurrency news use `get_crypto_news`; for general news use `get_news`.

    Time window (pass dates, or `timeframe`, or neither):
    - Neither: the last 30 days.
    - `from_date` / `to_date`: a date range in UTC, as far back as the plan's history.
    - `timeframe`: the last N hours or minutes (paid plans only).

    Strict rules (this tool returns Error before any API call if violated):
    - Use only ONE of `q`, `q_in_title`, or `q_in_meta`.
    - Do NOT combine `country` with `exclude_country`.
    - Do NOT combine `language` with `exclude_language`.
    - Do NOT combine `source_url` with `exclude_source_url`.
    - `sentiment_score` requires `sentiment` to also be set.

    Other guidance (checked by the API; its error message names the fix):
    - `market_id` filters by stock listing id such as `aapl-us-vy`, not by bare ticker. To find an id,
      pass the ticker or company name: the error lists the matching ids. Or search with `q` first and
      read `market_id` from the results.
    - This tool has no `category` and no `region`.
    - Do NOT combine `timeframe` with `from_date` or `to_date`.
    - `id` and `url` fetch specific known articles, with their full text on paid plans; they can only be
      combined with `from_date` and `to_date`.
    - `sort="relevancy"` needs `q`, `q_in_title` or `q_in_meta`.
    - Send `from_date` whenever you send `to_date`: `to_date` alone starts at the plan's oldest date.
    - Full text: lists leave it out. To read it, call again with `id` set to an article's id (several ids
      allowed) or `url` set to its address, or add `content=true` to the search (paid plans).
    - `size` is the number of articles per call: 10 by default, up to 50 on paid plans.
    - More results: pass the result's `next_page` as `page` and repeat every other argument unchanged.
    - Cost: 1 credit per call; 5 on paid plans when the range starts more than 30 days ago.

    Examples:
    - `market_id="aapl-us-vy,msft-us-vy", language="en"`
    - `q="earnings", country="us", sort="relevancy"`
    - `q="nvidia", sentiment="positive", sentiment_score=80, timeframe=48`
    """
    # Parameter names are the API's own names, so the arguments are the query
    # parameters. Keep this the first statement: `locals()` must hold only the
    # arguments.
    params = dict(locals())

    error = (
        check_mutex_groups(params)
        or check_sentiment_score_requires_sentiment(params)
    )
    if error:
        return f"Error: {error}"

    full_text = apply_article_defaults(params)
    data = await fetch("market", params)
    return format_articles(data, "market", full_text)
