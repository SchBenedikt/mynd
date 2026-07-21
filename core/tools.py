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
from pathlib import Path

import numpy as np
import requests
from defusedxml import ElementTree

from .config import BASE, CHUNKS, EMBS, MEMORY_FILE, C
from .embed import embed
from .sandbox import SandboxUnavailableError, run_sandboxed
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
        if not validated or len(validated) > 10000:
            return "❌ Ungültiger Befehl"
        cmd_parts = shlex.split(validated)

        if key:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.key', delete=False) as f:
                f.write(key)
                keyfile = f.name
            os.chmod(keyfile, 0o600)
            ssh_cmd = ['ssh', '-i', keyfile, '-o', 'StrictHostKeyChecking=accept-new',
                       '-o', 'UserKnownHostsFile=/dev/null',
                       '-p', str(port), f'{user}@{host}'] + cmd_parts
        elif password:
            ssh_cmd = ['sshpass', '-e', 'ssh', '-o', 'StrictHostKeyChecking=accept-new',
                       '-o', 'UserKnownHostsFile=/dev/null',
                       '-p', str(port), f'{user}@{host}'] + cmd_parts
        else:
            ssh_cmd = ['ssh', '-o', 'StrictHostKeyChecking=accept-new',
                       '-o', 'UserKnownHostsFile=/dev/null',
                       '-p', str(port), f'{user}@{host}'] + cmd_parts

        ssh_env = {**os.environ, 'SSHPASS': password} if password else None
        r = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=60, env=ssh_env)
        if key and password and r.returncode != 0:
            first_err = (r.stderr or r.stdout or "").strip()
            password_cmd = ['sshpass', '-e', 'ssh', '-o', 'StrictHostKeyChecking=accept-new',
                            '-o', 'UserKnownHostsFile=/dev/null',
                            '-p', str(port), f'{user}@{host}'] + cmd_parts
            r = subprocess.run(password_cmd, capture_output=True, text=True, timeout=60, env=ssh_env)
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


def _workspace_path(path):
    root = Path(os.getenv('MYND_WORKSPACE_DIR', BASE / 'data' / 'workspace')).expanduser().resolve()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve(strict=False)
    if candidate != root and root not in candidate.parents:
        raise ValueError(f'Path is outside the allowed workspace: {root}')
    return candidate


def read_local_file(path):
    try:
        p = _workspace_path(path)
        if not p.exists():
            return f"❌ Datei nicht gefunden: {p}"
        return p.read_text(encoding='utf-8', errors='replace')[:10000]
    except Exception as e:
        return f"❌ {e}"


def write_local_file(path, content):
    try:
        p = _workspace_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"✅ {p} geschrieben ({len(content)} Zeichen)"
    except Exception as e:
        return f"❌ {e}"


def execute_python(code):
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
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, parsed.port or 443)}
    except socket.gaierror as exc:
        raise ValueError(f'Host resolution failed: {hostname}') from exc
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
        m = json.loads(MEMORY_FILE.read_text()) if MEMORY_FILE.exists() else {}
        if key:
            return m.get(key, "")
        return '\n'.join(f"{k}: {v}" for k, v in sorted(m.items())) if m else "(leer)"
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return "❌ Fehler"
def memory_set(key, value):
    with _memory_lock:
        try:
            m = json.loads(MEMORY_FILE.read_text()) if MEMORY_FILE.exists() else {}
            m[key] = value
            MEMORY_FILE.write_text(json.dumps(m, indent=2, ensure_ascii=False))
            return f"✅ `{key}` gespeichert"
        except Exception as e:
            return f"❌ {e}"


def memory_delete(key):
    with _memory_lock:
        try:
            m = json.loads(MEMORY_FILE.read_text()) if MEMORY_FILE.exists() else {}
            if key in m:
                del m[key]
                MEMORY_FILE.write_text(json.dumps(m, indent=2, ensure_ascii=False))
                return f"🗑 `{key}` gelöscht"
            return f"❌ `{key}` nicht gefunden"
        except Exception as e:
            return f"❌ {e}"


# ── Sub-Agent Delegation ───────────────────────────────────────

def delegate(task, context="", model=""):
    """Delegate a sub-task to a focused sub-agent. Use for complex multi-step
    research, parallel analysis, or when you need a dedicated agent to work
    on a sub-problem while you handle the main task."""
    try:
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
    Returns the plan as a checklist."""
    try:
        if isinstance(steps, str):
            steps = [s.strip() for s in steps.split("\n") if s.strip()]
        plan = {
            "description": description or "Mehrschritt-Plan",
            "total_steps": len(steps),
            "steps": [{"id": i + 1, "task": s, "status": "pending"} for i, s in enumerate(steps)],
            "created": __import__('datetime').datetime.now().isoformat(),
        }
        lines = [f"## 📋 Plan: {plan['description']}", ""]
        for s in plan["steps"]:
            lines.append(f"  [{s['id']}] ⬜ **{s['task'][:80]}**")
            if len(s['task']) > 80:
                lines[-1] = lines[-1][:-2] + "...**"
        lines.append(f"\n{plan['total_steps']} Schritte insgesamt.")
        return "\n".join(lines)
    except Exception:
        logger.exception("create_plan failed")
        return "❌ Plan-Erstellung fehlgeschlagen."


# ── agent-browser Integration ───────────────────────────────

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
]

CORE_MAP = {
    "execute_bash": execute_bash,
    "execute_python": execute_python,
    "execute_ssh": execute_ssh,
    "search_documents": search_documents,
    "web_search": web_search,
    "fetch_news": fetch_news,
    "read_local_file": read_local_file,
    "write_local_file": write_local_file,
    "think": think,
    "prompt_user": prompt_user,
    "memory_get": memory_get,
    "memory_set": memory_set,
    "memory_delete": memory_delete,
    "vault_get": vault_get,
    "vault_set": vault_set,
    "vault_delete": vault_delete,
    "vault_list": vault_list,
    "http_request": http_request,
    "image_search": image_search,
    "delegate": delegate,
    "create_plan": create_plan,
    "agent_browser": agent_browser,
}
