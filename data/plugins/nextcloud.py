import html as _html
import json
import os
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
try:
    from defusedxml import ElementTree
except ImportError:
    import xml.etree.ElementTree as ElementTree
from requests.auth import HTTPBasicAuth

from core.vault import load_vault

PLUGIN_NAME = "nextcloud"
PLUGIN_DESC = "Nextcloud-Integration: Dateien, Kalender, Aufgaben, WebDAV"

def _clean_cfg(value):
    value = str(value or '').strip()
    placeholders = ('your_', 'example.com', 'your-nextcloud-instance.com')
    return '' if any(p in value.lower() for p in placeholders) else value

def _nc():
    url = _clean_cfg(os.environ.get('NEXTCLOUD_URL', '')).rstrip('/')
    user = _clean_cfg(os.environ.get('NEXTCLOUD_USERNAME', ''))
    pw = _clean_cfg(os.environ.get('NEXTCLOUD_PASSWORD', ''))
    dav = _clean_cfg(os.environ.get('NEXTCLOUD_WEBDAV_PATH', '')).rstrip('/')

    base_dir = Path(__file__).resolve().parents[2]
    cfg_file = base_dir / 'data' / 'indexing_config.json'
    vault_file = base_dir / 'data' / 'vault.json'
    if cfg_file.exists():
        try:
            cfg = json.loads(cfg_file.read_text())
            url = url or _clean_cfg(cfg.get('url', '')).rstrip('/')
            user = user or _clean_cfg(cfg.get('username', ''))
            cfg_pw = _clean_cfg(cfg.get('password', ''))
            if cfg_pw and cfg_pw != '***':
                pw = pw or cfg_pw
            elif cfg_pw == '***' and vault_file.exists():
                try:
                    vault = load_vault(vault_file)
                    pw = pw or _clean_cfg(vault.get('indexing/password', ''))
                except Exception:
                    pass
        except Exception:
            pass

    vault_file = base_dir / 'data' / 'vault.json'
    if vault_file.exists():
        try:
            vault = load_vault(vault_file)
            url = url or _clean_cfg(vault.get('nextcloud/url', '')).rstrip('/')
            user = user or _clean_cfg(vault.get('nextcloud/username', '') or vault.get('nextcloud/user', ''))
            pw = pw or _clean_cfg(vault.get('nextcloud/password', ''))
            dav = dav or _clean_cfg(vault.get('nextcloud/webdav_path', '')).rstrip('/')
        except Exception:
            pass

    if not url or not user or not pw:
        raise RuntimeError("Nextcloud nicht konfiguriert. Setze NEXTCLOUD_URL, NEXTCLOUD_USERNAME, NEXTCLOUD_PASSWORD oder data/indexing_config.json.")
    if not dav:
        dav = f"/remote.php/dav/files/{user}"
    return (url, dav, user, pw)

def _abs_url(base_url, href):
    if href.startswith('http://') or href.startswith('https://'):
        return href
    return urljoin(base_url.rstrip('/') + '/', href.lstrip('/'))

def nextcloud_list(folder=""):
    try:
        url, dav, user, pw = _nc()
        auth = HTTPBasicAuth(user, pw)
        path = f"/{folder}" if folder else ""
        r = requests.request("PROPFIND", f"{url}{dav}{path}",
            headers={"Depth":"1"}, auth=auth, timeout=30)
        if r.status_code not in (207, 200):
            return f"❌ Status {r.status_code}: {r.text[:300]}"
        root = ElementTree.fromstring(r.content)
        ns = {'d':'DAV:'}
        items = []
        for resp in root.findall(".//d:response", ns):
            href = resp.find("d:href", ns)
            if href is None or href.text is None:
                continue
            name = href.text.rstrip('/').split('/')[-1]
            is_dir = resp.find(".//d:resourcetype/d:collection", ns) is not None
            items.append(f"{'📁' if is_dir else '📄'} {name}")
        return '\n'.join(items[:200]) if items else "(leer)"
    except Exception as e:
        return f"❌ {e}"

def nextcloud_read_file(path):
    try:
        url, dav, user, pw = _nc()
        auth = HTTPBasicAuth(user, pw)
        r = requests.get(f"{url}{dav}/{path}", auth=auth, timeout=60)
        r.raise_for_status()
        data = r.content
        ext = Path(path).suffix.lower()
        if ext in ('.md', '.txt'):
            return data.decode('utf-8', errors='replace')
        elif ext == '.docx':
            import io

            from docx import Document
            doc = Document(io.BytesIO(data))
            return '\n\n'.join(p.text for p in doc.paragraphs)
        elif ext == '.pdf':
            try:
                import tempfile

                from docling.document_converter import DocumentConverter
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                    f.write(data)
                    tmp = f.name
                try:
                    return DocumentConverter().convert(tmp).document.export_to_markdown()
                finally:
                    os.unlink(tmp)
            except Exception:
                return f"(PDF-Fehler: {path})"
        else:
            return data.decode('utf-8', errors='replace')
    except Exception as e:
        return f"❌ {e}"

def nextcloud_write_file(path, content):
    try:
        url, dav, user, pw = _nc()
        auth = HTTPBasicAuth(user, pw)
        r = requests.put(f"{url}{dav}/{path}", data=content.encode('utf-8'), auth=auth, timeout=30)
        if r.status_code in (200, 201, 204):
            return f"✅ {path} geschrieben"
        return f"❌ Status {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return f"❌ {e}"

def nextcloud_request(method, path, headers=None, body='', depth='0'):
    try:
        url, dav, user, pw = _nc()
        auth = HTTPBasicAuth(user, pw)
        hdrs = {"Depth": depth} if method.upper() == 'PROPFIND' else {}
        if headers:
            hdrs.update(headers)
        path_clean = path.strip('/')
        if path_clean.startswith('ocs/') or path_clean.startswith('remote.php/dav/'):
            # OCS API or explicit dav path → use base URL directly
            full_url = f"{url.rstrip('/')}/{path_clean}"
            if path_clean.startswith('ocs/'):
                hdrs['OCS-APIRequest'] = 'true'
                if '?' not in path_clean:
                    sep = '&' if '?' in full_url else '?'
                    full_url += f"{sep}format=json"
        else:
            full_url = f"{url}{dav}/{path_clean}"
        r = requests.request(method.upper(), full_url,
            data=body or None, headers=hdrs if hdrs else None, auth=auth, timeout=30)
        out = f"Status: {r.status_code}"
        if r.text.strip():
            out += f"\n{r.text[:3000]}"
        return out
    except Exception as e:
        return f"❌ {e}"

