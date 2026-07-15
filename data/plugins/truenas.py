import base64
import json
from pathlib import Path

import requests

from core.vault import load_vault

VAULT_FILE = Path(__file__).resolve().parents[1] / 'vault.json'


def _vault():
    return load_vault(VAULT_FILE)


def _find_ip():
    v = _vault()
    for k, val in v.items():
        if k.endswith('/ip') and 'truenas' in k.lower():
            ip = val.strip()
            user = v.get(f'truenas/{ip}/user', 'root')
            pw = v.get(f'truenas/{ip}/password', '')
            return ip, user, pw
    return None, None, None


def _basic_auth(user, pw):
    raw = f'{user}:{pw}'.encode()
    return 'Basic ' + base64.b64encode(raw).decode('ascii')


def _conn():
    ip, user, pw = _find_ip()
    if not ip:
        return None, None, '❌ Keine TrueNAS-IP im Vault'
    url = f'http://{ip}/api/v2.0'
    h = {'Content-Type': 'application/json'}
    if user:
        h['Authorization'] = _basic_auth(user, pw)
    return url, h, None


def _api(path, method='GET', body=None):
    ip, user, pw = _find_ip()
    if not ip:
        return None, '❌ Keine TrueNAS-IP im Vault'
    try:
        url = f'http://{ip}/api/v2.0/{path.lstrip("/")}'
        h = {'Content-Type': 'application/json'} if body else {}
        if user:
            h['Authorization'] = _basic_auth(user, pw)
        r = requests.request(method, url,
                             json=body if body else None, headers=h, timeout=30)
        if r.status_code in (200, 201):
            try:
                return r.json(), None
            except (json.JSONDecodeError, ValueError):
                return r.text.strip(), None
        try:
            msg = r.json().get('error', r.text[:300])
        except Exception:
            msg = r.text[:300]
        return None, f'❌ Status {r.status_code}: {msg}'
    except requests.exceptions.ConnectTimeout:
        return None, '❌ Zeitüberschreitung'
    except requests.exceptions.ConnectionError:
        return None, '❌ Keine Verbindung'
    except Exception as e:
        return None, f'❌ {e}'


def _fmt_bytes(b):
    b = int(b)
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if b < 1024:
            return f'{b:.1f} {unit}'
        b /= 1024
    return f'{b:.1f} PB'


# ── Generic API Request ──────────────────────────────

def truenas_api_request(endpoint, method='GET', body=None):
    """Beliebiger TrueNAS-API-Aufruf – nutze DAS für alle Endpoints ohne eigene Funktion."""
    try:
        data, err = _api(endpoint, method, body)
        if err:
            return err
        return json.dumps(data, ensure_ascii=False, indent=2, default=str)[:3000]
    except Exception as e:
        return f'❌ {e}'


# ── System Info ──────────────────────────────────────

