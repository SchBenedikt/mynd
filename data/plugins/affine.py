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
    data = _graphql("{ workspaces { id role memberCount team owner { id name email } } }")
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


def _fetch_ws_docs(ws_id, limit=500):
    """Fetch documents from a workspace using recentlyUpdatedDocs with pagination.
    Works for both owned and shared (Collaborator) workspaces."""
    all_edges = []
    cursor = None
    has_more = True
    while has_more and len(all_edges) < limit:
        pag = {"first": min(100, limit - len(all_edges))}
        if cursor:
            pag["after"] = cursor
        data = _graphql(
            "query ($wsId: String!, $first: Int!, $after: String) { workspace(id: $wsId) { recentlyUpdatedDocs(pagination: {first: $first, after: $after}) { totalCount pageInfo { hasNextPage endCursor } edges { node { id title } } } } }",
            {"wsId": ws_id, "first": pag["first"], "after": cursor},
        )
        if "error" in data:
            return [], data["error"]
        docs = data.get("workspace", {}).get("recentlyUpdatedDocs", {})
        edges = docs.get("edges", [])
        all_edges.extend(edges)
        page_info = docs.get("pageInfo", {})
        has_more = page_info.get("hasNextPage", False)
        if has_more:
            cursor = page_info.get("endCursor")
    return all_edges, None


def _fetch_ws_doc_count(ws_id):
    """Get doc count, trying recentlyUpdatedDocs first, falling back to docs."""
    data = _graphql(
        "query ($wsId: String!) { workspace(id: $wsId) { recentlyUpdatedDocs(pagination: {first: 1}) { totalCount } docs(pagination: {first: 1}) { totalCount } } }",
        {"wsId": ws_id},
    )
    if "error" in data:
        return 0
    ws = data.get("workspace", {})
    count = ws.get("recentlyUpdatedDocs", {}).get("totalCount")
    if count is not None:
        return count
    return ws.get("docs", {}).get("totalCount", 0)


# ── Title Cache (existing) ─────────────────────────────────────

