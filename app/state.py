import json
import threading

from werkzeug.security import generate_password_hash

from app.audit import _audit_log as _audit_log
from app.config import AUTH_FILE, logger

_PROMPT_QUEUE = []
_PENDING_TOOL_CONFIRMS = {}
_app_lock = threading.Lock()

_PRIVILEGED_TOOL_PREFIXES = ('execute_', 'browser_', 'nextcloud_', 'vault_', 'memory_')
_PRIVILEGED_TOOL_NAMES = frozenset({'write_local_file', 'http_request', 'agent_browser', 'think'})

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
    AUTH_FILE.write_text(json.dumps(AUTH_USERS, indent=2))
    logger.warning('Created initial admin account with temporary password')

INDEXING_STATUS = {
    'status': 'idle', 'progress': 0, 'current_file': '',
    'processed_files': 0, 'total_files': 0, 'errors': [], 'elapsed_time': 0
}
