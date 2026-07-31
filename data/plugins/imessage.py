"""Apple iMessage integration (macOS only).

Sends messages via AppleScript/Messages.app and reads recent/searchable
history from the local Messages database (requires Full Disk Access for
the process running MYND).
"""

import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta

PLUGIN_NAME = "imessage"
PLUGIN_DESC = "Apple iMessage (macOS) – senden und Verlauf lesen"

_IS_MAC = sys.platform == "darwin"
_CHAT_DB = os.path.expanduser("~/Library/Messages/chat.db")

# Apple epoch (2001-01-01) offset from Unix epoch in seconds.
_APPLE_EPOCH_OFFSET = 978307200


def _asec(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _run_script(script, timeout=20):
    if not _IS_MAC:
        return None, "❌ iMessage ist nur auf macOS verfügbar."
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout,
        )
    except FileNotFoundError:
        return None, "❌ osascript nicht gefunden (kein macOS?)."
    except subprocess.TimeoutExpired:
        return None, "⏱ AppleScript-Timeout (Messages reagiert nicht)."
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        if "not allowed assistive access" in err.lower() or "not authorized" in err.lower():
            return None, "❌ Zugriff auf Messages nicht autorisiert. Erlaube in Systemeinstellungen > Datenschutz > Automatisierung."
        if "not allowed to send" in err.lower():
            return None, f"❌ Messages darf nicht senden: {err[:200]}"
        return None, f"❌ AppleScript-Fehler: {err[:300]}"
    return r.stdout.strip(), None


def imessage_send(buddy, text, service=""):
    """Send an iMessage to a phone number or Apple ID."""
    if not buddy:
        return "❌ Empfänger fehlt (Telefonnummer oder Apple-ID)."
    if not text:
        return "❌ Nachrichtentext fehlt."
    if service:
        script = (
            'tell application "Messages"\n'
            f'  send "{_asec(text)}" to buddy "{_asec(buddy)}" of service "{_asec(service)}"\n'
            'end tell\n'
        )
    else:
        script = (
            'tell application "Messages"\n'
            f'  send "{_asec(text)}" to buddy "{_asec(buddy)}"\n'
            'end tell\n'
        )
    out, err = _run_script(script)
    if err:
        return err
    return f"✅ Nachricht an {buddy} gesendet."


def imessage_list_services():
    """List available iMessage services (accounts)."""
    script = 'tell application "Messages"\n  return name of every service\nend tell'
    out, err = _run_script(script)
    if err:
        return err
    return out or "ℹ️ Keine Services gefunden."


def _db_connect():
    if not _IS_MAC:
        return None, "❌ iMessage ist nur auf macOS verfügbar."
    if not os.path.exists(_CHAT_DB):
        return None, "❌ Messages-Datenbank nicht gefunden. Logge dich in Messages ein."
    try:
        conn = sqlite3.connect(f"file:{_CHAT_DB}?mode=ro", uri=True, timeout=5)
        return conn, None
    except sqlite3.Error as e:
        return None, (
            "❌ Messages-Datenbank nicht lesbar. Erlaube 'Voller Datenträgerzugriff' "
            f"für das Prozess, der MYND startet. (Detail: {str(e)[:200]})"
        )


def _query_messages(where="", params=(), limit=20):
    conn, err = _db_connect()
    if err:
        return err
    try:
        sql = (
            "SELECT m.ROWID, datetime(m.date/1000000000 + 978307200, 'unixepoch', 'localtime'), "
            "       m.text, h.id AS buddy, m.is_from_me, m.guid "
            "FROM message m "
            "JOIN chat_message_join cmj ON m.ROWID = cmj.message_id "
            "JOIN chat c ON cmj.chat_id = c.ROWID "
            "LEFT JOIN handle h ON m.handle_id = h.ROWID "
        )
        if where:
            sql += "WHERE " + where + " "
        sql += "GROUP BY m.guid ORDER BY m.date DESC LIMIT ?"
        rows = conn.execute(sql, (*params, int(limit))).fetchall()
    except sqlite3.Error as e:
        return f"❌ Datenbankabfrage fehlgeschlagen: {str(e)[:200]}"
    finally:
        conn.close()
    if not rows:
        return "ℹ️ Keine Nachrichten gefunden."
    lines = []
    for rowid, ts, text, buddy, is_from_me, guid in rows:
        if not text:
            text = "(attachment)"
        direction = "→" if is_from_me else "←"
        buddy = buddy or "?"
        lines.append(f"{ts} [{direction} {buddy}] {text[:200]}")
    return "\n".join(lines)


def imessage_list_recent(limit=20, minutes=0):
    """List recent iMessage conversations. minutes>0 limits to the last N minutes."""
    where = ""
    params = ()
    if minutes and int(minutes) > 0:
        cutoff = datetime.now() - timedelta(minutes=int(minutes))
        cutoff_apple = (cutoff - datetime(2001, 1, 1)).total_seconds()
        where = "m.date/1000000000 > ?"
        params = (cutoff_apple,)
    return _query_messages(where, params, limit)


def imessage_search(query="", limit=20):
    """Search the iMessage history for a term."""
    if not query:
        return "❌ Suchbegriff fehlt."
    return _query_messages("m.text LIKE ?", (f"%{query}%",), limit)


TOOLS = [
    {"type": "function", "function": {"name": "imessage_send", "description": "Send an iMessage to a phone number or Apple ID (macOS only).", "parameters": {"type": "object", "properties": {"buddy": {"type": "string", "description": "Recipient phone number or Apple ID (e.g. '+491521234567')"}, "text": {"type": "string", "description": "Message text"}, "service": {"type": "string", "description": "Service/account name (optional, auto if empty)"}}, "required": ["buddy", "text"]}}},
    {"type": "function", "function": {"name": "imessage_list_services", "description": "List available iMessage accounts/services (macOS only).", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "imessage_list_recent", "description": "List recent iMessages (macOS only, needs Full Disk Access).", "parameters": {"type": "object", "properties": {"limit": {"type": "integer", "description": "Max messages (default 20)"}, "minutes": {"type": "integer", "description": "Only show messages from the last N minutes (0 = all)"}}, "required": []}}},
    {"type": "function", "function": {"name": "imessage_search", "description": "Search the iMessage history for a term (macOS only, needs Full Disk Access).", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Search term"}, "limit": {"type": "integer", "description": "Max results (default 20)"}}, "required": ["query"]}}},
]

TOOL_MAP = {
    "imessage_send": imessage_send,
    "imessage_list_services": imessage_list_services,
    "imessage_list_recent": imessage_list_recent,
    "imessage_search": imessage_search,
}

PROMPT_EXTRA = (
    "IMESSAGE (macOS):\n"
    "  - imessage_send(buddy, text, service): Sende eine iMessage an Telefonnummer oder Apple-ID\n"
    "  - imessage_list_services(): Verfügbare Konten anzeigen\n"
    "  - imessage_list_recent(limit, minutes): Letzte Nachrichten lesen\n"
    "  - imessage_search(query): Verlauf durchsuchen\n"
    "\n"
    "  Hinweise:\n"
    "    - Senden nutzt AppleScript (Messages.app). Lesen nutzt ~/Library/Messages/chat.db\n"
    "    - Für Lesen/Suchen muss der MYND-Prozess 'Vollen Datenträgerzugriff' haben\n"
    "    - iMessage ist Ende-zu-Ende-verschlüsselt; MYND greift nur auf den lokalen Verlauf zu\n"
)
