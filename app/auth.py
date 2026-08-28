import secrets
import time
from functools import wraps

from flask import jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from app.state import AUTH_USERS, issue_auth_token, revoke_auth_token, save_auth_users, token_hash


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
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    token = auth[7:].strip()
    if not token:
        return None
    presented_hash = token_hash(token)
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
            # Legacy records are upgraded lazily on first use. This preserves
            # existing sessions while ensuring the plaintext secret is removed.
            issue_auth_token(data)
            save_auth_users()
            return username
    return None


def _request_has_admin_token():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return False
    username = _authenticated_username()
    return bool(username and (AUTH_USERS.get(username, {}).get('role') == 'admin' or username == 'admin'))


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
        user = AUTH_USERS.get(username, {})
        if user.get('role') != 'admin' and username != 'admin':
            return jsonify({'success': False, 'error': 'Forbidden'}), 403
        return f(*args, **kwargs)
    return decorated
