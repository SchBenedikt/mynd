import json
import threading
from pathlib import Path

import requests

from core.vault import load_vault

PLUGIN_NAME = "discord"
PLUGIN_DESC = "Discord-Integration – Nachrichten, Channels, Mitglieder, Server-Info"

VAULT_FILE = Path(__file__).parent.parent / 'vault.json'

BASE = "https://discord.com/api/v10"

_cache = {"channels": None, "ts": 0, "ttl": 30}
_dc_lock = threading.Lock()

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

def _conn():
    token = _vget("discord/bot_token")
    if not token:
        return None, None, "Bot-Token fehlt. `vault_set discord/bot_token DEIN_TOKEN`"
    guild_id = _vget("discord/guild_id")
    return token, guild_id, None

def _discord_api(method, endpoint, body=None, params=None):
    token, guild_id, err = _conn()
    if err:
        return None, err
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json",
    }
    url = f"{BASE}{endpoint}"
    try:
        r = requests.request(method, url, headers=headers, json=body, params=params, timeout=15)
        if r.status_code in (200, 201):
            return r.json() if r.text else {}, None
        if r.status_code == 204:
            return {}, None
        detail = ""
        try:
            detail = r.json().get("message", r.text[:300])
        except Exception:
            detail = r.text[:300]
        return None, f"Discord-Fehler {r.status_code}: {detail}"
    except requests.exceptions.Timeout:
        return None, "Zeitüberschreitung bei der Discord-API"
    except requests.exceptions.ConnectionError:
        return None, "Verbindungsfehler zur Discord-API"
    except Exception as e:
        return None, str(e)

def _paginated_get(endpoint, limit, max_items=200, after_key="after"):
    results = []
    after = None
    while len(results) < max_items:
        take = min(limit, max_items - len(results))
        params = {"limit": take}
        if after is not None:
            params[after_key] = after
        data, err = _discord_api("GET", endpoint, params=params)
        if err:
            if results:
                break
            return None, err
        if not data:
            break
        results.extend(data)
        if len(data) < take:
            break
        after = str(data[-1].get("id", ""))
        if not after:
            break
    return results, None


def discord_send_message(channel_id, content=None, embeds=None):
    if not content and not embeds:
        return "❌ content oder embeds erforderlich"
    body = {}
    if content:
        body["content"] = content
    if embeds:
        if isinstance(embeds, str):
            try:
                embeds = json.loads(embeds)
            except Exception:
                return "❌ embeds muss gültiges JSON sein"
        body["embeds"] = embeds if isinstance(embeds, list) else [embeds]
    data, err = _discord_api("POST", f"/channels/{channel_id}/messages", body=body)
    if err:
        return f"❌ {err}"
    mid = data.get("id", "")
    link = f"https://discord.com/channels/@me/{channel_id}/{mid}" if mid else ""
    return f"✅ Nachricht gesendet {link}".strip()


def discord_read_messages(channel_id, limit=50):
    data, err = _paginated_get(f"/channels/{channel_id}/messages", limit=min(limit, 100))
    if err:
        return f"❌ {err}"
    if not data:
        return "ℹ️ Keine Nachrichten."
    lines = [f"📨 **{len(data)} Nachrichten** aus <#{channel_id}>:"]
    for msg in reversed(data):
        author = msg.get("author", {})
        name = author.get("global_name") or author.get("username") or "Unbekannt"
        ts = msg.get("timestamp", "")[:19].replace("T", " ")
        content = msg.get("content", "") or ""
        if len(content) > 200:
            content = content[:200] + "…"
        lines.append(f"  **{name}** ({ts}): {content}")
    return "\n".join(lines)


