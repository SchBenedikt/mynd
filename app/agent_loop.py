import json
import re
import secrets
import time
from urllib.parse import urljoin, urlparse

import core.tools as _ct

# Plugin references
from app.config import DATA_DIR, GENERATED_DIR, VAULT_FILE, _app_lock, logger
from app.helpers import load_security_mode
from app.session_store import agent_sessions
from app.state import _PENDING_TOOL_CONFIRMS, _PRIVILEGED_TOOL_NAMES, _PRIVILEGED_TOOL_PREFIXES, _audit_log
from core.llm import chat_with_tools, chat_with_tools_stream
from core.plugin_base import get_all_tools
from core.tools import CORE_MAP, CORE_TOOLS, execute_ssh, http_request, safe_http_request, think, vault_set
from core.vault import load_vault

plugins_loaded = False
PLUGIN_TOOLS = []
PLUGIN_TOOL_MAP = {}
AGENT_TOOLS = []
WEB_TOOL_MAP = {}

_CONFIRMATION_REQUIRED_TOOLS = frozenset()


def _tool_requires_confirmation(name, args):
    mode = load_security_mode().get('mode', 'standard')
    if mode == 'admin':
        return False
    if name in _CONFIRMATION_REQUIRED_TOOLS:
        return True
    if name in {'http_request', 'nextcloud_request', 'immich_api_request', 'truenas_api_request'}:
        return str((args or {}).get('method', 'GET')).upper() not in {'GET', 'HEAD', 'OPTIONS'}
    return False


def _queue_tool_confirmation(name, args, owner):
    confirmation_id = secrets.token_urlsafe(24)
    with _app_lock:
        _PENDING_TOOL_CONFIRMS[confirmation_id] = {
            'tool': name, 'args': args, 'owner': owner, 'created_at': time.time(),
        }
    return confirmation_id


def _confirmation_description(name, args):
    target = next((args.get(key) for key in ('path', 'url', 'host', 'filename', 'summary') if args.get(key)), None)
    suffix = f' ({str(target)[:120]})' if target else ''
    return f'{name}{suffix} ausführen?'


def load_plugins():
    global plugins_loaded, PLUGIN_TOOLS, PLUGIN_TOOL_MAP, AGENT_TOOLS, WEB_TOOL_MAP
    from core.plugin_base import get_all_tools as _get_all_tools
    from core.plugin_base import load_plugins as _load_plugins
    _load_plugins()
    PLUGIN_TOOLS, PLUGIN_TOOL_MAP = _get_all_tools()
    AGENT_TOOLS = [*CORE_TOOLS, *PLUGIN_TOOLS]
    new_map = {**CORE_MAP, **PLUGIN_TOOL_MAP, 'prompt_user': web_prompt_user}
    WEB_TOOL_MAP.clear()
    WEB_TOOL_MAP.update(new_map)
    plugins_loaded = True


def web_prompt_user(message, secret=False):
    return "⏳ USER_INPUT_REQUIRED: " + message


_ct.prompt_user = web_prompt_user
_ct._CONFIRM_TOOL_PENDING = True


_INTERMEDIATE_PATTERNS = [
    r'\blass mich\b',
    r'\bich (?:prüfe|schaue|sehe|rufe|frage|teste|versuche|werde|suche|starte|beginne)\b',
    r'\b(?:prüfe|schaue|rufe|frage|teste|versuche|suche|starte) (?:ich )?(?:jetzt|nun|mal)\b',
    r'\b(?:api|referenz|referenzen|apps?|kalender|nextcloud|truenas|immich).*\b(?:prüfen|abfragen|abrufen|testen|suchen|durchsuchen)\b',
]


