from .._mcp import READ_ONLY_TOOL, mcp
from ..formatters import format_sources
from ..http import fetch
from ..params import (
    CATEGORY_FILTER,
    COUNTRY_FILTER,
    DOMAIN_URL_FILTER,
    LANGUAGE_FILTER,
    PRIORITY_DOMAIN,
)
from ..validators import check_mutex_groups


@mcp.tool(annotations=READ_ONLY_TOOL)
async def get_news_sources(
    country: COUNTRY_FILTER | None = None,
    category: CATEGORY_FILTER | None = None,
    language: LANGUAGE_FILTER | None = None,
    priority_domain: PRIORITY_DOMAIN | None = None,
    domainurl: DOMAIN_URL_FILTER | None = None,
) -> str:
    """
    Use this tool to DISCOVER available news sources, not to fetch articles.
    Use this when the user wants to:
    - Find which sources are available for a country or language.
    - Get source IDs to use in `domain` filter in other tools.
    - Explore what categories a source covers.

    Strict rules: none. All parameters are independent and optional.

    Other guidance:
    - All parameters are optional — omit to get all available sources.
    - Returns source metadata: id, url, priority, languages, countries, categories.
    - Use the returned `source_id` values as input to `domain` in other tools.
    - No pagination — returns all matching sources in one call.

    Examples:
    - `country="in", language="hi"` → Hindi sources in India
    - `category="technology", priority_domain="top"` → top tech sources
    - `domainurl="reuters.com,bbc.com"` → check if specific domains are available
    """
    error = check_mutex_groups(locals())
    if error:
        return f"Error: {error}"

    data = await fetch(
        "sources",
        {
            "country": country,
            "category": category,
            "language": language,
            "prioritydomain": priority_domain,
            "domainurl": domainurl,
        },
    )
    return format_sources(data)
