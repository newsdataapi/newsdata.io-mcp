"""Unit tests for the defaults the article tools add to a request."""
from newsdata_mcp.defaults import DEFAULT_PAGE_SIZE, apply_article_defaults


def _args(**given):
    """Tool arguments as a tool body sees them: every parameter present,
    None unless passed."""
    return {"q": None, "id": None, "url": None, "size": None, "content": None, "exclude_field": None, **given}


def test_default_page_size_is_valid_on_the_free_plan():
    """The Free plan allows at most 10 articles per call."""
    assert DEFAULT_PAGE_SIZE == 10


def test_plain_search_gets_a_short_list_without_full_text():
    params = _args(q="bitcoin")
    assert apply_article_defaults(params) is False
    assert params["size"] == 10
    assert params["exclude_field"] == "content"
    assert params["q"] == "bitcoin"


def test_size_from_the_caller_is_kept():
    params = _args(q="bitcoin", size=50)
    apply_article_defaults(params)
    assert params["size"] == 50


def test_lookup_by_id_is_left_untouched_and_carries_full_text():
    params = _args(id="aabbccddeeff00112233445566778899")
    assert apply_article_defaults(params) is True
    assert params == _args(id="aabbccddeeff00112233445566778899")


def test_lookup_by_id_list_is_left_untouched():
    params = _args(id=["a" * 32, "b" * 32])
    assert apply_article_defaults(params) is True
    assert params["size"] is None
    assert params["exclude_field"] is None


def test_lookup_by_url_is_left_untouched_and_carries_full_text():
    params = _args(url="https://example.com/a")
    assert apply_article_defaults(params) is True
    assert params == _args(url="https://example.com/a")


def test_blank_id_is_not_a_lookup():
    params = _args(q="bitcoin", id="", url="   ")
    assert apply_article_defaults(params) is False
    assert params["size"] == 10


def test_content_true_keeps_full_text_but_still_shortens_the_list():
    for flag in (True, 1):
        params = _args(q="bitcoin", content=flag)
        assert apply_article_defaults(params) is True
        assert params["size"] == 10
        assert params["exclude_field"] is None


def test_content_false_does_not_bring_full_text_back():
    for flag in (False, 0):
        params = _args(q="bitcoin", content=flag)
        assert apply_article_defaults(params) is False
        assert params["exclude_field"] == "content"


def test_exclude_field_string_from_the_caller_is_extended():
    params = _args(exclude_field="media, ai.summary")
    apply_article_defaults(params)
    assert params["exclude_field"] == "media,ai.summary,content"


def test_exclude_field_list_from_the_caller_is_extended():
    params = _args(exclude_field=["media", "", None, "ai"])
    apply_article_defaults(params)
    assert params["exclude_field"] == "media,ai,content"


def test_content_already_excluded_is_not_added_twice():
    params = _args(exclude_field="keyword,CONTENT")
    apply_article_defaults(params)
    assert params["exclude_field"] == "keyword,CONTENT"