def _caldav_discover(base_url, user, auth):
    cal_base = f"{base_url}/remote.php/dav/calendars/{user}/"
    r = requests.request("PROPFIND", cal_base, auth=auth, headers={"Depth":"1"}, timeout=15)
    if r.status_code not in (207, 200):
        return []
    cals = []
    for match in re.finditer(r'<d:response>.*?<d:href>(.*?)</d:href>.*?<d:displayname>(.*?)</d:displayname>.*?</d:response>', r.text, re.DOTALL):
        href, name = match.group(1), _html.unescape(match.group(2)).strip()
        if name and href and href != cal_base.rstrip('/')+'/':
            cals.append((name, href))
    if not cals:
        for match in re.finditer(rf'<d:href>(.*?/calendars/{user}/.*?)/</d:href>', r.text):
            h = match.group(1)
            n = h.rstrip('/').split('/')[-1]
            if n and h != cal_base.rstrip('/'):
                cals.append((n, h))
    return cals

def _ical_date_to_ymd(raw):
    """Extract YYYYMMDD from iCal DTSTART/DTEND in any format."""
    if not raw:
        return ""
    val = raw
    if "VALUE=DATE:" in val:
        val = val.split("VALUE=DATE:")[-1]
    elif "TZID=" in val:
        val = val.split(":")[-1]
    if "T" in val:
        val = val.split("T")[0]
    return val.replace("-", "")

def _format_ical_dt(raw):
    """Format iCal DTSTART/DTEND to human-readable."""
    raw = raw.replace("VALUE=DATE:", "").replace("TZID=", "")
    if ":" in raw:
        raw = raw.split(":")[-1]
    if "T" in raw:
        parts = raw.split("T")
        d = parts[0]
        t = parts[1].rstrip("Z")
        return f"{d[:4]}-{d[4:6]}-{d[6:8]} {t[:2]}:{t[2:4]}"
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"

def nextcloud_caldav_query(start_date="", end_date=""):
    try:
        url, dav, user, pw = _nc()
        auth = HTTPBasicAuth(user, pw)
        cals = _caldav_discover(url, user, auth)
        if not cals:
            return "❌ Keine Kalender gefunden."
        body = '''<?xml version="1.0" encoding="utf-8"?>
<C:calendar-query xmlns:C="urn:ietf:params:xml:ns:caldav" xmlns:D="DAV:">
  <D:prop><D:getetag/><C:calendar-data/></D:prop>
  <C:filter><C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VEVENT"/>
  </C:comp-filter></C:filter>
</C:calendar-query>'''
        all_events = []
        start_ymd = start_date.replace("-", "") if start_date else ""
        end_ymd = end_date.replace("-", "") if end_date else ""
        for cal_name, cal_href in cals:
            r = requests.request("REPORT", _abs_url(url, cal_href), data=body, auth=auth,
                headers={"Content-Type":"application/xml; charset=utf-8","Depth":"1"}, timeout=30)
            if r.status_code not in (207, 200):
                continue
            for match in re.finditer(r'BEGIN:VEVENT(.*?)END:VEVENT', r.text, re.DOTALL):
                ev = match.group(1)
                def _ex(t):
                    m = re.search(t + r'[;:](.*?)(?:\r?\n|$)', ev)
                    return m.group(1).strip() if m else ""
                s = _ex('SUMMARY').replace('\\,',',').replace('\\n',' ').replace('\\N',' ')
                dts = _ex('DTSTART')
                dte = _ex('DTEND')
                if s and dts:
                    event_ymd = _ical_date_to_ymd(dts)
                    if start_ymd and event_ymd < start_ymd:
                        continue
                    if end_ymd and event_ymd > end_ymd:
                        continue
                    all_events.append({"s":s,"dts":dts,"dts_fmt":_format_ical_dt(dts),"dte_fmt":_format_ical_dt(dte) if dte else "?","cal":cal_name})
        if not all_events:
            return "Keine Termine im Zeitraum."
        by_cal = {}
        for e in all_events:
            by_cal.setdefault(e["cal"], []).append(e)
        lines = []
        for cal in sorted(by_cal):
            lines.append(f"\n📅 {cal}:")
            for e in by_cal[cal]:
                lines.append(f"  • {e['s']}  {e['dts_fmt']} → {e['dte_fmt']}")
        out = '\n'.join(lines).strip()
        if len(out) > 5000:
            total = sum(len(v) for v in by_cal.values())
            out = out[:5000] + f"\n... (+{total - 30} weitere)"
        return out
    except Exception as e:
        return f"❌ {e}"

def nextcloud_tasks_query():
    try:
        url, dav, user, pw = _nc()
        auth = HTTPBasicAuth(user, pw)
        cals = _caldav_discover(url, user, auth)
        if not cals:
            cals = [("Aufgaben", f"{url}/remote.php/dav/calendars/{user}/Aufgaben-1/")]
        else:
            # Make hrefs absolute if they are relative
            cals = [(name, _abs_url(url, href)) for name, href in cals]
        body = '''<?xml version="1.0" encoding="utf-8"?>
<C:calendar-query xmlns:C="urn:ietf:params:xml:ns:caldav" xmlns:D="DAV:">
  <D:prop><D:getetag/><C:calendar-data/></D:prop>
  <C:filter><C:comp-filter name="VCALENDAR">
    <C:comp-filter name="VTODO"/>
  </C:comp-filter></C:filter>
</C:calendar-query>'''
        all_tasks = []
        for cal_name, cal_href in cals:
            r = requests.request("REPORT", cal_href, data=body, auth=auth,
                headers={"Content-Type":"application/xml; charset=utf-8","Depth":"1"}, timeout=30)
            if r.status_code not in (207, 200):
                continue
            for match in re.finditer(r'BEGIN:VTODO(.*?)END:VTODO', r.text, re.DOTALL):
                t = match.group(1)
                def _ex(tag):
                    m = re.search(tag + r'[;:](.*?)(?:\r?\n|$)', t)
                    return m.group(1).strip() if m else ""
                summary = _ex('SUMMARY').replace('\\,',',').replace('\\n',' ')
                due = _ex('DUE')
                status = _ex('STATUS')
                if summary:
                    all_tasks.append(f"📌 [{cal_name}] {summary} | Fällig: {due or '?'} | Status: {status or '?'}")
        return '\n'.join(all_tasks[:50]) if all_tasks else "Keine Aufgaben gefunden."
    except Exception as e:
        return f"❌ {e}"

