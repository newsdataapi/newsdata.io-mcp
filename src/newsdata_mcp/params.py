"""Pydantic `Annotated` parameter types reused across the MCP tools.

These aliases bundle a regex/length/range plus a `description` and
`examples` so the resulting JSON Schema sent to MCP clients carries those
hints. The aliases live in one place; tool signatures import the ones
they need.
"""
from typing import Annotated, Literal, get_args

from pydantic import Field


def _csv_pattern(*values: str) -> str:
    choices = "|".join(values)
    return rf"^(?:{choices})(?:,(?:{choices}))*$"


# The 18 category codes NewsData accepts, as returned by its own filter API.
# Keep this in sync: the codes below become a regex on CATEGORY_FILTER, so a
# missing one is rejected client-side and never reaches the API.
CATEGORY_CODE = Literal[
    "breaking",
    "business",
    "crime",
    "domestic",
    "education",
    "entertainment",
    "environment",
    "food",
    "health",
    "lifestyle",
    "other",
    "politics",
    "science",
    "sports",
    "technology",
    "top",
    "tourism",
    "world",
]

CATEGORY_FILTER = Annotated[
    str | list[CATEGORY_CODE],
    Field(
        pattern=_csv_pattern(*get_args(CATEGORY_CODE)),
        description=(
            "One or more NewsData category codes. "
            "Accepts either a list (preferred): `['technology', 'science']`, "
            "or a comma-separated string without spaces: `'technology,science'`. "
            "A single value also works as a plain string: `'technology'`. "
            "Allowed values: breaking, business, crime, domestic, education, "
            "entertainment, environment, food, health, lifestyle, other, "
            "politics, science, sports, technology, top, tourism, world."
        ),
        examples=["technology", ["technology", "science"], "business,world"],
    ),
]

PRIORITY_DOMAIN = Annotated[
    Literal["top", "medium", "low"],
    Field(
        description=(
            "Filter results by source credibility tier. "
            "`top` = highest credibility sources (top 10% of all sources). "
            "`medium` = top 30% of sources. "
            "`low` = top 50% of sources. "
            "Omit for no filtering — returns articles from all sources. "
            "Use `top` when accuracy and source quality matters most."
        ),
        examples=["top", "medium"],
    ),
]

SORT = Annotated[
    Literal["pubdateasc", "relevancy", "source"],
    Field(
        description=(
            "Pass one sort mode only. Use `pubdateasc` for oldest first, "
            "`relevancy` for query relevance, or `source` for source-priority order. "
            "Omit this parameter to keep NewsData's default newest-first order."
        ),
        examples=["pubdateasc", "relevancy"],
    ),
]

SENTIMENT = Annotated[
    Literal["positive", "negative", "neutral"],
    Field(
        description=(
            "Pass one sentiment filter only. Use `positive`, `negative`, or `neutral`."
        ),
        examples=["positive", "neutral"],
    ),
]

FLAG = Annotated[
    bool | Literal[0, 1],
    Field(
        description=(
            "Binary filter flag. "
            "Pass `True` (preferred) or `1` to require articles that HAVE this field. "
            "Pass `False` or `0` to require articles that LACK this field. "
            "Omit the parameter entirely to apply no filter. "
            "Used for: `image`, `video`, `full_content`."
        ),
        examples=[True, False, 1, 0],
    ),
]

REMOVE_DUPLICATE = Annotated[
    bool | Literal[1],
    Field(
        description=(
            "Ask NewsData to drop duplicate articles from the result set. "
            "Pass `True` (preferred) or `1` to enable. "
            "Pass `False` to disable — equivalent to omitting the parameter. "
            "Do NOT pass `0` (the API rejects it; omit instead)."
        ),
        examples=[True, 1],
    ),
]

SIZE = Annotated[
    int,
    Field(
        ge=1,
        le=50,
        description=(
            "Pass the number of articles to return in one page. Valid range is 1 to 50. "
            "Free plans usually allow up to 10, while paid plans allow up to 50."
        ),
        examples=[10, 30],
    ),
]

