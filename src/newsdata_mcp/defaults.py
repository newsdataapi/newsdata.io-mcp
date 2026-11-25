"""Defaults this server adds to article requests, for the model reading the result.

The API's own defaults suit a program: the plan's maximum number of
articles per call (50 on paid plans), each with its full text. For a model
that is far too much to read; one such answer runs to several hundred
thousand characters. So, unless the caller asks otherwise, the article
tools request a short list without the full text.

Nothing is out of reach: `size` raises the number of articles, and a
lookup by `id` or `url`, or `content=true`, returns the full text.
"""
from typing import Any

from .validators import is_set

# Articles per call when the caller does not pass `size`. It is also the
# largest page the Free plan allows, so the default is valid on every plan.
DEFAULT_PAGE_SIZE = 10

# The article field that holds the full text.
FULL_TEXT_FIELD = "content"


def apply_article_defaults(params: dict[str, Any]) -> bool:
    """Adjust the query parameters of an article request, in place.

    Returns ``True`` when the result will carry the articles' full text,
    ``False`` when the full text is left out.

    - A lookup by ``id`` or ``url`` is sent unchanged and returns full
      text. The API accepts nothing next to ``id`` / ``url`` except
      ``from_date`` and ``to_date``, so no default may be added to it.
    - Any other request gets ``size=DEFAULT_PAGE_SIZE`` when ``size`` was
      not passed.
    - Unless ``content`` is true, ``content`` is added to ``exclude_field``
      so the API does not send the full text at all. ``exclude_field``
      works on every plan; the ``content`` parameter itself is refused on
      the Free plan, so it cannot be used for this.
    """
    if is_set(params.get("id")) or is_set(params.get("url")):
        return True

    if not is_set(params.get("size")):
        params["size"] = DEFAULT_PAGE_SIZE

    if params.get("content") in (True, 1):
        return True

    excluded = params.get("exclude_field")
    if isinstance(excluded, str):
        names = [name.strip() for name in excluded.split(",") if name.strip()]
    elif isinstance(excluded, list):
        names = [str(name).strip() for name in excluded if name and str(name).strip()]
    else:
        names = []
    if FULL_TEXT_FIELD not in {name.lower() for name in names}:
        names.append(FULL_TEXT_FIELD)
    params["exclude_field"] = ",".join(names)
    return False
