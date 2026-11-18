"""Pydantic `Annotated` parameter types reused across the MCP tools.

Each alias carries the `description` that MCP clients show the model in the
tool's JSON Schema. Names and meanings follow the NewsData.io API
one-to-one: a tool parameter is always called what the API calls it.

Three rules keep these schemas usable by any model:

- Every alias is optional by itself: `None` is part of the type, and a tool
  declares a parameter as `name: ALIAS = None`. Writing `ALIAS | None` in the
  signature instead would make pydantic put the description inside one branch
  of an `anyOf`; with `None` inside the alias the description sits at the top
  of the property, where every client and model reads it.
- Value checks stay with the API. There are no regex patterns or length
  limits here: the API knows the real limits (several depend on the plan)
  and answers a wrong value with a message and suggested values, which
  `formatters._format_error` passes on. Only closed sets (`Literal`) and
  plain numeric ranges are declared.
- Shapes are lenient. Multi-value filters take a comma-separated string or
  a list, flags take true/false or 1/0. `http._normalize_params` turns every
  shape into the query-string form.
"""
from typing import Annotated, Literal

from pydantic import Field

# ---------- Search ----------

QUERY = Annotated[
    str | None,
    Field(
        description=(
            "Search words, matched against title, description, content, keywords and URL. "
            "Several words must all appear. Use double quotes for an exact phrase and AND, OR, NOT "
            "with parentheses: `(tesla OR rivian) AND recall`. No wildcards. "
            "Maximum length depends on the plan (100 to 512 characters). "
            "Use only one of `q`, `q_in_title`, `q_in_meta`."
        ),
    ),
]

QUERY_IN_TITLE = Annotated[
    str | None,
    Field(description="Same search syntax as `q`, but matched against the article title only."),
]

QUERY_IN_META = Annotated[
    str | None,
    Field(
        description=(
            "Same search syntax as `q`, but matched against title, description, keywords and URL "
            "(not the article body)."
        ),
    ),
]

# ---------- Location, language, category ----------

COUNTRY_FILTER = Annotated[
    str | list[str] | None,
    Field(
        description=(
            "Country codes (ISO 3166-1 alpha-2), e.g. `us`, `gb`, `in`. Comma-separated string or list. "
            "`country` keeps only these countries; `exclude_country` leaves them out."
        ),
    ),
]

LANGUAGE_FILTER = Annotated[
    str | list[str] | None,
    Field(
        description=(
            "Language codes (ISO 639-1), e.g. `en`, `hi`, `es`. Comma-separated string or list. "
            "`language` keeps only these languages; `exclude_language` leaves them out."
        ),
    ),
]

CATEGORY_FILTER = Annotated[
    str | list[str] | None,
    Field(
        description=(
            "News categories. Allowed: breaking, business, crime, domestic, education, entertainment, "
            "environment, food, health, lifestyle, other, politics, science, sports, technology, top, "
            "tourism, world. Comma-separated string or list. "
            "`category` keeps only these categories; `exclude_category` leaves them out."
        ),
    ),
]

REGION_FILTER = Annotated[
    str | list[str] | None,
    Field(
        description=(
            "Places mentioned in the article (city, state or country), e.g. `india` or `paris-france` "
            "(join levels with `-` to require them together). Comma-separated string or list. "
            "Corporate plan only."
        ),
    ),
]

# ---------- Sources ----------

SOURCE_URL_FILTER = Annotated[
    str | list[str] | None,
    Field(
        description=(
            "News sources by website address: host plus optional path, e.g. `bbc.com` or `vice.com/de`. "
            "`https://` and `www.` are optional, so a `source.url` from a result can be passed as it is. "
            "It must match a known source exactly; an unknown value returns the closest known sources. "
            "Comma-separated string or list. "
            "`source_url` keeps only these sources; `exclude_source_url` leaves them out."
        ),
    ),
]

SOURCE_PRIORITY = Annotated[
    Literal["top", "medium", "low"] | None,
    Field(
        description=(
            "Keep only sources above a rank: `top` = the highest-ranked sources only, "
            "`medium` = top and mid-ranked, `low` = also lower-ranked. Omit for all sources."
        ),
    ),
]

# ---------- Time ----------

FROM_DATE = Annotated[
    str | None,
    Field(
        description=(
            "Start of the date range, in UTC: `YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS`, e.g. `2026-06-01`. "
            "Not in the future. Cannot be combined with `timeframe`."
        ),
    ),
]

TO_DATE = Annotated[
    str | None,
    Field(
        description=(
            "End of the date range, in UTC: `YYYY-MM-DD` (covers that whole day) or `YYYY-MM-DD HH:MM:SS`. "
            "Not in the future. Send `from_date` with it. Cannot be combined with `timeframe`."
        ),
    ),
]

TIMEFRAME = Annotated[
    int | str | None,
    Field(
        description=(
            "Only the last N hours (a number from 1 to 720, e.g. `6`) or the last N minutes "
            "(with `m`, from `1m` to `43200m`, e.g. `90m`). Paid plans only. "
            "Cannot be combined with `from_date` or `to_date`."
        ),
    ),
]

