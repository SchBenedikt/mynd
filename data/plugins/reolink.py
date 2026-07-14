import base64
import json
import threading

import requests

TOOL_SCHEMA = True

TOOLS = [
    {
        "name": "reolink_get_channels",
        "description": "Liste alle Reolink-Kameras mit Status (online/sleep)",
        "parameters": {}
    },
    {
        "name": "reolink_get_snapshot",
        "description": "Schnappschuss einer Kamera (Base64) – weckt die Kamera auf falls nötig",
        "parameters": {
            "channel": {"type": "number", "description": "Kanal-Nummer (0=Terrasse, 1=Hof, 2=Eckterrasse)", "default": 0}
        }
    },
    {
        "name": "reolink_get_ai_state",
        "description": "KI-Erkennungsstatus einer Kamera (Person, Fahrzeug, Tier)",
        "parameters": {
            "channel": {"type": "number", "description": "Kanal-Nummer", "default": 0}
        }
    },
    {
        "name": "reolink_get_rtsp_url",
        "description": "RTSP-Stream-URL einer Kamera für Live-Ansicht",
        "parameters": {
            "channel": {"type": "number", "description": "Kanal-Nummer", "default": 0}
        }
    },
    {
        "name": "reolink_get_device_info",
        "description": "Reolink-Geräte-Informationen (Modell, Firmware, Kanäle)",
        "parameters": {}
    },
    {
        "name": "reolink_get_records",
        "description": "Aufnahmen eines Kanals an einem Datum abrufen",
        "parameters": {
            "channel": {"type": "number", "description": "Kanal-Nummer", "default": 0},
            "year": {"type": "number", "description": "Jahr (z.B. 2026)", "default": 2026},
            "month": {"type": "number", "description": "Monat (1-12)", "default": 7},
            "day": {"type": "number", "description": "Tag (1-31)", "default": 8}
        }
    },
]

API_BASE_URL = "http://192.168.178.190"
API_USER = "admin"
API_PASS = "Schaechner"

_token = None
_token_expiry = 0
_login_lock = threading.Lock()


def _login():
    global _token, _token_expiry
    with _login_lock:
        import time
        now = time.time()
        if _token and _token_expiry > now + 60:
            return _token, None
        try:
            r = requests.post(f"{API_BASE_URL}/cgi-bin/api.cgi?cmd=Login",
                json=[{"cmd": "Login", "action": 0, "param": {"User": {"userName": API_USER, "password": API_PASS}}}],
                timeout=10)
            if r.status_code != 200:
                return None, f"❌ Login fehlgeschlagen (Status {r.status_code})"
            data = r.json()
            token = data[0]["value"]["Token"]["name"]
            lease = int(data[0]["value"]["Token"].get("leaseTime", 3600))
            _token = token
            _token_expiry = now + lease - 120
            return token, None
        except Exception as e:
            return None, f"❌ Login-Fehler: {e}"


def _api(cmd, params=None, body=None, method="GET"):
    token, err = _login()
    if err:
        return None, err
    url = f"{API_BASE_URL}/cgi-bin/api.cgi?cmd={cmd}&token={token}"
    if params:
        for k, v in params.items():
            url += f"&{k}={v}"
    try:
        if method == "POST" and body:
            r = requests.post(url, json=body, timeout=15)
        else:
            r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return None, f"❌ Status {r.status_code}: {r.text[:200]}"
        try:
            data = r.json()
            if data and data[0].get("code", 0) != 0 and data[0].get("code", 0) != 1:
                detail = data[0].get("error", {}).get("detail", str(data))
                return None, f"❌ API-Fehler: {detail}"
            return data, None
        except ValueError:
            return r.content, None
    except Exception as e:
        return None, f"❌ {e}"


def reolink_get_channels():
    data, err = _api("GetChannelStatus")
    if err:
        return err
    channels = data[0]["value"]["status"]
    lines = [f"📹 **Reolink Kameras** ({sum(1 for c in channels if c['online'])}/8 online)"]
    for ch in channels:
        if not ch.get("name"):
            continue
        status = "🟢 Online" if ch["online"] else "⚫ Offline"
        sleep = " 💤 Schlafmodus" if ch.get("sleep") else ""
        uid = ch.get("uid", "")
        lines.append(f"  **Ch{ch['channel']} – {ch['name']}**: {status}{sleep} | UID: {uid}")
    return "\n".join(lines)


