"""
Email Integration Client (IMAP)
Provides access to email accounts via IMAP for AI context and search
"""

import imaplib
import email
import logging
import re
import time
from datetime import datetime, timedelta
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
        self.imap_host = config.get('imap_host', '').strip()
        self.imap_port = int(config.get('imap_port', 993))
        self.username = config.get('username', '').strip()
        self.password = config.get('password', '')
        raw_folders = config.get('folders', 'INBOX')
        self.folders = [f.strip() for f in raw_folders.split(',') if f.strip()]
        self.max_emails = int(config.get('max_emails', self.DEFAULT_MAX_EMAILS))
        self.use_ssl = str(config.get('use_ssl', 'true')).lower() not in ('false', '0', 'no')

        if not self.imap_host or not self.username or not self.password:
            raise ValueError("imap_host, username and password are required for EmailClient")

    # ------------------------------------------------------------------
    # APIClient interface
    # ------------------------------------------------------------------

    def get_api_name(self) -> str:
        return 'email'

    def get_config_schema(self) -> Dict[str, Any]:
        return {
            'imap_host': {
                'type': 'string',
                'required': True,
                'description': 'IMAP server hostname',
                'example': 'imap.gmail.com'
            },
            'imap_port': {
                'type': 'number',
                'required': False,
                'description': 'IMAP server port (993 for SSL, 143 for STARTTLS)',
                'default': 993
            },
            'username': {
                'type': 'string',
                'required': True,
                'description': 'Email address / IMAP login',
                'example': 'you@example.com'
            },
            'password': {
                'type': 'string',
                'required': True,
                'description': 'Account password or app-specific password',
                'secret': True
            },
            'folders': {
                'type': 'string',
                'required': False,
                'description': 'Comma-separated IMAP folders to index (default: INBOX)',
                'default': 'INBOX',
                'example': 'INBOX,Sent'
            },
            'max_emails': {
                'type': 'number',
                'required': False,
                'description': 'Maximum number of recent emails to fetch per folder',
                'default': 50
            },
            'use_ssl': {
                'type': 'string',
                'required': False,
                'description': 'Use SSL for IMAP connection (true/false)',
                'default': 'true'
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
        per_folder_limit = max(1, self.max_emails // len(self.folders)) if len(self.folders) > 0 else self.max_emails

        for folder in self.folders:
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
