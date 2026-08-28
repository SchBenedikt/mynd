import hashlib
import json
import secrets
import threading
import time

from werkzeug.security import generate_password_hash

from app.audit import _audit_log as _audit_log
from app.config import AUTH_FILE, logger

_PROMPT_QUEUE = []
_app_lock = threading.Lock()

_PRIVILEGED_TOOL_PREFIXES = ('execute_', 'browser_', 'nextcloud_', 'vault_', 'memory_')
_PRIVILEGED_TOOL_NAMES = frozenset({'write_local_file', 'http_request', 'agent_browser', 'think'})

_auth_lock = threading.Lock()


AUTH_TOKEN_TTL = 24 * 60 * 60


def token_hash(token: str) -> str:
    return hashlib.sha256(str(token).encode('utf-8')).hexdigest()


def issue_auth_token(user: dict) -> str:
    token = secrets.token_hex(32)
    user['token_hash'] = token_hash(token)
    user['token_expires_at'] = time.time() + AUTH_TOKEN_TTL
    user.pop('token', None)
    return token


def revoke_auth_token(user: dict) -> None:
    user.pop('token', None)
    user.pop('token_hash', None)
    user.pop('token_expires_at', None)


def save_auth_users():
    with _auth_lock:
        AUTH_FILE.write_text(json.dumps(AUTH_USERS, indent=2))


# ── Auth state ─────────────────────────────────────────────
AUTH_USERS = {}
if AUTH_FILE.exists():
    try:
        AUTH_USERS.update(json.loads(AUTH_FILE.read_text()))
    except Exception:
        pass

if not AUTH_USERS:
    import secrets
    default_password = secrets.token_urlsafe(16)
    AUTH_USERS['admin'] = {
        'password_hash': generate_password_hash(default_password),
        'name': 'Admin',
        'role': 'admin',
    }
    save_auth_users()
    logger.warning('Created initial admin account with temporary password')

INDEXING_STATUS = {
    'status': 'idle', 'progress': 0, 'current_file': '',
    'processed_files': 0, 'total_files': 0, 'errors': [], 'elapsed_time': 0,
    'run_id': None,
}
INDEXING_CANCEL = threading.Event()
