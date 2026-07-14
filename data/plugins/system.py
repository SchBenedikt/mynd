import json
import os
import platform
import re
import shutil
import subprocess
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests

TOOL_SCHEMA = True
TIMER_FILE = Path(__file__).resolve().parents[2] / "data" / "timers.json"
_timers_lock = threading.Lock()

TOOLS = [
    {
        "name": "system_get_info",
        "description": "Server-Informationen (Disk, RAM, CPU, Uptime, OS, Python-Version)",
        "parameters": {}
    },
    {
        "name": "system_get_disk_usage",
        "description": "Festplattenbelegung aller wichtigen Mountpoints",
        "parameters": {}
    },
    {
        "name": "system_get_processes",
        "description": "Top-Prozesse nach CPU-Auslastung",
        "parameters": {"top_n": {"type": "number", "description": "Anzahl an Prozessen (default: 10)"}}
    },
    {
        "name": "system_get_network",
        "description": "Netzwerk-Interfaces und IP-Adressen",
        "parameters": {}
    },
    {
        "name": "timer_set",
        "description": "Einen Timer/Erinnerung setzen (wird im Hintergrund gespeichert)",
        "parameters": {
            "label": {"type": "string", "description": "Name/Bezeichnung des Timers"},
            "seconds": {"type": "number", "description": "Sekunden bis zum Ablauf"},
            "minutes": {"type": "number", "description": "Minuten bis zum Ablauf (alternativ zu seconds)"},
            "hours": {"type": "number", "description": "Stunden bis zum Ablauf (alternativ zu seconds/minutes)"}
        }
    },
    {
        "name": "timer_list",
        "description": "Alle aktiven Timer und abgelaufenen Timer anzeigen",
        "parameters": {}
    },
    {
        "name": "timer_remove",
        "description": "Einen Timer löschen",
        "parameters": {"id": {"type": "string", "description": "ID des Timers"}}
    },
    {
        "name": "weather_get",
        "description": "Aktuelles Wetter abfragen (Temperatur, Regen, Wind, Luftfeuchtigkeit) via Home Assistant oder Open-Meteo",
        "parameters": {
            "latitude": {"type": "number", "description": "Breitengrad (optional, default: 48.85 für München)"},
            "longitude": {"type": "number", "description": "Längengrad (optional, default: 11.5 für München)"}
        }
    },
    {
        "name": "weather_forecast",
        "description": "Wettervorhersage für die nächsten Tage abfragen",
        "parameters": {
            "days": {"type": "number", "description": "Anzahl Tage (1-7, default: 3)"},
            "latitude": {"type": "number", "description": "Breitengrad (optional)"},
            "longitude": {"type": "number", "description": "Längengrad (optional)"}
        }
    },
    {
        "name": "web_search",
        "description": "Internetsuche – aktuelle Informationen, Nachrichten, Fakten aus dem Web",
        "parameters": {
            "query": {"type": "string", "description": "Suchbegriff"},
            "max_results": {"type": "number", "description": "Maximale Ergebnisanzahl (default: 5)"}
        }
    },
    {
        "name": "system_save_text",
        "description": "Speichert Text/Inhalt in eine Datei im generated/-Verzeichnis. Für Berichte, Zusammenfassungen, Exporte.",
        "parameters": {
            "filename": {"type": "string", "description": "Dateiname (z.B. 'bericht.md', 'daten.csv'). Überschreibt existierende Dateien nicht."},
            "content": {"type": "string", "description": "Vollständiger Inhalt"},
            "description": {"type": "string", "description": "Kurzbeschreibung für die Chat-Anzeige (optional)"}
        },
        "required": ["filename", "content"]
    },
]