def discord_list_channels(guild_id=None):
    if not guild_id:
        _, gid, err = _conn()
        if err:
            return f"❌ {err}"
        guild_id = gid
    if not guild_id:
        return "❌ Guild-ID fehlt. `vault_set discord/guild_id ID` oder als Parameter übergeben"
    data, err = _discord_api("GET", f"/guilds/{guild_id}/channels")
    if err:
        return f"❌ {err}"
    if not data:
        return "ℹ️ Keine Channels gefunden."
    lines = [f"📋 **{len(data)} Channels**:"]
    type_names = {0: "Text", 2: "Voice", 4: "Kategorie", 5: "Announcement", 13: "Stage", 15: "Forum"}
    for ch in sorted(data, key=lambda x: (x.get("position", 0), x.get("type", 0))):
        ch_type = type_names.get(ch.get("type", 0), f"Typ {ch.get('type')}")
        ns = ch.get("name", "?")
        ch_id = ch.get("id", "")
        parent = ch.get("parent_id", "")
        parent_str = f" → {parent}" if parent else ""
        is_nsfw = " 🔞" if ch.get("nsfw") else ""
        lines.append(f"  📌 **{ns}** (`{ch_id}`) [{ch_type}]{parent_str}{is_nsfw}")
    return "\n".join(lines)


def discord_get_guild_info(guild_id=None):
    if not guild_id:
        _, gid, err = _conn()
        if err:
            return f"❌ {err}"
        guild_id = gid
    if not guild_id:
        return "❌ Guild-ID fehlt. `vault_set discord/guild_id ID` oder als Parameter übergeben"
    data, err = _discord_api("GET", f"/guilds/{guild_id}")
    if err:
        return f"❌ {err}"
    name = data.get("name", "?")
    desc = data.get("description", "")
    owner_id = data.get("owner_id", "?")
    members = data.get("approximate_member_count", "?")
    online = data.get("approximate_presence_count", "?")
    icon_hash = data.get("icon", "")
    icon_url = f"https://cdn.discordapp.com/icons/{guild_id}/{icon_hash}.png" if icon_hash else ""
    features = ", ".join(data.get("features", []))
    lines = [
        f"🏰 **{name}**",
        f"  ID: `{guild_id}`",
        f"  Besitzer: `{owner_id}`",
        f"  Mitglieder: {members} ({online} online)",
    ]
    if desc:
        lines.append(f"  Beschreibung: {desc}")
    if features:
        lines.append(f"  Features: {features}")
    if icon_url:
        lines.append(f"  Icon: {icon_url}")
    return "\n".join(lines)


def discord_get_guild_roles(guild_id=None):
    if not guild_id:
        _, gid, err = _conn()
        if err:
            return f"❌ {err}"
        guild_id = gid
    if not guild_id:
        return "❌ Guild-ID fehlt. `vault_set discord/guild_id ID` oder als Parameter übergeben"
    data, err = _discord_api("GET", f"/guilds/{guild_id}/roles")
    if err:
        return f"❌ {err}"
    if not data:
        return "ℹ️ Keine Rollen gefunden."
    lines = [f"🎭 **{len(data)} Rollen**:"]
    for r in sorted(data, key=lambda x: x.get("position", 0), reverse=True):
        rname = r.get("name", "?")
        rid = r.get("id", "")
        color = r.get("color", 0)
        mentionable = r.get("mentionable", False)
        hoist = r.get("hoist", False)
        tags = []
        if color:
            tags.append(f"Farbe=#{color:06X}")
        if hoist:
            tags.append("getrennt")
        if mentionable:
            tags.append("erwähnbar")
        tag_str = f" ({', '.join(tags)})" if tags else ""
        lines.append(f"  **{rname}** (`{rid}`){tag_str}")
    return "\n".join(lines)