def truenas_get_system_info():
    try:
        data, err = _api('system/info')
        if err:
            return err
        lines = ['🖥 **TrueNAS System**']
        lines.append(f"  Hostname: {data.get('hostname', '?')}")
        lines.append(f"  Version: {data.get('version', '?')}")
        lines.append(f"  Build: {data.get('buildtime', {}).get('$date', '?')}")
        lines.append(f"  Modell: {data.get('model', '?')}")
        lines.append(f"  RAM: {_fmt_bytes(data.get('physmem', 0))}")
        uptime = data.get('uptime_seconds', 0)
        if uptime:
            d = int(uptime // 86400)
            h = int((uptime % 86400) // 3600)
            m = int((uptime % 3600) // 60)
            lines.append(f"  Uptime: {d}T {h}h {m}m")
        lines.append(f"  System-Serial: {data.get('system_serial', '?')}")
        lines.append(f"  License: {data.get('license', 'Nicht lizenziert (Community)')}")
        return '\n'.join(lines)
    except Exception as e:
        return f'❌ {e}'


def truenas_get_version():
    data, err = _api('system/version')
    if err:
        return err
    return f'TrueNAS-Version: {data}'


# ── Storage ──────────────────────────────────────────

def truenas_list_pools():
    try:
        data, err = _api('pool')
        if err:
            return err
        if not data:
            return '❌ Keine Pools gefunden.'
        lines = ['💾 **Storage Pools**']
        for p in data:
            name = p.get('name', '?')
            status = p.get('status', '?')
            healthy = '✅' if p.get('healthy') else '⚠️'
            total = p.get('size_str', '?')
            used = p.get('allocated_str', '?')
            free = p.get('free_str', '?')
            lines.append(f"  {healthy} **{name}** ({status})")
            lines.append(f"    Belegt: {used} / {total} (Frei: {free})")
            encrypt = p.get('encrypt', 0)
            if encrypt:
                lines.append("    🔒 Verschlüsselt")
            # Get pool topology
            topo = p.get('topology', {})
            for ttype in ('data', 'log', 'cache', 'spare', 'dedup'):
                vdevs = topo.get(ttype, [])
                if isinstance(vdevs, list) and vdevs:
                    disk_names = []
                    for v in vdevs:
                        pth = v.get('path', '')
                        disk = pth.split('/')[-1] if pth else v.get('disk', v.get('name', '?'))
                        disk_names.append(disk)
                    lines.append(f"    {ttype}: {', '.join(disk_names)}")
        return '\n'.join(lines)
    except Exception as e:
        return f'❌ {e}'


def truenas_list_datasets():
    try:
        data, err = _api('pool/dataset')
        if err:
            return err
        if not data:
            return '❌ Keine Datasets gefunden.'
        lines = ['📂 **Datasets**']
        for d in data:
            name = d.get('name', d.get('id', '?'))
            pool = d.get('pool', '?')
            used = _fmt_bytes(d.get('used', 0)) if d.get('used') else '-'
            avail = _fmt_bytes(d.get('available', 0)) if d.get('available') else '-'
            refer = _fmt_bytes(d.get('referenced', 0)) if d.get('referenced') else '-'
            mount = d.get('mountpoint', '?')
            compress = d.get('compression', '?')
            dedup = d.get('deduplication', '?')
            atime = d.get('atime', '?')
            encrypt = d.get('encrypted', False)
            enc_tag = ' 🔒' if encrypt else ''
            lines.append(f"  📁 **{name}**{enc_tag}")
            lines.append(f"    Belegt: {used} · Verfügbar: {avail} · Referenziert: {refer}")
            lines.append(f"    Mount: `{mount}` | Pool: {pool}")
            lines.append(f"    Compress: {compress} | Dedup: {dedup} | Atime: {atime}")
        return '\n'.join(lines)
    except Exception as e:
        return f'❌ {e}'


def truenas_list_disks():
    try:
        data, err = _api('disk')
        if err:
            return err
        if not data:
            return '❌ Keine Disks gefunden.'
        lines = ['💽 **Festplatten**']
        for d in data:
            name = d.get('name', '?')
            serial = d.get('serial', '?')
            size = _fmt_bytes(d.get('size', 0)) if d.get('size') else '?'
            model = d.get('model', '?')
            type_ = d.get('type', '?')
            hdd = '🔴 HDD' if 'hdd' in type_ else '🔵 SSD' if 'ssd' in type_ else '💽'
            pool = d.get('pool', '-')
            temp = d.get('temperature', None)
            temp_str = f' 🌡️{temp}°C' if isinstance(temp, (int, float)) else ''
            lines.append(f"  {hdd} `{name}` {size}{temp_str}")
            lines.append(f"    Serie: {serial} | Pool: {pool} | {model}")
        return '\n'.join(lines)
    except Exception as e:
        return f'❌ {e}'


# ── Services ─────────────────────────────────────────

def truenas_list_services():
    try:
        data, err = _api('service')
        if err:
            return err
        if not data:
            return '❌ Keine Services gefunden.'
        lines = ['⚙️ **Dienste**']
        for s in data:
            name = s.get('service', '?')
            state = s.get('state', '')
            pids = s.get('pids', [])
            running = '🟢 Aktiv' if state == 'RUNNING' else '🔴 Gestoppt'
            enable = s.get('enable', False)
            boot = '🔄 Autostart' if enable else ''
            lines.append(f"  {running} **{name}** {boot}")
            if pids:
                lines.append(f"    PID(s): {', '.join(str(p) for p in pids)}")
        return '\n'.join(lines)
    except Exception as e:
        return f'❌ {e}'


# ── Alerts ───────────────────────────────────────────

def truenas_list_alerts():
    try:
        data, err = _api('alert/list')
        if err:
            return err
        if not data:
            return '✅ Keine Alarme.'
        lines = ['🔔 **TrueNAS Alarme**']
        for a in data:
            level = a.get('level', '?')
            formatted = a.get('formatted', '?')
            icon = '🔴' if level == 'CRITICAL' else '🟡' if level == 'WARNING' else '🔵'
            node = a.get('node', '?')
            lines.append(f"  {icon} **{level}** – {formatted[:200]}")
            if node and node != 'A':
                lines.append(f"    Node: {node}")
        return '\n'.join(lines)
    except Exception as e:
        return f'❌ {e}'


# ── Shares ───────────────────────────────────────────

def truenas_list_shares():
    try:
        lines = ['📁 **Freigaben**']
        # NFS
        nfs, err = _api('sharing/nfs')
        if not err and nfs:
            lines.append(f'\n  **NFS-Freigaben ({len(nfs)})**')
            for s in nfs:
                path = s.get('path', '?')
                networks = ', '.join(s.get('networks', ['alle']))
                comment = s.get('comment', '')
                lines.append(f"    📂 `{path}` – Netz: {networks}")
                if comment:
                    lines.append(f"       {comment}")
        else:
            lines.append('\n  NFS: Keine')
        # SMB
        smb, err2 = _api('sharing/smb')
        if not err2 and smb:
            lines.append(f'\n  **SMB-Freigaben ({len(smb)})**')
            for s in smb:
                name = s.get('name', '?')
                path = s.get('path', '?')
                browseable = '🔍' if s.get('browseable') else ''
                guest = '👤 Gast-Zugriff' if s.get('guestok') else ''
                enabled = '✅' if s.get('enabled') else '❌'
                lines.append(f"    {enabled} **{name}** – `{path}` {browseable} {guest}")
        else:
            lines.append('\n  SMB: Keine')
        # iSCSI
        iscsi, err3 = _api('iscsi/portal')
        if not err3 and iscsi:
            lines.append(f'\n  **iSCSI ({len(iscsi)} Portale)**')
        return '\n'.join(lines)
    except Exception as e:
        return f'❌ {e}'


# ── Update ───────────────────────────────────────────

def truenas_check_update():
    data, err = _api('update/status')
    if err:
        return err
    cur_data, cur_err = _api('system/version')
    current = str(cur_data).strip('"').strip("'") if not cur_err else '?'
    lines = [f'Aktuelle Version: {current}']
    if isinstance(data, dict):
        status = data.get('status', {})
        new = status.get('new_version', {})
        if isinstance(new, dict) and new.get('version'):
            ver = new['version']
            manifest = new.get('manifest', {})
            lines.append(f'Neue Version: {ver}')
            if manifest.get('date'):
                lines.append(f'Veröffentlicht: {manifest["date"][:10]}')
            if manifest.get('filesize'):
                mb = manifest['filesize'] / 1024 / 1024
                lines.append(f'Größe: {mb:.0f} MB')
            if new.get('release_notes'):
                lines.append(f'\nRelease Notes:\n{new["release_notes"][:1500]}')
        code = data.get('code', '')
        if code == 'NORMAL':
            lines.append('\nStatus: ✅ Bereit zur Installation')
        elif code == 'DOWNLOADING':
            pct = data.get('status', {}).get('download_percent', 0)
            lines.append(f'\nStatus: ⬇️ Herunterladen ({pct}%)')
        elif code == 'REBOOT_REQUIRED':
            lines.append('\nStatus: 🔄 Neustart erforderlich')
        elif code == 'UPDATING':
            lines.append('\nStatus: 🔧 Update läuft')
        else:
            lines.append(f'\nStatus: {code}')
    return '\n'.join(lines)[:2000] if lines else str(data)[:500]


# ── Users ────────────────────────────────────────────

def truenas_list_users():
    try:
        data, err = _api('user')
        if err:
            return err
        lines = ['👤 **Benutzer**']
        for u in data:
            uid = u.get('uid', '?')
            username = u.get('username', '?')
            fullname = u.get('full_name', u.get('fullname', '')) or ''
            builtin = u.get('builtin', False)
            locked = u.get('locked', False)
            groups = ', '.join(str(g) for g in u.get('groups', []) if g) or '-'
            shell = u.get('shell', '?').split('/')[-1]
            icon = '🔧' if builtin else '👤'
            lock = '🔒' if locked else ''
            lines.append(f"  {icon} **{username}** (UID {uid}){lock}")
            if fullname:
                lines.append(f"    Name: {fullname}")
            lines.append(f"    Shell: {shell} | Gruppen: {groups}")
        return '\n'.join(lines)
    except Exception as e:
        return f'❌ {e}'


# ── Apps ─────────────────────────────────────────────

def truenas_list_apps():
    try:
        data, err = _api('app')
        if err:
            return err
        if not data:
            return '❌ Keine Apps installiert.'
        lines = ['📦 **TrueNAS Apps**']
        for a in data:
            name = a.get('name', '?')
            state = a.get('state', a.get('status', '?'))
            version = a.get('version', a.get('app_version', '?')) or '?'
            icon = '🟢' if str(state).upper() in ('RUNNING', 'ACTIVE', 'DEPLOYED') else '🔴'
            lines.append(f"  {icon} **{name}** v{version} – {state}")
            # Get update info
            if a.get('upgrade_available', False):
                lines.append("    ⬆️ Update verfügbar")
        return '\n'.join(lines)
    except Exception as e:
        return f'❌ {e}'


# ── Network ──────────────────────────────────────────

def truenas_list_network():
    try:
        data, err = _api('interface')
        if err:
            # Try alternative endpoint
            data, err = _api('network/interface')
            if err:
                return f'❌ Netzwerk-API nicht verfügbar: {err}'
        if not data:
            # Try getting from interfaces
            lines = ['🌐 **Netzwerk**']
            sys_info, _ = _api('system/info')
            if sys_info and isinstance(sys_info, dict):
                if sys_info.get('hostname'):
                    lines.append(f"  Hostname: {sys_info['hostname']}")
            return '\n'.join(lines)
        lines = ['🌐 **Netzwerk-Interfaces**']
        for iface in data:
            name = iface.get('name', iface.get('id', '?'))
            ip = iface.get('ip_address', iface.get('addresses', [{}]))
            state = iface.get('state', iface.get('link_state', '?'))
            lines.append(f"  `{name}` – {ip} ({state})")
        return '\n'.join(lines)
    except Exception as e:
        return f'❌ {e}'


PLUGIN_NAME = "truenas"
PLUGIN_DESC = "TrueNAS Scale – System, Storage, Services, Apps, Netzwerk, Updates, Alarme"

TOOLS = [
    {"type": "function", "function": {
        "name": "truenas_api_request",
        "description": "Beliebiger TrueNAS-API-Aufruf (v2.0 REST API). Nutze DAS für alle Endpoints ohne eigene Funktion. Path z.B. 'system/info', 'pool', 'pool/dataset', 'service', 'user', 'alert/list', 'app', 'sharing/nfs', 'disk', 'filesystem/listdir'. Body als JSON-Objekt für POST/PUT.",  # noqa: E501
        "parameters": {"type": "object", "properties": {
            "endpoint": {"type": "string", "description": "API-Pfad wie 'system/info', 'pool', 'pool/dataset', 'service', 'user', 'disk'"},
            "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"], "default": "GET"},
            "body": {"type": "object", "description": "JSON-Body für POST/PUT (optional)"}
        }, "required": ["endpoint"]}
    }},
    {"type": "function", "function": {
        "name": "truenas_get_system_info",
        "description": "Detaillierte System-Informationen (CPU, RAM, Hostname, Modell, Version, Uptime, License).",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "truenas_get_version",
        "description": "TrueNAS-Version abrufen (z.B. TrueNAS-25.10.3.1).",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "truenas_list_pools",
        "description": "Liste aller Storage-Pools mit Größe, Belegung, Status und Topologie (VDEVs).",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "truenas_list_datasets",
        "description": "Liste aller Datasets mit Größe, Kompression, Dedup, Verschlüsselung und Mountpoints.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "truenas_list_disks",
        "description": "Liste aller Festplatten mit Größe, Modell, Temperatur, Typ (HDD/SSD) und Pool-Zugehörigkeit.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "truenas_list_services",
        "description": "Liste aller Dienste mit Status (Running/Stopped) und Autostart.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "truenas_list_alerts",
        "description": "Liste aller aktiven TrueNAS-Alarme (Critical, Warning, Info).",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "truenas_list_shares",
        "description": "Liste aller Freigaben (NFS, SMB, iSCSI) mit Pfad und Optionen.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "truenas_list_users",
        "description": "Liste aller Benutzer mit UID, Shell, Gruppen, Lock-Status.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "truenas_list_apps",
        "description": "Liste aller installierten TrueNAS-Apps mit Version und Status.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "truenas_list_network",
        "description": "Liste Netzwerk-Interfaces mit IP-Adressen und Link-State.",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
    {"type": "function", "function": {
        "name": "truenas_check_update",
        "description": "Prüft ob ein TrueNAS-Update verfügbar ist (aktuell/neu/Status/Release-Notes).",
        "parameters": {"type": "object", "properties": {}, "required": []}
    }},
]

TOOL_MAP = {
    'truenas_api_request': truenas_api_request,
    'truenas_get_system_info': truenas_get_system_info,
    'truenas_get_version': truenas_get_version,
    'truenas_list_pools': truenas_list_pools,
    'truenas_list_datasets': truenas_list_datasets,
    'truenas_list_disks': truenas_list_disks,
    'truenas_list_services': truenas_list_services,
    'truenas_list_alerts': truenas_list_alerts,
    'truenas_list_shares': truenas_list_shares,
    'truenas_list_users': truenas_list_users,
    'truenas_list_apps': truenas_list_apps,
    'truenas_list_network': truenas_list_network,
    'truenas_check_update': truenas_check_update,
}

PROMPT_EXTRA = (
    'TRUENAS SCALE (API v2.0 – 192.168.178.44, Vault: truenas/IP/user/password):\n'
    '  - **truenas_api_request(endpoint, method="GET", body={})**: Generischer API-Aufruf\n'
    '  - **truenas_get_system_info**: CPU, RAM, Hostname, Version, Uptime, Lizenz\n'
    '  - **truenas_get_version**: Kurze Versionsabfrage\n'
    '  - **truenas_list_pools**: Storage-Pools mit Topologie (VDEVs, Disks)\n'
    '  - **truenas_list_datasets**: Alle Datasets (Größe, Kompression, Mountpoints)\n'
    '  - **truenas_list_disks**: Physikalische Festplatten (HDD/SSD, Temperatur, Pool)\n'
    '  - **truenas_list_services**: Dienste mit Status (SMB, NFS, SSH, UPS, S3, …)\n'
    '  - **truenas_list_alerts**: Kritische/Warning-Alarme\n'
    '  - **truenas_list_shares**: NFS- und SMB-Freigaben\n'
    '  - **truenas_list_users**: Benutzer mit UID, Shell, Gruppen\n'
    '  - **truenas_list_apps**: Installierte Apps (Version, Status, Updates)\n'
    '  - **truenas_list_network**: Netzwerk-Interfaces\n'
    '  - **truenas_check_update**: Update-Status + Release Notes\n'
    '  Per truenas_api_request sind ALLE API-Endpoints erreichbar:\n'
    '    pool, pool/dataset, disk, service, alert/list, sharing/nfs, sharing/smb,\n'
    '    user, group, app, system/version, system/info, system/advanced,\n'
    '    cronjob, rsynctask, replication, cloudsync, iscsi/portal, filesystem/listdir\n'
)