REGISTRATION_ID = Annotated[
    str,
    Field(
        min_length=32,
        max_length=32,
        description=(
            "The 32-character `registration_id` of a real-time query, as "
            "returned by `register_realtime_query` or listed by "
            "`list_realtime_queries`. Do not invent one — look it up."
        ),
        examples=["9b2d1e8a7c4f4b6e9d3a5c7e1f2a4b6c"],
    ),
]

ARTICLE_IDS = Annotated[
    str | list[str],
    Field(
        pattern=r"^[0-9a-f]{32}(?:,[0-9a-f]{32}){0,49}$",
        description=(
            "One to fifty NewsData `article_id` values (lowercase 32-char hex). "
            "Accepts either a list (preferred): "
            "`['668de67f2c32ce652104e7c4a5c9b517', '8c2cc0fdb87a3382876dca3448eb4cbc']`, "
            "or a comma-separated string without spaces."
        ),
        examples=[
            "668de67f2c32ce652104e7c4a5c9b517",
            ["668de67f2c32ce652104e7c4a5c9b517", "8c2cc0fdb87a3382876dca3448eb4cbc"],
            "668de67f2c32ce652104e7c4a5c9b517,8c2cc0fdb87a3382876dca3448eb4cbc",
        ],
    ),
]

QUERY = Annotated[
    str,
    Field(
        min_length=1,
        max_length=512,
        description=(
            "Full-text search query for `q`, `qInTitle`, or `qInMeta`. "
            "Use only ONE of these three in the same request. "
            "Supports boolean operators: AND, OR, NOT. "
            "Use quotes for exact phrases: '\"climate change\"'. "
            "Use parentheses for grouping: '(bitcoin OR ethereum) AND regulation'. "
            "Max 512 characters."
        ),
        examples=[
            "bitcoin",
            "bitcoin AND ethereum",
            '"climate change" NOT "fossil fuel"',
            "(apple OR google) AND earnings",
        ],
    ),
]

TIMEFRAME = Annotated[
    int | str,
    Field(
        description=(
            "Time window for recent news. "
            "Pass an integer for hours: `1` to `48` (e.g. `6` = last 6 hours). "
            "Pass a string with suffix `m` for minutes: `1m` to `2880m` "
            "(e.g. `90m` = last 90 minutes). "
            "`48` and `2880m` are equivalent maximums. "
            "Values outside these ranges will be rejected by the API."
        ),
        examples=[6, 24, 48, "90m", "2880m"],
    ),
]

INTERVAL = Annotated[
    Literal["hour", "day", "all"],
    Field(
        description=(
            "Bucket size for count endpoints. "
            "`hour` returns per-hour buckets, `day` returns per-day buckets, "
            "`all` returns a single aggregate total (no buckets). "
            "Used by `get_news_counts`, `get_crypto_counts`, `get_market_counts`."
        ),
        examples=["hour", "day", "all"],
    ),
]

COUNTRY_FILTER = Annotated[
    str | list[str],
    Field(
        pattern=r"^[a-z]{2}(?:,[a-z]{2}){0,9}$",
        description=(
            "One or more lowercase ISO 3166-1 alpha-2 country codes. "
            "Accepts either a list (preferred): `['us', 'gb']`, "
            "or a comma-separated string without spaces: `'us,gb'`. "
            "Do not use country names or uppercase letters. Max 10 codes."
        ),
        examples=["us", ["us", "gb"], "in,au,jp"],
    ),
]

LANGUAGE_FILTER = Annotated[
    str | list[str],
    Field(
        pattern=r"^[a-z]{2}(?:,[a-z]{2}){0,9}$",
        description=(
            "One or more lowercase ISO 639-1 language codes. "
            "Accepts either a list (preferred): `['en', 'fr']`, "
            "or a comma-separated string without spaces: `'en,fr'`. "
            "Do not use language names. Max 10 codes."
        ),
        examples=["en", ["en", "fr"], "hi,bn,ta"],
    ),
]

