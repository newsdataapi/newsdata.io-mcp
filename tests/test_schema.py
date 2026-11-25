"""Contract tests for what MCP clients see in `tools/list`.

Every model that connects, whichever vendor it comes from, works from the
tool names, descriptions and JSON Schemas listed here. These tests pin
that contract to the NewsData API:

- exactly one tool per endpoint;
- each tool takes exactly the parameters its endpoint accepts, under the
  API's own names (the lists are `FILTERS_MAPPING` in the API's
  `env_file.py`, minus `apikey`);
- schemas use only plain JSON Schema that every client handles.
"""
import re

import httpx
import pytest
import respx
from mcp.server.fastmcp.exceptions import ToolError

from newsdata_mcp import __version__, tools  # noqa: F401 — registers the tools
from newsdata_mcp._mcp import mcp

SEARCH_COMMON = {
    "q",
    "q_in_title",
    "q_in_meta",
    "language",
    "exclude_language",
    "source_url",
    "exclude_source_url",
    "source_priority",
    "from_date",
    "to_date",
    "timeframe",
    "timezone",
    "image",
    "video",
    "content",
    "remove_duplicate",
    "sentiment",
    "tag",
    "id",
    "url",
    "size",
    "page",
    "sort",
    "exclude_field",
}

# The count endpoints take their search endpoint's filters without
# `exclude_field`, `id`, `url` and `timezone`, plus `interval`.
NOT_ON_COUNT = {"exclude_field", "id", "url", "timezone"}

NEWS = SEARCH_COMMON | {
    "country",
    "exclude_country",
    "category",
    "exclude_category",
    "sentiment_score",
    "region",
    "organization",
    "creator",
    "datatype",
}
MARKET = SEARCH_COMMON | {
    "market_id",
    "country",
    "exclude_country",
    "sentiment_score",
    "organization",
    "creator",
    "datatype",
}
CRYPTO = SEARCH_COMMON | {"coin"}

EXPECTED_PARAMETERS = {
    "get_news": NEWS,
    "get_market_news": MARKET,
    "get_crypto_news": CRYPTO,
    "get_news_sources": {"country", "category", "language", "source_priority", "source_url"},
    "get_news_counts": (NEWS - NOT_ON_COUNT) | {"interval"},
    "get_market_counts": (MARKET - NOT_ON_COUNT) | {"interval"},
    "get_crypto_counts": (CRYPTO - NOT_ON_COUNT) | {"interval"},
}

# The real-time (WebSocket) tools. They are not part of the per-endpoint table
# above: `list_realtime_queries`, `delete_realtime_query` and `stream_news` have
# no filters, and `register_realtime_query` sets `news_type` itself.
REALTIME_TOOLS = {"register_realtime_query", "list_realtime_queries", "delete_realtime_query", "stream_news"}

# The filters of the API's `websocket/register` endpoint (`FILTERS_MAPPING` in
# its `env_file.py`), minus `apikey` and `news_type`.
REGISTER_PARAMETERS = {
    "q",
    "q_in_title",
    "q_in_meta",
    "country",
    "exclude_country",
    "category",
    "exclude_category",
    "language",
    "exclude_language",
    "source_url",
    "exclude_source_url",
    "source_priority",
    "timezone",
    "content",
    "image",
    "video",
    "remove_duplicate",
    "tag",
    "sentiment",
    "sentiment_score",
    "region",
    "organization",
    "creator",
    "datatype",
    "exclude_field",
}

# JSON Schema keywords the tool schemas are allowed to use. Anything else
# (`pattern`, `$ref`, `$defs`, `examples`, `format`, ...) is unevenly
# supported across model vendors and must not appear.
ALLOWED_KEYWORDS = {
    "type",
    "properties",
    "required",
    "title",
    "description",
    "default",
    "anyOf",
    "enum",
    "const",
    "items",
    "minimum",
    "maximum",
}


async def _tools_by_name() -> dict:
    return {tool.name: tool for tool in await mcp.list_tools()}


