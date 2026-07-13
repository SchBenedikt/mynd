#!/usr/bin/env python3
"""mynd-2new – Flask backend combining mynd frontend with nextcloud-lightrag RAG core."""

import json
import locale
import logging
import os
import re
import secrets
import sys
import threading
import time
from datetime import UTC, date, datetime, timedelta
from functools import wraps
from html import unescape
from pathlib import Path
from urllib.parse import urljoin, urlparse

import numpy as np
import requests
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory, stream_with_context
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

import core.tools as _ct
import data.plugins.email as _email_module
import data.plugins.homeassistant as _ha_module
import data.plugins.immich as _immich_module
import data.plugins.nextcloud as _nc_module
from core.config import CHUNKS, EMBS, VAULT_FILE
from core.embed import embed as _embed_fn
from core.llm import chat_with_tools, chat_with_tools_stream
from core.model import check_tool_support
from core.plugin_base import get_all_tools, get_registry, load_plugins
from core.scheduler import CRON_HELP, TRIGGER_EXAMPLES, AutomationEngine
from core.tools import (
    CORE_MAP,
    CORE_TOOLS,
    execute_ssh,
    http_request,
    think,
    vault_delete,
    vault_set,
)
from core.utils import call_with_timeout
from core.vault import vault_get as _vg
from core.vault import vault_set as _vs

# Load .env
load_dotenv()

_app_lock = threading.Lock()

# ── Paths ────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
FRONTEND_DIR = BASE_DIR / 'frontend'
STATIC_EXPORT_DIR = FRONTEND_DIR / 'out'
AI_CONFIG_FILE = DATA_DIR / 'ai_config.json'

os.makedirs(DATA_DIR, exist_ok=True)
GENERATED_DIR = DATA_DIR / 'generated'
os.makedirs(GENERATED_DIR, exist_ok=True)
SETUP_DONE_FILE = DATA_DIR / 'setup_done.json'
AUTH_CONFIG_FILE = DATA_DIR / 'auth_config.json'

# ── Logging ──────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(BASE_DIR))

# Web-compatible prompt_user - instead of blocking on stdin, return structured response
_PROMPT_QUEUE = []
_WEB_PROMPT_PENDING = None
_AGENT_SESSION = None  # stores (msgs, stats, model, system_prompt, tools) for input resumption

def web_prompt_user(message, secret=False):
    global _WEB_PROMPT_PENDING
    with _app_lock:
        _WEB_PROMPT_PENDING = {'message': message, 'secret': secret}
    return "⏳ USER_INPUT_REQUIRED: " + message

# Patch prompt_user + tool confirmation in tools for web usage
_ct.prompt_user = web_prompt_user
_ct._CONFIRM_TOOL_PENDING = True

# --- Plugins (einheitlich) ---------------------------------
_plugins = load_plugins()
PLUGIN_TOOLS, PLUGIN_TOOL_MAP = get_all_tools()
AGENT_TOOLS = [*CORE_TOOLS, *PLUGIN_TOOLS]
WEB_TOOL_MAP = {**CORE_MAP, **PLUGIN_TOOL_MAP, 'prompt_user': web_prompt_user}

# Legacy plugin references (for PROMPT_EXTRA etc. in _build_agent_system_prompt)
email_plugin = _email_module
immich_plugin = _immich_module
homeassistant_plugin = _ha_module
nextcloud_plugin = _nc_module
ha_plugin = _ha_module

# Track pending tool for confirmation
_PENDING_TOOL_CONFIRM = None

# ── Automation Engine ───────────────────────────────────────
automation_engine = AutomationEngine(WEB_TOOL_MAP)

# ── App Initialization ───────────────────────────────────
app = Flask(__name__)

@app.after_request
def add_cors_headers(response):
    origin = request.headers.get('Origin', '')
    allowed_origins = {
        value.strip()
        for value in os.getenv(
            'CORS_ALLOWED_ORIGINS',
            'http://127.0.0.1:3000,http://localhost:3000',
        ).split(',')
        if value.strip()
    }
    if origin in allowed_origins:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Vary'] = 'Origin'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
    return response

@app.errorhandler(500)
def handle_500(e):
    logger.exception(f"500 Internal Server Error: {e}")
    return jsonify({"success": False, "error": "Interner Serverfehler – bitte Backend-Logs prüfen."}), 500

@app.errorhandler(Exception)
def handle_unhandled(e):
    if isinstance(e, HTTPException):
        logger.error('HTTP error: %s', e)
        return jsonify({"success": False, "error": "Request failed"}), e.code
    logger.exception(f"Unbehandelte Exception: {e}")
    return jsonify({"success": False, "error": "Request failed"}), 500

# ── Ollama Client (simplified wrapper) ──────────────────
class OllamaClient:
    def __init__(self, base_url=None, model=None):
        self.base_url = (base_url or os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434')).rstrip('/')
        self.model = model or os.getenv('OLLAMA_MODEL', 'gemma3:latest')

    def update_config(self, base_url, model):
        self.base_url = base_url.rstrip('/')
        self.model = model

    def chat(self, messages, context=None):
        q = ''
        for m in (messages or []):
            if m.get('role') == 'user':
                q = m.get('content', '')
                break

        system_prompt = "Du bist ein hilfreicher KI-Assistent. Antworte auf Deutsch."

        if context:
            ctx_text = '\n\n'.join([
                f"[{c.get('source', 'Quelle')}]\n{c.get('content', '')}" for c in context
            ])
            system_prompt = (
                "Du bist ein hilfreicher KI-Assistent mit Zugriff auf folgende Informationen.\n"
                "Antworte auf Deutsch basierend auf dem Kontext. Zitiere Quellen.\n\n"
                f"=== KONTEXT ===\n{ctx_text}"
            )

        msgs = [{"role": "system", "content": system_prompt}]
        for m in (messages or []):
            msgs.append(m)

        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": msgs,
            "stream": False,
            "options": {"temperature": 0.1, "max_tokens": 2048}
        }

        try:
            resp = requests.post(url, json=payload, timeout=120)
            if resp.status_code == 404:
                gen_url = f"{self.base_url}/api/generate"
                gen_payload = {
                    "model": self.model,
                    "prompt": q,
                    "stream": False
                }
                gr = requests.post(gen_url, json=gen_payload, timeout=120)
                gr.raise_for_status()
                gd = gr.json()
                return {"message": {"role": "assistant", "content": gd.get("response", "")}}
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"Ollama connection failed: {e}"}

    def check_connection(self):
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def list_models(self):
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=8)
            r.raise_for_status()
            return sorted(set(m['name'] for m in r.json().get('models', [])))
        except Exception:
            return []

ollama_client = OllamaClient()

def load_ai_config():
    cfg = {
        'provider': 'ollama',
        'base_url': os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/'),
        'model': os.getenv('OLLAMA_MODEL', 'gemma3:latest'),
        'api_key': ''
    }
    if AI_CONFIG_FILE.exists():
        try:
            fc = json.loads(AI_CONFIG_FILE.read_text())
            cfg['provider'] = str(fc.get('provider', cfg['provider']))
            cfg['base_url'] = str(fc.get('base_url', cfg['base_url'])).rstrip('/')
            cfg['model'] = str(fc.get('model', cfg['model']))
            stored_key = str(fc.get('api_key', ''))
            if stored_key and stored_key != '***':
                cfg['api_key'] = stored_key
            elif stored_key == '***':
                cfg['api_key'] = _vg('ai/api_key') or ''
        except Exception:
            pass
    if cfg['provider'] == 'ollama':
        ollama_client.update_config(cfg['base_url'], cfg['model'])
    return cfg

def save_ai_config(provider, base_url, model, api_key=''):
    cfg = {
        'provider': provider or 'ollama',
        'base_url': base_url.rstrip('/'),
        'model': model,
        'api_key': api_key or ''
    }
    if cfg.get('api_key'):
        vault_set('ai/api_key', cfg['api_key'])
    display_cfg = {**cfg}
    if display_cfg.get('api_key'):
        display_cfg['api_key'] = '***'
    AI_CONFIG_FILE.write_text(json.dumps(display_cfg, indent=2, ensure_ascii=False))
    if cfg['provider'] == 'ollama':
        ollama_client.update_config(cfg['base_url'], cfg['model'])

load_ai_config()

# ── Knowledge Base (using nextcloud-lightrag chunks/embeddings) ──
class KnowledgeBase:
    def __init__(self):
        self.chunks = []
        self.embs = np.array([]).reshape(0, 0)
        self._load()

    def _load(self):
        if CHUNKS.exists() and EMBS.exists():
            try:
                self.chunks = json.loads(CHUNKS.read_text())
                self.embs = np.load(EMBS)
                logger.info(f"Loaded {len(self.chunks)} chunks from index")
            except Exception as e:
                logger.warning(f"Could not load index: {e}")

    def search(self, query, k=10):
        if not self.chunks or self.embs.size == 0:
            return []
        try:
            qe = _embed_fn([query])[0]
            scores = np.array([
                float(np.dot(qe, e) / (np.linalg.norm(qe) * np.linalg.norm(e) + 1e-10))
                for e in self.embs
            ])
            top = np.argsort(scores)[-k:][::-1]
            results = []
            for i in top:
                if scores[i] > 0.15:
                    c = self.chunks[i]
                    results.append({
                        'content': c.get('text', ''),
                        'source': c.get('source', 'Unknown'),
                        'path': c.get('source', ''),
                        'similarity_score': float(scores[i]),
                        'search_type': 'semantic'
                    })
            return results
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

knowledge_base = KnowledgeBase()

_INTERMEDIATE_PATTERNS = [
    r'\blass mich\b',
    r'\bich (?:prüfe|schaue|sehe|rufe|frage|teste|versuche|werde|suche|starte|beginne)\b',
    r'\b(?:prüfe|schaue|rufe|frage|teste|versuche|suche|starte) (?:ich )?(?:jetzt|nun|mal)\b',
    r'\b(?:api|referenz|referenzen|apps?|kalender|nextcloud|truenas|immich).*\b(?:prüfen|abfragen|abrufen|testen|suchen|durchsuchen)\b',
]

def _looks_like_intermediate_response(text):
    cleaned = str(text or '').strip().lower()
    if not cleaned:
        return False
    if len(cleaned) > 500:
        return False
    return any(re.search(pattern, cleaned) for pattern in _INTERMEDIATE_PATTERNS)

def _assistant_message(content, tool_calls=None):
    msg = {"role": "assistant", "content": content or ""}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return msg

def _extract_numbered_sources(content):
    sources = []
    seen_urls = set()
    for line in str(content or "").splitlines():
        line_s = line.strip()
        m = re.match(r'^\((\d+)\)\s*\[([^\]]*)\]\(([^)]*)\)\s*$', line_s)
        if m:
            domain = (m.group(2) or '').strip()
            url = (m.group(3) or '').strip()
        else:
            m2 = re.match(r'^\s*[-*]\s*\[([^\]]*)\]\(([^)]*)\)', line_s)
            if m2:
                domain = (m2.group(1) or '').strip()
                url = (m2.group(2) or '').strip()
            else:
                m3 = re.match(r'^\s*(?:https?://\S+)', line_s)
                if m3:
                    url = m3.group(0).rstrip('.,;:!?)')
                    domain = urlparse(url).netloc
                else:
                    continue
        if url and url not in seen_urls:
            seen_urls.add(url)
            sources.append({"domain": domain or urlparse(url).netloc, "url": url})
    return sources

def _extract_meta_content(html_text, attr_name, attr_value):
    escaped_val = re.escape(attr_value)
    patterns = [
        rf'<meta[^>]*\s{attr_name}=["\']{escaped_val}["\'][^>]*\scontent=["\']([^"\']*)["\']',
        rf'<meta[^>]*\scontent=["\']([^"\']*)["\'][^>]*\s{attr_name}=["\']{escaped_val}["\']',
    ]
    for pattern in patterns:
        m = re.search(pattern, html_text, flags=re.IGNORECASE | re.DOTALL)
        if m and m.group(1):
            return unescape(m.group(1)).strip()
    return ""

def _extract_first_img(html_text, base_url):
    m = re.search(r'<img\s[^>]{0,500}\bsrc=["\'](https?://[^"\']+)["\']', html_text, re.IGNORECASE)
    if m:
        return m.group(1)
    return None

