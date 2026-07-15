import json
import os
import threading
from datetime import UTC, datetime

from app.config import DATA_DIR, logger

_AUDIT_LOCK = threading.Lock()
_SECRET_FIELDS = ('password', 'passwd', 'pass', 'secret', 'api_key', 'token', 'credential', 'authorization', 'cookie')


def _redact(value, key=''):
    key_lower = str(key).lower()
    if any(secret in key_lower for secret in _SECRET_FIELDS):
        return '***'
    if isinstance(value, dict):
        return {str(item_key): _redact(item_value, item_key) for item_key, item_value in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value[:50]]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:500]


def _target_resource(args):
    for key in ('path', 'url', 'host', 'filename', 'source', 'destination', 'key'):
        if key in (args or {}):
            return _redact(args[key], key)
    return None


def audit_tool(
    tool_name,
    user,
    args,
    success,
    result_preview=None,
    duration_ms=0,
    *,
    request_id=None,
    session_id=None,
    confirmation='not_required',
    error_class=None,
):
    """Append a structured, redacted audit event without recording tool output."""
    entry = {
        'timestamp': datetime.now(UTC).isoformat(),
        'event': 'privileged_tool_execution',
        'request_id': request_id,
        'session_id': session_id,
        'user': user or 'unknown',
        'tool': str(tool_name),
        'target_resource': _target_resource(args),
        'arguments': _redact(args or {}),
        'confirmation': confirmation,
        'outcome': 'success' if success else 'failure',
        'error_class': error_class,
        'duration_ms': max(0, int(duration_ms or 0)),
    }
    audit_file = DATA_DIR / 'audit.jsonl'
    try:
        audit_file.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(entry, ensure_ascii=False, separators=(',', ':')) + '\n'
        with _AUDIT_LOCK:
            descriptor = os.open(audit_file, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.write(descriptor, line.encode('utf-8'))
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            try:
                os.chmod(audit_file, 0o600)
            except OSError:
                pass
    except Exception:
        logger.exception('Could not write audit event')


_audit_log = audit_tool
