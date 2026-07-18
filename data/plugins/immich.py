import json
from pathlib import Path

import requests

from core.vault import load_vault

VAULT_FILE = Path(__file__).resolve().parents[1] / 'vault.json'
ENDPOINTS_FILE = Path(__file__).resolve().parents[1] / 'immich_endpoints.json'


def _vault():
    return load_vault(VAULT_FILE)


def _v(key):
    v = _vault()
    if key in v:
        return v.get(key, "")
    parts = key.split('/')
    for p in parts:
        if isinstance(v, dict):
            v = v.get(p)
        else:
            return ''
    return v if isinstance(v, str) else ''


def _base():
    url = _v('immich/url')
    if not url:
        return None, '❌ Immich URL fehlt (vault: immich/url)'
    return url.rstrip('/') + '/api', None


def _headers():
    key = _v('immich/api_key')
    if not key:
        return None, '❌ Immich API-Key fehlt (vault: immich/api_key)'
    return {'x-api-key': key, 'Accept': 'application/json'}, None


def _load_endpoints():
    if not ENDPOINTS_FILE.exists():
        return []
    return json.loads(ENDPOINTS_FILE.read_text())


_ENDPOINT_CACHE = None


def _get_endpoint_list():
    global _ENDPOINT_CACHE
    if _ENDPOINT_CACHE is None:
        _ENDPOINT_CACHE = _load_endpoints()
    return _ENDPOINT_CACHE


def _endpoint_safe(path, method):
    allowed = _get_endpoint_list()
    path = path.split('?')[0]
    for ep in allowed:
        if ep['method'] != method.upper():
            continue
        ep_parts = ep['path'].strip('/').split('/')
        path_parts = path.strip('/').split('/')
        if len(ep_parts) != len(path_parts):
            continue
        if all(
            ep_p.startswith('{') or ep_p == p_p
            for ep_p, p_p in zip(ep_parts, path_parts)
        ):
            return True
    return False


def immich_api_request(endpoint, method='GET', params=None, body=None):
    try:
        base, err = _base()
        if err:
            return err
        h, err = _headers()
        if err:
            return err
        method = method.upper()
        if not _endpoint_safe(endpoint, method):
            return f'❌ Endpoint nicht erlaubt: {method} {endpoint}'
        full_url = f'{base}{endpoint}'
        kwargs = {'headers': h, 'timeout': 30}
        if params:
            kwargs['params'] = params
        if body and method in ('POST', 'PUT', 'PATCH'):
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                except json.JSONDecodeError:
                    return f'❌ body ist kein gültiges JSON: {body[:200]}'
            kwargs['json'] = body
        try:
            r = requests.request(method, full_url, **kwargs)
        except requests.exceptions.Timeout:
            return '❌ Timeout (30s)'
        except requests.exceptions.ConnectionError:
            return '❌ Verbindungsfehler'
        if r.status_code == 204:
            return '✅ Erfolg (204)'
        if 200 <= r.status_code < 300:
            try:
                return json.dumps(r.json(), ensure_ascii=False, indent=2)[:8000]
            except Exception:
                return (r.text or '')[:8000]
        try:
            detail = r.json().get('message', r.json().get('error', r.text[:500]))
        except Exception:
            detail = r.text[:500]
        return f'❌ Status {r.status_code}: {detail}'
    except Exception as e:
        return f'❌ {e}'


def _search_metadata(search_body, size):
    base, err = _base()
    if err:
        return None, err
    h, err = _headers()
    if err:
        return None, err
    search_body['size'] = int(size)
    r = requests.post(f'{base}/search/metadata', json=search_body, headers=h, timeout=20)
    if r.status_code != 200:
        return None, f'❌ Status {r.status_code}'
    return r.json(), None


def _search_smart(search_body, size):
    base, err = _base()
    if err:
        return None, err
    h, err = _headers()
    if err:
        return None, err
    search_body['size'] = int(size)
    r = requests.post(f'{base}/search/smart', json=search_body, headers=h, timeout=20)
    if r.status_code != 200:
        return None, f'❌ Status {r.status_code}'
    return r.json(), None


