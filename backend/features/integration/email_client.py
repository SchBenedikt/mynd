"""
Email Integration Client (IMAP)
Provides access to email accounts via IMAP for AI context and search
"""

import imaplib
import email
import logging
import re
import smtplib
import ssl
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.header import decode_header
from typing import Dict, Any, List, Optional

from .api_registry import APIClient

logger = logging.getLogger(__name__)


def _decode_header_value(value: str) -> str:
    """Decode an encoded email header value to a plain string."""
    if not value:
        return ''
    parts = decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                decoded.append(part.decode(charset or 'utf-8', errors='replace'))
            except Exception:
                decoded.append(part.decode('utf-8', errors='replace'))
        else:
            decoded.append(str(part))
    return ' '.join(decoded).strip()


def _get_email_body(msg) -> str:
    """Extract plain-text body from an email.message.Message object."""
    body = ''
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get('Content-Disposition', ''))
            if content_type == 'text/plain' and 'attachment' not in disposition:
                charset = part.get_content_charset() or 'utf-8'
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        body = payload.decode(charset, errors='replace')
                        break
                except Exception:
                    pass
    else:
        charset = msg.get_content_charset() or 'utf-8'
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode(charset, errors='replace')
        except Exception:
            pass
    # Normalize whitespace
    body = re.sub(r'\r\n', '\n', body)
    body = re.sub(r'\n{3,}', '\n\n', body)
    return body.strip()