def _get_uptime():
    try:
        if platform.system() == "Darwin":
            r = subprocess.run(["sysctl", "-n", "kern.boottime"], capture_output=True, text=True)
            m = re.search(r"sec\s*=\s*(\d+)", r.stdout)
            if m:
                boot_sec = int(m.group(1))
                now = time.time()
                up_secs = now - boot_sec
                days = int(up_secs // 86400)
                hours = int((up_secs % 86400) // 3600)
                mins = int((up_secs % 3600) // 60)
                return f"{days} Tage, {hours}h {mins}m"
            return r.stdout.strip()
        elif platform.system() == "Linux":
            with open("/proc/uptime") as f:
                up_secs = float(f.read().split()[0])
            days = int(up_secs // 86400)
            hours = int((up_secs % 86400) // 3600)
            mins = int((up_secs % 3600) // 60)
            return f"{days} Tage, {hours}h {mins}m"
        return "Unbekannt"
    except Exception:
        return "Unbekannt"


def _get_load():
    try:
        if platform.system() == "Darwin":
            r = subprocess.run(["sysctl", "-n", "vm.loadavg"], capture_output=True, text=True)
            return r.stdout.strip()
        elif platform.system() == "Linux":
            with open("/proc/loadavg") as f:
                return " ".join(f.read().split()[:3])
        return "Unbekannt"
    except Exception:
        return "Unbekannt"


def _get_cpu():
    try:
        if platform.system() == "Darwin":
            r = subprocess.run(["sysctl", "-n", "hw.ncpu"], capture_output=True, text=True)
            cores = r.stdout.strip()
            r2 = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True)
            model = r2.stdout.strip()
            r3 = subprocess.run(["ps", "-A", "-o", "%cpu"], capture_output=True, text=True)
            lines = r3.stdout.strip().split("\n")[1:]
            usage = sum(float(line.strip()) for line in lines if line.strip()) / int(cores) if int(cores) else 0
            return f"{model} ({cores} Kerne, ~{usage:.0f}% Auslastung)"
        elif platform.system() == "Linux":
            with open("/proc/cpuinfo") as f:
                model = "?"
                for line in f:
                    if "model name" in line:
                        model = line.split(":")[1].strip()
                        break
            cores = os.cpu_count() or "?"
            return f"{model} ({cores} Kerne)"
        return str(platform.processor() or "Unbekannt")
    except Exception:
        return "Unbekannt"


def _get_ram():
    try:
        if platform.system() == "Darwin":
            r = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True)
            total_gb = int(r.stdout.strip()) / 1024**3
            r2 = subprocess.run(["vm_stat"], capture_output=True, text=True)
            free_match = re.search(r"Pages free:\s+(\d+)", r2.stdout)
            free_gb = int(free_match.group(1)) * 16384 / 1024**3 if free_match else 0
            used_gb = total_gb - free_gb
            pct = (used_gb / total_gb) * 100 if total_gb else 0
            return f"{used_gb:.1f} GB / {total_gb:.1f} GB ({pct:.0f}%)"
        elif platform.system() == "Linux":
            with open("/proc/meminfo") as f:
                mem = {}
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        k = parts[0].strip()
                        v = parts[1].strip().split()[0]
                        mem[k] = int(v)
            total = mem.get("MemTotal", 0) / 1024**2
            available = mem.get("MemAvailable", 0) / 1024**2
            used = total - available
            pct = (used / total) * 100 if total else 0
            return f"{used:.1f} GB / {total:.1f} GB ({pct:.0f}%)"
        return "Unbekannt"
    except Exception:
        return "Unbekannt"


def _load_timers():
    with _timers_lock:
        if TIMER_FILE.exists():
            return json.loads(TIMER_FILE.read_text())
    return []


def _save_timers(timers):
    with _timers_lock:
        TIMER_FILE.parent.mkdir(parents=True, exist_ok=True)
        TIMER_FILE.write_text(json.dumps(timers, indent=2, ensure_ascii=False))


def system_get_info():
    lines = ["🖥 **Server-Info**"]
    lines.append(f"  OS: {platform.system()} {platform.release()} ({platform.version()})")
    lines.append(f"  Hostname: {platform.node()}")
    lines.append(f"  Python: {platform.python_version()}")
    lines.append(f"  CPU: {_get_cpu()}")
    lines.append(f"  RAM: {_get_ram()}")
    lines.append(f"  Uptime: {_get_uptime()}")
    lines.append(f"  Load: {_get_load()}")
    return "\n".join(lines)


def system_get_disk_usage():
    lines = ["💾 **Festplattenbelegung**"]
    if platform.system() == "Darwin":
        mounts = ["/", "/System/Volumes/Data", "/Users"]
        seen = set()
        try:
            for m in mounts:
                u = shutil.disk_usage(m)
                total_gb = u.total / 1024**3
                used_gb = u.used / 1024**3
                free_gb = u.free / 1024**3
                pct = (u.used / u.total) * 100
                key = f"{total_gb:.0f}"
                if key not in seen:
                    lines.append(f"  `{m}`: {used_gb:.1f} GB / {total_gb:.1f} GB ({pct:.0f}% belegt, {free_gb:.1f} GB frei)")
                    seen.add(key)
        except OSError:
            pass
        else:
            try:
                r = subprocess.run(["df", "-h"], capture_output=True, text=True)
                for line in r.stdout.strip().split("\n")[1:]:
                    parts = line.split()
                    if len(parts) >= 6 and parts[0].startswith("/"):
                        lines.append(f"  `{parts[-1]}`: {parts[2]} / {parts[1]} ({parts[4]} belegt)")
            except OSError:
                pass
    return "\n".join(lines)


def system_get_processes(top_n=10):
    top_n = int(top_n)
    try:
        if platform.system() == "Darwin":
            r = subprocess.run(["ps", "axo", "pid,%cpu,%mem,comm", "-r"], capture_output=True, text=True, timeout=5)
        else:
            r = subprocess.run(["ps", "axo", "pid,%cpu,%mem,comm", "--sort=-%cpu"], capture_output=True, text=True, timeout=5)
        lines = [f"⚙️ **Top {top_n} Prozesse (nach CPU)**", "  PID   CPU%  MEM%  COMMAND"]
        for line in r.stdout.strip().split("\n")[1:top_n+1]:
            lines.append(f"  {line.strip()}")
        return "\n".join(lines)
    except subprocess.TimeoutExpired:
        return "❌ Prozessabfrage timeout"
    except Exception as e:
        return f"❌ {e}"


def system_get_network():
    lines = ["🌐 **Netzwerk-Interfaces**"]
    try:
        try:
            import netifaces
            for iface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(iface)
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr.get("addr", "")
                        if ip and not ip.startswith("127."):
                            lines.append(f"  `{iface}`: {ip}")
                if netifaces.AF_LINK in addrs:
                    for addr in addrs[netifaces.AF_LINK]:
                        mac = addr.get("addr", "")
                        if mac and mac != "00:00:00:00:00:00":
                            lines.append(f"  `{iface}` MAC: {mac}")
        except ImportError:
            r = subprocess.run(["ifconfig", "-l"], capture_output=True, text=True, timeout=5)
            ifaces = r.stdout.strip().split()
            for iface in ifaces:
                r2 = subprocess.run(["ifconfig", iface], capture_output=True, text=True, timeout=5)
                for line in r2.stdout.split("\n"):
                    line = line.strip()
                    if line.startswith("inet ") and "127.0.0.1" not in line:
                        ip = line.split()[1]
                        lines.append(f"  `{iface}`: {ip}")
    except Exception as e:
        lines.append(f"  (Fehler: {e})")
    return "\n".join(lines)


def timer_set(label="Timer", seconds=None, minutes=None, hours=None):
    total_seconds = 0
    if seconds:
        total_seconds += int(seconds)
    if minutes:
        total_seconds += int(minutes) * 60
    if hours:
        total_seconds += int(hours) * 3600
    if total_seconds <= 0:
        total_seconds = 60  # default 1 minute

    timers = _load_timers()
    now = time.time()
    expiry = now + total_seconds
    tid = str(uuid.uuid4())[:8]
    human = ""
    if total_seconds >= 3600:
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        human = f"{h}h {m}m"
    elif total_seconds >= 60:
        m = total_seconds // 60
        s = total_seconds % 60
        human = f"{m}m {s}s" if s else f"{m}m"
    else:
        human = f"{total_seconds}s"

    timers.append({"id": tid, "label": label, "expiry": expiry,
                   "duration": human, "created": datetime.now().isoformat(),
                   "expired": False})
    _save_timers(timers)
    return f"⏰ Timer **„{label}“** gesetzt auf {human} (ID: `{tid}`)"


def timer_list():
    timers = _load_timers()
    now = time.time()
    active = []
    expired = []
    for t in timers:
        if t["expiry"] <= now:
            expired.append(t)
        elif t["expiry"] > now:
            remaining = int(t["expiry"] - now)
            h = remaining // 3600
            m = (remaining % 3600) // 60
            s = remaining % 60
            if h > 0:
                t["remaining"] = f"{h}h {m}m"
            elif m > 0:
                t["remaining"] = f"{m}m {s}s"
            else:
                t["remaining"] = f"{s}s"
            active.append(t)
        else:
            expired.append(t)

    lines = []
    if active:
        lines.append("⏳ **Aktive Timer:**")
        for t in active:
            lines.append(f"  `{t['id']}` **{t['label']}** – noch {t['remaining']}")
    if expired:
        lines.append("\n🔔 **Abgelaufene Timer:**")
        for t in expired[-5:]:
            lines.append(f"  `{t['id']}` **{t['label']}** – abgelaufen")
    if not active and not expired:
        lines.append("Keine Timer gesetzt.")
    return "\n".join(lines)


def timer_remove(tid):
    timers = _load_timers()
    before = len(timers)
    timers = [t for t in timers if t["id"] != tid]
    if len(timers) < before:
        _save_timers(timers)
        return f"🗑️ Timer `{tid}` gelöscht."
    return f"❌ Timer `{tid}` nicht gefunden."


# ── Wetter ─────────────────────────────────────────────

def _ha_get_weather():
    """Try to get weather via Home Assistant sensors."""
    try:
        vf = Path(__file__).parent.parent / 'vault.json'
        if not vf.exists():
            return None
        v = json.loads(vf.read_text())
        url = v.get("homeassistant/url", "")
        token = v.get("homeassistant/token", "")
        if not url or not token:
            return None
        url = url.rstrip('/')
        h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        r = requests.get(f"{url}/api/states", headers=h, timeout=10)
        if r.status_code != 200:
            return None
        states = r.json()
        temp = None
        humidity = None
        pressure = None
        condition = None
        wind_speed = None
        for s in states:
            eid = s["entity_id"]
            attrs = s.get("attributes", {})
            st = s.get("state", "")
            if not eid.startswith("sensor."):
                continue
            fn = (attrs.get("friendly_name") or eid).lower()
            st_clean = (st.replace("°", "").replace("C", "").replace("F", "")
                       .replace("%", "").replace("hPa", "").replace("mbar", "")
                       .replace("km/h", "").replace("m/s", "").strip())
            if temp is None:
                for kw in ["aussentemperatur", "outdoor_temp", "aussen_temp",
                           "temperatur_aussen", "temperature_outdoor",
                           "temp_outdoor", "temperature"]:
                    if kw in fn and "chip" not in fn and "cpu" not in fn and "gpu" not in fn:
                        try:
                            temp = round(float(st_clean), 1)
                        except ValueError:
                            pass
                        break
            if temp is None and "temp" in fn and "chip" not in fn and "cpu" not in fn and "gpu" not in fn:
                try:
                    val = float(st_clean)
                    if -30 < val < 60:
                        temp = round(val, 1)
                except ValueError:
                    pass
            if humidity is None and any(x in fn for x in ["luftfeuchte", "humidity", "feuchte"]):
                try:
                    humidity = round(float(st_clean), 0)
                except ValueError:
                    pass
            if pressure is None and any(x in fn for x in ["luftdruck", "pressure"]):
                try:
                    pressure = round(float(st_clean), 0)
                except ValueError:
                    pass
            if wind_speed is None and any(x in fn for x in ["windgeschwindigkeit", "wind_speed", "windstärke", "wind_strength"]):
                try:
                    wind_speed = round(float(st_clean), 1)
                except ValueError:
                    pass
            if condition is None and any(x in fn for x in ["wetterzustand", "weather_condition", "wetter", "weather_cond"]):
                condition = st
        if temp is not None:
            condition_line = f"🌤️ **{condition}**" if condition else "🌤️ **Wetter aktuell**"
            lines = [condition_line]
            lines.append(f"  🌡️ Temperatur: {temp}°C")
            if humidity:
                lines.append(f"  💧 Luftfeuchte: {humidity}%")
            if pressure:
                lines.append(f"  🌀 Luftdruck: {pressure} hPa")
            if wind_speed:
                lines.append(f"  💨 Wind: {wind_speed} km/h")
            return "\n".join(lines)
        return None
    except Exception:
        return None


def _om_weather(lat, lon):
    """Open-Meteo API – kein API-Key nötig."""
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,pressure_msl",
                "timezone": "auto"
            },
            timeout=10
        )
        if r.status_code != 200:
            return f"❌ Open-Meteo Fehler: {r.status_code}"
        d = r.json()
        c = d.get("current", {})
        wmo = c.get("weather_code", 0)
        wmo_map = {0: "☀️ Sonnig", 1: "🌤️ Überwiegend klar", 2: "⛅ Teilweise bewölkt",
                   3: "☁️ Bewölkt", 45: "🌫️ Nebelig", 48: "🌫️ Reifnebel",
                   51: "🌦️ Leichter Niesel", 53: "🌦️ Mäßiger Niesel", 55: "🌧️ Starker Niesel",
                   61: "🌦️ Leichter Regen", 63: "🌧️ Mäßiger Regen", 65: "🌧️ Starker Regen",
                   71: "🌨️ Leichter Schnee", 73: "🌨️ Mäßiger Schnee", 75: "🌨️ Starker Schnee",
                   80: "🌦️ Leichte Schauer", 81: "🌧️ Mäßige Schauer", 82: "🌧️ Starke Schauer",
                   95: "⛈️ Gewitter", 96: "⛈️ Gewitter mit Hagel", 99: "⛈️ Starkes Gewitter mit Hagel"}
        condition = wmo_map.get(wmo, f"☁️ Code {wmo}")
        temp = c.get("temperature_2m")
        feels = c.get("apparent_temperature")
        humidity = c.get("relative_humidity_2m")
        precip = c.get("precipitation", 0)
        wind = c.get("wind_speed_10m")
        pressure = c.get("pressure_msl")
        lines = [condition]
        if temp is not None:
            lines.append(f"  🌡️ {temp}°C (gefühlt {feels}°C)")
        if humidity:
            lines.append(f"  💧 {humidity}% Luftfeuchte")
        if precip:
            lines.append(f"  🌧️ {precip} mm Niederschlag")
        if wind:
            lines.append(f"  💨 {wind} km/h Wind")
        if pressure:
            lines.append(f"  🌀 {pressure} hPa")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Wetterfehler: {e}"


def weather_get(latitude=48.85, longitude=11.5):
    lat = float(latitude)
    lon = float(longitude)
    result = _ha_get_weather()
    if result:
        return result
    return _om_weather(lat, lon)


def weather_forecast(days=3, latitude=48.85, longitude=11.5):
    lat = float(latitude)
    lon = float(longitude)
    days = min(max(int(days), 1), 7)
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat, "longitude": lon,
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
                "forecast_days": days, "timezone": "auto"
            },
            timeout=10
        )
        if r.status_code != 200:
            return f"❌ Fehler: {r.status_code}"
        d = r.json()
        daily = d.get("daily", {})
        dates = daily.get("time", [])
        if not dates:
            return "❌ Keine Wetterdaten verfügbar."
        codes = daily.get("weather_code", [])
        tmax = daily.get("temperature_2m_max", [])
        tmin = daily.get("temperature_2m_min", [])
        rain = daily.get("precipitation_sum", [])
        wind = daily.get("wind_speed_10m_max", [])
        wmo_map = {0: "☀️", 1: "🌤️", 2: "⛅", 3: "☁️", 45: "🌫️", 51: "🌦️",
                   61: "🌧️", 71: "🌨️", 80: "🌦️", 95: "⛈️"}
        lines = [f"📅 **Wettervorhersage ({days} Tage)**"]
        for i in range(len(dates)):
            wmo = wmo_map.get(codes[i] if i < len(codes) else 0, "☁️")
            hi = tmax[i] if i < len(tmax) else "?"
            lo = tmin[i] if i < len(tmin) else "?"
            rr = rain[i] if i < len(rain) else 0
            ww = wind[i] if i < len(wind) else "?"
            lines.append(f"  {dates[i]}: {wmo} {hi}/{lo}°C 🌧️{rr}mm 💨{ww}km/h")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ {e}"