def _format_asset(a):
    aid = a.get('id', '')
    label = a.get('originalFileName', a.get('id', '?'))
    dt = (a.get('fileCreatedAt') or '')[:19].replace('T', ' ')
    w = a.get('width') or '?'
    hh = a.get('height') or '?'
    img = a.get('type', '') == 'IMAGE'
    thumb_url = f'/api/immich/thumbnail/{aid}' if aid else ''
    orig_url = f'/api/immich/original/{aid}' if aid else ''
    if thumb_url and img:
        alt = f'{label} ({w}x{hh}) {dt}'
        return f'[![{alt}]({thumb_url})]({orig_url})'
    return f'• {label}  ({w}x{hh})  {dt}'


def immich_search_photos(query='', person='', date_from='', date_to='', page=1, size=20, smart=False):
    try:
        page, size = int(page), int(size)
        use_smart = smart or (query and not person)
        if person:
            base, err = _base()
            if err:
                return err
            h, err = _headers()
            if err:
                return err
            rp = requests.get(f'{base}/search/person', params={'name': person}, headers=h, timeout=10)
            if rp.status_code != 200:
                return f'❌ Person-Suche fehlgeschlagen (Status {rp.status_code})'
            people = rp.json()
            pids = [p['id'] for p in people if p.get('name', '').lower() == person.lower()]
            if not pids:
                return f'❌ Person "{person}" nicht gefunden'
            body = {'page': page, 'personIds': pids, 'size': size}
            if date_from:
                body['createdAfter'] = f'{date_from}T00:00:00.000Z'
                body['createdBefore'] = f'{date_to or date_from}T23:59:59.999Z'
            if use_smart and query:
                body['query'] = query
                data, err = _search_smart(body, size)
            else:
                data, err = _search_metadata(body, max(size, 50))
        elif use_smart:
            body = {'page': page, 'size': size, 'query': query}
            if date_from:
                body['createdAfter'] = f'{date_from}T00:00:00.000Z'
                body['createdBefore'] = f'{date_to or date_from}T23:59:59.999Z'
            data, err = _search_smart(body, size)
        elif query or date_from:
            body = {'page': page}
            if query:
                body['query'] = query
            if date_from:
                body['createdAfter'] = f'{date_from}T00:00:00.000Z'
                body['createdBefore'] = f'{date_to or date_from}T23:59:59.999Z'
            data, err = _search_metadata(body, size)
        else:
            base, err = _base()
            if err:
                return err
            h, err = _headers()
            if err:
                return err
            r = requests.post(f'{base}/search/random', json={'limit': 250}, headers=h, timeout=15)
            if r.status_code != 200:
                return f'❌ Status {r.status_code}'
            items = r.json()[:size]
            if not items:
                return '(keine Ergebnisse)'
            lines = [_format_asset(a) for a in items]
            header = f'🔍 {len(items)} zufällige Fotos' if len(items) > 1 else '🔍 Zufallsfoto'
            return header + '\n' + '\n'.join(lines)

        if err:
            return err
        items = data.get('assets', {}).get('items', data.get('items', []))
        if not items:
            return '(keine Ergebnisse)'
        lines = [_format_asset(a) for a in items]
        return '\n'.join(lines) if lines else '(keine Ergebnisse)'
    except Exception as e:
        return f'❌ {e}'


def immich_list_albums():
    try:
        base, err = _base()
        if err:
            return err
        h, err = _headers()
        if err:
            return err
        r = requests.get(f'{base}/albums', headers=h, timeout=15)
        if r.status_code != 200:
            return f'❌ Status {r.status_code}'
        albums = r.json()
        if not albums:
            return '(keine Alben)'
        lines = [f'  • {a.get("albumName", "?")} ({a.get("assetCount", 0)} Fotos, ID: {a.get("id", "?")})' for a in albums]
        return '\n'.join(lines)
    except Exception as e:
        return f'❌ {e}'


def immich_get_album_photos(album_id, page=1, size=50):
    try:
        page, size = int(page), int(size)
        body = {'page': page, 'size': size, 'albumId': album_id}
        data, err = _search_metadata(body, size)
        if err:
            return err
        items = data.get('assets', {}).get('items', data.get('items', []))
        if not items:
            return '(keine Fotos im Album)'
        lines = []
        total = data.get('assets', {}).get('total', 0)
        lines.append(f'📷 Album ({total} Fotos, zeige {len(items)}):')
        for a in items:
            lines.append(_format_asset(a))
        return '\n'.join(lines)
    except Exception as e:
        return f'❌ {e}'


