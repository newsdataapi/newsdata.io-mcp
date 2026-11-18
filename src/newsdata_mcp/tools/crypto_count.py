from .._mcp import READ_ONLY_TOOL, mcp
from ..formatters import format_counts
from ..http import fetch
from ..params import (
    BUCKET_SIZE,
    COIN_FILTER,
    CRYPTO_TAG_FILTER,
    FROM_DATE,
    INTERVAL,
    LANGUAGE_FILTER,
    PAGE,
    PRESENCE_FLAG,
    QUERY,
    QUERY_IN_META,
    QUERY_IN_TITLE,
    REMOVE_DUPLICATE,
    SENTIMENT,
    SORT_COUNT,
    SOURCE_PRIORITY,
    SOURCE_URL_FILTER,
    TIMEFRAME,
    TO_DATE,
)
from ..validators import check_mutex_groups


@mcp.tool(annotations=READ_ONLY_TOOL, structured_output=False)
async def get_crypto_counts(
    q: QUERY = None,
    q_in_title: QUERY_IN_TITLE = None,
    q_in_meta: QUERY_IN_META = None,
    coin: COIN_FILTER = None,
    language: LANGUAGE_FILTER = None,
    exclude_language: LANGUAGE_FILTER = None,
    source_url: SOURCE_URL_FILTER = None,
    exclude_source_url: SOURCE_URL_FILTER = None,
    source_priority: SOURCE_PRIORITY = None,
    from_date: FROM_DATE = None,
    to_date: TO_DATE = None,
    timeframe: TIMEFRAME = None,
    interval: INTERVAL = None,
    image: PRESENCE_FLAG = None,
    video: PRESENCE_FLAG = None,
    content: PRESENCE_FLAG = None,
    remove_duplicate: REMOVE_DUPLICATE = None,
    sentiment: SENTIMENT = None,
    tag: CRYPTO_TAG_FILTER = None,
    size: BUCKET_SIZE = None,
    page: PAGE = None,
    sort: SORT_COUNT = None,
) -> str:
    """
    COUNT how many CRYPTOCURRENCY NEWS articles match a search, as a total plus one count per month,
    day or hour. Returns numbers only, no articles: to read articles use `get_crypto_news`.
    COSTS 50 CREDITS PER CALL (and per page) and needs a paid plan. Call it only when the user
    asks for counts, volumes or trends, never to check whether articles exist.

    The result has `total_results` (all matching articles in the whole date range) and one
    `date_time,count` line per bucket; `date_time` is the start of the bucket in UTC.

    Time window (pass dates, or `timeframe`, or neither):
    - Neither: the last 30 days.
    - `from_date` / `to_date`: a date range in UTC, as far back as the plan's history.
    - `timeframe`: the last N hours or minutes.

    Strict rules (this tool returns Error before any API call if violated):
    - Use only ONE of `q`, `q_in_title`, or `q_in_meta`.
    - Do NOT combine `language` with `exclude_language`.
    - Do NOT combine `source_url` with `exclude_source_url`.

    Other guidance (checked by the API; its error message names the fix):
    - `coin` takes ticker symbols (`btc`, `eth`), not coin names.
    - `interval` sets the bucket length: `month`, `day` (default) or `hour`. For the total alone, read
      `total_results`; there is no `all` interval.
    - Do NOT combine `timeframe` with `from_date` or `to_date`.
    - `size` is the number of buckets per page. More buckets: pass `next_page` as `page` with the same
      other arguments (another 50 credits).

    Examples:
    - `coin="btc"` → daily counts for the last 30 days
    - `coin="btc,eth", from_date="2026-10-20", to_date="2026-10-21", interval="hour"`
    - `q="ETF", sentiment="positive", interval="month", from_date="2026-01-01"`
    """
    # Parameter names are the API's own names, so the arguments are the query
    # parameters. Keep this the first statement: `locals()` must hold only the
    # arguments.
    params = dict(locals())

    error = check_mutex_groups(params)
    if error:
        return f"Error: {error}"

    data = await fetch("count/crypto", params)
    return format_counts(data, "count/crypto")