def nextcloud_delete(path):
    try:
        url, dav, user, pw = _nc()
        r = requests.delete(f"{url}{dav}/{path}", auth=HTTPBasicAuth(user, pw), timeout=30)
        if r.status_code in (200, 201, 202, 204):
            return f"✅ {path} gelöscht"
        return f"❌ Status {r.status_code}: {r.text[:300]}"
    except Exception as e:
        return f"❌ {e}"

def nextcloud_mkdir(path):
    try:
        url, dav, user, pw = _nc()
        r = requests.request("MKCOL", f"{url}{dav}/{path}", auth=HTTPBasicAuth(user, pw), timeout=30)
        if r.status_code in (200, 201, 204):
            return f"✅ Ordner {path} erstellt"
        return f"❌ Status {r.status_code}: {r.text[:300]}"
    except Exception as e:
        return f"❌ {e}"

def nextcloud_move(source, destination):
    try:
        url, dav, user, pw = _nc()
        dst = f"{url}{dav}/{destination}"
        r = requests.request("MOVE", f"{url}{dav}/{source}",
            headers={"Destination": dst}, auth=HTTPBasicAuth(user, pw), timeout=30)
        if r.status_code in (200, 201, 204):
            return f"✅ {source} → {destination}"
        return f"❌ Status {r.status_code}: {r.text[:300]}"
    except Exception as e:
        return f"❌ {e}"

def _caldav_href(base_url, user, auth, cal_name):
    cal_base = f"{base_url}/remote.php/dav/calendars/{user}/"
    r = requests.request("PROPFIND", cal_base, auth=auth, headers={"Depth":"1"}, timeout=15)
    if r.status_code not in (207, 200):
        return None
    for match in re.finditer(r'<d:response>.*?<d:href>(.*?)</d:href>.*?<d:displayname>(.*?)</d:displayname>.*?</d:response>', r.text, re.DOTALL):
        href, name = match.group(1), _html.unescape(match.group(2)).strip()
        if name.lower() == cal_name.lower():
            return href
    return None

def nextcloud_caldav_create(summary, dtstart, dtend="", description="", calendar_name="Persönlich"):
    try:
        url, dav, user, pw = _nc()
        auth = HTTPBasicAuth(user, pw)
        href = _caldav_href(url, user, auth, calendar_name)
        if not href:
            return f"❌ Kalender '{calendar_name}' nicht gefunden."
        uid = __import__('uuid').uuid4().hex[:20]
        dtend_line = f"\nDTEND:{dtend}" if dtend else ""
        desc_line = f"\nDESCRIPTION:{description}" if description else ""
        ical = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Nextcloud Chat//DE
BEGIN:VEVENT
UID:{uid}@nextcloud
DTSTART:{dtstart}{desc_line}{dtend_line}
SUMMARY:{summary}
END:VEVENT
END:VCALENDAR"""
        r = requests.request("PUT", f"{_abs_url(url, href).rstrip('/')}/{uid}.ics", data=ical,
            headers={"Content-Type":"text/calendar; charset=utf-8"}, auth=auth, timeout=30)
        if r.status_code in (200, 201, 204):
            return f"✅ Termin '{summary}' erstellt in {calendar_name}"
        return f"❌ Status {r.status_code}: {r.text[:300]}"
    except Exception as e:
        return f"❌ {e}"

def nextcloud_tasks_create(summary, due="", description="", calendar_name="Aufgaben"):
    try:
        url, dav, user, pw = _nc()
        auth = HTTPBasicAuth(user, pw)
        href = _caldav_href(url, user, auth, calendar_name)
        if not href:
            href = f"{url}/remote.php/dav/calendars/{user}/Aufgaben-1/"
        uid = __import__('uuid').uuid4().hex[:20]
        due_line = f"\nDUE:{due}" if due else ""
        desc_line = f"\nDESCRIPTION:{description}" if description else ""
        ical = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Nextcloud Chat//DE
BEGIN:VTODO
UID:{uid}@nextcloud
SUMMARY:{summary}{desc_line}{due_line}
STATUS:NEEDS-ACTION
END:VTODO
END:VCALENDAR"""
        r = requests.request("PUT", f"{_abs_url(url, href).rstrip('/')}/{uid}.ics", data=ical,
            headers={"Content-Type":"text/calendar; charset=utf-8"}, auth=auth, timeout=30)
        if r.status_code in (200, 201, 204):
            return f"✅ Aufgabe '{summary}' erstellt in {calendar_name}"
        return f"❌ Status {r.status_code}: {r.text[:300]}"
    except Exception as e:
        return f"❌ {e}"

def _carddav_discover(base_url, user, auth):
    ab_base = f"{base_url}/remote.php/dav/addressbooks/users/{user}/"
    r = requests.request("PROPFIND", ab_base, auth=auth, headers={"Depth":"1"}, timeout=15)
    if r.status_code not in (207, 200):
        return []
    books = []
    try:
        root = ElementTree.fromstring(r.content)
        ns = {"d": "DAV:", "card": "urn:ietf:params:xml:ns:carddav"}
        for resp in root.findall(".//d:response", ns):
            href_el = resp.find("d:href", ns)
            if href_el is None:
                continue
            href = href_el.text.strip()
            is_addr = resp.find(".//card:addressbook", ns)
            if is_addr is None:
                continue
            display_el = resp.find(".//d:displayname", ns)
            if display_el is not None and display_el.text:
                name = _html.unescape(display_el.text.strip())
                if name.startswith("Principal"):
                    continue
            else:
                name = href.rstrip("/").split("/")[-1]
            books.append((name, href))
    except ElementTree.ParseError:
        pass
    return books

