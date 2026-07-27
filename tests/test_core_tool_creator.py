from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_reload():
    with patch('core.plugin_base.reload_plugins'), \
         patch('core.plugin_base.get_registry', return_value={}), \
         patch('core.plugin_base.get_all_tools', return_value=([], {})):
        yield


@pytest.fixture
def mock_verify_ok():
    with patch('core.tool_creator._verify_and_load', return_value=None):
        yield


@pytest.fixture
def temp_plugin_dir(tmp_path, monkeypatch):
    plugin_dir = tmp_path / 'plugins'
    plugin_dir.mkdir()
    monkeypatch.setattr('core.tool_creator.PLUGIN_DIR', plugin_dir)
    return plugin_dir


class TestCreateTool:
    def test_creates_valid_tool(self, temp_plugin_dir, mock_reload, mock_verify_ok):
        from core.tool_creator import create_tool
        result = create_tool(
            'hello_world',
            'Sagt Hallo',
            {'name': {'type': 'string', 'description': 'Der Name'}},
            'return f"Hallo, {name}!"',
        )
        assert '✅' in result, result
        assert (temp_plugin_dir / 'hello_world.py').exists()

    def test_rejects_invalid_name(self, temp_plugin_dir, mock_reload):
        from core.tool_creator import create_tool
        result = create_tool(
            'invalid name!',
            'test',
            {'x': {'type': 'string'}},
            'return x',
        )
        assert '❌' in result

    def test_rejects_core_tool_name(self, temp_plugin_dir, mock_reload):
        from core.tool_creator import create_tool
        result = create_tool(
            'think',
            'test',
            {'x': {'type': 'string'}},
            'return x',
        )
        assert '❌' in result

    def test_rejects_short_description(self, temp_plugin_dir, mock_reload):
        from core.tool_creator import create_tool
        result = create_tool(
            'test_tool',
            'abc',
            {'x': {'type': 'string'}},
            'return x',
        )
        assert '❌' in result

    def test_rejects_bad_parameters(self, temp_plugin_dir, mock_reload):
        from core.tool_creator import create_tool
        result = create_tool(
            'test_tool',
            'valid description',
            'not a dict',
            'return x',
        )
        assert '❌' in result

    def test_rejects_forbidden_import(self, temp_plugin_dir, mock_reload):
        from core.tool_creator import create_tool
        result = create_tool(
            'test_tool',
            'valid description',
            {'x': {'type': 'string'}},
            'import subprocess\nreturn x',
        )
        assert '❌' in result
        assert 'subprocess' in result

    def test_rejects_syntax_error(self, temp_plugin_dir, mock_reload):
        from core.tool_creator import create_tool
        result = create_tool(
            'test_tool',
            'valid description',
            {'x': {'type': 'string'}},
            'this is not valid python {{{',
        )
        assert '❌' in result
        assert 'Syntax' in result

    def test_rejects_eval_call(self, temp_plugin_dir, mock_reload):
        from core.tool_creator import create_tool
        result = create_tool(
            'test_tool',
            'valid description',
            {'x': {'type': 'string'}},
            'return eval(x)',
        )
        assert '❌' in result

    def test_rejects_duplicate_name(self, temp_plugin_dir, mock_reload):
        from core.tool_creator import create_tool
        (temp_plugin_dir / 'my_tool.py').write_text('# existing')
        result = create_tool('my_tool', 'another desc', {'x': {'type': 'string'}}, 'return x')
        assert '❌' in result
        assert 'existiert bereits' in result


class TestDeleteTool:
    def test_deletes_created_tool(self, temp_plugin_dir, mock_reload):
        from core.tool_creator import delete_tool
        (temp_plugin_dir / 'del_me.py').write_text('# test')
        result = delete_tool('del_me')
        assert '🗑' in result
        assert not (temp_plugin_dir / 'del_me.py').exists()

    def test_rejects_deleting_nonexistent(self, temp_plugin_dir, mock_reload):
        from core.tool_creator import delete_tool
        result = delete_tool('nonexistent')
        assert '❌' in result

    def test_rejects_deleting_system_plugin(self, temp_plugin_dir, mock_reload):
        from core.tool_creator import delete_tool
        (temp_plugin_dir / 'system.py').write_text('# system plugin')
        result = delete_tool('system')
        assert '❌' in result


class TestListCreatedTools:
    def test_returns_empty_initially(self, temp_plugin_dir, mock_reload):
        from core.tool_creator import list_created_tools
        assert list_created_tools() == []

    def test_lists_created_tools(self, temp_plugin_dir, mock_reload):
        from core.tool_creator import list_created_tools
        (temp_plugin_dir / 'tool_a.py').write_text('TOOL_SCHEMA = True\nTOOLS = []')
        (temp_plugin_dir / 'tool_b.py').write_text('TOOL_SCHEMA = True\nTOOLS = []')
        tools = list_created_tools()
        assert 'tool_a' in tools
        assert 'tool_b' in tools

    def test_excludes_system_plugins(self, temp_plugin_dir, mock_reload):
        from core.tool_creator import list_created_tools
        (temp_plugin_dir / 'email.py').write_text('# email')
        (temp_plugin_dir / 'my_tool.py').write_text('TOOL_SCHEMA = True\nTOOLS = []')
        tools = list_created_tools()
        assert 'email' not in tools
        assert 'my_tool' in tools


class TestGeneratePlugin:
    def test_generates_valid_python(self, temp_plugin_dir, mock_reload):
        from core.tool_creator import _generate_plugin
        code = _generate_plugin(
            'greeter', 'Says hello',
            {'name': {'type': 'string', 'description': 'The name'}},
            'return f"Hi {name}!"',
        )
        assert 'greeter' in code
        assert 'Hi {name}!' in code
        assert 'TOOL_SCHEMA = True' in code
        assert 'TOOL_MAP' in code
        compile(code, '<test>', 'exec')


class TestValidate:
    def test_accepts_valid_input(self, temp_plugin_dir, mock_reload):
        from core.tool_creator import _validate
        error = _validate(
            'valid_tool', 'A valid description',
            {'param1': {'type': 'string', 'description': 'test'}},
            'return param1',
        )
        assert error is None

    def test_rejects_empty_code(self, temp_plugin_dir, mock_reload):
        from core.tool_creator import _validate
        error = _validate(
            'test', 'valid description',
            {'x': {'type': 'string'}},
            '',
        )
        assert error is not None


class TestVerifyAndLoad:
    def test_returns_none_on_success(self, temp_plugin_dir, mock_reload):
        with patch('core.plugin_base.get_registry', return_value={'test_tool': object()}), \
             patch('core.plugin_base.get_all_tools',
                   return_value=([{'function': {'name': 'test_tool'}}], {})):
            from core.tool_creator import _verify_and_load
            plugin_path = temp_plugin_dir / 'test_tool.py'
            plugin_path.write_text('# test')
            result = _verify_and_load(plugin_path, 'test_tool')
            assert result is None

    def test_returns_error_for_unregistered(self, temp_plugin_dir, mock_reload):
        from core.tool_creator import _verify_and_load
        plugin_path = temp_plugin_dir / 'unknown_tool.py'
        plugin_path.write_text('# test')
        result = _verify_and_load(plugin_path, 'unknown_tool')
        assert result is not None
        assert 'nicht geladen' in result
