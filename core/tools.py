import base64
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import requests

from .config import BASE, CHUNKS, EMBS, MEMORY_FILE, C
from .embed import embed
from .vault import _vault_get, vault_delete, vault_get, vault_list, vault_set

warnings.filterwarnings('ignore', category=DeprecationWarning)
try:
    from ddgs import DDGS
    _DDGS_AVAILABLE = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        _DDGS_AVAILABLE = True
    except ImportError:
        _DDGS_AVAILABLE = False

PERMISSION_MODE = "auto"

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
    global PERMISSION_MODE
    if PERMISSION_MODE == "ask":
        ok = _request_tool_confirmation("execute_bash", command)
        if ok is False:
            return "⛔ Abgebrochen (nicht bestätigt)"
    elif PERMISSION_MODE == "semi" and _is_critical(command):
        ok = _request_tool_confirmation("execute_bash", command)
        if ok is False:
            return "⛔ Abgebrochen (nicht bestätigt)"
    try:
        if 'cd ' in command and '&&' not in command and ';' not in command:
            return "⚠️ cd allein ist nicht persistent. Nutze '&&' zum Verketten, z.B. 'cd ordner && ls'"
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=60)
        out = r.stdout.strip()[:5000] if r.stdout.strip() else r.stderr.strip()[:2000]
        return out if out else "(leer)"
    except subprocess.TimeoutExpired:
        return "⏱ Timeout (60s)"
    except Exception as e:
        return f"❌ {e}"


def execute_ssh(host="", command="", user="", port=22, key="", password="", profile=""):
    global PERMISSION_MODE
    if PERMISSION_MODE == "ask":
        ok = _request_tool_confirmation("execute_ssh", command)
        if ok is False:
            return "⛔ Abgebrochen (nicht bestätigt)"
    elif PERMISSION_MODE == "semi" and _is_critical(command):
        ok = _request_tool_confirmation("execute_ssh", command)
        if ok is False:
            return "⛔ Abgebrochen (nicht bestätigt)"
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

        keyfile = None
        if key:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.key', delete=False) as f:
                f.write(key)
                keyfile = f.name
            os.chmod(keyfile, 0o600)
            ssh_cmd = (
                f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
                f"-i {keyfile} -p {port} {user}@{host} {shlex.quote(command)}"
            )
        elif password:
            ssh_cmd = (
                f"sshpass -p {shlex.quote(password)} ssh -o StrictHostKeyChecking=no "
                f"-o UserKnownHostsFile=/dev/null -p {port} {user}@{host} {shlex.quote(command)}"
            )
        else:
            ssh_cmd = (
                f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "
                f"-p {port} {user}@{host} {shlex.quote(command)}"
            )

        r = subprocess.run(ssh_cmd, shell=True, capture_output=True, text=True, timeout=60)
        if key and password and r.returncode != 0:
            first_err = (r.stderr or r.stdout or "").strip()
            password_cmd = (
                f"sshpass -p {shlex.quote(password)} ssh -o StrictHostKeyChecking=no "
                f"-o UserKnownHostsFile=/dev/null -p {port} {user}@{host} {shlex.quote(command)}"
            )
            r = subprocess.run(password_cmd, shell=True, capture_output=True, text=True, timeout=60)
            if not (r.stdout or r.stderr).strip() and first_err:
                r.stderr = first_err
        out = r.stdout.strip()[:5000] if r.stdout.strip() else r.stderr.strip()[:2000]
        if keyfile: os.unlink(keyfile)
        return out if out else "(leer)"
    except subprocess.TimeoutExpired:
        if 'keyfile' in locals() and keyfile: os.unlink(keyfile)
        return "⏱ Timeout (60s)"
    except FileNotFoundError:
        if 'keyfile' in locals() and keyfile: os.unlink(keyfile)
        return "❌ sshpass nicht installiert. `brew install sshpass` oder SSH-Key verwenden."
    except Exception as e:
        if 'keyfile' in locals() and keyfile: os.unlink(keyfile)
        return f"❌ {e}"


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
    except Exception as e:
        return f"❌ {e}"


def read_local_file(path):
    try:
        p = Path(path)
        if not p.is_absolute():
            p = BASE / p
        if not p.exists():
            return f"❌ Datei nicht gefunden: {p}"
        return p.read_text(encoding='utf-8', errors='replace')[:10000]
    except Exception as e:
        return f"❌ {e}"


def write_local_file(path, content):
    try:
        p = Path(path)
        if not p.is_absolute():
            p = BASE / p
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"✅ {p} geschrieben ({len(content)} Zeichen)"
    except Exception as e:
        return f"❌ {e}"


def execute_python(code):
    global PERMISSION_MODE
    if PERMISSION_MODE == "ask":
        ok = _request_tool_confirmation("execute_python", code[:120])
        if ok is False:
            return "⛔ Abgebrochen (nicht bestätigt)"
    elif PERMISSION_MODE == "semi" and _is_critical(code):
        ok = _request_tool_confirmation("execute_python", code[:120])
        if ok is False:
            return "⛔ Abgebrochen (nicht bestätigt)"
    try:
        c = compile(code, '<exec>', 'exec', flags=0x0)
        local_vars = {}
        from io import StringIO
        old_out = sys.stdout
        old_err = sys.stderr
        captured_out = StringIO()
        captured_err = StringIO()
        sys.stdout = captured_out
        sys.stderr = captured_err
        try:
            exec(c, {"__builtins__": __builtins__, "__name__": "__main__"}, local_vars)
        finally:
            sys.stdout = old_out
            sys.stderr = old_err
        out = captured_out.getvalue()
        err = captured_err.getvalue()
        result = ""
        if out:
            result += f"stdout:\n{out[:4000]}"
        if err:
            if result:
                result += "\n"
            result += f"stderr:\n{err[:2000]}"
        if not result:
            result = "(keine Ausgabe)"
        return result
    except Exception as e:
        return f"❌ Python-Fehler: {e}"


def think(thought):
    print(f"  {C.YELLOW}🧠 {thought[:500]}{C.RESET}", flush=True)
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


def http_request(method="GET", url="", headers={}, body="", auth_user="", auth_pass=""):
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
        try:
            r = requests.request(method.upper(), url, data=body or None, headers=h or None, timeout=60)
        except requests.exceptions.SSLError:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            r = requests.request(method.upper(), url, data=body or None, headers=h or None, timeout=60, verify=False)

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
    except Exception as e:
        return f"❌ {e}"


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
            root = ET.fromstring(r.content)
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
    try:
        m = json.loads(MEMORY_FILE.read_text()) if MEMORY_FILE.exists() else {}
        m[key] = value
        MEMORY_FILE.write_text(json.dumps(m, indent=2, ensure_ascii=False))
        return f"✅ `{key}` gespeichert"
    except Exception as e:
        return f"❌ {e}"

def memory_delete(key):
    try:
        m = json.loads(MEMORY_FILE.read_text()) if MEMORY_FILE.exists() else {}
        if key in m:
            del m[key]
            MEMORY_FILE.write_text(json.dumps(m, indent=2, ensure_ascii=False))
            return f"🗑 `{key}` gelöscht"
        return f"❌ `{key}` nicht gefunden"
    except Exception as e:
        return f"❌ {e}"

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
        "description": "RUFE DIES ALS ERSTES AUF. Plane: Welche Tools? Welche Reihenfolge? Welche Daten fehlen?",
        "parameters": {"type": "object", "properties": {"thought": {"type": "string", "description": "Deine Überlegung"}}, "required": ["thought"]}
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
}
