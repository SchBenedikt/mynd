#!/usr/bin/env python3
"""MYND Flask application package."""
import json
import os
import secrets
import threading
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from app.config import DATA_DIR, SETUP_DONE_FILE, _app_lock, logger
from app.state import AUTH_USERS as _AUTH_USERS
from app.auth import _authenticated_username

load_dotenv()

flask_app = Flask(__name__)


@flask_app.after_request
def add_cors_headers(response):
    origin = request.headers.get('Origin', '')
    allowed_origins = {
        value.strip()
        for value in os.getenv(
            'CORS_ALLOWED_ORIGINS',
            'http://127.0.0.1:3000,http://localhost:3000',
        ).split(',')
        if value.strip()
    }
    if origin in allowed_origins:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Vary'] = 'Origin'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; img-src 'self' data: https:; media-src 'self' data: blob:; "
        "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
        "font-src 'self' data: https://cdnjs.cloudflare.com; connect-src 'self' http: https: ws: wss:; "
        "script-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
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
        '/api/health', '/api/auth/login', '/api/auth/register',
        '/api/auth/me', '/api/setup/status',
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
import app.routes  # noqa: F401, E402