def _fetch_preview_image_for_url(source_url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        resp = requests.get(source_url, timeout=8, headers=headers, allow_redirects=True)
        if not resp.ok:
            return None
        html_text = resp.text[:250000]
        image_url = (
            _extract_meta_content(html_text, "property", "og:image")
            or _extract_meta_content(html_text, "name", "twitter:image")
            or _extract_meta_content(html_text, "property", "twitter:image")
        )
        if not image_url:
            image_url = _extract_first_img(html_text, resp.url or source_url)
        if not image_url:
            return None
        if not image_url.startswith('http'):
            image_url = urljoin(resp.url or source_url, image_url)
        parsed = urlparse(image_url)
        if parsed.scheme not in ("http", "https"):
            return None
        return image_url
    except Exception:
        return None

def _should_add_source_images(content, stats):
    if re.search(r'!\[[^\]]{0,200}]\([^)]+\)', str(content or '')):
        return False
    if re.search(r'https?://[^\s<>()\]]+', str(content or '')):
        return True
    tool_names = set()
    for round_item in stats or []:
        for tool in round_item.get("tools", []):
            name = str(tool.get("name", "")).strip()
            if name:
                tool_names.add(name)
    return ("web_search" in tool_names) or ("fetch_news" in tool_names)

def _append_source_images(content, stats):
    text = str(content or "")
    if not text or not _should_add_source_images(text, stats):
        return text
    sources = _extract_numbered_sources(text)
    if not sources:
        return text

    items = []
    seen_images = set()
    for src in sources:
        image_url = _fetch_preview_image_for_url(src["url"])
        if not image_url or image_url in seen_images:
            continue
        seen_images.add(image_url)
        items.append({
            "domain": src.get("domain") or urlparse(src["url"]).netloc,
            "source_url": src["url"],
            "image_url": image_url
        })

    if not items:
        return text

    inline_images = " ".join(
        f"[![{item['domain']}]({item['image_url']})]({item['source_url']})"
        for item in items
    )
    return text.rstrip() + "\n\n" + inline_images + "\n"

def _extract_urls_from_stats(stats, max_urls=8):
    urls = []
    seen = set()
    for round_item in stats or []:
        for tool in round_item.get("tools", []):
            text = str(tool.get("result", "") or "")
            for m in re.finditer(r'https?://[^\s<>()\]]+', text):
                raw_url = m.group(0).rstrip('.,;:!?)]}\'"')
                if raw_url in seen:
                    continue
                seen.add(raw_url)
                urls.append(raw_url)
                if len(urls) >= max_urls:
                    return urls
    return urls

def _ensure_numbered_sources(content, stats, max_sources=6):
    text = str(content or "").rstrip()
    if not text:
        return text
    if _extract_numbered_sources(text):
        return text
    urls = _extract_urls_from_stats(stats, max_urls=max_sources)
    if not urls:
        return text
    source_lines = []
    for idx, url in enumerate(urls, start=1):
        try:
            domain = urlparse(url).netloc or "Quelle"
        except Exception:
            domain = "Quelle"
        source_lines.append(f"({idx}) [{domain}]({url})")
    return text + "\n\n" + "\n".join(source_lines) + "\n"

def _detect_generated_files(age_seconds=5):
    files = []
    cutoff = time.time() - age_seconds
    if GENERATED_DIR.exists():
        for f in sorted(GENERATED_DIR.iterdir()):
            if f.is_file() and f.stat().st_mtime >= cutoff:
                ext = f.suffix.lower()
                mime = {
                    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                    '.html': 'text/html',
                    '.htm': 'text/html',
                    '.pdf': 'application/pdf',
                    '.png': 'image/png',
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.gif': 'image/gif',
                    '.svg': 'image/svg+xml',
                    '.csv': 'text/csv',
                    '.json': 'application/json',
                    '.txt': 'text/plain',
                    '.md': 'text/markdown',
                    '.py': 'text/x-python',
                    '.js': 'application/javascript',
                    '.css': 'text/css',
                }.get(ext, 'application/octet-stream')
                files.append({
                    "name": f.name,
                    "path": f"api/generated/{f.name}",
                    "url": f"/api/generated/{f.name}",
                    "size": f.stat().st_size,
                    "type": mime,
                    "ext": ext,
                })
    return files

def _strip_tool_code_blocks(text):
    """Remove <tool_code>, <tool>, [TOOL_CALL], and <tool_call> blocks from AI responses."""
    if not text:
        return text
    cleaned = str(text)
    cleaned = _re.sub(r'<tool_code>.*?</tool_code>', '', cleaned)
    cleaned = _re.sub(r'<tool[ >][^<]*</tool>', '', cleaned)
    cleaned = _re.sub(r'<tool\s+[^>]*/>', '', cleaned)
    cleaned = _re.sub(r'\[TOOL_CALL\].*?\[/TOOL_CALL\]', '', cleaned)
    cleaned = _re.sub(r'<tool_call>[^<]*</tool_call>', '', cleaned)
    return cleaned.strip()

def _parse_tool_code_fallback(text):
    """Parse <tool_code>, [TOOL_CALL], or <tool_call> blocks as fallback tool calls.
    Handles multiple formats:
      - <tool name="xxx" key="val"/> (self-closing)
      - <tool name="xxx"><param name="key">val</param></tool> (nested)
      - tool_name\n<param name="key">val</param>
      - tool_name --key "val"
    Returns list of {name, args} dicts or empty list.
    """
    if not text:
        return []
    import re as _re
    # Extract <tool_code>... blocks
    blocks = _re.findall(
        r'(?:<tool_code>|\[TOOL_CALL\]|<tool_call>)(.*?)(?:</tool_code>|\[/TOOL_CALL\]|</tool_call>)',
        str(text), flags=_re.DOTALL
    )
    if not blocks:
        # Also try standalone <tool> blocks
        blocks = _re.findall(r'<tool\s+name\s*=\s*["\']([^"\']+)["\']\s*(.*?)(?:/>|</tool>)', str(text), flags=_re.DOTALL)
        result = []
        for name, rest in blocks:
            args = _parse_xml_attrs(rest)
            if name not in ('tool',):
                result.append({"name": name.strip(), "args": args})
        return result

    result = []
    for block in blocks:
        block = block.strip()
        # Try self-closing <tool name="xxx" key="val"/> inside block
        self_closing = _re.findall(r'<tool\s+name\s*=\s*["\']([^"\']+)["\']\s*(.*?)/>', block, flags=_re.DOTALL)
        if self_closing:
            for name, rest in self_closing:
                args = _parse_xml_attrs(rest)
                result.append({"name": name.strip(), "args": args})
            if result:
                continue
        # Try nested <tool name="xxx">...<param name="key">val</param></tool>
        single_tools = _re.findall(r'<tool\s+name\s*=\s*["\']([^"\']+)["\']>(.*?)</tool>', block, flags=_re.DOTALL)
        for name, body in (single_tools or [(None, block)]):
            if name is None:
                # Try: tool => 'xxx' or tool => "xxx"
                m = _re.search(r"tool\s*=>\s*['\"]([^'\"]+)['\"]", block)
                if m:
                    name = m.group(1)
            if name is None:
                # Try: first word = tool name (format: "tool_name\n<param ...>")
                lines = block.strip().split('\n')
                first_line = lines[0].strip()
                if lines and first_line and not first_line.startswith('<'):
                    words = first_line.split()
                    name = words[0]
                    rest_of_first = ' '.join(words[1:])
                    remaining_lines = '\n'.join(lines[1:])
                    if remaining_lines.strip():
                        body = remaining_lines
                    elif rest_of_first:
                        body = rest_of_first
                    else:
                        body = ''
            if not name:
                continue
            args = {}
            # Parse <param name="X">Y</param>
            for pm in _re.finditer(r'<param\s+name\s*=\s*["\']([^"\']+)["\']\s*>(.*?)</param>', body, _re.DOTALL):
                args[pm.group(1).strip()] = pm.group(2).strip()
            # Parse XML attrs from body
            if not args:
                args = _parse_xml_attrs(body)
            # Parse --key "value" or key: value
            if not args:
                for pm in _re.finditer(r'--(\w+)\s+["\']([^"\']+)["\']', body):
                    args[pm.group(1).strip()] = pm.group(2).strip()
                for pm in _re.finditer(r'(\w+)\s*:\s*["\']?([^"\'\n]+)["\']?', body):
                    k, v = pm.group(1).strip(), pm.group(2).strip()
                    if k != 'tool' and k not in args:
                        args[k] = v
            if name and args:
                result.append({"name": name, "args": args})
    return result


def _parse_xml_attrs(text):
    """Parse XML attribute key="value" pairs from a string."""
    import re as _re
    args = {}
    for pm in _re.finditer(r'(\w+)\s*=\s*["\']([^"\']+)["\']', text):
        k, v = pm.group(1).strip(), pm.group(2).strip()
        if k != 'name':
            args[k] = v
    return args


def _get_tool_names_for_prompt():
    """Build compact tool listing for no-tool models."""
    lines = []
    lines.append("  - think(thought): Überlege und plane")
    lines.append("  - vault_get(key): Zugangsdaten lesen (z.B. vault_get(key='truenas/.../ip'))")
    lines.append("  - vault_set(key, value): Zugangsdaten speichern")
    lines.append("  - http_request(url, method, body, headers, auth_user, auth_pass): HTTP-Request mit Basic Auth")
    lines.append("  - execute_ssh(host, user, password, command): SSH-Befehl ausführen")
    lines.append("  - execute_python(code): Python-Code ausführen")
    lines.append("  - web_search(query, max_results): Internet-Suche")
    lines.append("  - fetch_news(category): Aktuelle Nachrichten")
    lines.append("  - search_documents(query): Lokale Dokumente")
    lines.append("  - read_local_file(path) / write_local_file(path, content): Dateien")
    lines.append("  - memory_get(key) / memory_set(key, value): Gedächtnis")
    lines.append("  - prompt_user(message): User fragen")
    from core.plugin_base import get_all_tools
    all_tools, _ = get_all_tools()
    for t in all_tools:
        fn = t.get('function', {})
        name = fn.get('name', '')
        desc = fn.get('description', '')
        params = fn.get('parameters', {}).get('properties', {})
        if name and name not in ('think', 'vault_get', 'vault_set', 'http_request',
            'execute_ssh', 'execute_python', 'web_search', 'fetch_news',
            'search_documents', 'read_local_file', 'write_local_file',
            'memory_get', 'memory_set', 'prompt_user') and not name.startswith('_'):
            param_names = list(params.keys())
            lines.append(f"  - {name}({', '.join(param_names)}): {desc[:200]}")
    return '\n'.join(lines)


def _get_loaded_plugins():
    """Return list of loaded plugin modules for PROMPT_EXTRA."""
    registry = get_registry()
    reg = registry() if callable(registry) else registry
    return [
        p for p in reg.values()
        if p is not None and hasattr(p, 'PROMPT_EXTRA')
    ]

def _get_vault_keys_for_prompt():
    """List available vault keys for no-tool models."""
    vault_file = DATA_DIR / 'vault.json'
    if not vault_file.exists():
        return ""
    try:
        v = json.loads(vault_file.read_text())
        if not v:
            return ""
        groups = {}
        for k in v:
            prefix = k.split('/')[0] if '/' in k else k
            groups.setdefault(prefix, []).append(k)
        lines = ["Verfügbare Vault-Keys (per vault_get abrufbar):"]
        for g, keys in sorted(groups.items()):
            lines.append(f"  {g}: {', '.join(sorted(keys))}")
        return '\n'.join(lines) + "\n\n"
    except Exception:
        return ""

def _decorate_response_with_media(content, stats):
    content = _strip_tool_code_blocks(content)
    with_sources = _ensure_numbered_sources(content, stats)
    result = _append_source_images(with_sources, stats)
    files = _detect_generated_files()
    # Normalize Immich URLs: model sometimes uses the raw Immich host instead of proxy
    result = re.sub(
        r'https?://[^/\s]+(/api/immich/(?:thumbnail|original)/[^\s")\]]+)',
        r'\1',
        result
    )
    # Auto-append Immich thumbnails if missing
    if "/api/immich/thumbnail/" not in result:
        thumbs = set()
        for rd in stats or []:
            for t in rd.get("tools", []):
                res = str(t.get("result", ""))
                for line in res.splitlines():
                    if "/api/immich/thumbnail/" in line and "![]" in line:
                        thumbs.add(line.strip())
        if thumbs:
            result += "\n\n## 🖼️ Gefundene Bilder\n" + "\n".join(list(thumbs)[:5])
    if files:
        return result, files
    return result, []

# ── Web Agent Loop (tool-calling without stdin) ──────────
def web_agent_loop(model, user_msg, system_prompt, max_rounds=8, tools=None, initial_msgs=None):
    global _WEB_PROMPT_PENDING, _AGENT_SESSION
    with _app_lock:
        _WEB_PROMPT_PENDING = None
    if tools is None:
        tools = AGENT_TOOLS
    if initial_msgs is not None:
        msgs = list(initial_msgs)
    else:
        msgs = [{"role": "system", "content": system_prompt}]
        msgs.append({"role": "user", "content": user_msg})
    consecutive_think = 0
    bypass_executed = False
    intermediate_continuations = 0
    stats = []

    try:
        for rnd in range(max_rounds):
            rnd_start = time.time()
            resp = chat_with_tools(model, msgs, tools)
            if "error" in resp:
                return f"Fehler: {resp['error']}", msgs, None, stats
            msg = resp.get("message", {})

            with _app_lock:
                if _WEB_PROMPT_PENDING:
                    pending = _WEB_PROMPT_PENDING
                    _WEB_PROMPT_PENDING = None
                else:
                    pending = None
            if pending:
                return None, msgs, pending, stats

            if not msg.get("tool_calls"):
                raw_text = msg.get("content", "")
                fallback_calls = _parse_tool_code_fallback(raw_text)
                if fallback_calls:
                    text = _strip_tool_code_blocks(raw_text)
                    msgs.append(_assistant_message(text, [{
                        "id": f"fallback_{i}",
                        "function": {"name": tc["name"], "arguments": tc["args"]}
                    } for i, tc in enumerate(fallback_calls)]))
                    continue
                text = _strip_tool_code_blocks(raw_text)
                if _looks_like_intermediate_response(text) and intermediate_continuations < 3:
                    intermediate_continuations += 1
                    msgs.append(_assistant_message(text))
                    msgs.append({
                        "role": "user",
                        "content": (
                            "Das war nur eine Zwischenmeldung. Fahre jetzt ohne weitere Ankündigung fort: "
                            "nutze die passenden Tools, prüfe die Daten wirklich und antworte erst mit dem Ergebnis."
                        )
                    })
                    continue
                msgs.append(_assistant_message(text))
                final_text, files = _decorate_response_with_media(text, stats)
                return final_text, msgs, None, stats

            content = msg.get("content", "")
            content = _strip_tool_code_blocks(content)
            msgs.append(_assistant_message(content, msg.get("tool_calls")))

            tc_list = msg.get("tool_calls", [])
            round_tools = []

            for tc in tc_list:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                args_raw = fn.get("arguments", {})
                if isinstance(args_raw, str):
                    try:
                        args = json.loads(args_raw)
                    except Exception:
                        args = {}
                else:
                    args = args_raw

                tool_start = time.time()
                success = True
                if name == "think":
                    consecutive_think += 1
                    if consecutive_think >= 2:
                        result = "⚠️ KEIN weiteres think()! Führe execute_ssh oder http_request aus!"
                        bypass_executed = True
                        success = False
                    else:
                        result = think(thought=args.get('thought', ''))
                else:
                    consecutive_think = 0
                    func = WEB_TOOL_MAP.get(name)
                    if func:
                        try:
                            result = func(**args)
                            if isinstance(result, str) and result.startswith("⏳ USER_INPUT_REQUIRED"):
                                with _app_lock:
                                    _WEB_PROMPT_PENDING = {'message': args.get('message', result), 'secret': args.get('secret', False)}
                                    _AGENT_SESSION = {
                                        'msgs': msgs, 'stats': stats, 'model': model,
                                        'tools': tools, 'max_rounds': max_rounds,
                                        'prompt': args.get('message', result),
                                        'secret': args.get('secret', False),
                                    }
                                msgs.append({"role": "tool", "content": "⏳ Warte auf Antwort...", "name": "prompt_user"})
                                return None, msgs, _WEB_PROMPT_PENDING, stats
                            if isinstance(result, str) and result.startswith("⏳ TOOL_CONFIRM_REQUIRED"):
                                with _app_lock:
                                    _WEB_PROMPT_PENDING = {'message': result.replace("⏳ TOOL_CONFIRM_REQUIRED: Bist du sicher, dass du ", "").rstrip("?") + "?"}
                                return None, msgs, _WEB_PROMPT_PENDING, stats
                        except Exception as e:
                            result = f"❌ Fehler: {e}"
                            success = False
                    else:
                        result = f"❌ Unbekanntes Tool: {name}"
                        success = False
                tool_duration = int((time.time() - tool_start) * 1000)
                safe_args = {k: ('***' if any(secret in k.lower() for secret in ['password', 'pass', 'secret', 'api', 'token']) else v) for k, v in args.items()}

                round_tools.append({
                    "name": name,
                    "args": safe_args,
                    "duration_ms": tool_duration,
                    "result_size": len(str(result)),
                    "success": success,
                    "result": str(result)[:1000]
                })

                msgs.append({
                    "role": "tool",
                    "content": str(result)[:8000],
                    "name": name,
                    "tool_call_id": tc.get("id", "")
                })

            stats.append({
                "round": rnd + 1,
                "tool_count": len(tc_list),
                "duration_ms": int((time.time() - rnd_start) * 1000),
                "tools": round_tools
            })

            if bypass_executed:
                break

        # ── Bypass: Model stuck thinking, execute tools directly ──
        logger.info("Model stuck in think loop – executing SSH/API directly")
        vault_data = json.loads(VAULT_FILE.read_text()) if VAULT_FILE.exists() else {}
        ip = None
        for k, v in vault_data.items():
            if k.endswith('/ip'):
                ip = v
                break
        if not ip:
            ip_match = re.search(r'(192\.168\.\d{1,3}\.\d{1,3})', user_msg)
            if ip_match:
                ip = ip_match.group(1)

        if ip:
            user_val = vault_data.get(f"truenas/{ip}/user", "root")
            pwd_val = vault_data.get(f"truenas/{ip}/password", "")
            rows = []
            ssh_result = ""
            try:
                ssh_result = execute_ssh(host=ip, command="cat /etc/version 2>/dev/null || cat /etc/os-release 2>/dev/null || uname -a", user=user_val, password=pwd_val)
                rows.append(f"SSH: {ssh_result[:1000]}")
            except Exception as e:
                rows.append(f"SSH Fehler: {e}")
                ssh_result = str(e)
            if "Permission denied" in ssh_result or "sshpass" in ssh_result.lower() or "timeout" in ssh_result.lower():
                try:
                    token_resp = http_request(method='POST', url=f'http://{ip}/api/v2.0/auth/generate_token', headers={"Content-Type": "application/json"}, body=json.dumps({"username": user_val, "password": pwd_val}))  # noqa: E501
                    if "200" in token_resp:
                        rows.append(f"TrueNAS API erreichbar.\n{token_resp[:500]}")
                    else:
                        rows.append(f"TrueNAS API fehlgeschlagen:\n{token_resp[:500]}")
                except Exception as e:
                    rows.append(f"HTTP Fehler: {e}")
            text = f"## Ergebnis der Überprüfung von {ip}\n\n" + "\n\n".join(rows)
            msgs.append({"role": "assistant", "content": text})
            final_text, files = _decorate_response_with_media(text, stats)
            return final_text, msgs, None, stats

        msgs.append({"role": "user", "content": "Du hast das Limit erreicht. Fasse zusammen."})
        resp = chat_with_tools(model, msgs, [])
        if "message" in resp:
            content = "⚠️ Max Runden erreicht.\n\n" + resp["message"].get("content", "")
            msgs.append({"role": "assistant", "content": content})
            final_text, files = _decorate_response_with_media(content, stats)
            return final_text, msgs, None, stats
        return "⚠️ Max Runden erreicht.", msgs, None, stats
    except Exception as e:
        logger.exception(f"Unbehandelter Fehler in web_agent_loop: {e}")
        return f"❌ Interner Fehler: {e}", msgs, None, stats

# ── Streaming Agent Loop (SSE events) ────────────────────
def web_agent_loop_stream(model, user_msg, system_prompt, max_rounds=8, tools=None):
    global _WEB_PROMPT_PENDING, _PENDING_TOOL_CONFIRM, _AGENT_SESSION
    with _app_lock:
        _WEB_PROMPT_PENDING = None
    if tools is None:
        tools = AGENT_TOOLS
    msgs = [{"role": "system", "content": system_prompt}]
    msgs.append({"role": "user", "content": user_msg})
    consecutive_think = 0
    bypass_executed = False
    intermediate_continuations = 0
    stats = []

    try:
        for rnd in range(max_rounds):
            rnd_start = time.time()
            accumulated = ""
            accumulated_thinking = ""
            final_msg = None
            for evt_type, token, result in chat_with_tools_stream(model, msgs, tools):
                if evt_type == "content" and token:
                    token = _strip_tool_code_blocks(token)
                    accumulated += token
                    yield {"type": "content", "content": token}
                elif evt_type == "think" and token:
                    accumulated_thinking += token
                    yield {"type": "think", "content": token}
                if result is not None:
                    final_msg = result
            if final_msg is None:
                text = accumulated.strip()
                if text:
                    final_text, files = _decorate_response_with_media(text, stats)
                    yield {"type": "final", "response": final_text, "research_stats": stats, "files": files}
                else:
                    yield {"type": "error", "error": "Keine Antwort vom Modell"}
                return
            if "error" in final_msg:
                if accumulated.strip():
                    final_msg = {"role": "assistant", "content": accumulated.strip()}
                else:
                    yield {"type": "error", "error": final_msg["error"]}
                    return

            with _app_lock:
                if _WEB_PROMPT_PENDING:
                    pending = _WEB_PROMPT_PENDING
                    _WEB_PROMPT_PENDING = None
                    _AGENT_SESSION = {
                        'msgs': msgs, 'stats': stats, 'model': model,
                        'tools': tools, 'max_rounds': max_rounds,
                        'prompt': pending['message'], 'secret': pending.get('secret', False),
                    }
                else:
                    pending = None
            if pending:
                yield {"type": "needs_input", "message": pending['message']}
                return

            if not final_msg.get("tool_calls"):
                raw_text = final_msg.get("content", "")
                # Fallback: parse <tool_code> blocks as tool calls
                fallback_calls = _parse_tool_code_fallback(raw_text)
                if fallback_calls:
                    yield {"type": "status", "message": f"⏵ {len(fallback_calls)} Tool(s) via <tool_code>-Fallback erkannt", "round": rnd + 1}
                    text = _strip_tool_code_blocks(raw_text)
                    msgs.append(_assistant_message(text, [{
                        "id": f"call_fallback_{i}", "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["args"]}
                    } for i, tc in enumerate(fallback_calls)]))
                    tc_list = [{
                        "id": f"call_fallback_{i}", "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["args"]}
                    } for i, tc in enumerate(fallback_calls)]
                    rnd_tools = []
                    for tc in tc_list:
                        fn = tc.get("function", {})
                        name = fn.get("name", "")
                        args_raw = fn.get("arguments", {})
                        if isinstance(args_raw, str):
                            try:
                                args = json.loads(args_raw)
                            except Exception:
                                args = {}
                        else:
                            args = args_raw
                        safe_args = {k: ('***' if any(secret in k.lower() for secret in ['password', 'pass', 'secret', 'api', 'token']) else v) for k, v in args.items()}
                        yield {"type": "tool_start", "round": rnd + 1, "tool": name, "args": safe_args}
                        tool_start = time.time()
                        success = True
                        func = WEB_TOOL_MAP.get(name)
                        if func:
                            try:
                                result = func(**args)
                                if isinstance(result, str) and result.startswith("⏳ USER_INPUT_REQUIRED"):
                                    with _app_lock:
                                        _AGENT_SESSION = {
                                            'msgs': msgs, 'stats': stats, 'model': model,
                                            'tools': tools, 'max_rounds': max_rounds,
                                            'prompt': args.get('message', result),
                                            'secret': args.get('secret', False),
                                        }
                                    msgs.append({"role": "tool", "content": "⏳ Warte auf Antwort...", "name": "prompt_user"})
                                    yield {"type": "needs_input", "message": args.get('message', result)}
                                    return
                                if isinstance(result, str) and result.startswith("⏳ TOOL_CONFIRM_REQUIRED"):
                                    with _app_lock:
                                        _PENDING_TOOL_CONFIRM = {'tool': name, 'args': args, 'model': model, 'prompt': user_msg, 'system_prompt': system_prompt, 'msgs': msgs}
                                    yield {"type": "confirm_tool", "tool": name, "description": result.replace("⏳ TOOL_CONFIRM_REQUIRED: ", "")}
                                    return
                            except Exception as e:
                                result = f"❌ Fehler: {e}"
                                success = False
                        else:
                            result = f"❌ Unbekanntes Tool: {name}"
                            success = False
                        tool_duration = int((time.time() - tool_start) * 1000)
                        yield {"type": "tool_end", "round": rnd + 1, "tool": name, "result_preview": str(result)[:500], "duration_ms": tool_duration, "success": success}
                        rnd_tools.append({"name": name, "args": safe_args, "duration_ms": tool_duration, "result_size": len(str(result)), "success": success, "result": str(result)[:1000]})
                        msgs.append({"role": "tool", "content": str(result)[:8000], "name": name})
                    stats.append({"round": rnd + 1, "tool_count": len(tc_list), "duration_ms": int((time.time() - rnd_start) * 1000), "tools": rnd_tools})
                    yield {"type": "round_end", "round": rnd + 1, "round_stats": stats[-1]}
                    continue
                text = _strip_tool_code_blocks(raw_text)
                if _looks_like_intermediate_response(text) and intermediate_continuations < 3:
                    intermediate_continuations += 1
                    msgs.append(_assistant_message(text))
                    yield {"type": "status", "message": text, "round": rnd + 1}
                    msgs.append({
                        "role": "user",
                        "content": (
                            "Das war nur eine Zwischenmeldung. Fahre jetzt ohne weitere Ankündigung fort: "
                            "nutze die passenden Tools, prüfe die Daten wirklich und antworte erst mit dem Ergebnis."
                        )
                    })
                    continue
                msgs.append(_assistant_message(text))
                final_text, files = _decorate_response_with_media(text, stats)
                yield {"type": "final", "response": final_text, "research_stats": stats, "files": files}
                return

            content = final_msg.get("content", "")
            content = _strip_tool_code_blocks(content)
            msgs.append(_assistant_message(content, final_msg.get("tool_calls")))

            tc_list = final_msg.get("tool_calls", [])
            round_tools = []

            for tc in tc_list:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                args_raw = fn.get("arguments", {})
                if isinstance(args_raw, str):
                    try:
                        args = json.loads(args_raw)
                    except Exception:
                        args = {}
                else:
                    args = args_raw

                safe_args = {k: ('***' if any(secret in k.lower() for secret in ['password', 'pass', 'secret', 'api', 'token']) else v) for k, v in args.items()}
                yield {"type": "tool_start", "round": rnd + 1, "tool": name, "args": safe_args}

                tool_start = time.time()
                success = True
                if name == "think":
                    consecutive_think += 1
                    if consecutive_think >= 2:
                        result = "⚠️ KEIN weiteres think()! Führe execute_ssh oder http_request aus!"
                        bypass_executed = True
                        success = False
                    else:
                        result = think(thought=args.get('thought', ''))
                else:
                    consecutive_think = 0
                    func = WEB_TOOL_MAP.get(name)
                    if func:
                        try:
                            result = func(**args)
                            if isinstance(result, str) and result.startswith("⏳ USER_INPUT_REQUIRED"):
                                yield {"type": "needs_input", "message": args.get('message', result)}
                                return
                            if isinstance(result, str) and result.startswith("⏳ TOOL_CONFIRM_REQUIRED"):
                                with _app_lock:
                                    _PENDING_TOOL_CONFIRM = {'tool': name, 'args': args, 'model': model, 'prompt': user_msg, 'system_prompt': system_prompt, 'msgs': msgs}
                                yield {"type": "confirm_tool", "tool": name, "description": result.replace("⏳ TOOL_CONFIRM_REQUIRED: ", "")}
                                return
                        except Exception as e:
                            result = f"❌ Fehler: {e}"
                            success = False
                    else:
                        result = f"❌ Unbekanntes Tool: {name}"
                        success = False
                tool_duration = int((time.time() - tool_start) * 1000)

                yield {"type": "tool_end", "round": rnd + 1, "tool": name, "result_preview": str(result)[:500], "duration_ms": tool_duration, "success": success}

                round_tools.append({
                    "name": name,
                    "args": safe_args,
                    "duration_ms": tool_duration,
                    "result_size": len(str(result)),
                    "success": success,
                    "result": str(result)[:1000]
                })

                msgs.append({
                    "role": "tool",
                    "content": str(result)[:8000],
                    "name": name,
                    "tool_call_id": tc.get("id", "")
                })

            stats.append({
                "round": rnd + 1,
                "tool_count": len(tc_list),
                "duration_ms": int((time.time() - rnd_start) * 1000),
                "tools": round_tools
            })
            yield {"type": "round_end", "round": rnd + 1, "round_stats": stats[-1]}

            if bypass_executed:
                break

        # ── Bypass & max rounds (same as web_agent_loop) ──
        logger.info("Model stuck in think loop – executing SSH/API directly")
        vault_data = json.loads(VAULT_FILE.read_text()) if VAULT_FILE.exists() else {}
        ip = None
        for k, v in vault_data.items():
            if k.endswith('/ip'):
                ip = v
                break
        if not ip:
            ip_match = re.search(r'(192\.168\.\d{1,3}\.\d{1,3})', user_msg)
            if ip_match:
                ip = ip_match.group(1)

        if ip:
            user_val = vault_data.get(f"truenas/{ip}/user", "root")
            pwd_val = vault_data.get(f"truenas/{ip}/password", "")
            rows = []
            ssh_result = ""
            yield {"type": "tool_start", "round": rnd + 1, "tool": "execute_ssh", "args": {"host": ip, "command": "System-Info"}}
            try:
                ssh_result = execute_ssh(host=ip, command="cat /etc/version 2>/dev/null || cat /etc/os-release 2>/dev/null || uname -a", user=user_val, password=pwd_val)
                rows.append(f"SSH: {ssh_result[:1000]}")
            except Exception as e:
                rows.append(f"SSH Fehler: {e}")
                ssh_result = str(e)
            yield {"type": "tool_end", "round": rnd + 1, "tool": "execute_ssh", "result_preview": ssh_result[:300], "duration_ms": 0, "success": "Permission denied" not in ssh_result}
            if "Permission denied" in ssh_result or "sshpass" in ssh_result.lower() or "timeout" in ssh_result.lower():
                yield {"type": "tool_start", "round": rnd + 1, "tool": "http_request", "args": {"method": "POST", "url": f"http://{ip}/api/v2.0/auth/generate_token"}}
                try:
                    token_resp = http_request(method='POST', url=f'http://{ip}/api/v2.0/auth/generate_token', headers={"Content-Type": "application/json"}, body=json.dumps({"username": user_val, "password": pwd_val}))  # noqa: E501
                    if "200" in token_resp:
                        rows.append(f"TrueNAS API erreichbar.\n{token_resp[:500]}")
                    else:
                        rows.append(f"TrueNAS API fehlgeschlagen:\n{token_resp[:500]}")
                except Exception as e:
                    rows.append(f"HTTP Fehler: {e}")
                yield {"type": "tool_end", "round": rnd + 1, "tool": "http_request", "result_preview": rows[-1][:300], "duration_ms": 0, "success": "200" in rows[-1]}
            text = f"## Ergebnis der Überprüfung von {ip}\n\n" + "\n\n".join(rows)
            msgs.append({"role": "assistant", "content": text})
            final_text, files = _decorate_response_with_media(text, stats)
            yield {"type": "final", "response": final_text, "research_stats": stats, "files": files}
            return

        msgs.append({"role": "user", "content": "Du hast das Limit erreicht. Fasse zusammen."})
        resp = chat_with_tools(model, msgs, [])
        if "message" in resp:
            content = "⚠️ Max Runden erreicht.\n\n" + resp["message"].get("content", "")
            msgs.append({"role": "assistant", "content": content})
            final_text, files = _decorate_response_with_media(content, stats)
            yield {"type": "final", "response": final_text, "research_stats": stats, "files": files}
            return
        yield {"type": "final", "response": "⚠️ Max Runden erreicht.", "research_stats": stats}
        return
    except Exception as e:
        logger.exception(f"Unbehandelter Fehler in web_agent_loop_stream: {e}")
        yield {"type": "error", "error": "Request failed"}

# ── Helper Functions ──────────────────────────────────────
def _fmt_endpoints(d, lines, indent="    "):
    for key, val in d.items():
        if isinstance(val, dict):
            lines.append(f"{indent}{key}/:")
            _fmt_endpoints(val, lines, indent + "  ")
        else:
            lines.append(f"{indent}{key}: {val}")

def safe_json(resp):
    try:
        return resp.json() if resp.text else {}
    except Exception:
        return {}

def now_iso():
    return datetime.now().isoformat()

# ── Auth (simplified) ────────────────────────────────────
AUTH_USERS = {}
AUTH_FILE = DATA_DIR / 'auth_users.json'
if AUTH_FILE.exists():
    try:
        AUTH_USERS.update(json.loads(AUTH_FILE.read_text()))
    except Exception:
        pass

if not AUTH_USERS:
    default_password = secrets.token_urlsafe(16)
    AUTH_USERS['admin'] = {
        'password_hash': generate_password_hash(default_password),
        'name': 'Admin',
        'role': 'admin',
    }
    AUTH_FILE.write_text(json.dumps(AUTH_USERS, indent=2))
    logger.warning('Created initial admin account with temporary password')


def _safe_error(message, exception=None, status=500):
    if exception:
        logger.error('%s: %s', message, exception)
    return jsonify({'success': False, 'error': message}), status

def _verify_password(user, password):
    password_hash = user.get('password_hash')
    if password_hash:
        return check_password_hash(password_hash, password)
    # Transparent migration for installations that predate password hashing.
    if secrets.compare_digest(str(user.get('password', '')), str(password)):
        user['password_hash'] = generate_password_hash(password)
        user.pop('password', None)
        AUTH_FILE.write_text(json.dumps(AUTH_USERS, indent=2))
        return True
    return False


def _set_password(user, password):
    user['password_hash'] = generate_password_hash(password)
    user.pop('password', None)

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            token = auth[7:]
            for u, data in AUTH_USERS.items():
                if data.get('token') == token:
                    request.current_user = u
                    return f(*args, **kwargs)
        return jsonify({'authenticated': False, 'error': 'Unauthorized'}), 401
    return decorated


def require_admin(f):
    @require_auth
    @wraps(f)
    def decorated(*args, **kwargs):
        username = request.current_user
        user = AUTH_USERS.get(username, {})
        if user.get('role') != 'admin' and username != 'admin':
            return jsonify({'success': False, 'error': 'Forbidden'}), 403
        return f(*args, **kwargs)
    return decorated


def _request_has_admin_token():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return False
    token = auth[7:]
    return any(
        secrets.compare_digest(str(user.get('token', '')), token)
        and (user.get('role') == 'admin' or username == 'admin')
        for username, user in AUTH_USERS.items()
    )

# ==========================================================
#  API ENDPOINTS
# ==========================================================

# ── Auth ──────────────────────────────────────────────────
@app.route('/api/auth/me', methods=['GET'])
def auth_me():
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        token = auth[7:]
        for u, data in AUTH_USERS.items():
            if data.get('token') == token:
                return jsonify({
                    'authenticated': True,
                    'user': {'name': data.get('name', u), 'username': u}
                })
    return jsonify({'authenticated': False})

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    data = request.json or {}
    username = data.get('username', '')
    password = data.get('password', '')
    if username in AUTH_USERS and _verify_password(AUTH_USERS[username], password):
        token = os.urandom(32).hex()
        AUTH_USERS[username]['token'] = token
        AUTH_FILE.write_text(json.dumps(AUTH_USERS, indent=2))
        return jsonify({
            'authenticated': True,
            'user': {'name': AUTH_USERS[username].get('name', username), 'username': username},
            'token': token
        })
    return jsonify({'authenticated': False, 'error': 'Invalid credentials'}), 401


@app.route('/api/auth/refresh', methods=['POST'])
@require_auth
def auth_refresh():
    username = request.current_user
    token = secrets.token_hex(32)
    AUTH_USERS[username]['token'] = token
    AUTH_FILE.write_text(json.dumps(AUTH_USERS, indent=2))
    return jsonify({'success': True, 'token': token})

@app.route('/api/auth/register', methods=['POST'])
def auth_register():
    data = request.json or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    name = data.get('name', '').strip() or username
    cfg = {'allowRegistration': False}
    if AUTH_CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(AUTH_CONFIG_FILE.read_text()))
        except Exception:
            pass
    if not cfg.get('allowRegistration'):
        return jsonify({'success': False, 'error': 'Registration is disabled'}), 403
    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password required'}), 400
    if len(username) < 2:
        return jsonify({'success': False, 'error': 'Username too short (min 2 characters)'}), 400
    if len(password) < 4:
        return jsonify({'success': False, 'error': 'Password too short (min 4 characters)'}), 400
    if username in AUTH_USERS:
        return jsonify({'success': False, 'error': 'User already exists'}), 409
    token = os.urandom(32).hex()
    AUTH_USERS[username] = {
        'password_hash': generate_password_hash(password),
        'name': name,
        'role': 'user',
        'token': token,
    }
    AUTH_FILE.write_text(json.dumps(AUTH_USERS, indent=2))
    return jsonify({
        'success': True, 'authenticated': True,
        'user': {'name': name, 'username': username}, 'token': token
    })

