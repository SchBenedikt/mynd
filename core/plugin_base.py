import importlib
import json
import logging
import re
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

PLUGIN_DIR = Path(__file__).resolve().parents[1] / 'data' / 'plugins'
PLUGIN_INSTALL_DIR = PLUGIN_DIR  # same dir for now


class Plugin:
    name = ""
    description = ""
    version = "0.1.0"
    config_schema = {}  # {key: {"label": str, "type": "text|password|select", "options": [], "default": ""}}
    tools = []
    tool_map = {}

    def __init__(self, config=None):
        self.config = config or {}

    def on_load(self):
        pass

    def on_unload(self):
        pass


def normalize_tool_schema(tool):
    """Return one canonical OpenAI-compatible function-tool definition."""
    if not isinstance(tool, dict):
        raise ValueError("Tool definition must be an object")

    if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
        function = dict(tool["function"])
    else:
        function = {
            "name": tool.get("name"),
            "description": tool.get("description", ""),
            "parameters": {
                "type": "object",
                "properties": tool.get("parameters", {}),
                "required": tool.get("required", []),
            },
        }

    name = function.get("name")
    if not isinstance(name, str) or not TOOL_NAME_RE.fullmatch(name):
        raise ValueError(f"Invalid tool name: {name!r}")
    if not isinstance(function.get("description", ""), str):
        raise ValueError(f"Tool {name!r} has an invalid description")

    parameters = function.get("parameters") or {}
    if not isinstance(parameters, dict):
        raise ValueError(f"Tool {name!r} parameters must be an object")
    if "type" not in parameters:
        parameters = {
            "type": "object",
            "properties": parameters,
            "required": function.get("required", []),
        }
    if parameters.get("type") != "object":
        raise ValueError(f"Tool {name!r} parameters.type must be 'object'")
    if not isinstance(parameters.get("properties", {}), dict):
        raise ValueError(f"Tool {name!r} parameters.properties must be an object")
    required = parameters.get("required", [])
    if not isinstance(required, list) or not all(isinstance(item, str) for item in required):
        raise ValueError(f"Tool {name!r} parameters.required must be a string array")
    unknown_required = set(required) - set(parameters.get("properties", {}))
    if unknown_required:
        raise ValueError(f"Tool {name!r} requires unknown properties: {sorted(unknown_required)}")

    function["parameters"] = {
        "type": "object",
        "properties": parameters.get("properties", {}),
        "required": required,
    }
    return {"type": "function", "function": function}


def validate_plugin_tools(plugin):
    normalized = [normalize_tool_schema(tool) for tool in plugin.tools]
    names = [tool["function"]["name"] for tool in normalized]
    if len(names) != len(set(names)):
        raise ValueError(f"Plugin {plugin.name!r} defines duplicate tool names")
    missing = [name for name in names if not callable(plugin.tool_map.get(name))]
    if missing:
        raise ValueError(f"Plugin {plugin.name!r} has no callable implementation for: {missing}")
    plugin.tools = normalized
    plugin.tool_map = {name: plugin.tool_map[name] for name in names}
    return plugin


_registry = {}
_config_cache = {}


def get_plugin_config():
    cf = PLUGIN_DIR / 'plugin_config.json'
    if cf.exists():
        try:
            return json.loads(cf.read_text())
        except Exception:
            pass
    return {}


def save_plugin_config(cfg):
    cf = PLUGIN_DIR / 'plugin_config.json'
    cf.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
    _config_cache.clear()
    return cfg


