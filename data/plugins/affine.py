import json
import time
from pathlib import Path

import requests

from core.vault import load_vault

PLUGIN_NAME = "affine"
PLUGIN_DESC = "AFFiNE – Open-Source-Wissensdatenbank (Docs, Knowledge Base)"

VAULT_FILE = Path(__file__).parent.parent / 'vault.json'
CACHE_FILE = Path(__file__).parent / 'affine_cache.json'
CONTENT_CACHE_FILE = Path(__file__).parent / 'affine_content_cache.json'


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


_AFFINE_SESSION = None
_AFFINE_CSRF = None


def _login():
    global _AFFINE_SESSION, _AFFINE_CSRF
    domain = _vget("affine/domain")
    email = _vget("affine/email")
    password = _vget("affine/password")
    if not domain or not email or not password:
        return None, "Domain, E-Mail und Passwort eintragen."

    if _AFFINE_SESSION is not None:
        try:
            h = _AFFINE_SESSION.get(f"{domain.rstrip('/')}/api/auth/session", timeout=10)
            if h.status_code == 200:
                return _AFFINE_SESSION, None
        except (requests.RequestException, Exception):
            pass
        _AFFINE_SESSION = None
        _AFFINE_CSRF = None

    import time as _time
    for attempt in range(3):
        try:
            s = requests.Session()
            r = s.post(f"{domain.rstrip('/')}/api/auth/sign-in", json={
                "email": email,
                "password": password,
            }, headers={"Content-Type": "application/json"}, timeout=15)
            if r.status_code == 429:
                _time.sleep(2 ** attempt)
                continue
            if r.status_code != 200:
                return None, f"Login fehlgeschlagen ({r.status_code}): {r.json().get('message', r.text[:200])}"
            _AFFINE_SESSION = s
            _AFFINE_CSRF = s.cookies.get("affine_csrf_token") or ""
            return s, None
        except requests.RequestException as e:
            return None, f"AFFiNE nicht erreichbar: {e}"
        except Exception as e:
            return None, str(e)
    return None, "Login fehlgeschlagen (429 – zu viele Anfragen, bitte warten)."


def _graphql(query, variables=None):
    s, err = _login()
    if err:
        return {"error": err}
    domain = _vget("affine/domain")
    import time as _time
    for attempt in range(3):
        try:
            r = s.post(f"{domain.rstrip('/')}/graphql", json={
                "query": query,
                "variables": variables or {},
            }, headers={
                "Content-Type": "application/json",
                "x-affine-client-version": "0.25.0",
                "x-csrf-token": _AFFINE_CSRF or "",
            }, timeout=15)
            if r.status_code == 429:
                _time.sleep(2 ** attempt)
                continue
            data = r.json()
            if "errors" in data:
                return {"error": data["errors"][0].get("message", str(data["errors"]))}
            return data.get("data", {})
        except requests.RequestException as e:
            return {"error": f"AFFiNE nicht erreichbar: {e}"}
        except Exception as e:
            return {"error": str(e)}
    return {"error": "GraphQL: 429 (zu viele Anfragen)"}


def _list_workspaces():
    data = _graphql("{ workspaces { id } }")
    if "error" in data:
        return [], data["error"]
    return data.get("workspaces", []), None


# ── Cache Management ───────────────────────────────────────────

def _load_title_cache():
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text())
        except (OSError, json.JSONDecodeError):
            pass
    return {"titles": {}}


def _save_title_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, indent=2, ensure_ascii=False))


def _load_content_cache():
    if CONTENT_CACHE_FILE.exists():
        try:
            return json.loads(CONTENT_CACHE_FILE.read_text())
        except (OSError, json.JSONDecodeError):
            pass
    return {"contents": {}}


def _save_content_cache(cache):
    CONTENT_CACHE_FILE.write_text(json.dumps(cache, indent=2, ensure_ascii=False))


# ── Yjs Decoding Helpers ───────────────────────────────────────

def _decode_ydoc(yjs_binary):
    try:
        import y_py as Y  # noqa: N812
        ydoc = Y.YDoc()
        Y.apply_update(ydoc, yjs_binary)
        blocks = ydoc.get_map("blocks")
        return ydoc, blocks, None
    except ImportError:
        return None, None, "y-py nicht installiert"
    except Exception as e:
        return None, None, str(e)


def _extract_title(blocks):
    for key in list(blocks.keys()):
        block = blocks[key]
        if isinstance(block, Y.YMap):
            items = dict(block.items())
            if items.get("sys:flavour") == "affine:page" and "prop:title" in items:
                return str(items["prop:title"])
    return None


def _get_block_flavour(block):
    return str(block.get("sys:flavour", "")) if block else ""


def _get_block_text(block):
    val = block.get("prop:text") or block.get("prop:title")
    return str(val) if val is not None else ""


def _get_block_type(block):
    return str(block.get("prop:type", "")) if block else ""


def _get_block_level(block):
    return int(block.get("prop:level", 1)) if block and block.get("prop:level") is not None else 1


