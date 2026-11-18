"""Tests for the shared `Annotated` parameter types.

These guard the category list that reaches MCP clients in the JSON
Schema. The API is the one that validates a category (and suggests the
right one for a wrong value), so nothing is rejected client-side; the
description is what tells a model which values exist, and it must name
all of them.
"""
from typing import get_args

from newsdata_mcp.params import CATEGORY_FILTER

# The 18 codes NewsData's own filter API returns
# (https://newsdata.io/web/v1/dashboard/searchfilters).
EXPECTED_CATEGORIES = {
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
}


def _category_field():
    return get_args(CATEGORY_FILTER)[1]


def _listed_categories() -> list[str]:
    """The categories named in the description, in the order listed."""
    listed = _category_field().description.split("Allowed: ", 1)[1].split(". ", 1)[0]
    return [name.strip() for name in listed.split(",")]


def test_description_lists_exactly_the_api_categories():
    assert set(_listed_categories()) == EXPECTED_CATEGORIES


def test_listed_categories_are_sorted():
    listed = _listed_categories()
    assert listed == sorted(listed), "keep the list sorted so diffs stay readable"


def test_breaking_is_listed():
    """Regression: `breaking` was missing once, so breaking-news requests
    were rejected before any API call."""
    assert "breaking" in _listed_categories()


def test_no_client_side_pattern_rejects_a_category():
    """A regex here once rejected a valid category the list had not caught
    up with. Categories are validated by the API only."""
    assert not any(hasattr(item, "pattern") and item.pattern for item in _category_field().metadata)
