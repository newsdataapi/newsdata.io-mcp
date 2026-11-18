from .._mcp import READ_ONLY_TOOL, mcp
from ..formatters import format_sources
from ..http import fetch
from ..params import (
    CATEGORY_FILTER,
    COUNTRY_FILTER,
    LANGUAGE_FILTER,
    SOURCE_PRIORITY,
    SOURCE_URL_FILTER,
)


@mcp.tool(annotations=READ_ONLY_TOOL, structured_output=False)
async def get_news_sources(
    country: COUNTRY_FILTER = None,
    category: CATEGORY_FILTER = None,
    language: LANGUAGE_FILTER = None,
    source_priority: SOURCE_PRIORITY = None,
    source_url: SOURCE_URL_FILTER = None,
) -> str:
    """
    List the NEWS SOURCES (publishers) NewsData.io collects from. This tool returns sources, not articles.
    Use it to find which sources cover a country, language or category, or to check that a source exists.

    Strict rules: none. All parameters are optional and can be combined.

    Other guidance:
    - Returns at most 100 sources, best-ranked first, with no paging. When more than 100 match they are
      picked at random, so add filters to find a specific source.
    - A source must match every filter you pass; within one filter it may match any of the values.
    - Use a returned source's `url` as `source_url` (or `exclude_source_url`) on the news tools.
    - Each source shows name, url, priority (lower number = higher rank), languages, countries,
      categories, description and article statistics.
    - Cost: 1 credit per call.

    Examples:
    - `country="in", language="hi"`
    - `category="technology", source_priority="top"`
    - `source_url="bbc.com"`
    """
    data = await fetch("sources", dict(locals()))
    return format_sources(data)