def _format_block_text(block_id, block, blocks, depth=0, seen=None):
    if seen is None:
        seen = set()
    if block_id in seen:
        return []
    seen.add(block_id)

    flavour = _get_block_flavour(block)
    text = _get_block_text(block)
    prefix = ""
    suffix = ""

    if flavour == "affine:page":
        prefix = f"{'  ' * depth}📄 "
    elif flavour == "affine:heading":
        level = _get_block_level(block)
        prefix = f"{'  ' * depth}{'#' * level} "
    elif flavour == "affine:list":
        bt = _get_block_type(block)
        if bt == "numbered":
            prefix = f"{'  ' * depth}1. "
        elif bt == "todo":
            checked = block.get("prop:checked")
            prefix = f"{'  ' * depth}{'[x]' if checked else '[ ]'} "
        else:
            prefix = f"{'  ' * depth}- "
    elif flavour == "affine:code":
        lang = block.get("prop:language", "")
        result = [f"{'  ' * depth}```{lang}", text, f"{'  ' * depth}```"]
        children = _get_block_children(block, blocks, depth + 1, seen)
        result.extend(children)
        return result
    elif flavour == "affine:callout":
        prefix = f"{'  ' * depth}> "
    elif flavour == "affine:divider":
        return [f"{'  ' * depth}---"]
    elif flavour == "affine:image":
        caption = block.get("prop:caption", "")
        name = block.get("prop:name", "")
        src = block.get("prop:sourceId", "")
        label = caption or name or f"Image ({src[:20]})" if src else "Image"
        return [f"{'  ' * depth}[Image: {label}]"]
    elif flavour == "affine:bookmark":
        url = block.get("prop:url", "")
        bt = block.get("prop:title", "")
        return [f"{'  ' * depth}[Link: {bt or url}]({url})"]
    elif flavour == "affine:attachment":
        name = block.get("prop:name", "")
        return [f"{'  ' * depth}[Attachment: {name or '(unnamed)'}]"]
    elif flavour == "affine:database":
        db_title = _get_block_text(block) or "(Database)"
        return [f"{'  ' * depth}[Database: {db_title}]"]
    elif flavour == "affine:embed":
        et = block.get("prop:embedType", "")
        url = block.get("prop:url", "")
        return [f"{'  ' * depth}[Embed: {et}]({url})"]
    elif flavour == "affine:table":
        return [f"{'  ' * depth}[Table: {text or '(table)'}]"]
    elif flavour in ("affine:surface", "affine:note", "affine:frame", "affine:edgeless-text"):
        children = _get_block_children(block, blocks, depth, seen)
        if text:
            children.insert(0, f"{'  ' * depth}{text}")
        return children
    elif flavour == "affine:paragraph":
        if not text:
            children = _get_block_children(block, blocks, depth + 1, seen)
            if children:
                return children
            return []

    line = f"{prefix}{text}{suffix}"
    result = [line] if line.strip() else []
    children = _get_block_children(block, blocks, depth + 1, seen)
    result.extend(children)
    return result


def _get_block_children(block, blocks, depth=0, seen=None):
    children_key = block.get("sys:children")
    if children_key is None:
        return []
    try:
        child_ids = list(children_key)
    except (TypeError, ValueError):
        return []
    result = []
    for cid in child_ids:
        cid = str(cid)
        if cid in blocks:
            child = blocks[cid]
            if isinstance(child, dict) or hasattr(child, 'get'):
                result.extend(_format_block_text(cid, child, blocks, depth, seen))
    return result


def _extract_all_text(blocks, max_blocks=100):
    page_block_id = None
    for key in list(blocks.keys()):
        block = blocks[key]
        if isinstance(block, Y.YMap) and block.get("sys:flavour") == "affine:page":
            page_block_id = key
            break
    if page_block_id is None:
        return "(keine Seiten-Struktur gefunden)"

    page_block = blocks[page_block_id]
    lines = _format_block_text(page_block_id, page_block, blocks, depth=0)
    count = 0
    result = []
    for line in lines:
        if count >= max_blocks:
            result.append(f"\n… (gekürzt, mehr als {max_blocks} Blöcke)")
            break
        result.append(line)
        if line.strip():
            count += 1
    return "\n".join(result)


def _extract_block_tree(block_id, block, blocks, depth=0, seen=None):
    if seen is None:
        seen = set()
    if block_id in seen:
        return []
    seen.add(block_id)

    flavour = _get_block_flavour(block)
    text = _get_block_text(block)
    short_text = text[:80] + "…" if len(text) > 80 else text
    type_info = _get_block_type(block)
    info = f" [{type_info}]" if type_info else ""

    icon = "  "
    if flavour == "affine:page":
        icon = "📄"
    elif flavour == "affine:heading":
        icon = "##"
    elif flavour == "affine:list":
        icon = "📌"
    elif flavour == "affine:code":
        icon = "💻"
    elif flavour == "affine:callout":
        icon = "💬"
    elif flavour == "affine:divider":
        icon = "➖"
    elif flavour == "affine:image":
        icon = "🖼️"
    elif flavour == "affine:bookmark":
        icon = "🔗"
    elif flavour == "affine:attachment":
        icon = "📎"
    elif flavour == "affine:database":
        icon = "🗄️"
    elif flavour == "affine:embed":
        icon = "📦"
    elif flavour == "affine:table":
        icon = "📊"
    elif flavour == "affine:paragraph":
        icon = "  "

    indent = "  " * depth
    line = f"{indent}{icon} **{flavour}**{info}"
    if short_text:
        line += f": _{short_text}_"
    result = [line]

    children = _get_block_children(block, blocks, depth, seen)
    if children:
        result.extend(children)
    return result