class EmailClient(APIClient):
    """IMAP email client for AI-powered email integration."""

    # Maximum number of emails fetched per folder during a sync
    DEFAULT_MAX_EMAILS = 50
    # Characters of email body included in keyword scoring
    SCORING_BODY_LENGTH = 500
    # Characters of body included in the get_email_summary preview
    SUMMARY_PREVIEW_LENGTH = 300
    # Helpful presets for common providers so users do not need to enter every server manually
    PROVIDER_PRESETS = {
        'custom': {},
        'web.de': {
            'imap_host': 'imap.web.de',
            'imap_port': 993,
            'use_ssl': True,
            'smtp_host': 'smtp.web.de',
            'smtp_port': 587,
            'smtp_use_ssl': False,
            'smtp_starttls': True,
        },
        'gmx.de': {
            'imap_host': 'imap.gmx.net',
            'imap_port': 993,
            'use_ssl': True,
            'smtp_host': 'mail.gmx.net',
            'smtp_port': 587,
            'smtp_use_ssl': False,
            'smtp_starttls': True,
        },
        'gmail.com': {
            'imap_host': 'imap.gmail.com',
            'imap_port': 993,
            'use_ssl': True,
            'smtp_host': 'smtp.gmail.com',
            'smtp_port': 587,
            'smtp_use_ssl': False,
            'smtp_starttls': True,
        },
        'outlook.com': {
            'imap_host': 'outlook.office365.com',
            'imap_port': 993,
            'use_ssl': True,
            'smtp_host': 'smtp.office365.com',
            'smtp_port': 587,
            'smtp_use_ssl': False,
            'smtp_starttls': True,
        },
        'hotmail.com': {
            'imap_host': 'outlook.office365.com',
            'imap_port': 993,
            'use_ssl': True,
            'smtp_host': 'smtp.office365.com',
            'smtp_port': 587,
            'smtp_use_ssl': False,
            'smtp_starttls': True,
        },
    }

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the email client.

        Args:
            config: Configuration dict with:
                - imap_host: IMAP server hostname
                - imap_port: IMAP server port (default 993)
                - username: Email address / login
                - password: Account password or app password
                - folders: Comma-separated list of IMAP folders to sync
                           (default: INBOX)
                - max_emails: Maximum emails to fetch per folder (default: 50)
                - use_ssl: Whether to use SSL (default: True)
        """
        preset_name = str(config.get('provider_preset', 'custom') or 'custom').strip().lower()
        preset = self.PROVIDER_PRESETS.get(preset_name, {})

        self.provider_preset = preset_name
        self.username = str(config.get('username', '')).strip()
        self.password = config.get('password', '')
        self.from_address = str(config.get('from_address') or self.username).strip()
        self.from_name = str(config.get('from_name', '')).strip()

        self.imap_host = str(config.get('imap_host') or preset.get('imap_host') or '').strip()
        self.imap_port = int(config.get('imap_port') or preset.get('imap_port') or 993)
        self.use_ssl = str(config.get('use_ssl', preset.get('use_ssl', 'true'))).lower() not in ('false', '0', 'no')

        raw_smtp_host = str(config.get('smtp_host') or preset.get('smtp_host') or '').strip()
        inferred_smtp_host = self._infer_smtp_host(self.imap_host)
        self.smtp_host = raw_smtp_host or inferred_smtp_host
        self.smtp_port = int(config.get('smtp_port') or preset.get('smtp_port') or 587)
        self.smtp_use_ssl = str(config.get('smtp_use_ssl', preset.get('smtp_use_ssl', 'false'))).lower() in ('true', '1', 'yes')
        self.smtp_starttls = str(config.get('smtp_starttls', preset.get('smtp_starttls', 'true'))).lower() not in ('false', '0', 'no')

        raw_folders = str(config.get('folders', 'INBOX') or 'INBOX').strip()
        self.sync_all_folders = raw_folders.upper() in ('ALL', '*')
        self.folders = [f.strip() for f in raw_folders.split(',') if f.strip() and f.strip().upper() not in ('ALL', '*')]
        self.max_emails = int(config.get('max_emails', self.DEFAULT_MAX_EMAILS))

        if not self.imap_host or not self.username or not self.password:
            raise ValueError("imap_host, username and password are required for EmailClient")

    @staticmethod
    def _infer_smtp_host(imap_host: str) -> str:
        """Infer a likely SMTP host from an IMAP host."""
        host = str(imap_host or '').strip()
        if not host:
            return ''
        if host.startswith('imap.'):
            return 'smtp.' + host[len('imap.'):]
        if host.endswith('imap.gmail.com'):
            return 'smtp.gmail.com'
        if host.endswith('outlook.office365.com'):
            return 'smtp.office365.com'
        return host

    @classmethod
    def _get_preset_defaults(cls, preset_name: str) -> Dict[str, Any]:
        """Return default values for a provider preset."""
        return dict(cls.PROVIDER_PRESETS.get(str(preset_name or 'custom').strip().lower(), {}))

    # ------------------------------------------------------------------
    # APIClient interface
    # ------------------------------------------------------------------

    def get_api_name(self) -> str:
        return 'email'

    def get_config_schema(self) -> Dict[str, Any]:
        return {
            'provider_preset': {
                'type': 'string',
                'required': False,
                'description': 'Provider-Vorlage / vorkonfigurierte Mail-Server',
                'default': 'custom',
                'options': [
                    {'label': 'Eigene Angaben', 'value': 'custom'},
                    {'label': 'WEB.DE', 'value': 'web.de'},
                    {'label': 'GMX', 'value': 'gmx.de'},
                    {'label': 'Gmail', 'value': 'gmail.com'},
                    {'label': 'Outlook / Microsoft', 'value': 'outlook.com'}
                ]
            },
            'imap_host': {
                'type': 'string',
                'required': True,
                'description': 'IMAP-Servername',
                'example': 'imap.gmail.com'
            },
            'imap_port': {
                'type': 'number',
                'required': False,
                'description': 'IMAP-Port (993 für SSL, 143 für STARTTLS)',
                'default': 993
            },
            'username': {
                'type': 'string',
                'required': True,
                'description': 'E-Mail-Adresse / Login',
                'example': 'you@example.com'
            },
            'password': {
                'type': 'string',
                'required': True,
                'description': 'Passwort oder App-Passwort',
                'secret': True
            },
            'smtp_host': {
                'type': 'string',
                'required': False,
                'description': 'SMTP-Servername für den Versand',
                'example': 'smtp.web.de'
            },
            'smtp_port': {
                'type': 'number',
                'required': False,
                'description': 'SMTP-Port (587 mit STARTTLS, 465 mit SSL)',
                'default': 587
            },
            'smtp_starttls': {
                'type': 'string',
                'required': False,
                'description': 'STARTTLS für SMTP verwenden (true/false)',
                'default': 'true'
            },
            'smtp_use_ssl': {
                'type': 'string',
                'required': False,
                'description': 'SMTP direkt mit SSL verbinden (true/false)',
                'default': 'false'
            },
            'folders': {
                'type': 'string',
                'required': False,
                'description': 'IMAP-Ordner, kommagetrennt, oder ALL für alle Ordner',
                'default': 'INBOX',
                'example': 'INBOX,Sent'
            },
            'max_emails': {
                'type': 'number',
                'required': False,
                'description': 'Maximale Anzahl der Mails pro Ordner',
                'default': 50
            },
            'use_ssl': {
                'type': 'string',
                'required': False,
                'description': 'SSL für IMAP verwenden (true/false)',
                'default': 'true'
            },
            'from_name': {
                'type': 'string',
                'required': False,
                'description': 'Absendername für gesendete Mails',
                'example': 'Max Mustermann'
            },
            'from_address': {
                'type': 'string',
                'required': False,
                'description': 'Absenderadresse, falls sie vom Login abweicht',
                'example': 'max@example.com'
            }
        }

    def test_connection(self) -> bool:
        """Test IMAP connection."""
        conn = None
        logged_out = False
        try:
            conn = self._connect()
            conn.logout()
            logged_out = True
            return True
        except Exception as e:
            logger.error("Email connection test failed: %s", e)
            return False
        finally:
            if conn and not logged_out:
                try:
                    conn.logout()
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> imaplib.IMAP4:
        """Create and authenticate an IMAP connection."""
        if self.use_ssl:
            conn = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
        else:
            conn = imaplib.IMAP4(self.imap_host, self.imap_port)
        conn.login(self.username, self.password)
        return conn

    def _connect_smtp(self):
        """Create and authenticate an SMTP connection."""
        if not self.smtp_host:
            raise ValueError('smtp_host is required for sending emails')

        if self.smtp_use_ssl:
            conn = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=ssl.create_default_context())
        else:
            conn = smtplib.SMTP(self.smtp_host, self.smtp_port)
            conn.ehlo()
            if self.smtp_starttls:
                conn.starttls(context=ssl.create_default_context())
                conn.ehlo()

        conn.login(self.username, self.password)
        return conn

    def _format_from_header(self) -> str:
        """Build a user-friendly From header."""
        if self.from_name and self.from_address:
            return f'{self.from_name} <{self.from_address}>'
        return self.from_address or self.username

    @staticmethod
    def _decode_folder_name(folder_name: str) -> str:
        """Decode an IMAP folder name if the server uses modified UTF-7."""
        try:
            return imaplib.IMAP4._decode_utf7(folder_name)
        except Exception:
            return folder_name

    def list_folders(self) -> List[str]:
        """Return all available IMAP folders from the server."""
        conn = None
        folders: List[str] = []
        try:
            conn = self._connect()
            status, data = conn.list()
            if status != 'OK' or not data:
                return folders

            for raw_line in data:
                if not raw_line:
                    continue
                line = raw_line.decode('utf-8', errors='replace') if isinstance(raw_line, bytes) else str(raw_line)
                match = re.search(r'"([^"]+)"\s*$', line)
                if match:
                    folder_name = match.group(1)
                else:
                    folder_name = line.split(' ', 2)[-1].strip().strip('"')

                folder_name = self._decode_folder_name(folder_name).strip()
                if folder_name and folder_name not in folders:
                    folders.append(folder_name)

        except Exception as e:
            logger.warning('Failed to list IMAP folders: %s', e)
        finally:
            if conn:
                try:
                    conn.logout()
                except Exception:
                    pass

        return folders

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_recent_emails(
        self,
        folder: str = 'INBOX',
        limit: int = 20,
        days_back: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent emails from *folder*.

        Returns a list of dicts with keys:
            uid, subject, sender, recipients, date, body, folder
        """
        conn = None
        emails: List[Dict[str, Any]] = []
        try:
            conn = self._connect()
            # Some servers require quoting folder names with spaces
            folder_name = f'"{folder}"' if ' ' in folder else folder
            status, _ = conn.select(folder_name, readonly=True)
            if status != 'OK':
                logger.warning("Cannot select folder '%s'", folder)
                return emails

            since_date = (datetime.now() - timedelta(days=days_back)).strftime('%d-%b-%Y')
            status, data = conn.search(None, f'SINCE {since_date}')
            if status != 'OK' or not data or not data[0]:
                return emails

            msg_ids = data[0].split()
            # Fetch the most recent *limit* messages
            msg_ids = msg_ids[-limit:]

            for msg_id in reversed(msg_ids):
                try:
                    status, raw = conn.fetch(msg_id, '(RFC822)')
                    if status != 'OK' or not raw or raw[0] is None:
                        continue

                    raw_email = raw[0][1]
                    if not isinstance(raw_email, bytes):
                        continue

                    msg = email.message_from_bytes(raw_email)

                    subject = _decode_header_value(msg.get('Subject', '(no subject)'))
                    sender = _decode_header_value(msg.get('From', ''))
                    recipients = _decode_header_value(msg.get('To', ''))
                    date_str = msg.get('Date', '')
                    body = _get_email_body(msg)

                    emails.append({
                        'uid': msg_id.decode('ascii', errors='replace'),
                        'subject': subject,
                        'sender': sender,
                        'recipients': recipients,
                        'date': date_str,
                        'body': body,
                        'folder': folder,
                        'message_id': msg.get('Message-ID', '')
                    })
                except Exception as e:
                    logger.warning("Error parsing email %s: %s", msg_id, e)
                    continue

        except imaplib.IMAP4.error as e:
            logger.error("IMAP error fetching emails from '%s': %s", folder, e)
        except Exception as e:
            logger.error("Unexpected error fetching emails: %s", e)
        finally:
            if conn:
                try:
                    conn.logout()
                except Exception:
                    pass

        return emails

    def fetch_all_folders(self) -> List[Dict[str, Any]]:
        """
        Fetch emails from all configured folders.

        Returns a flat list of email dicts (same format as fetch_recent_emails).
        """
        all_emails: List[Dict[str, Any]] = []

        target_folders = self.list_folders() if self.sync_all_folders else self.folders
        if not target_folders:
            target_folders = ['INBOX']

        per_folder_limit = max(1, self.max_emails // len(target_folders)) if len(target_folders) > 0 else self.max_emails

        for folder in target_folders:
            try:
                folder_emails = self.fetch_recent_emails(
                    folder=folder,
                    limit=per_folder_limit
                )
                all_emails.extend(folder_emails)
                logger.info("Fetched %d emails from folder '%s'", len(folder_emails), folder)
            except Exception as e:
                logger.warning("Failed to fetch emails from folder '%s': %s", folder, e)

        return all_emails

    def search_emails(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search emails across all configured folders using simple keyword matching.

        Fetches recent emails and filters by *query* keywords.
        """
        all_emails = self.fetch_all_folders()
        if not all_emails or not query.strip():
            return all_emails[:limit]

        query_lower = query.lower()
        keywords = [w.lower() for w in re.findall(r'\w+', query_lower) if len(w) > 2]

        def _score(mail: Dict) -> int:
            haystack = ' '.join([
                mail.get('subject', ''),
                mail.get('sender', ''),
                mail.get('body', '')[:self.SCORING_BODY_LENGTH]
            ]).lower()
            return sum(1 for kw in keywords if kw in haystack)

        scored = [(m, _score(m)) for m in all_emails]
        scored.sort(key=lambda x: x[1], reverse=True)

        # Include all emails with at least one keyword match, fall back to all
        matched = [m for m, s in scored if s > 0]
        if not matched:
            matched = [m for m, _ in scored]

        return matched[:limit]

    def get_email_summary(self, max_emails: int = 20) -> Dict[str, Any]:
        """
        Return a structured summary of recent emails for AI context.

        Returns a dict with:
            emails: list of email summaries
            count: total count
            folders: folders scanned
        """
        all_emails = self.fetch_all_folders()
        recent = all_emails[:max_emails]

        summaries = []
        for mail in recent:
            body_preview = mail.get('body', '')
            if len(body_preview) > self.SUMMARY_PREVIEW_LENGTH:
                body_preview = body_preview[:self.SUMMARY_PREVIEW_LENGTH] + '...'
            summaries.append({
                'subject': mail.get('subject', '(no subject)'),
                'sender': mail.get('sender', ''),
                'date': mail.get('date', ''),
                'folder': mail.get('folder', ''),
                'body_preview': body_preview
            })

        return {
            'emails': summaries,
            'count': len(all_emails),
            'folders': self.folders
        }

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        reply_to: Optional[str] = None,
        from_name: Optional[str] = None,
        from_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send an email via SMTP."""
        recipients = [addr.strip() for addr in re.split(r'[;,]', to or '') if addr.strip()]
        if not recipients:
            raise ValueError('At least one recipient is required')

        cc_recipients = [addr.strip() for addr in re.split(r'[;,]', cc or '') if addr.strip()]
        bcc_recipients = [addr.strip() for addr in re.split(r'[;,]', bcc or '') if addr.strip()]
        all_recipients = recipients + cc_recipients + bcc_recipients

        message = EmailMessage()
        message['To'] = ', '.join(recipients)
        if cc_recipients:
            message['Cc'] = ', '.join(cc_recipients)
        if reply_to:
            message['Reply-To'] = reply_to
        message['Subject'] = subject or '(ohne Betreff)'

        effective_from_name = str(from_name or self.from_name or '').strip()
        effective_from_address = str(from_address or self.from_address or self.username).strip()
        if effective_from_name:
            message['From'] = f'{effective_from_name} <{effective_from_address}>'
        else:
            message['From'] = effective_from_address

        message.set_content(body or '')

        conn = None
        try:
            conn = self._connect_smtp()
            conn.send_message(message, from_addr=effective_from_address, to_addrs=all_recipients)
            logger.info('Email sent to %s', ', '.join(recipients))
            return {
                'success': True,
                'to': recipients,
                'cc': cc_recipients,
                'bcc': bcc_recipients,
                'subject': subject,
                'from': message['From']
            }
        finally:
            if conn:
                try:
                    conn.quit()
                except Exception:
                    try:
                        conn.close()
                    except Exception:
                        pass
