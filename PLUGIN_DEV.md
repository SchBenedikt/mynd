# MYND Plugin Development Guide

Plugins extend MYND with new tools the AI agent can call. Each plugin is a single `.py` file placed in `data/plugins/`. Plugins can be developed locally or installed directly from GitHub.

---

## Quick Start — Minimal Plugin

Create `data/plugins/hello.py`:

```python
"""Minimal MYND plugin — 3 tools."""
PLUGIN_NAME = "hello"
PLUGIN_DESC = "Example plugin with greeting and echo tools"

def _greet(name="World"):
    return f"Hello, {name}! 👋"

def _echo(text=""):
    return f"You said: {text}"

def _add(a=0, b=0):
    return f"{a} + {b} = {a + b}"

TOOLS = [
    {"type":"function","function":{
        "name":"hello_greet",
        "description":"Greet someone",
        "parameters":{"type":"object","properties":{
            "name":{"type":"string","description":"Name to greet"}
        },"required":[]}
    }},
    {"type":"function","function":{
        "name":"hello_echo",
        "description":"Echo back text",
        "parameters":{"type":"object","properties":{
            "text":{"type":"string","description":"Text to echo"}
        },"required":[]}
    }},
    {"type":"function","function":{
        "name":"hello_add",
        "description":"Add two numbers",
        "parameters":{"type":"object","properties":{
            "a":{"type":"integer","description":"First number","default":0},
            "b":{"type":"integer","description":"Second number","default":0}
        },"required":[]}
    }},
]

TOOL_MAP = {
    "hello_greet": _greet,
    "hello_echo": _echo,
    "hello_add": _add,
}
```

Save and restart the backend — your plugin loads automatically. Run `GET /api/plugins` to verify.

---

## Plugin Format — Two Styles

### Style A: Legacy (module-level variables) — Simple

Set these module-level variables:

| Variable | Type | Required | Description |
|---|---|---|---|
| `PLUGIN_NAME` | `str` | Yes | Unique plugin name |
| `PLUGIN_DESC` | `str` | No | Human-readable description |
| `PLUGIN_CONFIG_SCHEMA` | `dict` | No | UI form schema for configuration |
| `TOOLS` | `list[dict]` | No | Tool definitions (OpenAI function format) |
| `TOOL_MAP` | `dict[str, callable]` | No | Maps tool name → function |
| `PROMPT_EXTRA` | `str` | No | Extra text injected into the system prompt |

### Style B: Class-based (Plugin subclass) — Full lifecycle

```python
from core.plugin_base import Plugin

class MyPlugin(Plugin):
    name = "myplugin"
    description = "Description"
    version = "1.0.0"
    config_schema = {}  # Optional UI config schema
    tools = TOOLS
    tool_map = TOOL_MAP

    def on_load(self):
        # Called when the plugin is loaded
        pass

    def on_unload(self):
        # Called when the plugin is unloaded/reloaded
        pass
```

---

## Tool Definition Format

Tools follow the **OpenAI function-calling schema**:

```python
{
    "type": "function",
    "function": {
        "name": "my_tool",                              # Snake-case, unique
        "description": "What this tool does",            # Shown to the AI
        "parameters": {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",                    # string, integer, number, boolean, array, object
                    "description": "What param1 does",    # Guides the AI
                    "default": "optional_value"           # Optional – if absent, param is required
                },
                "param2": {
                    "type": "integer",
                    "description": "Some number",
                    "minimum": 0,
                    "maximum": 100
                }
            },
            "required": ["param1"]                       # Params without "default"
        }
    }
}
```

### Parameter Types

| Type | JSON Schema | Example |
|---|---|---|
| String | `{"type": "string"}` | `"Berlin"` |
| Integer | `{"type": "integer"}` | `42` |
| Number | `{"type": "number"}` | `3.14` |
| Boolean | `{"type": "boolean"}` | `true` |
| Enum | `{"type": "string", "enum": ["a", "b"]}` | `"a"` |

---

## Configuration UI (config_schema)

If your plugin needs configuration, define `config_schema` to auto-generate a settings form:

```python
PLUGIN_CONFIG_SCHEMA = {
    "api_key": {
        "label": "API Key",
        "type": "password",        # text | password | select
        "default": ""
    },
    "server_url": {
        "label": "Server URL",
        "type": "text",
        "default": "https://..."
    },
    "mode": {
        "label": "Mode",
        "type": "select",
        "options": ["fast", "balanced", "accurate"],
        "default": "balanced"
    }
}
```

Access configuration in your functions:

```python
import data.plugins.plugin_config as _cfg

def my_tool():
    config = _cfg.get_plugin_config()  # dict of all configs

# Or read the config JSON directly:
config = json.loads(
    (Path(__file__).parent / 'plugin_config.json').read_text()
).get(PLUGIN_NAME, {})
api_key = config.get('api_key', '')
```

---

## Installing Plugins from GitHub

MYND can install plugins directly from any GitHub repository via raw URL download.

### URL Import (in the UI)

1. Open **Settings → Integrations → Plugin Manager**
2. Enter a GitHub URL: `https://github.com/your-user/your-plugin-repo`
3. Click **Installieren**

### URL Import (API)

```bash
curl -X POST http://127.0.0.1:5001/api/plugins/install \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://github.com/your-user/your-plugin-repo"}'
```

### How it works

1. The backend extracts `user/repo` from the URL
2. Downloads `https://raw.githubusercontent.com/user/repo/main/plugin.py`
3. Falls back to `master` branch if `main` fails
4. Saves as `data/plugins/<repo-name>.py`
5. Auto-loads the plugin via `reload_plugins()`
6. If loading fails, the file is deleted (rollback)

### Requirements for GitHub repos

- Repository root must contain a `plugin.py` file
- The file must follow the plugin format (legacy or class-based)
- No external dependencies beyond what `pip install -e '.[dev]'` provides
- Import custom packages at your own risk (they must be installed separately)

---

## API Endpoints

| Method | Route | Description |
|---|---|---|
| `GET` | `/api/plugins` | List all plugins with name, version, description, tools, enabled status |
| `POST` | `/api/plugins/install` | Install plugin from GitHub URL |
| `POST` | `/api/plugins/<name>/toggle` | Enable/disable a plugin (`{"enabled": true/false}`) |
| `DELETE` | `/api/plugins/<name>` | Uninstall plugin (deletes file + state) |
| `GET` | `/api/plugins/<name>/config` | Get plugin configuration |
| `POST` | `/api/plugins/<name>/config` | Save plugin configuration |

Plugin state is stored in `data/plugins/plugin_state.json`.
Plugin configuration is stored in `data/plugins/plugin_config.json`.

---

## Tips

- **Name tools with a prefix** matching your plugin name (e.g., `myplugin_do_thing`) to avoid conflicts
- **Keep tool descriptions clear** — the AI model uses the description to decide when to call your tool
- **Use `PROMPT_EXTRA`** to inject instructions into the system prompt (e.g., "You have access to weather data")
- **Log with `logger`** — import from `app.config` or use `print()` (stdout is captured in server logs)
- **Test loading** — after writing your plugin, restart the server and call `GET /api/plugins` to verify
- **Errors** — raise exceptions or return error strings; the agent loop catches and reports them