# ── Content Fetching + Caching ─────────────────────────────────

def _fetch_page_raw(ws_id, doc_id):
    s, err = _login()
    if err:
        return None, err
    domain = _vget("affine/domain")
    import time as _time
    for attempt in range(3):
        try:
            r = s.get(
                f"{domain.rstrip('/')}/api/workspaces/{ws_id}/docs/{doc_id}",
                headers={"x-affine-client-version": "0.25.0", "x-csrf-token": _AFFINE_CSRF or ""},
                timeout=30,
            )
            if r.status_code == 429:
                _time.sleep(2 ** attempt)
                continue
            if r.status_code != 200:
                return None, f"Status {r.status_code}"
            return r.content, None
        except requests.RequestException as e:
            return None, str(e)
    return None, "429 (zu viele Anfragen)"


def _ensure_page_cached(ws_id, doc_id):
    content_cache = _load_content_cache()
    entry = content_cache["contents"].get(doc_id)

    s, err = _login()
    if err:
        return None
    domain = _vget("affine/domain")
    try:
        r = s.head(
            f"{domain.rstrip('/')}/api/workspaces/{ws_id}/docs/{doc_id}",
            headers={"x-affine-client-version": "0.25.0", "x-csrf-token": _AFFINE_CSRF or ""},
            timeout=15,
        )
        current_size = int(r.headers.get("Content-Length", 0))
    except (requests.RequestException, ValueError):
        current_size = 0

    if entry and entry.get("yjs_size") == current_size and current_size > 0:
        return entry

    yjs_binary, fetch_err = _fetch_page_raw(ws_id, doc_id)
    if fetch_err:
        return entry

    ydoc, blocks, decode_err = _decode_ydoc(yjs_binary)
    if decode_err or blocks is None:
        return entry

    title = _extract_title(blocks)
    text = _extract_all_text(blocks, max_blocks=200)

    entry = {
        "title": title or "",
        "text": text,
        "yjs_size": len(yjs_binary),
        "updated_at": time.time(),
        "block_count": len(list(blocks.keys())),
    }
    content_cache["contents"][doc_id] = entry
    _save_content_cache(content_cache)
    return entry


def _fetch_page_metadata_graphql(ws_id, doc_id):
    data = _graphql(
        """query ($wsId: String!, $docId: String!) {
            workspace(id: $wsId) {
                doc(docId: $docId) {
                    id title createdAt updatedAt mode
                    createdBy { id name email }
                    lastUpdatedBy { id name email }
                }
            }
        }""",
        {"wsId": ws_id, "docId": doc_id},
    )
    if "error" in data:
        return None, data["error"]
    doc = data.get("workspace", {}).get("doc")
    return doc, None


def _extract_yjs_metadata(blocks):
    meta = {}
    for key in list(blocks.keys()):
        block = blocks[key]
        if isinstance(block, Y.YMap) and block.get("sys:flavour") == "affine:page":
            items = dict(block.items())
            for k in items:
                if k.startswith("prop:meta:"):
                    meta[k[len("prop:meta:"):]] = str(items[k])
    return meta


def _get_workspace_ids():
    ws_list, err = _list_workspaces()
    if err or not ws_list:
        return []
    return [w["id"] for w in ws_list]


# ── Title Cache (existing) ─────────────────────────────────────

def _fetch_all_titles():
    cache = _load_title_cache()
    ws_ids = _get_workspace_ids()
    if not ws_ids:
        return cache
    s, err = _login()
    if err:
        return cache
    domain = _vget("affine/domain")
    changed = False
    for ws_id in ws_ids:
        pages = _graphql(
            "query ($wsId: String!, $first: Int!) { workspace(id: $wsId) { docs(pagination: {first: $first}) { edges { node { id } } } } }",
            {"wsId": ws_id, "first": 100},
        )
        if "error" in pages:
            continue
        for e in pages.get("workspace", {}).get("docs", {}).get("edges", []):
            doc_id = e["node"]["id"]
            if doc_id in cache["titles"] and cache["titles"][doc_id] is not None:
                continue
            try:
                r = s.get(
                    f"{domain.rstrip('/')}/api/workspaces/{ws_id}/docs/{doc_id}",
                    headers={"x-affine-client-version": "0.25.0", "x-csrf-token": _AFFINE_CSRF or ""},
                    timeout=30,
                )
                if r.status_code != 200:
                    continue
                ydoc, blocks, decode_err = _decode_ydoc(r.content)
                if decode_err or blocks is None:
                    cache["titles"][doc_id] = None
                    changed = True
                    continue
                title = _extract_title(blocks)
                cache["titles"][doc_id] = title
                changed = True
            except requests.RequestException:
                continue
    if changed:
        _save_title_cache(cache)
    return cache