def _schema_keywords(node: object, *, is_properties_map: bool = False) -> set[str]:
    """Collect every JSON Schema keyword used anywhere in a schema.

    The keys of a `properties` object are parameter names, not keywords,
    so they are skipped and only their sub-schemas are walked.
    """
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if not is_properties_map:
                found.add(key)
            found |= _schema_keywords(value, is_properties_map=(key == "properties" and not is_properties_map))
    elif isinstance(node, list):
        for item in node:
            found |= _schema_keywords(item)
    return found


async def test_one_tool_per_endpoint_plus_the_realtime_tools():
    assert set(await _tools_by_name()) == set(EXPECTED_PARAMETERS) | REALTIME_TOOLS


@pytest.mark.parametrize("tool_name", sorted(EXPECTED_PARAMETERS))
async def test_tool_parameters_are_the_endpoint_parameters(tool_name):
    tool = (await _tools_by_name())[tool_name]
    assert set(tool.inputSchema["properties"]) == EXPECTED_PARAMETERS[tool_name]


@pytest.mark.parametrize("tool_name", sorted(EXPECTED_PARAMETERS))
async def test_every_parameter_is_optional(tool_name):
    """No tool has a required parameter, and each one accepts null: models
    in strict function-calling mode send null for what they do not use."""
    tool = (await _tools_by_name())[tool_name]
    assert tool.inputSchema.get("required", []) == []
    for name, schema in tool.inputSchema["properties"].items():
        assert {"type": "null"} in schema.get("anyOf", []), f"{tool_name}.{name} does not accept null"
        assert schema.get("default", "missing") is None, f"{tool_name}.{name} has no null default"


@pytest.mark.parametrize("tool_name", sorted(EXPECTED_PARAMETERS))
async def test_every_parameter_has_a_top_level_description(tool_name):
    """The description must sit on the property itself, not inside an
    `anyOf` branch, so that every client shows it to the model."""
    tool = (await _tools_by_name())[tool_name]
    for name, schema in tool.inputSchema["properties"].items():
        description = schema.get("description")
        assert isinstance(description, str) and description.strip(), f"{tool_name}.{name} has no description"
        for branch in schema.get("anyOf", []):
            assert "description" not in branch, f"{tool_name}.{name} has a description inside anyOf"


@pytest.mark.parametrize("tool_name", sorted(EXPECTED_PARAMETERS))
async def test_schema_uses_only_widely_supported_keywords(tool_name):
    tool = (await _tools_by_name())[tool_name]
    unexpected = _schema_keywords(tool.inputSchema) - ALLOWED_KEYWORDS
    assert not unexpected, f"{tool_name} schema uses {sorted(unexpected)}"


@pytest.mark.parametrize("tool_name", sorted(EXPECTED_PARAMETERS))
async def test_tool_has_a_description_and_no_output_schema(tool_name):
    """Tools return text. An output schema would make the SDK send the
    whole text a second time as `structuredContent`."""
    tool = (await _tools_by_name())[tool_name]
    assert tool.description and tool.description.strip()
    assert tool.outputSchema is None


@pytest.mark.parametrize("tool_name", sorted(EXPECTED_PARAMETERS))
async def test_tool_is_annotated_read_only(tool_name):
    tool = (await _tools_by_name())[tool_name]
    assert tool.annotations is not None
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.destructiveHint is False


def test_server_reports_the_package_version():
    """Clients are told this server's version at initialization, not the
    version of the MCP SDK it is built on."""
    assert mcp._mcp_server.create_initialization_options().server_version == __version__


# ---------------------------------------------------------------------------
# The real call path: `mcp.call_tool` validates the arguments with the
# schema's pydantic model and then runs the tool, as a client request does.
# ---------------------------------------------------------------------------


