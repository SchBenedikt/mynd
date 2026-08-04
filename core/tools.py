import base64
import ipaddress
import json
import logging
import os
import re
import shlex
import socket
import subprocess
import sys
import tempfile
import threading
import time
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
import requests
from defusedxml import ElementTree

from .config import BASE, CHUNKS, EMBS, MEMORY_FILE, C
from .embed import embed
from .planner import create_plan as _plan_create
from .planner import delete_plan as _plan_delete
from .planner import get_plan as _plan_get
from .planner import list_plans as _plan_list
from .planner import update_step as _plan_update
from .reasoning import evaluate_reasoning as _evaluate_reasoning
from .reasoning import reason_step_by_step as _reason_step_by_step
from .reasoning import tree_of_thought as _tree_of_thought
from .reflection import get_daily_summary as _reflection_daily
from .reflection import get_failure_analysis, get_tool_performance
from .reflection import get_improvement_suggestions as _reflection_suggestions
from .reflection import prune_history as _reflection_prune
from .sandbox import SandboxUnavailableError, run_sandboxed
from .skills import learn_skill as _learn_skill
from .skills import recall_skills as _recall_skills
from .skills import skill_delete as _skill_delete
from .skills import skill_list as _skill_list
from .tool_creator import create_tool as _create_tool
from .tool_creator import delete_tool as _delete_tool
from .tool_creator import list_created_tools as _list_created_tools
from .vault import _vault_get, vault_delete, vault_get, vault_list, vault_set

warnings.filterwarnings('ignore', category=DeprecationWarning)
logger = logging.getLogger(__name__)
try:
    from ddgs import DDGS
    _DDGS_AVAILABLE = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        _DDGS_AVAILABLE = True
    except ImportError:
        _DDGS_AVAILABLE = False

PERMISSION_MODE = os.environ.get("MYND_PERMISSION_MODE", "ask").strip().lower()
if PERMISSION_MODE not in {"auto", "semi", "ask"}:
    PERMISSION_MODE = "ask"

PERMISSION_HELP = {
    "auto": "alle Bash-Befehle erlaubt",
    "semi": "Nachfrage bei kritischen Befehlen (rm, sudo, dd, mkfs, ...)",
    "ask": "Nachfrage bei JEDEM Bash-Befehl",
}

CRITICAL_PATTERNS = [
    " rm ", " rm -", " rmdir ", " mkfs", " dd ", " fdisk ", " parted ", " format ",
    " sudo ", " doas ", " pkexec ",
    " chmod ", " chown ", " chattr ",
    " shutdown ", " reboot ", " poweroff ", " halt ",
    " kill ", " pkill ",
    " systemctl ", " service ",
    " mount ", " umount ",
    ":(){",
]

# Web confirmation hook – replaced in web mode
_CONFIRM_TOOL_PENDING = None

_memory_lock = threading.Lock()

_TOOL_CODE_TAGS = (
    ('<tool_code>', '</tool_code>'),
    ('<tool_code>', '</minimax:tool_call>'),
    ('[TOOL_CALL]', '[/TOOL_CALL]'),
    ('<tool_call>', '</tool_call>'),
)


def _extract_tagged_blocks(text, opening, closing):
    blocks = []
    offset = 0
    while len(blocks) < 20:
        start = text.find(opening, offset)
        if start < 0:
            break
        start += len(opening)
        end = text.find(closing, start)
        if end < 0:
            break
        blocks.append(text[start:end].strip())
        offset = end + len(closing)
    return blocks


INPUT_MAX = 100000

_rate_limit_data = defaultdict(list)
_rate_limit_lock = threading.Lock()


def _check_rate_limit(tool_name):
    now = time.monotonic()
    with _rate_limit_lock:
        calls = _rate_limit_data[tool_name]
        calls = [t for t in calls if now - t < 1.0]
        if len(calls) >= 10:
            return False, f"⏱ Rate limit exceeded for {tool_name} (>10 calls/second)"
        calls.append(now)
        _rate_limit_data[tool_name] = calls
        return True, None


def _validate_str(value, name, max_len=INPUT_MAX):
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string, got {type(value).__name__}")
    if len(value) > max_len:
        raise ValueError(f"{name} exceeds maximum length ({max_len})")
    if '\0' in value:
        raise ValueError(f"{name} contains null bytes")
    return value


def _rate_limited(name):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            ok, err = _check_rate_limit(name)
            if not ok:
                return err
            return fn(*args, **kwargs)
        wrapper.__name__ = fn.__name__
        wrapper.__module__ = fn.__module__
        return wrapper
    return decorator


def _parse_tool_arguments(text):
    arguments = {}
    for match in re.finditer(
        r'<param\s+name\s*=\s*["\']([^"\']+)["\']\s*>([^<]*)</param>',
        text,
    ):
        arguments[match.group(1).strip()] = match.group(2).strip()
    if arguments:
        return arguments
    for match in re.finditer(r'(\w+)\s*=\s*["\']([^"\']+)["\']', text):
        if match.group(1) != 'name':
            arguments[match.group(1)] = match.group(2)
    if arguments:
        return arguments
    for match in re.finditer(r'--(\w+)\s+["\']([^"\']+)["\']', text):
        arguments[match.group(1)] = match.group(2)
    return arguments


def _parse_tool_code_fallback(text):
    """Parse bounded fallback tool markup emitted by models without tool calling."""
    if not text:
        return []
    source = str(text)[:100_000]
    blocks = []
    for opening, closing in _TOOL_CODE_TAGS:
        blocks.extend(_extract_tagged_blocks(source, opening, closing))
    if not blocks:
        if '<tool' not in source:
            return []
        blocks = [source]

    known_browser_tools = {
        'browser_click', 'browser_evaluate', 'browser_extract', 'browser_navigate',
        'browser_open', 'browser_screenshot', 'browser_scroll', 'browser_search',
        'browser_type',
    }
    calls = []
    for block in blocks[:20]:
        structured_calls = []
        for match in re.finditer(
            r'<tool\s+name\s*=\s*["\']([^"\']+)["\']\s*([^<>]*?)/>',
            block,
        ):
            structured_calls.append((match.group(1), match.group(2)))
        for match in re.finditer(
            r'<tool\s+name\s*=\s*["\']([^"\']+)["\']\s*>([^<]*(?:<param[^>]*>[^<]*</param>[^<]*)*)</tool>',
            block,
        ):
            structured_calls.append((match.group(1), match.group(2)))
        if structured_calls:
            for name, body in structured_calls[:20 - len(calls)]:
                calls.append({
                    'name': name.strip(),
                    'args': _parse_tool_arguments(body),
                })
            if len(calls) >= 20:
                break
            continue

        nested = re.search(r"tool\s*=>\s*['\"]([^'\"]+)['\"]", block)
        if nested:
            calls.append({
                'name': nested.group(1).strip(),
                'args': _parse_tool_arguments(block),
            })
            continue

        parts = block.split()
        if not parts:
            continue
        name = parts[0]
        if name not in known_browser_tools:
            continue
        arguments = _parse_tool_arguments(block)
        if not arguments:
            if name in {'browser_open', 'browser_navigate'} and len(parts) >= 2:
                arguments['url'] = parts[1]
            elif name == 'browser_search' and len(parts) >= 2:
                arguments['query'] = ' '.join(parts[1:])
            elif name in {'browser_click', 'browser_type'} and len(parts) >= 2:
                arguments['selector'] = parts[1]
                if name == 'browser_type' and len(parts) >= 3:
                    arguments['text'] = ' '.join(parts[2:])
            elif name == 'browser_extract' and len(parts) >= 2:
                arguments['mode'] = parts[1]
        calls.append({'name': name, 'args': arguments})
    return calls

def _request_tool_confirmation(tool_name, description):
    """Called by tools when user confirmation is required.
    In CLI mode: interactive input().
    In web mode: set _CONFIRM_TOOL_PENDING, return special string."""
    global _CONFIRM_TOOL_PENDING
    if _CONFIRM_TOOL_PENDING is not None:
        # Web mode – store pending and return special string
        _CONFIRM_TOOL_PENDING = {'tool': tool_name, 'description': description}
        return "⏳ TOOL_CONFIRM_REQUIRED: " + description
    display = description[:120] + ("..." if len(description) > 120 else "")
    ans = input(
        f"\n  {C.YELLOW}⚠️  {tool_name} ausführen?{C.RESET}\n    {display}\n  {C.CYAN}[j/N]{C.RESET}: "
    ).strip().lower()
    return ans in ("j", "ja", "y", "yes")


def _is_critical(cmd):
    c = " " + cmd.lower().strip() + " "
    if " > " in c or " >> " in c or " | " in c:
        return True
    for p in CRITICAL_PATTERNS:
        if p in c:
            return True
    return False


def _confirm_cmd(cmd):
    display = cmd[:120] + ("..." if len(cmd) > 120 else "")
    ans = input(
        f"\n  {C.YELLOW}⚠️  Befehl ausführen?{C.RESET}\n    $ {display}\n  {C.CYAN}[j/N]{C.RESET}: "
    ).strip().lower()
    return ans in ("j", "ja", "y", "yes")


