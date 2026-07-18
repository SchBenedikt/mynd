import base64
import json
from pathlib import Path

import requests

from core.vault import _vault_get

VAULT_FILE = Path(__file__).resolve().parents[1] / 'vault.json'
TOKEN_URL = 'https://accounts.spotify.com/api/token'
API_BASE = 'https://api.spotify.com'


def _spotify_api(method, endpoint, body=None):
    try:
        client_id = _vault_get('spotify/client_id')
        client_secret = _vault_get('spotify/client_secret')
        refresh_token = _vault_get('spotify/refresh_token')
        if not client_id or not client_secret or not refresh_token:
            return '❌ Spotify-Credentials fehlen (vault: spotify/client_id, spotify/client_secret, spotify/refresh_token)'

        auth = base64.b64encode(f'{client_id}:{client_secret}'.encode()).decode()
        r = requests.post(TOKEN_URL, data={
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
        }, headers={
            'Authorization': f'Basic {auth}',
            'Content-Type': 'application/x-www-form-urlencoded',
        }, timeout=10)
        if r.status_code != 200:
            return f'❌ Token-Refresh fehlgeschlagen (Status {r.status_code}): {r.text[:300]}'
        access_token = r.json().get('access_token', '')
        if not access_token:
            return '❌ Kein access_token in der Antwort'

        url = f'{API_BASE}{endpoint}'
        h = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        }
        kwargs = {'headers': h, 'timeout': 30}
        method = method.upper()
        if body is not None and method in ('POST', 'PUT'):
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                except json.JSONDecodeError:
                    return f'❌ body ist kein gültiges JSON: {body[:200]}'
            kwargs['json'] = body
        try:
            resp = requests.request(method, url, **kwargs)
        except requests.exceptions.Timeout:
            return '❌ Timeout (30s)'
        except requests.exceptions.ConnectionError:
            return '❌ Verbindungsfehler'

        if resp.status_code == 204:
            return '✅ Erfolg (204)'
        if resp.status_code in (200, 201):
            try:
                return json.dumps(resp.json(), ensure_ascii=False, indent=2)[:8000]
            except Exception:
                return (resp.text or '')[:8000]
        try:
            detail = resp.json().get('error', {}).get('message', resp.text[:500])
        except Exception:
            detail = resp.text[:500]
        return f'❌ Status {resp.status_code}: {detail}'
    except Exception as e:
        return f'❌ {e}'


def spotify_currently_playing():
    return _spotify_api('GET', '/v1/me/player/currently-playing')


def spotify_playback_state():
    return _spotify_api('GET', '/v1/me/player')


def spotify_play(device_id='', context_uri='', offset=None, position_ms=0):
    body = {}
    if context_uri:
        body['context_uri'] = context_uri
    if offset:
        if isinstance(offset, str):
            try:
                offset = json.loads(offset)
            except json.JSONDecodeError:
                return f'❌ offset ist kein gültiges JSON: {offset}'
        body['offset'] = offset
    if position_ms:
        body['position_ms'] = int(position_ms)
    endpoint = '/v1/me/player/play'
    if device_id:
        endpoint += f'?device_id={device_id}'
    return _spotify_api('PUT', endpoint, body if body else None)


def spotify_pause(device_id=''):
    endpoint = '/v1/me/player/pause'
    if device_id:
        endpoint += f'?device_id={device_id}'
    return _spotify_api('PUT', endpoint)


def spotify_next(device_id=''):
    endpoint = '/v1/me/player/next'
    if device_id:
        endpoint += f'?device_id={device_id}'
    return _spotify_api('POST', endpoint)


def spotify_previous(device_id=''):
    endpoint = '/v1/me/player/previous'
    if device_id:
        endpoint += f'?device_id={device_id}'
    return _spotify_api('POST', endpoint)


def spotify_search(q, type='track', limit=10, offset=0):
    params = f'?q={q}&type={type}&limit={int(limit)}&offset={int(offset)}'
    return _spotify_api('GET', f'/v1/search{params}')


def spotify_get_playlists(limit=20, offset=0):
    return _spotify_api('GET', f'/v1/me/playlists?limit={int(limit)}&offset={int(offset)}')


def spotify_get_playlist(playlist_id, limit=50, offset=0):
    return _spotify_api('GET', f'/v1/playlists/{playlist_id}/tracks?limit={int(limit)}&offset={int(offset)}')