def _looks_like_intermediate_response(text):
    cleaned = str(text or '').strip().lower()
    if not cleaned or len(cleaned) > 500:
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
    import re
    from html import unescape
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
        resp = safe_http_request('GET', source_url, timeout=8, headers=headers, max_bytes=250_000)
        if not resp.ok:
            return None
        content_type = resp.headers.get('Content-Type', '').lower()
        if content_type and not any(kind in content_type for kind in ('text/html', 'application/xhtml+xml')):
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
    from urllib.parse import urlparse
    text = str(content or "").rstrip()
    if not text or _extract_numbered_sources(text):
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
                    '.html': 'text/html', '.htm': 'text/html',
                    '.pdf': 'application/pdf', '.png': 'image/png',
                    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                    '.gif': 'image/gif', '.svg': 'image/svg+xml',
                    '.csv': 'text/csv', '.json': 'application/json',
                    '.txt': 'text/plain', '.md': 'text/markdown',
                    '.py': 'text/x-python', '.js': 'application/javascript',
                    '.css': 'text/css',
                }.get(ext, 'application/octet-stream')
                files.append({
                    "name": f.name, "path": f"api/generated/{f.name}",
                    "url": f"/api/generated/{f.name}", "size": f.stat().st_size,
                    "type": mime, "ext": ext,
                })
    return files


def _decorate_response_with_media(content, stats):
    content = _strip_tool_code_blocks(content)
    with_sources = _ensure_numbered_sources(content, stats)
    result = _append_source_images(with_sources, stats)
    files = _detect_generated_files()
    result = re.sub(
        r'https?://[^/\s]+(/api/immich/(?:thumbnail|original)/[^\s")\]]+)',
        r'\1', result
    )
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


def _strip_tool_code_blocks(text):
    if not text:
        return text
    cleaned = str(text)
    cleaned = re.sub(r'<tool_code>[^<]*</tool_code>', '', cleaned)
    cleaned = re.sub(r'<tool_code>[^<]*</minimax:tool_call>', '', cleaned)
    cleaned = re.sub(r'<tool[ >][^<]*</tool>', '', cleaned)
    cleaned = re.sub(r'<tool\s+[^>]*/>', '', cleaned)
    cleaned = re.sub(r'\[TOOL_CALL\][^<]*\[/TOOL_CALL\]', '', cleaned)
    cleaned = re.sub(r'<tool_call>[^<]*</tool_call>', '', cleaned)
    return cleaned.strip()


def _parse_tool_code_fallback(text):
    from core.tools import _parse_tool_code_fallback as _parse
    return _parse(text)