# ── Content Search ─────────────────────────────────────────────

def _search_in_cache(query_text, max_results=10):
    content_cache = _load_content_cache()
    title_cache = _load_title_cache()
    query_lower = query_text.lower()
    results = []

    for doc_id, entry in content_cache.get("contents", {}).items():
        title = entry.get("title", "")
        text = entry.get("text", "")
        score = 0
        if query_lower in title.lower():
            score += 10
        if query_lower in text.lower():
            score += 1
        if score > 0:
            snippet = _make_snippet(text, query_text, 150)
            results.append({
                "id": doc_id,
                "title": title or "(kein Titel)",
                "score": score,
                "snippet": snippet,
            })

    for doc_id, title in title_cache.get("titles", {}).items():
        if title and query_lower in title.lower():
            if not any(r["id"] == doc_id for r in results):
                results.append({
                    "id": doc_id,
                    "title": title,
                    "score": 5,
                    "snippet": "",
                })

    results.sort(key=lambda x: -x["score"])
    return results[:max_results]


def _make_snippet(text, query, context=100):
    idx = text.lower().find(query.lower())
    if idx == -1:
        return text[:200]
    start = max(0, idx - context)
    end = min(len(text), idx + len(query) + context)
    snippet = text[start:end]
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet += "…"
    return snippet


# ── Tool Functions ─────────────────────────────────────────────

def affine_list_workspaces():
    ws_list, err = _list_workspaces()
    if err:
        return f"❌ {err}"
    if not ws_list:
        return "ℹ️ Keine Workspaces gefunden."
    lines = ["📚 **AFFiNE Workspaces:**"]
    for w in ws_list:
        lines.append(f"  `{w['id']}`")
    return "\n".join(lines)


def affine_workspace_info():
    ws_ids = _get_workspace_ids()
    if not ws_ids:
        return "ℹ️ Keine Workspaces gefunden."
    result_parts = []
    for ws_id in ws_ids:
        data = _graphql(
            """query ($id: String!) {
                workspace(id: $id) {
                    id createdAt memberCount role
                    quota { memberLimit memberCount storageQuota usedStorageQuota }
                    docs(pagination: {first: 100}) { totalCount }
                }
            }""",
            {"id": ws_id},
        )
        if "error" in data:
            result_parts.append(f"⚠️ {data['error']}")
            continue
        ws = data.get("workspace", {})
        q = ws.get("quota") or {}
        storage_gb = q.get("storageQuota", 0) / (1024**3) if q.get("storageQuota") else 0
        used_gb = q.get("usedStorageQuota", 0) / (1024**3) if q.get("usedStorageQuota") else 0
        doc_count = ws.get("docs", {}).get("totalCount", 0)
        result_parts.append(
            f"📚 **Workspace** `{ws_id}`\n"
            f"  Rolle: {ws.get('role', '?')}\n"
            f"  Mitglieder: {ws.get('memberCount', '?')}\n"
            f"  Docs: {doc_count}\n"
            f"  Speicher: {used_gb:.1f}GB / {storage_gb:.1f}GB\n"
            f"  Erstellt: {ws.get('createdAt', '?')}"
        )
    return "\n\n".join(result_parts)


def affine_list_pages():
    ws_ids = _get_workspace_ids()
    if not ws_ids:
        return "ℹ️ Keine Workspaces gefunden."
    cache = _fetch_all_titles()
    content_cache = _load_content_cache()
    result_parts = []
    for ws_id in ws_ids:
        pages = _graphql(
            "query ($wsId: String!, $first: Int!) { workspace(id: $wsId) { docs(pagination: {first: $first}) { edges { node { id } } } } }",
            {"wsId": ws_id, "first": 100},
        )
        if "error" in pages:
            result_parts.append(f"  ⚠️ Fehler: {pages['error']}")
            continue
        edges = pages.get("workspace", {}).get("docs", {}).get("edges", [])
        if not edges:
            continue
        for e in edges:
            doc_id = e["node"]["id"]
            title = cache["titles"].get(doc_id)
            cached = "📦" if doc_id in content_cache.get("contents", {}) else ""
            display = f"**{title}**" if title else "(kein Titel)"
            result_parts.append(f"  📄 {cached} {display} (`{doc_id}`)")
    if not result_parts:
        return "ℹ️ Keine Seiten gefunden."
    return "📄 **AFFiNE Seiten:**\n" + "\n".join(result_parts)[:6000]