@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        token = auth[7:]
        for user in AUTH_USERS.values():
            if secrets.compare_digest(str(user.get('token', '')), token):
                user.pop('token', None)
                AUTH_FILE.write_text(json.dumps(AUTH_USERS, indent=2))
                break
    return jsonify({'success': True})

@app.route('/api/auth/factory-reset', methods=['POST'])
def auth_factory_reset():
    data = request.json or {}
    password = data.get('password', '')
    admin_user = AUTH_USERS.get('admin', {})
    if not _verify_password(admin_user, password):
        return jsonify({'success': False, 'error': 'Invalid password'}), 401
    admin_name = admin_user.get('name', 'Admin')
    AUTH_USERS.clear()
    AUTH_USERS['admin'] = {
        'password_hash': generate_password_hash(password),
        'name': admin_name,
        'role': 'admin',
    }
    AUTH_FILE.write_text(json.dumps(AUTH_USERS, indent=2))
    SETUP_DONE_FILE.unlink(missing_ok=True)
    return jsonify({'success': True})

@app.route('/api/auth/config', methods=['GET', 'POST'])
def auth_config():
    cfg = {'allowRegistration': False, 'requireLogin': True}
    if AUTH_CONFIG_FILE.exists():
        try:
            stored = json.loads(AUTH_CONFIG_FILE.read_text())
            cfg.update(stored)
        except Exception:
            pass
    if request.method == 'GET':
        return jsonify({'success': True, **cfg})
    if not _request_has_admin_token():
        return jsonify({'success': False, 'error': 'Forbidden'}), 403
    data = request.json or {}
    if 'allowRegistration' in data:
        cfg['allowRegistration'] = bool(data['allowRegistration'])
    if 'requireLogin' in data:
        cfg['requireLogin'] = bool(data['requireLogin'])
    try:
        AUTH_CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
        return jsonify({'success': True, **cfg})
    except Exception as e:
        return jsonify({'success': False, 'error': "Request failed"}), 500

