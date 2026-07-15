import json
import os
import secrets
from functools import wraps

from flask import jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from app.config import AUTH_CONFIG_FILE, AUTH_FILE, DATA_DIR, logger
from app.state import AUTH_USERS


def _verify_password(user, password):
    password_hash = user.get('password_hash')
    if password_hash:
        return check_password_hash(password_hash, password)
    if secrets.compare_digest(str(user.get('password', '')), str(password)):
        user['password_hash'] = generate_password_hash(password)
        user.pop('password', None)
        AUTH_FILE.write_text(json.dumps(AUTH_USERS, indent=2))
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
    for username, data in AUTH_USERS.items():
        stored = str(data.get('token', ''))
        if stored and secrets.compare_digest(stored, token):
            return username
    return None


def _request_has_admin_token():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return False
    token = auth[7:]
    return any(
        secrets.compare_digest(str(user.get('token', '')), token)
        and (user.get('role') == 'admin' or username == 'admin')
        for username, user in AUTH_USERS.items()
    )


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
