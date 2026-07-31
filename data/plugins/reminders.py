"""Apple Reminders integration (macOS only) via AppleScript.

Reads, creates, completes and searches reminders in the Reminders.app.
Only available on macOS; returns a clear error on other platforms.
"""

import re
import subprocess
import sys
from datetime import datetime

PLUGIN_NAME = "reminders"
PLUGIN_DESC = "Apple Reminders (macOS) – Listen, Erinnerungen, Fälligkeitsdaten"

_IS_MAC = sys.platform == "darwin"


def _asec(value):
    """Escape a value for safe embedding in an AppleScript string literal."""
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _run_script(script, timeout=20):
    if not _IS_MAC:
        return None, "❌ Apple Reminders ist nur auf macOS verfügbar."
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout,
        )
    except FileNotFoundError:
        return None, "❌ osascript nicht gefunden (kein macOS?)."
    except subprocess.TimeoutExpired:
        return None, "⏱ AppleScript-Timeout (Reminders reagiert nicht)."
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        if "not allowed assistive access" in err.lower() or "not authorized" in err.lower():
            return None, "❌ Zugriff auf Reminders nicht autorisiert. Erlaube in Systemeinstellungen > Datenschutz > Automatisierung."
        if "Application isn't running" in err.lower():
            return None, "❌ Reminders.app läuft nicht. Öffne sie einmal."
        return None, f"❌ AppleScript-Fehler: {err[:300]}"
    return r.stdout.strip(), None


def _script_body_with_fields(list_name=""):
    """Build a repeat-loop that emits reminder fields separated by | and \\n."""
    src = 'set out to ""\n'
    src += f'set targetList to list "{_asec(list_name)}"\n' if list_name else 'set targetList to {}\n'
    src += 'tell application "Reminders"\n'
    if list_name:
        src += '  set allR to every reminder of targetList\n'
    else:
        src += '  set allR to every reminder\n'
    src += '  repeat with r in allR\n'
    src += '    set d to missing value\n'
    src += '    try\n'
    src += '      set d to (due date of r) as text\n'
    src += '    end try\n'
    src += '    set out to out & (name of r) & "|" & (body of r) & "|" & d & "|" & (completed of r) & "\\n"\n'
    src += '  end repeat\n'
    src += 'end tell\n'
    src += 'return out\n'
    return src


def _parse_reminder_line(line):
    parts = line.split("|", 3)
    while len(parts) < 4:
        parts.append("")
    name, body, due, completed = parts
    return {
        "name": name,
        "body": body,
        "due_date": due,
        "completed": completed.strip() == "true",
    }


def _format_reminder(r):
    icon = "✅" if r["completed"] else "⬜"
    due = f" | Fällig: {r['due_date']}" if r["due_date"] and r["due_date"] != "missing value" else ""
    body = f"\n    {r['body'][:200]}" if r["body"] else ""
    return f"{icon} {r['name']}{due}{body}"


def reminders_lists():
    """List all reminder lists in Reminders.app."""
    script = 'tell application "Reminders"\n  return name of every list\nend tell'
    out, err = _run_script(script)
    if err:
        return err
    items = [i.strip().strip('"') for i in re.findall(r'"((?:[^"\\]|\\.)*)"', out)]
    if not items or out.strip() == "":
        return "ℹ️ Keine Listen vorhanden."
    lines = [f"📋 **{len(items)} Listen:**"]
    lines += [f"  • {name}" for name in items]
    return "\n".join(lines)


def reminders_list(list_name="", include_completed="no"):
    """List reminders, optionally filtered by list and completion state."""
    if not list_name:
        return "❌ Bitte list_name angeben (z.B. 'Persönlich'). Nutze reminders_lists()."
    script = _script_body_with_fields(list_name)
    out, err = _run_script(script)
    if err:
        return err
    reminders = [_parse_reminder_line(line) for line in out.splitlines() if line.strip()]
    if include_completed and str(include_completed).strip().lower() in ("1", "yes", "true"):
        reminders = [r for r in reminders if r["completed"]]
    else:
        reminders = [r for r in reminders if not r["completed"]]
    if not reminders:
        return f"ℹ️ Keine Erinnerungen in '{list_name}'."
    lines = [f"📝 **{len(reminders)} Erinnerungen in '{list_name}':**"]
    lines += [f"  {_format_reminder(r)}" for r in reminders]
    return "\n".join(lines)