def reolink_get_snapshot(channel=0):
    channel = int(channel)
    result, err = _api("GetSnap", params={"channel": channel})
    if err:
        return err
    # Snapshot returns binary JPEG data, but might return JSON if camera is sleeping
    if isinstance(result, bytes):
        b64 = base64.b64encode(result).decode()
        return f"data:image/jpeg;base64,{b64}"
    # If camera is sleeping, return status
    if isinstance(result, list):
        detail = result[0].get("error", {}).get("detail", "Kamera schläft")
        return f"❌ Schnappschuss fehlgeschlagen (Kamera Ch{channel} ist im Schlafmodus): {detail}"
    return "❌ Kein Bild empfangen"


def reolink_get_ai_state(channel=0):
    channel = int(channel)
    data, err = _api("GetAiState", params={"channel": channel})
    if err:
        return err
    ai = data[0]["value"]
    lines = [f"🤖 **KI-Erkennung – Ch{channel} ({ai.get('channel', '?')})**"]
    detections = []
    for key, label in [("people", "Person"), ("vehicle", "Fahrzeug"), ("dog_cat", "Tier")]:
        state = ai.get(key, {})
        if state.get("support"):
            status = "🔴 Ausgelöst" if state.get("alarm_state") else "🟢 Keine Erkennung"
            detections.append(f"  {label}: {status}")
    if detections:
        lines.extend(detections)
    else:
        lines.append("  Keine KI-Erkennungsfunktionen aktiviert")
    return "\n".join(lines)


def reolink_get_rtsp_url(channel=0):
    channel = int(channel)
    data, err = _api("GetRtspUrl", params={"channel": channel})
    if err:
        return err
    rtsp = data[0]["value"]["rtspUrl"]
    lines = [f"📺 **RTSP-Streams – Ch{channel}**"]
    lines.append(f"  Haupt-Stream: `{rtsp.get('mainStream', '?')}`")
    lines.append(f"  Sub-Stream: `{rtsp.get('subStream', '?')}`")
    lines.append("\n💡 Nutze z.B. VLC zum Öffnen: `vlc rtsp://...`")
    return "\n".join(lines)


def reolink_get_device_info():
    data, err = _api("GetDevInfo")
    if err:
        return err
    info = data[0]["value"]["DevInfo"]
    lines = [f"🖥 **Reolink {info.get('model', '?')}**"]
    lines.append(f"  Name: {info.get('name', '?')}")
    lines.append(f"  Firmware: {info.get('firmVer', '?')}")
    lines.append(f"  Build: {info.get('buildDay', '?')}")
    lines.append(f"  Serial: {info.get('serial', '?')}")
    lines.append(f"  Kanäle: {info.get('channelNum', '?')}")
    lines.append(f"  Typ: {info.get('exactType', '?')}")
    lines.append(f"  Hardware: {info.get('hardVer', '?')}")
    # Get RTSP port info
    net, _ = _api("GetNetPort")
    if net:
        port = net[0]["value"]["NetPort"]
        lines.append(f"  RTSP-Port: {port.get('rtspPort', '?')}")
        lines.append(f"  ONVIF-Port: {port.get('onvifPort', '?')}")
        lines.append(f"  HTTP-Port: {port.get('httpPort', '?')}")
    return "\n".join(lines)


def reolink_get_records(channel=0, year=2026, month=7, day=8):
    channel = int(channel)
    body = [{"cmd": "GetRecData", "action": 0, "param": {
        "channel": channel, "onlyCount": 0,
        "year": int(year), "month": int(month), "day": int(day)
    }}]
    data, err = _api("GetRecData", body=body, method="POST")
    if err:
        return err
    return f"📹 Aufnahmen für Ch{channel} am {day}.{month}.{year}:\n{json.dumps(data, ensure_ascii=False, indent=2)[:2000]}"


PROMPT_EXTRA = (
    "REOLINK (Überwachungskameras – Home Hub auf 192.168.178.190):\n"
    "  - **reolink_get_channels**: Alle Kameras mit Status anzeigen\n"
    "  - **reolink_get_snapshot(channel=0)**: Schnappschuss einer Kamera\n"
    "  - **reolink_get_ai_state(channel=0)**: KI-Erkennungsstatus (Person/Fahrzeug/Tier)\n"
    "  - **reolink_get_rtsp_url(channel=0)**: RTSP-Stream-URL für Live-Ansicht\n"
    "  - **reolink_get_device_info**: Geräte-Informationen\n"
    "  - **reolink_get_records(channel=0, year=2026, month=7, day=8)**: Aufnahmen eines Datums\n"
    "  Kameras: Ch0=Terrasse, Ch1=Hof, Ch2=Eckterrasse (alle Batterie, schlafen standardmäßig)\n"
    "  Bei 'Kamera schläft': Schnappschuss nicht möglich – Kamera wacht bei Bewegung auf.\n"
)