# ── Web Agent Loop ─────────────────────────────────────────
def web_agent_loop(model, user_msg, system_prompt, max_rounds=8, tools=None, initial_msgs=None, owner=None):
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
                logger.warning('Model request failed: %s', resp.get('error'))
                return "Model provider unavailable", msgs, None, stats
            msg = resp.get("message", {})

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
                            if _tool_requires_confirmation(name, args):
                                confirmation_id = _queue_tool_confirmation(name, args, owner)
                                return None, msgs, {
                                    'message': _confirmation_description(name, args),
                                    'confirmation_id': confirmation_id,
                                    'tool': name,
                                    'requires_confirmation': True,
                                }, stats
                            result = func(**args)
                            if isinstance(result, str) and result.startswith("⏳ USER_INPUT_REQUIRED"):
                                message = args.get('message', result.replace('⏳ USER_INPUT_REQUIRED: ', ''))
                                session_id = agent_sessions.create(owner, {
                                    'msgs': msgs, 'stats': stats, 'model': model,
                                    'tools': tools, 'max_rounds': max_rounds,
                                    'prompt': message, 'secret': args.get('secret', False),
                                })
                                msgs.append({"role": "tool", "content": "⏳ Warte auf Antwort...", "name": "prompt_user"})
                                return None, msgs, {'message': message, 'session_id': session_id}, stats
                            if isinstance(result, str) and result.startswith("⏳ TOOL_CONFIRM_REQUIRED"):
                                message = result.replace("⏳ TOOL_CONFIRM_REQUIRED: Bist du sicher, dass du ", "").rstrip("?") + "?"
                                return None, msgs, {'message': message}, stats
                        except Exception:
                            logger.exception('Tool execution failed: %s', name)
                            result = "❌ Tool execution failed"
                            success = False
                    else:
                        result = f"❌ Unbekanntes Tool: {name}"
                        success = False
                tool_duration = int((time.time() - tool_start) * 1000)
                safe_args = {k: ('***' if any(secret in k.lower() for secret in ['password', 'pass', 'secret', 'api', 'token']) else v) for k, v in args.items()}
                if name.startswith(_PRIVILEGED_TOOL_PREFIXES) or name in _PRIVILEGED_TOOL_NAMES:
                    _audit_log(name, 'unknown', args, success, result, tool_duration)

                round_tools.append({
                    "name": name, "args": safe_args, "duration_ms": tool_duration,
                    "result_size": len(str(result)), "success": success, "result": str(result)[:1000]
                })

                msgs.append({
                    "role": "tool", "content": "<untrusted_tool_data>\n" + str(result)[:8000] + "\n</untrusted_tool_data>",
                    "name": name, "tool_call_id": tc.get("id", "")
                })

            stats.append({
                "round": rnd + 1, "tool_count": len(tc_list),
                "duration_ms": int((time.time() - rnd_start) * 1000), "tools": round_tools
            })

            if bypass_executed:
                break

        # Bypass
        logger.info("Model stuck in think loop – executing SSH/API directly")
        vault_data = load_vault(VAULT_FILE) if VAULT_FILE.exists() else {}
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
            except Exception:
                logger.exception('TrueNAS SSH check failed')
                rows.append("SSH check failed")
                ssh_result = "SSH check failed"
            if "Permission denied" in ssh_result or "sshpass" in ssh_result.lower() or "timeout" in ssh_result.lower():
                try:
                    token_resp = http_request(method='POST', url=f'http://{ip}/api/v2.0/auth/generate_token', headers={"Content-Type": "application/json"}, body=json.dumps({"username": user_val, "password": pwd_val}))
                    if "200" in token_resp:
                        rows.append(f"TrueNAS API erreichbar.\n{token_resp[:500]}")
                    else:
                        rows.append(f"TrueNAS API fehlgeschlagen:\n{token_resp[:500]}")
                except Exception:
                    logger.exception('TrueNAS HTTP check failed')
                    rows.append("HTTP check failed")
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
    except Exception:
        logger.exception("Unhandled error in web_agent_loop")
        return "❌ Internal processing error", msgs, None, stats


