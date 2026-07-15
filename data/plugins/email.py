import email as eml
import imaplib
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from core.vault import load_vault

PLUGIN_NAME = "email"
PLUGIN_DESC = "Email-Integration via IMAP + SMTP – Mehrere Konten unterstützt"

VAULT_FILE = Path(__file__).parent.parent / 'vault.json'

def _vault():
    return load_vault(VAULT_FILE)

def _vget(key):
    v = _vault()
    if key in v:
        return v.get(key, "")
    parts = key.split('/')
    for p in parts:
        if isinstance(v, dict):
            v = v.get(p)
        else:
            return ""
    return v if isinstance(v, str) else ""

def _list_accounts():
    v = _vault()
    accts = v.get("email", {}).get("accounts", {})
    return list(accts.keys()) if accts else ["default"]

def _acct_keys(account="default"):
    if account == "default":
        return {
            "imap_server": _vget("email/imap_server"),
            "imap_port": int(_vget("email/imap_port") or 993),
            "imap_user": _vget("email/imap_user"),
            "imap_password": _vget("email/imap_password"),
            "smtp_server": _vget("email/smtp_server"),
            "smtp_port": int(_vget("email/smtp_port") or 587),
            "smtp_user": _vget("email/smtp_user"),
            "smtp_password": _vget("email/smtp_password"),
        }
    pref = f"email/accounts/{account}"
    return {
        "imap_server": _vget(f"{pref}/imap_server"),
        "imap_port": int(_vget(f"{pref}/imap_port") or 993),
        "imap_user": _vget(f"{pref}/imap_user"),
        "imap_password": _vget(f"{pref}/imap_password"),
        "smtp_server": _vget(f"{pref}/smtp_server"),
        "smtp_port": int(_vget(f"{pref}/smtp_port") or 587),
        "smtp_user": _vget(f"{pref}/smtp_user"),
        "smtp_password": _vget(f"{pref}/smtp_password"),
    }

def _connect_imap(account="default"):
    ck = _acct_keys(account)
    host, port, user, pw = ck["imap_server"], ck["imap_port"], ck["imap_user"], ck["imap_password"]
    if not host or not user or not pw:
        return None, f"❌ IMAP-Zugangsdaten fehlen für '{account}'."
    c = imaplib.IMAP4_SSL(host, port, timeout=15)
    c.login(user, pw)
    return c, None

def _connect_smtp(account="default"):
    ck = _acct_keys(account)
    host, port, user, pw = ck["smtp_server"], ck["smtp_port"], ck["smtp_user"], ck["smtp_password"]
    if not host or not user or not pw:
        return None, f"❌ SMTP-Zugangsdaten fehlen für '{account}'."
    s = smtplib.SMTP(host, port, timeout=15)
    s.starttls()
    s.login(user, pw)
    return s, None

