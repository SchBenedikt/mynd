import pytest

from core.plugin_base import Plugin, get_all_tools, load_plugins, normalize_tool_schema, validate_plugin_tools


def test_flat_tool_schema_is_normalized():
    tool = normalize_tool_schema({
        "name": "example",
        "description": "Example",
        "parameters": {"value": {"type": "string"}},
        "required": ["value"],
    })

    assert tool == {
        "type": "function",
        "function": {
            "name": "example",
            "description": "Example",
            "parameters": {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
        },
    }


def test_plugin_validation_rejects_missing_callable():
    plugin = Plugin()
    plugin.name = "broken"
    plugin.tools = [{"name": "missing", "parameters": {}}]
    plugin.tool_map = {}

    with pytest.raises(ValueError, match="no callable implementation"):
        validate_plugin_tools(plugin)


def test_every_loaded_tool_has_canonical_schema_and_callable():
    load_plugins()
    tools, tool_map = get_all_tools()

    assert tools
    for tool in tools:
        assert tool["type"] == "function"
        function = tool["function"]
        assert function["parameters"]["type"] == "object"
        assert callable(tool_map[function["name"]])
