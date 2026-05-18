import logging
import requests
import os
import secrets
import hmac
import hashlib
from typing import Optional
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)


class NextcloudTalkClient:
    """Nextcloud Talk client with Bot API support and User-API fallback.

    Preferred: use Bot API (`/ocs/v2.php/apps/spreed/api/v1/bot/{token}/message`) when
    a bot secret is configured. Falls back to the user-facing OCS v1 message endpoint
    when the Bot API is not available or fails.
    """

    def __init__(self, url: str, username: Optional[str] = None, password: Optional[str] = None, bot_secret: Optional[str] = None):
        self.url = str(url).rstrip('/')
        self.username = username
        self.password = password
        # Bot secret may be provided explicitly or via env BRIEFING_TALK_WEBHOOK_SECRET
        self.bot_secret = bot_secret or os.getenv('BRIEFING_TALK_WEBHOOK_SECRET') or ''

    def _build_auth(self):
        if self.username is not None and self.password is not None:
            return HTTPBasicAuth(self.username, self.password)
        return None

    def send_message(self, room_token: str, message: str, format: str = 'plain') -> bool:
        """Send message preferring Bot API, fallback to User API.

        room_token: conversation token / room id
        message: text body
        """
        if not room_token:
            logger.warning('No Talk room_token provided')
            return False

        # Try Bot API when secret is available
        if self.bot_secret:
            ok = self._send_via_bot_api(room_token, message)
            if ok:
                return True

        # Fallback to user API (messages appear as the configured user)
        return self._send_via_user_api(room_token, message, format)

    def _send_via_bot_api(self, token: str, message: str) -> bool:
        try:
            endpoint = f"{self.url}/ocs/v2.php/apps/spreed/api/v1/bot/{token}/message"

            # random header (64 hex chars) and signature per Nextcloud docs
            random_header = secrets.token_hex(32)
            to_sign = (random_header + message).encode('utf-8')
            sig = hmac.new(self.bot_secret.encode('utf-8'), to_sign, hashlib.sha256).hexdigest()

            headers = {
                'OCS-APIRequest': 'true',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'X-Nextcloud-Talk-Bot-Random': random_header,
                'X-Nextcloud-Talk-Bot-Signature': sig,
            }

            resp = requests.post(endpoint, json={'message': message}, headers=headers, timeout=30)
            if resp.status_code in (200, 201):
                logger.info('✅ Sent Talk message via Bot API to token %s (sig_len=%d)', token[:8], len(sig))
                return True
            
            # Log detailed failure info
            resp_text = resp.text[:500] if resp.text else '(empty)'
            if resp.status_code == 401:
                logger.warning('⚠️ Bot API 401 (Unauthorized): Bot not installed or secret mismatch. Response: %s', resp_text)
            elif resp.status_code == 404:
                logger.warning('⚠️ Bot API 404: Endpoint not found or bot not set up for room. URL=%s', endpoint)
            else:
                logger.warning('⚠️ Bot API failed: status=%s body=%s', resp.status_code, resp_text)
            return False
        except Exception as e:
            logger.exception('❌ Error sending via Bot API: %s', e)
            return False

    def _send_via_user_api(self, room_id: str, message: str, format: str = 'plain') -> bool:
        try:
            endpoint = f"{self.url}/ocs/v1.php/apps/spreed/api/v1/rooms/{room_id}/message"
            headers = {
                'OCS-APIRequest': 'true',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            payload = {'message': message, 'format': format}
            auth = self._build_auth()
            resp = requests.post(endpoint, json=payload, headers=headers, auth=auth, timeout=30)
            if resp.status_code in (200, 201, 202):
                logger.info('✅ Sent Talk message via User API to room %s (status=%s)', room_id[:8], resp.status_code)
                return True
            
            resp_text = resp.text[:400] if resp.text else '(empty)'
            logger.warning('⚠️ User API message failed: status=%s body=%s', resp.status_code, resp_text)
            return False
        except Exception as e:
            logger.exception('❌ Error sending via User API: %s', e)
            return False