@app.route('/api/auth/profile', methods=['GET', 'PUT'])
@require_auth
def auth_profile():
    username = request.current_user
    if request.method == 'GET':
        data = AUTH_USERS.get(username, {})
        return jsonify({
            'success': True,
            'user': {'username': username, 'name': data.get('name', username)}
        })
    data = request.json or {}
    name = data.get('name', '').strip()
    password = data.get('password', '').strip()
    if username in AUTH_USERS:
        if name:
            AUTH_USERS[username]['name'] = name
        if password:
            _set_password(AUTH_USERS[username], password)
        AUTH_FILE.write_text(json.dumps(AUTH_USERS, indent=2))
    return jsonify({'success': True, 'user': {'username': username, 'name': name or AUTH_USERS.get(username, {}).get('name', username)}})

@app.route('/api/admin/users', methods=['GET'])
@require_admin
def admin_users_list():
    return jsonify({
        'success': True,
        'users': [{'username': u, 'name': d.get('name', '')} for u, d in AUTH_USERS.items()]
    })

@app.route('/api/admin/users/create', methods=['POST'])
@require_admin
def admin_users_create():
    data = request.json or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    name = data.get('name', '').strip()
    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password required'}), 400
    if username in AUTH_USERS:
        return jsonify({'success': False, 'error': 'User already exists'}), 409
    AUTH_USERS[username] = {
        'password_hash': generate_password_hash(password),
        'name': name or username,
        'role': 'user',
    }
    AUTH_FILE.write_text(json.dumps(AUTH_USERS, indent=2))
    return jsonify({'success': True, 'user': {'username': username, 'name': name or username}})

@app.route('/api/admin/users/delete', methods=['POST'])
@require_admin
def admin_users_delete():
    data = request.json or {}
    username = data.get('username', '').strip()
    if not username or username not in AUTH_USERS:
        return jsonify({'success': False, 'error': 'User not found'}), 404
    if username == 'admin':
        return jsonify({'success': False, 'error': 'Cannot delete admin user'}), 400
    del AUTH_USERS[username]
    AUTH_FILE.write_text(json.dumps(AUTH_USERS, indent=2))
    return jsonify({'success': True})

@app.route('/api/admin/users/reset', methods=['POST'])
@require_admin
def admin_users_reset():
    data = request.json or {}
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    if not username or username not in AUTH_USERS:
        return jsonify({'success': False, 'error': 'User not found'}), 404
    if not password:
        return jsonify({'success': False, 'error': 'Password required'}), 400
    _set_password(AUTH_USERS[username], password)
    AUTH_FILE.write_text(json.dumps(AUTH_USERS, indent=2))
    return jsonify({'success': True})

def _reset_app_data():
    import shutil
    for f in DATA_DIR.iterdir():
        if f.name == '.gitkeep':
            continue
        if f.is_file():
            f.unlink()
        elif f.is_dir():
            shutil.rmtree(f)
    temporary_password = secrets.token_urlsafe(16)
    AUTH_USERS.clear()
    AUTH_USERS['admin'] = {
        'password_hash': generate_password_hash(temporary_password),
        'name': 'Admin',
        'role': 'admin',
    }
    AUTH_FILE.write_text(json.dumps(AUTH_USERS, indent=2))
    AI_CONFIG_FILE.write_text(json.dumps({
        'base_url': 'http://127.0.0.1:11434',
        'model': '',
        'embedding_model': ''
    }, indent=2))
    auth_cfg = DATA_DIR / 'auth_config.json'
    auth_cfg.write_text(json.dumps({'allowRegistration': False, 'requireLogin': True}, indent=2))
    return temporary_password

@app.route('/api/admin/reset', methods=['POST'])
@require_admin
def admin_reset():
    temporary_password = _reset_app_data()
    return jsonify({'success': True, 'temporary_password': temporary_password})

@app.route('/api/health', methods=['GET'])
def api_health():
    return jsonify({
        'ollama': 'unknown', 'kb': 'unknown', 'embeddings': 'unknown'
    })

@app.route('/')
def root_status():
    if STATIC_EXPORT_DIR.is_dir():
        return send_from_directory(STATIC_EXPORT_DIR, 'index.html')
    return '<!DOCTYPE html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>mynd Backend</title><style>body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#0f0f1a;color:#e2e8f0}div{text-align:center}h1{font-size:2.5rem;margin:0 0 0.5rem}.ok{color:#22c55e}.info{color:#94a3b8;font-size:0.9rem}</style></head><body><div><h1 class="ok">✓ api ok</h1><p class="info">mynd Backend – Port 5001</p></div></body></html>'

@app.route('/<path:path>')
def frontend_static(path):
    if path == 'api' or path.startswith('api/'):
        return jsonify({'success': False, 'error': 'Not found'}), 404
    if not STATIC_EXPORT_DIR.is_dir():
        return jsonify({'error': 'not found'}), 404
    safe_path = os.path.normpath('/' + path).lstrip('/')
    file_path = os.path.realpath(os.path.join(STATIC_EXPORT_DIR, safe_path))
    if not file_path.startswith(os.path.realpath(STATIC_EXPORT_DIR)):
        return jsonify({'error': 'not found'}), 404
    if os.path.isfile(file_path):
        return send_from_directory(STATIC_EXPORT_DIR, safe_path)
    index = os.path.join(file_path, 'index.html')
    if os.path.isfile(index):
        return send_from_directory(file_path, 'index.html')
    return send_from_directory(STATIC_EXPORT_DIR, 'index.html')

@app.route('/api/setup/status', methods=['GET'])
def setup_status():
    needs_setup = not SETUP_DONE_FILE.exists()
    oauth_cfg = DATA_DIR / 'nextcloud_oauth.json'
    oauth_configured = oauth_cfg.exists()
    nc_url = _vg('nextcloud/url') or os.getenv('NEXTCLOUD_URL', '')
    return jsonify({
        'success': True,
        'needs_setup': needs_setup,
        'oauth_configured': oauth_configured,
        'nextcloud_url': nc_url
    })

@app.route('/api/setup/bootstrap', methods=['POST'])
def setup_bootstrap():
    if SETUP_DONE_FILE.exists() and not _request_has_admin_token():
        return jsonify({'success': False, 'error': 'Forbidden'}), 403
    data = request.json or {}
    mode = data.get('mode', '')
    if mode == 'admin':
        name = data.get('admin_name', 'Admin').strip()
        pw = data.get('admin_password', '').strip()
        if not pw:
            return jsonify({'success': False, 'error': 'Password required'}), 400
        AUTH_USERS.clear()
        AUTH_USERS['admin'] = {
            'password_hash': generate_password_hash(pw),
            'name': name,
            'role': 'admin',
        }
        AUTH_FILE.write_text(json.dumps(AUTH_USERS, indent=2))
        return jsonify({'success': True, 'mode': 'admin'})
    elif mode == 'ai':
        cfg = {
            'base_url': data.get('base_url', 'http://127.0.0.1:11434'),
            'model': data.get('model', ''),
            'embedding_model': data.get('embedding_model', '')
        }
        AI_CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
        return jsonify({'success': True, 'mode': 'ai'})
    elif mode == 'system':
        if data.get('enable_ollama'):
            cfg = {
                'base_url': data.get('base_url', 'http://127.0.0.1:11434'),
                'model': data.get('model', ''),
                'embedding_model': data.get('embedding_model', 'nomic-embed-text')
            }
            AI_CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
        if data.get('enable_immich'):
            url = data.get('immich_url_default', '').strip()
            key = data.get('immich_api_key_default', '').strip()
            if url:
                _vs('immich/url', url)
            if key:
                _vs('immich/api-key', key)
        SETUP_DONE_FILE.write_text(json.dumps({'done': True, 'mode': 'system'}))
        return jsonify({'success': True, 'mode': 'system'})
    elif mode == 'nextcloud':
        nc_url = data.get('nextcloud_url', '').strip()
        cid = data.get('client_id', '').strip()
        secret = data.get('client_secret', '').strip()
        vault_set('nextcloud/url', nc_url)
        vault_set('nextcloud/client_id', cid)
        vault_set('nextcloud/client_secret', secret)
        (DATA_DIR / 'nextcloud_oauth.json').write_text(json.dumps({'configured': True}))
        return jsonify({'success': True, 'mode': 'nextcloud'})
    elif mode == 'auth_config':
        cfg = {'allowRegistration': False, 'requireLogin': True}
        if AUTH_CONFIG_FILE.exists():
            try:
                stored = json.loads(AUTH_CONFIG_FILE.read_text())
                cfg.update(stored)
            except Exception:
                pass
        if 'allowRegistration' in data:
            cfg['allowRegistration'] = bool(data['allowRegistration'])
        if 'requireLogin' in data:
            cfg['requireLogin'] = bool(data['requireLogin'])
        AUTH_CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
        return jsonify({'success': True, 'mode': 'auth_config'})
    return jsonify({'success': False, 'error': 'Unknown mode'}), 400

# ── Chat with tool-calling ────────────────────────────────
def _build_agent_system_prompt(message):
    now = datetime.now()
    date_str = now.strftime("%A, %d. %B %Y")
    time_str = now.strftime("%H:%M")
    try:
        locale.setlocale(locale.LC_TIME, 'de_DE.UTF-8')
        date_str = now.strftime("%A, %d. %B %Y")
    except Exception:
        pass

    memory_block = ""
    mem_file = DATA_DIR / 'memory.json'
    if mem_file.exists():
        try:
            mem = json.loads(mem_file.read_text())
            if mem:
                items = [f"  {k}: {v}" for k, v in sorted(mem.items())]
                memory_block = "## Gespeichertes Wissen (Memory)\n" + '\n'.join(items) + "\n\n"
        except Exception:
            pass

    vault_block = ""
    vault_file = DATA_DIR / 'vault.json'
    if vault_file.exists():
        try:
            v = json.loads(vault_file.read_text())
            if v:
                groups = {}
                for k in v:
                    prefix = k.split('/')[0] if '/' in k else k
                    groups.setdefault(prefix, []).append(k)
                lines = ["## Verfügbare Vault-Keys"]
                for g, keys in sorted(groups.items()):
                    lines.append(f"  {g}: {', '.join(sorted(keys))}")
                vault_block = '\n'.join(lines) + "\n\n"
        except Exception:
            pass

    refs_block = ""
    refs_file = DATA_DIR / 'api_refs.json'
    if refs_file.exists():
        try:
            refs = json.loads(refs_file.read_text())
            lines = ["## API-Referenzen (api_refs.json)"]
            for service, cfg in sorted(refs.items()):
                base = cfg.get('base', '')
                endpoints = cfg.get('endpoints', {})
                auth = cfg.get('authentication', cfg.get('auth', ''))
                lines.append(f"\n### {service}")
                if base:
                    lines.append(f"  Base: {base}")
                if auth:
                    if isinstance(auth, dict):
                        atype = auth.get('type', '')
                        if isinstance(atype, list):
                            atype = ', '.join(atype)
                        lines.append(f"  Auth: {atype}")
                    else:
                        lines.append(f"  Auth: {auth}")
                lines.append("  Endpoints:")
                _fmt_endpoints(endpoints, lines, "    ")
            refs_block = '\n'.join(lines) + "\n\n"
        except Exception:
            pass

    email_extra = getattr(email_plugin, 'PROMPT_EXTRA', '') if email_plugin else ''
    immich_extra = getattr(immich_plugin, 'PROMPT_EXTRA', '') if immich_plugin else ''
    ha_extra = getattr(ha_plugin, 'PROMPT_EXTRA', '') if ha_plugin else ''

    system = (
        f"Heute ist {date_str}, {time_str} Uhr.\n\n"
        "Du bist ein KI-Assistent mit Zugriff auf Nextcloud-Dokumente, E-Mails, Fotos und Server-Tools.\n\n"
        "KERN-WERKZEUGE:\n"
        "- **think**: IMMER ZUERST aufrufen. Plane dein Vorgehen.\n"
        "- **search_documents**: Indexierte Dokumente semantisch durchsuchen\n"
        "- **web_search**: INTERNET-Suche via DuckDuckGo für aktuelle Infos, News, Webseiten\n"
        "- **fetch_news**: AKTUELLE NACHRICHTEN per WEB-MULTI-QUELLEN. RSS nur ergänzend/fallback (category='top' oder 'technologie')\n"
        "- **vault_get / vault_set / vault_list / vault_delete**: Zugangsdaten speichern/lesen\n"
        "- **execute_python**: Python-Code ausführen für Berechnungen, Datum/Uhrzeit, Daten-Analyse, URL-Inhalte laden, Datei-Erstellung (Excel/openpyxl, Word/docx, PowerPoint/pptx), Formatierungen, Mathe, etc. Nutze DAS STATT execute_bash für alles außer System-Befehle.\n"  # noqa: E501
        "- **http_request**: HTTP-Request an JEDE REST-API (auch URL-Inhalte laden!). auth_user + auth_pass für Basic Auth (UTF-8-sicher). Self-Signed-Certs automatisch akzeptiert.\n"
        "- **execute_ssh**: Befehl per SSH auf Remote-Host (host, user, password, command)\n"
        "- **read_local_file / write_local_file**: Lokale Dateien lesen/schreiben\n"
        "- **prompt_user**: User interaktiv nach Eingabe fragen – wenn du unsicher bist, mehrere Möglichkeiten siehst, eine Auswahl brauchst oder zusätzliche Infos benötigst. ÜBERLEGE NICHT LANGE, sondern frage einfach.\n"  # noqa: E501
        "- **memory_get / memory_set / memory_delete**: Dauerhaftes Gedächtnis über Chats hinweg\n\n"
        "NEXTCLOUD:\n"
        "- **nextcloud_list / nextcloud_read_file / nextcloud_write_file / nextcloud_delete / nextcloud_mkdir / nextcloud_move**: Dateien verwalten\n"
        "- **nextcloud_caldav_query(start_date=YYYYMMDD, end_date=YYYYMMDD)**: Kalender-Termine abrufen\n"
        "- **nextcloud_caldav_create**: Termin erstellen\n"
        "- **nextcloud_tasks_query**: Offene Aufgaben abrufen\n"
        "- **nextcloud_tasks_create**: Aufgabe erstellen\n"
        "- **nextcloud_contact_search(query)**: Kontakte suchen nach Name/E-Mail/Telefon – z.B. 'Vinzenz Schächner'\n"
        "- **nextcloud_contact_get(uid)**: Einzelnen Kontakt per UID abrufen\n\n"
        f"{email_extra}"
        f"{immich_extra}"
        f"{ha_extra}"
        "⚠️ WICHTIG: Wenn der User dir eine persönliche Information nennt (Name, Wohnort, Geburtstag, Vorlieben etc.), "
        "rufe SOFORT memory_set() auf – nicht nur sagen dass du es merkst. Das Tool MUSS ausgeführt werden.\n\n"
        "WICHTIGE REGELN:\n"
        "- Credentials IMMER per vault_get() mit vollem Key abrufen (z.B. vault_get('truenas/192.168.178.44/user')). NIEMALS aus Nachrichten kopieren.\n"
        "- KEINE <tool_code> Blöcke generieren! Nutze ausschließlich die standardisierten function_call/tool_calls der API.\n"
        "- **prompt_user() NUTZEN bei Unsicherheit**: Wenn du dir nicht sicher bist, der User eine Wahl treffen muss, oder du mehrere Möglichkeiten siehst – rufe SOFORT prompt_user() auf. Rate NICHT einfach irgendwas. Beispiele:\n"  # noqa: E501
        "  * 'Welche Farbe?' → prompt_user('Soll ich Blau oder Rot nehmen?')\n"
        "  * 'Ich habe XYZ zur Auswahl' → prompt_user('Welche Option bevorzugst du?')\n"
        "  * 'Ich kenne den Standort nicht' → prompt_user('In welcher Stadt bist du?')\n"
        "- Unsicher oder mehrere Optionen? → prompt_user().\n"
        "- vault_get liefert nichts? → prompt_user().\n"
        "- http_request schlägt fehl? → anderen Endpoint probieren oder execute_bash mit Python/requests (verify=False).\n"
        "- Remote-Befehle? → execute_ssh (Credentials aus Vault).\n"
        "- API-Endpunkte unbekannt? → read_local_file('data/api_refs.json').\n"
        "- Nach 3 Fehlschlägen: komplett andere Strategie.\n\n"
        "BEISPIEL: 'TrueNAS-Update?' → vault_get('truenas/.../ip'), vault_get('truenas/.../user'), vault_get('truenas/.../password') "
        "→ http_request mit auth_user + auth_pass → Ergebnis präsentieren.\n\n"
        f"{vault_block}"
        f"{refs_block}"
        "ENTSCHEIDUNGS-BAUM:\n"
        "1. **DENKE** → think()\n"
        "2. **WISSEN QUELLE WÄHLEN**:\n"
        "   - Aktuelle Tages-Nachrichten/News → **fetch_news()** (Web-Multi-Quellen, RSS nur ergänzend)\n"
        "   - Allgemeine Internet-Recherche (Hintergrund, Fakten, aktuelle Infos, Webseiten) → **web_search()**\n"
        "   - URL vom User gegeben → **http_request(url)** oder **execute_python(requests.get(url))** zum Laden der Seite\n"
        "   - Lokale Nextcloud-Dokumente → **search_documents()**\n"
        "   - Kombiniere bei Bedarf: z.B. web_search() für Kontext + fetch_news() für heutige News\n"
         "3. **AKTION** → Vault → prompt_user (bei Unsicherheit/Fragen) → vault_set → http_request / execute_ssh / execute_python. API unbekannt? → api_refs.json.\n"
        "4. **MERKEN (MUSS)** → User sagt etwas Persönliches (Name, Alter, Wohnort etc.)? → DU MUSST memory_set() AUFRUFEN. Sage nicht nur 'ich merke es mir' – führe das Tool aus!\n"
        "5. **ANTWORTEN**: Deutsch.\n"
        "   - **QUELLE IMMER NENNEN** – bei JEDER Antwort die Quellen angeben.\n"
        "   - **Quellen-Format**: Verwende KURZE ZITIER-MARKIERUNGEN im Text wie (1), (2), (3) ... "
        "und führe die Quellen am Ende aufgelistet auf:\n"
        "     (1) [tagesschau.de](https://www.tagesschau.de/...)\n"
        "     (2) [heise.de](https://www.heise.de/...)\n"
        "   - Zeige NUR den Domain-Namen als Link an, NICHT die volle URL.\n"
        "   - NUMERIERUNG MUSS SEQUENTIELL SEIN: 1, 2, 3, 4, 5, ... – "
        "niemals Zahlen aus den Rohdaten übernehmen!\n"
        "   - **LISTEN WICHTIG**: Format `• **Titel**: Beschreibung (1)` – ZAHL und TEXT in EINER Zeile. "
        "NIEMALS Zahl und Text auf zwei Zeilen verteilen. KEINE Leerzeilen zwischen Listeneinträgen.\n"
        "   - Bei Nachrichten: Kompakte Aufzählung ohne leere Zeilen zwischen den Einträgen.\n"
        "   - VERBOTEN: `---` Trennlinien, `##` Doppel-Überschriften, übermäßige Leerzeilen.\n"
        "   - Gute Beispiele:\n"
        "     • **EU-Umfrage**: 75% bewerten EU als sicheren Hafen (1)\n"
        "     • **Korruptions-Razzia** wegen EM-Tickets 2024 (2)\n"
        "     • **Nächster Punkt**: Text (3)\n\n"
        "     (1) [tagesschau.de](https://www.tagesschau.de/...)\n"
        "     (2) [tagesschau.de](https://www.tagesschau.de/...)\n\n"
        f"DATUM: {datetime.now().strftime('%d.%m.%Y')}.\n\n"
        f"{memory_block}"
    )
    return system

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json or {}
    message = data.get('message', '')
    if not message:
        return jsonify({'error': 'No message'}), 400

    _store_credentials_from_message(message)
    system_prompt = _build_agent_system_prompt(message)
    cfg = load_ai_config()
    model_has_tools = check_tool_support(ollama_client.model, cfg.get('base_url'))
    # Safety-Net: auch anhand des Namens erkennen
    no_tool_keywords = ['gemma', 'phi', 'tinyllama']
    if any(k in ollama_client.model.lower() for k in no_tool_keywords):
        model_has_tools = False
    no_tool_context = ""

    if not model_has_tools:
        from core.tools import web_search
        wc_res, wc_err = call_with_timeout(web_search, (message,), {"max_results": 10}, timeout=8)
        if wc_res and not wc_err:
            no_tool_context = (
                "\n\n📋 VORAB-RECHERCHE (automatisch, da dein Modell keine Tools aufrufen kann):\n"
                f"{wc_res}\n\n"
                "Beantworte die Frage anhand dieser Informationen. "
                "Zitiere Quellen mit (1), (2) etc. und liste sie am Ende auf.\n"
            )
        try:
            from core.tools import fetch_news
            nc, _ = call_with_timeout(fetch_news, (), {"max_results": 5}, timeout=8)
            if nc and not str(nc).startswith("⚠"):
                no_tool_context += f"\n\n📰 AKTUELLE NACHRICHTEN:\n{nc}\n"
        except Exception:
            pass
        system_prompt += no_tool_context

    content, history, needs_input, research_stats = web_agent_loop(
        ollama_client.model, message, system_prompt, max_rounds=20,
        tools=[] if not model_has_tools else None
    )

    if needs_input:
        return jsonify({
            'response': f"⚠️ Ich benötige weitere Informationen:\n\n{needs_input['message']}",
            'requires_input': True,
            'prompt_message': needs_input['message']
        })

    if content is None:
        content = "⚠️ Die Anfrage konnte nicht verarbeitet werden."

    return jsonify({'response': content, 'research_stats': research_stats})