def _fetch_all_titles():
    cache = _load_title_cache()
    ws_ids = _get_workspace_ids()
    if not ws_ids:
        return cache
    changed = False
    for ws_id in ws_ids:
        edges, err = _fetch_ws_docs(ws_id)
        if err or not edges:
            continue
        for e in edges:
            doc_id = e["node"]["id"]
            title = e["node"].get("title", "")
            if title:
                cache["titles"][doc_id] = title
                changed = True
            elif doc_id not in cache["titles"] or cache["titles"][doc_id] is None:
                # Title not available via GraphQL, fetch raw
                s, lerr = _login()
                if lerr:
                    continue
                domain = _vget("affine/domain")
                try:
                    r = s.get(
                        f"{domain.rstrip('/')}/api/workspaces/{ws_id}/docs/{doc_id}",
                        headers={"x-affine-client-version": "0.25.0", "x-csrf-token": _AFFINE_CSRF or ""},
                        timeout=30,
                    )
                    if r.status_code == 200:
                        ydoc, blocks, decode_err = _decode_ydoc(r.content)
                        if not decode_err and blocks:
                            t = _extract_title(blocks)
                            cache["titles"][doc_id] = t
                            changed = True
                        else:
                            cache["titles"][doc_id] = None
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
        role = w.get("role", "?")
        team = " (Team)" if w.get("team") else ""
        owner = w.get("owner", {})
        owner_name = owner.get("name", "?")
        member_count = w.get("memberCount", "?")
        lines.append(f"  `{w['id']}` — Rolle: {role}{team}, Besitzer: {owner_name}, Mitglieder: {member_count}")
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
                    owner { id name email }
                    quota { memberLimit memberCount storageQuota usedStorageQuota }
                    recentlyUpdatedDocs(pagination: {first: 1}) { totalCount }
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
        doc_count = ws.get("recentlyUpdatedDocs", {}).get("totalCount", 0)
        owner = ws.get("owner", {})
        owner_str = f"{owner.get('name', '?')} ({owner.get('email', '?')})" if owner else "?"
        result_parts.append(
            f"📚 **Workspace** `{ws_id}`\n"
            f"  Rolle: {ws.get('role', '?')}\n"
            f"  Besitzer: {owner_str}\n"
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
        edges, err = _fetch_ws_docs(ws_id)
        if err:
            result_parts.append(f"  ⚠️ Fehler: {err}")
            continue
        if not edges:
            continue
        for e in edges:
            doc_id = e["node"]["id"]
            title = e["node"].get("title") or cache["titles"].get(doc_id)
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
            edges, ferr = _fetch_ws_docs(ws_id, limit=100)
            if ferr or not edges:
                continue
            for e in edges:
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
        from app.config import _app_lock  # noqa: I001
        from core.config import BASE  # noqa: I001
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

    existing_ids = {c["source"] for c in existing_chunks if "source" in c}
    all_new_chunks = []
    doc_count = 0
    total_docs = 0

    for ws_id in ws_ids:
        edges, ferr = _fetch_ws_docs(ws_id, limit=500)
        if ferr or not edges:
            continue
        total_docs += len(edges)
        _INDEXING_STATUS["total"] = total_docs

        for e in edges:
            doc_id = e["node"]["id"]
            _INDEXING_STATUS["progress"] += 1
            _INDEXING_STATUS["current"] = doc_id

            source_key = f"affine://{ws_id}/{doc_id}"
            if source_key in existing_ids:
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
                ch["source"] = source_key
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


# ── Doc CRUD (Create, Update, Delete) ──────────────────────────

def _make_page_yjs_binary(title, markdown):
    """Generate a Yjs binary for a new AFFiNE page with title + markdown content.
    Returns (doc_id, binary, error)."""
    if not Y:
        return None, None, "y-py nicht installiert"
    import re as _re

    from y_py import YArray, YDoc, YMap, encode_state_as_update  # noqa: I001

    doc_id = "mynd-" + str(int(time.time() * 1000))
    ydoc = YDoc()
    blocks = ydoc.get_map("blocks")
    txn = ydoc.begin_transaction()

    page_block = YMap({})
    page_block.set(txn, "sys:flavour", "affine:page")
    page_block.set(txn, "prop:title", title)
    page_block.set(txn, "sys:id", doc_id)
    page_block.set(txn, "sys:version", 1)

    children = YArray({})

    lines = markdown.split('\n')
    i = 0
    block_idx = 0
    while i < len(lines):
        line = lines[i].rstrip()
        i += 1
        if not line:
            continue
        block_id = f"{doc_id}-b{block_idx}"
        block = YMap({})
        block.set(txn, "sys:id", block_id)
        block.set(txn, "prop:text", line)

        h = _re.match(r'^(#{1,6})\s+(.+)$', line)
        if h:
            block.set(txn, "sys:flavour", "affine:heading")
            block.set(txn, "prop:text", h.group(2))
            block.set(txn, "prop:level", len(h.group(1)))
        elif line.startswith('- [x] '):
            block.set(txn, "sys:flavour", "affine:list")
            block.set(txn, "prop:text", line[6:])
            block.set(txn, "prop:type", "todo")
            block.set(txn, "prop:checked", True)
        elif line.startswith('- [ ] '):
            block.set(txn, "sys:flavour", "affine:list")
            block.set(txn, "prop:text", line[6:])
            block.set(txn, "prop:type", "todo")
            block.set(txn, "prop:checked", False)
        elif line.startswith('- ') or line.startswith('* '):
            block.set(txn, "sys:flavour", "affine:list")
            block.set(txn, "prop:text", line[2:])
            block.set(txn, "prop:type", "bulleted")
        elif line.startswith('> '):
            block.set(txn, "sys:flavour", "affine:callout")
            block.set(txn, "prop:text", line[2:])
        elif line.startswith('```'):
            lang = line[3:].strip()
            code_lines = []
            while i < len(lines):
                next_line = lines[i].rstrip()
                i += 1
                if next_line.rstrip() == '```':
                    break
                code_lines.append(next_line)
            block.set(txn, "sys:flavour", "affine:code")
            block.set(txn, "prop:language", lang or "text")
            block.set(txn, "prop:text", '\n'.join(code_lines))
        elif line.strip() == '---':
            block.set(txn, "sys:flavour", "affine:divider")
        else:
            block.set(txn, "sys:flavour", "affine:paragraph")

        blocks.set(txn, block_id, block)
        children.append(txn, block_id)
        block_idx += 1

    page_block.set(txn, "sys:children", children)
    blocks.set(txn, doc_id, page_block)
    txn.commit()

    binary = bytes(encode_state_as_update(ydoc))
    return doc_id, binary, None


def affine_create_page(title, content, workspace_id=""):
    """Create a new page in AFFiNE from plain text/Markdown content.

    Note: AFFiNE v0.27 supports doc creation only via WebSocket sync,
    which is unavailable on this instance. The page binary is generated
    and exported to a local file for manual import via AFFiNE UI.
    """
    ws_ids = _get_workspace_ids()
    if not ws_ids:
        return "❌ Keine Workspaces verfügbar."

    ws_id = workspace_id if workspace_id and workspace_id in [w["id"] for w in (_list_workspaces()[0] or [])] else ws_ids[0]

    doc_id, binary, err = _make_page_yjs_binary(title, content)
    if err:
        return f"❌ {err}"

    export_file = Path(__file__).parent / f"affine_export_{doc_id}.bin"

    export_file.write_bytes(binary)

    from data.plugins.affine import _AFFINE_CSRF, _login, _vget
    s, lerr = _login()
    if not lerr:
        try:
            r = s.put(
                f"{_vget('affine/domain').rstrip('/')}/api/workspaces/{ws_id}/docs/{doc_id}",
                data=binary,
                headers={
                    "Content-Type": "application/octet-stream",
                    "x-affine-client-version": "0.27.2",
                    "x-csrf-token": _AFFINE_CSRF or "",
                },
                timeout=30,
            )
            if r.status_code in (200, 201):
                content_cache = _load_content_cache()
                content_cache["contents"][doc_id] = {
                    "title": title,
                    "text": content,
                    "yjs_size": len(binary),
                    "updated_at": time.time(),
                    "block_count": content.count('\n') + 1,
                }
                _save_content_cache(content_cache)
                return f"✅ Seite **{title}** erstellt (`{doc_id}`) in Workspace `{ws_id}`"
        except Exception:
            pass

    return (
        f"📄 **Seite generiert** – `{doc_id}`\n"
        f"  Titel: {title}\n"
        f"  Export: `{export_file}` ({len(binary)} Bytes)\n\n"
        f"  ⚠️ AFFiNE v0.27 unterstützt keine Doc-Erstellung via REST API.\n"
        f"  Die Yjs-Binärdatei liegt bereit – importiere sie über die AFFiNE-UI:\n"
        f"  1. Öffne AFFiNE → Einstellungen → Import\n"
        f"  2. Wähle `{export_file}`\n"
        f"  3. Oder kopiere den Text manuell in eine neue Seite\n"
        f"  Alternativ: AFFiNE auf v0.28+ aktualisieren für API-Support.\n"
        f"  Nach der Erstellung wird die Seite beim nächsten affine_index_all() erkannt."
    )


def affine_edit_page(page_id, content):
    """Edit/update the content of an existing AFFiNE page.

    Reads the current page, applies changes, and attempts to sync back.
    Falls back to exporting the modified binary for manual import.
    """
    ws_ids = _get_workspace_ids()
    if not ws_ids:
        return "❌ Keine Workspaces verfügbar."

    title_cache = _fetch_all_titles()
    old_title = title_cache["titles"].get(page_id, "") or "(unbenannt)"

    # Read current doc
    ws_id = None
    for wid in ws_ids:
        yjs_binary, ferr = _fetch_page_raw(wid, page_id)
        if yjs_binary:
            ws_id = wid
            break

    if not ws_id:
        return f"❌ Seite `{page_id}` nicht gefunden."

    # Generate updated binary
    new_doc_id, binary, err = _make_page_yjs_binary(old_title, content)
    if err:
        return f"❌ {err}"

    export_file = Path(__file__).parent / f"affine_export_{page_id}.bin"
    export_file.write_bytes(binary)

    s, lerr = _login()
    if not lerr:
        try:
            r = s.put(
                f"{_vget('affine/domain').rstrip('/')}/api/workspaces/{ws_id}/docs/{page_id}",
                data=binary,
                headers={
                    "Content-Type": "application/octet-stream",
                    "x-affine-client-version": "0.27.2",
                    "x-csrf-token": _AFFINE_CSRF or "",
                },
                timeout=30,
            )
            if r.status_code in (200, 201):
                content_cache = _load_content_cache()
                content_cache["contents"][page_id] = {
                    "title": old_title,
                    "text": content,
                    "yjs_size": len(binary),
                    "updated_at": time.time(),
                    "block_count": content.count('\n') + 1,
                }
                _save_content_cache(content_cache)
                return f"✅ Seite **{old_title}** (`{page_id}`) aktualisiert"
        except Exception:
            pass

    return (
        f"📄 **Bearbeitete Seite exportiert** – `{page_id}`\n"
        f"  Titel: {old_title}\n"
        f"  Export: `{export_file}` ({len(binary)} Bytes)\n\n"
        f"  ⚠️ AFFiNE v0.27 unterstützt keine Doc-Änderungen via REST API.\n"
        f"  Die aktualisierte Yjs-Binärdatei liegt bereit:\n"
        f"  Importiere sie über AFFiNE → Einstellungen → Import\n"
        f"  Oder bearbeite den Inhalt direkt in der AFFiNE-UI."
    )


def affine_delete_page(page_id):
    """Delete an AFFiNE page by its ID.

    Note: AFFiNE REST API doesn't support doc deletion. The page
    will be removed from MYND's local cache only.
    """
    ws_ids = _get_workspace_ids()
    if not ws_ids:
        return "❌ Keine Workspaces verfügbar."

    title_cache = _fetch_all_titles()
    title = title_cache["titles"].get(page_id, "") or "(unbenannt)"

    # Remove from local cache
    content_cache = _load_content_cache()
    if page_id in content_cache.get("contents", {}):
        del content_cache["contents"][page_id]
        _save_content_cache(content_cache)

    if page_id in title_cache.get("titles", {}):
        del title_cache["titles"][page_id]
        _save_title_cache(title_cache)

    return (
        f"🗑️ **Seite aus Cache entfernt**: {title} (`{page_id}`)\n\n"
        f"  ⚠️ AFFiNE v0.27 REST API unterstützt keine Löschung.\n"
        f"  Lösche die Seite in AFFiNE über die Web-UI:\n"
        f"  1. Öffne workspace → finde die Seite\n"
        f"  2. Rechtsklick → In Papierkorb verschieben\n"
        f"  3. Oder Permanently delete aus dem Papierkorb\n"
        f"  Nach dem Löschen in AFFiNE wird sie beim nächsten affine_index_all()"
        f" nicht mehr indexiert."
    )


# ── Tool Registration ──────────────────────────────────────────

TOOLS = [
    {"type": "function", "function": {"name": "affine_list_workspaces", "description": "List all AFFiNE workspace IDs with role (Owner/Collaborator) and member count.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "affine_workspace_info", "description": "Show detailed info about each workspace: member count, role, doc count, storage quota, owner.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "affine_list_pages", "description": "List all pages across all workspaces (including shared) with their titles.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "affine_search", "description": "Search AFFiNE pages by title. Fast – searches cached titles only.", "parameters": {"type": "object", "properties": {"query_text": {"type": "string", "description": "Search term"}, "max_results": {"type": "integer", "description": "Max results (default 20)"}}, "required": ["query_text"]}}},
    {"type": "function", "function": {"name": "affine_search_content", "description": "Full-text search across all AFFiNE page contents (titles + body text). Returns text snippets with context.", "parameters": {"type": "object", "properties": {"query_text": {"type": "string", "description": "Search term"}, "max_results": {"type": "integer", "description": "Max results (default 10)"}}, "required": ["query_text"]}}},
    {"type": "function", "function": {"name": "affine_read_page", "description": "Read full page content from AFFiNE by page ID. Returns formatted text with headings (#), lists (-), code blocks, and hierarchy preserved.", "parameters": {"type": "object", "properties": {"page_id": {"type": "string", "description": "Page ID"}}, "required": ["page_id"]}}},
    {"type": "function", "function": {"name": "affine_get_page_metadata", "description": "Get detailed metadata for an AFFiNE page: created/updated dates, authors, page mode, block type breakdown, cache status.", "parameters": {"type": "object", "properties": {"page_id": {"type": "string", "description": "Page ID"}}, "required": ["page_id"]}}},
    {"type": "function", "function": {"name": "affine_page_hierarchy", "description": "Show the hierarchical block tree structure of an AFFiNE page. Displays all block types as a tree.", "parameters": {"type": "object", "properties": {"page_id": {"type": "string", "description": "Page ID"}}, "required": ["page_id"]}}},
    {"type": "function", "function": {"name": "affine_create_page", "description": "Create a new AFFiNE page with title and Markdown content. Note: requires AFFiNE WebSocket sync (v0.28+ recommend). Falls back to binary export.", "parameters": {"type": "object", "properties": {"title": {"type": "string", "description": "Page title"}, "content": {"type": "string", "description": "Markdown content for the page body"}, "workspace_id": {"type": "string", "description": "Optional workspace ID (uses first if empty)"}}, "required": ["title", "content"]}}},
    {"type": "function", "function": {"name": "affine_edit_page", "description": "Edit an existing AFFiNE page by replacing its content. Note: requires AFFiNE v0.28+ for direct API write; falls back to binary export.", "parameters": {"type": "object", "properties": {"page_id": {"type": "string", "description": "Page ID to edit"}, "content": {"type": "string", "description": "New Markdown content"}}, "required": ["page_id", "content"]}}},
    {"type": "function", "function": {"name": "affine_delete_page", "description": "Remove an AFFiNE page from MYND's cache. Note: actual AFFiNE deletion requires AFFiNE Web UI.", "parameters": {"type": "object", "properties": {"page_id": {"type": "string", "description": "Page ID to delete"}}, "required": ["page_id"]}}},
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
    "affine_create_page": affine_create_page,
    "affine_edit_page": affine_edit_page,
    "affine_delete_page": affine_delete_page,
}

PROMPT_EXTRA = (
    "AFFiNE (Wissensdatenbank – Deine Nr. 1 Wissensquelle):\n"
    "  AFFiNE ist deine **primäre Wissensquelle** mit allen persönlichen Dokumenten, Notizen und\n"
    "  Aufzeichnungen. Wenn der User eine Frage stellt, solltest du AFFiNE IMMER durchsuchen,\n"
    "  bevor du antwortest oder das Internet verwendest!\n"
    "  Tools:\n"
    "  1. **affine_list_workspaces()**: Workspace-IDs auflisten (mit Rolle)\n"
    "  2. **affine_workspace_info()**: Details zum Workspace\n"
    "  3. **affine_list_pages()**: Alle Seiten mit Titel auflisten\n"
    "  4. **affine_search(query)**: Schnelle Titel-Suche\n"
    "  5. **affine_search_content(query)**: VOLLTEXT-Suche in Seiteninhalten\n"
    "  6. **affine_read_page(page_id)**: Seiteninhalt abrufen\n"
    "  7. **affine_get_page_metadata(page_id)**: Metadaten einer Seite\n"
    "  8. **affine_page_hierarchy(page_id)**: Baumstruktur anzeigen\n"
    "  9. **affine_create_page(title, content)**: Neue Seite anlegen\n"
    "  10. **affine_edit_page(page_id, content)**: Seite bearbeiten\n"
    "  11. **affine_delete_page(page_id)**: Seite aus Cache entfernen\n"
    "  12. **affine_index_all()**: AFFiNE in den Knowledge Base einlesen (einmalig ausführen!)\n"
    "      Danach findet **search_documents()** automatisch AFFiNE-Inhalte!\n"
    "  13. **affine_index_status()**: Indexierungs-Status prüfen\n"
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