def nextcloud_contact_search(query):
    try:
        url, dav, user, pw = _nc()
        auth = HTTPBasicAuth(user, pw)
        books = _carddav_discover(url, user, auth)
        if not books:
            return "❌ Keine Adressbücher gefunden."
        q = query.strip().lower()
        body = '''<?xml version="1.0" encoding="utf-8"?>
<card:addressbook-query xmlns:card="urn:ietf:params:xml:ns:carddav" xmlns:D="DAV:">
  <D:prop><D:getetag/><card:address-data/></D:prop>
</card:addressbook-query>'''
        results = []
        for ab_name, ab_href in books:
            r = requests.request("REPORT", _abs_url(url, ab_href), data=body, auth=auth,
                headers={"Content-Type":"application/xml; charset=utf-8","Depth":"1"}, timeout=30)
            if r.status_code not in (207, 200):
                continue
            for vcard_match in re.finditer(r'BEGIN:VCARD(.*?)END:VCARD', r.text, re.DOTALL):
                vcard = 'BEGIN:VCARD' + vcard_match.group(1) + 'END:VCARD'
                name = re.search(r'FN[;:](.*?)(?:\r?\n|$)', vcard)
                email = re.search(r'EMAIL[;:].*?:(\S[^\r\n]*)', vcard)
                tel = re.search(r'TEL[;:].*?:(\S[^\r\n]*)', vcard)
                org = re.search(r'ORG[;:](.*?)(?:\r?\n|$)', vcard)
                uid = re.search(r'UID[;:](.*?)(?:\r?\n|$)', vcard)
                fn = _html.unescape((name.group(1) if name else '').strip())
                em = _html.unescape((email.group(1) if email else '').strip())
                ph = _html.unescape((tel.group(1) if tel else '').strip())
                org_name = _html.unescape((org.group(1) if org else '').strip()).replace('\\,', ',')
                uid_val = (uid.group(1) if uid else '').strip()
                if not fn and not em:
                    n = re.search(r'N[;:](.*?)(?:\r?\n|$)', vcard)
                    if n:
                        parts = n.group(1).strip().split(';')
                        fn = ' '.join(p for p in parts if p).strip()
                        fn = _html.unescape(fn)
                if q and q not in fn.lower() and q not in em.lower() and q not in ph.lower():
                    continue
                line = f"👤 {fn}"
                if em:
                    line += f"\n   ✉️ {em}"
                if ph:
                    line += f"\n   📞 {ph}"
                if org_name:
                    line += f"\n   🏢 {org_name}"
                if uid_val:
                    line += f"\n   🔑 {uid_val}"
                results.append(line)
        if not results:
            return f"Keine Kontakte gefunden für '{query}'."
        out = '\n---\n'.join(results)
        return out[:4000]
    except Exception as e:
        return f"❌ {e}"

def nextcloud_contact_get(uid):
    try:
        url, dav, user, pw = _nc()
        auth = HTTPBasicAuth(user, pw)
        books = _carddav_discover(url, user, auth)
        if not books:
            return "❌ Keine Adressbücher gefunden."
        for ab_name, ab_href in books:
            r = requests.get(_abs_url(url, ab_href) + uid + '.vcf', auth=auth, timeout=15)
            if r.status_code == 200:
                return r.text[:4000]
        return f"❌ Kontakt {uid} nicht gefunden."
    except Exception as e:
        return f"❌ {e}"


def nextcloud_share_link(path, share_type=3, permissions=1):
    """Erstelle einen Share-Link für eine Datei/Ordner.
    share_type: 3=öffentlicher Link, 0=Benutzer, 1=Gruppe
    permissions: 1=lesen, 2=ändern, 3=lesen+ändern, 4=erstellen, 5=lesen+erstellen, 7=voll
    """
    try:
        url, dav, user, pw = _nc()
        auth = HTTPBasicAuth(user, pw)
        full_url = f"{url.rstrip('/')}/ocs/v2.php/apps/files_sharing/api/v1/shares?format=json"
        data = {
            "path": path,
            "shareType": int(share_type),
            "permissions": int(permissions),
        }
        r = requests.post(full_url, data=data, auth=auth,
                          headers={"OCS-APIRequest": "true"}, timeout=15)
        if r.status_code in (200, 201):
            result = r.json()
            oc = result.get("ocs", {})
            meta = oc.get("meta", {})
            if meta.get("statuscode") == 100:
                d = oc.get("data", {})
                link = d.get("url", d.get("link", ""))
                token = d.get("token", "")
                lines = ["🔗 **Share-Link erstellt**"]
                if link:
                    lines.append(f"  Link: {link}")
                if token:
                    lines.append(f"  Token: `{token}`")
                lines.append(f"  Berechtigung: {'öffentlich' if int(share_type)==3 else 'privat'}")
                return "\n".join(lines)
            return f"❌ OCS-Fehler: {meta.get('message', str(meta))}"
        return f"❌ Status {r.status_code}: {r.text[:300]}"
    except Exception as e:
        return f"❌ {e}"


def nextcloud_search(query, folder=""):
    """Volltextsuche in Nextcloud-Dateien per OCS Search API."""
    try:
        url, dav, user, pw = _nc()
        auth = HTTPBasicAuth(user, pw)
        # Try OCS full-text search provider
        full_url = f"{url.rstrip('/')}/ocs/v2.php/search/providers?format=json"
        r = requests.get(full_url, auth=auth, headers={"OCS-APIRequest": "true"}, timeout=15)
        providers = []
        if r.status_code == 200:
            result = r.json()
            for p in result.get("ocs", {}).get("data", []):
                if p.get("id") in ("files", "files_full_text"):
                    providers.append(p["id"])
        if not providers:
            # Fallback: simple filename search via PROPFIND
            folder = folder.strip("/")
            search_path = f"{folder}" if folder else ""
            limit = 20
            r2 = requests.request("PROPFIND", f"{url}{dav}/{search_path}",
                                  auth=auth, headers={"Depth": "infinity"}, timeout=30)
            if r2.status_code not in (207, 200):
                return f"❌ Keine Volltextsuche verfügbar (Status {r2.status_code})"
            q = query.lower()
            matches = []
            for resp in re.finditer(r'<d:response>.*?<d:href>(.*?)</d:href>.*?</d:response>', r2.text, re.DOTALL):
                href = resp.group(1)
                name = href.rstrip("/").split("/")[-1]
                if q in name.lower() or any(kw in name.lower() for kw in q.split() if len(kw) > 2):
                    matches.append(f"  📄 `{href}`")
                    if len(matches) >= limit:
                        break
            if not matches:
                return f"❌ Nichts gefunden für '{query}'."
            return f"🔍 **{len(matches)} Treffer für '{query}'**\n" + "\n".join(matches)
        # Use OCS search
        results = []
        for prov in providers:
            search_url = f"{url.rstrip('/')}/ocs/v2.php/search/providers/{prov}/search?format=json&term={query}"
            if folder:
                search_url += f"&from={folder}"
            r3 = requests.get(search_url, auth=auth, headers={"OCS-APIRequest": "true"}, timeout=15)
            if r3.status_code == 200:
                sr = r3.json()
                for entry in sr.get("ocs", {}).get("data", []):
                    title = entry.get("title", "")
                    link = entry.get("link", "")
                    excerpt = entry.get("excerpt", "")
                    results.append(f"  📄 **{title}**\n    {excerpt}\n    🔗 {link}")
        if results:
            return f"🔍 **{len(results)} Treffer für '{query}'**\n" + "\n".join(results[:10])
        return f"❌ Keine Ergebnisse für '{query}'."
    except Exception as e:
        return f"❌ {e}"


