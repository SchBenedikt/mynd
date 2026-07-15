import json
import threading
from datetime import UTC, date, datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

from app.config import AUTH_CONFIG_FILE, AUTH_FILE, DATA_DIR, logger

_PROMPT_QUEUE = []
_WEB_PROMPT_PENDING = None
_AGENT_SESSION = None
_PENDING_TOOL_CONFIRMS = {}
_app_lock = threading.Lock()

_PRIVILEGED_TOOL_PREFIXES = ('execute_', 'browser_', 'nextcloud_', 'vault_', 'memory_')
_PRIVILEGED_TOOL_NAMES = frozenset({'write_local_file', 'http_request', 'agent_browser', 'think'})

# ── Audit logging ─────────────────────────────────────────
def _audit_log(tool_name, user, args, success, result_preview, duration_ms):
    try:
        audit_file = DATA_DIR / 'audit.jsonl'
        safe_args = {}
        for k, v in (args or {}).items():
            if any(secret in k.lower() for secret in ['password', 'pass', 'secret', 'api', 'token', 'key']):
                safe_args[k] = '***'
            else:
                safe_args[k] = str(v)[:200]
        entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'tool': tool_name,
            'user': user or 'unknown',
            'args': safe_args,
            'success': success,
            'result_preview': str(result_preview)[:200] if result_preview else '',
            'duration_ms': duration_ms,
        }
        with open(audit_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    except Exception:
        pass

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