@respx.mock
async def test_call_tool_accepts_the_shapes_models_send():
    route = respx.get("https://newsdata.io/api/2/news").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": "success",
                "total_results": 1,
                "results": [{"id": "a1", "title": "Hello"}],
                "next_page": None,
            },
        )
    )
    result = await mcp.call_tool(
        "get_news",
        {
            "q": "bitcoin",
            "country": ["us", "gb"],  # a list ...
            "category": "business,technology",  # ... or a comma-separated string
            "image": True,  # a boolean ...
            "remove_duplicate": 1,  # ... or 1/0
            "timeframe": 24,
            "size": 10,
            "page": "1792649700000000000",
            "sentiment": None,  # null for a parameter that is not used
            "exclude_field": "",  # or an empty string
        },
    )
    assert dict(route.calls[0].request.url.params) == {
        "q": "bitcoin",
        "country": "us,gb",
        "category": "business,technology",
        "image": "1",
        "remove_duplicate": "1",
        "timeframe": "24",
        "size": "10",
        "page": "1792649700000000000",
        "exclude_field": "content",  # a search leaves the full text out
    }
    # One text block, and nothing else: no structured copy of the text.
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0].type == "text"
    assert result[0].text.startswith("endpoint: news")
    assert "title: Hello" in result[0].text


# ---------------------------------------------------------------------------
# Unknown argument names. FastMCP would drop them and run the tool without
# them; the server refuses them instead, before any request, and lists the
# names the tool does have.
# ---------------------------------------------------------------------------


def _valid_names(error_text: str) -> set[str]:
    return set(error_text.split("Valid parameters: ", 1)[1].rstrip(".").split(", "))


@respx.mock(assert_all_called=False)
async def test_unknown_parameter_is_refused_with_the_valid_names():
    result = await mcp.call_tool("get_news", {"keyword": "election", "size": 1})
    assert isinstance(result, list)
    text = result[0].text
    assert text.startswith(
        "Error: Unknown parameter 'keyword' for get_news. Valid parameters: q, q_in_title, q_in_meta, "
    )
    assert text.endswith(".")
    assert _valid_names(text) == EXPECTED_PARAMETERS["get_news"]
    # Nothing was sent to the API.
    assert len(respx.calls) == 0


@respx.mock(assert_all_called=False)
async def test_several_unknown_parameters_are_all_named():
    result = await mcp.call_tool("get_news", {"qInTitle": "x", "q": "y", "domain": "bbc"})
    assert isinstance(result, list)
    assert result[0].text.startswith("Error: Unknown parameters 'qInTitle', 'domain' for get_news. ")
    assert len(respx.calls) == 0


@pytest.mark.parametrize("tool_name", sorted(EXPECTED_PARAMETERS))
@respx.mock(assert_all_called=False)
async def test_every_tool_refuses_unknown_parameters(tool_name):
    result = await mcp.call_tool(tool_name, {"not_a_parameter": 1})
    assert isinstance(result, list)
    text = result[0].text
    assert text.startswith(f"Error: Unknown parameter 'not_a_parameter' for {tool_name}. ")
    assert _valid_names(text) == EXPECTED_PARAMETERS[tool_name]
    assert len(respx.calls) == 0


@respx.mock(assert_all_called=False)
async def test_apikey_from_the_model_never_reaches_the_api():
    """The API reads `apikey` from the query string before the header, so
    an `apikey` argument must not be passed on. It is not a parameter of
    any tool, so it is refused like any other unknown name."""
    result = await mcp.call_tool("get_news", {"q": "bitcoin", "apikey": "pub_someone_elses_key"})
    assert isinstance(result, list)
    assert result[0].text.startswith("Error: Unknown parameter 'apikey' for get_news. ")
    assert len(respx.calls) == 0


async def test_unknown_tool_name_is_still_reported_by_fastmcp():
    with pytest.raises(ToolError, match="Unknown tool: get_latest_news"):
        await mcp.call_tool("get_latest_news", {"q": "x"})


# ---------------------------------------------------------------------------
# Real-time tools. Their parameter names are part of a released interface
# and must not change by accident.
# ---------------------------------------------------------------------------