def affine_search(query_text, max_results=20):
    cache = _fetch_all_titles()
    results = []
    for doc_id, title in cache["titles"].items():
        if title and query_text.lower() in title.lower():
            results.append({"id": doc_id, "title": title})
    if not results:
        return f"🔍 Keine Seiten gefunden für '{query_text}'."
    lines = [f"🔍 **Suchergebnisse für '{query_text}':**"]
    for r in results[:max_results]:
        lines.append(f"  📄 **{r['title']}** (`{r['id']}`)")
    return "\n".join(lines)


def affine_search_content(query_text, max_results=10):
    ws_ids = _get_workspace_ids()
    if not ws_ids:
        return "❌ Keine Workspaces verfügbar."

    title_cache = _fetch_all_titles()

    result_count = 0
    found_ids = set()
    lines = [f"🔍 **Volltext-Suche nach '{query_text}':**"]

    for doc_id, entry in _load_content_cache().get("contents", {}).items():
        title = entry.get("title", "") or title_cache["titles"].get(doc_id, "")
        text = entry.get("text", "")
        if query_text.lower() in title.lower() or query_text.lower() in text.lower():
            snippet = _make_snippet(text, query_text, 120)
            lines.append(f"\n  📄 **{title or doc_id}** (`{doc_id}`)")
            if snippet:
                lines.append(f"    _{snippet}_")
            found_ids.add(doc_id)
            result_count += 1
            if result_count >= max_results:
                lines.append(f"\n  … und weitere (max {max_results} angezeigt)")
                break

    if result_count == 0:
        lines.append("\n  ℹ️ Keine gecachten Inhalte gefunden. Versuche Seiten zu laden…")
        loaded = 0
        for ws_id in ws_ids:
            if result_count >= max_results:
                break
            pages = _graphql(
                "query ($wsId: String!, $first: Int!) { workspace(id: $wsId) { docs(pagination: {first: $first}) { edges { node { id } } } } }",
                {"wsId": ws_id, "first": 100},
            )
            if "error" in pages:
                continue
            for e in pages.get("workspace", {}).get("docs", {}).get("edges", []):
                doc_id = e["node"]["id"]
                if doc_id in found_ids or result_count >= max_results:
                    continue
                entry = _ensure_page_cached(ws_id, doc_id)
                if entry:
                    title = entry.get("title", "") or title_cache["titles"].get(doc_id, "")
                    text = entry.get("text", "")
                    if query_text.lower() in (title + " " + text).lower():
                        snippet = _make_snippet(text, query_text, 120)
                        lines.append(f"\n  📄 **{title or doc_id}** (`{doc_id}`)")
                        if snippet:
                            lines.append(f"    _{snippet}_")
                        found_ids.add(doc_id)
                        result_count += 1
                        loaded += 1

        if result_count == 0:
            return f"🔍 Keine Treffer für '{query_text}' in {loaded} geladenen Seiten."

    return "\n".join(lines)


def affine_read_page(page_id):
    ws_ids = _get_workspace_ids()
    if not ws_ids:
        return "❌ Keine Workspaces verfügbar."

    title_cache = _fetch_all_titles()
    title = title_cache["titles"].get(page_id)
    title_display = f" **{title}**" if title else ""

    for ws_id in ws_ids:
        entry = _ensure_page_cached(ws_id, page_id)
        if entry:
            block_count = entry.get("block_count", "?")
            updated = time.strftime("%d.%m.%Y %H:%M", time.localtime(entry.get("updated_at", 0)))
            meta_lines = []
            meta_lines.append(f"📄 Seite{title_display} (`{page_id}`)")
            meta_lines.append(f"  Blöcke: {block_count} | Stand: {updated}")
            if entry["text"]:
                meta_lines.append(f"\n{entry['text'][:8000]}")
            else:
                meta_lines.append("\n(kein Text-Inhalt)")
            return "\n".join(meta_lines)

    for ws_id in ws_ids:
        yjs_binary, err = _fetch_page_raw(ws_id, page_id)
        if yjs_binary:
            ydoc, blocks, decode_err = _decode_ydoc(yjs_binary)
            if decode_err:
                return f"📄 Seite{title_display} (`{page_id}`) – {len(yjs_binary)} Bytes (Dekodierung: {decode_err})"
            if blocks is None:
                return f"📄 Seite{title_display} (`{page_id}`) – {len(yjs_binary)} Bytes"
            text = _extract_all_text(blocks, max_blocks=100)
            return f"📄 Seite{title_display} (`{page_id}`):\n\n{text[:8000]}"
    return f"❌ Seite `{page_id}` nicht gefunden."