def immich_list_people():
    try:
        base, err = _base()
        if err:
            return err
        h, err = _headers()
        if err:
            return err
        r = requests.get(f'{base}/people', params={'size': 500}, headers=h, timeout=15)
        if r.status_code != 200:
            return f'❌ Status {r.status_code}'
        data = r.json()
        people = data.get('people', [])
        if not people:
            return '(keine Personen erkannt)'
        lines = [f'  • {p.get("name", "?")}' for p in people[:50]]
        total = data.get('total', len(people))
        if total > 50:
            lines.append(f'  ... und {total - 50} weitere')
        return '\n'.join(lines)
    except Exception as e:
        return f'❌ {e}'


def immich_get_server_stats():
    try:
        base, err = _base()
        if err:
            return err
        h, err = _headers()
        if err:
            return err
        r = requests.get(f'{base}/server/statistics', headers=h, timeout=15)
        info = {}
        if r.status_code == 200:
            info = r.json()
        about = requests.get(f'{base}/server/about', headers=h, timeout=10)
        version = ''
        if about.status_code == 200:
            d = about.json()
            v = d.get('version', {})
            if isinstance(v, dict):
                version = f'{v.get("major", "?")}.{v.get("minor", "?")}.{v.get("patch", "?")}'
            else:
                version = str(v).lstrip('v')
        lines = []
        if version:
            lines.append(f'Version: {version}')
        if info:
            photos = info.get('photos', info.get('images', 0))
            videos = info.get('videos', 0)
            total = photos + videos
            usage = info.get('usage', 0)
            if photos or videos:
                lines.append(f'Fotos: {photos} · Videos: {videos} · Gesamt: {total}')
            if usage:
                lines.append(f'Speicher: {_fmt_bytes(usage * 1024 * 1024)}')
        return '\n'.join(lines) if lines else '❌ Keine Daten'
    except Exception as e:
        return f'❌ {e}'


def _fmt_bytes(b):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if b < 1024:
            return f'{b:.1f} {unit}'
        b /= 1024
    return f'{b:.1f} PB'


PLUGIN_NAME = "immich"
PLUGIN_DESC = "Immich Foto- und Medienverwaltung – 270+ API-Endpoints per immich_api_request"

_HINT = (
    'Nutze immich_api_request() für ALLE Endpoints, die keine spezielle Funktion haben. '
    'Erlaubte Endpoints: /server/config, /server/statistics, /search/smart, /stacks, /tags, /duplicates, '
    '/faces, /albums/statistics, /shared-links, /users/me, /libraries, /memories, /map/markers, '
    '/notifications, /partners, /workflows, /jobs, /system-config, /view/folder, /sessions, /activities, '
    '/assets/{id}/metadata, /assets/{id}/ocr, /download/info, /sync, /trash, /faces, /people/{id}, '
    '/search/cities, /search/explore, /search/places, /search/random, /search/suggestions, '
    '/timeline/bucket, /timeline/buckets, etc. (270+ Endpoints in immich_endpoints.json)'
)