async def test_realtime_register_keeps_its_parameter_names():
    tool = (await _tools_by_name())["register_realtime_query"]
    assert set(tool.inputSchema["properties"]) == REGISTER_PARAMETERS
    assert tool.inputSchema.get("required", []) == []
    for name, schema in tool.inputSchema["properties"].items():
        assert isinstance(schema.get("description"), str), f"register_realtime_query.{name} has no description"


async def test_realtime_tools_that_need_an_id_require_it():
    by_name = await _tools_by_name()
    assert set(by_name["list_realtime_queries"].inputSchema.get("properties", {})) == set()
    assert by_name["delete_realtime_query"].inputSchema["required"] == ["registration_id"]
    assert set(by_name["stream_news"].inputSchema["properties"]) == {
        "registration_id",
        "max_articles",
        "wait_seconds",
        "content",
    }
    assert by_name["stream_news"].inputSchema["required"] == ["registration_id"]


@pytest.mark.parametrize("tool_name", sorted(REALTIME_TOOLS))
async def test_every_realtime_parameter_has_a_top_level_description(tool_name):
    """`max_articles` and `wait_seconds` of `stream_news` once had none: a
    model saw two bare numbers and had to find their limits in the prose."""
    tool = (await _tools_by_name())[tool_name]
    for name, schema in tool.inputSchema.get("properties", {}).items():
        description = schema.get("description")
        assert isinstance(description, str) and description.strip(), f"{tool_name}.{name} has no description"


async def test_stream_news_leaves_the_full_text_out_unless_asked():
    properties = (await _tools_by_name())["stream_news"].inputSchema["properties"]
    assert properties["content"]["type"] == "boolean"
    assert properties["content"]["default"] is False


@pytest.mark.parametrize("tool_name", ["get_news", "get_crypto_news", "get_market_news"])
async def test_lookup_by_id_or_url_is_described_as_returning_the_full_text(tool_name):
    """Two models reading only the tool list could not tell whether a lookup
    by `id` or `url` includes the text that a list leaves out."""
    properties = (await _tools_by_name())[tool_name].inputSchema["properties"]
    assert "full text" in properties["id"]["description"]
    assert "full text" in properties["url"]["description"]


async def test_no_example_registration_id_is_shorter_than_the_schema_allows():
    """`registration_id` must be 32 characters; an example like "a1b2c3"
    would be refused if a model copied it."""
    description = (await _tools_by_name())["stream_news"].description
    examples = re.findall(r'registration_id="([^"]+)"', description)
    assert examples, "stream_news should show an example call"
    assert all(len(example) == 32 for example in examples), examples


async def test_no_tool_has_an_output_schema():
    for tool in await mcp.list_tools():
        assert tool.outputSchema is None, f"{tool.name} would send its text twice"


async def test_only_the_two_realtime_write_tools_are_not_read_only():
    by_name = await _tools_by_name()
    not_read_only = {name for name, tool in by_name.items() if not tool.annotations.readOnlyHint}
    assert not_read_only == {"register_realtime_query", "delete_realtime_query"}
    assert by_name["delete_realtime_query"].annotations.destructiveHint is True
    assert by_name["register_realtime_query"].annotations.destructiveHint is False


@respx.mock(assert_all_called=False)
async def test_realtime_tools_refuse_unknown_parameters_too():
    result = await mcp.call_tool("list_realtime_queries", {"q": "bitcoin"})
    assert isinstance(result, list)
    assert result[0].text == "Error: Unknown parameter 'q' for list_realtime_queries. This tool takes no parameters."

    result = await mcp.call_tool("stream_news", {"registration_id": "a" * 32, "limit": 5})
    assert isinstance(result, list)
    assert result[0].text == (
        "Error: Unknown parameter 'limit' for stream_news. "
        "Valid parameters: registration_id, max_articles, wait_seconds, content."
    )
    assert len(respx.calls) == 0
