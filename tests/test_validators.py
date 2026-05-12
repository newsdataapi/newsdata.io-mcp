"""Tests for the client-side mutex-group validator.

These tests are pure-Python — no async, no HTTP — because the validator
returns a string instead of raising and doesn't touch the network.
"""
import pytest

from newsdata_mcp.validators import (
    MUTEX_GROUPS,
    check_mutex_groups,
    check_sentiment_score_requires_sentiment,
)

# ---------- No-violation cases ----------

def test_empty_kwargs_no_violation():
    assert check_mutex_groups({}) is None


def test_all_none_values_no_violation():
    assert check_mutex_groups({
        "q": None,
        "q_in_title": None,
        "q_in_meta": None,
        "country": None,
        "exclude_country": None,
    }) is None


def test_one_per_group_no_violation():
    """A legal combination: one member per group, nothing conflicts."""
    assert check_mutex_groups({
        "q": "bitcoin",
        "country": "us",
        "category": "technology",
        "language": "en",
        "domain": "reuters.com",
    }) is None


def test_unknown_kwargs_ignored():
    """Keys not in any mutex group are passed through without effect."""
    assert check_mutex_groups({
        "q": "bitcoin",
        "size": 10,
        "timezone": "UTC",
        "completely_unknown_param": "value",
    }) is None


# ---------- Group 1: q / q_in_title / q_in_meta ----------

def test_q_and_q_in_title_conflict():
    err = check_mutex_groups({"q": "a", "q_in_title": "b"})
    assert err is not None
    assert "'q'" in err
    assert "'q_in_title'" in err


def test_q_and_q_in_meta_conflict():
    err = check_mutex_groups({"q": "a", "q_in_meta": "b"})
    assert err is not None
    assert "'q'" in err
    assert "'q_in_meta'" in err


def test_q_in_title_and_q_in_meta_conflict():
    err = check_mutex_groups({"q_in_title": "a", "q_in_meta": "b"})
    assert err is not None
    assert "'q_in_title'" in err
    assert "'q_in_meta'" in err


def test_all_three_q_modes_conflict():
    err = check_mutex_groups({"q": "a", "q_in_title": "b", "q_in_meta": "c"})
    assert err is not None
    for name in ("'q'", "'q_in_title'", "'q_in_meta'"):
        assert name in err


# ---------- Groups 2-4: simple include/exclude pairs ----------

@pytest.mark.parametrize(
    "kwargs,expected_names",
    [
        (
            {"country": "us", "exclude_country": "gb"},
            ["'country'", "'exclude_country'"],
        ),
        (
            {"category": "tech", "exclude_category": "sports"},
            ["'category'", "'exclude_category'"],
        ),
        (
            {"language": "en", "exclude_language": "fr"},
            ["'language'", "'exclude_language'"],
        ),
    ],
)
def test_include_exclude_pairs_conflict(kwargs, expected_names):
    err = check_mutex_groups(kwargs)
    assert err is not None
    for name in expected_names:
        assert name in err


# ---------- Group 5: three-way domain mutex ----------

def test_domain_and_domainurl_conflict():
    err = check_mutex_groups({"domain": "x", "domainurl": "y.com"})
    assert err is not None


def test_domain_and_exclude_domain_conflict():
    err = check_mutex_groups({"domain": "x", "exclude_domain": "y"})
    assert err is not None


def test_domainurl_and_exclude_domain_conflict():
    err = check_mutex_groups({"domainurl": "y.com", "exclude_domain": "z"})
    assert err is not None


def test_all_three_domain_modes_conflict():
    err = check_mutex_groups({
        "domain": "x",
        "domainurl": "y.com",
        "exclude_domain": "z",
    })
    assert err is not None
    for name in ("'domain'", "'domainurl'", "'exclude_domain'"):
        assert name in err


def test_mutex_groups_includes_three_way_domain():
    """Regression: the official SDK enforces a three-way domain mutex.
    Earlier MCP docstrings only documented a two-way exclusion."""
    domain_group = next(g for g in MUTEX_GROUPS if "domain" in g)
    assert "domain" in domain_group
    assert "domainurl" in domain_group
    assert "exclude_domain" in domain_group


# ---------- Error message shape ----------

def test_error_message_format_names_conflict_and_full_group():
    err = check_mutex_groups({"q": "a", "q_in_title": "b"})
    assert err is not None
    # Names what conflicted.
    assert "Cannot combine mutually exclusive parameters" in err
    # Tells the LLM what the full set of options was.
    assert "Pass only one of" in err
    # The whole group is listed in the "allowed" clause, including the
    # member that wasn't passed.
    assert "'q_in_meta'" in err
    # Explicit fix at the end.
    assert "Omit the others" in err


def test_error_message_uses_python_kwarg_names_not_wire_names():
    """The LLM passes Python kwarg names; the error must reference those,
    not NewsData's wire names (qInTitle, excludecountry, ...)."""
    err = check_mutex_groups({"country": "us", "exclude_country": "gb"})
    assert err is not None
    # Python kwarg name appears.
    assert "'exclude_country'" in err
    # Wire-name form must NOT appear.
    assert "excludecountry" not in err


# ---------- First-group-wins ordering ----------

def test_first_violated_group_is_reported_when_multiple_violate():
    """If two groups both violate, only the first (in MUTEX_GROUPS order)
    is reported. The LLM fixes that one and retries; if a second violation
    is still present, the next call surfaces it. Trying to bundle all
    violations into one message makes the parse harder."""
    err = check_mutex_groups({
        "q": "a", "q_in_title": "b",
        "country": "us", "exclude_country": "gb",
    })
    assert err is not None
    # First group (q*) is reported; country/exclude_country pair isn't
    # mentioned in the same message.
    assert "'q'" in err
    assert "'country'" not in err


# ---------- check_sentiment_score_requires_sentiment ----------

def test_sentiment_score_alone_returns_error():
    err = check_sentiment_score_requires_sentiment({"sentiment_score": 50})
    assert err is not None
    assert "'sentiment_score'" in err
    assert "'sentiment'" in err


def test_sentiment_score_with_sentiment_returns_none():
    assert check_sentiment_score_requires_sentiment({
        "sentiment_score": 50,
        "sentiment": "positive",
    }) is None


def test_sentiment_alone_returns_none():
    """`sentiment` without `sentiment_score` is always legal."""
    assert check_sentiment_score_requires_sentiment({"sentiment": "positive"}) is None


def test_neither_sentiment_nor_score_returns_none():
    assert check_sentiment_score_requires_sentiment({}) is None
    assert check_sentiment_score_requires_sentiment({"q": "bitcoin"}) is None


def test_sentiment_score_zero_still_triggers_check():
    """`0` is a valid threshold and must trigger the check if `sentiment`
    is missing. Tests that `is not None` (not truthiness) is used."""
    err = check_sentiment_score_requires_sentiment({"sentiment_score": 0})
    assert err is not None


def test_sentiment_score_error_message_suggests_concrete_fix():
    """Error message must name the labels the LLM can pass."""
    err = check_sentiment_score_requires_sentiment({"sentiment_score": 50})
    assert err is not None
    assert "'positive'" in err
    assert "'negative'" in err
    assert "'neutral'" in err