def execute_bash(command):
    try:
        _validate_str(command, "command", max_len=10000)
    except ValueError as e:
        return f"❌ {e}"
    if len(command) < 1:
        return "❌ Empty command"
    _bash_dangerous = ['$(', '`', '${']
    for pat in _bash_dangerous:
        if pat in command:
            return f"❌ Dangerous pattern '{pat}' blocked in command"
    if PERMISSION_MODE == "ask":
        ok = _request_tool_confirmation("execute_bash", command)
        if ok is not True:
            return ok if isinstance(ok, str) else "⛔ Cancelled (not confirmed)"
    elif PERMISSION_MODE == "semi" and _is_critical(command):
        ok = _request_tool_confirmation("execute_bash", command)
        if ok is not True:
            return ok if isinstance(ok, str) else "⛔ Cancelled (not confirmed)"
    try:
        if 'cd ' in command and '&&' not in command and ';' not in command:
            return "⚠️ cd allein ist nicht persistent. Nutze '&&' zum Verketten, z.B. 'cd ordner && ls'"
        workspace = Path(os.getenv('MYND_WORKSPACE_DIR', BASE / 'data' / 'workspace'))
        workspace.mkdir(parents=True, exist_ok=True)
        r = run_sandboxed(['/bin/sh', '-c', command], cwd=workspace, timeout=60)
        out = r.stdout.strip()[:5000] if r.stdout.strip() else r.stderr.strip()[:2000]
        return out if out else "(leer)"
    except subprocess.TimeoutExpired:
        return "⏱ Timeout (60s)"
    except SandboxUnavailableError as e:
        return f"⛔ Sandbox unavailable; command was not executed: {e}"
    except Exception as e:
        return f"❌ {e}"


def execute_ssh(host="", command="", user="", port=22, key="", password="", profile=""):
    try:
        _validate_str(host, "host", max_len=500)
        _validate_str(command, "command", max_len=10000)
        _validate_str(user, "user", max_len=200)
        _validate_str(key, "key", max_len=50000)
        _validate_str(password, "password", max_len=50000)
        _validate_str(profile, "profile", max_len=200)
    except ValueError as e:
        return f"❌ {e}"

    if host:
        import re as _re
        host = host.strip()
        if not _re.match(r'^[a-zA-Z0-9.\-:\[\]]+$', host):
            return "❌ Invalid hostname characters"
        if host.startswith('.') or host.endswith('.'):
            return "❌ Hostname cannot start or end with a dot"
        if len(host) > 253:
            return "❌ Hostname too long"

    if port is not None:
        try:
            port = int(port)
            if port < 1 or port > 65535:
                return "❌ Port must be between 1 and 65535"
        except (ValueError, TypeError):
            return "❌ Invalid port number"

    if PERMISSION_MODE == "ask":
        ok = _request_tool_confirmation("execute_ssh", command)
        if ok is not True:
            return ok if isinstance(ok, str) else "⛔ Cancelled (not confirmed)"
    elif PERMISSION_MODE == "semi" and _is_critical(command):
        ok = _request_tool_confirmation("execute_ssh", command)
        if ok is not True:
            return ok if isinstance(ok, str) else "⛔ Cancelled (not confirmed)"
    keyfile = None
    try:
        if profile:
            base = f"vm/{profile}"
            if not host: host = _vault_get(f"{base}/ip")
            if not user: user = _vault_get(f"{base}/user") or "root"
            if not password: password = _vault_get(f"{base}/password")
            if not key: key = _vault_get(f"{base}/key")
            if port == 22:
                p = _vault_get(f"{base}/port")
                if p: port = int(p)
        else:
            if not host: host = _vault_get("vm/ip")
            if not user: user = _vault_get("vm/user") or "root"
            if not password: password = _vault_get("vm/password")
            if not key: key = _vault_get("vm/key")
        port = int(port)

        if not host:
            return "❌ Keine Host/IP. `vault_set vm/<profil>/ip <ip>` oder host-Parameter angeben."

        validated = command.strip()
        if not validated:
            return "❌ Ungültiger Befehl"
        cmd_parts = shlex.split(validated)

        ssh_base = ['ssh', '-o', 'StrictHostKeyChecking=accept-new',
                    '-o', 'UserKnownHostsFile=/dev/null',
                    '-p', str(port), f'{user}@{host}']
        if key:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.key', delete=False) as f:
                f.write(key)
                keyfile = f.name
            os.chmod(keyfile, 0o600)
            ssh_cmd = ['ssh', '-i', keyfile, '-o', 'StrictHostKeyChecking=accept-new',
                       '-o', 'UserKnownHostsFile=/dev/null',
                       '-p', str(port), f'{user}@{host}'] + cmd_parts
        elif password:
            # Pass the password via sshpass stdin (pipe) instead of the SSHPASS
            # environment variable, which is readable from /proc/<pid>/environ.
            ssh_cmd = ['sshpass', 'ssh', '-o', 'StrictHostKeyChecking=accept-new',
                       '-o', 'UserKnownHostsFile=/dev/null',
                       '-p', str(port), f'{user}@{host}'] + cmd_parts
        else:
            ssh_cmd = ssh_base + cmd_parts

        # Never leak the password into the subprocess environment.
        ssh_env = dict(os.environ)
        ssh_env.pop('SSHPASS', None)
        ssh_input = (password + '\n') if password else None
        r = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=60, env=ssh_env, input=ssh_input)
        if key and password and r.returncode != 0:
            first_err = (r.stderr or r.stdout or "").strip()
            password_cmd = ['sshpass', 'ssh'] + ssh_base[1:]
            r = subprocess.run(password_cmd, capture_output=True, text=True, timeout=60, env=ssh_env, input=password + '\n')
            if not (r.stdout or r.stderr).strip() and first_err:
                r.stderr = first_err
        out = r.stdout.strip()[:5000] if r.stdout.strip() else r.stderr.strip()[:2000]
        return out if out else "(leer)"
    except subprocess.TimeoutExpired:
        return "⏱ Timeout (60s)"
    except FileNotFoundError:
        return "❌ sshpass nicht installiert. `brew install sshpass` oder SSH-Key verwenden."
    except Exception:
        logger.exception("execute_ssh failed")
        return "❌ SSH-Ausführung fehlgeschlagen."
    finally:
        if keyfile:
            try: os.unlink(keyfile)
            except OSError: pass


def search_documents(query, top_k=10):
    try:
        _validate_str(query, "query", max_len=5000)
        chunks = json.loads(CHUNKS.read_text())
        embs = np.load(EMBS)
        qe = embed([query])[0]
        scores = np.array(
            [float(np.dot(qe, e) / (np.linalg.norm(qe) * np.linalg.norm(e) + 1e-10)) for e in embs]
        )
        top = np.argsort(scores)[-top_k:][::-1]
        parts = []
        for i in top:
            if scores[i] > 0.1:
                parts.append(
                    f"[{chunks[i]['source']}] (Score: {scores[i]:.2f})\n{chunks[i]['text'][:300]}"
                )
        return '\n\n---\n\n'.join(parts[:top_k]) if parts else "Keine Treffer."
    except Exception:
        logger.exception("search_documents failed")
        return "❌ Suche fehlgeschlagen"


def _kb_search_structured(query, top_k=6, min_score=0.1):
    """Semantische Suche über den lokalen Knowledge Base.

    Returns a list of dicts: {"source", "text", "score", "kind"}.
    kind is 'affine' when the source URI starts with affine://, else 'doc'.
    """
    try:
        chunks = json.loads(CHUNKS.read_text())
        embs = np.load(EMBS)
        qe = embed([query])[0]
        scores = np.array(
            [float(np.dot(qe, e) / (np.linalg.norm(qe) * np.linalg.norm(e) + 1e-10)) for e in embs]
        )
        top = np.argsort(scores)[-top_k:][::-1]
        out = []
        for i in top:
            if scores[i] > min_score:
                src = str(chunks[i].get('source', 'Unbekannt'))
                out.append({
                    'source': src,
                    'text': str(chunks[i].get('text', ''))[:400],
                    'score': round(float(scores[i]), 3),
                    'kind': 'affine' if src.lower().startswith('affine://') else 'doc',
                })
        return out
    except Exception:
        logger.exception("_kb_search_structured failed")
        return []


def _affine_search_structured(query, max_results=5):
    """Volltextsuche über AFFiNE-Inhalte (Titel + Body). Returns list of dicts."""
    try:
        from data.plugins import affine as _affine_mod
    except Exception:
        return []
    try:
        raw = _affine_mod.affine_search_content(query_text=query, max_results=max_results)
    except Exception:
        logger.exception("affine_search_content failed")
        return []
    if not isinstance(raw, str) or "❌" in raw or "Keine Treffer" in raw:
        return []
    out = []
    for block in re.split(r'\n  📄 ', raw):
        block = block.strip()
        if not block:
            continue
        lines = block.split('\n')
        first = _clean_title(lines[0].strip('* `').strip())
        snippet = next((line.strip(' _').strip() for line in lines[1:] if line.strip()), '')
        if not first or '🔍 Volltext-Suche' in first or 'max_results' in first or '… und weitere' in first:
            continue
        out.append({
            'source': f'affine://{first}',
            'title': first,
            'text': snippet[:300],
            'kind': 'affine',
        })
    return out[:max_results]


def _clean_title(text):
    """Strip markdown artefacts and collapse whitespace for use in link text."""
    if not text:
        return ''
    cleaned = re.sub(r'[*_~`]+', '', text)
    cleaned = cleaned.split('`')[0] if '`' in cleaned else cleaned
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def _web_search_structured(query, max_results=6):
    """Internetsuche via DuckDuckGo. Returns list of dicts {title, url, snippet}."""
    if not _DDGS_AVAILABLE:
        return []
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results, region='de-de'))
        out = []
        for r in results:
            title = (r.get('title') or '').strip()
            href = (r.get('href') or '').strip()
            body = (r.get('body') or '').strip()[:250]
            if title and href:
                out.append({'title': title, 'url': href, 'snippet': body})
        return out
    except Exception:
        logger.exception("web search failed in deep_research")
        return []


