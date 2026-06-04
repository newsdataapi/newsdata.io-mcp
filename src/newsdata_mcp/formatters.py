"""Pure-text rendering helpers for NewsData responses.

These functions have no network or framework dependencies; they take a
`fetch()`-style envelope (`{"status": "success"|"error", ...}`) and emit
a flat `label: value` text block suitable as an MCP tool return value.

Error envelopes from ``http.fetch`` carry an optional ``status_code``
and ``retry_after``. ``_format_error`` surfaces both in the rendered
string (e.g. ``Error (HTTP 429, retry after 12s): ...``) so the LLM can
parse the failure mode without having to interpret prose.
"""
from typing import Any


def _format_error(envelope: dict[str, Any]) -> str:
    """Render an error envelope as a one-line string.

    Includes HTTP status code and retry-after seconds when those fields
    are present. Format is stable: ``Error[ (HTTP {code}[, retry after
    {N}s])]: {message}``. The optional clause uses parens + comma so the
    LLM can extract `HTTP \\d+` and `retry after \\d+s` with simple regex.

    Special case: status_code 200 is a soft error (the HTTP request
    succeeded but the API returned ``{"status": "error"}``). Showing
    ``HTTP 200`` in front of an error message is confusing — an LLM may
    interpret it as success — so the prefix is omitted for that case.
    """
    message = envelope.get("message", "Unknown error")
    code = envelope.get("status_code")
    retry_after = envelope.get("retry_after")
    parts: list[str] = []
    if code is not None and code != 200:
        parts.append(f"HTTP {code}")
    if retry_after is not None:
        parts.append(f"retry after {retry_after}s")
    suffix = f" ({', '.join(parts)})" if parts else ""
    return f"Error{suffix}: {message}"


def _format_sentiment_stats(value: Any) -> str | None:
    """Flatten NewsData's sentiment_stats dict (``{"positive": N, ...}``)
    into a CSV string. Returns ``None`` for missing or empty values so
    ``_append_field`` skips the line entirely."""
    if not isinstance(value, dict) or not value:
        return None

    return ", ".join(f"{key}={val}" for key, val in value.items())


def _clean_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def _append_field(lines: list[str], label: str, value: Any) -> None:
    if value is None:
        return

    if isinstance(value, bool):
        rendered = "true" if value else "false"
    elif isinstance(value, list):
        rendered = ", ".join([str(item) for item in value if item])
    else:
        rendered = str(value)

    lines.append(f"{label}: {rendered}")


def _format_article_item(article: dict[str, Any]) -> list[str]:
    """Render one article. Fields are ordered most-useful first (title,
    url, source, when, summary text) so the LLM can grasp the article
    from the first few lines; less-important fields (internal tokens,
    media URLs, AI metadata) come later.
    """
    lines: list[str] = []
    # What and where.
    _append_field(lines, "title", article.get("title"))
    _append_field(lines, "url", article.get("link"))
    _append_field(lines, "source_name", article.get("source_name"))
    _append_field(lines, "published_at", article.get("pubDate"))
    # The article text, in increasing length.
    _append_field(lines, "description", article.get("description"))
    _append_field(lines, "summary", article.get("summary"))
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
    # The internal article id is useful only for follow-up calls
    # (article_id=… on the same endpoint); deliberately last.
    _append_field(lines, "article_id", article.get("article_id"))

    return lines


def format_articles(data: dict[str, Any], endpoint_name: str) -> str:
    """Render an article-endpoint response (`/latest`, `/archive`,
    `/crypto`, `/market`). Emits an ``endpoint:`` / ``total_results:`` /
    ``returned_results:`` / ``next_page:`` header followed by one
    ``Article N:`` block per result. The ``next_page`` token is the
    cursor to pass back as ``page=`` on the next call; ``none`` means
    there are no more pages.
    """
    if data.get("status") != "success":
        return _format_error(data)

    inner = data.get("data", {}) or {}
    articles = inner.get("results") or []
    if not articles:
        return f"No {endpoint_name} articles found matching your query."

    total = inner.get("totalResults", len(articles))
    next_page = inner.get("nextPage")

    lines = [
        f"endpoint: {endpoint_name}",
        f"total_results: {total}",
        f"returned_results: {len(articles)}",
        f"next_page: {next_page or 'none'}",
        "",
    ]

    for index, article in enumerate(articles, 1):
        lines.append(f"Article {index}:")
        lines.extend(_format_article_item(article))
        lines.append("")

    return "\n".join(lines)


