"""Pure-text rendering helpers for NewsData.io API responses.

These functions have no network or framework dependencies; they take a
`fetch()`-style envelope (`{"status": "success"|"error", ...}`) and emit
a flat `label: value` text block suitable as an MCP tool return value.

Labels are the API's own field paths (`source.name`, `ai.summary`,
`media.image_url`). They are the names `exclude_field` accepts and the
names in the NewsData documentation, so a model meets one vocabulary for
parameters, results and docs.

Error envelopes from ``http.fetch`` carry an optional ``status_code``,
``error_code``, ``retry_after`` and ``recommendations``. ``_format_error``
renders all of them (e.g. ``Error (HTTP 422, UnsupportedFilter): ...``
followed by the valid values close to the rejected one) so the model can
correct its call without interpreting prose.
"""
from typing import Any

# A field the plan does not include holds a notice string instead of data:
# "ONLY AVAILABLE IN PAID PLANS", "ONLY AVAILABLE IN PROFESSIONAL AND
# CORPORATE PLANS" or "ONLY AVAILABLE IN CORPORATE PLANS". The HTTP client
# sends `Accept-Language: en`, so the notices arrive in English.
_PLAN_NOTICE_PREFIX = "ONLY AVAILABLE IN"

# `/sources` returns at most this many sources and has no paging.
_SOURCES_LIMIT = 100

# Article fields in display order: what the article is and where it comes
# from first, classification and AI fields next, media and bookkeeping last.
# `source.icon_url` is deliberately not shown: an icon address is of no use
# to a model and would be repeated on every article.
_ARTICLE_FIELDS: tuple[str, ...] = (
    "title",
    "url",
    "source.name",
    "published_at",
    "meta_description",
    "ai.summary",
    "content",
    "language",
    "country",
    "category",
    "datatype",
    "keyword",
    "creator",
    "coin",
    "ticker",
    "market_id",
    "ai.sentiment",
    "ai.tag",
    "ai.region",
    "ai.organization",
    "media.image_url",
    "media.video_url",
    "source.url",
    "source.priority",
    "fetched_at",
    "duplicate",
    "id",
)

# `ai.region` entries contain commas themselves ("paris,ile-de-france,france").
_LIST_SEPARATORS: dict[str, str] = {"ai.region": "; "}

# Header line of an article list whose full text was left out (see
# `defaults.apply_article_defaults`). It tells the model how to get the text.
_FULL_TEXT_HINT = (
    "full_text: left out of this list. To read an article in full, call this tool again with "
    "id=<its id> (several ids allowed), or add content=true to the search."
)


def _format_recommendation(item: Any) -> str:
    """Render one suggested value, with the value to send first.

    The API suggests plain strings (categories, source URLs) or objects:
    ``{"code", "name"}`` for countries, languages and coins, ``{"id",
    "name"}`` for tags, ``{"ticker", "country", "exchangeName", "id"}``
    for market ids. In every object the value to send is ``id`` or
    ``code``; the rest is shown in brackets as context.
    """
    if not isinstance(item, dict):
        return str(item)

    value = item.get("id") or item.get("code")
    extras = [str(val) for key, val in item.items() if key not in ("id", "code") and val]
    if value is None:
        return ", ".join(extras)
    if extras:
        return f"{value} ({', '.join(extras)})"
    return str(value)


def _format_error(envelope: dict[str, Any]) -> str:
    """Render an error envelope.

    The first line is ``Error[ (HTTP {code}[, {error_code}][, retry after
    {N}s])]: {message}``, in that fixed order. When the API suggested
    valid values for a rejected one, one more line per rejected value
    follows: ``Valid values close to "usa": us (united states of
    america)``. A duplicate real-time registration adds the existing
    ``registration_id`` on a line of its own.

    Status code 200 is a soft error: the HTTP request succeeded but the
    API answered ``{"status": "error"}``. ``HTTP 200`` in front of an error
    could be read as success, so the status is left out in that case.
    """
    message = envelope.get("message", "Unknown error")
    code = envelope.get("status_code")
    error_code = envelope.get("error_code")
    retry_after = envelope.get("retry_after")
    parts: list[str] = []
    if code is not None and code != 200:
        parts.append(f"HTTP {code}")
    if error_code:
        parts.append(str(error_code))
    if retry_after is not None:
        parts.append(f"retry after {retry_after}s")
    suffix = f" ({', '.join(parts)})" if parts else ""
    lines = [f"Error{suffix}: {message}"]

    recommendations = envelope.get("recommendations")
    if isinstance(recommendations, dict):
        for rejected, suggestions in recommendations.items():
            if isinstance(suggestions, list) and suggestions:
                rendered = "; ".join(_format_recommendation(item) for item in suggestions)
                lines.append(f'Valid values close to "{rejected}": {rendered}')
            else:
                lines.append(f'No valid value close to "{rejected}" was found.')

    _append_field(lines, "registration_id", envelope.get("registration_id"))

    return "\n".join(lines)