def affine_get_page_metadata(page_id):
    ws_ids = _get_workspace_ids()
    if not ws_ids:
        return "❌ Keine Workspaces verfügbar."

    title_cache = _fetch_all_titles()
    title = title_cache["titles"].get(page_id)
    title_display = f" **{title}**" if title else ""

    for ws_id in ws_ids:
        yjs_binary, err = _fetch_page_raw(ws_id, page_id)
        if yjs_binary:
            ydoc, blocks, decode_err = _decode_ydoc(yjs_binary)
            if decode_err:
                return f"❌ Dekodierung fehlgeschlagen: {decode_err}"
            if blocks is None:
                continue

            yjs_meta = _extract_yjs_metadata(blocks)

            block_count = 0
            flavour_counts = {}
            for key in list(blocks.keys()):
                b = blocks[key]
                if isinstance(b, Y.YMap):
                    block_count += 1
                    f = b.get("sys:flavour", "")
                    if f:
                        flavour_counts[f] = flavour_counts.get(f, 0) + 1

            lines = [f"📄 **Metadaten**{title_display} (`{page_id}`)"]
            if yjs_meta:
                lines.append(f"\n  📅 Erstellt: {yjs_meta.get('createdAt', yjs_meta.get('createdAt', '?'))}")
                lines.append(f"  ✏️ Von: {yjs_meta.get('createdBy', '?')}")
                lines.append(f"  🔄 Zuletzt aktualisiert: {yjs_meta.get('updatedAt', '?')}")
                lines.append(f"  👤 Aktualisiert von: {yjs_meta.get('updatedBy', '?')}")

            doc, gql_err = _fetch_page_metadata_graphql(ws_id, page_id)
            if doc and not gql_err:
                lines.append(f"\n  🏢 Workspace: `{ws_id}`")
                lines.append(f"  📐 Modus: {doc.get('mode', '?')}")
                if doc.get("createdAt"):
                    lines.append(f"  📅 Erstellt (Server): {doc['createdAt']}")
                if doc.get("updatedAt"):
                    lines.append(f"  🔄 Aktualisiert (Server): {doc['updatedAt']}")
                creator = doc.get("createdBy")
                if creator:
                    lines.append(f"  ✏️ Erstellt von: {creator.get('name', creator.get('email', '?'))}")
                updater = doc.get("lastUpdatedBy")
                if updater:
                    lines.append(f"  👤 Zuletzt bearbeitet von: {updater.get('name', updater.get('email', '?'))}")

            lines.append(f"\n  📊 Blöcke gesamt: {block_count}")
            if flavour_counts:
                lines.append("  🏷️ Block-Typen:")
                for f, c in sorted(flavour_counts.items(), key=lambda x: -x[1]):
                    lines.append(f"    {f}: {c}")

            entry = _load_content_cache().get("contents", {}).get(page_id)
            if entry:
                lines.append(f"\n  📦 Gecachet: {time.strftime('%d.%m.%Y %H:%M', time.localtime(entry['updated_at']))}")
                lines.append(f"  📏 Yjs-Größe: {entry['yjs_size']} Bytes")

            return "\n".join(lines)

    return f"❌ Seite `{page_id}` nicht gefunden."


def affine_page_hierarchy(page_id):
    ws_ids = _get_workspace_ids()
    if not ws_ids:
        return "❌ Keine Workspaces verfügbar."

    title_cache = _fetch_all_titles()
    title = title_cache["titles"].get(page_id)
    title_display = f" **{title}**" if title else ""

    for ws_id in ws_ids:
        yjs_binary, err = _fetch_page_raw(ws_id, page_id)
        if yjs_binary:
            ydoc, blocks, decode_err = _decode_ydoc(yjs_binary)
            if decode_err:
                return f"❌ Dekodierung fehlgeschlagen: {decode_err}"
            if blocks is None:
                continue

            page_block_id = None
            for key in list(blocks.keys()):
                b = blocks[key]
                if isinstance(b, Y.YMap) and b.get("sys:flavour") == "affine:page":
                    page_block_id = key
                    break

            if page_block_id is None:
                return f"📄 Seite{title_display} (`{page_id}`)\n\n(keine Seiten-Struktur)"

            page_block = blocks[page_block_id]
            tree = _extract_block_tree(page_block_id, page_block, blocks)
            result = f"🌳 **Seiten-Hierarchie**{title_display} (`{page_id}`)\n" + "\n".join(tree)
            return result

    return f"❌ Seite `{page_id}` nicht gefunden."


# ── Knowledge Base Integration (AFFiNE → chunks.json/embeddings.npy) ──

_INDEXING_STATUS = {"status": "idle", "progress": 0, "total": 0, "errors": []}


def affine_index_status():
    s = _INDEXING_STATUS
    if s["status"] == "idle":
        return "⏳ Indexierung läuft gerade nicht. Starte mit affine_index_all()."
    return (
        f"📊 **AFFiNE Indexierung:**\n"
        f"  Status: {s['status']}\n"
        f"  Fortschritt: {s['progress']}/{s['total']}\n"
        f"  Fehler: {len(s['errors'])}"
    )