def nextcloud_get_previews(path, x=400, y=400):
    """Hole eine Vorschau-URL für eine Datei."""
    try:
        url, dav, user, pw = _nc()
        auth = HTTPBasicAuth(user, pw)
        preview_url = f"{url.rstrip('/')}/index.php/core/preview.png?file={path}&x={x}&y={y}&a=1"
        r = requests.head(preview_url, auth=auth, timeout=10)
        if r.status_code == 200:
            return f"🖼️ Vorschau: {preview_url}"
        return f"⚠️ Keine Vorschau verfügbar für '{path}' (Status {r.status_code})"
    except Exception as e:
        return f"❌ {e}"


def nextcloud_get_notifications():
    """Rufe Nextcloud-Benachrichtigungen ab."""
    try:
        url, dav, user, pw = _nc()
        auth = HTTPBasicAuth(user, pw)
        noti_url = f"{url.rstrip('/')}/ocs/v2.php/apps/notifications/api/v2/notifications?format=json"
        r = requests.get(noti_url, auth=auth, headers={"OCS-APIRequest": "true"}, timeout=15)
        if r.status_code == 200:
            data = r.json().get("ocs", {}).get("data", [])
            if not data:
                return "✅ Keine Benachrichtigungen."
            lines = [f"🔔 **{len(data)} Benachrichtigungen**"]
            for n in data[:20]:
                app = n.get("app", "")
                subject = n.get("subject", "")
                lines.append(f"  • [{app}] {subject}")
            return "\n".join(lines)
        return f"❌ Fehler {r.status_code}"
    except Exception as e:
        return f"❌ {e}"


def nextcloud_create_share_link(path, password="", expire_days=None, permissions=1):
    """Erstelle einen öffentlichen Share-Link mit Passwort und Ablaufdatum."""
    try:
        url, dav, user, pw = _nc()
        auth = HTTPBasicAuth(user, pw)
        share_url = f"{url.rstrip('/')}/ocs/v2.php/apps/files_sharing/api/v1/shares?format=json"
        data = {"path": path, "shareType": 3, "permissions": int(permissions)}
        if password:
            data["password"] = password
        if expire_days:
            from datetime import datetime, timedelta
            expire = (datetime.now() + timedelta(days=int(expire_days))).strftime("%Y-%m-%d")
            data["expireDate"] = expire
        r = requests.post(share_url, data=data, auth=auth,
                          headers={"OCS-APIRequest": "true"}, timeout=15)
        if r.status_code in (200, 201):
            result = r.json()
            d = result.get("ocs", {}).get("data", {})
            link = d.get("url", d.get("link", ""))
            lines = ["🔗 **Share-Link erstellt**"]
            if link:
                lines.append(f"  Link: {link}")
            if password:
                lines.append(f"  Passwort: `{password}`")
            if expire_days:
                lines.append(f"  Läuft ab: {expire}")
            return "\n".join(lines)
        return f"❌ Status {r.status_code}: {r.text[:300]}"
    except Exception as e:
        return f"❌ {e}"


def nextcloud_list_tags():
    """Liste alle Nextcloud-System-Tags auf."""
    try:
        url, dav, user, pw = _nc()
        auth = HTTPBasicAuth(user, pw)
        tag_url = f"{url.rstrip('/')}/ocs/v2.php/apps/systemtags/tags?format=json"
        r = requests.get(tag_url, auth=auth, headers={"OCS-APIRequest": "true"}, timeout=15)
        if r.status_code == 200:
            tags = r.json().get("ocs", {}).get("data", [])
            if not tags:
                return "📭 Keine Tags vorhanden."
            lines = ["🏷️ **System-Tags**"]
            for t in tags:
                name = t.get("name", "")
                tag_id = t.get("id", "")
                user_visible = t.get("userVisible", True)
                lines.append(f"  • `{name}` (ID: {tag_id})")
            return "\n".join(lines)
        return f"❌ Fehler {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return f"❌ {e}"


def nextcloud_search_tags(tag):
    """Suche Dateien nach System-Tag."""
    try:
        url, dav, user, pw = _nc()
        auth = HTTPBasicAuth(user, pw)
        search_url = f"{url.rstrip('/')}/ocs/v2.php/apps/systemtags/tags?format=json"
        r = requests.get(search_url, auth=auth, headers={"OCS-APIRequest": "true"}, timeout=15)
        if r.status_code != 200:
            return f"❌ Fehler {r.status_code}"
        tags = r.json().get("ocs", {}).get("data", [])
        tag_id = None
        for t in tags:
            if t.get("name", "").lower() == tag.lower():
                tag_id = t.get("id")
                break
        if not tag_id:
            return f"❌ Tag '{tag}' nicht gefunden."
        files_url = f"{url.rstrip('/')}/ocs/v2.php/apps/systemtags/tags/{tag_id}/files?format=json"
        r2 = requests.get(files_url, auth=auth, headers={"OCS-APIRequest": "true"}, timeout=15)
        if r2.status_code == 200:
            files = r2.json().get("ocs", {}).get("data", [])
            if not files:
                return f"📭 Keine Dateien mit Tag '{tag}'."
            lines = [f"📂 **{len(files)} Dateien mit Tag '{tag}'**"]
            for f in files[:30]:
                name = f.get("name", "")
                lines.append(f"  • {name}")
            return "\n".join(lines)
        return f"❌ Fehler {r2.status_code}"
    except Exception as e:
        return f"❌ {e}"