def _is_plan_notice(value: Any) -> bool:
    """True when a field holds the API's "not in your plan" notice."""
    return isinstance(value, str) and value.strip().upper().startswith(_PLAN_NOTICE_PREFIX)


def _format_sentiment(value: Any) -> str | None:
    """Flatten ``ai.sentiment`` (``{"label": ..., "score": {...}}``) into
    ``neutral (negative=4.12, neutral=90.33, positive=5.55)``. Returns
    ``None`` when there is nothing to show so ``_append_field`` skips the
    line."""
    if not isinstance(value, dict):
        return None

    label = value.get("label")
    label_text = label.strip() if isinstance(label, str) and label.strip() else None
    score = value.get("score")
    score_text = (
        ", ".join(f"{key}={val}" for key, val in score.items())
        if isinstance(score, dict) and score
        else None
    )
    if label_text and score_text:
        return f"{label_text} ({score_text})"
    return label_text or score_text


def _format_code_names(value: Any) -> str | None:
    """Flatten a ``/sources`` language or country list
    (``[{"code": "en", "name": "english"}]``) into ``en (english)``."""
    if not isinstance(value, list):
        return None

    rendered: list[str] = []
    for item in value:
        if isinstance(item, dict):
            code = item.get("code")
            name = item.get("name")
            if code and name:
                rendered.append(f"{code} ({name})")
            elif code or name:
                rendered.append(str(code or name))
        elif item:
            rendered.append(str(item))
    return ", ".join(rendered) or None


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _get_path(item: dict[str, Any], path: str) -> Any:
    """Read ``title`` or a grouped field such as ``ai.summary`` from an
    API object. A missing field or group reads as ``None``."""
    group, _, key = path.rpartition(".")
    if not group:
        return item.get(key)
    parent = item.get(group)
    return parent.get(key) if isinstance(parent, dict) else None


def _append_field(lines: list[str], label: str, value: Any, separator: str = ", ") -> None:
    """Append ``label: value`` unless there is nothing to show (``None``,
    a blank string, a list with no items)."""
    if value is None:
        return

    if isinstance(value, bool):
        rendered = "true" if value else "false"
    elif isinstance(value, list):
        rendered = separator.join([str(item) for item in value if item])
    else:
        rendered = str(value)

    if not rendered.strip():
        return
    lines.append(f"{label}: {rendered}")


def _format_article_item(
    article: dict[str, Any], not_in_plan: list[str], full_text: bool = True
) -> list[str]:
    """Render one article as ``label: value`` lines in ``_ARTICLE_FIELDS``
    order.

    A field that holds a plan notice is not rendered; its name is added
    to ``not_in_plan`` (once) so ``format_articles`` can report it a
    single time for the whole page. With ``full_text=False`` the
    ``content`` field is skipped.
    """
    lines: list[str] = []
    for path in _ARTICLE_FIELDS:
        if path == "content" and not full_text:
            continue
        value = _get_path(article, path)

        notice = _is_plan_notice(value)
        if path == "ai.sentiment" and isinstance(value, dict):
            notice = _is_plan_notice(value.get("label"))
        if notice:
            if path not in not_in_plan:
                not_in_plan.append(path)
            continue

        if path == "ai.sentiment":
            value = _format_sentiment(value)
        _append_field(lines, path, value, _LIST_SEPARATORS.get(path, ", "))

    return lines