TOOLS = [
    {"type": "function", "function": {
        "name": "immich_api_request",
        "description": "Generischer Immich-API-Aufruf. Nutze DAS für alle Endpoints, die keine spezielle Funktion haben. " + _HINT,
        "parameters": {"type": "object", "properties": {
            "endpoint": {"type": "string", "description": "API-Pfad wie /server/config, /albums, /search/smart, /tags, /stacks, /faces?assetId=... etc."},
            "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"], "default": "GET"},
            "params": {"type": "object", "description": "Query-Parameter (optional)"},
            "body": {"type": "object", "description": "JSON-Body für POST/PUT/PATCH (optional)"}
        }, "required": ["endpoint"]}
    }},
    {"type": "function", "function": {
        "name": "immich_search_photos",
        "description": "Durchsuche Immich-Fotos nach Text, Person oder Datum. Wenn nur date_from: Fotos von einem bestimmten Datum. Wenn nur query: Text-Suche. Wenn nur person: Fotos einer Person. Ohne Parameter: Zufällige Fotos.",  # noqa: E501
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Suchbegriff (optional)"},
            "person": {"type": "string", "description": "Personenname (optional, z.B. 'Vinzenz Schächner')"},
            "date_from": {"type": "string", "description": "Datum von im Format YYYY-MM-DD (optional, z.B. '2026-07-07')"},
            "date_to": {"type": "string", "description": "Datum bis im Format YYYY-MM-DD (optional, z.B. '2026-07-07')"},
            "page": {"type": "integer", "default": 1},
            "size": {"type": "integer", "default": 20}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "immich_list_albums",
        "description": "Liste alle Alben in Immich mit Foto-Anzahl und ID.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "immich_get_album_photos",
        "description": "Liste Fotos in einem Immich-Album. Album-ID aus immich_list_albums.",
        "parameters": {"type": "object", "properties": {
            "album_id": {"type": "string", "description": "Album-ID"},
            "page": {"type": "integer", "default": 1, "description": "Seite (optional)"},
            "size": {"type": "integer", "default": 50, "description": "Fotos pro Seite (optional)"}
        }, "required": ["album_id"]}
    }},
    {"type": "function", "function": {
        "name": "immich_list_people",
        "description": "Liste alle erkannten Personen in Immich.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "immich_get_server_stats",
        "description": "Zeige Immich-Server-Statistiken (Version, Foto/Video-Anzahl, Speicher).",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "immich_upload_photo",
        "description": "Lade ein Foto von einer URL in Immich hoch (z.B. von einer Webseite, aus der Zwischenablage).",
        "parameters": {"type": "object", "properties": {
            "image_url": {"type": "string", "description": "URL des Bildes (öffentlich erreichbar)"},
            "album_id": {"type": "string", "description": "Optional: Album-ID, in das das Bild hochgeladen werden soll"},
            "description": {"type": "string", "description": "Optionale Beschreibung zum Bild"}
        }, "required": ["image_url"]}
    }},
    {"type": "function", "function": {
        "name": "immich_create_album",
        "description": "Erstelle ein neues Album in Immich (z.B. für Urlaub, Events).",
        "parameters": {"type": "object", "properties": {
            "title": {"type": "string", "description": "Album-Titel"},
            "description": {"type": "string", "description": "Optionale Beschreibung"}
        }, "required": ["title"]}
    }},
    {"type": "function", "function": {
        "name": "immich_delete_album",
        "description": "Lösche ein Album in Immich.",
        "parameters": {"type": "object", "properties": {
            "album_id": {"type": "string", "description": "Album-ID"}
        }, "required": ["album_id"]}
    }},
    {"type": "function", "function": {
        "name": "immich_add_photos_to_album",
        "description": "Füge Fotos zu einem Album hinzu.",
        "parameters": {"type": "object", "properties": {
            "album_id": {"type": "string", "description": "Album-ID"},
            "asset_ids": {"type": "string", "description": "Komma-getrennte Liste von Asset-IDs"}
        }, "required": ["album_id", "asset_ids"]}
    }},
    {"type": "function", "function": {
        "name": "immich_remove_photos_from_album",
        "description": "Entferne Fotos aus einem Album.",
        "parameters": {"type": "object", "properties": {
            "album_id": {"type": "string", "description": "Album-ID"},
            "asset_ids": {"type": "string", "description": "Komma-getrennte Liste von Asset-IDs"}
        }, "required": ["album_id", "asset_ids"]}
    }},
    {"type": "function", "function": {
        "name": "immich_list_tags",
        "description": "Liste alle Tags in Immich auf.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "immich_get_tag_photos",
        "description": "Hole Fotos mit einem bestimmten Tag.",
        "parameters": {"type": "object", "properties": {
            "tag_id": {"type": "string", "description": "Tag-ID aus immich_list_tags"}
        }, "required": ["tag_id"]}
    }},
    {"type": "function", "function": {
        "name": "immich_list_shared_links",
        "description": "Liste alle geteilten Links in Immich auf.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "immich_create_shared_link",
        "description": "Erstelle einen geteilten Link für ein Foto oder Album.",
        "parameters": {"type": "object", "properties": {
            "type": {"type": "string", "enum": ["INDIVIDUAL", "ALBUM"], "description": "INDIVIDUAL für einzelnes Foto, ALBUM für Album"},
            "id": {"type": "string", "description": "Asset-ID oder Album-ID"},
            "description": {"type": "string", "description": "Optionale Beschreibung"}
        }, "required": ["type", "id"]}
    }},
    {"type": "function", "function": {
        "name": "immich_list_duplicates",
        "description": "Liste doppelte Fotos in Immich auf.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "immich_get_memories",
        "description": "Hole Erinnerungen/On-This-Day von Immich.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "immich_get_map_markers",
        "description": "Hole Geo-Marker für alle Fotos mit GPS-Koordinaten.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "immich_archive_asset",
        "description": "Archiviere ein Foto (entferne es aus der Hauptansicht).",
        "parameters": {"type": "object", "properties": {
            "asset_id": {"type": "string", "description": "Asset-ID"}
        }, "required": ["asset_id"]}
    }},
    {"type": "function", "function": {
        "name": "immich_trash_assets",
        "description": "Verschiebe Fotos in den Papierkorb.",
        "parameters": {"type": "object", "properties": {
            "asset_ids": {"type": "string", "description": "Komma-getrennte Liste von Asset-IDs"}
        }, "required": ["asset_ids"]}
    }},
    {"type": "function", "function": {
        "name": "immich_empty_trash",
        "description": "Leere den Papierkorb endgültig.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
]

def immich_upload_photo(image_url, album_id="", description=""):
    """Lade ein Foto von einer URL in Immich hoch."""
    try:
        base, err = _base()
        if err:
            return err
        h, err = _headers()
        if err:
            return err
        # Download image
        ir = requests.get(image_url, timeout=30)
        if ir.status_code != 200:
            return f"❌ Bild konnte nicht von {image_url} geladen werden (Status {ir.status_code})"
        content_type = ir.headers.get("Content-Type", "image/jpeg")
        ext = "jpg"
        if "png" in content_type:
            ext = "png"
        elif "webp" in content_type:
            ext = "webp"
        elif "gif" in content_type:
            ext = "gif"
        data = ir.content
        # Generate filename
        from datetime import datetime
        fname = f"chat_upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
        # Upload via Immich API (multipart)
        files = {
            "assetData": (fname, data, content_type),
        }
        params = {}
        if album_id:
            params["albumId"] = album_id
        up_h = {**h, "Accept": "application/json"}
        r = requests.post(f"{base}/assets", headers=up_h, params=params, files=files, timeout=60)
        if r.status_code in (200, 201):
            result = r.json()
            aid = result.get("id", result.get("assetId", ""))
            dup = " (bereits vorhanden)" if result.get("duplicate") else ""
            msg = f"✅ Foto hochgeladen: {fname}{dup}"
            if aid:
                msg += f"\n🔗 {base.replace('/api', '/')}photos/{aid}"
            return msg
        return f"❌ Upload fehlgeschlagen (Status {r.status_code}): {r.text[:200]}"
    except Exception as e:
        return f"❌ {e}"


def immich_create_album(title, description=""):
    """Erstelle ein neues Album in Immich."""
    try:
        base, err = _base()
        if err:
            return err
        h, err = _headers()
        if err:
            return err
        body = {"albumName": title}
        if description:
            body["description"] = description
        r = requests.post(f"{base}/albums", json=body, headers=h, timeout=15)
        if r.status_code in (200, 201):
            result = r.json()
            aid = result.get("id", "")
            return f"✅ Album **{title}** erstellt (ID: `{aid}`)"
        return f"❌ Album-Erstellung fehlgeschlagen (Status {r.status_code}): {r.text[:200]}"
    except Exception as e:
        return f"❌ {e}"


def immich_delete_album(album_id):
    """Lösche ein Album."""
    try:
        base, err = _base()
        if err: return err
        h, err = _headers()
        if err: return err
        r = requests.delete(f"{base}/albums/{album_id}", headers=h, timeout=15)
        if r.status_code in (200, 204):
            return f"✅ Album `{album_id}` gelöscht."
        return f"❌ Fehler (Status {r.status_code}): {r.text[:200]}"
    except Exception as e:
        return f"❌ {e}"


def immich_add_photos_to_album(album_id, asset_ids):
    """Füge Fotos zu einem Album hinzu."""
    try:
        base, err = _base()
        if err: return err
        h, err = _headers()
        if err: return err
        ids = [a.strip() for a in asset_ids.split(",")]
        r = requests.put(f"{base}/albums/{album_id}/assets",
                         json={"ids": ids}, headers=h, timeout=30)
        if r.status_code in (200, 204):
            result = r.json() if r.text else {}
            count = len(ids)
            return f"✅ {count} Fotos zu Album hinzugefügt."
        return f"❌ Fehler (Status {r.status_code}): {r.text[:200]}"
    except Exception as e:
        return f"❌ {e}"


def immich_remove_photos_from_album(album_id, asset_ids):
    """Entferne Fotos aus einem Album."""
    try:
        base, err = _base()
        if err: return err
        h, err = _headers()
        if err: return err
        ids = [a.strip() for a in asset_ids.split(",")]
        r = requests.delete(f"{base}/albums/{album_id}/assets",
                            json={"ids": ids}, headers=h, timeout=30)
        if r.status_code in (200, 204):
            return f"✅ Fotos aus Album entfernt."
        return f"❌ Fehler (Status {r.status_code}): {r.text[:200]}"
    except Exception as e:
        return f"❌ {e}"


def immich_list_tags():
    """Liste alle Tags auf."""
    try:
        base, err = _base()
        if err: return err
        h, err = _headers()
        if err: return err
        r = requests.get(f"{base}/tags", headers=h, timeout=15)
        if r.status_code == 200:
            tags = r.json()
            if not tags:
                return "📭 Keine Tags vorhanden."
            lines = ["🏷️ **Tags**"]
            for t in tags:
                name = t.get("name", "?")
                tid = t.get("id", "")
                count = t.get("value", t.get("assetCount", 0))
                lines.append(f"  • **{name}** (ID: `{tid}`, {count} Fotos)")
            return "\n".join(lines)
        return f"❌ Status {r.status_code}"
    except Exception as e:
        return f"❌ {e}"


def immich_get_tag_photos(tag_id):
    """Hole Fotos mit einem bestimmten Tag."""
    try:
        base, err = _base()
        if err: return err
        h, err = _headers()
        if err: return err
        r = requests.get(f"{base}/tags/{tag_id}/assets", headers=h, timeout=15)
        if r.status_code == 200:
            assets = r.json()
            if not assets:
                return "(keine Fotos mit diesem Tag)"
            lines = [_format_asset(a) for a in assets[:50]]
            return "\n".join(lines)
        return f"❌ Status {r.status_code}"
    except Exception as e:
        return f"❌ {e}"


def immich_list_shared_links():
    """Liste alle geteilten Links."""
    try:
        base, err = _base()
        if err: return err
        h, err = _headers()
        if err: return err
        r = requests.get(f"{base}/shared-links", headers=h, timeout=15)
        if r.status_code == 200:
            links = r.json()
            if not links:
                return "📭 Keine geteilten Links."
            lines = ["🔗 **Geteilte Links**"]
            for l in links:
                key = l.get("key", "")
                link_type = l.get("type", "?")
                desc = l.get("description", "")
                expires = l.get("expiresAt", "kein Ablauf")
                lines.append(f"  • `{key}` ({link_type}) - {desc} - Ablauf: {expires}")
            return "\n".join(lines)
        return f"❌ Status {r.status_code}"
    except Exception as e:
        return f"❌ {e}"


def immich_create_shared_link(type, id, description=""):
    """Erstelle einen geteilten Link."""
    try:
        base, err = _base()
        if err: return err
        h, err = _headers()
        if err: return err
        body = {"type": type, "assetIds": [id]} if type == "INDIVIDUAL" else {"type": type, "albumId": id}
        if description:
            body["description"] = description
        r = requests.post(f"{base}/shared-links", json=body, headers=h, timeout=15)
        if r.status_code in (200, 201):
            result = r.json()
            key = result.get("key", "")
            url = result.get("link", f"{base.replace('/api', '/share')}/{key}")
            return f"✅ Geteilter Link erstellt: {url}"
        return f"❌ Status {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return f"❌ {e}"


def immich_list_duplicates():
    """Liste doppelte Fotos."""
    try:
        base, err = _base()
        if err: return err
        h, err = _headers()
        if err: return err
        r = requests.get(f"{base}/duplicates", headers=h, timeout=15)
        if r.status_code == 200:
            dups = r.json()
            if not dups:
                return "✅ Keine Duplikate gefunden."
            lines = [f"📸 **{len(dups)} Duplikat-Gruppen**"]
            for d in dups[:20]:
                assets = d.get("assets", [])
                ids = ", ".join(a.get("id", "?") for a in assets[:3])
                lines.append(f"  • {d.get('assetId', '?')} -> {ids}")
            return "\n".join(lines)
        return f"❌ Status {r.status_code}"
    except Exception as e:
        return f"❌ {e}"


def immich_get_memories():
    """Hole Erinnerungen."""
    try:
        base, err = _base()
        if err: return err
        h, err = _headers()
        if err: return err
        r = requests.get(f"{base}/memories", headers=h, timeout=15)
        if r.status_code == 200:
            memories = r.json()
            if isinstance(memories, dict):
                memories = memories.get("memories", memories.get("items", []))
            if not memories:
                return "📭 Keine Erinnerungen für heute."
            lines = ["📅 **Erinnerungen**"]
            for m in memories[:10]:
                title = m.get("title", "Erinnerung")
                dt = m.get("createdAt", "")[:10]
                lines.append(f"  • **{title}** ({dt})")
            return "\n".join(lines)
        return f"❌ Status {r.status_code}"
    except Exception as e:
        return f"❌ {e}"


def immich_get_map_markers():
    """Hole Geo-Marker."""
    try:
        base, err = _base()
        if err: return err
        h, err = _headers()
        if err: return err
        r = requests.get(f"{base}/map/markers", params={"fileCreatedAfter": "2020-01-01"}, headers=h, timeout=15)
        if r.status_code == 200:
            markers = r.json()
            if not markers:
                return "📭 Keine Fotos mit GPS-Koordinaten."
            lines = [f"📍 **{len(markers)} Geo-Marker**"]
            for m in markers[:30]:
                lat = m.get("lat", m.get("latitude", "?"))
                lon = m.get("lon", m.get("longitude", "?"))
                count = m.get("count", 1)
                city = m.get("city", "")
                label = f" in {city}" if city else ""
                lines.append(f"  • ({lat}, {lon}){label} - {count} Fotos")
            return "\n".join(lines)
        return f"❌ Status {r.status_code}"
    except Exception as e:
        return f"❌ {e}"


def immich_archive_asset(asset_id):
    """Archiviere ein Foto."""
    try:
        base, err = _base()
        if err: return err
        h, err = _headers()
        if err: return err
        r = requests.put(f"{base}/assets/{asset_id}/archive", headers=h, timeout=15)
        if r.status_code in (200, 204):
            return f"✅ Asset `{asset_id}` archiviert."
        return f"❌ Status {r.status_code}"
    except Exception as e:
        return f"❌ {e}"


def immich_trash_assets(asset_ids):
    """Verschiebe Fotos in den Papierkorb."""
    try:
        base, err = _base()
        if err: return err
        h, err = _headers()
        if err: return err
        ids = [a.strip() for a in asset_ids.split(",")]
        r = requests.post(f"{base}/trash/assets", json={"ids": ids}, headers=h, timeout=15)
        if r.status_code in (200, 204):
            return f"✅ {len(ids)} Fotos in den Papierkorb verschoben."
        return f"❌ Status {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return f"❌ {e}"


def immich_empty_trash():
    """Leere den Papierkorb."""
    try:
        base, err = _base()
        if err: return err
        h, err = _headers()
        if err: return err
        r = requests.post(f"{base}/trash/empty", headers=h, timeout=30)
        if r.status_code in (200, 204):
            return "✅ Papierkorb geleert."
        return f"❌ Status {r.status_code}"
    except Exception as e:
        return f"❌ {e}"


TOOL_MAP = {
    'immich_api_request': immich_api_request,
    'immich_search_photos': immich_search_photos,
    'immich_list_albums': immich_list_albums,
    'immich_get_album_photos': immich_get_album_photos,
    'immich_list_people': immich_list_people,
    'immich_get_server_stats': immich_get_server_stats,
    'immich_upload_photo': immich_upload_photo,
    'immich_create_album': immich_create_album,
    'immich_delete_album': immich_delete_album,
    'immich_add_photos_to_album': immich_add_photos_to_album,
    'immich_remove_photos_from_album': immich_remove_photos_from_album,
    'immich_list_tags': immich_list_tags,
    'immich_get_tag_photos': immich_get_tag_photos,
    'immich_list_shared_links': immich_list_shared_links,
    'immich_create_shared_link': immich_create_shared_link,
    'immich_list_duplicates': immich_list_duplicates,
    'immich_get_memories': immich_get_memories,
    'immich_get_map_markers': immich_get_map_markers,
    'immich_archive_asset': immich_archive_asset,
    'immich_trash_assets': immich_trash_assets,
    'immich_empty_trash': immich_empty_trash,
}

PROMPT_EXTRA = (
    'IMMICH (Komplett-Zugriff per immich_api_request):\n'
    '  - immich_search_photos(person="Vorname Nachname", size=50): Fotos einer erkannten Person (mit Thumbnails)\n'
    '  - immich_search_photos(query="..."): Textsuche nach Metadaten (Dateiname, Beschreibung)\n'
    '  - immich_search_photos(query="Hund", smart=True): KI-Suche nach Objekten/Konzepten (Hunde, Autos, Strand, ...)\n'
    '  - immich_search_photos(date_from="2026-07-07", date_to="2026-07-07"): Fotos von einem bestimmten Datum\n'
    '  - immich_search_photos(date_from="2026-07-01", date_to="2026-07-07"): Fotos eines Datumsbereichs\n'
    '  - immich_search_photos(person="Vinzenz", date_from="2026-06-30", date_to="2026-07-07"): Fotos einer Person in einem Zeitraum\n'
    '  - immich_search_photos(): Zufällige Fotos anzeigen (keine Parameter = random)\n'
    '  - immich_list_albums / immich_get_album_photos(album_id, size=50) / immich_list_people / immich_get_server_stats\n'
    '  - immich_upload_photo(image_url, album_id="", description=""): Foto von URL hochladen\n'
    '  - immich_create_album(title, description=""): Neues Album erstellen\n'
    '  - immich_delete_album(album_id): Album löschen\n'
    '  - immich_add_photos_to_album(album_id, asset_ids): Fotos zu Album hinzufügen\n'
    '  - immich_remove_photos_from_album(album_id, asset_ids): Fotos aus Album entfernen\n'
    '  - immich_list_tags(): Tags auflisten\n'
    '  - immich_get_tag_photos(tag_id): Fotos eines Tags abrufen\n'
    '  - immich_list_shared_links(): Geteilte Links auflisten\n'
    '  - immich_create_shared_link(type, id, description=""): Geteilten Link erstellen\n'
    '  - immich_list_duplicates(): Doppelte Fotos anzeigen\n'
    '  - immich_get_memories(): Erinnerungen abrufen\n'
    '  - immich_get_map_markers(): Fotos mit GPS-Koordinaten anzeigen\n'
    '  - immich_archive_asset(asset_id): Foto archivieren\n'
    '  - immich_trash_assets(asset_ids): Fotos in Papierkorb verschieben\n'
    '  - immich_empty_trash(): Papierkorb leeren\n'
    '  - immich_api_request(endpoint="/...", method="GET", params={}, body={}): GENERISCHER AUFRUF\n'
    '    für alle 254 Endpoints aus immich_endpoints.json (v3 OpenAPI-Spezifikation).\n'
    '  WICHTIG: Bei Fragen nach "Fotos von gestern/heute/dieser Woche/diesem Monat" IMMER date_from verwenden!\n'
    '  WICHTIG: Bei Fragen nach Objekten/Konzepten (Hunde, Auto, Strand, Essen) smart=True setzen!\n'
    '  Das Heute-Datum ist 2026-07-08.\n'
    '  Die Thumbnails sind klickbar und öffnen das Originalfoto in voller Auflösung.\n'
    '  Thumbnail-Bilder nebeneinander in Tabellen oder Grids anordnen.\n'
)