def format_counts(data: dict[str, Any], endpoint_name: str) -> str:
    """Render a count-endpoint response (`/count`, `/crypto/count`,
    `/market/count`). ``results`` may be either a list of bucket dicts
    (one per ``interval`` slot — e.g. ``{"dateTime": "...", "count": N}``
    when ``interval="hour"`` or ``"day"``) or a single aggregate dict
    (``{"count": N}`` when ``interval="all"`` or omitted). We handle
    both shapes.
    """
    if data.get("status") != "success":
        return _format_error(data)

    inner = data.get("data", {}) or {}
    results = inner.get("results")
    if not results:
        return f"No results found for {endpoint_name} over the given range."

    if isinstance(results, dict):
        total = results.get("count", "n/a")
    else:
        # Match the renderer below: skip non-dict items defensively rather
        # than AttributeError if the API ever returns a mixed-shape list.
        total = sum(
            bucket.get("count", 0)
            for bucket in results
            if isinstance(bucket, dict)
        )

    next_page = inner.get("nextPage")

    lines = [
        f"endpoint: {endpoint_name}",
        f"total_results: {total}",
        f"next_page: {next_page or 'none'}",
        "",
    ]

    if isinstance(results, list):
        lines.append(f"buckets: {len(results)}")
        lines.append("")
        for index, bucket in enumerate(results, 1):
            lines.append(f"Bucket {index}:")
            if isinstance(bucket, dict):
                for key, value in bucket.items():
                    _append_field(lines, key, value)
            else:
                lines.append(f"value: {bucket}")
            lines.append("")
    elif isinstance(results, dict):
        lines.append("aggregate:")
        for key, value in results.items():
            _append_field(lines, key, value)
        lines.append("")
    else:
        lines.append(f"raw_results: {results}")
        lines.append("")

    return "\n".join(lines)


def format_sources(data: dict[str, Any]) -> str:
    """Render the `/sources` endpoint response. Emits an ``endpoint:`` /
    ``total_results:`` / ``returned_results:`` header followed by one
    block per source headed by ``[N] {name}``. Source IDs are the
    values to pass as ``domain=…`` on the article tools.
    """
    if data.get("status") != "success":
        return _format_error(data)

    inner = data.get("data", {}) or {}
    sources = inner.get("results") or []
    if not sources:
        return "No sources found matching your filters."

    total = inner.get("totalResults", len(sources))

    lines = [
        "endpoint: sources",
        f"total_results: {total}",
        f"returned_results: {len(sources)}",
        "",
    ]

    for index, source in enumerate(sources, 1):
        source_id = _clean_text(source.get("id")) or "N/A"
        name = _clean_text(source.get("name")) or source_id
        lines.append(f"[{index}] {name}")
        _append_field(lines, "source_id", source_id)
        _append_field(lines, "source_name", source.get("name"))
        _append_field(lines, "url", source.get("url"))
        _append_field(lines, "icon", source.get("icon"))
        _append_field(lines, "priority", source.get("priority"))
        _append_field(lines, "languages", source.get("language"))
        _append_field(lines, "countries", source.get("country"))
        _append_field(lines, "categories", source.get("category"))
        _append_field(lines, "total_article", source.get("total_article"))
        _append_field(lines, "last_fetch", source.get("last_fetch"))
        _append_field(lines, "description", _clean_text(source.get("description")))
        lines.append("")

    return "\n".join(lines)