def format_articles(data: dict[str, Any], endpoint_name: str, full_text: bool = True) -> str:
    """Render an article response (`/news`, `/crypto`, `/market`). Emits an
    ``endpoint:`` / ``total_results:`` / ``returned_results:`` /
    ``next_page:`` header followed by one ``Article N:`` block per result.

    ``total_results`` counts every matching article, not just this page.
    The ``next_page`` token is the value to pass back as ``page=`` on the
    next call; ``none`` means there are no more pages. A
    ``not_in_your_plan:`` header line lists the fields the API withheld
    because of the plan.

    ``full_text=False`` is for a list whose full text was left out of the
    request: ``content`` is not rendered, and a ``full_text:`` header line
    tells the model how to read an article in full.
    """
    if data.get("status") != "success":
        return _format_error(data)

    inner = data.get("data", {}) or {}
    results = inner.get("results")
    articles = [item for item in results if isinstance(item, dict)] if isinstance(results, list) else []
    if not articles:
        return f"No {endpoint_name} articles found matching your query."

    total = inner.get("total_results", len(articles))
    next_page = inner.get("next_page")

    not_in_plan: list[str] = []
    body: list[str] = []
    for index, article in enumerate(articles, 1):
        body.append(f"Article {index}:")
        body.extend(_format_article_item(article, not_in_plan, full_text))
        body.append("")

    lines = [
        f"endpoint: {endpoint_name}",
        f"total_results: {total}",
        f"returned_results: {len(articles)}",
        f"next_page: {next_page or 'none'}",
    ]
    if not full_text:
        lines.append(_FULL_TEXT_HINT)
    if not_in_plan:
        lines.append(f"not_in_your_plan: {', '.join(not_in_plan)}")
    lines.append("")
    lines.extend(body)

    return "\n".join(lines)


def format_counts(data: dict[str, Any], endpoint_name: str) -> str:
    """Render a count response (`/count/news`, `/count/crypto`,
    `/count/market`).

    ``total_results`` is the API's number of matching articles over the
    whole date range (the same on every page). The buckets of this page
    follow as ``date_time,count`` lines, one per bucket; ``date_time`` is
    the start of the bucket in UTC.
    """
    if data.get("status") != "success":
        return _format_error(data)

    inner = data.get("data", {}) or {}
    results = inner.get("results")
    buckets = [item for item in results if isinstance(item, dict)] if isinstance(results, list) else []
    total = inner.get("total_results")
    if total is None and not buckets:
        return f"No results found for {endpoint_name} over the given range."

    next_page = inner.get("next_page")

    lines = [
        f"endpoint: {endpoint_name}",
        f"total_results: {total if total is not None else 'n/a'}",
        f"returned_buckets: {len(buckets)}",
        f"next_page: {next_page or 'none'}",
        "",
    ]
    if buckets:
        lines.append("date_time,count")
        lines.extend(f"{bucket.get('date_time')},{bucket.get('count')}" for bucket in buckets)
        lines.append("")

    return "\n".join(lines)


def format_sources(data: dict[str, Any]) -> str:
    """Render the `/sources` response. Emits an ``endpoint:`` /
    ``total_results:`` / ``returned_results:`` header followed by one
    ``Source N:`` block per source. A source's ``url`` is the value to
    pass as ``source_url`` on the other tools.
    """
    if data.get("status") != "success":
        return _format_error(data)

    inner = data.get("data", {}) or {}
    results = inner.get("results")
    sources = [item for item in results if isinstance(item, dict)] if isinstance(results, list) else []
    if not sources:
        return "No sources found matching your filters."

    total = inner.get("total_results", len(sources))

    lines = [
        "endpoint: sources",
        f"total_results: {total}",
        f"returned_results: {len(sources)}",
    ]
    if len(sources) >= _SOURCES_LIMIT:
        lines.append(
            f"note: the API returns at most {_SOURCES_LIMIT} sources, picked at random when more match; "
            "add filters to narrow the list"
        )
    lines.append("")

    for index, source in enumerate(sources, 1):
        lines.append(f"Source {index}:")
        _append_field(lines, "name", _clean_text(source.get("name")))
        _append_field(lines, "url", source.get("url"))
        _append_field(lines, "priority", source.get("priority"))
        _append_field(lines, "language", _format_code_names(source.get("language")))
        _append_field(lines, "country", _format_code_names(source.get("country")))
        _append_field(lines, "category", source.get("category"))
        _append_field(lines, "description", _clean_text(source.get("description")))
        _append_field(lines, "stat.article_count", _get_path(source, "stat.article_count"))
        _append_field(lines, "stat.last_fetched_at", _get_path(source, "stat.last_fetched_at"))
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Real-time tools. The real-time service has its own, flat article layout
# (`article_id`, `link`, `pubDate`, `source_name`, `ai_tag`, ...), so a
# streamed article has its own renderer; `_format_article_item` above is for
# the grouped layout of the news, crypto and market tools.
# ---------------------------------------------------------------------------