TIMEZONE = Annotated[
    str | None,
    Field(
        description=(
            "IANA time zone name, e.g. `Asia/Kolkata`. It only changes how `published_at` and `fetched_at` "
            "are shown (default UTC); dates you pass are always read as UTC."
        ),
    ),
]

# ---------- Content flags ----------

IMAGE_FLAG = Annotated[
    bool | Literal[0, 1] | None,
    Field(
        description=(
            "`true`: only articles that have an image. "
            "`false`: no filtering, but `media.image_url` is left out of the result."
        ),
    ),
]

VIDEO_FLAG = Annotated[
    bool | Literal[0, 1] | None,
    Field(
        description=(
            "`true`: only articles that have a video. "
            "`false`: no filtering, but `media.video_url` is left out of the result."
        ),
    ),
]

CONTENT_FLAG = Annotated[
    bool | Literal[0, 1] | None,
    Field(
        description=(
            "`true`: only articles that have full text, and that text is included in the result "
            "(it is long; a list leaves it out otherwise). `false` changes nothing. Needs a paid plan."
        ),
    ),
]

PRESENCE_FLAG = Annotated[
    bool | Literal[0, 1] | None,
    Field(
        description=(
            "`true`: count only articles that have this (`image`: an image, `video`: a video, "
            "`content`: full text; `content` needs a paid plan). `false` has no effect."
        ),
    ),
]

REMOVE_DUPLICATE = Annotated[
    bool | Literal[0, 1] | None,
    Field(
        description=(
            "`true`: leave out articles flagged as duplicates of another article. "
            "`false` or omitted: keep them."
        ),
    ),
]

# ---------- AI filters ----------

SENTIMENT = Annotated[
    Literal["positive", "neutral", "negative"] | None,
    Field(description="Only articles whose AI sentiment is `positive`, `neutral` or `negative`."),
]

SENTIMENT_SCORE = Annotated[
    float | None,
    Field(
        ge=1,
        le=100,
        description=(
            "Minimum confidence, from 1 to 100, for the chosen `sentiment`, e.g. "
            '`sentiment="negative", sentiment_score=80`. Requires `sentiment`.'
        ),
    ),
]

TAG_FILTER = Annotated[
    str | list[str] | None,
    Field(
        description=(
            "AI topic tag ids, lowercase with underscores, e.g. `artificial_intelligence`, `elections`, "
            "`financial_markets`, `climate_and_weather`. An unknown id returns the closest valid ids. "
            "Comma-separated string or list."
        ),
    ),
]

CRYPTO_TAG_FILTER = Annotated[
    str | list[str] | None,
    Field(
        description=(
            "Crypto topic tag ids. Allowed: adoption, blockchain, coin_fundamental, competition, "
            "developer_community, economy, education, exchange, founders_investors, general, geopolitics, "
            "global_markets, government, liquidity, mining, scam, security_privacy, sentiments, supply, "
            "technical_analysis, technology. Comma-separated string or list."
        ),
    ),
]

ORGANIZATION_FILTER = Annotated[
    str | list[str] | None,
    Field(
        description=(
            "Organizations mentioned in the article, by name, e.g. `apple,uber`. "
            "Comma-separated string or list. Corporate plan only."
        ),
    ),
]

CREATOR_FILTER = Annotated[
    str | list[str] | None,
    Field(description="Article authors (bylines), e.g. `jane doe`. Comma-separated string or list."),
]

DATATYPE_FILTER = Annotated[
    str | list[str] | None,
    Field(
        description=(
            "Content types. Allowed: news, blog, multimedia, forum, pressrelease, review, research, "
            "opinion, analysis, podcast. Comma-separated string or list."
        ),
    ),
]

# ---------- Crypto and market ----------

COIN_FILTER = Annotated[
    str | list[str] | None,
    Field(
        description=(
            "Coin ticker symbols, e.g. `btc`, `eth`. A coin name such as `bitcoin` is rejected, "
            "and the error gives the right symbol. Comma-separated string or list."
        ),
    ),
]

MARKET_ID_FILTER = Annotated[
    str | list[str] | None,
    Field(
        description=(
            "Stock listing ids in the form ticker-country-exchange, e.g. `aapl-us-vy`. "
            "To find an id, pass a ticker or company name (`aapl`): it is rejected, and the error lists "
            "the matching ids. Results also show each article's `market_id`. "
            "Comma-separated string or list."
        ),
    ),
]

# ---------- Specific articles ----------

ARTICLE_IDS = Annotated[
    str | list[str] | None,
    Field(
        description=(
            "Article ids (the 32-character `id` of a result) to fetch exactly those articles, with their "
            "full text (paid plans). Comma-separated string or list. Can only be combined with "
            "`from_date` and `to_date`."
        ),
    ),
]

URL = Annotated[
    str | None,
    Field(
        description=(
            "Full URL of one article, starting with `http://` or `https://`, to fetch exactly that "
            "article, with its full text (paid plans). Can only be combined with `from_date` and `to_date`."
        ),
    ),
]

# ---------- Output and paging ----------