# ── Web Search ──────────────────────────────────────────

def web_search(query, max_results=5):
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS
    max_results = int(max_results)
    try:
        with DDGS() as client:
            results = list(client.text(query, max_results=max_results))
        if not results:
            return f"❌ Keine Ergebnisse für '{query}'."
        lines = [f"🔍 **Web-Suche: {query}**"]
        for i, r in enumerate(results[:max_results], 1):
            title = r.get("title", "?")
            href = r.get("href", r.get("link", ""))
            snippet = (r.get("body", "") or "")[:200]
            lines.append(f"\n**{i}. {title}**")
            lines.append(f"  {snippet}")
            if href:
                lines.append(f"  🔗 {href}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Web-Suche fehlgeschlagen: {e}"


# ── Text speichern ──────────────────────────────────────

_GENERATED_DIR = Path(__file__).resolve().parents[2] / 'data' / 'generated'

def system_save_text(filename, content, description=''):
    filename = filename.strip().replace(' ', '_')
    if '..' in filename or '/' in filename:
        return '❌ Ungültiger Dateiname.'
    target = _GENERATED_DIR / filename
    if target.exists():
        return f'❌ Datei {filename} existiert bereits.'
    _GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding='utf-8')
    label = f' – {description}' if description else ''
    return f'✅ Datei `{filename}` erstellt ({len(content)} Bytes){label}'


