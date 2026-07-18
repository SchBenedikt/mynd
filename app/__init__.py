#!/usr/bin/env python3
"""MYND Flask application package."""
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from app.auth import _authenticated_username
from app.config import AUTH_FILE as AUTH_FILE
from app.config import DATA_DIR as DATA_DIR
from app.config import SETUP_DONE_FILE, logger
from app.config import _app_lock as _app_lock
from app.state import _PENDING_TOOL_CONFIRMS as _PENDING_TOOL_CONFIRMS
from app.state import AUTH_USERS as AUTH_USERS

load_dotenv()

flask_app = Flask(__name__)
# Backwards-compatible public name used by tests and WSGI servers.
app = flask_app


def create_app(test_config=None):
    if test_config:
        flask_app.config.update(test_config)
    return flask_app


@flask_app.after_request
def add_cors_headers(response):
    origin = request.headers.get('Origin', '')
    raw = os.getenv('CORS_ALLOWED_ORIGINS', 'http://127.0.0.1:3000,http://localhost:3000')
    allowed_origins = {v.strip() for v in raw.split(',') if v.strip()}
    if origin and ('*' in allowed_origins):
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Vary'] = 'Origin'
    elif origin in allowed_origins:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Vary'] = 'Origin'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
    response.headers['Access-Control-Expose-Headers'] = 'Content-Type,Authorization'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
        "img-src 'self' data: https: http:; "
        "font-src 'self' data: https://cdnjs.cloudflare.com; "
        "connect-src 'self' http: https: ws: wss:; "
        "media-src 'self' data: blob:; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )
    return response


@flask_app.errorhandler(500)
def handle_500(e):
    logger.exception(f"500 Internal Server Error: {e}")
    return jsonify({"success": False, "error": "Interner Serverfehler – bitte Backend-Logs prüfen."}), 500


@flask_app.errorhandler(Exception)
def handle_unhandled(e):
    if isinstance(e, HTTPException):
        logger.error('HTTP error: %s', e)
        return jsonify({"success": False, "error": "Request failed"}), e.code
    logger.exception(f"Unbehandelte Exception: {e}")
    return jsonify({"success": False, "error": "Request failed"}), 500


@flask_app.before_request
def protect_api_by_default():
    if request.method == 'OPTIONS' or not request.path.startswith('/api/'):
        return None
    public = {
        '/api/health', '/api/capabilities', '/api/auth/login',
        '/api/auth/register', '/api/auth/me', '/api/setup/status',
    }
    if request.path in public or (request.path == '/api/auth/config' and request.method == 'GET'):
        return None
    if not SETUP_DONE_FILE.exists() and request.path in {
        '/api/setup/bootstrap', '/api/ollama/status',
        '/api/ollama/models', '/api/nextcloud/oauth/config',
    }:
        return None
    username = _authenticated_username()
    if not username:
        return jsonify({'authenticated': False, 'error': 'Unauthorized'}), 401
    request.current_user = username
    return None


# Import routes – triggers all @flask_app.route decorators
from app import routes as _routes  # noqa: F401, E402

# Importing a submodule can bind the package name in this module; restore the
# documented WSGI/test alias after route registration.
app = flask_app