TAG_FILTER = Annotated[
    str | list[str],
    Field(
        min_length=1,
        max_length=256,
        pattern=r"^[^,]+(?:,[^,]+){0,9}$",
        description=(
            "One or more NewsData AI tags. "
            "Accepts either a list (preferred): `['tourism', 'food']`, "
            "or a comma-separated string without spaces: `'tourism,food'`. "
            "Use the exact tag text expected by NewsData. Max 10 tags."
        ),
        examples=["food", ["tourism", "food"], "blockchain,markets"],
    ),
]

REGION_FILTER = Annotated[
    str | list[str],
    Field(
        min_length=1,
        max_length=256,
        pattern=r"^[^,]+(?:,[^,]+){0,9}$",
        description=(
            "One or more NewsData region names. "
            "Accepts either a list (preferred): `['london-united kingdom', 'dubai-united arab emirates']`, "
            "or a comma-separated string: `'london-united kingdom,dubai-united arab emirates'`. "
            "Use city-country style values. Max 10 regions."
        ),
        examples=[
            "new york-united states of america",
            ["london-united kingdom", "dubai-united arab emirates"],
            "london-united kingdom,dubai-united arab emirates",
        ],
    ),
]

DOMAIN_FILTER = Annotated[
    str | list[str],
    Field(
        min_length=1,
        max_length=255,
        pattern=r"^[A-Za-z0-9.-]+(?:,[A-Za-z0-9.-]+){0,9}$",
        description=(
            "One or more domain identifiers (short source IDs or hostnames). "
            "Accepts either a list (preferred): `['reuters.com', 'bbc.com']`, "
            "or a comma-separated string: `'reuters.com,bbc.com'`. "
            "Do not include `http://` or `https://`. Max 10 entries."
        ),
        examples=["bbc", ["bbc", "coindesk"], "reuters.com,bbc.com"],
    ),
]

DOMAIN_URL_FILTER = Annotated[
    str | list[str],
    Field(
        min_length=1,
        max_length=255,
        pattern=r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:,[A-Za-z0-9.-]+\.[A-Za-z]{2,}){0,9}$",
        description=(
            "One or more full domain hosts (hostnames only, not URLs). "
            "Accepts either a list (preferred): `['bbc.com', 'reuters.com']`, "
            "or a comma-separated string: `'bbc.com,reuters.com'`. "
            "Use hostnames like `bbc.com`, not full article URLs. Max 10 hosts."
        ),
        examples=["bbc.com", ["bbc.com", "reuters.com"], "bbc.com,reuters.com"],
    ),
]

EXCLUDE_FIELD_FILTER = Annotated[
    str | list[str],
    Field(
        min_length=1,
        max_length=256,
        pattern=r"^[A-Za-z_]+(?:,[A-Za-z_]+){0,27}$",
        description=(
            "One or more response field names to exclude from the result. "
            "Accepts either a list (preferred): `['pubdate', 'imageurl']`, "
            "or a comma-separated string: `'pubdate,imageurl'`. "
            "Use the field names expected by NewsData, e.g. `pubdate`, "
            "`imageurl`, `content`, `source_id`. Max 28 fields."
        ),
        examples=["pubdate", ["pubdate", "imageurl"], "content,source_id"],
    ),
]

TIMEZONE = Annotated[
    str,
    Field(
        min_length=3,
        max_length=64,
        pattern=r"^[A-Za-z_+-]+(?:/[A-Za-z0-9_+-]+)+$",
        description=(
            "Pass an IANA timezone name. Use values like `Asia/Dubai` or "
            "`America/New_York`."
        ),
        examples=["Asia/Dubai", "America/New_York"],
    ),
]

PAGE = Annotated[
    str,
    Field(
        description=(
            "Pagination cursor for fetching the next page of results. "
            "Only pass this if a previous API response returned a `nextPage` field. "
            "On first request, omit this parameter entirely. "
            "Copy the token exactly — do not modify, encode, or guess it."
        ),
        examples=["17349543216784a12c9f0f6fbe7c1234"],
    ),
]