PROMPT_EXTRA = (
    "SYSTEM (Server-Informationen, Timer, Wetter & Web-Suche):\n"
    "  - **system_get_info**: Server-Details (CPU, RAM, OS, Uptime, Python-Version)\n"
    "  - **system_get_disk_usage**: Festplattenbelegung\n"
    "  - **system_get_processes(top_n=10)**: Top-Prozesse nach CPU\n"
    "  - **system_get_network**: Netzwerk-Interfaces und IPs\n"
    "  - **timer_set(label='Timer', seconds=60)**: Timer/Wecker/Erinnerung setzen\n"
    "  - **timer_list**: Alle Timer anzeigen\n"
    "  - **timer_remove(id)**: Timer löschen\n"
    "  - **weather_get(latitude=48.85, longitude=11.5)**: Aktuelles Wetter (Temperatur, Regen, Wind)\n"
    "  - **weather_forecast(days=3, latitude=48.85, longitude=11.5)**: Wettervorhersage für die nächsten Tage\n"
    "  - **web_search(query, max_results=5)**: Internetsuche für aktuelle Infos, Nachrichten, Fakten\n"
    "  - **system_save_text(filename, content, description)**: Speichert Text/Inhalt als Datei\n"
    "  HA-Wetter: Nutzt Home-Assistant-Sensoren (Temperatur, Feuchte, Wind) falls verfügbar\n"
    "  Fallback: Open-Meteo (kostenlos, kein API-Key)\n"
    "  Web-Suche: DuckDuckGo (anonym, kein API-Key)\n"
)