def reminders_create(title, due_date="", notes="", list_name="Persönlich"):
    """Create a new reminder. due_date: 'YYYY-MM-DD HH:MM' (optional)."""
    if not title:
        return "❌ Titel fehlt."
    props = f'name:"{_asec(title)}"'
    if notes:
        props += f', body:"{_asec(notes)}"'
    date_expr = ""
    if due_date:
        try:
            dt = datetime.strptime(due_date[:16], "%Y-%m-%d %H:%M")
        except ValueError:
            return "❌ due_date Format: 'YYYY-MM-DD HH:MM'"
        date_expr = (
            'set d to current date\n'
            f'set year of d to {dt.year}\n'
            f'set month of d to {dt.month}\n'
            f'set day of d to {dt.day}\n'
            f'set time of d to ({dt.hour} * 3600 + {dt.minute} * 60)\n'
            f'set props to props & {{due date:d}}\n'
        )
    script = (
        f'set props to {{{props}}}\n'
        + date_expr
        + 'tell application "Reminders"\n'
        f'  make new reminder at end of list "{_asec(list_name)}" with properties props\n'
        'end tell\n'
        'return "ok"\n'
    )
    out, err = _run_script(script)
    if err:
        return err
    due = f" (fällig {due_date})" if due_date else ""
    return f"✅ Erinnerung '{title}' in '{list_name}' erstellt{due}."


def reminders_complete(title, list_name=""):
    """Mark a reminder as completed."""
    if not title:
        return "❌ Titel fehlt."
    src = 'tell application "Reminders"\n'
    if list_name:
        src += f'  set r to (first reminder of list "{_asec(list_name)}" whose name is "{_asec(title)}" and completed is false)\n'
    else:
        src += f'  set r to (first reminder whose name is "{_asec(title)}" and completed is false)\n'
    src += '  set completed of r to true\n'
    src += 'end tell\n'
    src += 'return "ok"\n'
    out, err = _run_script(src)
    if err:
        return err
    return f"✅ Erinnerung '{title}' abgeschlossen."


def reminders_uncomplete(title, list_name=""):
    """Re-open a completed reminder."""
    if not title:
        return "❌ Titel fehlt."
    src = 'tell application "Reminders"\n'
    if list_name:
        src += f'  set r to (first reminder of list "{_asec(list_name)}" whose name is "{_asec(title)}" and completed is true)\n'
    else:
        src += f'  set r to (first reminder whose name is "{_asec(title)}" and completed is true)\n'
    src += '  set completed of r to false\n'
    src += 'end tell\n'
    src += 'return "ok"\n'
    out, err = _run_script(src)
    if err:
        return err
    return f"✅ Erinnerung '{title}' wieder geöffnet."


def reminders_delete(title, list_name=""):
    """Delete a reminder."""
    if not title:
        return "❌ Titel fehlt."
    src = 'tell application "Reminders"\n'
    if list_name:
        src += f'  delete (first reminder of list "{_asec(list_name)}" whose name is "{_asec(title)}")\n'
    else:
        src += f'  delete (first reminder whose name is "{_asec(title)}")\n'
    src += 'end tell\n'
    src += 'return "ok"\n'
    out, err = _run_script(src)
    if err:
        return err
    return f"✅ Erinnerung '{title}' gelöscht."