def affine_index_all():
    global _INDEXING_STATUS
    _INDEXING_STATUS = {"status": "running", "progress": 0, "total": 0, "errors": []}

    try:
        import numpy as np  # noqa: I001
        from core.config import BASE, _app_lock  # noqa: I001
        from core.embed import embed  # noqa: I001
    except ImportError as e:
        _INDEXING_STATUS["status"] = "error"
        return f"❌ Abhängigkeit fehlt: {e}"

    ws_ids = _get_workspace_ids()
    if not ws_ids:
        _INDEXING_STATUS["status"] = "error"
        return "❌ Keine Workspaces verfügbar."

    chunks_file = BASE / "data" / "chunks.json"
    embs_file = BASE / "data" / "embeddings.npy"

    with _app_lock:
        existing_chunks = []
        existing_embs = np.array([], dtype=np.float32).reshape(0, 0)
        if chunks_file.exists():
            try:
                existing_chunks = json.loads(chunks_file.read_text())
            except (OSError, json.JSONDecodeError):
                existing_chunks = []
        if embs_file.exists():
            try:
                existing_embs = np.load(str(embs_file)).astype(np.float32)
                if existing_embs.ndim == 1:
                    existing_embs = existing_embs.reshape(-1, 1)
            except (OSError, ValueError):
                existing_embs = np.array([], dtype=np.float32).reshape(0, 0)

    existing_titles = {Path(c["source"]).stem for c in existing_chunks if "source" in c}
    all_new_chunks = []
    doc_count = 0

    for ws_id in ws_ids:
        pages = _graphql(
            "query ($wsId: String!, $first: Int!) { workspace(id: $wsId) { docs(pagination: {first: $first}) { edges { node { id } } } } }",
            {"wsId": ws_id, "first": 100},
        )
        if "error" in pages:
            continue
        edges = pages.get("workspace", {}).get("docs", {}).get("edges", [])
        _INDEXING_STATUS["total"] = len(edges)

        for e in edges:
            doc_id = e["node"]["id"]
            _INDEXING_STATUS["progress"] += 1
            _INDEXING_STATUS["current"] = doc_id

            if doc_id in existing_titles:
                continue

            entry = _ensure_page_cached(ws_id, doc_id)
            if not entry:
                continue
            text = entry.get("text", "")
            title = entry.get("title", "") or doc_id
            if not text.strip():
                continue

            chunks = _chunk_text(text, title)
            for ch in chunks:
                ch["source"] = f"affine://{ws_id}/{doc_id}"
                ch["title"] = title
            all_new_chunks.extend(chunks)
            doc_count += 1

    if not all_new_chunks:
        _INDEXING_STATUS["status"] = "idle"
        return "ℹ️ Keine neuen AFFiNE-Dokumente zum Indexieren. Alle sind bereits im Knowledge Base."

    all_texts = [c["text"] for c in all_new_chunks]
    try:
        new_embs = embed(all_texts)
    except Exception as e:
        _INDEXING_STATUS["status"] = "error"
        _INDEXING_STATUS["errors"].append(str(e))
        return f"❌ Fehler beim Embedding: {e}"

    with _app_lock:
        combined_chunks = existing_chunks + all_new_chunks
        if existing_embs.size == 0 or existing_embs.shape[0] == 0:
            combined_embs = new_embs
        elif new_embs.ndim == 2 and new_embs.shape[1] == existing_embs.shape[1]:
            combined_embs = np.vstack([existing_embs, new_embs])
        else:
            combined_embs = new_embs
            combined_chunks = all_new_chunks

        chunks_file.write_text(json.dumps(combined_chunks, indent=2, ensure_ascii=False))
        np.save(str(embs_file), combined_embs.astype(np.float32))

    try:
        from app.helpers import knowledge_base
        knowledge_base._load()
    except ImportError:
        pass

    _INDEXING_STATUS["status"] = "idle"
    return (
        f"✅ **AFFiNE-Indexierung abgeschlossen!**\n"
        f"  {doc_count} neue Dokumente indexiert\n"
        f"  {len(all_new_chunks)} Text-Chunks erstellt\n"
        f"  Knowledge Base aktualisiert: {len(combined_chunks)} Chunks gesamt\n"
        f"  Jetzt via search_documents() durchsuchbar!"
    )


def _chunk_text(text, title="", size=600):
    lines = text.split('\n')
    chunks, buf, buf_len = [], [], 0
    import re
    hs = []
    for line in lines:
        if line.startswith('#'):
            m = re.match(r'^(#+)\s+(.*)', line)
            if m:
                hs = [h for h in hs if h['level'] < len(m.group(1))]
                hs.append({'level': len(m.group(1)), 'text': m.group(2)})
        buf.append(line)
        buf_len += len(line) + 1
        if buf_len >= size:
            chunks.append({'text': '\n'.join(buf), 'headings': list(hs), 'title': title})
            oc = size // 5
            while buf_len > oc and buf:
                p = buf.pop(0)
                buf_len -= len(p) + 1
    if buf:
        chunks.append({'text': '\n'.join(buf), 'headings': list(hs), 'title': title})
    return chunks


# ── Tool Registration ──────────────────────────────────────────