def deep_research(query, top_k=6, include_kb=True, include_affine=True, include_web=True):
    """Kombinierte Tiefen-Recherche über mehrere Wissensquellen.

    Durchsucht parallel (1) die lokale Knowledge Base (Nextcloud-Dokumente +
    bereits indexierte AFFiNE-Inhalte), (2) die AFFiNE-Volltextsuche und
    (3) das Internet. Liefert eine strukturierte Antwort mit klar getrennten,
    nummerierten Quellen, die die KI direkt zitieren kann.
    """
    try:
        _validate_str(query, "query", max_len=5000)
    except ValueError as e:
        return f"❌ {e}"

    sections = []
    source_index = 1
    all_sources = []

    def _push(section_title, items, fmt):
        nonlocal source_index
        if not items:
            return
        lines = [f"### {section_title}"]
        for item in items:
            label = f"({source_index})"
            lines.append(fmt(label, item))
            all_sources.append({'label': source_index, 'section': section_title, **item})
            source_index += 1
        sections.append('\n'.join(lines))

    if include_kb:
        kb = _kb_search_structured(query, top_k=top_k)
        _push("Lokale Dokumente & Notizen (Wissensbasis)", kb,
              lambda label, it: f"{label} **[{it['source']}]({it['source']})** (Score: {it['score']})\n   {it['text']}")

    if include_affine:
        affine = _affine_search_structured(query, max_results=5)
        _push("AFFiNE – persönliche Wissensdatenbank", affine,
              lambda label, it: f"{label} **[{it.get('title', it['source'])}]({it['source']})**\n   {it.get('text', '')}")

    if include_web:
        web = _web_search_structured(query, max_results=top_k)
        _push("Internet", web,
              lambda label, it: f"{label} [{it['title']}]({it['url']})\n   {it.get('snippet', '')}")

    if not sections:
        return f"❌ Keine Ergebnisse aus Knowledge Base, AFFiNE oder Web für '{query}'."

    lines = [
        "🔎 DEEP RESEARCH zu: „" + query + "“",
        "Die folgenden Quellen stammen aus mehreren unabhängigen Systemen "
        "(lokale Wissensbasis, AFFiNE, Internet). Zitiere sie in deiner Antwort "
        "mit den Nummern in Klammern, z. B. (1), (2), (3).\n",
    ]
    lines.append("\n\n".join(sections))
    lines.append("\n\n## Quellen")
    for s in all_sources:
        title = _clean_title(s.get('title') or s.get('source', ''))
        if s.get('url'):
            lines.append(f"({s['label']}) [{title}]({s['url']})")
        else:
            lines.append(f"({s['label']}) [{title}]({s['source']})")
    return "\n".join(lines)


def _workspace_path(path):
    if '\0' in str(path):
        raise ValueError('Path contains null bytes')
    root = Path(os.getenv('MYND_WORKSPACE_DIR', BASE / 'data' / 'workspace')).expanduser().resolve()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    _max_depth = 50
    if len(candidate.parts) > _max_depth:
        raise ValueError(f'Path exceeds maximum depth ({_max_depth})')
    candidate = candidate.resolve(strict=False)
    if candidate != root and root not in candidate.parents:
        raise ValueError(f'Path is outside the allowed workspace: {root}')
    return candidate


def read_local_file(path):
    try:
        _validate_str(path, "path", max_len=2000)
        p = _workspace_path(path)
        if not p.exists():
            return f"❌ Datei nicht gefunden: {p}"
        return p.read_text(encoding='utf-8', errors='replace')[:10000]
    except Exception as e:
        return f"❌ {e}"


def write_local_file(path, content):
    try:
        _validate_str(path, "path", max_len=2000)
        _validate_str(content, "content", max_len=1000000)
        p = _workspace_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"✅ {p} geschrieben ({len(content)} Zeichen)"
    except Exception as e:
        return f"❌ {e}"


def execute_python(code):
    try:
        _validate_str(code, "code", max_len=50000)
    except ValueError as e:
        return f"❌ {e}"
    if PERMISSION_MODE == "ask":
        ok = _request_tool_confirmation("execute_python", code[:120])
        if ok is not True:
            return ok if isinstance(ok, str) else "⛔ Cancelled (not confirmed)"
    elif PERMISSION_MODE == "semi" and _is_critical(code):
        ok = _request_tool_confirmation("execute_python", code[:120])
        if ok is not True:
            return ok if isinstance(ok, str) else "⛔ Cancelled (not confirmed)"
    try:
        compile(code, '<exec>', 'exec', flags=0x0)
        with tempfile.TemporaryDirectory(prefix='mynd_python_') as temporary:
            script = Path(temporary) / 'script.py'
            script.write_text(code, encoding='utf-8')
            result = run_sandboxed([sys.executable, '-I', '-S', str(script)], cwd=temporary, timeout=60)
        output = result.stdout[:4000]
        error = result.stderr[:2000]
        parts = []
        if output:
            parts.append(f"stdout:\n{output}")
        if error:
            parts.append(f"stderr:\n{error}")
        if result.returncode:
            parts.append(f"exit code: {result.returncode}")
        return '\n'.join(parts) or '(keine Ausgabe)'
    except SandboxUnavailableError as e:
        return f"⛔ Sandbox unavailable; Python was not executed: {e}"
    except subprocess.TimeoutExpired:
        return "⏱ Timeout (60s)"
    except Exception as e:
        return f"❌ Python-Fehler: {e}"


def think(thought, auto_plan=False):
    try:
        _validate_str(thought, "thought")
    except ValueError as e:
        return f"❌ {e}"
    complex_keywords = [
        'recherchiere', 'vergleiche', 'analysiere', 'erstelle', 'baue', 'entwickle',
        'konfiguriere', 'installiere', 'automatisiere', 'optimiere', 'migriere',
        'integriere', 'koordiniere', 'überwache', 'sammle', 'evaluiere', 'teste',
        'verhandle', 'bereite vor', 'strukturiere', 'dokumentiere',
    ]
    lines = [line.strip() for line in thought.split('\n') if line.strip()]
    is_complex = auto_plan or len(lines) > 2 or any(kw in thought.lower() for kw in complex_keywords)
    print(f"  {C.YELLOW}🧠 {thought[:500]}{C.RESET}", flush=True)
    if is_complex and len(lines) >= 2:
        plan = create_plan('\n'.join(lines), "Automatisch erstellter Plan aus think()")
        return f"📋 KOMPLEXE AUFGABE ERKANNT – Plan erstellt:\n\n{plan}\n\n📝 Ursprüngliche Überlegung: {thought[:500]}"
    if is_complex:
        plan = create_plan(thought, "Automatisch erstellter Plan aus think()")
        return f"📋 KOMPLEXE AUFGABE ERKANNT – Plan erstellt:\n\n{plan}\n\n📝 Ursprüngliche Überlegung: {thought[:500]}"
    return f"📝 Überlegung notiert: {thought[:500]}"


def prompt_user(message, secret=False):
    try:
        _validate_str(message, "message")
        if secret:
            import getpass
            val = getpass.getpass(f"  {C.CYAN}🔒 {message}{C.RESET} ")
        else:
            val = input(f"  {C.CYAN}💬 {message}{C.RESET} ").strip()
        return val if val else "(keine Eingabe)"
    except EOFError:
        return "(abgebrochen)"


def _validate_http_url(url):
    from urllib.parse import urlparse

    if url.lower().startswith(('gopher://', 'dict://', 'ftp://')):
        raise ValueError(f'Blocked URL scheme in: {url[:30]}')

    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname:
        raise ValueError('Only absolute http:// and https:// URLs are allowed')
    hostname = parsed.hostname.rstrip('.').lower()

    allow_private = {
        item.strip().lower()
        for item in os.getenv('MYND_HTTP_ALLOW_PRIVATE_HOSTS', '').split(',')
        if item.strip()
    }
    if hostname in allow_private:
        return

    # Block raw IP addresses to prevent hex/octal bypass attacks
    try:
        ipaddress.ip_address(hostname)
        raise ValueError(f'Raw IP address hostname is not allowed: {hostname}')
    except ValueError:
        if hostname.replace('.', '').replace(':', '').isdigit() and '.' in hostname:
            raise ValueError(f'Raw IP address hostname is not allowed: {hostname}')

    try:
        addrs_before = {item[4][0] for item in socket.getaddrinfo(hostname, parsed.port or 443)}
    except socket.gaierror as exc:
        raise ValueError(f'Host resolution failed: {hostname}') from exc

    # Simple DNS rebinding check: resolve again and compare
    try:
        addrs_after = {item[4][0] for item in socket.getaddrinfo(hostname, parsed.port or 443)}
        if addrs_before != addrs_after:
            raise ValueError(f'DNS rebinding detected for: {hostname}')
    except socket.gaierror:
        pass

    addresses = addrs_before
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ValueError(f'Private or reserved address is blocked: {address}')


def safe_http_request(method, url, *, headers=None, data=None, timeout=60, max_bytes=1_000_000):
    """Perform an HTTP request with SSRF-safe redirect validation and a size limit."""
    current_url = url
    request_headers = dict(headers or {})
    for _ in range(6):
        _validate_http_url(current_url)
        response = requests.request(
            method.upper(),
            current_url,
            data=data,
            headers=request_headers or None,
            timeout=timeout,
            allow_redirects=False,
            stream=True,
        )
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get('Location')
            response.close()
            if not location:
                raise ValueError('Redirect response did not include a Location header')
            from urllib.parse import urljoin
            current_url = urljoin(current_url, location)
            continue

        content_length = response.headers.get('Content-Length')
        if content_length and int(content_length) > max_bytes:
            response.close()
            raise ValueError(f'Response exceeds the {max_bytes}-byte limit')
        chunks = []
        total = 0
        read_deadline = time.monotonic() + timeout
        for chunk in response.iter_content(chunk_size=16_384):
            if time.monotonic() > read_deadline:
                response.close()
                raise ValueError('Response read timed out')
            total += len(chunk)
            if total > max_bytes:
                response.close()
                raise ValueError(f'Response exceeds the {max_bytes}-byte limit')
            chunks.append(chunk)
        response._content = b''.join(chunks)
        response._content_consumed = True
        return response
    raise ValueError('Too many redirects')


