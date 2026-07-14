import base64
import json
import threading
import time
from pathlib import Path

import requests

PLUGIN_NAME = "homeassistant"
PLUGIN_DESC = "Home Assistant Smart-Home-Steuerung – Räume, Geräte, Status, Steuerung"

VAULT_FILE = Path(__file__).parent.parent / 'vault.json'

_cache = {"states": None, "ts": 0, "ttl": 60}
_ha_lock = threading.Lock()

def _vault():
    if not VAULT_FILE.exists():
        return {}
    return json.loads(VAULT_FILE.read_text())

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

def _conn():
    url = _vget("homeassistant/url").rstrip('/')
    token = _vget("homeassistant/token")
    if not url:
        return None, None, "HA-URL fehlt. `vault_set homeassistant/url https://ha.example.com:8123`"
    if not token:
        return None, None, "HA-Token fehlt. `vault_set homeassistant/token …`"
    return url, {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, None

def _fetch_states(url, headers):
    global _cache
    with _ha_lock:
        now = time.time()
        if _cache["states"] and now - _cache["ts"] < _cache["ttl"]:
            return _cache["states"], None
        try:
            r = requests.get(f"{url}/api/states", headers=headers, timeout=15)
            if r.status_code == 200:
                _cache["states"] = r.json()
                _cache["ts"] = now
                return _cache["states"], None
            return None, f"Status {r.status_code}"
        except Exception as e:
            return None, str(e)

def _extract_area(eid, attrs):
    name = (attrs.get("friendly_name") or eid).lower()
    # Check if entity_id or name contains area keywords
    area_keywords = {
        "wohnzimmer": "Wohnzimmer", "schlafzimmer": "Schlafzimmer",
        "küche": "Küche", "kueche": "Küche",
        "bad": "Bad", "badezimmer": "Bad",
        "flur": "Flur", "hausgang": "Hausgang", "eingang": "Eingang",
        "terrasse": "Terrasse", "garten": "Garten", "garage": "Garage",
        "büro": "Büro", "arbeitszimmer": "Büro", "keller": "Keller",
        "innen": "Innen", "aussen": "Außen", "außen": "Außen",
        "hof": "Hof", "eckerrasse": "Eckterrasse", "eckterasse": "Eckterrasse",
    }
    for kw, area in area_keywords.items():
        if kw in eid.lower() or kw in name:
            return area
    return ""

def _format_entity(s):
    eid = s.get("entity_id", "?")
    state = s.get("state", "?")
    attrs = s.get("attributes", {})
    fn = attrs.get("friendly_name", eid)
    area = _extract_area(eid, attrs)
    icon = ""
    if state == "on":
        icon = "🟢"
    elif state == "off":
        icon = "⚫"
    elif state == "unavailable":
        icon = "❌"
    elif state == "open":
        icon = "🚪"
    elif state == "closed":
        icon = "🔒"
    elif state == "home":
        icon = "🏠"
    elif state == "not_home":
        icon = "🚶"
    elif state.isdigit() or state.replace(".","").isdigit():
        icon = "📊"
    else:
        icon = "🔘"

    parts = [f"{icon} **{fn}** (`{eid}`)"]
    if area:
        parts.append(f"📍{area}")
    parts.append(f"→ {state}")
    extras = []
    if "brightness" in attrs:
        extras.append(f"Helligkeit {attrs['brightness']}")
    if "temperature" in attrs:
        extras.append(f"{attrs['temperature']}°C")
    if "current_temperature" in attrs:
        extras.append(f"{attrs['current_temperature']}°C")
    if "humidity" in attrs:
        extras.append(f"{attrs['humidity']}%")
    if "color_temp" in attrs:
        extras.append(f"Farbtemp {attrs['color_temp']}")
    if extras:
        parts.append(f"({', '.join(extras)})")
    return " ".join(parts)


def homeassistant_get_states(domain=""):
    url, headers, err = _conn()
    if err:
        return err
    try:
        states, err = _fetch_states(url, headers)
        if err:
            return f"❌ {err}"
        if not states:
            return "Keine Entitäten."
        if domain:
            states = [s for s in states if s.get("entity_id","").startswith(f"{domain}.")]
        if not states:
            return f"Keine Entitäten für Domain '{domain}'."
        lines = [_format_entity(s) for s in states[:50]]
        total = len(states)
        out = f"Home Assistant – {total} Entitäten"
        if domain:
            out += f" (Domain: {domain})"
        if total > 50:
            out += " (erste 50 gezeigt)"
        return out + "\n" + "\n".join(lines)
    except Exception as e:
        return f"❌ {e}"

def homeassistant_get_state(entity_id):
    url, headers, err = _conn()
    if err:
        return err
    try:
        r = requests.get(f"{url}/api/states/{entity_id}", headers=headers, timeout=15)
        if r.status_code == 200:
            s = r.json()
            return _format_entity(s)
        return f"❌ Status {r.status_code}"
    except Exception as e:
        return f"❌ {e}"

def homeassistant_find(query):
    url, headers, err = _conn()
    if err:
        return err
    try:
        states, err = _fetch_states(url, headers)
        if err:
            return f"❌ {err}"
        q = query.lower().strip()
        if not q:
            return "❌ Suchbegriff fehlt."
        matches = []
        for s in states:
            eid = s.get("entity_id", "")
            attrs = s.get("attributes", {})
            fn = (attrs.get("friendly_name") or "").lower()
            area = _extract_area(eid, attrs).lower()
            score = 0
            if q == fn:
                score = 100
            elif q in fn or q in eid:
                score = 50
            elif q in area:
                score = 30
            elif any(kw in fn for kw in q.split() if len(kw) > 2):
                score = 20
            if score:
                matches.append((score, s))
        matches.sort(key=lambda x: -x[0])
        if not matches:
            return f"❌ Nichts gefunden für '{query}'. Nutze homeassistant_get_states() für alle Entitäten."
        lines = [f"🔍 {len(matches)} Treffer für '{query}':"]
        for score, s in matches[:15]:
            formatted = _format_entity(s)
            lines.append(f"  [{score:3d}%] {formatted}")
        if len(matches) > 15:
            lines.append(f"  ... +{len(matches)-15} weitere")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ {e}"

def homeassistant_turn_on(entity_id):
    domain = entity_id.split(".")[0] if "." in entity_id else "light"
    return homeassistant_call_service(domain, "turn_on", entity_id)

def homeassistant_turn_off(entity_id):
    domain = entity_id.split(".")[0] if "." in entity_id else "light"
    return homeassistant_call_service(domain, "turn_off", entity_id)

def homeassistant_toggle(entity_id):
    domain = entity_id.split(".")[0] if "." in entity_id else "light"
    return homeassistant_call_service(domain, "toggle", entity_id)

_COLORS = {
    "rot": (255, 0, 0), "red": (255, 0, 0),
    "blau": (0, 0, 255), "blue": (0, 0, 255),
    "grün": (0, 255, 0), "gruen": (0, 255, 0), "green": (0, 255, 0),
    "gelb": (255, 255, 0), "yellow": (255, 255, 0),
    "orange": (255, 165, 0),
    "lila": (128, 0, 128), "violett": (128, 0, 128), "purple": (128, 0, 128),
    "pink": (255, 192, 203), "rosa": (255, 192, 203),
    "weiß": (255, 255, 255), "weiss": (255, 255, 255), "white": (255, 255, 255),
    "türkis": (0, 255, 255), "cyan": (0, 255, 255), "teal": (0, 128, 128),
}

def _parse_color(color_str):
    if not color_str:
        return None
    c = color_str.strip().lower()
    if c in _COLORS:
        return _COLORS[c]
    try:
        parts = [int(x) for x in c.replace("(", "").replace(")", "").split(",")]
        if len(parts) == 3:
            return tuple(parts[:3])
    except Exception:
        pass
    return None

def homeassistant_light_set(entity_id, power=None, color="", brightness=None, color_temp=None):
    url, headers, err = _conn()
    if err:
        return err
    try:
        payload = {"entity_id": entity_id}
        if power is not None:
            if isinstance(power, str):
                power = power.lower() in ("true", "on", "1", "yes", "ein", "an")
        rgb = _parse_color(color)
        if rgb:
            payload["rgb_color"] = list(rgb)
        if brightness is not None:
            payload["brightness"] = max(1, min(255, int(brightness)))
        if color_temp:
            payload["color_temp"] = int(color_temp)

        if power is True or (power is None and (rgb or brightness or color_temp)):
            domain, service = "light", "turn_on"
        elif power is False:
            domain, service = "light", "turn_off"
        else:
            return f"ℹ️ {entity_id}: Keine Änderung (kein power/color/brightness angegeben)"

        r = requests.post(f"{url}/api/services/{domain}/{service}",
                          json=payload, headers=headers, timeout=15)
        if r.status_code == 200:
            parts = [f"✅ {entity_id}"]
            if power is True:
                parts.append("ein")
            elif power is False:
                parts.append("aus")
            if rgb:
                parts.append(f"Farbe=RGB{rgb}")
            if brightness is not None:
                parts.append(f"Helligkeit={brightness}")
            if color_temp:
                parts.append(f"Farbtemp={color_temp}")
            return " ".join(parts)
        return f"❌ Status {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return f"❌ {e}"


def homeassistant_list_scenes():
    url, headers, err = _conn()
    if err:
        return err
    try:
        states, err = _fetch_states(url, headers)
        if err:
            return f"❌ {err}"
        scenes = [s for s in states if s.get("entity_id", "").startswith("scene.")]
        if not scenes:
            return "Keine Szenen gefunden."
        lines = ["🎬 **Szenen**"]
        for s in sorted(scenes, key=lambda x: x.get("attributes", {}).get("friendly_name", "")):
            eid = s["entity_id"]
            fn = s.get("attributes", {}).get("friendly_name", eid)
            area = _extract_area(eid, s.get("attributes", {}))
            icon = "✅" if s.get("state") == "on" else "⚫"
            line = f"  {icon} **{fn}** (`{eid}`)"
            if area:
                line += f" 📍{area}"
            lines.append(line)
        return "\n".join(lines)
    except Exception as e:
        return f"❌ {e}"


def homeassistant_activate_scene(scene_id):
    return homeassistant_call_service("scene", "turn_on", scene_id)


def homeassistant_list_scripts():
    url, headers, err = _conn()
    if err:
        return err
    try:
        states, err = _fetch_states(url, headers)
        if err:
            return f"❌ {err}"
        scripts = [s for s in states if s.get("entity_id", "").startswith("script.")]
        if not scripts:
            return "Keine Skripte gefunden."
        lines = ["📜 **Skripte**"]
        for s in sorted(scripts, key=lambda x: x.get("attributes", {}).get("friendly_name", "")):
            eid = s["entity_id"]
            fn = s.get("attributes", {}).get("friendly_name", eid)
            state = s.get("state", "")
            icon = "▶️" if state == "on" else "⏹️"
            lines.append(f"  {icon} **{fn}** (`{eid}`) → {state}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ {e}"


def homeassistant_run_script(entity_id):
    return homeassistant_call_service("script", "turn_on", entity_id)


def homeassistant_call_service(domain, service, entity_id, data=""):
    url, headers, err = _conn()
    if err:
        return err
    try:
        payload = {"entity_id": entity_id}
        if data:
            try:
                payload.update(json.loads(data) if isinstance(data, str) else data)
            except Exception:
                pass
        r = requests.post(f"{url}/api/services/{domain}/{service}",
                          json=payload, headers=headers, timeout=15)
        if r.status_code == 200:
            result = r.json()
            if result:
                return f"✅ {domain}/{service} auf {entity_id} ausgeführt"
            return f"✅ {domain}/{service} ausgeführt (keine Rückmeldung)"
        return f"❌ Status {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return f"❌ {e}"


def homeassistant_get_camera_snapshot(entity_id):
    """Holt ein Live-Kamerabild aus Home Assistant als Base64."""
    url, headers, err = _conn()
    if err:
        return err
    try:
        r = requests.get(f"{url}/api/states/{entity_id}", headers=headers, timeout=15)
        if r.status_code != 200:
            return f"❌ Kamera {entity_id} nicht gefunden (Status {r.status_code})"
        state = r.json().get("state", "")
        # Try HA camera proxy
        # HA exposes /api/camera_proxy/{camera_entity_id} for live snapshots
        img_r = requests.get(f"{url}/api/camera_proxy/{entity_id}", headers=headers, timeout=15)
        if img_r.status_code == 200:
            b64 = base64.b64encode(img_r.content).decode()
            return f"data:image/jpeg;base64,{b64}"
        # Fallback: Try fetching via snapshot service
        snap_r = requests.post(
            f"{url}/api/services/camera/snapshot",
            json={"entity_id": entity_id, "filename": "/tmp/ha_snapshot.jpg"},
            headers=headers, timeout=15
        )
        if snap_r.status_code == 200:
            b64 = base64.b64encode(snap_r.content).decode()
            return f"data:image/jpeg;base64,{b64}"
        return f"❌ Live-Bild nicht verfügbar (Status {img_r.status_code}) – Kamera-ID: `{entity_id}` (Status: {state})"
    except Exception as e:
        return f"❌ {e}"

TOOLS = [
    {"type":"function","function":{"name":"homeassistant_get_states","description":"Liste ALLE Entitäten nach Domain gefiltert (z.B. 'light', 'sensor', 'switch', '' für alle). Jede Entität zeigt Name, Entity-ID, Raum und Status.","parameters":{"type":"object","properties":{"domain":{"type":"string","description":"Domain-Filter: 'light', 'sensor', 'switch', 'climate', '' (alle)."}},"required":[]}}},  # noqa: E501
    {"type":"function","function":{"name":"homeassistant_get_state","description":"Zeige detaillierten Status einer Entität (z.B. light.wohnzimmer).","parameters":{"type":"object","properties":{"entity_id":{"type":"string","description":"Entity-ID wie light.wohnzimmer"}},"required":["entity_id"]}}},  # noqa: E501
    {"type":"function","function":{"name":"homeassistant_find","description":"SUCHE Entitäten nach Name, Raum oder Hersteller. Z.B. 'Wohnzimmer' findet alle Lichter dort, 'Nano' findet Nanoleaf-Geräte, 'Temperatur' findet Thermostate.","parameters":{"type":"object","properties":{"query":{"type":"string","description":"Suchbegriff – Name, Raum, Hersteller oder Teil davon"}},"required":["query"]}}},  # noqa: E501
    {"type":"function","function":{"name":"homeassistant_turn_on","description":"Schalte eine Entität EIN (Licht, Steckdose, etc.). ENTITY_ID VORHER MIT homeassistant_find() HERAUSFINDEN.","parameters":{"type":"object","properties":{"entity_id":{"type":"string","description":"Entity-ID"}},"required":["entity_id"]}}},  # noqa: E501
    {"type":"function","function":{"name":"homeassistant_turn_off","description":"Schalte eine Entität AUS.","parameters":{"type":"object","properties":{"entity_id":{"type":"string","description":"Entity-ID"}},"required":["entity_id"]}}},  # noqa: E501
    {"type":"function","function":{"name":"homeassistant_toggle","description":"Schalte eine Entität UM (an/aus wechseln).","parameters":{"type":"object","properties":{"entity_id":{"type":"string","description":"Entity-ID"}},"required":["entity_id"]}}},  # noqa: E501
    {"type":"function","function":{"name":"homeassistant_light_set","description":"Setze Lichtfarbe, Helligkeit oder Farbtemperatur. Farbe als Name ('rot', 'blau', 'grün', 'gelb', 'orange', 'lila', 'pink', 'weiß', 'türkis') oder RGB (255,0,0).","parameters":{"type":"object","properties":{"entity_id":{"type":"string","description":"Entity-ID"},"power":{"type":"boolean","description":"True=ein, False=aus, None=lassen (optional)"},"color":{"type":"string","description":"Farbe als Name ('rot') oder RGB-Komma-Liste ('255,0,0') (optional)"},"brightness":{"type":"integer","description":"Helligkeit 1-255 (optional)"},"color_temp":{"type":"integer","description":"Farbtemperatur in Kelvin (optional)"}},"required":["entity_id"]}}},  # noqa: E501
    {"type":"function","function":{"name":"homeassistant_call_service","description":"Rufe einen beliebigen Service auf (z.B. light/turn_on, scene/turn_on).","parameters":{"type":"object","properties":{"domain":{"type":"string","description":"Domain (light, switch, scene, climate...)"},"service":{"type":"string","description":"Service (turn_on, turn_off, toggle...)"},"entity_id":{"type":"string","description":"Entity-ID"},"data":{"type":"string","description":"Zusätzliche Daten als JSON-String (optional)"}},"required":["domain","service","entity_id"]}}},  # noqa: E501
    {"type":"function","function":{"name":"homeassistant_list_scenes","description":"Liste alle Szenen (Lichtstimmungen) auf.","parameters":{"type":"object","properties":{},"required":[]}}},
    {"type":"function","function":{"name":"homeassistant_activate_scene","description":"Aktiviere eine Szene. VORHER homeassistant_list_scenes() für verfügbare Szenen.","parameters":{"type":"object","properties":{"scene_id":{"type":"string","description":"Entity-ID der Szene (z.B. scene.abendstimmung)"}},"required":["scene_id"]}}},  # noqa: E501
    {"type":"function","function":{"name":"homeassistant_list_scripts","description":"Liste alle verfügbaren Skripte/Automationen auf.","parameters":{"type":"object","properties":{},"required":[]}}},
    {"type":"function","function":{"name":"homeassistant_run_script","description":"Führe ein Skript aus. VORHER homeassistant_list_scripts() für verfügbare Skripte.","parameters":{"type":"object","properties":{"entity_id":{"type":"string","description":"Entity-ID des Skripts (z.B. script.guten_morgen)"}},"required":["entity_id"]}}},  # noqa: E501
    {"type":"function","function":{"name":"homeassistant_get_camera_snapshot","description":"Live-Kamerabild von einer Home-Assistant-Kamera abrufen. Gibt Base64-Bild zurück. Vorher camera-Entity mit homeassistant_find('camera') finden.","parameters":{"type":"object","properties":{"entity_id":{"type":"string","description":"Entity-ID der Kamera (z.B. camera.terasse_standardauflosung)"}},"required":["entity_id"]}}},  # noqa: E501
]

TOOL_MAP = {
    "homeassistant_get_states": homeassistant_get_states,
    "homeassistant_get_state": homeassistant_get_state,
    "homeassistant_find": homeassistant_find,
    "homeassistant_light_set": homeassistant_light_set,
    "homeassistant_turn_on": homeassistant_turn_on,
    "homeassistant_turn_off": homeassistant_turn_off,
    "homeassistant_toggle": homeassistant_toggle,
    "homeassistant_call_service": homeassistant_call_service,
    "homeassistant_list_scenes": homeassistant_list_scenes,
    "homeassistant_activate_scene": homeassistant_activate_scene,
    "homeassistant_list_scripts": homeassistant_list_scripts,
    "homeassistant_run_script": homeassistant_run_script,
    "homeassistant_get_camera_snapshot": homeassistant_get_camera_snapshot,
}

PROMPT_EXTRA = (
    "HOME ASSISTANT:\n"
    "  WICHTIG: Entity-IDs sind NICHT nach Hersteller benannt! 'Nanoleaf' → light.canvas_48e9, 'Wohnzimmer Lampe' → light.wohnzimmer\n"
    "  1. **homeassistant_get_states(domain)**: Alle Entitäten nach Domain (light, sensor, switch, ''=alle)\n"
    "  2. **homeassistant_find(query)**: Suche nach Name/Raum/Hersteller (z.B. 'Wohnzimmer', 'Nano', 'Garage')\n"
    "  3. **homeassistant_get_state(entity_id)**: Status einer Entität\n"
    "  4. **homeassistant_light_set(entity_id, color='rot', brightness=255)**: Lichtfarbe + Helligkeit setzen\n"
    "  5. **homeassistant_turn_on/turn_off/toggle(entity_id)**: Ein/Aus/Um\n"
    "  6. **homeassistant_call_service(domain, service, entity_id, data)**: Erweiterte Steuerung\n"
    "  7. **homeassistant_list_scenes**: Alle Lichtstimmungen(Szenen) anzeigen\n"
    "  8. **homeassistant_activate_scene(scene_id)**: Szene aktivieren (z.B. 'Kino', 'Abendstimmung')\n"
    "  9. **homeassistant_list_scripts**: Alle Skripte/Automationen anzeigen\n"
    "  10. **homeassistant_run_script(entity_id)**: Skript ausführen (z.B. script.guten_morgen)\n"
    "  11. **homeassistant_get_camera_snapshot(entity_id)**: Live-Kamerabild abrufen (Base64)\n"
    "  Vault: homeassistant/url, homeassistant/token\n"
    "  BEISPIELE:\n"
    "    'Schalte Nanoleaf ein auf rot' → homeassistant_find('Nano') → homeassistant_light_set('light.canvas_48e9', power=True, color='rot')\n"
    "    'Licht Wohnzimmer aus' → homeassistant_find('Wohnzimmer') → homeassistant_turn_off('light.wohnzimmer')\n"
    "    'Wohnzimmer heller' → homeassistant_light_set('light.wohnzimmer', brightness=200)\n"
    "    'Kinostimmung' → homeassistant_list_scenes() → homeassistant_activate_scene('scene.kino')\n"
)