URL = Annotated[
    str,
    Field(
        pattern=r"^https?://\S+$",
        description=(
            "Pass a full absolute article URL starting with `http://` or `https://`."
        ),
        examples=["https://newsdata.io/blog/multiple-api-key-newsdata-io"],
    ),
]

DATE_OR_DATETIME = Annotated[
    str,
    Field(
        pattern=r"^\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}:\d{2})?$",
        description=(
            "A date as `YYYY-MM-DD` (e.g. `2025-01-01`) or as "
            "`YYYY-MM-DD HH:MM:SS` (e.g. `2025-01-01 06:12:45`) when "
            "you need sub-day precision. Both forms are accepted on "
            "every endpoint that takes a date."
        ),
        examples=["2025-01-01", "2025-01-01 06:12:45"],
    ),
]

COIN_FILTER = Annotated[
    str | list[str],
    Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._-]+(?:,[A-Za-z0-9._-]+){0,9}$",
        description=(
            "One or more crypto coin symbols (ticker-style). "
            "Accepts either a list (preferred): `['btc', 'eth']`, "
            "or a comma-separated string: `'btc,eth'`. Max 10 coins."
        ),
        examples=["btc", ["btc", "eth"], "sol,ada,xrp"],
    ),
]

MARKET_ID_FILTER = Annotated[
    str | list[str],
    Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._-]+(?:,[A-Za-z0-9._-]+){0,9}$",
        description=(
            "One or more market identifiers or stock tickers. "
            "Accepts either a list (preferred): `['AAPL', 'MSFT']`, "
            "or a comma-separated string: `'AAPL,MSFT'`. Max 10 market IDs."
        ),
        examples=["AAPL", ["AAPL", "MSFT"], "TSLA,NVDA,AMZN"],
    ),
]

ORGANIZATION_FILTER = Annotated[
    str | list[str],
    Field(
        min_length=1,
        max_length=256,
        pattern=r"^[^,]+(?:,[^,]+){0,9}$",
        description=(
            "One or more organization names. "
            "Accepts either a list (preferred): `['tesla', 'apple']`, "
            "or a comma-separated string: `'tesla,apple'`. "
            "Use plain organization names. Max 10 entries."
        ),
        examples=["uber", ["tesla", "apple"], "tesla,microsoft,google"],
    ),
]

CREATOR_FILTER = Annotated[
    str | list[str],
    Field(
        min_length=1,
        max_length=256,
        pattern=r"^[^,]+(?:,[^,]+){0,9}$",
        description=(
            "One or more author/byline names. "
            "Accepts either a list (preferred): `['John Smith', 'Jane Doe']`, "
            "or a comma-separated string: `'John Smith,Jane Doe'`. "
            "Use the exact byline text expected by NewsData. Max 10 names."
        ),
        examples=["john smith", ["john smith", "jane doe"], "ana lopez,bao chen"],
    ),
]

DATATYPE_FILTER = Annotated[
    str | list[str],
    Field(
        min_length=1,
        max_length=64,
        pattern=r"^[^,]+(?:,[^,]+){0,9}$",
        description=(
            "Filter by content type. "
            "Accepts either a list (preferred): `['article', 'video']`, "
            "or a comma-separated string: `'article,video'`. "
            "Use the exact datatype values supported by NewsData (e.g. `article`). "
            "Max 10 entries."
        ),
        examples=["article", ["article", "video"], "article,image"],
    ),
]

SENTIMENT_SCORE = Annotated[
    int,
    Field(
        ge=0,
        le=100,
        description=(
            "Minimum confidence percentage (0–100) for the chosen `sentiment` label. "
            "For example, with `sentiment='positive'` and `sentiment_score=50`, only "
            "articles whose positive-sentiment confidence is at least 50 are returned. "
            "REQUIRES `sentiment` to also be set; passing `sentiment_score` without "
            "`sentiment` returns Error before any API call."
        ),
        examples=[50, 70, 90],
    ),
]