def nextcloud_get_versions(path):
    """Liste die Versionen einer Datei auf."""
    try:
        url, dav, user, pw = _nc()
        auth = HTTPBasicAuth(user, pw)
        full_path = f"{url}{dav}/{path.lstrip('/')}"
        ver_url = f"{url.rstrip('/')}/remote.php/dav/versions/{user}/versions/{path}"
        r = requests.request("PROPFIND", full_path, auth=auth,
                            headers={"Depth": "0"}, timeout=15)
        if r.status_code not in (207, 200):
            return f"❌ Datei nicht gefunden: {path}"
        r2 = requests.request("PROPFIND", ver_url, auth=auth,
                              headers={"Depth": "1"}, timeout=15)
        if r2.status_code not in (207, 200):
            return f"ℹ️ Keine Versionen für '{path}' oder Versionierung nicht aktiviert."
        versions = []
        for match in re.finditer(r'<d:response>.*?<d:href>(.*?)</d:href>.*?<d:getlastmodified>(.*?)</d:getlastmodified>.*?<d:getcontentlength>(.*?)</d:getcontentlength>', r2.text, re.DOTALL):
            vhref = match.group(1)
            vdate = match.group(2)
            vsize = match.group(3)
            vid = vhref.rstrip("/").split("/")[-1]
            versions.append(f"  • {vdate} ({vsize} Bytes) - ID: `{vid}`")
        if not versions:
            return f"ℹ️ Keine Versionen gefunden."
        return f"📋 **Versionen von '{path}'**\n" + "\n".join(versions)
    except Exception as e:
        return f"❌ {e}"


def nextcloud_restore_version(path, version_id):
    """Stelle eine frühere Version einer Datei wieder her."""
    try:
        url, dav, user, pw = _nc()
        auth = HTTPBasicAuth(user, pw)
        # WebDAV COPY to restore: copy from version to current path
        src_url = f"{url.rstrip('/')}/remote.php/dav/versions/{user}/versions/{path}/{version_id}"
        dest_url = f"{url}{dav}/{path.lstrip('/')}"
        r = requests.request("COPY", src_url, auth=auth, headers={"Destination": dest_url}, timeout=15)
        if r.status_code in (200, 201, 204):
            return f"✅ Version `{version_id}` von '{path}' wiederhergestellt."
        return f"❌ Wiederherstellung fehlgeschlagen (Status {r.status_code})"
    except Exception as e:
        return f"❌ {e}"


def nextcloud_create_contact(fn, email="", tel="", org="", addressbook="Standard"):
    """Erstelle einen neuen Kontakt im Nextcloud-Adressbuch."""
    try:
        url, dav, user, pw = _nc()
        auth = HTTPBasicAuth(user, pw)
        books = _carddav_discover(url, user, auth)
        target_href = None
        for bname, bhref in books:
            if bname.lower() == addressbook.lower() or addressbook.lower() in bname.lower():
                target_href = bhref
                break
        if not target_href and books:
            target_href = books[0][1]
        if not target_href:
            return "❌ Kein Adressbuch gefunden."
        uid = f"uid-{int(time.time())}@local"
        lines = ["BEGIN:VCARD", "VERSION:3.0", f"UID:{uid}", f"FN:{fn}"]
        n_parts = fn.split(None, 1)
        if len(n_parts) == 2:
            lines.append(f"N:{n_parts[1]};{n_parts[0]}")
        else:
            lines.append(f"N:{fn};")
        if email:
            lines.append(f"EMAIL;TYPE=INTERNET:{email}")
        if tel:
            lines.append(f"TEL:{tel}")
        if org:
            lines.append(f"ORG:{org}")
        lines.append("END:VCARD")
        vcard = "\r\n".join(lines)
        contact_url = _abs_url(url, target_href) + uid + ".vcf"
        r = requests.put(contact_url, data=vcard, auth=auth,
                         headers={"Content-Type": "text/vcard; charset=utf-8"}, timeout=15)
        if r.status_code in (200, 201, 204):
            return f"✅ Kontakt **{fn}** erstellt (UID: `{uid}`)"
        return f"❌ Fehler {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return f"❌ {e}"


def nextcloud_update_contact(uid, fn="", email="", tel="", org=""):
    """Aktualisiere einen bestehenden Kontakt."""
    try:
        url, dav, user, pw = _nc()
        auth = HTTPBasicAuth(user, pw)
        books = _carddav_discover(url, user, auth)
        vcard = None
        for ab_name, ab_href in books:
            r = requests.get(_abs_url(url, ab_href) + uid + '.vcf', auth=auth, timeout=15)
            if r.status_code == 200:
                vcard = r.text
                contact_ab_href = ab_href
                break
        if not vcard:
            return f"❌ Kontakt {uid} nicht gefunden."
        if fn:
            vcard = re.sub(r'FN[;:].*', f'FN:{fn}', vcard)
            n_match = re.search(r'N[;:].*', vcard)
            n_parts = fn.split(None, 1)
            if len(n_parts) == 2:
                new_n = f"N:{n_parts[1]};{n_parts[0]}"
            else:
                new_n = f"N:{fn};"
            vcard = re.sub(r'N[;:].*', new_n, vcard) if n_match else vcard + f"\r\n{new_n}"
        if email:
            vcard = re.sub(r'EMAIL[;:].*?:.*', f'EMAIL;TYPE=INTERNET:{email}', vcard) if re.search(r'EMAIL', vcard) else vcard + f"\r\nEMAIL;TYPE=INTERNET:{email}"
        if tel:
            vcard = re.sub(r'TEL[;:].*', f'TEL:{tel}', vcard) if re.search(r'TEL', vcard) else vcard + f"\r\nTEL:{tel}"
        if org:
            vcard = re.sub(r'ORG[;:].*', f'ORG:{org}', vcard) if re.search(r'ORG', vcard) else vcard + f"\r\nORG:{org}"
        contact_url = _abs_url(url, contact_ab_href) + uid + ".vcf"
        r = requests.put(contact_url, data=vcard.encode("utf-8"), auth=auth,
                         headers={"Content-Type": "text/vcard; charset=utf-8"}, timeout=15)
        if r.status_code in (200, 201, 204):
            return f"✅ Kontakt `{uid}` aktualisiert."
        return f"❌ Fehler {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return f"❌ {e}"