def http_request(method="GET", url="", headers=None, body="", auth_user="", auth_pass=""):
    try:
        _validate_str(url, "url", max_len=10000)
        _validate_str(method, "method", max_len=10)
        _validate_str(body, "body", max_len=1000000)
        _validate_str(auth_user, "auth_user", max_len=5000)
        _validate_str(auth_pass, "auth_pass", max_len=5000)
        h = {}
        if headers:
            if isinstance(headers, str):
                try:
                    h = json.loads(headers)
                except (json.JSONDecodeError, TypeError):
                    return f"❌ headers ist kein gültiges JSON: {headers[:200]}"
            elif isinstance(headers, dict):
                h = dict(headers)
        if "Content-Type" not in h and method.upper() in ("POST", "PUT", "PATCH"):
            h["Content-Type"] = "application/json"
        if auth_user and auth_pass is not None:
            auth_bytes = f"{auth_user}:{auth_pass}".encode()
            h["Authorization"] = "Basic " + base64.b64encode(auth_bytes).decode('ascii')
        r = safe_http_request(method, url, data=body or None, headers=h or None, timeout=60, max_bytes=1_000_000)

        ct = r.headers.get("Content-Type", "")
        if "application/json" in ct:
            data = json.dumps(r.json(), indent=2, ensure_ascii=False)
        else:
            data = r.text[:5000]
        out = f"Status: {r.status_code}\n{data[:5000]}"
        if len(r.text) > 5000:
            out += f"\n... (gekürzt, {len(r.text)} total)"
        return out
    except requests.exceptions.Timeout:
        return "⏱ Timeout (60s)"
    except (ValueError, requests.exceptions.SSLError):
        logger.exception("http_request blocked due to validation/SSL error")
        return "❌ Request blocked."
    except Exception:
        logger.exception("http_request failed")
        return "❌ Anfrage fehlgeschlagen."


def image_search(query, max_results=6):
    """Durchsucht DuckDuckGo nach Bildern und liefert Markdown-kodierte Thumbnails + Quellen."""
    try:
        _validate_str(query, "query", max_len=5000)
    except ValueError as e:
        return f"❌ {e}"
    if not _DDGS_AVAILABLE:
        return '❌ Keine Suchbibliothek verfügbar (pip install ddgs)'
    try:
        max_results = max(1, min(int(max_results or 6), 12))
        with DDGS() as ddgs:
            images = list(ddgs.images(query, max_results=max_results))
        if not images:
            return f"Keine Bilder gefunden für '{query}'."
        out = [f"🔍 Bilder-Suche nach '{query}':\n"]
        for i, img in enumerate(images[:max_results], 1):
            src = (img.get("thumbnail") or img.get("image", "") or "").replace(" ", "%20")
            url = (img.get("url") or img.get("image", "") or "").replace(" ", "%20")
            title = (img.get("title", "") or "").strip()[:80]
            out.append(f"  {i}. [![{title}]({src})]({url})")
            out.append(f"     [{title}]({url})")
        return "\n".join(out)
    except Exception as e:
        return f"❌ Bildersuche fehlgeschlagen: {e}"

def web_search(query, max_results=10):
    try:
        _validate_str(query, "query", max_len=5000)
    except ValueError as e:
        return f"❌ {e}"
    if not _DDGS_AVAILABLE:
        return '❌ Keine Suchbibliothek verfügbar (pip install ddgs)'
    try:
        max_results = max(1, min(int(max_results or 10), 20))
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results, region='de-de'))
        if not results:
            return f"Keine Web-Ergebnisse für '{query}'."
        out = f"Web-Suche nach '{query}':\n\n"
        for i, r in enumerate(results, 1):
            title = (r.get('title') or '').strip()
            href = (r.get('href') or '').strip()
            body = (r.get('body') or '').strip()[:300]
            out += f"{i}. [{title}]({href})\n   {href}\n   {body}\n\n"
        return out.strip()
    except Exception as e:
        return f'❌ Web-Suche fehlgeschlagen: {e}'

NEWS_FEEDS = [
    ("Tagesschau", "https://www.tagesschau.de/xml/rss2", "allgemein"),
    ("Spiegel", "https://www.spiegel.de/schlagzeilen/index.rss", "allgemein"),
    ("Heise", "https://www.heise.de/rss/heise-atom.xml", "technologie"),
]

def _extract_web_search_results(raw):
    entries = []
    for m in re.finditer(r'\d+\.\s+\[(.*?)\]\((.*?)\)(?:\n\s+.*?)?(?:\n\s+(.*?))?(?:\n\n|$)', raw or '', re.DOTALL):
        title = (m.group(1) or '').strip()
        url = (m.group(2) or '').strip()
        snippet = (m.group(3) or '').strip()
        if title and url:
            entries.append((title, url, snippet))
    return entries

def _news_queries_for_category(category):
    if category == "technologie":
        return [
            "Technologie Neuigkeiten heute",
            "KI News heute",
            "IT Security News heute"
        ]
    return [
        "Neuigkeiten heute Deutschland",
        "Wichtige Nachrichten heute",
        "Aktuelle Welt Nachrichten heute"
    ]

def _fetch_news_from_rss(category, max_results):
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    results = []
    seen = set()
    feeds = NEWS_FEEDS if category == "top" else [f for f in NEWS_FEEDS if category in f[2]]
    if not feeds:
        feeds = NEWS_FEEDS
    for name, url, _tag in feeds:
        try:
            r = requests.get(url, timeout=10, headers=headers)
            root = ElementTree.fromstring(r.content)
            is_atom = 'http://www.w3.org/2005/Atom' in r.text[:300]
            if is_atom:
                items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
            else:
                items = root.findall(".//item")
            for item in items:
                if is_atom:
                    title = item.findtext("{http://www.w3.org/2005/Atom}title", "")
                    link_el = item.find("{http://www.w3.org/2005/Atom}link")
                    link = link_el.get("href", "") if link_el is not None else ""
                    pub = item.findtext("{http://www.w3.org/2005/Atom}published", "")
                else:
                    title = item.findtext("title", "")
                    link = item.findtext("link", "")
                    pub = item.findtext("pubDate", "")
                dedup = title.lower().strip()
                if dedup and dedup not in seen:
                    seen.add(dedup)
                    title = title.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
                    if pub and len(pub) > 20:
                        pub = pub[:16].strip()
                    tag = f"[{name}]"
                    results.append((pub, tag, title, link))
                    if len(results) >= max_results:
                        return results
        except Exception:
            continue
    return results

def fetch_news(category="top", max_results=10):
    try:
        _validate_str(category, "category", max_len=200)
        max_results = max(1, min(int(max_results or 10), 20))
        category = (category or "top").strip().lower()
        if category not in ("top", "technologie"):
            category = "top"

        web_hits = []
        seen = set()
        queries = _news_queries_for_category(category)

        if _DDGS_AVAILABLE:
            try:
                with DDGS() as ddgs:
                    for q in queries:
                        results = list(ddgs.news(q, max_results=min(8, max_results), region='de-de'))
                        for r in results:
                            title = (r.get('title') or '').strip()
                            url = (r.get('url') or r.get('link') or '').strip()
                            snippet = (r.get('body') or r.get('snippet') or '').strip()
                            dedup = (title.lower(), url)
                            if dedup not in seen and title:
                                seen.add(dedup)
                                web_hits.append((title, url, snippet))
                                if len(web_hits) >= max_results:
                                    break
                        if len(web_hits) >= max_results:
                            break
            except Exception:
                pass

        rss_fill = []
        if len(web_hits) < max_results:
            rss_fill = _fetch_news_from_rss(category, max_results=max_results - len(web_hits))

        if not web_hits and not rss_fill:
            return "Keine aktuellen Nachrichten gefunden."

        out = f"📰 AKTUELLE NACHRICHTEN ({category.upper()})\n\n"
        if web_hits:
            out += "Web-Multi-Quellen:\n"
            for title, url, snippet in web_hits[:max_results]:
                out += f"- {title}\n  {url}\n"
                if snippet:
                    out += f"  {snippet[:220]}\n"
            out += "\n"

        if rss_fill:
            out += "RSS-Ergänzung:\n"
            for _pub, tag, title, link in rss_fill:
                out += f"- {title} ({tag})\n  {link}\n"

        return out.strip()
    except Exception as e:
        return f"❌ News-Fehler: {e}"

def memory_get(key=""):
    try:
        _validate_str(key, "key", max_len=5000)
        m = json.loads(MEMORY_FILE.read_text()) if MEMORY_FILE.exists() else {}
        if key:
            return m.get(key, "")
        return '\n'.join(f"{k}: {v}" for k, v in sorted(m.items())) if m else "(leer)"
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return "❌ Fehler"
def memory_set(key, value):
    with _memory_lock:
        try:
            _validate_str(key, "key", max_len=5000)
            _validate_str(value, "value", max_len=100000)
            m = json.loads(MEMORY_FILE.read_text()) if MEMORY_FILE.exists() else {}
            m[key] = value
            MEMORY_FILE.write_text(json.dumps(m, indent=2, ensure_ascii=False))
            return f"✅ `{key}` gespeichert"
        except Exception as e:
            return f"❌ {e}"


def memory_delete(key):
    with _memory_lock:
        try:
            _validate_str(key, "key", max_len=5000)
            m = json.loads(MEMORY_FILE.read_text()) if MEMORY_FILE.exists() else {}
            if key in m:
                del m[key]
                MEMORY_FILE.write_text(json.dumps(m, indent=2, ensure_ascii=False))
                return f"🗑 `{key}` gelöscht"
            return f"❌ `{key}` nicht gefunden"
        except Exception as e:
            return f"❌ {e}"


