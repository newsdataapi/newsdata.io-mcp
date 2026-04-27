import os
from typing import Annotated, Literal, get_args

from dotenv import load_dotenv
from pydantic import Field

load_dotenv()

NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY")
NEWSDATA_BASE_URL = "https://newsdata.io/api/1"

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

if not NEWSDATA_API_KEY:
    import warnings

    warnings.warn("NEWSDATA_API_KEY is not set", stacklevel=2)


def _csv_pattern(*values: str) -> str:
    choices = "|".join(values)
    return rf"^(?:{choices})(?:,(?:{choices}))*$"


# NewsData documents 17 category codes in its public endpoint docs/blogs.
CATEGORY_CODE = Literal[
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
    str,
    Field(
        pattern=_csv_pattern(*get_args(CATEGORY_CODE)),
        description=(
            "Pass one or more NewsData category codes as a comma-separated string. "
            "Do not use spaces. Allowed values are: business, crime, domestic, "
            "education, entertainment, environment, food, health, lifestyle, "
            "other, politics, science, sports, technology, top, tourism, world."
        ),
        examples=["technology", "technology,science", "business,world"],
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
    Literal[0, 1],
    Field(
        description=(
            "Binary flag. Pass `1` to filter FOR articles that have this field "
            "(e.g. articles with images). Pass `0` to filter for articles WITHOUT it. "
            "Omit the parameter entirely if you don't want to filter by it at all. "
            "Used for: `image`, `video`, `full_content`."
        ),
        examples=[1, 0],
    ),
]

REMOVE_DUPLICATE = Annotated[
    Literal[1],
    Field(
        description=(
            "Pass only `1` when you want NewsData to remove duplicate articles. "
            "If you do not want that filter, omit the parameter instead of passing `0`."
        ),
        examples=[1],
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

ARTICLE_IDS = Annotated[
    str,
    Field(
        pattern=r"^[0-9a-f]{32}(?:,[0-9a-f]{32}){0,49}$",
        description=(
            "Pass one to fifty NewsData `article_id` values as a comma-separated "
            "string of lowercase 32-character hex IDs. Do not add spaces."
        ),
        examples=[
            "668de67f2c32ce652104e7c4a5c9b517",
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
    str,
    Field(
        pattern=(
            r"^(?:"
            r"[1-9]|[1-3][0-9]|4[0-8]"
            r"|[1-9][0-9]{0,2}m|1[0-9]{3}m|2[0-7][0-9]{2}m|28[0-7][0-9]m|2880m"
            r")$"
        ),
        description=(
            "Time window for recent news. "
            "Use plain integers for hours (1-48 only, e.g. `6` = last 6 hours). "
            "Use suffix `m` for minutes (1m-2880m, e.g. `90m` = last 90 minutes). "
            "2880m and 48 are equivalent maximums. "
            "Do NOT pass values like `49` or `3000m` — they will be rejected."
        ),
        examples=["2", "48", "90m", "2880m"],
    ),
]

COUNTRY_FILTER = Annotated[
    str,
    Field(
        pattern=r"^[a-z]{2}(?:,[a-z]{2}){0,9}$",
        description=(
            "Pass one or more lowercase ISO 3166-1 alpha-2 country codes as a "
            "comma-separated string. Do not use country names or uppercase letters."
        ),
        examples=["us", "us,gb", "in,au,jp"],
    ),
]

LANGUAGE_FILTER = Annotated[
    str,
    Field(
        pattern=r"^[a-z]{2}(?:,[a-z]{2}){0,9}$",
        description=(
            "Pass one or more lowercase ISO 639-1 language codes as a "
            "comma-separated string. Do not use language names."
        ),
        examples=["en", "en,fr", "hi,bn,ta"],
    ),
]

TAG_FILTER = Annotated[
    str,
    Field(
        min_length=1,
        max_length=256,
        pattern=r"^[^,]+(?:,[^,]+){0,9}$",
        description=(
            "Pass one or more NewsData AI tags as a comma-separated string. "
            "Use the exact tag text expected by NewsData and do not add spaces "
            "around commas."
        ),
        examples=["food", "tourism,food", "blockchain,markets"],
    ),
]

REGION_FILTER = Annotated[
    str,
    Field(
        min_length=1,
        max_length=256,
        pattern=r"^[^,]+(?:,[^,]+){0,9}$",
        description=(
            "Pass one or more NewsData region names as a comma-separated string. "
            "Use the region text directly, for example city-country style values."
        ),
        examples=[
            "new york-united states of america",
            "london-united kingdom,dubai-united arab emirates",
        ],
    ),
]

DOMAIN_FILTER = Annotated[
    str,
    Field(
        min_length=1,
        max_length=255,
        pattern=r"^[A-Za-z0-9.-]+(?:,[A-Za-z0-9.-]+){0,9}$",
        description=(
            "Pass one or more domain identifiers as a comma-separated string "
            "without `http://` or `https://`. NewsData accepts values such as "
            "short source IDs or hostnames."
        ),
        examples=["bbc", "coindesk", "reuters.com,bbc.com"],
    ),
]

DOMAIN_URL_FILTER = Annotated[
    str,
    Field(
        min_length=1,
        max_length=255,
        pattern=r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:,[A-Za-z0-9.-]+\.[A-Za-z]{2,}){0,9}$",
        description=(
            "Pass one or more full domain hosts as a comma-separated string without "
            "protocol or path. Use hostnames like `bbc.com`, not full article URLs."
        ),
        examples=["bbc.com", "bbc.com,reuters.com"],
    ),
]

EXCLUDE_FIELD_FILTER = Annotated[
    str,
    Field(
        min_length=1,
        max_length=256,
        pattern=r"^[A-Za-z_]+(?:,[A-Za-z_]+){0,27}$",
        description=(
            "Pass one or more response field names to exclude as a comma-separated "
            "string. Use the field names expected by NewsData, such as `pubdate`, "
            "`imageurl`, `content`, or `source_id`."
        ),
        examples=["pubdate", "pubdate,imageurl", "content,source_id"],
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
            "Pass either `YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS`, depending on the "
            "endpoint requirement."
        ),
        examples=["2025-01-01", "2025-01-01 06:12:45"],
    ),
]

COIN_FILTER = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._-]+(?:,[A-Za-z0-9._-]+){0,9}$",
        description=(
            "Pass one or more crypto coin symbols as a comma-separated string. "
            "Use ticker-style values such as `btc` or `eth,btc`."
        ),
        examples=["btc", "eth,btc", "sol,ada,xrp"],
    ),
]

SYMBOL_FILTER = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._-]+(?:,[A-Za-z0-9._-]+){0,9}$",
        description=(
            "Pass one or more market symbols or stock tickers as a comma-separated "
            "string."
        ),
        examples=["AAPL", "AAPL,MSFT", "TSLA,NVDA,AMZN"],
    ),
]

ORGANIZATION_FILTER = Annotated[
    str,
    Field(
        min_length=1,
        max_length=256,
        pattern=r"^[^,]+(?:,[^,]+){0,9}$",
        description=(
            "Pass one or more organization names as a comma-separated string. "
            "Use plain organization names and do not add spaces around commas."
        ),
        examples=["uber", "uber,apple", "tesla,microsoft,google"],
    ),
]