def reminders_search(query="", limit=20):
    """Search reminders by title or notes across all lists."""
    if not query:
        return "❌ Suchbegriff fehlt."
    script = _script_body_with_fields("")
    out, err = _run_script(script)
    if err:
        return err
    q = query.lower()
    reminders = [_parse_reminder_line(line) for line in out.splitlines() if line.strip()]
    hits = [r for r in reminders if q in r["name"].lower() or q in r["body"].lower()]
    hits = hits[: int(limit)]
    if not hits:
        return f"ℹ️ Keine Erinnerungen zu '{query}' gefunden."
    lines = [f"🔍 **{len(hits)} Treffer zu '{query}':**"]
    lines += [f"  {_format_reminder(r)}" for r in hits]
    return "\n".join(lines)


TOOLS = [
    {"type": "function", "function": {"name": "reminders_lists", "description": "List all reminder lists in Apple Reminders (macOS only).", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "reminders_list", "description": "List reminders from an Apple Reminders list (macOS only). Optionally include completed ones.", "parameters": {"type": "object", "properties": {"list_name": {"type": "string", "description": "Name of the reminder list (e.g. 'Persönlich')"}, "include_completed": {"type": "string", "description": "Set to 'yes' to include completed reminders (default no)"}}, "required": ["list_name"]}}},
    {"type": "function", "function": {"name": "reminders_create", "description": "Create a new reminder in Apple Reminders (macOS only).", "parameters": {"type": "object", "properties": {"title": {"type": "string", "description": "Reminder title"}, "due_date": {"type": "string", "description": "Due date 'YYYY-MM-DD HH:MM' (optional)"}, "notes": {"type": "string", "description": "Notes/body (optional)"}, "list_name": {"type": "string", "description": "Target list (default 'Persönlich')"}}, "required": ["title"]}}},
    {"type": "function", "function": {"name": "reminders_complete", "description": "Mark a reminder as completed (macOS only).", "parameters": {"type": "object", "properties": {"title": {"type": "string", "description": "Reminder title"}, "list_name": {"type": "string", "description": "List to search in (optional)"}}, "required": ["title"]}}},
    {"type": "function", "function": {"name": "reminders_uncomplete", "description": "Re-open a completed reminder (macOS only).", "parameters": {"type": "object", "properties": {"title": {"type": "string", "description": "Reminder title"}, "list_name": {"type": "string", "description": "List to search in (optional)"}}, "required": ["title"]}}},
    {"type": "function", "function": {"name": "reminders_delete", "description": "Delete a reminder (macOS only).", "parameters": {"type": "object", "properties": {"title": {"type": "string", "description": "Reminder title"}, "list_name": {"type": "string", "description": "List to search in (optional)"}}, "required": ["title"]}}},
    {"type": "function", "function": {"name": "reminders_search", "description": "Search reminders across all lists (macOS only).", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "Search term"}, "limit": {"type": "integer", "description": "Max results (default 20)"}}, "required": ["query"]}}},
]

TOOL_MAP = {
    "reminders_lists": reminders_lists,
    "reminders_list": reminders_list,
    "reminders_create": reminders_create,
    "reminders_complete": reminders_complete,
    "reminders_uncomplete": reminders_uncomplete,
    "reminders_delete": reminders_delete,
    "reminders_search": reminders_search,
}

PROMPT_EXTRA = (
    "APPLE REMINDERS (macOS):\n"
    "  Integriert die Apple Erinnerungen-App (nur auf diesem Mac).\n"
    "  - reminders_lists(): Alle Listen anzeigen\n"
    "  - reminders_list(list_name, include_completed): Erinnerungen einer Liste\n"
    "  - reminders_create(title, due_date='YYYY-MM-DD HH:MM', notes, list_name='Persönlich')\n"
    "  - reminders_complete(title) / reminders_uncomplete(title)\n"
    "  - reminders_delete(title)\n"
    "  - reminders_search(query): Suche über alle Listen\n"
    "\n"
    "  Beispiele:\n"
    "    'Erinnere mich morgen um 9 Uhr an das Meeting' -> reminders_create(title='Meeting', due_date='<morgen> 09:00', list_name='Persönlich')\n"
    "    'Was steht auf meiner Einkaufsliste?' -> reminders_list(list_name='Einkaufen')\n"
    "    'Welche Listen gibt es?' -> reminders_lists()\n"
)