# ── Reflection ─────────────────────────────────────────────────

def reflect_on_failure(tool_name="", max_recent=5):
    try:
        _validate_str(tool_name, "tool_name", max_len=200)
    except ValueError as e:
        return f"❌ {e}"
    analysis = get_failure_analysis(tool_name=tool_name or None, max_recent=max_recent)
    if analysis:
        return analysis
    return 'Keine relevanten Fehlermuster gefunden.'


def reset_failures(tool_name=""):
    try:
        _validate_str(tool_name, "tool_name", max_len=200)
    except ValueError as e:
        return f"❌ {e}"
    from .reflection import _load as _rl
    from .reflection import _save as _rs
    data = _rl()
    if tool_name:
        data['consecutive_failures'].pop(tool_name, None)
    else:
        data['consecutive_failures'] = {}
    _rs(data)
    return '✅ Fehlerzähler zurückgesetzt.'


# ── Skill Learning & Retrieval ────────────────────────────────

def learn_skill(name, description, steps, tags="", context=""):
    try:
        _validate_str(name, "name", max_len=500)
        _validate_str(description, "description", max_len=5000)
        _validate_str(tags, "tags", max_len=5000)
        _validate_str(context, "context", max_len=100000)
    except ValueError as e:
        return f"❌ {e}"
    if isinstance(steps, str):
        try:
            _validate_str(steps, "steps", max_len=100000)
            steps = json.loads(steps)
        except (json.JSONDecodeError, TypeError):
            return '❌ steps muss ein JSON-Array sein.'
    tag_list = [t.strip() for t in tags.split(',') if t.strip()] if tags else []
    return _learn_skill(name, description, steps, tags=tag_list, context=context)