def discord_list_members(guild_id=None, limit=50):
    if not guild_id:
        _, gid, err = _conn()
        if err:
            return f"❌ {err}"
        guild_id = gid
    if not guild_id:
        return "❌ Guild-ID fehlt. `vault_set discord/guild_id ID` oder als Parameter übergeben"
    data, err = _paginated_get(f"/guilds/{guild_id}/members", limit=min(limit, 100))
    if err:
        return f"❌ {err}"
    if not data:
        return "ℹ️ Keine Mitglieder."
    lines = [f"👥 **{len(data)} Mitglieder**:"]
    for m in data:
        user = m.get("user", {})
        uname = user.get("global_name") or user.get("username") or "?"
        uid = user.get("id", "")
        bot = " 🤖" if user.get("bot") else ""
        nick = m.get("nick", "")
        nick_str = f" ({nick})" if nick else ""
        roles = m.get("roles", [])
        role_str = f" [{len(roles)} Rollen]" if roles else ""
        lines.append(f"  **{uname}**`{nick_str}` (`{uid}`){bot}{role_str}")
    return "\n".join(lines)


def discord_get_member(guild_id, user_id):
    data, err = _discord_api("GET", f"/guilds/{guild_id}/members/{user_id}")
    if err:
        return f"❌ {err}"
    user = data.get("user", {})
    uname = user.get("global_name") or user.get("username") or "?"
    uid = user.get("id", "")
    bot = " 🤖" if user.get("bot") else ""
    nick = data.get("nick", "")
    nick_str = f" ({nick})" if nick else ""
    joined_at = (data.get("joined_at", "")[:19].replace("T", " ") if data.get("joined_at") else "?")
    roles = data.get("roles", [])
    avatar = user.get("avatar", "")
    avatar_url = f"https://cdn.discordapp.com/avatars/{uid}/{avatar}.png" if avatar else ""
    lines = [
        f"👤 **{uname}**`{nick_str}` (`{uid}`){bot}",
        f"  Beitritt: {joined_at}",
        f"  Rollen ({len(roles)}): " + ", ".join(f"`{r}`" for r in roles[:20]),
    ]
    if avatar_url:
        lines.append(f"  Avatar: {avatar_url}")
    if data.get("premium_since"):
        lines.append("  ⭐ Nitro-Booster")
    if data.get("deaf"):
        lines.append("  🔇 Taubgeschaltet")
    if data.get("mute"):
        lines.append("  🔇 Stummgeschaltet")
    return "\n".join(lines)


def discord_create_thread(channel_id, message_id, name, auto_archive=60):
    if not name:
        return "❌ Thread-Name erforderlich"
    body = {"name": name, "auto_archive_duration": auto_archive}
    data, err = _discord_api("POST", f"/channels/{channel_id}/messages/{message_id}/threads", body=body)
    if err:
        return f"❌ {err}"
    tid = data.get("id", "")
    tname = data.get("name", "")
    link = f"https://discord.com/channels/@me/{channel_id}/{tid}" if tid else ""
    return f"✅ Thread **{tname}** erstellt {link}".strip()


def discord_get_channel(channel_id):
    data, err = _discord_api("GET", f"/channels/{channel_id}")
    if err:
        return f"❌ {err}"
    name = data.get("name", "?")
    ch_type = {0: "Text", 2: "Voice", 4: "Kategorie", 5: "Announcement", 13: "Stage", 15: "Forum"}.get(data.get("type", 0), "?")
    guild_id = data.get("guild_id", "?")
    topic = data.get("topic", "")
    pos = data.get("position", "?")
    nsfw = data.get("nsfw", False)
    parent = data.get("parent_id", "")
    lines = [
        f"📌 **#{name}** (`{channel_id}`)",
        f"  Typ: {ch_type}",
        f"  Guild: `{guild_id}`",
        f"  Position: {pos}",
    ]
    if topic:
        lines.append(f"  Thema: {topic}")
    if nsfw:
        lines.append("  🔞 NSFW")
    if parent:
        lines.append(f"  Kategorie: `{parent}`")
    for attr in ("rate_limit_per_user", "user_limit", "bitrate"):
        val = data.get(attr)
        if val is not None:
            lines.append(f"  {attr}: {val}")
    return "\n".join(lines)