TOOLS = [
    {"type":"function","function":{"name":"nextcloud_list","description":"Liste den Inhalt eines Nextcloud-Ordners. Pfad relativ zum WebDAV-Root, z.B. 'Privat' oder 'Geteilt/2021'. Leer lassen für Root.","parameters":{"type":"object","properties":{"folder":{"type":"string","description":"Ordnerpfad relativ zum WebDAV-Root (optional, leer = Root)"}},"required":[]}}},  # noqa: E501
    {"type":"function","function":{"name":"nextcloud_read_file","description":"Lese den Inhalt einer Datei von Nextcloud. Pfad relativ zum WebDAV-Root, z.B. 'Privat/datei.md'. Extrahiert Text aus .md, .txt, .docx, .pdf.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Dateipfad relativ zum WebDAV-Root"}},"required":["path"]}}},  # noqa: E501
    {"type":"function","function":{"name":"nextcloud_write_file","description":"Erstelle oder überschreibe eine Datei auf Nextcloud. Pfad relativ zum WebDAV-Root. Inhalt als Text.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Dateipfad relativ zum WebDAV-Root"},"content":{"type":"string","description":"Datei-Inhalt als Text"}},"required":["path","content"]}}},  # noqa: E501
    {"type":"function","function":{"name":"nextcloud_delete","description":"Lösche eine Datei oder einen leeren Ordner auf Nextcloud. Pfad relativ zum WebDAV-Root.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Datei-/Ordnerpfad"}},"required":["path"]}}},  # noqa: E501
    {"type":"function","function":{"name":"nextcloud_mkdir","description":"Erstelle einen neuen Ordner auf Nextcloud. Pfad relativ zum WebDAV-Root.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Ordnerpfad"}},"required":["path"]}}},  # noqa: E501
    {"type":"function","function":{"name":"nextcloud_move","description":"Verschiebe oder benenne eine Datei / einen Ordner auf Nextcloud um.","parameters":{"type":"object","properties":{"source":{"type":"string","description":"Quellpfad relativ zu WebDAV-Root"},"destination":{"type":"string","description":"Zielpfad relativ zu WebDAV-Root"}},"required":["source","destination"]}}},  # noqa: E501
    {"type":"function","function":{"name":"nextcloud_request","description":"Sende HTTP-Request an die Nextcloud-API (WebDAV/CalDAV/CardDAV/OCS). Methoden: GET, PUT, DELETE, PROPFIND, REPORT, MKCOL, MOVE, COPY.","parameters":{"type":"object","properties":{"method":{"type":"string","description":"GET, PUT, DELETE, PROPFIND, MKCOL, MOVE, COPY"},"path":{"type":"string","description":"Pfad relativ zur WebDAV-Basis"},"headers":{"type":"object","description":"Zusätzliche HTTP-Header (optional)"},"body":{"type":"string","description":"Request-Body (optional)"},"depth":{"type":"string","description":"Depth für PROPFIND (0, 1, infinity)"}},"required":["method","path"]}}},  # noqa: E501
    {"type":"function","function":{"name":"nextcloud_caldav_query","description":"Rufe Kalendereinträge (Termine) von ALLEN Nextcloud-Kalendern ab. Erkennt alle Kalender automatisch. Datumsfilter optional (YYYYMMDD).","parameters":{"type":"object","properties":{"start_date":{"type":"string","description":"Start YYYYMMDD (optional)"},"end_date":{"type":"string","description":"Ende YYYYMMDD (optional)"}}}}},  # noqa: E501
    {"type":"function","function":{"name":"nextcloud_caldav_create","description":"Erstelle einen neuen Kalender-Termin. Datum im iCal-Format: 20260628T090000. Kalendername optional (default 'Persönlich').","parameters":{"type":"object","properties":{"summary":{"type":"string","description":"Titel des Termins"},"dtstart":{"type":"string","description":"Start (iCal: 20260628T090000)"},"dtend":{"type":"string","description":"Ende (iCal, optional)"},"description":{"type":"string","description":"Beschreibung (optional)"},"calendar_name":{"type":"string","description":"Kalendername (default: Persönlich)"}},"required":["summary","dtstart"]}}},  # noqa: E501
    {"type":"function","function":{"name":"nextcloud_tasks_query","description":"Rufe Aufgaben/Todos von ALLEN Nextcloud-Kalendern ab.","parameters":{"type":"object","properties":{}}}},  # noqa: E501
    {"type":"function","function":{"name":"nextcloud_tasks_create","description":"Erstelle eine neue Aufgabe/Todo in Nextcloud. Datum im iCal-Format: 20260628. Standard-Kalender: 'Aufgaben'.","parameters":{"type":"object","properties":{"summary":{"type":"string","description":"Aufgaben-Titel"},"due":{"type":"string","description":"Fällig bis (iCal: 20260628, optional)"},"description":{"type":"string","description":"Beschreibung (optional)"},"calendar_name":{"type":"string","description":"Kalendername (default: Aufgaben)"}},"required":["summary"]}}},  # noqa: E501
    {"type":"function","function":{"name":"nextcloud_contact_search","description":"Suche in ALLEN Nextcloud-Adressbüchern nach Kontakten. Query ist Name, E-Mail oder Telefonnummer. Liefert Name, E-Mail, Telefon, Firma und UID zurück.","parameters":{"type":"object","properties":{"query":{"type":"string","description":"Suchbegriff (Name, E-Mail oder Telefon)"}},"required":["query"]}}},  # noqa: E501
    {"type":"function","function":{"name":"nextcloud_contact_get","description":"Rufe einen einzelnen Nextcloud-Kontakt per UID ab. Liefert die vollständige vCard. Die UID bekommst du aus nextcloud_contact_search.","parameters":{"type":"object","properties":{"uid":{"type":"string","description":"Die UID des Kontakts (aus nextcloud_contact_search)"}},"required":["uid"]}}},  # noqa: E501
    {"type":"function","function":{"name":"nextcloud_share_link","description":"Erstelle einen öffentlichen Share-Link für eine Datei oder einen Ordner auf Nextcloud. Pfad relativ zum Nextcloud-Root (z.B. 'Privat/Urlaub/foto.jpg').","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Datei- oder Ordnerpfad relativ zum WebDAV-Root"},"share_type":{"type":"integer","description":"3=öffentlicher Link (default), 0=Benutzer, 1=Gruppe"},"permissions":{"type":"integer","description":"1=lesen (default), 2=ändern, 3=lesen+ändern, 7=voll"}},"required":["path"]}}},  # noqa: E501
    {"type":"function","function":{"name":"nextcloud_search","description":"Volltextsuche in Nextcloud-Dateien. Durchsucht Dateinamen und -inhalte (falls Full-Text-Search aktiviert).","parameters":{"type":"object","properties":{"query":{"type":"string","description":"Suchbegriff"},"folder":{"type":"string","description":"Optional: Ordner einschränken (z.B. 'Privat')"}},"required":["query"]}}},  # noqa: E501
    {"type":"function","function":{"name":"nextcloud_get_previews","description":"Hole eine Vorschau-URL für eine Datei.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Dateipfad relativ zum WebDAV-Root"},"x":{"type":"integer","description":"Breite (default 400)"},"y":{"type":"integer","description":"Höhe (default 400)"}},"required":["path"]}}},  # noqa: E501
    {"type":"function","function":{"name":"nextcloud_get_notifications","description":"Rufe Nextcloud-Benachrichtigungen ab.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"nextcloud_create_share_link","description":"Erstelle einen öffentlichen Share-Link mit Passwort und Ablaufdatum.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Datei- oder Ordnerpfad"},"password":{"type":"string","description":"Optional: Passwort"},"expire_days":{"type":"integer","description":"Optional: Tage bis Ablauf"},"permissions":{"type":"integer","description":"1=lesen, 2=ändern, 3=lesen+ändern"}},"required":["path"]}}},  # noqa: E501
    {"type":"function","function":{"name":"nextcloud_list_tags","description":"Liste alle Nextcloud-System-Tags auf.","parameters":{"type":"object","properties":{}}}},
    {"type":"function","function":{"name":"nextcloud_search_tags","description":"Suche Dateien nach System-Tag.","parameters":{"type":"object","properties":{"tag":{"type":"string","description":"Tag-Name (z.B. wichtig)"}},"required":["tag"]}}},
    {"type":"function","function":{"name":"nextcloud_get_versions","description":"Liste die Versionen einer Datei auf.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Dateipfad relativ zum WebDAV-Root"}},"required":["path"]}}},  # noqa: E501
    {"type":"function","function":{"name":"nextcloud_restore_version","description":"Stelle eine frühere Version einer Datei wieder her.","parameters":{"type":"object","properties":{"path":{"type":"string","description":"Dateipfad"},"version_id":{"type":"string","description":"Version-ID"}},"required":["path","version_id"]}}},  # noqa: E501
    {"type":"function","function":{"name":"nextcloud_create_contact","description":"Erstelle einen neuen Kontakt im Nextcloud-Adressbuch.","parameters":{"type":"object","properties":{"fn":{"type":"string","description":"Vollständiger Name"},"email":{"type":"string","description":"E-Mail (optional)"},"tel":{"type":"string","description":"Telefon (optional)"},"org":{"type":"string","description":"Firma (optional)"}},"required":["fn"]}}},  # noqa: E501
    {"type":"function","function":{"name":"nextcloud_update_contact","description":"Aktualisiere einen bestehenden Kontakt.","parameters":{"type":"object","properties":{"uid":{"type":"string","description":"UID des Kontakts"},"fn":{"type":"string","description":"Neuer Name (optional)"},"email":{"type":"string","description":"Neue E-Mail (optional)"},"tel":{"type":"string","description":"Neue Telefonnummer (optional)"}},"required":["uid"]}}},  # noqa: E501
]

