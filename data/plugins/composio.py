import json
from pathlib import Path

from core.vault import load_vault

PLUGIN_NAME = "composio"
PLUGIN_DESC = "Composio – 200+ App-Integrationen (GitHub, Gmail, Slack, Notion, Linear, Jira uvm.)"

VAULT_FILE = Path(__file__).parent.parent / 'vault.json'


def _vault():
    return load_vault(VAULT_FILE)


def _vget(key):
    v = _vault()
    if key in v:
        return v.get(key, "")
    for p in key.split('/'):
        if isinstance(v, dict):
            v = v.get(p, {})
        else:
            return ""
    return v if isinstance(v, str) else ""


def _get_client():
    api_key = _vget("composio/api_key")
    if not api_key:
        return None, "API-Key fehlt. Trage ihn unter Integrationen > Composio ein."
    try:
        from composio import Composio
        c = Composio(api_key=api_key)
        return c, None
    except ImportError:
        return None, "composio ist nicht installiert. pip install composio"
    except Exception as e:
        return None, str(e)


def _get_entity_id():
    return _vget("composio/user_id") or "default"


def composio_list_toolkits(search=""):
    client, err = _get_client()
    if err:
        return f"❌ {err}"
    try:
        result = client.toolkits.list()
        items = result.items if hasattr(result, 'items') else (result or [])
        if search:
            s = search.lower()
            items = [i for i in items if s in (i.name or "").lower() or s in (i.description or "").lower()]
        if not items:
            return "ℹ️ Keine Toolkits gefunden."
        lines = [f"📦 **{len(items)} Apps/Toolkits**:"]
        for i in sorted(items, key=lambda x: x.name):
            auth = getattr(i, 'auth_scheme', None)
            auth_str = " 🔑" if auth else ""
            cats = getattr(i, 'categories', None) or []
            cat_str = f" [{', '.join(cats[:3])}]" if cats else ""
            desc = (getattr(i, 'description', '') or '')[:120]
            lines.append(f"  **{i.name}**{auth_str}{cat_str}")
            if desc:
                lines.append(f"    {desc}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ {e}"


def composio_list_tools(app="", search="", limit=20):
    client, err = _get_client()
    if err:
        return f"❌ {err}"
    try:
        kwargs = {"user_id": _get_entity_id(), "limit": min(limit, 50)}
        if app:
            kwargs["toolkits"] = [app]
        if search:
            kwargs["search"] = search
        tools = client.tools.get(**kwargs)
        if not tools:
            return "ℹ️ Keine Tools gefunden."
        if not isinstance(tools, list):
            tools = [tools]
        lines = [f"🔧 **{len(tools)} Tools**" + (f" für **{app}**" if app else "") + (f" zu '{search}'" if search else "") + ":"]
        for t in tools[:limit]:
            name = "?"
            desc = ""
            props = {}
            if isinstance(t, dict):
                fn = t.get("function", t)
                name = fn.get("name", "?")
                desc = (fn.get("description", "") or "")[:100]
                params = fn.get("parameters", {})
                props = params.get("properties", {}) if isinstance(params, dict) else {}
            elif hasattr(t, "function"):
                fn = t.function
                name = getattr(fn, "name", "?")
                desc = (getattr(fn, "description", "") or "")[:100]
                p = getattr(fn, "parameters", {})
                props = p.get("properties", {}) if isinstance(p, dict) else {}
            app_name = app or "?"
            lines.append(f"  **{name}**")
            if desc:
                lines.append(f"    {desc}")
            lines.append(f"    App: {app_name} | Parameter: {len(props)}")
        if len(tools) > limit:
            lines.append(f"  … und {len(tools) - limit} weitere (erhöhe limit)")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ {e}"


def composio_execute(slug, params="{}", connected_account_id=""):
    client, err = _get_client()
    if err:
        return f"❌ {err}"
    try:
        if isinstance(params, str):
            params = json.loads(params)
        kwargs = {
            "slug": slug,
            "arguments": params,
            "user_id": _get_entity_id(),
        }
        if connected_account_id:
            kwargs["connected_account_id"] = connected_account_id
        result = client.tools.execute(**kwargs)
        data = result.data if hasattr(result, 'data') else result
        if isinstance(data, dict) and "error" in data:
            return f"❌ {data['error']}"
        return json.dumps(data, ensure_ascii=False, indent=2, default=str)[:8000]
    except Exception as e:
        return f"❌ {e}"


def composio_list_connections():
    client, err = _get_client()
    if err:
        return f"❌ {err}"
    try:
        result = client.connected_accounts.list()
        items = result.items if hasattr(result, 'items') else (result or [])
        if not items:
            return "ℹ️ Keine verbundenen Konten."
        lines = [f"🔗 **{len(items)} Verbindungen**:"]
        for conn in items:
            status = getattr(conn, 'status', 'UNKNOWN')
            status_icon = "✅" if status == "ACTIVE" else "❌"
            app_name = getattr(conn, 'appName', '?')
            conn_id = getattr(conn, 'id', '?')
            lines.append(f"  {status_icon} **{app_name}** (`{conn_id}`) – {status}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ {e}"


def composio_initiate_connection(app_name):
    client, err = _get_client()
    if err:
        return f"❌ {err}"
    try:
        entity_id = _get_entity_id()
        # Get toolkit info to find auth config
        toolkit = client.toolkits.get(slug=app_name)
        auth_config_id = None
        if hasattr(toolkit, 'auth_schemes') and toolkit.auth_schemes:
            auth_config_id = toolkit.auth_schemes[0].get('auth_config_id') if isinstance(toolkit.auth_schemes[0], dict) else getattr(toolkit.auth_schemes[0], 'auth_config_id', None)
        if not auth_config_id:
            # Fallback: try passing app_name as auth_config_id
            auth_config_id = app_name
        connection_request = client.connected_accounts.initiate(
            user_id=entity_id,
            auth_config_id=auth_config_id,
        )
        redirect_url = getattr(connection_request, 'redirectUrl', None) or getattr(connection_request, 'redirect_url', None)
        if redirect_url:
            return (
                f"🌐 Öffne diesen Link um **{app_name}** zu verbinden:\n"
                f"{redirect_url}\n\n"
                f"Nach der Autorisierung kannst du Composio-Tools für {app_name} nutzen.\n"
                f"Verwende composio_list_connections() um den Status zu prüfen."
            )
        return f"✅ **{app_name}** wurde verbunden (kein OAuth nötig)."
    except Exception as e:
        return f"❌ {e}"


TOOLS = [
    {"type": "function", "function": {"name": "composio_list_apps", "description": "List all available apps/toolkits available via Composio. Optionally filter by search term.", "parameters": {"type": "object", "properties": {"search": {"type": "string", "description": "Search term to filter (optional)"}}, "required": []}}},
    {"type": "function", "function": {"name": "composio_list_toolkits", "description": "List all available apps/toolkits available via Composio. Optionally filter by search term.", "parameters": {"type": "object", "properties": {"search": {"type": "string", "description": "Search term to filter (optional)"}}, "required": []}}},
    {"type": "function", "function": {"name": "composio_list_tools", "description": "List available tools/actions for a specific app or search for tools.", "parameters": {"type": "object", "properties": {"app": {"type": "string", "description": "App name (e.g. GITHUB, GMAIL, SLACK, NOTION)"}, "search": {"type": "string", "description": "Search term for use case"}, "limit": {"type": "integer", "description": "Maximum count (default 20, max 50)"}}, "required": []}}},
    {"type": "function", "function": {"name": "composio_execute", "description": "Execute a Composio tool. Tools follow the pattern APP_ACTION (e.g. GITHUB_LIST_STARGAZERS, GMAIL_SEND_EMAIL). Use composio_list_tools() first to discover available tools and their parameters.", "parameters": {"type": "object", "properties": {"slug": {"type": "string", "description": "Tool slug (e.g. GITHUB_LIST_ISSUES, GMAIL_SEND_EMAIL)"}, "params": {"type": "string", "description": "JSON string with parameters. Must match the tool's input schema."}, "connected_account_id": {"type": "string", "description": "Connected account ID (optional, if not the default one)"}}, "required": ["slug", "params"]}}},
    {"type": "function", "function": {"name": "composio_list_connections", "description": "List all active connected accounts.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "composio_initiate_connection", "description": "Start the OAuth connection process for an app (e.g. GITHUB, GMAIL). Returns a link to authorize.", "parameters": {"type": "object", "properties": {"app_name": {"type": "string", "description": "App name (e.g. GITHUB, GMAIL, SLACK, NOTION, LINEAR, JIRA)"}}, "required": ["app_name"]}}},
]

TOOL_MAP = {
    "composio_list_apps": composio_list_toolkits,
    "composio_list_toolkits": composio_list_toolkits,
    "composio_list_tools": composio_list_tools,
    "composio_execute": composio_execute,
    "composio_list_connections": composio_list_connections,
    "composio_initiate_connection": composio_initiate_connection,
}

PROMPT_EXTRA = (
    "COMPOSIO (200+ App-Integrations):\n"
    "  Composio provides connections to 200+ services (GitHub, Gmail, Slack, Notion, Linear, Jira, etc.).\n"
    "  1. **composio_list_toolkits(search)**: Browse all available apps\n"
    "  2. **composio_list_tools(app, search, limit)**: Show tools for an app\n"
    "  3. **composio_execute(slug, params, connected_account_id)**: Execute a tool\n"
    "  4. **composio_list_connections()**: Show connected accounts\n"
    "  5. **composio_initiate_connection(app_name)**: Get OAuth link to connect an app\n"
    "\n"
    "  Tool slugs follow APP_ACTION pattern, e.g.:\n"
    "    - GITHUB_LIST_ISSUES, GITHUB_CREATE_ISSUE, GITHUB_LIST_REPOS\n"
    "    - GMAIL_SEND_EMAIL, GMAIL_LIST_THREADS, GMAIL_READ_EMAIL\n"
    "    - SLACK_POST_MESSAGE, SLACK_LIST_CHANNELS\n"
    "    - NOTION_CREATE_PAGE, NOTION_QUERY_DATABASE\n"
    "\n"
    "  IMPORTANT:\n"
    "    - Call composio_list_tools() first to discover available tools\n"
    "    - For authenticated tools, run composio_initiate_connection() first\n"
    "    - Vault: composio/api_key (required), composio/user_id (optional)\n"
    "    - After OAuth, use composio_list_connections() to verify\n"
    "\n"
    "  EXAMPLES:\n"
    "    'What apps are available?' -> composio_list_toolkits()\n"
    "    'List GitHub issues in ComposioHQ/composio' -> composio_list_tools(app='GITHUB', search='issues') -> composio_execute('GITHUB_LIST_ISSUES', '{\"owner\":\"ComposioHQ\",\"repo\":\"composio\"}')\n"
    "    'Send an email to test@example.com' -> composio_list_tools(app='GMAIL', search='send') -> composio_execute('GMAIL_SEND_EMAIL', '{\"to\":\"test@example.com\",\"subject\":\"Hello\",\"body\":\"Test\"}')\n"
    "    'Connect my GitHub account' -> composio_initiate_connection('GITHUB')\n"
    "    'What is connected?' -> composio_list_connections()\n"
)