def load_plugins():
    global _registry, _config_cache
    _registry = {}
    _config_cache = get_plugin_config()
    state = get_plugin_state()
    plugins_file = PLUGIN_DIR / '__init__.py'
    plugins_file.write_text('')
    sys.path.insert(0, str(PLUGIN_DIR.parent))
    for f in sorted(PLUGIN_DIR.glob('*.py')):
        if f.name in ('__init__.py', 'plugin_config.json', 'plugin_state.json'):
            continue
        mod_name = f'data.plugins.{f.stem}'
        try:
            mod = importlib.import_module(mod_name)
            # Find Plugin subclasses defined in THIS module (not the imported base class)
            plugin_cls = None
            for attr_name in dir(mod):
                obj = getattr(mod, attr_name, None)
                if (isinstance(obj, type) and issubclass(obj, Plugin)
                        and obj is not Plugin
                        and getattr(obj, 'name', '')):
                    plugin_cls = obj
                    break
            if plugin_cls is None:
                legacy_tools = list(getattr(mod, 'TOOLS', []))
                legacy_map = dict(getattr(mod, 'TOOL_MAP', {}))
                if not legacy_tools:
                    continue
                name = getattr(mod, 'PLUGIN_NAME', f.stem)
                if not _is_enabled(name, state):
                    logger.info(f"Plugin deaktiviert: {name}")
                    _registry[name] = None
                    continue
                desc = getattr(mod, 'PLUGIN_DESC', '')
                legacy_config_schema = getattr(mod, 'PLUGIN_CONFIG_SCHEMA', {})
                plugin = type('LegacyPlugin', (Plugin,), {
                    'name': name,
                    'description': desc,
                    'tools': legacy_tools,
                    'tool_map': legacy_map,
                    'config_schema': legacy_config_schema,
                })
                instance = plugin(config=_config_cache.get(name, {}))
                validate_plugin_tools(instance)
                _registry[name] = instance
                logger.info(f"Plugin geladen (Legacy): {name}")
            else:
                name = plugin_cls.name
                if not _is_enabled(name, state):
                    logger.info(f"Plugin deaktiviert: {name}")
                    _registry[name] = None
                    continue
                instance = plugin_cls(config=_config_cache.get(name, {}))
                validate_plugin_tools(instance)
                instance.on_load()
                _registry[name] = instance
                logger.info(f"Plugin geladen: {instance.name} v{instance.version}")
        except Exception as e:
            logger.warning(f"Plugin {f.stem} nicht geladen: {e}")
    return _registry


def get_registry():
    return _registry


def get_plugin(name):
    return _registry.get(name)


def get_all_tools():
    tools = []
    tool_map = {}
    for name, plugin in _registry.items():
        if plugin is None:
            continue
        tools.extend(plugin.tools)
        tool_map.update(plugin.tool_map)
    return tools, tool_map


def get_plugin_state():
    f = PLUGIN_DIR / 'plugin_state.json'
    if f.exists():
        try:
            return json.loads(f.read_text())
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            pass
    return {}

def save_plugin_state(state):
    (PLUGIN_DIR / 'plugin_state.json').write_text(json.dumps(state, indent=2, ensure_ascii=False))

def _is_enabled(name, state):
    return state.get(name, {}).get('enabled', True)

def get_all_plugins():
    state = get_plugin_state()
    result = []
    for name, plugin in _registry.items():
        s = state.get(name, {})
        if plugin is None:
            result.append({'name': name, 'description': '', 'version': '', 'tools': [], 'tool_count': 0, 'enabled': False})
        else:
            result.append({
                'name': name,
                'description': getattr(plugin, 'description', ''),
                'version': getattr(plugin, 'version', ''),
                'tools': [t.get('function', {}).get('name', '') for t in getattr(plugin, 'tools', [])],
                'tool_count': len(getattr(plugin, 'tools', [])),
                'enabled': s.get('enabled', True),
            })
    return result

def set_plugin_enabled(name, enabled):
    state = get_plugin_state()
    if name not in state:
        state[name] = {}
    state[name]['enabled'] = enabled
    save_plugin_state(state)
    reload_plugins()

def uninstall_plugin(name):
    state = get_plugin_state()
    state.pop(name, None)
    save_plugin_state(state)
    f = PLUGIN_DIR / f'{name}.py'
    if f.exists():
        f.unlink()
    reload_plugins()

def install_from_github(url):
    raise RuntimeError(
        'Remote plugin installation is disabled. Review plugin source locally '
        'and add it through the trusted repository workflow.'
    )

def reload_plugins():
    for name, plugin in list(_registry.items()):
        try:
            plugin.on_unload()
        except Exception:
            pass
    for mod_name in list(sys.modules.keys()):
        if mod_name.startswith('data.plugins.') and mod_name != 'data.plugins':
            del sys.modules[mod_name]
    return load_plugins()