def discord_search_messages(guild_id=None, query="", channel_id=None, author_id=None, limit=25):
    if not guild_id:
        _, gid, err = _conn()
        if err:
            return f"❌ {err}"
        guild_id = gid
    if not guild_id:
        return "❌ Guild-ID fehlt. `vault_set discord/guild_id ID` oder als Parameter übergeben"
    if not query and not author_id:
        return "❌ Suchbegriff (query) oder author_id erforderlich"
    params = {}
    if query:
        params["content"] = query
    if channel_id:
        params["channel_id"] = channel_id
    if author_id:
        params["author_id"] = author_id
    params["limit"] = min(limit, 100)
    data, err = _discord_api("GET", f"/guilds/{guild_id}/messages/search", params=params)
    if err:
        return f"❌ {err}"
    messages = data.get("messages", [])
    total = data.get("total_results", 0)
    if not messages:
        return f"🔍 Keine Ergebnisse für '{query}'."
    lines = [f"🔍 **{total} Ergebnisse** für '{query}':"]
    for msg in data.get("messages", [])[:limit]:
        first = msg[0] if isinstance(msg, list) else msg
        author = first.get("author", {})
        aname = author.get("global_name") or author.get("username") or "?"
        ts = (first.get("timestamp") or "")[:19].replace("T", " ")
        cid = first.get("channel_id", "")
        content = (first.get("content") or "")[:300]
        lines.append(f"  **{aname}** in <#{cid}> ({ts}): {content}")
    return "\n".join(lines)


TOOLS = [
    {"type":"function","function":{"name":"discord_send_message","description":"Sende eine Nachricht in einen Discord-Channel. Optional mit Embeds (JSON-Array).","parameters":{"type":"object","properties":{"channel_id":{"type":"string","description":"Channel-ID"},"content":{"type":"string","description":"Nachrichtentext (optional wenn embeds gesetzt)"},"embeds":{"type":"string","description":"JSON-String mit Embeds (optional, z.B. '[{\"title\":\"Hallo\",\"description\":\"Welt\"}]')"}},"required":["channel_id"]}}},
    {"type":"function","function":{"name":"discord_read_messages","description":"Lese die letzten Nachrichten aus einem Discord-Channel.","parameters":{"type":"object","properties":{"channel_id":{"type":"string","description":"Channel-ID"},"limit":{"type":"integer","description":"Anzahl Nachrichten (max 200)"}},"required":["channel_id"]}}},
    {"type":"function","function":{"name":"discord_list_channels","description":"Liste alle Channels des Discord-Servers. Nutzt Guild-ID aus dem Vault (discord/guild_id) oder Parameter.","parameters":{"type":"object","properties":{"guild_id":{"type":"string","description":"Guild-ID (optional, sonst aus Vault)"}},"required":[]}}},
    {"type":"function","function":{"name":"discord_get_guild_info","description":"Zeige Informationen über den Discord-Server (Name, Mitglieder, Features).","parameters":{"type":"object","properties":{"guild_id":{"type":"string","description":"Guild-ID (optional, sonst aus Vault)"}},"required":[]}}},
    {"type":"function","function":{"name":"discord_get_guild_roles","description":"Liste alle Rollen des Discord-Servers auf.","parameters":{"type":"object","properties":{"guild_id":{"type":"string","description":"Guild-ID (optional, sonst aus Vault)"}},"required":[]}}},
    {"type":"function","function":{"name":"discord_list_members","description":"Liste Mitglieder des Discord-Servers auf.","parameters":{"type":"object","properties":{"guild_id":{"type":"string","description":"Guild-ID (optional, sonst aus Vault)"},"limit":{"type":"integer","description":"Maximale Anzahl (default 50)"}},"required":[]}}},
    {"type":"function","function":{"name":"discord_get_member","description":"Zeige Details zu einem bestimmten Discord-Mitglied.","parameters":{"type":"object","properties":{"guild_id":{"type":"string","description":"Guild-ID"},"user_id":{"type":"string","description":"User-ID"}},"required":["guild_id","user_id"]}}},
    {"type":"function","function":{"name":"discord_create_thread","description":"Erstelle einen Thread aus einer Nachricht.","parameters":{"type":"object","properties":{"channel_id":{"type":"string","description":"Channel-ID"},"message_id":{"type":"string","description":"Nachrichten-ID"},"name":{"type":"string","description":"Thread-Name"},"auto_archive":{"type":"integer","description":"Auto-Archivierung in Minuten (60, 1440, 4320, 10080, default 60)"}},"required":["channel_id","message_id","name"]}}},
    {"type":"function","function":{"name":"discord_get_channel","description":"Zeige Details zu einem Discord-Channel (Name, Typ, Thema, Position).","parameters":{"type":"object","properties":{"channel_id":{"type":"string","description":"Channel-ID"}},"required":["channel_id"]}}},
    {"type":"function","function":{"name":"discord_search_messages","description":"Durchsuche Nachrichten auf dem Discord-Server nach Inhalt oder Autor.","parameters":{"type":"object","properties":{"guild_id":{"type":"string","description":"Guild-ID (optional, sonst aus Vault)"},"query":{"type":"string","description":"Suchbegriff"},"channel_id":{"type":"string","description":"Auf Channel einschränken (optional)"},"author_id":{"type":"string","description":"Auf Autor einschränken (optional)"},"limit":{"type":"integer","description":"Maximale Anzahl Ergebnisse (default 25)"}},"required":[]}}},
]

