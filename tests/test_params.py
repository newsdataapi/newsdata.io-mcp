"""Tests for the shared `Annotated` parameter types.

These guard the value enums that reach MCP clients as JSON Schema. A code
missing here is rejected client-side and never reaches the API, so drift
against NewsData's real filter list is a silent loss of functionality.
"""
import re
from typing import get_args

from newsdata_mcp.params import CATEGORY_CODE, CATEGORY_FILTER

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


def _category_pattern() -> str:
    meta = get_args(CATEGORY_FILTER)[1]
    return meta.metadata[0].pattern


def test_category_codes_match_the_api():
    assert set(get_args(CATEGORY_CODE)) == EXPECTED_CATEGORIES


def test_category_codes_are_sorted():
    codes = list(get_args(CATEGORY_CODE))
    assert codes == sorted(codes), "keep the list sorted so diffs stay readable"


def test_breaking_is_accepted():
    """Regression: `breaking` was missing, so breaking-news requests were
    rejected before any API call."""
    assert "breaking" in get_args(CATEGORY_CODE)
    assert re.match(_category_pattern(), "breaking")


def test_every_code_passes_the_csv_pattern():
    pattern = _category_pattern()
    for code in get_args(CATEGORY_CODE):
        assert re.match(pattern, code), f"{code} rejected by its own pattern"
    assert re.match(pattern, "breaking,top,world")


def test_unknown_codes_are_still_rejected():
    pattern = _category_pattern()
    for bad in ("nonsense", "Breaking", "breaking,", "breaking,nonsense", ""):
        assert not re.match(pattern, bad), f"{bad!r} should not validate"


def test_description_lists_every_code():
    # The pattern lives in FieldInfo.metadata; the prose sits on the
    # FieldInfo itself. Both reach clients, so both must stay in sync.
    description = get_args(CATEGORY_FILTER)[1].description
    for code in get_args(CATEGORY_CODE):
        assert code in description, f"{code} missing from the description"