@app.route('/api/agent/query/stream', methods=['POST'])
def agent_query_stream():
    data = request.json or {}
    prompt = data.get('prompt', '')
    preferred_source = data.get('preferred_source', 'auto')
    requested_model = data.get('model', '')
    if not prompt:
        return jsonify({'success': False, 'error': 'No prompt'}), 400

    _store_credentials_from_message(prompt)
    base_prompt = _build_agent_system_prompt(prompt)
    source_hint = ""

    def _get_web_context_safe(query, max_results):
        """Fetch web context with timeout and error handling."""
        try:
            from core.tools import web_search
            result, error = call_with_timeout(web_search, (query,), {"max_results": max_results}, timeout=8)
            if error:
                if isinstance(error, TimeoutError):
                    return "⚠️ Web-Suche hat zu lange gedauert (Timeout nach 8s)."
                return f"⚠️ Web-Suche Fehler: {str(error)[:200]}"
            if not result:
                return "Keine Ergebnisse gefunden."
            return result
        except Exception as e:
            return "⚠️ Web-Suche nicht verfügbar"
    if preferred_source == 'web':
        web_context = _get_web_context_safe(prompt, 10)
        source_hint = (
            "\n\n⚠️ AKTUELLE EINSTELLUNG: Internet-Suche aktiviert.\n"
            "VORAB-ERGEBNISSE (web_search):\n"
            f"{web_context}\n\n"
            "Du kannst jederzeit eigene web_search()- oder fetch_news()-Aufrufe tätigen "
            "falls die VORAB-ERGEBNISSE nicht ausreichen.\n"
        )
    elif preferred_source == 'deep':
        web_context = _get_web_context_safe(prompt, 15)
        source_hint = (
            "\n\n⚠️ DEEP RESEARCH MODUS aktiviert.\n"
            "VORAB-ERGEBNISSE (web_search):\n"
            f"{web_context}\n\n"
            "**DEEP RESEARCH REGELN**:\n"
            "1. Führe MEHRERE Suchdurchläufe durch – nicht nur einen.\n"
            "2. Prüfe Informationen GEGEN eine zweite Quelle, bevor du sie als Fakt ausgibst.\n"
            "3. WENN eine Quelle unsicher oder unvollständig ist, suche gezielt weiter.\n"
            "4. Gib an, wenn eine Information nicht verifiziert werden kann.\n"
            "5. Nutze web_search() mit verschiedenen Suchbegriffen für vollständige Abdeckung.\n"
            "6. Strukturiere die Antwort ausführlicher als normal – mit Kontext und Einordnung.\n"
            "7. Gib bei Quellen an: Datum, Domain und ggf. Titel der Seite.\n"
        )
    elif preferred_source == 'local':
        source_hint = (
            "\n\n⚠️ AKTUELLE EINSTELLUNG: Der User hat 'Nur lokale Dokumente' aktiviert. "
            "Nutze AUSSCHLIESSLICH search_documents(). KEINE web_search() – "
            "auch nicht bei aktuellen Themen.\n\n"
        )
    system_prompt = base_prompt + source_hint
    active_model = requested_model or ollama_client.model

    # Check tool support – gemma4 etc. können keine Tools aufrufen (mit Cache)
    if not hasattr(agent_query_stream, '_tool_cache'):
        agent_query_stream._tool_cache = {}
    cfg = load_ai_config()
    cache_key = f"{active_model}:{cfg.get('base_url','')}"
    if cache_key not in agent_query_stream._tool_cache:
        agent_query_stream._tool_cache[cache_key] = check_tool_support(active_model, cfg.get('base_url'))
    model_has_tools = agent_query_stream._tool_cache[cache_key]
    # Safety-Net: auch anhand des Namens erkennen (falls check_tool_support falsch positiv)
    no_tool_keywords = ['gemma', 'phi', 'tinyllama']
    if any(k in active_model.lower() for k in no_tool_keywords):
        model_has_tools = False

    if not model_has_tools:
        now_str = datetime.now().strftime("%A, %d. %B %Y, %H:%M")
        try:
            locale.setlocale(locale.LC_TIME, 'de_DE.UTF-8')
            now_str = datetime.now().strftime("%A, %d. %B %Y, %H:%M")
        except Exception:
            pass
        tool_list = _get_tool_names_for_prompt()
        vault_block = _get_vault_keys_for_prompt()
        system_prompt = (
            f"Heute ist {now_str}.\n\n"
            "Du bist ein KI-Assistent. Du kannst Tools über das folgende XML-Format aufrufen:\n\n"
            "<tool_code><tool name=\"TOOL_NAME\" arg1=\"wert1\" arg2=\"wert2\"/></tool_code>\n\n"
            "Verfügbare Tools:\n"
            f"{tool_list}\n\n"
            f"{vault_block}"
            "REGELN:\n"
            "- IMMER zuerst think() aufrufen.\n"
            "- Credentials per vault_get(key) abrufen.\n"
            "- Mehrere Tools in EINEM <tool_code>-Block möglich.\n"
            "- Warte auf das Ergebnis, bevor du den nächsten Schritt machst.\n"
            "- Antworte auf Deutsch.\n"
            "- Quellen mit (1), (2) etc. zitieren.\n"
            f"\n{''.join(getattr(p, 'PROMPT_EXTRA', '') for p in (_get_loaded_plugins()) if hasattr(p, 'PROMPT_EXTRA'))}"
        )

    def generate():
        yield f"data: {json.dumps({'type': 'status', 'message': '⏳ Starte...'}, ensure_ascii=False)}\n\n"
        agent_tools = [] if not model_has_tools else None
        for event in web_agent_loop_stream(active_model, prompt, system_prompt, max_rounds=100, tools=agent_tools):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )

def _get_web_context_safe_v2(query, max_results):
    """Fetch web context with timeout and error handling for non-streaming."""
    try:
        from core.tools import web_search
        result, error = call_with_timeout(web_search, (query,), {"max_results": max_results}, timeout=8)
        if error:
            if isinstance(error, TimeoutError):
                return "⚠️ Web-Suche hat zu lange gedauert (Timeout nach 8s)."
            return "⚠️ Web-Suche Fehler"
        if not result:
            return "Keine Ergebnisse gefunden."
        return result
    except Exception as e:
        return "⚠️ Web-Suche nicht verfügbar"

@app.route('/api/generated/<path:filename>')
def serve_generated(filename):
    return send_from_directory(GENERATED_DIR, filename)