TOOL_MAP = {
    "discord_send_message": discord_send_message,
    "discord_read_messages": discord_read_messages,
    "discord_list_channels": discord_list_channels,
    "discord_get_guild_info": discord_get_guild_info,
    "discord_get_guild_roles": discord_get_guild_roles,
    "discord_list_members": discord_list_members,
    "discord_get_member": discord_get_member,
    "discord_create_thread": discord_create_thread,
    "discord_get_channel": discord_get_channel,
    "discord_search_messages": discord_search_messages,
}

PROMPT_EXTRA = (
    "DISCORD:\n"
    "  WICHTIG: Channel-IDs und User-IDs sind Zahlen. Nutze discord_list_channels() um verfügbare Channels zu finden.\n"
    "  1. **discord_send_message(channel_id, content, embeds)**: Nachricht in Channel senden\n"
    "  2. **discord_read_messages(channel_id, limit)**: Letzte Nachrichten lesen (max 200)\n"
    "  3. **discord_list_channels(guild_id)**: Channels des Servers auflisten\n"
    "  4. **discord_get_guild_info(guild_id)**: Server-Informationen abrufen\n"
    "  5. **discord_get_guild_roles(guild_id)**: Rollen des Servers auflisten\n"
    "  6. **discord_list_members(guild_id, limit)**: Mitglieder auflisten\n"
    "  7. **discord_get_member(guild_id, user_id)**: Mitglied-Details abrufen\n"
    "  8. **discord_create_thread(channel_id, message_id, name)**: Thread aus Nachricht erstellen\n"
    "  9. **discord_get_channel(channel_id)**: Channel-Details abrufen\n"
    "  10. **discord_search_messages(guild_id, query, channel_id, author_id, limit)**: Nachrichten durchsuchen\n"
    "  Vault: discord/bot_token (erforderlich), discord/guild_id (optional, als Fallback)\n"
    "  BEISPIELE:\n"
    "    'Schreib Hallo in #allgemein' → discord_list_channels() → discord_send_message('123', 'Hallo zusammen!')\n"
    "    'Lies die letzten 10 Nachrichten in #chat' → discord_read_messages('456', 10)\n"
    "    'Wer ist online auf dem Server?' → discord_list_members(limit=100)\n"
    "    'Wie viele Mitglieder hat der Server?' → discord_get_guild_info()\n"
    "    'Such nach Fehlermeldungen' → discord_search_messages(query='error')\n"
)