TOOLS = [
    {"type": "function", "function": {"name": "affine_list_workspaces", "description": "List all AFFiNE workspace IDs.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "affine_workspace_info", "description": "Show detailed info about each workspace: member count, role, doc count, storage quota.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "affine_list_pages", "description": "List all pages across all workspaces with their titles. Shows 📦 icons for pages that have cached content available for fast reading.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "affine_search", "description": "Search AFFiNE pages by title. Fast – searches cached titles only.", "parameters": {"type": "object", "properties": {"query_text": {"type": "string", "description": "Search term"}, "max_results": {"type": "integer", "description": "Max results (default 20)"}}, "required": ["query_text"]}}},
    {"type": "function", "function": {"name": "affine_search_content", "description": "Full-text search across all AFFiNE page contents (titles + body text). Returns text snippets with context.", "parameters": {"type": "object", "properties": {"query_text": {"type": "string", "description": "Search term"}, "max_results": {"type": "integer", "description": "Max results (default 10)"}}, "required": ["query_text"]}}},
    {"type": "function", "function": {"name": "affine_read_page", "description": "Read full page content from AFFiNE by page ID. Returns formatted text with headings (#), lists (-), code blocks, and hierarchy preserved.", "parameters": {"type": "object", "properties": {"page_id": {"type": "string", "description": "Page ID"}}, "required": ["page_id"]}}},
    {"type": "function", "function": {"name": "affine_get_page_metadata", "description": "Get detailed metadata for an AFFiNE page: created/updated dates, authors, page mode, block type breakdown, cache status.", "parameters": {"type": "object", "properties": {"page_id": {"type": "string", "description": "Page ID"}}, "required": ["page_id"]}}},
    {"type": "function", "function": {"name": "affine_page_hierarchy", "description": "Show the hierarchical block tree structure of an AFFiNE page. Displays all block types as a tree.", "parameters": {"type": "object", "properties": {"page_id": {"type": "string", "description": "Page ID"}}, "required": ["page_id"]}}},
    {"type": "function", "function": {"name": "affine_index_all", "description": "Index ALL AFFiNE documents into the AI knowledge base (embeddings). After running this, search_documents() will find AFFiNE content alongside Nextcloud docs. Must be called once to enable semantic AFFiNE search.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "affine_index_status", "description": "Show current AFFiNE indexing status.", "parameters": {"type": "object", "properties": {}, "required": []}}},
]

TOOL_MAP = {
    "affine_list_workspaces": affine_list_workspaces,
    "affine_list_pages": affine_list_pages,
    "affine_search": affine_search,
    "affine_search_content": affine_search_content,
    "affine_read_page": affine_read_page,
    "affine_workspace_info": affine_workspace_info,
    "affine_get_page_metadata": affine_get_page_metadata,
    "affine_page_hierarchy": affine_page_hierarchy,
    "affine_index_all": affine_index_all,
    "affine_index_status": affine_index_status,
}

PROMPT_EXTRA = (
    "AFFiNE (Wissensdatenbank – Deine Nr. 1 Wissensquelle):\n"
    "  AFFiNE ist deine **primäre Wissensquelle** mit allen persönlichen Dokumenten, Notizen und\n"
    "  Aufzeichnungen. Wenn der User eine Frage stellt, solltest du AFFiNE IMMER durchsuchen,\n"
    "  bevor du antwortest oder das Internet verwendest!\n"
    "  Tools:\n"
    "  1. **affine_list_workspaces()**: Workspace-IDs auflisten\n"
    "  2. **affine_workspace_info()**: Details zum Workspace\n"
    "  3. **affine_list_pages()**: Alle Seiten mit Titel auflisten\n"
    "  4. **affine_search(query)**: Schnelle Titel-Suche\n"
    "  5. **affine_search_content(query)**: VOLLTEXT-Suche in Seiteninhalten\n"
    "  6. **affine_read_page(page_id)**: Seiteninhalt abrufen\n"
    "  7. **affine_get_page_metadata(page_id)**: Metadaten einer Seite\n"
    "  8. **affine_page_hierarchy(page_id)**: Baumstruktur anzeigen\n"
    "  9. **affine_index_all()**: AFFiNE in den Knowledge Base einlesen (einmalig ausführen!)\n"
    "     Danach findet **search_documents()** automatisch AFFiNE-Inhalte!\n"
    "  10. **affine_index_status()**: Indexierungs-Status prüfen\n"
    "\n"
    "  ⚠️ WICHTIG: Wenn der User nach Informationen fragt, rufe NICHT sofort das Internet auf!\n"
    "  Gehe stattdessen so vor:\n"
    "    1. **affine_search()** oder **affine_search_content()** für Titel/Text-Suche\n"
    "    2. **search_documents()** für semantische Suche im gesamten Knowledge Base\n"
    "    3. **affine_read_page()** um die gefundene Seite vollständig zu lesen\n"
    "    4. Erst DANN web_search() wenn AFFiNE nichts gefunden hat\n"
    "  Nach einmaligem Aufruf von affine_index_all() sind alle AFFiNE-Inhalte auch über\n"
    "  **search_documents()** auffindbar – wie Nextcloud-Dokumente.\n"
    "  Führe affine_index_all() einmal aus, wenn du es noch nicht getan hast!\n"
)
try:
    import y_py as Y  # noqa: N812
except ImportError:
    Y = None