UPLOAD_DIR = DATA_DIR / 'uploads'
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    f = request.files['file']
    if f.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    try:
        safe_name = re.sub(r'[^\w\.\-]', '_', f.filename)
        dest = os.path.realpath(os.path.join(UPLOAD_DIR, safe_name))
        if not dest.startswith(os.path.realpath(UPLOAD_DIR)):
            return jsonify({'success': False, 'error': 'Invalid path'}), 400
        Path(dest).write_bytes(f.read())
        size = os.path.getsize(dest)
        return jsonify({
            'success': True,
            'filename': safe_name,
            'size': size,
            'url': f'/api/uploads/{safe_name}'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': 'Upload failed'}), 500

@app.route('/api/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)

@app.route('/api/agent/query', methods=['POST'])
def agent_query():
    data = request.json or {}
    prompt = data.get('prompt', '')
    preferred_source = data.get('preferred_source', 'auto')
    requested_model = data.get('model', '')
    if not prompt:
        return jsonify({'success': False, 'error': 'No prompt'}), 400

    _store_credentials_from_message(prompt)
    base_prompt = _build_agent_system_prompt(prompt)
    source_hint = ""
    if preferred_source == 'web':
        web_context = _get_web_context_safe_v2(prompt, 10)
        source_hint = (
            "\n\n⚠️ AKTUELLE EINSTELLUNG: Internet-Suche aktiviert.\n"
            "VORAB-ERGEBNISSE (web_search):\n"
            f"{web_context}\n\n"
            "Du kannst jederzeit eigene web_search()- oder fetch_news()-Aufrufe tätigen "
            "falls die VORAB-ERGEBNISSE nicht ausreichen.\n"
        )
    elif preferred_source == 'deep':
        web_context = _get_web_context_safe_v2(prompt, 15)
        source_hint = (
            "\n\n⚠️ DEEP RESEARCH MODUS aktiviert.\n"
            "VORAB-ERGEBNISSE (web_search):\n"
            f"{web_context}\n\n"
            "**DEEP RESEARCH REGELN**:\n"
            "1. Führe MEHRERE Suchdurchläufe durch – nicht nur einen.\n"
            "2. Prüfe Informationen GEGEN eine zweite Quelle, bevor du sie als Fakt ausgibst.\n"
            "3. WENN eine Quelle unsicher oder unvollständig ist, suche gezielt weiter.\n"
            "4. Gib an, wenn eine Information nicht verifiziert werden kann.\n"
            "5. Nutze web_search() mit verschiedenen Suchbegriffen für vollständige Abdeckung.\n"
            "6. Strukturiere die Antwort ausführlicher als normal – mit Kontext und Einordnung.\n"
            "7. Gib bei Quellen an: Datum, Domain und ggf. Titel der Seite.\n"
        )
    elif preferred_source == 'local':
        source_hint = (
            "\n\n⚠️ AKTUELLE EINSTELLUNG: Der User hat 'Nur lokale Dokumente' aktiviert. "
            "Nutze AUSSCHLIESSLICH search_documents(). KEINE web_search() – "
            "auch nicht bei aktuellen Themen.\n\n"
        )
    system_prompt = base_prompt + source_hint
    active_model = requested_model or ollama_client.model
    content, history, needs_input, research_stats = web_agent_loop(
        active_model, prompt, system_prompt, max_rounds=100
    )

    if needs_input:
        return jsonify({
            'success': True,
            'response': f"⚠️ Ich benötige weitere Informationen:\n\n{needs_input['message']}",
            'requires_input': True,
            'prompt_message': needs_input['message']
        })

    if content is None:
        content = "⚠️ Die Anfrage konnte nicht verarbeitet werden."

    return jsonify({'success': True, 'response': content, 'ui_cards': [], 'research_stats': research_stats})

@app.route('/api/agent/input', methods=['POST'])
def agent_input():
    """Receive user response to a pending prompt_user() and resume the conversation."""
    global _AGENT_SESSION
    data = request.json or {}
    user_input = data.get('input', '').strip()
    if not user_input:
        return jsonify({'success': False, 'error': 'Keine Eingabe'}), 400
    with _app_lock:
        if not _AGENT_SESSION:
            return jsonify({'success': False, 'error': 'Keine ausstehende Frage'}), 400
        session = _AGENT_SESSION
        _AGENT_SESSION = None
    msgs = session['msgs']
    model = session['model']
    tools = session['tools']
    max_rounds = session.get('max_rounds', 100)
    # Add user's response as context
    msgs.append({
        "role": "user",
        "content": f"👤 Der User antwortet: \"{user_input}\"\n\nVerarbeite diese Antwort nun."
    })
    content, history, needs_input, research_stats = web_agent_loop(
        model, "", "", max_rounds=max_rounds, tools=tools, initial_msgs=msgs
    )
    if needs_input:
        with _app_lock:
            _AGENT_SESSION = {
                'msgs': history, 'stats': research_stats, 'model': model,
                'tools': tools, 'max_rounds': max_rounds,
                'prompt': needs_input['message'],
                'secret': False,
            }
        return jsonify({
            'success': True, 'response': needs_input['message'],
            'requires_input': True, 'prompt_message': needs_input['message']
        })
    if content is None:
        content = "⚠️ Die Anfrage konnte nicht verarbeitet werden."
    return jsonify({'success': True, 'response': content, 'research_stats': research_stats})

def _store_credentials_from_message(message):
    """Extract and store server credentials mentioned in the message."""
    ip_match = re.search(r'(192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3})', message)
    if not ip_match:
        ip_match = re.search(r'truenas|proxmox|server', message, re.IGNORECASE)
    user_match = re.search(r'(?:username|benutzer|user)\s+(\S+)', message, re.IGNORECASE)
    pass_match = re.search(r'(?:passwort|password|pass)\s+(\S+)', message, re.IGNORECASE)

    if ip_match:
        ip = ip_match.group(1) if ip_match.lastindex else 'server'
        vault_set(f"truenas/{ip}/ip", ip)
        if user_match:
            vault_set(f"truenas/{ip}/user", user_match.group(1).strip())
        if pass_match:
            pwd = pass_match.group(1).strip().rstrip('.')
            vault_set(f"truenas/{ip}/password", pwd)

# ── Ollama / AI Config ────────────────────────────────────
@app.route('/api/ollama/status', methods=['GET'])
def ollama_status():
    return jsonify({
        'connected': ollama_client.check_connection(),
        'base_url': ollama_client.base_url,
        'model': ollama_client.model
    })

@app.route('/api/ollama/models', methods=['GET'])
def ollama_models():
    try:
        models = ollama_client.list_models()
        if ollama_client.model and ollama_client.model not in models:
            models.insert(0, ollama_client.model)
        return jsonify({
            'connected': True,
            'base_url': ollama_client.base_url,
            'current_model': ollama_client.model,
            'models': models
        })
    except Exception as e:
        return jsonify({
            'connected': False,
            'base_url': ollama_client.base_url,
            'current_model': ollama_client.model,
            'models': [ollama_client.model] if ollama_client.model else [],
            'error': 'Ollama connection failed'
        })

@app.route('/api/ai/config', methods=['GET', 'POST'])
def ai_config():
    if request.method == 'GET':
        cfg = load_ai_config()
        return jsonify({
            'provider': cfg['provider'],
            'base_url': cfg['base_url'],
            'model': cfg['model'],
            'api_key_set': bool(cfg.get('api_key', '')),
            'connected': ollama_client.check_connection() if cfg['provider'] == 'ollama' else True
        })
    data = request.json or {}
    provider = str(data.get('provider', 'ollama')).strip()
    base_url = str(data.get('base_url', '')).strip().rstrip('/')
    model = str(data.get('model', '')).strip()
    api_key = str(data.get('api_key', '')).strip()
    if not model:
        return jsonify({'error': 'model is required'}), 400
    if provider == 'ollama':
        if not base_url:
            return jsonify({'error': 'base_url is required for Ollama'}), 400
        if not (base_url.startswith('http://') or base_url.startswith('https://')):
            return jsonify({'error': 'base_url must start with http:// or https://'}), 400
    elif provider == 'openai':
        if not base_url:
            base_url = 'https://api.openai.com/v1'
        if not api_key:
            api_key = load_ai_config().get('api_key', '')
    else:
        return jsonify({'error': 'Unknown provider'}), 400
    save_ai_config(provider, base_url, model, api_key)
    return jsonify({
        'status': 'saved',
        'provider': provider,
        'base_url': base_url,
        'model': model,
        'api_key_set': bool(api_key),
        'connected': True
    })

@app.route('/api/ai/test', methods=['POST'])
def ai_test():
    data = request.json or {}
    prompt = data.get('prompt', 'Antworte nur mit: OK')
    start = time.time()
    resp = ollama_client.chat([{'role': 'user', 'content': prompt}])
    dur = int((time.time() - start) * 1000)
    if 'error' in resp:
        return jsonify({'status': 'error', 'error': resp['error'], 'duration_ms': dur}), 502
    content = resp.get('message', {}).get('content', '')
    return jsonify({
        'status': 'ok', 'connected': True,
        'base_url': ollama_client.base_url,
        'model': ollama_client.model,
        'duration_ms': dur,
        'response': content,
        'response_preview': content[:280]
    })

@app.route('/api/permission/mode', methods=['GET', 'POST'])
def permission_mode():
    from core.tools import PERMISSION_HELP, PERMISSION_MODE
    if request.method == 'GET':
        return jsonify({'success': True, 'mode': PERMISSION_MODE, 'help': PERMISSION_HELP})
    data = request.json or {}
    mode = data.get('mode', 'auto')
    if mode not in PERMISSION_HELP:
        return jsonify({'success': False, 'error': f'Invalid mode: {mode}. Valid: {", ".join(PERMISSION_HELP.keys())}'}), 400
    _ct.PERMISSION_MODE = mode
    return jsonify({'success': True, 'mode': mode})

@app.route('/api/ai/check-models', methods=['POST'])
def api_ai_check_models():
    data = request.json or {}
    base_url = str(data.get('base_url', ollama_client.base_url)).rstrip('/')
    if not (base_url.startswith('http://') or base_url.startswith('https://')):
        return jsonify({'error': 'Invalid base_url'}), 400
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=8)
        r.raise_for_status()
        all_models = sorted(set(m['name'] for m in r.json().get('models', [])))
    except Exception as e:
        return jsonify({'error': 'Cannot fetch models from ' + base_url}), 502
    results = []
    for model in all_models:
        supported = check_tool_support(model, base_url)
        results.append({'model': model, 'tool_support': supported})
    return jsonify({'base_url': base_url, 'results': results})

# ── Vault API ────────────────────────────────────────
@app.route('/api/vault/entries', methods=['GET'])
def api_vault_entries():
    try:
        vault_data = json.loads(VAULT_FILE.read_text()) if VAULT_FILE.exists() else {}
        entries = [{'key': k, 'value': v} for k, v in sorted(vault_data.items())]
        return jsonify({'entries': entries, 'count': len(entries)})
    except Exception as e:
        return jsonify({'error': "Request failed", 'entries': [], 'count': 0})

@app.route('/api/vault/entries', methods=['POST'])
def api_vault_set():
    data = request.json or {}
    key = (data.get('key') or '').strip()
    value = (data.get('value') or '').strip()
    if not key or not value:
        return jsonify({'error': 'key and value required'}), 400
    vault_set(key, value)
    return jsonify({'status': 'saved', 'key': key})

@app.route('/api/vault/entries/<path:key>', methods=['DELETE'])
def api_vault_delete(key):
    vault_delete(key)
    return jsonify({'status': 'deleted', 'key': key})

# ── Knowledge Base ────────────────────────────────────────
@app.route('/api/knowledge/status', methods=['GET'])
def knowledge_status():
    return jsonify({
        'chunks_loaded': len(knowledge_base.chunks),
        'documents_count': len(set(c.get('source', '') for c in knowledge_base.chunks)),
        'semantic_search_available': len(knowledge_base.chunks) > 0,
        'database_path': str(CHUNKS)
    })

@app.route('/api/knowledge/sources', methods=['GET'])
def knowledge_sources():
    sources = list(set(c.get('source', 'Unknown') for c in knowledge_base.chunks))
    return jsonify({'sources': sources, 'total_chunks': len(knowledge_base.chunks)})

@app.route('/api/knowledge/graph-data', methods=['GET'])
def knowledge_graph_data():
    return jsonify({'chunks': knowledge_base.chunks, 'sources': []})

@app.route('/api/knowledge/reload', methods=['POST'])
def knowledge_reload():
    knowledge_base._load()
    return jsonify({'status': 'reloaded', 'chunks_loaded': len(knowledge_base.chunks)})

@app.route('/api/knowledge/update-embeddings', methods=['POST'])
def knowledge_update_embeddings():
    return jsonify({'status': 'success', 'message': 'Embeddings are managed by the indexing pipeline'})

# ── Memory (persistent AI memory across chats) ──
MEMORY_FILE = DATA_DIR / 'memory.json'

def _load_memory():
    if MEMORY_FILE.exists():
        return json.loads(MEMORY_FILE.read_text())
    return {}

def _save_memory(m):
    MEMORY_FILE.write_text(json.dumps(m, indent=2, ensure_ascii=False))

@app.route('/api/memory', methods=['GET'])
def api_memory_list():
    m = _load_memory()
    items = [{'key': k, 'value': v} for k, v in sorted(m.items())]
    return jsonify({'items': items, 'count': len(items)})

@app.route('/api/memory/<path:key>', methods=['GET'])
def api_memory_get(key):
    m = _load_memory()
    if key in m:
        return jsonify({'key': key, 'value': m[key]})
    return jsonify({'error': 'not found'}), 404

@app.route('/api/memory', methods=['POST'])
def api_memory_set():
    data = request.get_json(silent=True) or {}
    key = data.get('key', '').strip()
    value = data.get('value', '').strip()
    if not key:
        return jsonify({'error': 'key required'}), 400
    m = _load_memory()
    m[key] = value
    _save_memory(m)
    return jsonify({'status': 'saved', 'key': key})

@app.route('/api/memory/<path:key>', methods=['DELETE'])
def api_memory_delete(key):
    m = _load_memory()
    if key in m:
        del m[key]
        _save_memory(m)
        return jsonify({'status': 'deleted', 'key': key})
    return jsonify({'error': 'not found'}), 404

# ── Indexing (simplified – calls nextcloud-lightrag sync) ──
INDEXING_STATUS = {'status': 'idle', 'progress': 0, 'current_file': '', 'processed_files': 0, 'total_files': 0, 'errors': [], 'elapsed_time': 0}

@app.route('/api/indexing/start', methods=['POST'])
def indexing_start():
    global INDEXING_STATUS
    with _app_lock:
        INDEXING_STATUS = {'status': 'running', 'progress': 0, 'current_file': '', 'processed_files': 0, 'total_files': 0, 'errors': [], 'elapsed_time': 0, 'started_at': time.time()}

    def run_index():
        global INDEXING_STATUS
        try:
            from scripts.sync_nextcloud import main as sync_main
            logger.info("Starting Nextcloud sync...")
            with _app_lock:
                INDEXING_STATUS['current_file'] = 'Syncing from Nextcloud...'
            sync_main()
            with _app_lock:
                INDEXING_STATUS['current_file'] = 'Indexing complete'
                INDEXING_STATUS['status'] = 'completed'
                INDEXING_STATUS['progress'] = 100
                INDEXING_STATUS['elapsed_time'] = time.time() - INDEXING_STATUS.get('started_at', time.time())
            knowledge_base._load()
        except Exception as e:
            with _app_lock:
                INDEXING_STATUS['status'] = 'error'
                INDEXING_STATUS['errors'].append(str(e)[:200])
            logger.error(f"Indexing error: {e}")

    threading.Thread(target=run_index, daemon=True).start()
    return jsonify({'status': 'started', 'message': 'Indexing started'})

@app.route('/api/indexing/stop', methods=['POST'])
def indexing_stop():
    global INDEXING_STATUS
    with _app_lock:
        INDEXING_STATUS = {'status': 'stopped', 'progress': 0}
    return jsonify({'status': 'stopped'})

@app.route('/api/indexing/progress', methods=['GET'])
def indexing_progress():
    with _app_lock:
        status = INDEXING_STATUS['status']
        progress = INDEXING_STATUS['progress']
        current_file = INDEXING_STATUS.get('current_file', '')
        processed_files = INDEXING_STATUS.get('processed_files', 0)
        total_files = INDEXING_STATUS.get('total_files', 0)
        elapsed_time = INDEXING_STATUS.get('elapsed_time', 0)
        errors = INDEXING_STATUS.get('errors', [])
    return jsonify({
        'status': status,
        'progress_percentage': progress,
        'current_file': current_file,
        'processed_files': processed_files,
        'total_files': total_files,
        'elapsed_time': elapsed_time,
        'errors': errors
    })

@app.route('/api/indexing/config', methods=['GET', 'POST'])
def indexing_config():
    if request.method == 'GET':
        cfg_file = DATA_DIR / 'indexing_config.json'
        if cfg_file.exists():
            cfg = json.loads(cfg_file.read_text())
            return jsonify({'url': cfg.get('url', ''), 'username': cfg.get('username', ''), 'password': '***' if cfg.get('password') else ''})
        return jsonify({'url': '', 'username': '', 'password': ''})
    data = request.json or {}
    pw = data.get('password', '')
    if pw:
        vault_set('indexing/password', pw)
    cfg = {'url': data.get('url', ''), 'username': data.get('username', ''), 'password': '***' if pw else ''}
    (DATA_DIR / 'indexing_config.json').write_text(json.dumps(cfg, indent=2))
    return jsonify({'status': 'saved'})

def _nextcloud_status():
    if not nextcloud_plugin:
        return False, "Nextcloud plugin not available"
    try:
        url, dav, user, pw = nextcloud_plugin._nc()
        return True, {"url": url, "dav": dav, "user": user, "configured": bool(url and user and pw)}
    except Exception:
        return False, "Nextcloud connection failed"

def _calendar_range(kind, day_name=None):
    today = date.today()
    if kind == 'tomorrow':
        start = today + timedelta(days=1)
        end = start
    elif kind == 'week':
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
    elif kind == 'next-week':
        start = today - timedelta(days=today.weekday()) + timedelta(days=7)
        end = start + timedelta(days=6)
    elif kind == 'day':
        names = {
            'montag': 0, 'monday': 0,
            'dienstag': 1, 'tuesday': 1,
            'mittwoch': 2, 'wednesday': 2,
            'donnerstag': 3, 'thursday': 3,
            'freitag': 4, 'friday': 4,
            'samstag': 5, 'saturday': 5,
            'sonntag': 6, 'sunday': 6,
        }
        target = names.get(str(day_name or '').lower(), today.weekday())
        start = today - timedelta(days=today.weekday()) + timedelta(days=target)
        end = start
    else:
        start = today
        end = today
    return start, end

def _calendar_query_response(start, end):
    ok, info = _nextcloud_status()
    if not ok:
        return {'success': False, 'enabled': False, 'events': [], 'event_count': 0, 'error': 'Nextcloud nicht verbunden'}, 503
    text = nextcloud_plugin.nextcloud_caldav_query(start.strftime('%Y%m%d'), end.strftime('%Y%m%d'))
    if str(text).startswith("❌"):
        return {'success': False, 'enabled': True, 'events': [], 'event_count': 0, 'error': 'Calendar query failed'}, 502
    lines = [line.strip() for line in str(text).splitlines() if line.strip() and not line.strip().startswith('📅')]
    events = [{'text': line.lstrip('• ').strip()} for line in lines if line.lstrip('• ').strip()]
    return {
        'success': True,
        'enabled': True,
        'start_date': start.isoformat(),
        'end_date': end.isoformat(),
        'events': events,
        'event_count': len(events),
        'raw': text
    }, 200

# ── Calendar (Nextcloud CalDAV) ──────────────────────────
@app.route('/api/calendar/status', methods=['GET'])
def calendar_status():
    ok, info = _nextcloud_status()
    return jsonify({'enabled': ok, 'connected': ok, 'message': 'Nextcloud CalDAV verfügbar' if ok else 'Nextcloud nicht verbunden'})

@app.route('/api/calendar/calendars', methods=['GET'])
def calendar_calendars():
    ok, info = _nextcloud_status()
    if not ok:
        return jsonify({'success': False, 'calendars': [], 'count': 0, 'error': info}), 503
    try:
        url, dav, user, pw = nextcloud_plugin._nc()
        auth = requests.auth.HTTPBasicAuth(user, pw)
        cals = nextcloud_plugin._caldav_discover(url, user, auth)
        calendars = [{'name': name, 'href': href} for name, href in cals]
        return jsonify({'success': True, 'calendars': calendars, 'count': len(calendars)})
    except Exception as e:
        return jsonify({'success': False, 'calendars': [], 'count': 0, 'error': "Request failed"}), 502

@app.route('/api/calendar/create', methods=['POST'])
def calendar_create():
    data = request.json or {}
    result = nextcloud_plugin.nextcloud_caldav_create(
        data.get('summary') or data.get('title') or '',
        data.get('dtstart') or data.get('start') or '',
        data.get('dtend') or data.get('end') or '',
        data.get('description', ''),
        data.get('calendar_name') or data.get('calendarName') or 'Persönlich'
    ) if nextcloud_plugin else '❌ Nextcloud plugin not available'
    return jsonify({'success': not str(result).startswith('❌'), 'message': result, 'result': result})

@app.route('/api/calendar/create-with-details', methods=['POST'])
def calendar_create_with_details():
    return calendar_create()

@app.route('/api/calendar/today', methods=['GET'])
def calendar_today():
    start, end = _calendar_range('today')
    payload, status = _calendar_query_response(start, end)
    payload.update({'date': start.strftime('%d.%m.%Y'), 'weekday': ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'][start.weekday()]})
    return jsonify(payload), status

@app.route('/api/calendar/tomorrow', methods=['GET'])
def calendar_tomorrow():
    start, end = _calendar_range('tomorrow')
    payload, status = _calendar_query_response(start, end)
    return jsonify(payload), status

@app.route('/api/calendar/week', methods=['GET'])
def calendar_week():
    start, end = _calendar_range('week')
    payload, status = _calendar_query_response(start, end)
    return jsonify(payload), status

@app.route('/api/calendar/next-week', methods=['GET'])
def calendar_next_week():
    start, end = _calendar_range('next-week')
    payload, status = _calendar_query_response(start, end)
    return jsonify(payload), status

@app.route('/api/calendar/day/<day_name>', methods=['GET'])
def calendar_day(day_name):
    start, end = _calendar_range('day', day_name)
    payload, status = _calendar_query_response(start, end)
    payload['day'] = day_name
    return jsonify(payload), status

# ── Tasks / Todos (Nextcloud VTODO) ─────────────────────
@app.route('/api/tasks/status', methods=['GET'])
def tasks_status():
    ok, info = _nextcloud_status()
    return jsonify({'enabled': ok, 'connected': ok, 'message': 'Nextcloud Tasks verfügbar' if ok else 'Nextcloud nicht verbunden'})

@app.route('/api/tasks/list', methods=['GET'])
def tasks_list():
    ok, info = _nextcloud_status()
    if not ok:
        return jsonify({'success': False, 'tasks': [], 'count': 0, 'enabled': False, 'error': info}), 503
    text = nextcloud_plugin.nextcloud_tasks_query()
    tasks = [{'text': line.strip()} for line in str(text).splitlines() if line.strip()]
    return jsonify({'success': not str(text).startswith('❌'), 'tasks': tasks, 'count': len(tasks), 'enabled': True, 'raw': text})

@app.route('/api/tasks/create', methods=['POST'])
def tasks_create():
    data = request.json or {}
    result = nextcloud_plugin.nextcloud_tasks_create(
        data.get('summary') or data.get('title') or '',
        data.get('due') or data.get('dueDate') or '',
        data.get('description', ''),
        data.get('calendar_name') or data.get('listName') or 'Aufgaben'
    ) if nextcloud_plugin else '❌ Nextcloud plugin not available'
    return jsonify({'success': not str(result).startswith('❌'), 'message': result, 'result': result})

@app.route('/api/tasks/create-with-details', methods=['POST'])
def tasks_create_with_details():
    return tasks_create()

@app.route('/api/tasks/init', methods=['POST'])
def tasks_init():
    ok, info = _nextcloud_status()
    return jsonify({'enabled': ok, 'success': ok, 'message': 'Nextcloud Tasks verfügbar' if ok else 'Nextcloud nicht verbunden'})

@app.route('/api/tasks/complete/<task_uid>', methods=['POST'])
def tasks_complete(task_uid):
    return jsonify({'error': 'Tasks not available'}), 400

@app.route('/api/tasks/sync', methods=['POST'])
def tasks_sync():
    return jsonify({'error': 'Tasks not available'}), 400

@app.route('/api/tasks/sync-status', methods=['GET'])
def tasks_sync_status():
    return jsonify({'status': {}, 'is_loading': False})

@app.route('/api/tasks/db-stats', methods=['GET'])
def tasks_db_stats():
    return jsonify({})

# ── Security ─────────────────────────────────────────────
SECURITY_MODE_FILE = DATA_DIR / 'security_mode.json'

def load_security_mode():
    if SECURITY_MODE_FILE.exists():
        try:
            return json.loads(SECURITY_MODE_FILE.read_text())
        except Exception:
            pass
    return {'mode': 'standard'}

def save_security_mode(mode):
    SECURITY_MODE_FILE.write_text(json.dumps({'mode': mode}, indent=2))

@app.route('/api/security/status', methods=['GET'])
def security_status():
    sm = load_security_mode()
    return jsonify({
        'success': True,
        'headline': 'Sicherheitsstatus',
        'nina_warning_count': 0,
        'nina_warnings': [],
        'weather': None,
        'security_mode': sm['mode']
    })

@app.route('/api/security/mode', methods=['GET', 'POST'])
def security_mode():
    if request.method == 'POST':
        data = request.json or {}
        mode = data.get('mode', 'standard')
        if mode not in ('restricted', 'standard', 'admin'):
            return jsonify({'error': 'Invalid mode. Must be restricted, standard, or admin'}), 400
        save_security_mode(mode)
        return jsonify({'success': True, 'mode': mode})
    sm = load_security_mode()
    return jsonify({'success': True, 'mode': sm['mode']})

# ── API References Editor ────────────────────────────────
API_REFS_PATH = os.path.join(DATA_DIR, 'api_refs.json')

@app.route('/api/references', methods=['GET', 'POST'])
def api_references():
    if request.method == 'POST':
        data = request.json or {}
        refs = data.get('refs')
        if refs is None:
            return jsonify({'error': 'Missing refs'}), 400
        with open(API_REFS_PATH, 'w') as f:
            json.dump(refs, f, indent=2, ensure_ascii=False)
        return jsonify({'success': True})
    with open(API_REFS_PATH) as f:
        refs = json.load(f)
    return jsonify({'success': True, 'refs': refs})

# ── Briefings (stub) ──────────────────────────────────────
@app.route('/api/assistant/briefing/current', methods=['GET'])
def assistant_briefing():
    return jsonify({'success': True, 'items': []})

# ── Email / Registry (stub) ──────────────────────────────
@app.route('/api/registry/email/config', methods=['GET'])
def registry_email_config():
    return jsonify({'success': True, 'config': None})

# ── Location ──────────────────────────────────────────────
@app.route('/api/location/resolve', methods=['POST'])
def location_resolve():
    return jsonify({'success': True})

# ── Training ──────────────────────────────────────────────
@app.route('/api/training/stats', methods=['GET'])
def training_stats():
    return jsonify({'total_interactions': 0, 'feedback_count': 0})

# ── Settings page stubs (not yet implemented) ─────────────
@app.route('/api/ui/system-config', methods=['GET', 'POST'])
def ui_system_config():
    if request.method == 'POST':
        return jsonify({'success': True})
    return jsonify({'success': True, 'config': {
        'immich_url_default': '', 'immich_api_key_default': '',
        'briefing_daily_enabled': True, 'briefing_weekly_enabled': False,
        'briefing_morning_hour': 7, 'briefing_send_daily': False,
        'briefing_send_weekly': False, 'briefing_send_recipients': '',
        'briefing_send_account_id': '', 'briefing_send_talk': False,
        'briefing_talk_room_id': '', 'briefing_talk_webhook_secret_set': False
    }})

@app.route('/api/email/config', methods=['GET', 'POST'])
def email_config():
    if request.method == 'POST':
        data = request.json or {}
        for key in ('imap_server','imap_port','imap_user','imap_password','smtp_server','smtp_port','smtp_user','smtp_password'):
            val = data.get(key)
            if val is not None:
                vault_set(f'email/{key}', str(val))
        return jsonify({'success': True})
    return jsonify({'success': True, 'config': {
        'imap_server': _vg('email/imap_server'), 'imap_port': _vg('email/imap_port'),
        'imap_user': _vg('email/imap_user'), 'imap_password': '••••' if _vg('email/imap_password') else '',
        'smtp_server': _vg('email/smtp_server'), 'smtp_port': _vg('email/smtp_port'),
        'smtp_user': _vg('email/smtp_user'), 'smtp_password': '••••' if _vg('email/smtp_password') else '',
    }})


@app.route('/api/nextcloud/config', methods=['GET'])
def nextcloud_config():
    ok, info = _nextcloud_status()
    if not ok:
        return jsonify({'configured': False, 'display_name': '', 'username': '', 'nextcloud_url': '', 'error': 'Nextcloud nicht verbunden'})
    return jsonify({
        'configured': True,
        'display_name': info.get('user', ''),
        'username': info.get('user', ''),
        'nextcloud_url': info.get('url', ''),
        'webdav_path': info.get('dav', '')
    })

@app.route('/api/nextcloud/loginflow/start', methods=['POST'])
def nextcloud_loginflow_start():
    return jsonify({'error': 'Not implemented'})

@app.route('/api/nextcloud/loginflow/poll', methods=['GET'])
def nextcloud_loginflow_poll():
    return jsonify({'status': 'error', 'error': 'Not implemented'})

@app.route('/api/nextcloud/disconnect', methods=['POST'])
def nextcloud_disconnect():
    return jsonify({'success': True})

@app.route('/api/nextcloud/talk/webhook', methods=['POST'])
def nextcloud_talk_webhook():
    return jsonify({'success': True, 'message': 'Not implemented'})

@app.route('/api/calendar/config', methods=['GET', 'POST'])
def calendar_config():
    if request.method == 'POST':
        return jsonify({'success': True})
    return jsonify({'default_calendar_name': ''})

@app.route('/api/indexing/path', methods=['GET', 'POST'])
def indexing_path():
    if request.method == 'POST':
        return jsonify({'success': True})
    return jsonify({'path': ''})

@app.route('/api/indexing/stats', methods=['GET'])
def indexing_stats():
    return jsonify({'documents': 0, 'chunks': 0, 'embeddings': 0, 'last_indexing': None})

@app.route('/api/email-indexing/config', methods=['GET', 'POST'])
def email_indexing_config():
    if request.method == 'POST':
        return jsonify({'success': True})
    return jsonify({'imap_host': '', 'imap_port': 993, 'username': '', 'folders': '', 'max_emails': 100, 'use_ssl': True})

@app.route('/api/email-indexing/start', methods=['POST'])
def email_indexing_start():
    return jsonify({'success': True})

@app.route('/api/email-indexing/progress', methods=['GET'])
def email_indexing_progress():
    return jsonify({'status': 'idle', 'progress_percentage': 0, 'emails_processed': 0, 'elapsed_time': 0, 'current_folder': '', 'status_message': '', 'indexed_emails': 0, 'skipped_emails': 0, 'indexed_chunks': 0})  # noqa: E501

@app.route('/api/email-indexing/stop', methods=['POST'])
def email_indexing_stop():
    return jsonify({'success': True})

@app.route('/api/knowledge/txt-files', methods=['GET'])
def knowledge_txt_files():
    return jsonify({'files': []})

@app.route('/api/knowledge/upload-txt', methods=['POST'])
def knowledge_upload_txt():
    return jsonify({'uploaded': [], 'total_chunks': 0, 'errors': []})

@app.route('/api/knowledge/txt-files/<doc_id>', methods=['DELETE'])
def knowledge_txt_file_delete(doc_id):
    return jsonify({'success': True})

@app.route('/api/registry/apis', methods=['GET'])
def registry_apis():
    return jsonify({'apis': []})

@app.route('/api/registry/health', methods=['GET'])
def registry_health():
    return jsonify({'health': {}})

@app.route('/api/registry/<api_name>/config', methods=['GET', 'POST', 'DELETE'])
def registry_api_config(api_name):
    if request.method == 'DELETE':
        return jsonify({'success': True})
    if request.method == 'POST':
        return jsonify({'success': True})
    return jsonify({'config': {}, 'api_name': api_name})

@app.route('/api/registry/<api_name>/test', methods=['POST'])
def registry_api_test(api_name):
    return jsonify({'health': {'status': 'unknown', 'error': 'Not implemented'}})

@app.route('/api/email/test', methods=['POST'])
def email_test():
    try:
        import imaplib
        import smtplib
        imap_ok = False
        smtp_ok = False
        errors = []
        imap_server = _vg('email/imap_server')
        imap_port = int(_vg('email/imap_port') or 993)
        imap_user = _vg('email/imap_user')
        imap_pass = _vg('email/imap_password')
        if imap_server and imap_user and imap_pass:
            try:
                c = imaplib.IMAP4_SSL(imap_server, imap_port, timeout=10)
                c.login(imap_user, imap_pass)
                c.logout()
                imap_ok = True
            except Exception:
                errors.append('IMAP connection failed')
        else:
            errors.append('IMAP unconfigured')
        smtp_server = _vg('email/smtp_server')
        smtp_port = int(_vg('email/smtp_port') or 587)
        smtp_user = _vg('email/smtp_user')
        smtp_pass = _vg('email/smtp_password')
        if smtp_server and smtp_user and smtp_pass:
            try:
                s = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
                s.starttls()
                s.login(smtp_user, smtp_pass)
                s.quit()
                smtp_ok = True
            except Exception:
                errors.append('SMTP connection failed')
        else:
            errors.append('SMTP unconfigured')
        return jsonify({'success': imap_ok or smtp_ok, 'imap': imap_ok, 'smtp': smtp_ok, 'errors': errors})
    except Exception as e:
        return jsonify({'success': False, 'error': "Request failed"})

@app.route('/api/email/folders', methods=['POST'])
def email_folders():
    try:
        import imaplib
        imap_server = _vg('email/imap_server')
        imap_port = int(_vg('email/imap_port') or 993)
        imap_user = _vg('email/imap_user')
        imap_pass = _vg('email/imap_password')
        if not all([imap_server, imap_user, imap_pass]):
            return jsonify({'success': False, 'error': 'IMAP not configured'})
        c = imaplib.IMAP4_SSL(imap_server, imap_port, timeout=10)
        c.login(imap_user, imap_pass)
        _, folders = c.list()
        c.logout()
        names = []
        for f in folders:
            parts = f.decode().split(' "/" ')
            if len(parts) == 2:
                names.append(parts[1].strip())
        return jsonify({'success': True, 'folders': names or ['INBOX']})
    except Exception as e:
        return jsonify({'success': False, 'error': "Request failed"})


# ── E-Mail-Konten API ──────────────────────────────────

@app.route('/api/email/accounts', methods=['GET', 'POST'])
def api_email_accounts():
    """GET: Liste alle E-Mail-Konten. POST: Speichere ein Konto."""
    if request.method == 'GET':
        try:
            default = {
                "imap_server": _vg("email/imap_server") or "",
                "imap_user": _vg("email/imap_user") or "",
                "smtp_server": _vg("email/smtp_server") or "",
                "smtp_user": _vg("email/smtp_user") or "",
            }
            result = {"default": default} if default.get("imap_server") else {}
            # Scan for additional accounts from flat vault keys
            v = json.loads(VAULT_FILE.read_text()) if VAULT_FILE.exists() else {}
            for k in v:
                if k.startswith("email/accounts/") and k.endswith("/imap_server"):
                    name = k.split("/")[2]
                    if name not in result:
                        pref = f"email/accounts/{name}"
                        result[name] = {
                            "imap_server": v.get(f"{pref}/imap_server", ""),
                            "imap_port": v.get(f"{pref}/imap_port", "993"),
                            "imap_user": v.get(f"{pref}/imap_user", ""),
                            "smtp_server": v.get(f"{pref}/smtp_server", ""),
                            "smtp_port": v.get(f"{pref}/smtp_port", "587"),
                            "smtp_user": v.get(f"{pref}/smtp_user", ""),
                        }
            return jsonify({"success": True, "accounts": result})
        except Exception as e:
            return jsonify({"success": False, "error": "Request failed"})
    data = request.json or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "error": "Konto-Name erforderlich"}), 400
    for key in ["imap_server", "imap_port", "imap_user", "imap_password",
                 "smtp_server", "smtp_port", "smtp_user", "smtp_password"]:
        if key in data and data[key]:
            _vs(f"email/accounts/{name}/{key}", str(data[key]))
    return jsonify({"success": True, "account": name})


@app.route('/api/email/accounts/<name>', methods=['DELETE'])
def api_email_account_delete(name):
    """Lösche ein E-Mail-Konto."""
    try:
        for key in ["imap_server", "imap_port", "imap_user", "imap_password",
                     "smtp_server", "smtp_port", "smtp_user", "smtp_password"]:
            vault_delete(f"email/accounts/{name}/{key}")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": "Request failed"})


# ── E-Mail-Indexierung ─────────────────────────────────

@app.route('/api/email/index', methods=['POST'])
def email_index():
    """Indiziere E-Mails in den RAG-Index."""
    import data.plugins.email as em
    data = request.json or {}
    account = data.get("account", "default")
    max_emails = int(data.get("max_emails", 50))
    try:
        result = em.email_search(query="ALL", max_results=max_emails, account=account)
        if result.startswith("❌"):
            return jsonify({"success": False, "error": result})
        lines = result.split('\n')
        count = len([line for line in lines if line.startswith("ID:")])
        return jsonify({"success": True, "indexed": count, "account": account})
    except Exception as e:
        return jsonify({"success": False, "error": "Request failed"})


# ── Indexing-Schedule (startet beim App-Start) ─────────

def _start_indexing_scheduler():
    """Startet periodische Indexierung von E-Mails, Nextcloud etc."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        sched = BackgroundScheduler()

        # E-Mails indexieren alle 30 Minuten
        @sched.scheduled_job('interval', minutes=30, id='email_index', max_instances=1)
        def auto_index_emails():
            try:
                from data.plugins.email import _list_accounts, email_search
                accts = _list_accounts()
                for acct in accts:
                    try:
                        email_search(query="ALL", max_results=10, account=acct)
                    except Exception:
                        pass
            except Exception:
                pass

        # Nextcloud-Termine/Tasks indexieren alle 60 Minuten
        @sched.scheduled_job('interval', minutes=60, id='nc_index', max_instances=1)
        def auto_index_nextcloud():
            try:
                from data.plugins.nextcloud import nextcloud_caldav_query, nextcloud_tasks_query
                today = datetime.now().strftime("%Y%m%d")
                nextcloud_caldav_query(today, today)
                nextcloud_tasks_query()
            except Exception:
                pass

        # Tägliches Briefing um 7:00
        @sched.scheduled_job('cron', hour=7, minute=0, id='morning_briefing', max_instances=1)
        def auto_briefing():
            try:
                requests.get("http://127.0.0.1:5001/api/agent/briefing", timeout=30)
            except Exception:
                pass

        sched.start()
    except Exception:
        pass


@app.route('/api/indexing/status', methods=['GET'])
def indexing_status():
    """Status der Indexierung."""
    try:
        stats = {"email_accounts": 0, "last_briefing": None}
        from data.plugins.email import _list_accounts
        stats["email_accounts"] = len(_list_accounts())
        return jsonify({"success": True, "stats": stats})
    except Exception as e:
        return jsonify({"success": False, "error": "Request failed"})


# ── Tagesassistent Briefing ──────────────────────────────

@app.route('/api/agent/briefing', methods=['GET'])
def agent_briefing():
    """Generiert ein persönliches Tages-Briefing mit Terminen, E-Mails, Aufgaben und Fotos."""
    try:
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        date_str = now.strftime("%A, %d. %B %Y")
        time_str = now.strftime("%H:%M")

        briefing = {
            "date": date_str,
            "time": time_str,
            "sections": []
        }

# 1. Nextcloud-Termine heute
        try:
            import data.plugins.nextcloud as nc
            cal, _ = call_with_timeout(nc.nextcloud_caldav_query,
                (today_str.replace("-",""), today_str.replace("-","")), timeout=10)
            if cal and "❌" not in cal and "(keine)" not in cal:
                briefing["sections"].append({"title": "📅 Termine heute", "content": cal[:2000]})
        except Exception:
            pass

        # 2. Ungelesene/Unbeantwortete E-Mails (nur wenn Konten konfiguriert)
        try:
            import data.plugins.email as em
            accounts = em._list_accounts()
            if accounts and "❌" not in str(accounts) and accounts != "Keine E-Mail-Konten konfiguriert.":
                unread, _ = call_with_timeout(em.email_search,
                    (), {"query": "UNSEEN", "max_results": 10}, timeout=8)
                if unread and "❌" not in unread and "(keine)" not in unread:
                    briefing["sections"].append({"title": "📧 Ungelesene E-Mails", "content": unread[:2000]})
                unanswered, _ = call_with_timeout(em.email_search,
                    (), {"query": "UNANSWERED", "max_results": 10}, timeout=8)
                if unanswered and "❌" not in unanswered and "(keine)" not in unanswered:
                    briefing["sections"].append({"title": "✉️ Unbeantwortete E-Mails", "content": unanswered[:2000]})
        except Exception:
            pass

        # 3. Nextcloud-Aufgaben
        try:
            import data.plugins.nextcloud as nc
            tasks, _ = call_with_timeout(nc.nextcloud_tasks_query, timeout=10)
            if tasks and "❌" not in tasks and "(keine)" not in tasks:
                briefing["sections"].append({"title": "✅ Offene Aufgaben", "content": tasks[:2000]})
        except Exception:
            pass

        # 4. Heutige Fotos (Immich)
        try:
            import data.plugins.immich as imm
            photos, _ = call_with_timeout(imm.immich_search_photos,
                (), {"date_from": today_str, "date_to": today_str, "size": 5}, timeout=10)
            if photos and "❌" not in photos and "(keine Ergebnisse)" not in photos:
                briefing["sections"].append({"title": "📸 Heutige Fotos", "content": photos[:2000]})
        except Exception:
            pass

        return jsonify({"success": True, "briefing": briefing})
    except Exception as e:
        return jsonify({"success": False, "error": "Request failed"})


# ── Immich ──────────────────────────────────────────────

@app.route('/api/immich/config', methods=['POST'])
def immich_config():
    data = request.json or {}
    url = (data.get('url') or '').strip()
    api_key = (data.get('api_key') or '').strip()
    if url:
        vault_set('immich/url', url)
    if api_key:
        vault_set('immich/api_key', api_key)
    return jsonify({'success': True, 'url_set': bool(url), 'key_set': bool(api_key)})

@app.route('/api/immich/thumbnail/<asset_id>')
def immich_thumbnail(asset_id):
    key = _vg('immich/api_key')
    url = _vg('immich/url')
    if not key or not url:
        return jsonify({'error': 'Immich not configured'}), 400
    try:
        h = {'x-api-key': key}
        base = url.rstrip('/')
        # Try thumbnail (fast), then original file (full res) as fallback
        for ep in [f"{base}/api/assets/{asset_id}/thumbnail", f"{base}/api/assets/{asset_id}/original"]:
            r = requests.get(ep, headers=h, timeout=10, stream=True)
            if r.ok:
                return Response(r.raw, content_type=r.headers.get('Content-Type', 'image/jpeg'), status=r.status_code)
            if r.status_code != 404:
                break
        # Transparent 1x1 GIF as last resort
        return Response(b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b',
                        content_type='image/gif')
    except Exception as e:
        return jsonify({'error': "Request failed"}), 500


@app.route('/api/immich/original/<asset_id>')
def immich_original(asset_id):
    """Proxy for full-resolution Immich original image."""
    key = _vg('immich/api_key')
    url = _vg('immich/url')
    if not key or not url:
        return jsonify({'error': 'Immich not configured'}), 400
    try:
        h = {'x-api-key': key}
        base = url.rstrip('/')
        ep = f"{base}/api/assets/{asset_id}/original"
        r = requests.get(ep, headers=h, timeout=30, stream=True)
        if r.ok:
            return Response(r.raw, content_type=r.headers.get('Content-Type', 'image/jpeg'), status=r.status_code)
        # Try /download as fallback
        ep2 = f"{base}/api/assets/{asset_id}/download"
        r2 = requests.get(ep2, headers=h, timeout=30, stream=True)
        if r2.ok:
            return Response(r2.raw, content_type=r2.headers.get('Content-Type', 'image/jpeg'), status=r2.status_code)
        return jsonify({'error': f'Original nicht gefunden (Status {r.status_code})'}), 404
    except Exception as e:
        return jsonify({'error': "Request failed"}), 500


@app.route('/api/immich/test', methods=['POST'])
def immich_test():
    url = _vg('immich/url')
    api_key = _vg('immich/api_key')
    if not url or not api_key:
        return jsonify({'success': False, 'error': 'Not configured. Store URL and API-Key first.'})
    try:
        resp = requests.post(url.rstrip('/') + '/api/search/metadata', json={"query": "", "page": 1, "size": 1}, headers={'x-api-key': api_key, 'Content-Type': 'application/json'}, timeout=10)
        if resp.ok:
            data = resp.json()
            count = data.get("assets", {}).get("total", data.get("total", "?"))
            return jsonify({'success': True, 'status': 'connected', 'asset_count': count})
        return jsonify({'success': False, 'error': f'Immich responded with {resp.status_code}: {resp.text[:200]}'})
    except Exception as e:
        return jsonify({'success': False, 'error': "Request failed"})

@app.route('/api/nina/regions', methods=['GET'])
def nina_regions():
    return jsonify({'data': {'items': []}})

@app.route('/api/nina/dashboard', methods=['GET'])
def nina_dashboard():
    return jsonify({'data': {}, 'ars': ''})

# ── Suggestions API ─────────────────────────────────────
@app.route('/api/suggestions/query', methods=['POST'])
def suggestions_query():
    data = request.json or {}
    lang = data.get('language', 'de')
    chat_history = data.get('chatHistory', [])
    now = datetime.now()
    hour = now.hour
    if hour < 5:
        tp = 'night'
    elif hour < 12:
        tp = 'morning'
    elif hour < 17:
        tp = 'afternoon'
    else:
        tp = 'evening'

    recent = []
    for m in (chat_history or [])[-4:]:
        c = m.get('content', '')
        if len(c) > 200:
            c = c[:200] + '…'
        recent.append(f"{m.get('role', 'user')}: {c}")
    context = '\n'.join(recent)

    model = ollama_client.model
    mem_info = ""
    mem_file = DATA_DIR / 'memory.json'
    if mem_file.exists():
        try:
            mem = json.loads(mem_file.read_text())
            if mem:
                mem_info = "User-Memory: " + "; ".join(f"{k}={v}" for k, v in list(mem.items())[:5])
        except Exception:
            pass
    prompt = (
        f"Generate 3 short, useful question suggestions (max 8 words each) for a personal AI assistant. "
        f"Time: {tp}. "
        f"Language: {'German' if lang == 'de' else 'English'}. "
        f"{'Context: ' + mem_info + '. ' if mem_info else ''}"
        f"Recent chat:\n{context}\n\n"
        f"Suggestions should be relevant to the user's context and time of day. "
        f"Return ONLY a JSON array of 3 strings, e.g. [\"…\", \"…\", \"…\"]. "
        f"No markdown, no explanation."
    )

    try:
        from core.llm import chat_with_tools
        resp = chat_with_tools(model, [{"role": "user", "content": prompt}], [])
        content = (resp.get("message") or resp).get("content", "")
        content = content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            content = content.rsplit("```", 1)[0]
        suggestions = json.loads(content)
        if not isinstance(suggestions, list) or len(suggestions) != 3:
            raise ValueError("unexpected format")
        return jsonify({'success': True, 'suggestions': suggestions, 'time_period': tp, 'personalized': True})
    except Exception:
        defaults_de = [
            'Was steht heute auf meinem Kalender?',
            'Zeige mir meine Aufgaben für heute',
            'Was ist neu in meinen Dateien?'
        ]
        defaults_en = [
            "What's on my calendar today?",
            'Show me my tasks for today',
            "What's new in my files?"
        ]
        suggestions = defaults_de if lang == 'de' else defaults_en
        return jsonify({'success': True, 'suggestions': suggestions, 'time_period': tp, 'personalized': False})

@app.route('/api/ai/greeting', methods=['POST'])
def ai_greeting():
    data = request.json or {}
    lang = data.get('language', 'de')
    name = data.get('name', '')
    now = datetime.now()
    hour = now.hour
    if hour < 5:
        tp = 'night'
    elif hour < 12:
        tp = 'morning'
    elif hour < 17:
        tp = 'afternoon'
    else:
        tp = 'evening'

    weekdays_de = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
    weekdays_en = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    wd = (weekdays_de if lang == 'de' else weekdays_en)[now.weekday()]

    name_suffix = f" The user's name is {name}." if name else ""
    prompt = (
        f"Generate a short, warm greeting for {tp} on {wd} in {'German' if lang == 'de' else 'English'}. "
        f"Include 1-2 fitting emojis (e.g. ☀️🌅🌙🌟🌻 etc.). "
        f"Max 10 words. "
        f"Return ONLY the greeting text, nothing else.{name_suffix}"
    )

    try:
        from core.llm import chat_with_tools
        resp = chat_with_tools(ollama_client.model, [{"role": "user", "content": prompt}], [])
        content = (resp.get("message") or resp).get("content", "").strip()
        if not content:
            raise ValueError("empty")
        return jsonify({'success': True, 'greeting': content})
    except Exception:
        segment_greetings = {
            'morning': 'Guten Morgen' if lang == 'de' else 'Good morning',
            'afternoon': 'Guten Tag' if lang == 'de' else 'Good afternoon',
            'evening': 'Guten Abend' if lang == 'de' else 'Good evening',
            'night': 'Hallo' if lang == 'de' else 'Hello',
        }
        base = segment_greetings.get(tp, 'Hallo' if lang == 'de' else 'Hello')
        greeting = f"{base}, {name}" if name else base
        return jsonify({'success': True, 'greeting': greeting})

# ── Backup Export/Import ──────────────────────────────────
@app.route('/api/backup/export', methods=['GET'])
@require_admin
def backup_export():
    import base64
    files = {}
    data_dir = DATA_DIR
    for fname in os.listdir(data_dir):
        fpath = data_dir / fname
        if fpath.is_file() and fname != 'setup_done.json':
            try:
                raw = fpath.read_bytes()
                if fname.endswith('.npy'):
                    files[fname] = {'content': base64.b64encode(raw).decode('ascii'), 'encoding': 'base64'}
                else:
                    files[fname] = {'content': raw.decode('utf-8'), 'encoding': 'utf-8'}
            except Exception as e:
                files[fname] = {'error': 'read failed'}
    return jsonify({'success': True, 'files': files, 'exported_at': datetime.now(UTC).isoformat()})

@app.route('/api/backup/import', methods=['POST'])
@require_admin
def backup_import():
    import base64
    data = request.json or {}
    files = data.get('files', {})
    if not isinstance(files, dict):
        return jsonify({'success': False, 'error': 'files must be an object'}), 400
    errors = []
    restored = 0
    for fname, meta in files.items():
        if (
            not isinstance(fname, str)
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', fname)
            or '/' in fname
            or '\\' in fname
        ):
            errors.append(f"Rejected unsafe filename: {fname}")
            continue
        if not isinstance(meta, dict):
            errors.append(f"{fname}: metadata must be an object")
            continue
        if meta.get('error'):
            errors.append(f"Skipped {fname}: source error")
            continue
        try:
            content = meta.get('content', '')
            encoding = meta.get('encoding', 'utf-8')
            safe_restore = os.path.normpath('/' + fname).lstrip('/')
            fpath = os.path.realpath(os.path.join(DATA_DIR, safe_restore))
            if not fpath.startswith(os.path.realpath(DATA_DIR)):
                errors.append(f"{fname}: invalid path")
                continue
            if encoding == 'base64':
                Path(fpath).write_bytes(base64.b64decode(content, validate=True))
            elif encoding == 'utf-8':
                Path(fpath).write_text(content, encoding='utf-8')
            else:
                errors.append(f"{fname}: unsupported encoding")
                continue
            restored += 1
        except Exception:
            errors.append(f"{fname}: restore failed")
    return jsonify({'success': True, 'restored': restored, 'errors': errors})

# ── Tool confirmation ─────────────────────────────────────
@app.route('/api/tool/run', methods=['POST'])
@require_auth
def tool_run():
    """Execute a tool that was previously pending confirmation."""
    global _PENDING_TOOL_CONFIRM
    data = request.json or {}
    with _app_lock:
        if not _PENDING_TOOL_CONFIRM:
            return jsonify({'success': False, 'error': 'No pending tool'}), 400
        pending = _PENDING_TOOL_CONFIRM
        _PENDING_TOOL_CONFIRM = None
    confirmed = data.get('confirmed', False)
    if not confirmed:
        return jsonify({'success': True, 'result': '⛔ Abgebrochen (nicht bestätigt)'})
    func = WEB_TOOL_MAP.get(pending['tool'])
    if not func:
        return jsonify({'success': False, 'error': f'Unknown tool: {pending["tool"]}'}), 400
    try:
        _ct.PERMISSION_MODE = 'auto'
        result = func(**pending['args'])
        return jsonify({'success': True, 'result': str(result)})
    except Exception as e:
        return jsonify({'success': False, 'error': "Request failed"}), 500

# ── Automations API ────────────────────────────────────────


@app.route('/api/automations', methods=['GET'])
def list_automations():
    return jsonify({'success': True, 'automations': automation_engine.load_automations()})

@app.route('/api/automations', methods=['POST'])
def create_automation():
    data = request.json or {}
    auto = {
        "id": data.get("id", str(int(time.time() * 1000))),
        "name": data.get("name", "Neue Automation"),
        "description": data.get("description", ""),
        "enabled": data.get("enabled", True),
        "trigger": data.get("trigger", {"type": "cron", "hour": "6", "minute": "0"}),
        "steps": data.get("steps", [])
    }
    if not auto.get("steps"):
        return jsonify({'success': False, 'error': 'Mindestens ein Schritt erforderlich'}), 400
    automation_engine.add_automation(auto)
    return jsonify({'success': True, 'automation': auto})

@app.route('/api/automations/<aid>', methods=['PUT'])
def update_automation(aid):
    data = request.json or {}
    ok = automation_engine.update_automation(aid, data)
    if not ok:
        return jsonify({'success': False, 'error': 'Nicht gefunden'}), 404
    return jsonify({'success': True, 'automation': automation_engine.get_automation(aid)})

@app.route('/api/automations/<aid>', methods=['DELETE'])
def delete_automation(aid):
    automation_engine.delete_automation(aid)
    return jsonify({'success': True})

@app.route('/api/automations/<aid>/test', methods=['POST'])
def test_automation(aid):
    result = automation_engine.run_automation(aid)
    return jsonify(result)

@app.route('/api/automations/history', methods=['GET'])
def list_automation_history():
    limit = request.args.get('limit', 50, type=int)
    history = automation_engine.load_history()
    history.sort(key=lambda h: h.get('timestamp', ''), reverse=True)
    return jsonify({'success': True, 'history': history[:limit]})

@app.route('/api/automations/schema', methods=['GET'])
def automation_schema():
    from core.plugin_base import get_registry
    from core.tools import CORE_TOOLS
    plugin_tools, _ = get_all_tools()
    all_tools = CORE_TOOLS + plugin_tools
    plugins_info = []
    tool_groups = {}
    for t in CORE_TOOLS:
        tool_groups[t['function']['name']] = 'Core'
    for name, p in get_registry().items():
        if p is None:
            plugins_info.append({'name': name, 'description': '', 'version': '', 'tools': [], 'tool_count': 0})
            continue
        pname = p.name or name
        plugins_info.append({
            'name': pname,
            'description': getattr(p, 'description', ''),
            'version': getattr(p, 'version', ''),
            'tools': [t.get('function', {}).get('name', '') for t in getattr(p, 'tools', [])],
            'tool_count': len(getattr(p, 'tools', []))
        })
        for t in getattr(p, 'tools', []):
            tname = t.get('function', {}).get('name', '')
            if tname:
                tool_groups[tname] = pname
    return jsonify({
        'success': True,
        'tools': all_tools,
        'tool_groups': tool_groups,
        'plugins': plugins_info,
        'cron_help': CRON_HELP,
        'trigger_examples': TRIGGER_EXAMPLES
    })


@app.route('/api/plugins', methods=['GET'])
def list_plugins():
    from core.plugin_base import get_all_plugins
    return jsonify({'success': True, 'plugins': get_all_plugins()})

@app.route('/api/plugins/install', methods=['POST'])
@require_admin
def install_plugin():
    from core.plugin_base import install_from_github
    data = request.get_json(silent=True) or {}
    url = data.get('url', '')
    if not url:
        return jsonify({'success': False, 'error': 'URL erforderlich'}), 400
    try:
        name = install_from_github(url)
        return jsonify({'success': True, 'name': name})
    except Exception as e:
        return jsonify({'success': False, 'error': "Request failed"}), 400

@app.route('/api/plugins/<name>/toggle', methods=['POST'])
@require_admin
def toggle_plugin(name):
    from core.plugin_base import set_plugin_enabled
    data = request.get_json(silent=True) or {}
    enabled = data.get('enabled', True)
    try:
        set_plugin_enabled(name, enabled)
        return jsonify({'success': True, 'enabled': enabled})
    except Exception as e:
        return jsonify({'success': False, 'error': "Request failed"}), 400

@app.route('/api/plugins/<name>', methods=['DELETE'])
@require_admin
def delete_plugin(name):
    from core.plugin_base import uninstall_plugin
    try:
        uninstall_plugin(name)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': "Request failed"}), 400

# ── Main ──────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 50)
    print("  mynd-2new – Frontend + nextcloud-lightrag Backend")
    print("=" * 50)
    print(f"  Ollama:     {ollama_client.base_url}")
    print(f"  Model:      {ollama_client.model}")
    print(f"  Chunks:     {len(knowledge_base.chunks)}")
    print("  Backend:    http://127.0.0.1:5001/api/")
    print("  Frontend:   cd frontend && npm run dev")
    print(f"  Automations: {len(automation_engine.load_automations())} aktiv")
    print("=" * 50)
    automation_engine.start()
    _start_indexing_scheduler()

    # Warm-up: Modell initial laden (damit erste Anfrage nicht timeoutet)
    try:
        _warm = ollama_client.chat([{"role": "user", "content": "Antworte nur mit: OK"}])
        if 'error' in _warm:
            logger.warning(f"Model warm-up: {_warm['error']}")
    except Exception as _we:
        logger.warning(f"Model warm-up failed: {_we}")

    app.run(debug=False, host='0.0.0.0', port=5001, use_reloader=False, threaded=True)
