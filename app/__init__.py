#!/usr/bin/env python3
"""MYND Flask application package."""

import ipaddress
import json
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from app.auth import _authenticated_username, is_admin_username
from app.config import AUTH_CONFIG_FILE, SETUP_DONE_FILE, logger
from app.config import AUTH_FILE as AUTH_FILE
from app.config import DATA_DIR as DATA_DIR
from app.config import _app_lock as _app_lock
from app.state import AUTH_USERS as AUTH_USERS

load_dotenv()

flask_app = Flask(__name__)
flask_app.config['MAX_CONTENT_LENGTH'] = 55 * 1024 * 1024
# Backwards-compatible public name used by tests and WSGI servers.
app = flask_app


def create_app(test_config=None):
    if test_config:
        flask_app.config.update(test_config)
    return flask_app


@flask_app.after_request
def add_cors_headers(response):
    origin = request.headers.get('Origin', '')
    raw = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000')
    allowed_origins = {v.strip() for v in raw.split(',') if v.strip()}
    if origin and ('*' in allowed_origins):
        response.headers['Access-Control-Allow-Origin'] = '*'
    elif origin in allowed_origins:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Vary'] = 'Origin'
    if response.headers.get('Access-Control-Allow-Origin') and response.headers['Access-Control-Allow-Origin'] != '*':
        response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
    response.headers['Access-Control-Expose-Headers'] = 'Content-Type,Authorization'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(self), geolocation=()'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; object-src 'none'; "
        "script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
        "font-src 'self' data: https://cdnjs.cloudflare.com; img-src 'self' data: blob: https:; "
        "connect-src 'self' http://127.0.0.1:* http://localhost:* https:; frame-src 'self'"
    )
    return response


_ADMIN_API_PREFIXES = (
    '/api/admin/',
    '/api/ai/',
    '/api/ollama/',
    '/api/permission/',
    '/api/vault/',
    '/api/knowledge/',
    '/api/indexing/',
    '/api/calendar/',
    '/api/tasks/',
    '/api/security/',
    '/api/references',
    '/api/registry/',
    '/api/training/',
    '/api/email',
    '/api/nextcloud/',
    '/api/ui/',
    '/api/immich/',
    '/api/backup/',
    '/api/automations',
    '/api/notifications/',
    '/api/plugins',
    '/api/generated/',
    '/api/tts/',
    '/api/assistant/',
    '/api/agent/briefing',
)


def _auth_config():
    config = {'requireLogin': True}
    if AUTH_CONFIG_FILE.exists():
        try:
            stored = json.loads(AUTH_CONFIG_FILE.read_text())
            if isinstance(stored, dict):
                config.update(stored)
        except (OSError, ValueError, TypeError):
            pass
    return config


def _is_loopback_request():
    try:
        return ipaddress.ip_address(request.remote_addr or '').is_loopback
    except ValueError:
        return False


def _requires_admin(path):
    return any(path == prefix.rstrip('/') or path.startswith(prefix) for prefix in _ADMIN_API_PREFIXES)


@flask_app.errorhandler(500)
def handle_500(e):
    logger.exception(f'500 Internal Server Error: {e}')
    return jsonify({'success': False, 'error': 'Interner Serverfehler – bitte Backend-Logs prüfen.'}), 500


@flask_app.errorhandler(Exception)
def handle_unhandled(e):
    if isinstance(e, HTTPException):
        logger.error('HTTP error: %s', e)
        return jsonify({'success': False, 'error': 'Request failed'}), e.code
    logger.exception(f'Unbehandelte Exception: {e}')
    return jsonify({'success': False, 'error': 'Request failed'}), 500


@flask_app.before_request
def protect_api_by_default():
    if request.method == 'OPTIONS' or not request.path.startswith('/api/'):
        return None
    public = {
        '/api/health',
        '/api/capabilities',
        '/api/auth/login',
        '/api/auth/register',
        '/api/auth/me',
        '/api/setup/status',
    }
    if request.path in public or (request.path == '/api/auth/config' and request.method == 'GET'):
        return None
    if request.path.startswith('/api/automations/webhook/') and request.method == 'POST':
        return None
    if not SETUP_DONE_FILE.exists() and request.path in {
        '/api/setup/bootstrap',
        '/api/ollama/status',
        '/api/ollama/models',
        '/api/nextcloud/oauth/config',
        '/api/nextcloud/loginflow/start',
        '/api/nextcloud/loginflow/poll',
        '/api/ui/system-config',
    }:
        if not _is_loopback_request() and os.getenv('MYND_ALLOW_REMOTE_SETUP') != '1':
            return jsonify({'success': False, 'error': 'Initial setup is restricted to the local machine'}), 403
        return None
    username = _authenticated_username()
    if not username:
        if not _auth_config().get('requireLogin', True) and not _requires_admin(request.path):
            request.current_user = 'anonymous'
            return None
        return jsonify({'authenticated': False, 'error': 'Unauthorized'}), 401
    request.current_user = username
    if _requires_admin(request.path) and not is_admin_username(username):
        return jsonify({'success': False, 'error': 'Administrator access required'}), 403
    if (
        request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}
        and request.cookies.get('mynd_session')
        and not request.headers.get('Authorization')
    ):
        origin = request.headers.get('Origin')
        if origin:
            raw = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000')
            allowed = {item.strip() for item in raw.split(',') if item.strip()}
            if origin not in allowed:
                return jsonify({'success': False, 'error': 'Origin not allowed'}), 403
    return None


# Import routes – triggers all @flask_app.route decorators
from app import routes as _routes  # noqa: F401, E402

# Importing a submodule can bind the package name in this module; restore the
# documented WSGI/test alias after route registration.
app = flask_app