# Header line of a `stream_news` answer whose full text was left out. A
# streamed article is delivered once, so asking again with `content=true`
# only helps for articles still to come; one that was already delivered is
# read through `get_news`, whose `id` is the stream's `article_id`.
_STREAM_FULL_TEXT_HINT = (
    "full_text: left out of this result. Pass content=true to include it in later calls. These articles "
    "are not sent again: to read one in full, call get_news with id=<its article_id>."
)


def _format_sentiment_stats(value: Any) -> str | None:
    """Flatten a streamed article's sentiment_stats dict (``{"positive": N,
    ...}``) into a CSV string. Returns ``None`` for missing or empty values
    so ``_append_field`` skips the line entirely."""
    if not isinstance(value, dict) or not value:
        return None

    return ", ".join(f"{key}={val}" for key, val in value.items())


def _format_stream_article(
    article: dict[str, Any], not_in_plan: list[str] | None = None, full_text: bool = True
) -> list[str]:
    """Render one article delivered by the real-time stream. Fields are
    ordered most-useful first (title, url, source, when, summary text);
    less-important fields (media URLs, AI metadata, ids) come later.

    A field that holds a plan notice is not rendered; its name in the
    stream (`content`, `ai_tag`, ...) is added to ``not_in_plan`` (once) so
    ``format_stream`` can report it a single time for the whole answer.
    With ``full_text=False`` the ``content`` field is skipped.
    """
    withheld = [key for key, value in article.items() if _is_plan_notice(value)]
    if withheld:
        if not_in_plan is not None:
            not_in_plan.extend(key for key in withheld if key not in not_in_plan)
        article = {key: value for key, value in article.items() if key not in withheld}

    lines: list[str] = []
    # What and where.
    _append_field(lines, "title", article.get("title"))
    _append_field(lines, "url", article.get("link"))
    _append_field(lines, "source_name", article.get("source_name"))
    _append_field(lines, "published_at", article.get("pubDate"))
    # The article text, in increasing length.
    _append_field(lines, "description", article.get("description"))
    _append_field(lines, "ai_summary", article.get("ai_summary"))
    if full_text:
        _append_field(lines, "content", article.get("content"))
    # Classification and language.
    _append_field(lines, "language", article.get("language"))
    _append_field(lines, "countries", article.get("country"))
    _append_field(lines, "categories", article.get("category"))
    _append_field(lines, "keywords", article.get("keywords"))
    _append_field(lines, "creators", article.get("creator"))
    # Sentiment / AI signals.
    _append_field(lines, "sentiment", article.get("sentiment"))
    _append_field(lines, "sentiment_stats", _format_sentiment_stats(article.get("sentiment_stats")))
    _append_field(lines, "ai_tags", article.get("ai_tag"))
    _append_field(lines, "ai_regions", article.get("ai_region"))
    _append_field(lines, "ai_orgs", article.get("ai_org"))
    # Domain-specific.
    _append_field(lines, "coins", article.get("coin"))
    _append_field(lines, "symbols", article.get("symbol"))
    _append_field(lines, "market_id", article.get("market_id"))
    _append_field(lines, "datatype", article.get("datatype"))
    # Media.
    _append_field(lines, "image_url", article.get("image_url"))
    _append_field(lines, "video_url", article.get("video_url"))
    # Source details (source_name already up top).
    _append_field(lines, "source_id", article.get("source_id"))
    _append_field(lines, "source_url", article.get("source_url"))
    _append_field(lines, "source_icon", article.get("source_icon"))
    _append_field(lines, "source_priority", article.get("source_priority"))
    # Temporal / internal metadata.
    _append_field(lines, "published_timezone", article.get("pubDateTZ"))
    _append_field(lines, "fetched_at", article.get("fetched_at"))
    _append_field(lines, "duplicate", article.get("duplicate"))
    # The article id comes last.
    _append_field(lines, "article_id", article.get("article_id"))

    return lines