SIZE = Annotated[
    int | None,
    Field(
        ge=1,
        le=50,
        description=(
            "Articles per call, from 1 to the plan maximum (10 on the Free plan, 50 on paid plans). "
            "Default: 10."
        ),
    ),
]

BUCKET_SIZE = Annotated[
    int | None,
    Field(
        ge=1,
        le=50,
        description="Buckets per page, from 1 to 50. Default: 50.",
    ),
]

PAGE = Annotated[
    str | int | None,
    Field(
        description=(
            "Paging token: the `next_page` value of the previous result, copied exactly. "
            "Repeat every other argument unchanged. Omit on the first call."
        ),
    ),
]

SORT = Annotated[
    Literal["pubdatedesc", "pubdateasc", "relevancy", "source", "fetched_at"] | None,
    Field(
        description=(
            "Order of results: `pubdatedesc` newest first (default), `pubdateasc` oldest first, "
            "`relevancy` best match first (needs `q`, `q_in_title` or `q_in_meta`), "
            "`source` highest-ranked sources first, `fetched_at` most recently collected first."
        ),
    ),
]

SORT_CRYPTO = Annotated[
    Literal["pubdatedesc", "pubdateasc", "relevancy", "source"] | None,
    Field(
        description=(
            "Order of results: `pubdatedesc` newest first (default), `pubdateasc` oldest first, "
            "`relevancy` best match first (needs `q`, `q_in_title` or `q_in_meta`), "
            "`source` highest-ranked sources first."
        ),
    ),
]

SORT_COUNT = Annotated[
    Literal["pubdatedesc", "pubdateasc"] | None,
    Field(description="Order of buckets: `pubdatedesc` newest bucket first (default) or `pubdateasc` oldest first."),
]

EXCLUDE_FIELD_FILTER = Annotated[
    str | list[str] | None,
    Field(
        description=(
            "Result fields to leave out, to make the result smaller: a field (`content`, `keyword`), "
            "a whole group (`media`, `source`, `ai`) or one field of a group (`ai.summary`). "
            "`id` cannot be left out. Comma-separated string or list."
        ),
    ),
]

# ---------- Count tools only ----------

INTERVAL = Annotated[
    Literal["month", "day", "hour"] | None,
    Field(description="Length of each bucket: `month`, `day` (default) or `hour`. Buckets are in UTC."),
]

# ---------- Real-time tools only ----------
# The real-time (WebSocket) service has its own registration endpoint, with
# its own names for the source filters and for the fields of a streamed
# article. `register_realtime_query` keeps those names; the aliases below
# describe them.

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
    ),
]

# The three settings of `stream_news`. They belong to this server, not to the
# API, and each has a default other than `None`, so the default is written in
# the tool signature (`max_articles: STREAM_MAX_ARTICLES = 10`). The two
# numbers are not range-checked here: the tool moves an out-of-range value to
# the nearest limit instead of refusing the call.
STREAM_MAX_ARTICLES = Annotated[
    int,
    Field(
        description=(
            "Stop as soon as this many articles have arrived. From 1 to 50; a value outside that range "
            "is moved to the nearest limit. Default: 10."
        ),
    ),
]

STREAM_WAIT_SECONDS = Annotated[
    float,
    Field(
        description=(
            "Longest time to listen, in seconds. From 1 to 120; a value outside that range is moved to "
            "the nearest limit. Default: 30."
        ),
    ),
]

STREAM_CONTENT = Annotated[
    bool,
    Field(
        description=(
            "`true`: include each article's full text (`content`) in the result. It is long, so it is "
            "left out by default."
        ),
    ),
]

REALTIME_DOMAIN_FILTER = Annotated[
    str | list[str] | None,
    Field(
        description=(
            "News sources by their NewsData source id, e.g. `bbc`. Comma-separated string or list. "
            "Keeps only these sources."
        ),
    ),
]

# `exclude_domain` is named like `domain` but takes website addresses, not
# source ids: the API answers `bbc` with HTTP 422 and suggests `bbc.com`.
REALTIME_EXCLUDE_DOMAIN_FILTER = Annotated[
    str | list[str] | None,
    Field(
        description=(
            "News sources to leave out, by website address, e.g. `bbc.com` (a source id such as `bbc` "
            "is rejected). It must match a known source exactly. Comma-separated string or list."
        ),
    ),
]

REALTIME_DOMAIN_URL_FILTER = Annotated[
    str | list[str] | None,
    Field(
        description=(
            "News sources by website address, e.g. `bbc.com`. It must match a known source exactly. "
            "Comma-separated string or list. Keeps only these sources."
        ),
    ),
]

REALTIME_FLAG = Annotated[
    bool | Literal[0, 1] | None,
    Field(
        description=(
            "`true`: only articles that have this (`image`: an image, `video`: a video, "
            "`full_content`: full text; `full_content` needs a paid plan). `false` does not filter."
        ),
    ),
]

REALTIME_EXCLUDE_FIELD_FILTER = Annotated[
    str | list[str] | None,
    Field(
        description=(
            "Fields to leave out of each streamed article, by the stream's own field names, "
            "e.g. `content`, `keywords`, `ai_summary`. `article_id` cannot be left out. "
            "Comma-separated string or list."
        ),
    ),
]
