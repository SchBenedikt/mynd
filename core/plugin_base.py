import importlib
import json
import logging
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

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
                _registry[name] = instance
                logger.info(f"Plugin geladen (Legacy): {name}")
            else:
                name = plugin_cls.name
                if not _is_enabled(name, state):
                    logger.info(f"Plugin deaktiviert: {name}")
                    _registry[name] = None
                    continue
                instance = plugin_cls(config=_config_cache.get(name, {}))
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

GITHUB_RAW_RE = re.compile(r'github\.com[:/]([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)$')

def install_from_github(url):
    m = GITHUB_RAW_RE.search(url)
    if not m:
        raise ValueError("Keine gültige GitHub-URL. Erwartet: https://github.com/user/repo")
    repo = m.group(1)
    raw_url = f'https://raw.githubusercontent.com/{repo}/main/plugin.py'
    try:
        req = urllib.request.Request(raw_url, headers={'User-Agent': 'MYND'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            code = resp.read().decode('utf-8')
    except urllib.error.HTTPError:
        raw_url = f'https://raw.githubusercontent.com/{repo}/master/plugin.py'
        req = urllib.request.Request(raw_url, headers={'User-Agent': 'MYND'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            code = resp.read().decode('utf-8')
    name = repo.split('/')[-1]
    target = PLUGIN_DIR / f'{name}.py'
    if target.exists():
        raise FileExistsError(f'Plugin "{name}" existiert bereits.')
    target.write_text(code, encoding='utf-8')
    try:
        reload_plugins()
    except Exception as e:
        target.unlink()
        raise ValueError(f'Plugin-Code konnte nicht geladen werden: {e}')
    return name

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