TOOL_MAP = {
    "nextcloud_list": nextcloud_list,
    "nextcloud_read_file": nextcloud_read_file,
    "nextcloud_write_file": nextcloud_write_file,
    "nextcloud_delete": nextcloud_delete,
    "nextcloud_mkdir": nextcloud_mkdir,
    "nextcloud_move": nextcloud_move,
    "nextcloud_request": nextcloud_request,
    "nextcloud_caldav_query": nextcloud_caldav_query,
    "nextcloud_caldav_create": nextcloud_caldav_create,
    "nextcloud_tasks_query": nextcloud_tasks_query,
    "nextcloud_tasks_create": nextcloud_tasks_create,
    "nextcloud_contact_search": nextcloud_contact_search,
    "nextcloud_contact_get": nextcloud_contact_get,
    "nextcloud_share_link": nextcloud_share_link,
    "nextcloud_search": nextcloud_search,
    "nextcloud_get_previews": nextcloud_get_previews,
    "nextcloud_get_notifications": nextcloud_get_notifications,
    "nextcloud_create_share_link": nextcloud_create_share_link,
    "nextcloud_list_tags": nextcloud_list_tags,
    "nextcloud_search_tags": nextcloud_search_tags,
    "nextcloud_get_versions": nextcloud_get_versions,
    "nextcloud_restore_version": nextcloud_restore_version,
    "nextcloud_create_contact": nextcloud_create_contact,
    "nextcloud_update_contact": nextcloud_update_contact,
}

PROMPT_EXTRA = (
    "Nextcloud:\n"
    "  - **nextcloud_list**: Ordnerinhalt auflisten\n"
    "  - **nextcloud_read_file**: Datei lesen (.md, .txt, .docx, .pdf)\n"
    "  - **nextcloud_write_file**: Datei schreiben\n"
    "  - **nextcloud_delete**: Datei/Ordner löschen\n"
    "  - **nextcloud_mkdir**: Ordner erstellen\n"
    "  - **nextcloud_move**: Datei/Ordner verschieben/umbenennen\n"
    "  - **nextcloud_request**: Beliebiger WebDAV/CalDAV/CardDAV/OCS-Request\n"
    "  - **nextcloud_caldav_query**: Termine abrufen (mit Datumsfilter)\n"
    "  - **nextcloud_caldav_create**: Termin erstellen\n"
    "  - **nextcloud_tasks_query**: Aufgaben abrufen\n"
    "  - **nextcloud_tasks_create**: Aufgabe erstellen\n"
    "  - **nextcloud_contact_search**: Kontakte suchen (Name/E-Mail/Telefon)\n"
    "  - **nextcloud_contact_get**: Einzelnen Kontakt per UID abrufen\n"
    "  - **nextcloud_share_link(path, share_type=3, permissions=1)**: Öffentlichen Share-Link erstellen\n"
    "  - **nextcloud_search(query, folder='')**: Volltextsuche in Dateien\n"
    "  - **nextcloud_get_previews(path, x=400, y=400)**: Vorschau-URL für eine Datei\n"
    "  - **nextcloud_get_notifications()**: Benachrichtigungen abrufen\n"
    "  - **nextcloud_create_share_link(path, password='', expire_days, permissions=1)**: Share-Link mit Passwort/Ablauf\n"
    "  - **nextcloud_list_tags()**: System-Tags auflisten\n"
    "  - **nextcloud_search_tags(tag)**: Dateien nach Tag suchen\n"
    "  - **nextcloud_get_versions(path)**: Datei-Versionen anzeigen\n"
    "  - **nextcloud_restore_version(path, version_id)**: Version wiederherstellen\n"
    "  - **nextcloud_create_contact(fn, email, tel, org)**: Neuen Kontakt erstellen\n"
    "  - **nextcloud_update_contact(uid, fn, email, tel, org)**: Kontakt aktualisieren\n"
    "  API-Pfade: WebDAV /remote.php/dav/files/BENUTZER/, CalDAV /remote.php/dav/calendars/BENUTZER/, CardDAV /remote.php/dav/addressbooks/BENUTZER/, OCS /ocs/v1.php/\n")