def spotify_get_recommendations(seed_tracks='', seed_artists='', seed_genres='', limit=10, **kwargs):
    params = f'?limit={int(limit)}'
    if seed_tracks:
        params += f'&seed_tracks={seed_tracks}'
    if seed_artists:
        params += f'&seed_artists={seed_artists}'
    if seed_genres:
        params += f'&seed_genres={seed_genres}'
    for k, v in kwargs.items():
        params += f'&{k}={v}'
    return _spotify_api('GET', f'/v1/recommendations{params}')


def spotify_add_to_queue(uri, device_id=''):
    endpoint = f'/v1/me/player/queue?uri={uri}'
    if device_id:
        endpoint += f'&device_id={device_id}'
    return _spotify_api('POST', endpoint)


def spotify_get_top_tracks(limit=10, offset=0, time_range='medium_term'):
    return _spotify_api('GET', f'/v1/me/top/tracks?limit={int(limit)}&offset={int(offset)}&time_range={time_range}')


def spotify_get_artist(artist_id):
    return _spotify_api('GET', f'/v1/artists/{artist_id}')


def spotify_get_album(album_id):
    return _spotify_api('GET', f'/v1/albums/{album_id}')


def spotify_set_volume(volume_percent, device_id=''):
    endpoint = f'/v1/me/player/volume?volume_percent={int(volume_percent)}'
    if device_id:
        endpoint += f'&device_id={device_id}'
    return _spotify_api('PUT', endpoint)


def spotify_get_categories(limit=20, offset=0):
    return _spotify_api('GET', f'/v1/browse/categories?limit={int(limit)}&offset={int(offset)}')


def spotify_get_new_releases(limit=20, offset=0):
    return _spotify_api('GET', f'/v1/browse/new-releases?limit={int(limit)}&offset={int(offset)}')


def spotify_set_shuffle(state, device_id=''):
    endpoint = f'/v1/me/player/shuffle?state={str(state).lower()}'
    if device_id:
        endpoint += f'&device_id={device_id}'
    return _spotify_api('PUT', endpoint)


def spotify_set_repeat(state, device_id=''):
    endpoint = f'/v1/me/player/repeat?state={state}'
    if device_id:
        endpoint += f'&device_id={device_id}'
    return _spotify_api('PUT', endpoint)


PLUGIN_NAME = "spotify"
PLUGIN_VERSION = "1.0"

