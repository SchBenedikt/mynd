import secrets
import threading
import time
from collections import defaultdict, deque
from functools import wraps

from flask import jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from app.state import AUTH_STATE_LOCK, AUTH_USERS, issue_auth_token, revoke_auth_token, save_auth_users, token_hash

_AUTH_ATTEMPTS = defaultdict(deque)
_AUTH_ATTEMPTS_LOCK = threading.Lock()
AUTH_RATE_LIMIT = 8
AUTH_RATE_WINDOW_SECONDS = 5 * 60


def _presented_token():
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth[7:].strip()
    return str(request.cookies.get('mynd_session') or '').strip()


def auth_rate_limited(action: str, identity: str = '') -> bool:
    """Return True after too many failed auth attempts from one client."""
    remote = request.remote_addr or 'unknown'
    key = f'{action}:{remote}:{identity.strip().lower()[:100]}'
    now = time.monotonic()
    with _AUTH_ATTEMPTS_LOCK:
        attempts = _AUTH_ATTEMPTS[key]
        while attempts and now - attempts[0] > AUTH_RATE_WINDOW_SECONDS:
            attempts.popleft()
        return len(attempts) >= AUTH_RATE_LIMIT


def record_auth_failure(action: str, identity: str = '') -> None:
    remote = request.remote_addr or 'unknown'
    key = f'{action}:{remote}:{identity.strip().lower()[:100]}'
    with _AUTH_ATTEMPTS_LOCK:
        _AUTH_ATTEMPTS[key].append(time.monotonic())


def clear_auth_failures(action: str, identity: str = '') -> None:
    remote = request.remote_addr or 'unknown'
    key = f'{action}:{remote}:{identity.strip().lower()[:100]}'
    with _AUTH_ATTEMPTS_LOCK:
        _AUTH_ATTEMPTS.pop(key, None)


def is_admin_username(username: str | None) -> bool:
    if not username:
        return False
    with AUTH_STATE_LOCK:
        user = dict(AUTH_USERS.get(username, {}))
    return user.get('role') == 'admin' or username == 'admin'


def _verify_password(user, password):
    password_hash = user.get('password_hash')
    if password_hash:
        return check_password_hash(password_hash, password)
    if secrets.compare_digest(str(user.get('password', '')), str(password)):
        user['password_hash'] = generate_password_hash(password)
        user.pop('password', None)
        save_auth_users()
        return True
    return False


def _set_password(user, password):
    user['password_hash'] = generate_password_hash(password)
    user.pop('password', None)


def _authenticated_username():
    token = _presented_token()
    if not token:
        return None
    presented_hash = token_hash(token)
    with AUTH_STATE_LOCK:
        for username, data in AUTH_USERS.items():
            stored_hash = str(data.get('token_hash', ''))
            expires_at = float(data.get('token_expires_at', 0) or 0)
            if stored_hash and secrets.compare_digest(stored_hash, presented_hash):
                # Tokens issued before expiry metadata existed remain valid once;
                # all newly issued tokens always carry an explicit expiry.
                if not expires_at:
                    return username
                if expires_at <= time.time():
                    revoke_auth_token(data)
                    save_auth_users()
                    return None
                return username
            # Migrate a legacy plaintext token on first successful use. This keeps
            # existing sessions functional while removing the secret from disk.
            legacy = str(data.get('token', ''))
            if legacy and secrets.compare_digest(legacy, token):
                issue_auth_token(data)
                save_auth_users()
                return username
    return None


def _request_has_admin_token():
    username = _authenticated_username()
    return is_admin_username(username)


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        username = _authenticated_username()
        if username:
            request.current_user = username
            return f(*args, **kwargs)
        return jsonify({'authenticated': False, 'error': 'Unauthorized'}), 401

    return decorated


def require_admin(f):
    @require_auth
    @wraps(f)
    def decorated(*args, **kwargs):
        username = request.current_user
        if not is_admin_username(username):
            return jsonify({'success': False, 'error': 'Forbidden'}), 403
        return f(*args, **kwargs)

    return decorated