def recall_skills(context, max_results=5):
    try:
        _validate_str(context, "context", max_len=100000)
    except ValueError as e:
        return f"❌ {e}"
    results = _recall_skills(context, max_results=max_results)
    if not results:
        return 'Keine relevanten Skills gefunden.'
    lines = [f'Relevante Skills für: {context}', '']
    for r in results:
        score_display = '⭐' * min(int(r['relevance'] // 5) + 1, 5)
        lines.append(f'{score_display} {r["name"]}')
        lines.append(f'   {r["description"]}')
        tags = ', '.join(r.get('tags', []))
        if tags:
            lines.append(f'   Tags: {tags}')
        if r.get('pattern'):
            lines.append(f'   Schritte: {len(r["pattern"])}')
        lines.append('')
    return '\n'.join(lines).strip()


def list_skills(tag=""):
    try:
        _validate_str(tag, "tag", max_len=200)
    except ValueError as e:
        return f"❌ {e}"
    results = _skill_list(tag=tag)
    if not results:
        return 'Keine Skills gespeichert.'
    lines = ['📋 Gespeicherte Skills:', '']
    for r in results:
        tags = ', '.join(r.get('tags', []))
        tag_str = f' [{tags}]' if tags else ''
        lines.append(f'  • {r["name"]}{tag_str} – {r["description"]}')
    lines.append(f'\n{len(results)} Skills insgesamt.')
    return '\n'.join(lines)


def delete_skill(name):
    try:
        _validate_str(name, "name", max_len=500)
    except ValueError as e:
        return f"❌ {e}"
    return _skill_delete(name)


def delegate(task, context="", model=""):
    """Delegate a sub-task to a focused sub-agent. Use for complex multi-step
    research, parallel analysis, or when you need a dedicated agent to work
    on a sub-problem while you handle the main task."""
    try:
        _validate_str(task, "task", max_len=50000)
        _validate_str(context, "context", max_len=100000)
        _validate_str(model, "model", max_len=200)
        prompt = f"Du bist ein fokussierter Sub-Agent. Löse folgende Aufgabe:\n\n{task}"
        if context:
            prompt += f"\n\nKontext:\n{context}"
        prompt += "\n\nAntworte ausführlich und präzise."
        cfg_path = Path(__file__).resolve().parent.parent / 'data' / 'ai_config.json'
        cfg = {"model": os.getenv('OLLAMA_MODEL', 'gemma3:latest'), "base_url": "http://127.0.0.1:11434"}
        if cfg_path.exists():
            try:
                c = json.loads(cfg_path.read_text())
                cfg["model"] = c.get("model", cfg["model"])
                cfg["base_url"] = c.get("base_url", c.get("ollama_host", cfg["base_url"]))
            except Exception:
                pass
        if model:
            cfg["model"] = model
        resp = requests.post(
            f"{cfg['base_url']}/api/chat",
            json={"model": cfg["model"], "messages": [{"role": "user", "content": prompt}], "stream": False},
            timeout=120,
        )
        data = resp.json()
        content = data.get("message", {}).get("content", "") or data.get("response", "")
        return f"📋 SUB-AGENT ERGEBNIS (Aufgabe: {task[:100]}...):\n\n{content[:3000]}"
    except Exception as e:
        return f"❌ Sub-Agent Fehler: {e}"


def create_plan(steps, description=""):
    """Create a structured multi-step plan before executing. Use this for
    complex tasks that need coordination of multiple tools across multiple rounds.
    Returns the plan as a checklist with tracking ID."""
    try:
        _validate_str(steps, "steps", max_len=50000)
        _validate_str(description, "description", max_len=5000)
        plan_id, result = _plan_create(steps, description=description)
        if plan_id:
            return f'📋 Plan-ID: {plan_id}\n\n{result}'
        return result
    except Exception:
        logger.exception("create_plan failed")
        return "❌ Plan-Erstellung fehlgeschlagen."


def get_plan(plan_id):
    try:
        _validate_str(plan_id, "plan_id", max_len=200)
        _, result = _plan_get(plan_id)
        return result
    except Exception:
        logger.exception("get_plan failed")
        return "❌ Plan abrufen fehlgeschlagen."


def update_plan_step(plan_id, step_id, status, result=""):
    try:
        _validate_str(plan_id, "plan_id", max_len=200)
        _validate_str(status, "status", max_len=50)
        _validate_str(result, "result", max_len=50000)
        return _plan_update(plan_id, int(step_id), status, result=result)
    except Exception:
        logger.exception("update_plan_step failed")
        return "❌ Plan-Update fehlgeschlagen."


def list_plans(status=""):
    try:
        _validate_str(status, "status", max_len=200)
        plans = _plan_list(status=status or None)
        if not plans:
            return "Keine Pläne gefunden."
        lines = ["📋 Pläne:", ""]
        for p in plans:
            lines.append(f'  • {p["id"]} [{p["status"]}] {p["progress"]} – {p["description"][:60]}')
        return "\n".join(lines)
    except Exception:
        logger.exception("list_plans failed")
        return "❌ Plan-Liste fehlgeschlagen."


def delete_plan(plan_id):
    try:
        _validate_str(plan_id, "plan_id", max_len=200)
        return _plan_delete(plan_id)
    except Exception:
        logger.exception("delete_plan failed")
        return "❌ Plan-Löschen fehlgeschlagen."


# ── Performance Analytics ─────────────────────────────────────

def analyze_performance(tool_name=""):
    try:
        _validate_str(tool_name, "tool_name", max_len=200)
        stats = get_tool_performance(tool_name=tool_name or None)
        if not stats:
            return "Keine Daten verfügbar."
        lines = [f'📊 Performance-Analyse{f" für {tool_name}" if tool_name else ""}:', '']
        for name, s in sorted(stats.items(), key=lambda x: x[1]['success_rate']):
            bar_len = int(s['success_rate'] / 10)
            bar = '█' * bar_len + '░' * (10 - bar_len)
            lines.append(
                f'  {bar} {name}: {s["success_rate"]:.0f}% ({s["calls"]}x, '
                f'Ø {s["avg_ms"]:.0f}ms, max {s["max_ms"]}ms)'
            )
        return '\n'.join(lines)
    except Exception:
        logger.exception("analyze_performance failed")
        return '❌ Performance-Analyse fehlgeschlagen.'


def get_improvement_suggestions():
    try:
        return _reflection_suggestions()
    except Exception:
        logger.exception("get_improvement_suggestions failed")
        return '❌ Verbesserungsvorschläge fehlgeschlagen.'


def get_daily_summary():
    try:
        return _reflection_daily()
    except Exception:
        logger.exception("get_daily_summary failed")
        return '❌ Tagesübersicht fehlgeschlagen.'


def prune_history(days=30):
    try:
        return _reflection_prune(days=days)
    except Exception:
        logger.exception("prune_history failed")
        return '❌ Aufräumen fehlgeschlagen.'


# ── Advanced Reasoning ────────────────────────────────────────

def reason_deep(problem, method="tot", branches=3, depth=3, steps=""):
    """Führe TIEFGEHENDE Reasoning-Analyse durch. Nutze DAS bei komplexen
    Problemen, die mehrstufiges Denken erfordern.

    Methoden:
      tot  – Tree-of-Thought: mehrere Denkpfade werden parallel erkundet,
             evaluiert und der beste wird ausgewählt. Ideal bei offenen,
             mehrdeutigen Problemen.
      step – Schritt-für-Schritt: logische Schritte mit Verifikation.
             Ideal bei sequenziellen oder mathematischen Problemen.

    Returns a structured analysis with evaluations and confidence."""
    try:
        _validate_str(problem, "problem", max_len=50000)
        _validate_str(method, "method", max_len=20)
        if method == "step":
            steps_list = [s.strip() for s in steps.split("\n") if s.strip()] if steps else None
            result = _reason_step_by_step(problem, steps=steps_list)
        else:
            result = _tree_of_thought(problem, branches=branches, depth=depth)
        return json.dumps(result, ensure_ascii=False, indent=2)[:8000]
    except Exception:
        logger.exception("reason_deep failed")
        return "❌ Reasoning fehlgeschlagen."


def evaluate_reasoning(problem, reasoning):
    """Bewerte und bewerte einen Reasoning-Pfad. Gibt Score (0-1),
    Stärken, Schwächen und Verbesserungsvorschläge.
    Nutze DAS um die Qualität deiner Analysen zu prüfen."""
    try:
        _validate_str(problem, "problem", max_len=50000)
        _validate_str(reasoning, "reasoning", max_len=50000)
        result = _evaluate_reasoning(problem, reasoning)
        return json.dumps(result, ensure_ascii=False, indent=2)[:8000]
    except Exception:
        logger.exception("evaluate_reasoning failed")
        return "❌ Evaluierung fehlgeschlagen."


# ── Sub-Agent Delegation (Enhanced) ───────────────────────────

def agent_browser(action, selector="", text="", url=""):
    """Steuere den Browser via agent-browser CLI.

    Actions:
      goto <url>        – Seite öffnen
      click <selector>  – Element klicken (CSS oder ref=...)
      type <selector> <text> – Text eingeben
      snapshot          – Accessibility-Tree ausgeben
      screenshot        – Screenshot (base64) machen
      extract <selector> – Text extrahieren
      back              – Zurück
      scroll <dir>      – Scrollen (up/down)
    """
    try:
        _validate_str(action, "action", max_len=50)
        _validate_str(selector, "selector", max_len=5000)
        _validate_str(text, "text", max_len=50000)
        _validate_str(url, "url", max_len=10000)
        cmd = ["agent-browser"]
        action = action.strip().lower()
        if action == "goto" and url:
            cmd += ["goto", url]
        elif action == "click" and selector:
            cmd += ["click", selector]
        elif action == "type" and selector and text:
            cmd += ["type", selector, text]
        elif action == "snapshot":
            cmd += ["snapshot"]
        elif action == "screenshot":
            import tempfile
            tmp = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            tmp.close()
            cmd += ["screenshot", tmp.name]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if r.returncode != 0:
                    return f"❌ Screenshot-Fehler: {r.stderr[:500]}"
                data = base64.b64encode(open(tmp.name, 'rb').read()).decode()
                return json.dumps({"screenshot": data[:500000], "screenshot_available": True, "action": "screenshot"})
            finally:
                if os.path.exists(tmp.name):
                    os.unlink(tmp.name)
        elif action == "extract" and selector:
            cmd += ["extract", selector]
        elif action == "back":
            cmd += ["back"]
        elif action in ("scroll", "scroll_up", "scroll_down"):
            direction = action.replace("scroll_", "").replace("scroll", "down") or "down"
            cmd += ["scroll", direction]
        else:
            return f"❌ Unbekannte agent-browser Aktion: {action}. Erlaubt: goto, click, type, snapshot, screenshot, extract, back, scroll"

        if action != "screenshot":
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                return f"❌ agent-browser Fehler: {r.stderr[:500]}"
            output = r.stdout[:3000] or r.stderr[:500] or "(leer)"
            return json.dumps({
                "action": action,
                "result": output,
                "screenshot_available": False,
            })
    except FileNotFoundError:
        return "❌ agent-browser nicht installiert. Installiere es via: brew install agent-browser"
    except subprocess.TimeoutExpired:
        return "❌ agent-browser Zeitüberschreitung (>30s)"
    except Exception as e:
        return f"❌ agent-browser Fehler: {e}"


# ── Tool Creation ─────────────────────────────────────────────

def create_tool(name, description, parameters, code):
    try:
        _validate_str(name, "name", max_len=500)
        _validate_str(description, "description", max_len=5000)
        _validate_str(code, "code", max_len=100000)
    except ValueError as e:
        return f"❌ {e}"
    return _create_tool(name, description, parameters, code)


def delete_tool(name):
    try:
        _validate_str(name, "name", max_len=500)
    except ValueError as e:
        return f"❌ {e}"
    return _delete_tool(name)


def list_created_tools():
    return _list_created_tools()


CORE_TOOLS = [
    {"type": "function", "function": {
        "name": "execute_bash",
        "description": "Führe einen Bash-Befehl aus. Achtung: Sonderzeichen wie !, %, ä im Befehl oder Passwort escaped werden! Bei Problemen mit Escaping: python3 -c \"import requests; …\" nutzen (kein Shell-Escaping nötig). Nutze absolute Pfade oder workdir – cd ist nicht persistent.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string", "description": "Der Bash-Befehl"}}, "required": ["command"]}
    }},
    {"type": "function", "function": {
        "name": "execute_python",
        "description": "Führe Python-Code aus. Nutze DAS für Berechnungen, Datum/Uhrzeit-Prüfungen, Daten-Analyse, URL-Inhalte laden (requests.get()), Formatierungen, JSON-Transformationen, Mathe, Statistik, Datei-Erstellung (Excel/openpyxl, Word/python-docx, PowerPoint/python-pptx) oder wenn execute_bash zu umständlich ist. Verwende KEIN input() oder Aufrufe, die auf User-Eingabe warten. Standard-Bibliothek + requests, openpyxl, docx, pptx verfügbar.",
        "parameters": {"type": "object", "properties": {
            "code": {"type": "string", "description": "Python-Code (KEIN input() oder interaktive Aufrufe). Ergebnis per print() ausgeben."}
        }, "required": ["code"]}
    }},
    {"type": "function", "function": {
        "name": "execute_ssh",
        "description": "Führe Befehl per SSH auf Remote-Host aus. Vault-Schema: vm/<profil>/ip, vm/<profil>/user, vm/<profil>/password, vm/<profil>/key. Ohne profile: vm/ip, vm/user etc.",
        "parameters": {"type": "object", "properties": {
            "host": {"type": "string", "description": "Host/IP (optional)"},
            "command": {"type": "string", "description": "Befehl auf Remote-Host"},
            "user": {"type": "string", "description": "SSH-User (optional)"},
            "port": {"type": "integer", "description": "SSH-Port (default 22)", "default": 22},
            "key": {"type": "string", "description": "Privat-Key als String (optional)"},
            "password": {"type": "string", "description": "Passwort (optional)"},
            "profile": {"type": "string", "description": "VM-Profilname für Vault-Prefix vm/<profil>/ (optional)"}
        }, "required": ["command"]}
    }},
    {"type": "function", "function": {
        "name": "search_documents",
        "description": "Durchsuche die indexierten Nextcloud-Dokumente semantisch nach einem Begriff.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Suchbegriff oder Frage"},
            "top_k": {"type": "integer", "description": "Anzahl Ergebnisse (default 10)", "default": 10}
        }, "required": ["query"]}
    }},
    {"type": "function", "function": {
        "name": "deep_research",
        "description": "KOMBINIERTE Tiefen-Recherche über ALLE Wissensquellen in EINEM Aufruf: (1) lokale Wissensbasis (Nextcloud-Dokumente + indexierte AFFiNE-Inhalte), (2) AFFiNE-Volltextsuche, (3) Internet. Liefert nummerierte Quellen, die du direkt zitieren kannst. Nutze DAS für komplexe Recherche-Fragen, bei denen mehrere Quellen relevant sind – statt mehrere Einzel-Suchen zu starten. Optional können Quellen per include_kb/include_affine/include_web deaktiviert werden.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Suchbegriff oder Frage"},
            "top_k": {"type": "integer", "description": "Anzahl Ergebnisse pro Quelle (default 6)", "default": 6},
            "include_kb": {"type": "boolean", "description": "Lokale Wissensbasis durchsuchen (default true)", "default": True},
            "include_affine": {"type": "boolean", "description": "AFFiNE durchsuchen (default true)", "default": True},
            "include_web": {"type": "boolean", "description": "Internet durchsuchen (default true)", "default": True}
        }, "required": ["query"]}
    }},
    {"type": "function", "function": {
        "name": "web_search",
        "description": "Durchsuche das INTERNET via DuckDuckGo nach aktuellen Informationen, Nachrichten, Webseiten. Nutze DAS für aktuelle Themen, die NICHT in den indexierten Dokumenten sind. Wenn der User dir eine URL gibt, rufe http_request auf, um deren Inhalt zu laden.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Suchbegriff oder Frage"},
            "max_results": {"type": "integer", "description": "Anzahl Ergebnisse (default 10)", "default": 10}
        }, "required": ["query"]}
    }},
    {"type": "function", "function": {
        "name": "fetch_news",
        "description": "Rufe AKTUELLE NACHRICHTEN über WEB-MULTI-QUELLEN ab. RSS wird nur ergänzend/fallback genutzt. Nutze DAS für 'Nachrichten', 'News', 'was ist heute passiert'. category='technologie' für Tech-News.",
        "parameters": {"type": "object", "properties": {
            "category": {"type": "string", "description": "Kategorie: 'top' (alle News) oder 'technologie' (Tech-News)", "default": "top"},
            "max_results": {"type": "integer", "description": "Anzahl News (default 10)", "default": 10}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "read_local_file",
        "description": "Lese eine lokale Datei. Pfad absolut oder relativ zum Skript-Verzeichnis.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "Dateipfad"}}, "required": ["path"]}
    }},
    {"type": "function", "function": {
        "name": "write_local_file",
        "description": "Schreibe eine lokale Datei. Pfad absolut oder relativ zu chat.py. Erstellt Ordner automatisch.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Dateipfad"},
            "content": {"type": "string", "description": "Inhalt"}
        }, "required": ["path", "content"]}
    }},
    {"type": "function", "function": {
        "name": "think",
        "description": "RUFE DIES ALS ERSTES AUF. Bei komplexen Aufgaben (3+ Schritte, Recherche, Vergleich, Analyse) erkennt think() das automatisch und erstellt einen Plan mit create_plan(). Gib deine Gedanken als Stichpunkte pro Zeile ein – daraus wird der Plan generiert.",
        "parameters": {"type": "object", "properties": {
            "thought": {"type": "string", "description": "Deine Überlegung – bei komplexen Aufgaben als Liste von Schritten pro Zeile formatieren (wird automatisch zu create_plan())"},
            "auto_plan": {"type": "boolean", "description": "True erzwingt create_plan(), auch bei einfachen Gedanken"}
        }, "required": ["thought"]}
    }},
    {"type": "function", "function": {
        "name": "vault_get",
        "description": "Lese einen gespeicherten Wert. OHNE KEY: liste alle verfügbaren Keys. Gruppierte Keys: vault_get('truenas/ip'). Nutze DAS BEVOR du den User fragst.",
        "parameters": {"type": "object", "properties": {"key": {"type": "string", "description": "z.B. 'truenas/ip' – leer lassen für alle Keys"}}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "vault_set",
        "description": "Speichere einen Wert. Nutze GROUP/KEY (z.B. 'truenas/ip').",
        "parameters": {"type": "object", "properties": {
            "key": {"type": "string", "description": "Gruppe/Schlüssel"},
            "value": {"type": "string", "description": "Wert"}
        }, "required": ["key", "value"]}
    }},
    {"type": "function", "function": {
        "name": "vault_delete",
        "description": "Lösche einen gespeicherten Wert.",
        "parameters": {"type": "object", "properties": {"key": {"type": "string", "description": "Schlüssel"}}, "required": ["key"]}
    }},
    {"type": "function", "function": {
        "name": "vault_list",
        "description": "Liste alle gespeicherten Werte (gruppiert).",
        "parameters": {"type": "object", "properties": {}}
    }},
    {"type": "function", "function": {
        "name": "http_request",
        "description": "Lade den Inhalt einer URL/Webseite oder rufe eine REST-API auf. Nutze DAS für Webseiten-Inhalte, API-Abfragen (Immich, TrueNAS, HA, Proxmox), etc. Wenn du nur den Inhalt einer Seite laden willst, reicht http_request(url='https://...') – method ist dann automatisch GET. Self-Signed-Certs akzeptiert. Bei Basic Auth: auth_user + auth_pass.",
        "parameters": {"type": "object", "properties": {
            "method": {"type": "string", "description": "GET (default), POST, PUT, DELETE, PATCH"},
            "url": {"type": "string", "description": "Vollständige URL"},
            "headers": {"type": "object", "description": "Zusätzliche Header als Dict"},
            "body": {"type": "string", "description": "Body (JSON-String für POST/PUT)"},
            "auth_user": {"type": "string", "description": "User für Basic Auth (optional, UTF-8-sicher)"},
            "auth_pass": {"type": "string", "description": "Passwort für Basic Auth (optional, UTF-8-sicher)"}
        }, "required": ["url"]}
    }},
    {"type": "function", "function": {
        "name": "image_search",
        "description": "Durchsuche das INTERNET nach BILDERN zu einem Thema (via DuckDuckGo). Liefert Thumbnails und Quell-Links als Markdown. Nutze DAS wenn der User explizit nach Bildern fragt oder visuelle Ergebnisse braucht.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Suchbegriff für die Bildersuche"},
            "max_results": {"type": "integer", "description": "Anzahl Bilder (default 6, max 12)", "default": 6}
        }, "required": ["query"]}
    }},
    {"type": "function", "function": {
        "name": "prompt_user",
        "description": "Frage den User interaktiv nach Eingabe (z.B. fehlende Passwörter, API-Keys). Die Antwort kommt direkt vom User. Nutze DAS, wenn vault_get keine Daten liefert – statt einfach zu sagen 'fehlt'.",
        "parameters": {"type": "object", "properties": {
            "message": {"type": "string", "description": "Die Frage an den User"},
            "secret": {"type": "boolean", "description": "Wenn true: Passwort-Masking (Sternchen)", "default": False}
        }, "required": ["message"]}
    }},
    {"type": "function", "function": {
        "name": "memory_get",
        "description": "Lese einen gespeicherten Fakt (z.B. 'user/name') oder alle Fakten (leer lassen). Memory ist dauerhaft und gilt über Chats hinweg.",
        "parameters": {"type": "object", "properties": {
            "key": {"type": "string", "description": "Schlüssel (z.B. 'user/name', 'network/ip_range'). Leer = alle."}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "memory_set",
        "description": "Speichere einen Fakt dauerhaft (über Chats hinweg). Z.B. 'user/name', 'network/ip_range', 'server/config'. Überschreibt vorherigen Wert.",
        "parameters": {"type": "object", "properties": {
            "key": {"type": "string", "description": "Schlüssel (z.B. 'user/name')"},
            "value": {"type": "string", "description": "Wert"}
        }, "required": ["key", "value"]}
    }},
    {"type": "function", "function": {
        "name": "memory_delete",
        "description": "Lösche einen gespeicherten Fakt aus dem dauerhaften Gedächtnis.",
        "parameters": {"type": "object", "properties": {
            "key": {"type": "string", "description": "Schlüssel"}
        }, "required": ["key"]}
    }},
    {"type": "function", "function": {
        "name": "delegate",
        "description": "ÜBERGEBE eine Teilaufgabe an einen spezialisierten Sub-Agenten. Nutze DAS bei komplexen, mehrstufigen Aufgaben: Recherche, Analyse, Code-Generierung, Parallel-Aufgaben. Der Sub-Agent arbeitet fokussiert und liefert Ergebnisse zurück. Du kannst mehrere delegate()-Aufrufe machen für verschiedene Aspekte einer Aufgabe.",
        "parameters": {"type": "object", "properties": {
            "task": {"type": "string", "description": "Die Aufgabe für den Sub-Agenten (detailliert)"},
            "context": {"type": "string", "description": "Zusätzlicher Kontext / Hintergrundinfos (optional)"},
            "model": {"type": "string", "description": "Model für Sub-Agent (default: Haupt-Model, optional)"}
        }, "required": ["task"]}
    }},
    {"type": "function", "function": {
        "name": "create_plan",
        "description": "Erstelle einen MEHR-SCHRITT-PLAN für komplexe Aufgaben. Definiere die Schritte in chronologischer Reihenfolge. Der Plan hilft dir, den Überblick zu behalten und systematisch vorzugehen. Nutze DAS BEVOR du mit mehrstufigen Aktionen beginnst.",
        "parameters": {"type": "object", "properties": {
            "steps": {"type": "string", "description": "Schritte, einer pro Zeile, in der Reihenfolge der Ausführung"},
            "description": {"type": "string", "description": "Kurze Beschreibung des Gesamtplans (optional)"}
        }, "required": ["steps"]}
    }},
    {"type": "function", "function": {
        "name": "agent_browser",
        "description": "Steuere den Browser via agent-browser CLI. Einfacher als die Playwright-browser_* Tools. Aktionen: goto (URL öffnen), click (Element klicken), type (Text eingeben), snapshot (Seitenstruktur lesen), screenshot (Screenshot), extract (Text aus Element), back (zurück), scroll (scrollen).",
        "parameters": {"type": "object", "properties": {
            "action": {"type": "string", "description": "Aktion: goto, click, type, snapshot, screenshot, extract, back, scroll"},
            "selector": {"type": "string", "description": "CSS-Selektor oder ref=... für click/type/extract"},
            "text": {"type": "string", "description": "Text für type-Aktion"},
            "url": {"type": "string", "description": "URL für goto-Aktion"}
        }, "required": ["action"]}
    }},
    {"type": "function", "function": {
        "name": "reason_deep",
        "description": "Führe TIEFGEHENDES Reasoning durch. Bei komplexen, mehrdeutigen Problemen: Tree-of-Thought (tot) erkundet mehrere Denkpfade parallel und wählt den besten. Bei sequenziellen/mathematischen Problemen: Schritt-für-Schritt (step) mit Verifikation jedes Schritts. Liefert strukturierte Analyse mit Bewertungen und Konfidenz.",
        "parameters": {"type": "object", "properties": {
            "problem": {"type": "string", "description": "Das Problem oder die Frage, die analysiert werden soll"},
            "method": {"type": "string", "description": "Methode: 'tot' (Tree-of-Thought, default) oder 'step' (Schritt-für-Schritt)", "default": "tot"},
            "branches": {"type": "integer", "description": "Anzahl Denkpfade bei tot-Methode (1-5, default 3)", "default": 3},
            "depth": {"type": "integer", "description": "Tiefe pro Pfad bei tot-Methode (1-5, default 3)", "default": 3},
            "steps": {"type": "string", "description": "Optional: eigene Schritte für step-Methode, einer pro Zeile"}
        }, "required": ["problem"]}
    }},
    {"type": "function", "function": {
        "name": "evaluate_reasoning",
        "description": "Bewerte einen Reasoning-Pfad nach Klarheit, Korrektheit, Vollständigkeit. Gibt Score (0-1), Stärken, Schwächen und Verbesserungsvorschläge. Nutze DAS um die Qualität deiner Analysen zu prüfen und zu verbessern.",
        "parameters": {"type": "object", "properties": {
            "problem": {"type": "string", "description": "Das ursprüngliche Problem"},
            "reasoning": {"type": "string", "description": "Der zu evaluierende Reasoning-Pfad"}
        }, "required": ["problem", "reasoning"]}
    }},
    {"type": "function", "function": {
        "name": "reflect_on_failure",
        "description": "Analysiere Fehlermuster bei Tool-Aufrufen. Zeigt welche Tools häufig fehlschlagen und gibt Strategie-Empfehlungen. Nutze DAS nach Fehlschlägen, um zu verstehen was schiefläuft.",
        "parameters": {"type": "object", "properties": {
            "tool_name": {"type": "string", "description": "Tool-Name (leer = alle Tools)"},
            "max_recent": {"type": "integer", "description": "Anzahl der letzten Aufrufe zur Analyse (default 5)", "default": 5}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "learn_skill",
        "description": "Lerne eine neue Fähigkeit (Skill) für zukünftige Aufgaben. Speichert ein erfolgreiches Pattern von Tool-Schritten, das später automatisch abgerufen werden kann. Nutze DAS wenn du ein nützliches Muster entdeckt hast.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "Eindeutiger Skill-Name, z.B. 'truenas_status_check'"},
            "description": {"type": "string", "description": "Beschreibung wofür der Skill gut ist und wann er eingesetzt werden sollte"},
            "steps": {"type": "string", "description": "JSON-Array der Tool-Schritte: [{'tool': 'name', 'args': {...}}, ...]"},
            "tags": {"type": "string", "description": "Komma-getrennte Tags für bessere Auffindbarkeit (optional)"},
            "context": {"type": "string", "description": "Kontext/Hintergrund für den Skill (optional)"}
        }, "required": ["name", "description", "steps"]}
    }},
    {"type": "function", "function": {
        "name": "recall_skills",
        "description": "Rufe relevante, zuvor gelernte Skills basierend auf dem aktuellen Kontext ab. Die Skills werden semantisch gematcht. Nutze DAS zu Beginn einer Aufgabe um von früheren Erfahrungen zu profitieren.",
        "parameters": {"type": "object", "properties": {
            "context": {"type": "string", "description": "Aktuelle Aufgabe oder Kontext zur Skill-Suche"},
            "max_results": {"type": "integer", "description": "Maximale Anzahl Skills (default 5)", "default": 5}
        }, "required": ["context"]}
    }},
    {"type": "function", "function": {
        "name": "list_skills",
        "description": "Liste alle gelernten Skills auf, optional gefiltert nach Tag.",
        "parameters": {"type": "object", "properties": {
            "tag": {"type": "string", "description": "Optional: Nur Skills mit diesem Tag anzeigen"}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "delete_skill",
        "description": "Lösche einen gelernten Skill.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "Name des zu löschenden Skills"}
        }, "required": ["name"]}
    }},
    {"type": "function", "function": {
        "name": "create_tool",
        "description": "Erstelle ein NEUES Tool/Plugin zur Laufzeit. Der Agent kann sich so selbst neue Fähigkeiten geben. Code wird auf Sicherheit geprüft und bei Erfolg sofort geladen. Nutze DAS wenn du eine wiederkehrende Aufgabe automatisieren willst oder ein spezialisiertes Tool brauchst.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "Eindeutiger Tool-Name (A-Z, a-z, 0-9, _, -)"},
            "description": {"type": "string", "description": "Beschreibung für das LLM wann/wie das Tool genutzt wird"},
            "parameters": {"type": "object", "description": "JSON-Schema der Parameter: {'param_name': {'type': 'string', 'description': '...'}}"},
            "code": {"type": "string", "description": "Python-Code (function-body). Parameter-Namen müssen mit 'parameters' übereinstimmen. Importe: requests, json, datetime, re, math, Path. KEIN input(), subprocess, os.system, eval, exec."}
        }, "required": ["name", "description", "parameters", "code"]}
    }},
    {"type": "function", "function": {
        "name": "delete_tool",
        "description": "Lösche ein zuvor erstelltes Tool/Plugin. Nur selbst-erstellte Tools können gelöscht werden, keine System-Plugins.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string", "description": "Name des zu löschenden Tools"}
        }, "required": ["name"]}
    }},
    {"type": "function", "function": {
        "name": "list_created_tools",
        "description": "Liste alle selbst-erstellten Tools auf. Zeigt nur dynamisch erstellte Tools, keine System-Plugins.",
        "parameters": {"type": "object", "properties": {}}
    }},
    {"type": "function", "function": {
        "name": "get_plan",
        "description": "Zeige den aktuellen Status eines Plans. Ruft Fortschritt, abgeschlossene/fehlgeschlagene Schritte und Ergebnisse ab.",
        "parameters": {"type": "object", "properties": {
            "plan_id": {"type": "string", "description": "Plan-ID (erhalten bei create_plan)"}
        }, "required": ["plan_id"]}
    }},
    {"type": "function", "function": {
        "name": "update_plan_step",
        "description": "Aktualisiere den Status eines Plan-Schritts. Setze auf 'done' bei Erfolg, 'failed' bei Fehler. Der Fortschritt wird automatisch berechnet.",
        "parameters": {"type": "object", "properties": {
            "plan_id": {"type": "string", "description": "Plan-ID"},
            "step_id": {"type": "integer", "description": "Schritt-Nummer (1-based)"},
            "status": {"type": "string", "description": "Neuer Status: 'done', 'failed', 'in_progress'"},
            "result": {"type": "string", "description": "Ergebnis/Begründung (optional)"}
        }, "required": ["plan_id", "step_id", "status"]}
    }},
    {"type": "function", "function": {
        "name": "list_plans",
        "description": "Liste alle aktiven und abgeschlossenen Pläne auf. Optional filterbar nach Status.",
        "parameters": {"type": "object", "properties": {
            "status": {"type": "string", "description": "Filter: 'active', 'completed', 'completed_with_errors' (optional)"}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "delete_plan",
        "description": "Lösche einen Plan und seinen Verlauf.",
        "parameters": {"type": "object", "properties": {
            "plan_id": {"type": "string", "description": "Plan-ID"}
        }, "required": ["plan_id"]}
    }},
    {"type": "function", "function": {
        "name": "analyze_performance",
        "description": "Analysiere die Performance aller Tools: Erfolgsrate, Anzahl Aufrufe, durchschnittliche/maximale Dauer. Zeigt eine sortierte Übersicht mit visuellen Balken. Nutze DAS um Engpässe zu identifizieren.",
        "parameters": {"type": "object", "properties": {
            "tool_name": {"type": "string", "description": "Optional: Nur dieses Tool analysieren"}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "get_improvement_suggestions",
        "description": "Analysiere Tool-Nutzung und gib konkrete Verbesserungsvorschläge basierend auf Erfolgsraten, Latenz und Nutzungsmustern.",
        "parameters": {"type": "object", "properties": {}}
    }},
    {"type": "function", "function": {
        "name": "get_daily_summary",
        "description": "Zeige eine Zusammenfassung der heutigen Tool-Aufrufe: Anzahl, Erfolgsrate, häufigste Tools, Durchschnittsdauer.",
        "parameters": {"type": "object", "properties": {}}
    }},
    {"type": "function", "function": {
        "name": "prune_history",
        "description": "Bereinige alte Reflexions-Daten. Entfernt Einträge älter als die angegebenen Tage. Hilft, die Datenbank schlank zu halten.",
        "parameters": {"type": "object", "properties": {
            "days": {"type": "integer", "description": "Maximales Alter in Tagen (default: 30)", "default": 30}
        }, "required": []}
    }},
]

CORE_MAP = {
    "execute_bash": _rate_limited("execute_bash")(execute_bash),
    "execute_python": _rate_limited("execute_python")(execute_python),
    "execute_ssh": _rate_limited("execute_ssh")(execute_ssh),
    "search_documents": _rate_limited("search_documents")(search_documents),
    "deep_research": _rate_limited("deep_research")(deep_research),
    "web_search": _rate_limited("web_search")(web_search),
    "fetch_news": _rate_limited("fetch_news")(fetch_news),
    "read_local_file": _rate_limited("read_local_file")(read_local_file),
    "write_local_file": _rate_limited("write_local_file")(write_local_file),
    "think": _rate_limited("think")(think),
    "prompt_user": _rate_limited("prompt_user")(prompt_user),
    "memory_get": _rate_limited("memory_get")(memory_get),
    "memory_set": _rate_limited("memory_set")(memory_set),
    "memory_delete": _rate_limited("memory_delete")(memory_delete),
    "vault_get": _rate_limited("vault_get")(vault_get),
    "vault_set": _rate_limited("vault_set")(vault_set),
    "vault_delete": _rate_limited("vault_delete")(vault_delete),
    "vault_list": _rate_limited("vault_list")(vault_list),
    "http_request": _rate_limited("http_request")(http_request),
    "image_search": _rate_limited("image_search")(image_search),
    "delegate": _rate_limited("delegate")(delegate),
    "create_plan": _rate_limited("create_plan")(create_plan),
    "agent_browser": _rate_limited("agent_browser")(agent_browser),
    "reason_deep": _rate_limited("reason_deep")(reason_deep),
    "evaluate_reasoning": _rate_limited("evaluate_reasoning")(evaluate_reasoning),
    "reflect_on_failure": _rate_limited("reflect_on_failure")(reflect_on_failure),
    "learn_skill": _rate_limited("learn_skill")(learn_skill),
    "recall_skills": _rate_limited("recall_skills")(recall_skills),
    "list_skills": _rate_limited("list_skills")(list_skills),
    "delete_skill": _rate_limited("delete_skill")(delete_skill),
    "create_tool": _rate_limited("create_tool")(create_tool),
    "delete_tool": _rate_limited("delete_tool")(delete_tool),
    "list_created_tools": _rate_limited("list_created_tools")(list_created_tools),
    "get_plan": _rate_limited("get_plan")(get_plan),
    "update_plan_step": _rate_limited("update_plan_step")(update_plan_step),
    "list_plans": _rate_limited("list_plans")(list_plans),
    "delete_plan": _rate_limited("delete_plan")(delete_plan),
    "analyze_performance": _rate_limited("analyze_performance")(analyze_performance),
    "get_improvement_suggestions": _rate_limited("get_improvement_suggestions")(get_improvement_suggestions),
    "get_daily_summary": _rate_limited("get_daily_summary")(get_daily_summary),
    "prune_history": _rate_limited("prune_history")(prune_history),
}