TOOLS = [
    {"type": "function", "function": {
        "name": "spotify_currently_playing",
        "description": "Zeigt den aktuell laufenden Track auf Spotify an (Titel, Künstler, Album, Fortschritt).",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "spotify_playback_state",
        "description": "Zeigt den aktuellen Playback-Status (wiedergabe/pausiert, Gerät, aktueller Track, Lautstärke, shuffle/repeat).",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "spotify_play",
        "description": "Setzt die Wiedergabe fort oder startet einen bestimmten Track/Album/Playlist.",
        "parameters": {"type": "object", "properties": {
            "device_id": {"type": "string", "description": "Geräte-ID (optional)"},
            "context_uri": {"type": "string", "description": "Spotify-URI des Kontexts (z.B. spotify:album:..., spotify:playlist:..., spotify:artist:...)"},
            "offset": {"type": "object", "description": "Position im Kontext: {\"position\": 5} oder {\"uri\": \"spotify:track:...\"}"},
            "position_ms": {"type": "integer", "description": "Startposition in Millisekunden"}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "spotify_pause",
        "description": "Pausiert die aktuelle Wiedergabe.",
        "parameters": {"type": "object", "properties": {
            "device_id": {"type": "string", "description": "Geräte-ID (optional)"}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "spotify_next",
        "description": "Überspringt zum nächsten Track.",
        "parameters": {"type": "object", "properties": {
            "device_id": {"type": "string", "description": "Geräte-ID (optional)"}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "spotify_previous",
        "description": "Geht zum vorherigen Track zurück.",
        "parameters": {"type": "object", "properties": {
            "device_id": {"type": "string", "description": "Geräte-ID (optional)"}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "spotify_search",
        "description": "Durchsucht Spotify nach Tracks, Alben, Künstlern oder Playlists.",
        "parameters": {"type": "object", "properties": {
            "q": {"type": "string", "description": "Suchbegriff"},
            "type": {"type": "string", "enum": ["track", "album", "artist", "playlist"], "default": "track", "description": "Suchtyp"},
            "limit": {"type": "integer", "default": 10, "description": "Maximale Ergebnisse (1-50)"},
            "offset": {"type": "integer", "default": 0, "description": "Offset für Paginierung"}
        }, "required": ["q"]}
    }},
    {"type": "function", "function": {
        "name": "spotify_get_playlists",
        "description": "Liste die Playlists des aktuellen Benutzers auf.",
        "parameters": {"type": "object", "properties": {
            "limit": {"type": "integer", "default": 20, "description": "Maximale Anzahl (1-50)"},
            "offset": {"type": "integer", "default": 0, "description": "Offset für Paginierung"}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "spotify_get_playlist",
        "description": "Hole die Tracks einer Playlist anhand der Playlist-ID.",
        "parameters": {"type": "object", "properties": {
            "playlist_id": {"type": "string", "description": "Playlist-ID (aus spotify_get_playlists)"},
            "limit": {"type": "integer", "default": 50, "description": "Maximale Tracks (1-100)"},
            "offset": {"type": "integer", "default": 0, "description": "Offset für Paginierung"}
        }, "required": ["playlist_id"]}
    }},
    {"type": "function", "function": {
        "name": "spotify_get_recommendations",
        "description": "Empfehlungen basierend auf Seed-Tracks, -Künstlern oder -Genres. Parameter als seed_tracks=..., seed_artists=..., seed_genres=... (max 5 Seeds).",
        "parameters": {"type": "object", "properties": {
            "seed_tracks": {"type": "string", "description": "Komma-getrennte Track-IDs"},
            "seed_artists": {"type": "string", "description": "Komma-getrennte Künstler-IDs"},
            "seed_genres": {"type": "string", "description": "Komma-getrennte Genres (z.B. 'rock,pop,electronic')"},
            "limit": {"type": "integer", "default": 10, "description": "Anzahl Empfehlungen (1-100)"},
            "target_danceability": {"type": "number", "description": "Ziel-Wert 0.0-1.0"},
            "target_energy": {"type": "number", "description": "Ziel-Wert 0.0-1.0"},
            "target_valence": {"type": "number", "description": "Ziel-Wert 0.0-1.0 (musikalische Positivität)"}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "spotify_add_to_queue",
        "description": "Füge einen Track zur Warteschlange hinzu.",
        "parameters": {"type": "object", "properties": {
            "uri": {"type": "string", "description": "Spotify-URI des Tracks (z.B. spotify:track:...)"},
            "device_id": {"type": "string", "description": "Geräte-ID (optional)"}
        }, "required": ["uri"]}
    }},
    {"type": "function", "function": {
        "name": "spotify_get_top_tracks",
        "description": "Zeige die Top-Tracks des Benutzers an.",
        "parameters": {"type": "object", "properties": {
            "limit": {"type": "integer", "default": 10, "description": "Anzahl (1-50)"},
            "offset": {"type": "integer", "default": 0, "description": "Offset"},
            "time_range": {"type": "string", "enum": ["long_term", "medium_term", "short_term"], "default": "medium_term", "description": "long_term=Jahre, medium_term=6 Monate, short_term=4 Wochen"}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "spotify_get_artist",
        "description": "Hole Informationen zu einem Künstler.",
        "parameters": {"type": "object", "properties": {
            "artist_id": {"type": "string", "description": "Spotify-Künstler-ID"}
        }, "required": ["artist_id"]}
    }},
    {"type": "function", "function": {
        "name": "spotify_get_album",
        "description": "Hole Informationen zu einem Album inklusive Tracks.",
        "parameters": {"type": "object", "properties": {
            "album_id": {"type": "string", "description": "Spotify-Album-ID"}
        }, "required": ["album_id"]}
    }},
    {"type": "function", "function": {
        "name": "spotify_set_volume",
        "description": "Setze die Wiedergabelautstärke.",
        "parameters": {"type": "object", "properties": {
            "volume_percent": {"type": "integer", "description": "Lautstärke 0-100"},
            "device_id": {"type": "string", "description": "Geräte-ID (optional)"}
        }, "required": ["volume_percent"]}
    }},
    {"type": "function", "function": {
        "name": "spotify_get_categories",
        "description": "Zeige verfügbare Browse-Kategorien (Genres/Stimmungen).",
        "parameters": {"type": "object", "properties": {
            "limit": {"type": "integer", "default": 20, "description": "Anzahl (1-50)"},
            "offset": {"type": "integer", "default": 0, "description": "Offset"}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "spotify_get_new_releases",
        "description": "Zeige neue Veröffentlichungen (New Releases).",
        "parameters": {"type": "object", "properties": {
            "limit": {"type": "integer", "default": 20, "description": "Anzahl (1-50)"},
            "offset": {"type": "integer", "default": 0, "description": "Offset"}
        }, "required": []}
    }},
    {"type": "function", "function": {
        "name": "spotify_set_shuffle",
        "description": "Schalte Zufallswiedergabe ein oder aus.",
        "parameters": {"type": "object", "properties": {
            "state": {"type": "boolean", "description": "true für Zufallswiedergabe an, false für aus"},
            "device_id": {"type": "string", "description": "Geräte-ID (optional)"}
        }, "required": ["state"]}
    }},
    {"type": "function", "function": {
        "name": "spotify_set_repeat",
        "description": "Setze den Wiederholungsmodus.",
        "parameters": {"type": "object", "properties": {
            "state": {"type": "string", "enum": ["off", "context", "track"], "description": "off=aus, context=Playlist/Album wiederholen, track=ein Titel wiederholen"},
            "device_id": {"type": "string", "description": "Geräte-ID (optional)"}
        }, "required": ["state"]}
    }},
]

TOOL_MAP = {
    'spotify_currently_playing': spotify_currently_playing,
    'spotify_playback_state': spotify_playback_state,
    'spotify_play': spotify_play,
    'spotify_pause': spotify_pause,
    'spotify_next': spotify_next,
    'spotify_previous': spotify_previous,
    'spotify_search': spotify_search,
    'spotify_get_playlists': spotify_get_playlists,
    'spotify_get_playlist': spotify_get_playlist,
    'spotify_get_recommendations': spotify_get_recommendations,
    'spotify_add_to_queue': spotify_add_to_queue,
    'spotify_get_top_tracks': spotify_get_top_tracks,
    'spotify_get_artist': spotify_get_artist,
    'spotify_get_album': spotify_get_album,
    'spotify_set_volume': spotify_set_volume,
    'spotify_get_categories': spotify_get_categories,
    'spotify_get_new_releases': spotify_get_new_releases,
    'spotify_set_shuffle': spotify_set_shuffle,
    'spotify_set_repeat': spotify_set_repeat,
}

PROMPT_EXTRA = (
    'SPOTIFY (Musik-Streaming):\n'
    '  - spotify_currently_playing(): Aktuell laufenden Track anzeigen\n'
    '  - spotify_playback_state(): Detaillierten Playback-Status abrufen\n'
    '  - spotify_play(device_id="", context_uri="", offset={}, position_ms=0): Wiedergabe starten/fortsetzen\n'
    '    context_uri z.B. spotify:album:..., spotify:playlist:..., spotify:artist:...\n'
    '    offset z.B. {"position": 5} oder {"uri": "spotify:track:..."}\n'
    '  - spotify_pause(device_id=""): Wiedergabe pausieren\n'
    '  - spotify_next(device_id=""): Nächsten Track überspringen\n'
    '  - spotify_previous(device_id=""): Vorherigen Track\n'
    '  - spotify_search(q="...", type="track|album|artist|playlist", limit=10): Suche\n'
    '  - spotify_get_playlists(limit=20): Eigene Playlists auflisten\n'
    '  - spotify_get_playlist(playlist_id, limit=50): Tracks einer Playlist\n'
    '  - spotify_get_recommendations(seed_tracks="...", seed_artists="...", seed_genres="...", limit=10): Empfehlungen\n'
    '  - spotify_add_to_queue(uri="spotify:track:..."): Track in Warteschlange\n'
    '  - spotify_get_top_tracks(limit=10, time_range="medium_term"): Top-Tracks\n'
    '  - spotify_get_artist(artist_id): Künstler-Details\n'
    '  - spotify_get_album(album_id): Album-Details mit Tracks\n'
    '  - spotify_set_volume(volume_percent, device_id=""): Lautstärke 0-100\n'
    '  - spotify_get_categories(limit=20): Browse-Kategorien\n'
    '  - spotify_get_new_releases(limit=20): Neue Veröffentlichungen\n'
    '  - spotify_set_shuffle(state=True/False): Zufallswiedergabe\n'
    '  - spotify_set_repeat(state="off|context|track"): Wiederholungsmodus\n'
    '  WICHTIG: Credentials aus vault (spotify/client_id, spotify/client_secret, spotify/refresh_token).\n'
    '  Der access_token wird automatisch via Refresh-Token erneuert.\n'
    '  Bei device_id: Wenn kein Gerät angegeben ist, wird das aktive Gerät verwendet.\n'
)