def email_search(query="ALL", mailbox="INBOX", max_results=20, account="default"):
    try:
        c, err = _connect_imap(account)
        if err:
            return err
        c.select(mailbox)
        _, data = c.search(None, query)
        ids = data[0].split() if data[0] else []
        ids = ids[-max_results:]
        results = []
        for mid in ids:
            _, d = c.fetch(mid, "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
            if d[0][1]:
                msg = eml.message_from_bytes(d[0][1])
                results.append(f"ID:{mid.decode()} | {account} | {msg['Date']} | {msg['From']} | {msg['Subject']}")
        c.logout()
        return '\n'.join(results) if results else "(keine)"
    except Exception as e:
        return f"❌ {e}"

def email_read(mail_id, mailbox="INBOX", account="default"):
    c = None
    try:
        c, err = _connect_imap(account)
        if err:
            return err
        c.select(mailbox)
        _, d = c.fetch(mail_id.encode(), "(BODY[])")
        if d[0][1]:
            msg = eml.message_from_bytes(d[0][1])
            subj = msg['Subject'] or "(kein Betreff)"
            fr = msg['From'] or "(unbekannt)"
            dt = msg['Date'] or ""
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode('utf-8', errors='replace')
                        break
                    elif part.get_content_type() == "text/html":
                        body = part.get_payload(decode=True).decode('utf-8', errors='replace')[:2000]
            else:
                body = msg.get_payload(decode=True).decode('utf-8', errors='replace')
            return f"Von: {fr}\nDatum: {dt}\nBetreff: {subj}\nKonto: {account}\n\n{body[:5000]}"
        return "(leer)"
    except Exception as e:
        return f"❌ {e}"
    finally:
        if c:
            try:
                c.logout()
            except Exception:
                pass

def email_send(to, subject, body, cc="", bcc="", account="default"):
    s = None
    try:
        ck = _acct_keys(account)
        user = ck["smtp_user"]
        s, err = _connect_smtp(account)
        if err:
            return err
        msg = MIMEMultipart()
        msg['From'] = user
        msg['To'] = to
        msg['Subject'] = subject
        if cc:
            msg['Cc'] = cc
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        all_recip = [to] + ([cc] if cc else [])
        s.sendmail(user, all_recip, msg.as_string())
        return f"✅ Email an {to} gesendet (Konto: {account}): {subject}"
    except Exception as e:
        return f"❌ {e}"
    finally:
        if s:
            try:
                s.quit()
            except Exception:
                pass

def email_list_accounts():
    return _list_accounts()

TOOLS = [
    {"type":"function","function":{"name":"email_search","description":"Durchsuche IMAP-Postfach (z.B. 'FROM ben@x.de', 'SUBJECT meeting', 'SINCE 01-Jun-2026', 'UNANSWERED', 'UNSEEN'). Standard: ALL = neueste 20.","parameters":{"type":"object","properties":{"query":{"type":"string","description":"IMAP-Suchfilter","default":"ALL"},"mailbox":{"type":"string","description":"Postfach","default":"INBOX"},"max_results":{"type":"integer","description":"Max Ergebnisse","default":20},"account":{"type":"string","description":"E-Mail-Konto (optional, default='default')"}},"required":[]}}},  # noqa: E501
    {"type":"function","function":{"name":"email_read","description":"Lese eine Email per ID (aus email_search). Rückgabe: Von, Datum, Betreff, Body.","parameters":{"type":"object","properties":{"mail_id":{"type":"string","description":"Email-ID aus email_search"},"mailbox":{"type":"string","description":"Postfach","default":"INBOX"},"account":{"type":"string","description":"E-Mail-Konto (optional, default='default')"}},"required":["mail_id"]}}},  # noqa: E501
    {"type":"function","function":{"name":"email_send","description":"Sende eine Email via SMTP. Pflicht: to, subject, body. Optional: cc, bcc.","parameters":{"type":"object","properties":{"to":{"type":"string","description":"Empfänger (Email-Adresse)"},"subject":{"type":"string","description":"Betreff"},"body":{"type":"string","description":"Nachrichtentext"},"cc":{"type":"string","description":"CC (optional)"},"bcc":{"type":"string","description":"BCC (optional)"},"account":{"type":"string","description":"E-Mail-Konto (optional, default='default')"}},"required":["to","subject","body"]}}},  # noqa: E501
    {"type":"function","function":{"name":"email_list_accounts","description":"Liste alle konfigurierten E-Mail-Konten auf.","parameters":{"type":"object","properties":{},"required":[]}}},
]

TOOL_MAP = {
    "email_search": email_search,
    "email_read": email_read,
    "email_send": email_send,
    "email_list_accounts": email_list_accounts,
}

PROMPT_EXTRA = (
    "Email (Mehrere Konten unterstützt):\n"
    "  - **email_search**: Postfach durchsuchen (IMAP-Syntax: ALL, FROM x, SUBJECT y, SINCE datum)\n"
    "    BEISPIELE:\n"
    "      email_search(query='UNANSWERED'): Unbeantwortete E-Mails\n"
    "      email_search(query='UNSEEN'): Ungelesene E-Mails\n"
    "      email_search(query='FROM ben@x.de'): E-Mails von einer Person\n"
    "      email_search(query='SINCE 01-Jul-2026'): E-Mails seit einem Datum\n"
    "  - **email_read**: Email mit ID lesen\n"
    "  - **email_send**: Email senden (to, subject, body, account)\n"
    "  - **email_list_accounts**: Alle konfigurierten Konten auflisten\n"
    "  Standard-Konto (default): vault email/imap_server, email/imap_user, email/imap_password\n"
    "  Weitere Konten: vault email/accounts/NAME/imap_server etc.\n"
)