def format_registration(data: dict[str, Any]) -> str:
    """Render a `websocket/register` response: the new query's
    ``registration_id`` plus whatever else the server echoes back.
    """
    if data.get("status") != "success":
        return _format_error(data)

    results = (data.get("data", {}) or {}).get("results") or {}
    if not isinstance(results, dict):
        return "Registered, but the response carried no registration details."

    lines = ["registered: yes"]
    _append_field(lines, "registration_id", results.get("registration_id"))
    for key, value in results.items():
        if key == "registration_id":
            continue
        _append_field(lines, key, value)
    return "\n".join(lines)


def format_registered_queries(data: dict[str, Any]) -> str:
    """Render a `websocket/fetch` response: one block per registered
    real-time query.
    """
    if data.get("status") != "success":
        return _format_error(data)

    results = (data.get("data", {}) or {}).get("results") or {}
    queries = results.get("queries") if isinstance(results, dict) else None
    if not queries:
        return "No real-time queries are registered on this account."

    lines = [f"registered_queries: {len(queries)}", ""]
    for index, query in enumerate(queries, 1):
        lines.append(f"Query {index}:")
        if isinstance(query, dict):
            _append_field(lines, "registration_id", query.get("registration_id"))
            for key, value in query.items():
                if key == "registration_id":
                    continue
                _append_field(lines, key, value)
        else:
            _append_field(lines, "value", query)
        lines.append("")
    return "\n".join(lines)


def format_deletion(data: dict[str, Any], registration_id: str) -> str:
    """Render a `websocket/delete` response."""
    if data.get("status") != "success":
        return _format_error(data)
    return f"deleted: yes\nregistration_id: {registration_id}"


def format_stream(
    articles: list[dict[str, Any]],
    registration_id: str,
    stopped_because: str,
    waited_seconds: float,
    error: dict[str, Any] | None = None,
    full_text: bool = True,
) -> str:
    """Render the articles collected by a bounded `stream_news` call.

    ``full_text=False`` leaves each article's ``content`` out and, when
    there was text to leave out, adds a ``full_text:`` header line that
    tells the model how to get it. Measured on the live service: 10
    articles were 35,000 to 50,000 characters with their text and 15,000
    to 18,000 without, and a call can return 50 articles.

    ``stopped_because`` explains why collection ended (``max_articles``,
    ``timeout``, ``connection_closed`` or ``error``) so the model can tell
    "the feed is quiet" from "I hit the cap and there may be more".

    ``error`` is the error envelope of a stream the server refused or
    ended (credits used up, access removed, device limit, a server
    failure). With no article collected the error is the whole answer,
    rendered like every other error of this server. Articles that arrived
    before it are still returned, because they were delivered and charged;
    the error then sits in the header on a ``stream_ended_with:`` line.

    A ``not_in_your_plan:`` header line lists the fields the service
    withheld because of the plan.
    """
    if error is not None and not articles:
        return _format_error(error)

    header = [
        f"registration_id: {registration_id}",
        f"collected_articles: {len(articles)}",
        f"stopped_because: {stopped_because}",
        f"waited_seconds: {round(waited_seconds, 1)}",
    ]
    if error is not None:
        header.append(f"stream_ended_with: {_format_error(error)}")
    if not articles:
        header.append("")
        header.append(
            "No matching articles were published during this window. "
            "The query is still registered — call again to keep listening."
        )
        return "\n".join(header)

    not_in_plan: list[str] = []
    body: list[str] = []
    for index, article in enumerate(articles, 1):
        body.append(f"Article {index}:")
        body.extend(_format_stream_article(article, not_in_plan, full_text))
        body.append("")

    texts = [article.get("content") for article in articles]
    text_left_out = not full_text and any(
        isinstance(text, str) and text.strip() and not _is_plan_notice(text) for text in texts
    )
    if text_left_out:
        header.append(_STREAM_FULL_TEXT_HINT)
    if not_in_plan:
        header.append(f"not_in_your_plan: {', '.join(not_in_plan)}")
    return "\n".join([*header, "", *body])