# ── Streaming Agent Loop ───────────────────────────────────
def web_agent_loop_stream(model, user_msg, system_prompt, max_rounds=8, tools=None, owner=None):
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

            if not final_msg.get("tool_calls"):
                raw_text = final_msg.get("content", "")
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
                                if _tool_requires_confirmation(name, args):
                                    confirmation_id = _queue_tool_confirmation(name, args, owner)
                                    yield {
                                        "type": "confirm_tool", "confirmation_id": confirmation_id,
                                        "tool": name, "description": _confirmation_description(name, args),
                                    }
                                    return
                                result = func(**args)
                                if isinstance(result, str) and result.startswith("⏳ USER_INPUT_REQUIRED"):
                                    message = args.get('message', result.replace('⏳ USER_INPUT_REQUIRED: ', ''))
                                    session_id = agent_sessions.create(owner, {
                                        'msgs': msgs, 'stats': stats, 'model': model,
                                        'tools': tools, 'max_rounds': max_rounds,
                                        'prompt': message, 'secret': args.get('secret', False),
                                    })
                                    msgs.append({"role": "tool", "content": "⏳ Warte auf Antwort...", "name": "prompt_user"})
                                    yield {"type": "needs_input", "message": message, "session_id": session_id}
                                    return
                                if isinstance(result, str) and result.startswith("⏳ TOOL_CONFIRM_REQUIRED"):
                                    confirmation_id = secrets.token_urlsafe(24)
                                    with _app_lock:
                                        _PENDING_TOOL_CONFIRMS[confirmation_id] = {
                                            'tool': name, 'args': args, 'owner': owner,
                                            'created_at': time.time(),
                                        }
                                    yield {"type": "confirm_tool", "confirmation_id": confirmation_id, "tool": name, "description": result.replace("⏳ TOOL_CONFIRM_REQUIRED: ", "")}
                                    return
                            except Exception:
                                logger.exception('Tool execution failed: %s', name)
                                result = "❌ Tool execution failed"
                                success = False
                        else:
                            result = f"❌ Unbekanntes Tool: {name}"
                            success = False
                        tool_duration = int((time.time() - tool_start) * 1000)
                        if name.startswith(_PRIVILEGED_TOOL_PREFIXES) or name in _PRIVILEGED_TOOL_NAMES:
                            _audit_log(name, owner, args, success, result, tool_duration)
                        browser_data = None
                        if name.startswith('browser_') and isinstance(result, str):
                            m = re.search(r'"screenshot"\s*:\s*"([^"]+)"', result)
                            if m:
                                t = re.search(r'"title"\s*:\s*"([^"]+)"', result) or re.search(r'"new_title"\s*:\s*"([^"]+)"', result)
                                u = re.search(r'"url"\s*:\s*"([^"]+)"', result) or re.search(r'"new_url"\s*:\s*"([^"]+)"', result)
                                tx = re.search(r'"text_preview"\s*:\s*"([^"]+)"', result) or re.search(r'"text"\s*:\s*"([^"]+)"', result)
                                browser_data = {"screenshot": m.group(1)}
                                if t: browser_data["title"] = t.group(1)
                                if u: browser_data["url"] = u.group(1)
                                if tx: browser_data["text_preview"] = tx.group(1)
                        yield {"type": "tool_end", "round": rnd + 1, "tool": name, "result_preview": str(result)[:2000], "duration_ms": tool_duration, "success": success, "browser": browser_data}
                        rnd_tools.append({"name": name, "args": safe_args, "duration_ms": tool_duration, "result_size": len(str(result)), "success": success, "result": str(result)[:5000]})
                        msgs.append({"role": "tool", "content": "<untrusted_tool_data>\n" + str(result)[:8000] + "\n</untrusted_tool_data>", "name": name})
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
                            if _tool_requires_confirmation(name, args):
                                confirmation_id = _queue_tool_confirmation(name, args, owner)
                                yield {
                                    "type": "confirm_tool", "confirmation_id": confirmation_id,
                                    "tool": name, "description": _confirmation_description(name, args),
                                }
                                return
                            result = func(**args)
                            if isinstance(result, str) and result.startswith("⏳ USER_INPUT_REQUIRED"):
                                message = args.get('message', result.replace('⏳ USER_INPUT_REQUIRED: ', ''))
                                session_id = agent_sessions.create(owner, {
                                    'msgs': msgs, 'stats': stats, 'model': model,
                                    'tools': tools, 'max_rounds': max_rounds,
                                    'prompt': message, 'secret': args.get('secret', False),
                                })
                                yield {"type": "needs_input", "message": message, "session_id": session_id}
                                return
                            if isinstance(result, str) and result.startswith("⏳ TOOL_CONFIRM_REQUIRED"):
                                confirmation_id = secrets.token_urlsafe(24)
                                with _app_lock:
                                    _PENDING_TOOL_CONFIRMS[confirmation_id] = {
                                        'tool': name, 'args': args, 'owner': owner,
                                        'created_at': time.time(),
                                    }
                                yield {"type": "confirm_tool", "confirmation_id": confirmation_id, "tool": name, "description": result.replace("⏳ TOOL_CONFIRM_REQUIRED: ", "")}
                                return
                        except Exception:
                            logger.exception('Tool execution failed: %s', name)
                            result = "❌ Tool execution failed"
                            success = False
                    else:
                        result = f"❌ Unbekanntes Tool: {name}"
                        success = False
                tool_duration = int((time.time() - tool_start) * 1000)
                if name.startswith(_PRIVILEGED_TOOL_PREFIXES) or name in _PRIVILEGED_TOOL_NAMES:
                    _audit_log(name, owner, args, success, result, tool_duration)

                browser_data = None
                if name.startswith('browser_') and isinstance(result, str):
                    m = re.search(r'"screenshot"\s*:\s*"([^"]+)"', result)
                    if m:
                        t = re.search(r'"title"\s*:\s*"([^"]+)"', result) or re.search(r'"new_title"\s*:\s*"([^"]+)"', result)
                        u = re.search(r'"url"\s*:\s*"([^"]+)"', result) or re.search(r'"new_url"\s*:\s*"([^"]+)"', result)
                        tx = re.search(r'"text_preview"\s*:\s*"([^"]+)"', result) or re.search(r'"text"\s*:\s*"([^"]+)"', result)
                        browser_data = {"screenshot": m.group(1)}
                        if t: browser_data["title"] = t.group(1)
                        if u: browser_data["url"] = u.group(1)
                        if tx: browser_data["text_preview"] = tx.group(1)
                yield {"type": "tool_end", "round": rnd + 1, "tool": name, "result_preview": str(result)[:2000], "duration_ms": tool_duration, "success": success, "browser": browser_data}

                round_tools.append({
                    "name": name, "args": safe_args, "duration_ms": tool_duration,
                    "result_size": len(str(result)), "success": success, "result": str(result)[:5000]
                })

                msgs.append({
                    "role": "tool", "content": "<untrusted_tool_data>\n" + str(result)[:8000] + "\n</untrusted_tool_data>",
                    "name": name, "tool_call_id": tc.get("id", "")
                })

            stats.append({
                "round": rnd + 1, "tool_count": len(tc_list),
                "duration_ms": int((time.time() - rnd_start) * 1000), "tools": round_tools
            })
            yield {"type": "round_end", "round": rnd + 1, "round_stats": stats[-1]}

            if bypass_executed:
                break

        # Bypass
        logger.info("Model stuck in think loop – executing SSH/API directly")
        vault_data = load_vault(VAULT_FILE) if VAULT_FILE.exists() else {}
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
            except Exception:
                logger.exception('TrueNAS SSH check failed')
                rows.append("SSH check failed")
                ssh_result = "SSH check failed"
            yield {"type": "tool_end", "round": rnd + 1, "tool": "execute_ssh", "result_preview": ssh_result[:300], "duration_ms": 0, "success": "Permission denied" not in ssh_result}
            if "Permission denied" in ssh_result or "sshpass" in ssh_result.lower() or "timeout" in ssh_result.lower():
                yield {"type": "tool_start", "round": rnd + 1, "tool": "http_request", "args": {"method": "POST", "url": f"http://{ip}/api/v2.0/auth/generate_token"}}
                try:
                    token_resp = http_request(method='POST', url=f'http://{ip}/api/v2.0/auth/generate_token', headers={"Content-Type": "application/json"}, body=json.dumps({"username": user_val, "password": pwd_val}))
                    if "200" in token_resp:
                        rows.append(f"TrueNAS API erreichbar.\n{token_resp[:500]}")
                    else:
                        rows.append(f"TrueNAS API fehlgeschlagen:\n{token_resp[:500]}")
                except Exception:
                    logger.exception('TrueNAS HTTP check failed')
                    rows.append("HTTP check failed")
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


def _store_credentials_from_message(message):
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


def _get_tool_names_for_prompt():
    lines = []
    lines.append("  - think(thought): Überlege und plane")
    lines.append("  - vault_get(key): Zugangsdaten lesen")
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
    all_tools, _ = get_all_tools()
    for t in all_tools:
        fn = t.get('function', {})
        name = fn.get('name', '')
        desc = fn.get('description', '')
        params = fn.get('parameters', {}).get('properties', {})
        skip_names = ('think', 'vault_get', 'vault_set', 'http_request', 'execute_ssh',
                      'execute_python', 'web_search', 'fetch_news', 'search_documents',
                      'read_local_file', 'write_local_file', 'memory_get', 'memory_set', 'prompt_user')
        if name and name not in skip_names and not name.startswith('_'):
            param_names = list(params.keys())
            lines.append(f"  - {name}({', '.join(param_names)}): {desc[:200]}")
    return '\n'.join(lines)


def _get_vault_keys_for_prompt():
    vault_file = DATA_DIR / 'vault.json'
    if not vault_file.exists():
        return ""
    try:
        v = load_vault(vault_file)
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
