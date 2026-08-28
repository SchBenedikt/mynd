import base64
import hashlib
import ipaddress
import json
import os
import re
import secrets
import shutil
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from flask import Response, jsonify, make_response, request, send_from_directory, stream_with_context
from werkzeug.security import generate_password_hash

import core.tools as _ct
import data.plugins.email as _email_module
import data.plugins.immich as _immich_module
import data.plugins.nextcloud as _nc_module
from app import flask_app as app
from app.agent_loop import (
    _get_tool_names_for_prompt,
    _get_vault_keys_for_prompt,
    _store_credentials_from_message,
    load_plugins,
    web_agent_loop,
    web_agent_loop_stream,
)
from app.auth import (
    _authenticated_username,
    _request_has_admin_token,
    _set_password,
    _verify_password,
    auth_rate_limited,
    clear_auth_failures,
    is_admin_username,
    record_auth_failure,
    require_admin,
    require_auth,
)
from app.config import (
    AUTH_CONFIG_FILE,
    BROWSER_DOWNLOADS_DIR,
    BROWSER_SCREENSHOTS_DIR,
    CHUNKS,
    DATA_DIR,
    EMBS,
    GENERATED_DIR,
    SETUP_DONE_FILE,
    UPLOAD_DIR,
    VAULT_FILE,
    _app_lock,
    logger,
)
from app.helpers import (
    _build_agent_system_prompt,
    _calendar_query_response,
    _calendar_range,
    _load_memory,
    _nextcloud_status,
    _reset_app_data,
    _save_memory,
    knowledge_base,
    load_security_mode,
    sanitize_response_text,
    save_security_mode,
)
from app.ollama_client import load_ai_config, ollama_client, save_ai_config
from app.scheduler import _init_automation_engine, automation_engine
from app.session_store import agent_sessions
from app.state import (
    AUTH_STATE_LOCK,
    INDEXING_CANCEL,
    INDEXING_STATUS,
    issue_auth_token,
    revoke_auth_token,
    save_auth_users,
    token_hash,
)
from core.llm import chat_with_tools
from core.model import check_tool_support
from core.plugin_base import (
    get_all_plugins,
    get_all_tools,
    get_registry,
    set_plugin_enabled,
    uninstall_plugin,
)
from core.scheduler import CRON_HELP, TRIGGER_EXAMPLES, TRIGGER_TYPES
from core.tools import CORE_TOOLS, PERMISSION_HELP, vault_delete, vault_set, web_search
from core.utils import call_with_timeout
from core.vault import load_vault
from core.vault import vault_get as _vg
from core.vault import vault_set as _vs

# ── Init ───────────────────────────────────────────────────
load_plugins()
_init_automation_engine()

# Patch prompt_user — agent_loop.py handles PERMISSION_MODE

_TOOL_SUPPORT_CACHE = {}
_TOOL_SUPPORT_TTL = 30 * 60  # seconds
_NO_TOOL_MODEL_KEYWORDS = tuple(
    k.strip().lower() for k in os.getenv('NO_TOOL_MODEL_KEYWORDS', 'phi,tinyllama').split(',') if k.strip()
)

_MODELS_CACHE = {}
_MODELS_TTL = 60  # seconds
_NEXTCLOUD_LOGIN_FLOWS = {}
_NEXTCLOUD_LOGIN_FLOWS_LOCK = threading.RLock()
_NEXTCLOUD_LOGIN_FLOW_TTL = 10 * 60


def _session_response(payload, token=None, status=200, clear=False):
    response = make_response(jsonify(payload), status)
    if clear:
        response.delete_cookie('mynd_session', path='/', samesite='Strict')
    elif token:
        response.set_cookie(
            'mynd_session',
            token,
            max_age=24 * 60 * 60,
            httponly=True,
            secure=request.is_secure,
            samesite='Strict',
            path='/',
        )
    return response


def _valid_password(password):
    return isinstance(password, str) and len(password) >= 12


def _atomic_json_write(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f'.{path.name}.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _valid_service_url(value, allow_local_http=False):
    parsed = urlparse(str(value or ''))
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
        return False
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return False
    if parsed.scheme == 'https':
        return True
    if not allow_local_http:
        return False
    try:
        return ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        return parsed.hostname.lower() == 'localhost'


def _available_models(base_url):
    """Short-cached set of models currently known to Ollama."""
    key = base_url
    now = time.time()
    cached = _MODELS_CACHE.get(key)
    if cached and now - cached[1] < _MODELS_TTL:
        return cached[0]
    normalized_base = str(base_url).rstrip('/')
    if normalized_base == str(ollama_client.base_url).rstrip('/'):
        models = set(ollama_client.list_models())
    else:
        response = requests.get(f'{normalized_base}/api/tags', timeout=8, allow_redirects=False)
        response.raise_for_status()
        models = {item.get('name') for item in response.json().get('models', []) if item.get('name')}
    _MODELS_CACHE[key] = (models, now)
    return models


def _conversation_messages(data, system_prompt, prompt):
    raw_history = data.get('history', [])
    history = []
    total_chars = 0
    if isinstance(raw_history, list):
        for item in raw_history[-12:]:
            if not isinstance(item, dict) or item.get('role') not in {'user', 'assistant'}:
                continue
            content = str(item.get('content') or '')[:8000]
            if not content:
                continue
            remaining = 40000 - total_chars
            if remaining <= 0:
                break
            content = content[:remaining]
            total_chars += len(content)
            history.append({'role': item['role'], 'content': content})
    return [{'role': 'system', 'content': system_prompt}, *history, {'role': 'user', 'content': prompt}]


def _resolve_active_model(requested, cfg):
    """Use the requested model if it is actually available, else fall back to
    the configured model. Prevents e.g. 410 Gone for retired/removed models.
    Only consults Ollama's model list for the ollama provider."""
    configured = str(cfg.get('model') or ollama_client.model)
    requested = str(requested) if requested else ''
    if not requested or requested == configured:
        return configured
    if cfg.get('provider') != 'ollama':
        return requested
    available = _available_models(str(cfg.get('base_url') or ollama_client.base_url))
    if available and requested in available:
        return requested
    logger.warning(
        'Requested model %r is not available – falling back to %r',
        requested,
        configured,
    )
    return configured


def _cached_tool_support(model, base_url):
    """Cached check_tool_support — avoids a live LLM round-trip on every request."""
    if any(k in str(model).lower() for k in _NO_TOOL_MODEL_KEYWORDS):
        return False
    key = f'{model}:{base_url}'
    now = time.time()
    cached = _TOOL_SUPPORT_CACHE.get(key)
    if cached and now - cached[1] < _TOOL_SUPPORT_TTL:
        return cached[0]
    try:
        result = check_tool_support(model, base_url)
    except Exception:
        logger.exception('check_tool_support failed')
        result = True
    _TOOL_SUPPORT_CACHE[key] = (result, now)
    return result


# ── /api/auth/* ────────────────────────────────────────────
@app.route('/api/auth/me', methods=['GET'])
def auth_me():
    username = _authenticated_username()
    if username:
        from app.state import AUTH_USERS

        with AUTH_STATE_LOCK:
            data = dict(AUTH_USERS.get(username, {}))
        if not data:
            return jsonify({'authenticated': False})
        return jsonify(
            {
                'authenticated': True,
                'user': {
                    'name': data.get('name', username),
                    'username': username,
                    'role': data.get('role', 'user'),
                },
            }
        )
    return jsonify({'authenticated': False})


@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    from app.state import AUTH_USERS

    data = request.json or {}
    username = data.get('username', '')
    password = data.get('password', '')
    if auth_rate_limited('login', username):
        return jsonify({'authenticated': False, 'error': 'Too many login attempts. Try again later.'}), 429
    with AUTH_STATE_LOCK:
        authenticated = username in AUTH_USERS and _verify_password(AUTH_USERS[username], password)
        if authenticated:
            token = issue_auth_token(AUTH_USERS[username])
            save_auth_users()
    if authenticated:
        clear_auth_failures('login', username)
        return _session_response(
            {
                'authenticated': True,
                'user': {
                    'name': AUTH_USERS[username].get('name', username),
                    'username': username,
                    'role': AUTH_USERS[username].get('role', 'user'),
                },
            },
            token=token,
        )
    record_auth_failure('login', username)
    return jsonify({'authenticated': False, 'error': 'Invalid credentials'}), 401


@app.route('/api/auth/refresh', methods=['POST'])
@require_auth
def auth_refresh():
    from app.state import AUTH_USERS

    username = request.current_user
    with AUTH_STATE_LOCK:
        token = issue_auth_token(AUTH_USERS[username])
        save_auth_users()
    return _session_response({'success': True}, token=token)


@app.route('/api/auth/register', methods=['POST'])
def auth_register():
    from app.state import AUTH_USERS

    data = request.json or {}
    username = data.get('username', '').strip()
    password = str(data.get('password') or '')
    name = data.get('name', '').strip() or username
    cfg = {'allowRegistration': False}
    if AUTH_CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(AUTH_CONFIG_FILE.read_text()))
        except Exception:
            pass
    if not cfg.get('allowRegistration'):
        return jsonify({'success': False, 'error': 'Registration is disabled'}), 403
    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password required'}), 400
    if len(username) < 2:
        return jsonify({'success': False, 'error': 'Username too short (min 2 characters)'}), 400
    if not _valid_password(password):
        return jsonify({'success': False, 'error': 'Password too short (minimum 12 characters)'}), 400
    if auth_rate_limited('register', username):
        return jsonify({'success': False, 'error': 'Too many registration attempts. Try again later.'}), 429
    with AUTH_STATE_LOCK:
        if username in AUTH_USERS:
            record_auth_failure('register', username)
            return jsonify({'success': False, 'error': 'User already exists'}), 409
        AUTH_USERS[username] = {
            'password_hash': generate_password_hash(password),
            'name': name,
            'role': 'user',
        }
        token = issue_auth_token(AUTH_USERS[username])
        save_auth_users()
    clear_auth_failures('register', username)
    return _session_response(
        {
            'success': True,
            'authenticated': True,
            'user': {'name': name, 'username': username, 'role': 'user'},
        },
        token=token,
    )


@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    from app.state import AUTH_USERS

    auth = request.headers.get('Authorization', '')
    token = auth[7:] if auth.startswith('Bearer ') else request.cookies.get('mynd_session', '')
    if token:
        with AUTH_STATE_LOCK:
            presented_hash = token_hash(token)
            for user in AUTH_USERS.values():
                if secrets.compare_digest(str(user.get('token_hash', '')), presented_hash):
                    revoke_auth_token(user)
                    save_auth_users()
                    break
    return _session_response({'success': True}, clear=True)


@app.route('/api/auth/factory-reset', methods=['POST'])
@require_admin
def auth_factory_reset():
    from app.state import AUTH_USERS

    data = request.json or {}
    password = data.get('password', '')
    with AUTH_STATE_LOCK:
        admin_user = dict(AUTH_USERS.get('admin', {}))
    if auth_rate_limited('factory-reset', 'admin'):
        return jsonify({'success': False, 'error': 'Too many attempts. Try again later.'}), 429
    if not _verify_password(admin_user, password):
        record_auth_failure('factory-reset', 'admin')
        return jsonify({'success': False, 'error': 'Invalid password'}), 401
    clear_auth_failures('factory-reset', 'admin')
    admin_name = admin_user.get('name', 'Admin')
    with AUTH_STATE_LOCK:
        AUTH_USERS.clear()
        AUTH_USERS['admin'] = {
            'password_hash': generate_password_hash(password),
            'name': admin_name,
            'role': 'admin',
        }
        save_auth_users()
    SETUP_DONE_FILE.unlink(missing_ok=True)
    return _session_response({'success': True}, clear=True)


@app.route('/api/auth/config', methods=['GET', 'POST'])
def auth_config():
    cfg = {'allowRegistration': False, 'requireLogin': True}
    if AUTH_CONFIG_FILE.exists():
        try:
            stored = json.loads(AUTH_CONFIG_FILE.read_text())
            cfg.update(stored)
        except Exception:
            pass
    if request.method == 'GET':
        return jsonify({'success': True, **cfg})
    if not _request_has_admin_token():
        return jsonify({'success': False, 'error': 'Forbidden'}), 403
    data = request.json or {}
    if 'allowRegistration' in data:
        cfg['allowRegistration'] = bool(data['allowRegistration'])
    if 'requireLogin' in data:
        cfg['requireLogin'] = bool(data['requireLogin'])
    try:
        _atomic_json_write(AUTH_CONFIG_FILE, cfg)
        return jsonify({'success': True, **cfg})
    except Exception:
        return jsonify({'success': False, 'error': 'Request failed'}), 500


@app.route('/api/auth/profile', methods=['GET', 'PUT'])
@require_auth
def auth_profile():
    from app.state import AUTH_USERS

    username = request.current_user
    if request.method == 'GET':
        with AUTH_STATE_LOCK:
            data = dict(AUTH_USERS.get(username, {}))
        return jsonify(
            {
                'success': True,
                'user': {
                    'username': username,
                    'name': data.get('name', username),
                    'role': data.get('role', 'user'),
                },
            }
        )
    data = request.json or {}
    name = data.get('name', '').strip()
    password = str(data.get('password') or '')
    current_password = str(data.get('current_password') or '')
    with AUTH_STATE_LOCK:
        if username in AUTH_USERS:
            if name:
                AUTH_USERS[username]['name'] = name
            if password:
                if not _valid_password(password):
                    return jsonify({'success': False, 'error': 'Password must contain at least 12 characters'}), 400
                if not _verify_password(AUTH_USERS[username], current_password):
                    return jsonify({'success': False, 'error': 'Current password is required'}), 403
                _set_password(AUTH_USERS[username], password)
                revoke_auth_token(AUTH_USERS[username])
            save_auth_users()
        current = dict(AUTH_USERS.get(username, {}))
    return _session_response(
        {
            'success': True,
            'reauthenticate': bool(password),
            'user': {
                'username': username,
                'name': name or current.get('name', username),
                'role': current.get('role', 'user'),
            },
        },
        clear=bool(password),
    )


@app.route('/api/admin/users', methods=['GET'])
@require_admin
def admin_users_list():
    from app.state import AUTH_USERS

    with AUTH_STATE_LOCK:
        users = [
            {'username': username, 'name': data.get('name', ''), 'role': data.get('role', 'user')}
            for username, data in AUTH_USERS.items()
        ]
    return jsonify({'success': True, 'users': users})


@app.route('/api/admin/users/create', methods=['POST'])
@require_admin
def admin_users_create():
    from app.state import AUTH_USERS

    data = request.json or {}
    username = data.get('username', '').strip()
    password = str(data.get('password') or '')
    name = data.get('name', '').strip()
    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password required'}), 400
    if not _valid_password(password):
        return jsonify({'success': False, 'error': 'Password must contain at least 12 characters'}), 400
    role = data.get('role', 'user')
    if role not in ('user', 'admin'):
        return jsonify({'success': False, 'error': 'Role must be user or admin'}), 400
    with AUTH_STATE_LOCK:
        if username in AUTH_USERS:
            return jsonify({'success': False, 'error': 'User already exists'}), 409
        AUTH_USERS[username] = {
            'password_hash': generate_password_hash(password),
            'name': name or username,
            'role': role,
        }
        save_auth_users()
    return jsonify({'success': True, 'user': {'username': username, 'name': name or username, 'role': role}})


@app.route('/api/admin/users/delete', methods=['POST'])
@require_admin
def admin_users_delete():
    from app.state import AUTH_USERS

    data = request.json or {}
    username = data.get('username', '').strip()
    if username == 'admin':
        return jsonify({'success': False, 'error': 'Cannot delete admin user'}), 400
    with AUTH_STATE_LOCK:
        if not username or username not in AUTH_USERS:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        del AUTH_USERS[username]
        save_auth_users()
    return jsonify({'success': True})


@app.route('/api/admin/users/reset', methods=['POST'])
@require_admin
def admin_users_reset():
    from app.state import AUTH_USERS

    data = request.json or {}
    username = data.get('username', '').strip()
    password = str(data.get('password') or '')
    if not password:
        return jsonify({'success': False, 'error': 'Password required'}), 400
    if not _valid_password(password):
        return jsonify({'success': False, 'error': 'Password must contain at least 12 characters'}), 400
    with AUTH_STATE_LOCK:
        if not username or username not in AUTH_USERS:
            return jsonify({'success': False, 'error': 'User not found'}), 404
        _set_password(AUTH_USERS[username], password)
        revoke_auth_token(AUTH_USERS[username])
        save_auth_users()
    return jsonify({'success': True})


@app.route('/api/admin/reset', methods=['POST'])
@require_admin
def admin_reset():
    temporary_password = _reset_app_data()
    return jsonify({'success': True, 'temporary_password': temporary_password})


# ── /api/capabilities ──────────────────────────────────────
def _get_capabilities():
    return {
        'chat': True,
        'agent': True,
        'streaming': True,
        'knowledge_graph': True,
        'knowledge_status': True,
        'knowledge_reload': True,
        'calendar': True,
        'calendar_mutating': True,
        'tasks': True,
        'tasks_mutating': True,
        'email': True,
        'email_indexing': False,
        'nextcloud': True,
        'nextcloud_login_flow': True,
        'location': True,
        'briefing': True,
        'automations': True,
        'plugins': True,
        'security': True,
        'memory': True,
        'vault': True,
        'tts_server_side': False,
        'training': False,
        'registry': False,
        'nina': False,
        'projects': True,
    }


@app.route('/api/capabilities', methods=['GET'])
def api_capabilities():
    return jsonify({'success': True, 'schema_version': 1, 'capabilities': _get_capabilities()})


# ── /api/health ────────────────────────────────────────────
@app.route('/api/health', methods=['GET'])
def api_health():
    cfg = load_ai_config()
    provider = cfg.get('provider', 'ollama')
    provider_configured = bool(cfg.get('base_url') and cfg.get('model'))
    if provider == 'openai':
        provider_configured = provider_configured and bool(cfg.get('api_key'))
    return jsonify(
        {
            'status': 'ok',
            'provider': {'name': provider, 'configured': provider_configured},
            'knowledge_base': {'loaded': knowledge_base is not None, 'chunks': len(knowledge_base.chunks)},
        }
    )


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def frontend_static(path):
    from app.config import STATIC_EXPORT_DIR

    if path == 'api' or path.startswith('api/'):
        return jsonify({'success': False, 'error': 'Not found'}), 404
    if not STATIC_EXPORT_DIR.is_dir():
        return jsonify({'error': 'not found'}), 404
    safe_path = os.path.normpath('/' + path).lstrip('/')
    file_path = os.path.realpath(os.path.join(STATIC_EXPORT_DIR, safe_path))
    if not file_path.startswith(os.path.realpath(STATIC_EXPORT_DIR)):
        return jsonify({'error': 'not found'}), 404
    if os.path.isfile(file_path):
        return send_from_directory(STATIC_EXPORT_DIR, safe_path)
    index = os.path.join(file_path, 'index.html')
    if os.path.isfile(index):
        return send_from_directory(file_path, 'index.html')
    return send_from_directory(STATIC_EXPORT_DIR, 'index.html')


# ── /api/setup/* ───────────────────────────────────────────
@app.route('/api/setup/status', methods=['GET'])
def setup_status():
    needs_setup = not SETUP_DONE_FILE.exists()
    oauth_configured = bool(_vg('nextcloud/url') and _vg('nextcloud/user') and _vg('nextcloud/password'))
    nc_url = _vg('nextcloud/url') or ''
    return jsonify(
        {'success': True, 'needs_setup': needs_setup, 'oauth_configured': oauth_configured, 'nextcloud_url': nc_url}
    )


@app.route('/api/setup/bootstrap', methods=['POST'])
def setup_bootstrap():
    from app.state import AUTH_USERS

    if SETUP_DONE_FILE.exists() and not _request_has_admin_token():
        return jsonify({'success': False, 'error': 'Forbidden'}), 403
    data = request.json or {}
    mode = data.get('mode', '')
    if mode == 'admin':
        name = data.get('admin_name', 'Admin').strip()
        pw = str(data.get('admin_password') or '')
        if not _valid_password(pw):
            return jsonify({'success': False, 'error': 'Password must contain at least 12 characters'}), 400
        with AUTH_STATE_LOCK:
            AUTH_USERS.clear()
            AUTH_USERS['admin'] = {
                'password_hash': generate_password_hash(pw),
                'name': name,
                'role': 'admin',
            }
            save_auth_users()
        return jsonify({'success': True, 'mode': 'admin'})
    elif mode == 'ai':
        provider = str(data.get('provider') or 'ollama').strip().lower()
        base_url = (
            str(
                data.get('base_url')
                or ('https://api.openai.com/v1' if provider == 'openai' else 'http://127.0.0.1:11434')
            )
            .strip()
            .rstrip('/')
        )
        model = str(data.get('model') or '').strip()
        api_key = str(data.get('api_key') or '').strip()
        if provider not in {'ollama', 'openai'} or not model:
            return jsonify({'success': False, 'error': 'A supported provider and model are required'}), 400
        if not _valid_service_url(base_url, allow_local_http=True):
            return jsonify({'success': False, 'error': 'Invalid AI provider URL'}), 400
        if provider == 'openai' and not api_key:
            return jsonify({'success': False, 'error': 'API key is required for OpenAI-compatible providers'}), 400
        save_ai_config(
            provider,
            base_url,
            model,
            api_key=api_key,
            embedding_model=data.get('embedding_model', ''),
        )
        return jsonify({'success': True, 'mode': 'ai'})
    elif mode == 'system':
        if data.get('enable_ollama'):
            save_ai_config(
                'ollama',
                data.get('base_url', 'http://127.0.0.1:11434'),
                data.get('model', ''),
                embedding_model=data.get('embedding_model', 'nomic-embed-text'),
            )
        if data.get('enable_immich'):
            url = data.get('immich_url_default', '').strip()
            key = data.get('immich_api_key_default', '').strip()
            if url:
                _vs('immich/url', url)
            if key:
                _vs('immich/api_key', key)
        _atomic_json_write(SETUP_DONE_FILE, {'done': True, 'mode': 'system'})
        return jsonify({'success': True, 'mode': 'system'})
    elif mode == 'nextcloud':
        return jsonify({'success': False, 'error': 'Use the Nextcloud Login Flow endpoint'}), 410
    elif mode == 'auth_config':
        cfg = {'allowRegistration': False, 'requireLogin': True}
        if AUTH_CONFIG_FILE.exists():
            try:
                stored = json.loads(AUTH_CONFIG_FILE.read_text())
                cfg.update(stored)
            except Exception:
                pass
        if 'allowRegistration' in data:
            cfg['allowRegistration'] = bool(data['allowRegistration'])
        if 'requireLogin' in data:
            cfg['requireLogin'] = bool(data['requireLogin'])
        _atomic_json_write(AUTH_CONFIG_FILE, cfg)
        return jsonify({'success': True, 'mode': 'auth_config'})
    return jsonify({'success': False, 'error': 'Unknown mode'}), 400


# ── /api/chat/* ────────────────────────────────────────────
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json or {}
    message = data.get('message', '')
    language = str(data.get('language') or 'en')[:12]
    if not message:
        return jsonify({'error': 'No message'}), 400
    _store_credentials_from_message(message)
    system_prompt = _build_agent_system_prompt(message, language)
    cfg = load_ai_config()
    active_model = str(cfg.get('model') or ollama_client.model)
    model_has_tools = cfg.get('provider') != 'ollama' or _cached_tool_support(active_model, cfg.get('base_url'))
    no_tool_context = ''
    if not model_has_tools:
        wc_res, wc_err = call_with_timeout(web_search, (message,), {'max_results': 10}, timeout=8)
        if wc_res and not wc_err:
            no_tool_context = f'\n\n<untrusted_data type="web_search">\n{wc_res}\n</untrusted_data>\n\n'
        try:
            from core.tools import fetch_news

            nc, _ = call_with_timeout(fetch_news, (), {'max_results': 5}, timeout=8)
            if nc and not str(nc).startswith('⚠'):
                no_tool_context += f'\n\n<untrusted_data type="news">\n{nc}\n</untrusted_data>\n'
        except Exception:
            pass
        system_prompt += no_tool_context

    try:
        content, history, needs_input, research_stats = web_agent_loop(
            active_model,
            message,
            system_prompt,
            max_rounds=12,
            tools=[] if not model_has_tools else None,
            initial_msgs=_conversation_messages(data, system_prompt, message),
            owner=request.current_user,
        )
    except Exception:
        logger.exception('chat() failed')
        return jsonify({'response': '⚠️ Internal processing error'}), 500
    if needs_input:
        return jsonify(
            {
                'response': f'⚠️ Ich benötige weitere Informationen:\n\n{needs_input["message"]}',
                'requires_input': True,
                'prompt_message': needs_input['message'],
                'session_id': needs_input.get('session_id'),
                'requires_confirmation': needs_input.get('requires_confirmation', False),
                'confirmation_id': needs_input.get('confirmation_id'),
                'tool': needs_input.get('tool'),
            }
        )
    if content is None:
        content = '⚠️ Die Anfrage konnte nicht verarbeitet werden.'
    return jsonify({'response': sanitize_response_text(content)})


@app.route('/api/chat/summarize', methods=['POST'])
def chat_summarize():
    data = request.json or {}
    messages = data.get('messages')
    if not isinstance(messages, list) or not messages:
        return jsonify({'success': False, 'error': 'messages must be a non-empty list'}), 400
    language = str(data.get('language') or 'en')[:12]
    transcript = '\n'.join(
        f'{str(item.get("role", "user")).upper()}: {str(item.get("content", ""))[:8000]}'
        for item in messages[-100:]
        if isinstance(item, dict) and item.get('content')
    )[:50000]
    prompt = (
        f'Summarize this conversation in {language}. Include the goal, key facts, decisions, '
        f'open questions, and next actions. Use concise Markdown.\n\n{transcript}'
    )
    cfg = load_ai_config()
    result = chat_with_tools(cfg.get('model') or ollama_client.model, [{'role': 'user', 'content': prompt}], [])
    if result.get('error'):
        return jsonify({'success': False, 'error': 'The model provider is unavailable'}), 502
    summary = str(result.get('message', {}).get('content', '')).strip()
    if not summary:
        return jsonify({'success': False, 'error': 'The model returned an empty summary'}), 502
    return jsonify({'success': True, 'summary': summary})


# ── /api/agent/* ───────────────────────────────────────────
@app.route('/api/agent/query/stream', methods=['POST'])
def agent_query_stream():
    data = request.json or {}
    prompt = data.get('prompt', '')
    preferred_source = data.get('preferred_source', 'auto')
    requested_model = data.get('model', '')
    language = str(data.get('language') or 'en')[:12]
    owner = request.current_user if hasattr(request, 'current_user') else 'unknown'
    if not prompt:
        return jsonify({'success': False, 'error': 'No prompt'}), 400
    _store_credentials_from_message(prompt)
    base_prompt = _build_agent_system_prompt(prompt, language)
    cfg = load_ai_config()
    active_model = _resolve_active_model(requested_model, cfg)

    def _get_web_context_safe(query, max_results):
        try:
            wc, err = call_with_timeout(web_search, (query,), {'max_results': max_results}, timeout=8)
            if err:
                return (
                    '⚠️ Web-Suche nicht verfügbar'
                    if isinstance(err, TimeoutError)
                    else '⚠️ Web search is currently unavailable.'
                )
            return wc or 'Keine Ergebnisse gefunden.'
        except Exception:
            return '⚠️ Web-Suche nicht verfügbar'

    def generate():
        yield f'data: {json.dumps({"type": "status", "message": "⏳ Starte..."})}\n\n'
        # Everything potentially blocking runs AFTER the first SSE byte so the
        # frontend sees an immediate connection.
        if preferred_source == 'web':
            web_context = _get_web_context_safe(prompt, 10)
            source_hint = f'\n\n⚠️ Internet-Suche aktiviert.\n<untrusted_data type="web_search">\n{web_context}\n</untrusted_data>\n\n'
        elif preferred_source == 'deep':
            web_context = _get_web_context_safe(prompt, 15)
            source_hint = f'\n\n⚠️ Deep Research Modus aktiviert.\n<untrusted_data type="deep_search">\n{web_context}\n</untrusted_data>\n\n'
        elif preferred_source == 'local':
            source_hint = '\n\n⚠️ Nur lokale Dokumente.\n'
        else:
            source_hint = ''

        system_prompt = base_prompt + source_hint

        model_has_tools = cfg.get('provider') != 'ollama' or _cached_tool_support(active_model, cfg.get('base_url'))
        if not model_has_tools and is_admin_username(owner):
            tool_list = _get_tool_names_for_prompt()
            vault_block = _get_vault_keys_for_prompt()
            system_prompt = (
                f'Heute ist {datetime.now().strftime("%A, %d. %B %Y, %H:%M")}.\n\n'
                'Du bist ein KI-Assistent. Du kannst Tools über das folgende XML-Format aufrufen:\n\n'
                '<tool_code><tool name="TOOL_NAME" arg1="wert1" arg2="wert2"/></tool_code>\n\n'
                f'Verfügbare Tools:\n{tool_list}\n\n'
                f'{vault_block}'
                f"- Answer in the user's selected language ({language}).\n"
            )

        agent_tools = [] if not model_has_tools else None
        initial_msgs = _conversation_messages(data, system_prompt, prompt)
        for event in web_agent_loop_stream(
            active_model,
            prompt,
            system_prompt,
            max_rounds=12,
            tools=agent_tools,
            owner=owner,
            initial_msgs=initial_msgs,
        ):
            yield f'data: {json.dumps(event)}\n\n'

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive'},
    )


@app.route('/api/agent/query', methods=['POST'])
def agent_query():
    data = request.json or {}
    prompt = data.get('prompt', '')
    preferred_source = data.get('preferred_source', 'auto')
    requested_model = data.get('model', '')
    language = str(data.get('language') or 'en')[:12]
    if not prompt:
        return jsonify({'success': False, 'error': 'No prompt'}), 400

    _store_credentials_from_message(prompt)
    base_prompt = _build_agent_system_prompt(prompt, language)
    source_hint = ''
    if preferred_source == 'web':
        web_context = _get_web_context_safe_v2(prompt, 10)
        source_hint = (
            f'\n\n⚠️ Internet-Suche aktiviert.\n<untrusted_data type="web_search">\n{web_context}\n</untrusted_data>\n\n'
        )
    elif preferred_source == 'deep':
        web_context = _get_web_context_safe_v2(prompt, 15)
        source_hint = f'\n\n⚠️ Deep Research Modus aktiviert.\n<untrusted_data type="deep_search">\n{web_context}\n</untrusted_data>\n\n'
    elif preferred_source == 'local':
        source_hint = '\n\n⚠️ Nur lokale Dokumente.\n'
    system_prompt = base_prompt + source_hint
    cfg = load_ai_config()
    active_model = _resolve_active_model(requested_model, cfg)
    try:
        content, history, needs_input, research_stats = web_agent_loop(
            active_model,
            prompt,
            system_prompt,
            max_rounds=12,
            initial_msgs=_conversation_messages(data, system_prompt, prompt),
            owner=request.current_user,
        )
    except Exception:
        logger.exception('agent_query() failed')
        return jsonify({'success': False, 'error': 'Internal processing error'}), 500
    if needs_input:
        return jsonify(
            {
                'success': True,
                'response': f'⚠️ Ich benötige weitere Informationen:\n\n{needs_input["message"]}',
                'requires_input': True,
                'prompt_message': needs_input['message'],
                'session_id': needs_input.get('session_id'),
                'requires_confirmation': needs_input.get('requires_confirmation', False),
                'confirmation_id': needs_input.get('confirmation_id'),
                'tool': needs_input.get('tool'),
            }
        )
    if content is None:
        content = '⚠️ Die Anfrage konnte nicht verarbeitet werden.'
    return jsonify({'success': True, 'response': sanitize_response_text(content)})


def _get_web_context_safe_v2(query, max_results):
    try:
        from core.tools import web_search

        result, error = call_with_timeout(web_search, (query,), {'max_results': max_results}, timeout=8)
        if error:
            return '⚠️ Web-Suche Fehler'
        return result or 'Keine Ergebnisse gefunden.'
    except Exception:
        return '⚠️ Web-Suche nicht verfügbar'


@app.route('/api/agent/input', methods=['POST'])
def agent_input():
    data = request.json or {}
    user_input = data.get('input', '').strip()
    session_id = str(data.get('session_id') or '').strip()
    if not user_input:
        return jsonify({'success': False, 'error': 'Keine Eingabe'}), 400
    if not session_id:
        return jsonify({'success': False, 'error': 'session_id is required'}), 400
    session, session_error = agent_sessions.consume(request.current_user, session_id)
    if session_error == 'forbidden':
        return jsonify({'success': False, 'error': 'Forbidden'}), 403
    if session_error:
        return jsonify({'success': False, 'error': 'Session not found or expired'}), 404
    msgs = session['msgs']
    model = session['model']
    tools = session['tools']
    max_rounds = min(int(session.get('max_rounds', 12)), 12)
    msgs.append({'role': 'user', 'content': f'👤 Der User antwortet: "{user_input}"\n\nVerarbeite diese Antwort nun.'})
    try:
        content, history, needs_input, research_stats = web_agent_loop(
            model, '', '', max_rounds=max_rounds, tools=tools, initial_msgs=msgs, owner=request.current_user
        )
    except Exception:
        logger.exception('agent_input() failed')
        return jsonify({'success': False, 'error': 'Internal processing error'}), 500
    if needs_input:
        return jsonify(
            {
                'success': True,
                'response': needs_input['message'],
                'requires_input': True,
                'prompt_message': needs_input['message'],
                'session_id': needs_input.get('session_id'),
                'requires_confirmation': needs_input.get('requires_confirmation', False),
                'confirmation_id': needs_input.get('confirmation_id'),
                'tool': needs_input.get('tool'),
            }
        )
    if content is None:
        content = '⚠️ Die Anfrage konnte nicht verarbeitet werden.'
    return jsonify({'success': True, 'response': sanitize_response_text(content)})


# ── /api/generated/* ───────────────────────────────────────
@app.route('/api/generated/<path:filename>')
@require_admin
def serve_generated(filename):
    return send_from_directory(GENERATED_DIR, filename)


@app.route('/data/browser_screenshots/<path:filename>')
@require_admin
def serve_browser_screenshot(filename):
    return send_from_directory(BROWSER_SCREENSHOTS_DIR, filename)


@app.route('/data/browser_downloads/<path:filename>')
@require_admin
def serve_browser_download(filename):
    return send_from_directory(BROWSER_DOWNLOADS_DIR, filename)


@app.route('/api/upload', methods=['POST'])
@require_auth
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400
    f = request.files['file']
    if f.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    _max_upload_size = 50 * 1024 * 1024
    if request.content_length and request.content_length > _max_upload_size:
        return jsonify({'success': False, 'error': 'File exceeds 50 MB limit'}), 400
    try:
        owner = re.sub(r'[^A-Za-z0-9_-]', '_', str(request.current_user))[:80] or 'user'
        owner_dir = Path(UPLOAD_DIR) / owner
        owner_dir.mkdir(parents=True, exist_ok=True)
        display_name = re.sub(r'[^\w\.\-]', '_', Path(f.filename).name)
        display_name = display_name[:180] or 'upload'
        object_name = f'{secrets.token_hex(16)}_{display_name}'
        dest = owner_dir / object_name
        data = f.read(_max_upload_size + 1)
        if len(data) > _max_upload_size:
            return jsonify({'success': False, 'error': 'File exceeds 50 MB limit'}), 400
        dest.write_bytes(data)
        size = dest.stat().st_size
        return jsonify(
            {
                'success': True,
                'filename': display_name,
                'object_id': object_name,
                'size': size,
                'url': f'/api/uploads/{object_name}',
            }
        )
    except Exception:
        return jsonify({'success': False, 'error': 'Upload failed'}), 500


@app.route('/api/uploads/<path:filename>')
@require_auth
def serve_upload(filename):
    owner = re.sub(r'[^A-Za-z0-9_-]', '_', str(request.current_user))[:80] or 'user'
    owner_dir = Path(UPLOAD_DIR) / owner
    safe_filename = Path(filename).name
    if safe_filename != filename or not re.fullmatch(r'[0-9a-f]{32}_[\w.\-]{1,180}', safe_filename):
        return jsonify({'success': False, 'error': 'Invalid upload id'}), 400
    return send_from_directory(owner_dir, safe_filename)


# ── /api/ollama/* / /api/ai/* ──────────────────────────────
@app.route('/api/ollama/status', methods=['GET'])
def ollama_status():
    return jsonify(
        {
            'connected': ollama_client.check_connection(),
            'base_url': ollama_client.base_url,
            'model': ollama_client.model,
        }
    )


@app.route('/api/ollama/models', methods=['GET'])
def ollama_models():
    cfg = load_ai_config()
    if cfg['provider'] == 'openai':
        try:
            base_url = cfg['base_url'].rstrip('/')
            api_key = cfg.get('api_key', '')
            models_url = base_url.removesuffix('/v1') + '/v1/models'
            headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}
            r = requests.get(models_url, headers=headers, timeout=10)
            r.raise_for_status()
            raw = r.json().get('data', [])
            models = sorted(set(m['id'] for m in raw if 'id' in m))
            current = cfg.get('model', '')
            if current and current not in models:
                models.insert(0, current)
            return jsonify({'connected': True, 'base_url': base_url, 'current_model': current, 'models': models})
        except Exception:
            logger.exception('Could not fetch OpenAI-compatible model list')
            current = cfg.get('model', '')
            return jsonify(
                {
                    'connected': False,
                    'base_url': cfg['base_url'],
                    'current_model': current,
                    'models': [current] if current else [],
                    'error': 'Could not fetch models from configured provider',
                }
            )
    try:
        models = ollama_client.list_models()
        if ollama_client.model and ollama_client.model not in models:
            models.insert(0, ollama_client.model)
        return jsonify(
            {
                'connected': True,
                'base_url': ollama_client.base_url,
                'current_model': ollama_client.model,
                'models': models,
            }
        )
    except Exception:
        return jsonify(
            {
                'connected': False,
                'base_url': ollama_client.base_url,
                'current_model': ollama_client.model,
                'models': [ollama_client.model] if ollama_client.model else [],
                'error': 'Ollama connection failed',
            }
        )


@app.route('/api/ai/config', methods=['GET', 'POST'])
def ai_config():
    if request.method == 'GET':
        cfg = load_ai_config()
        return jsonify(
            {
                'provider': cfg['provider'],
                'base_url': cfg['base_url'],
                'model': cfg['model'],
                'embedding_model': cfg.get('embedding_model', ''),
                'api_key_set': bool(cfg.get('api_key', '')),
                'connected': ollama_client.check_connection() if cfg['provider'] == 'ollama' else True,
            }
        )
    data = request.json or {}
    provider = str(data.get('provider', 'ollama')).strip()
    base_url = str(data.get('base_url', '')).strip().rstrip('/')
    model = str(data.get('model', '')).strip()
    embedding_model = str(data.get('embedding_model', '')).strip() or None
    api_key = str(data.get('api_key', '')).strip()
    if not model:
        return jsonify({'error': 'model is required'}), 400
    if provider == 'ollama':
        if not base_url:
            return jsonify({'error': 'base_url is required for Ollama'}), 400
        if not _valid_service_url(base_url, allow_local_http=True):
            return jsonify({'error': 'Use HTTPS or a loopback HTTP URL without credentials, query, or fragment'}), 400
        try:
            if model not in _available_models(base_url):
                return jsonify({'error': 'The selected Ollama model is not available'}), 400
        except requests.RequestException:
            return jsonify({'error': 'Ollama is not reachable at the configured URL'}), 502
    elif provider == 'openai':
        if not base_url:
            base_url = 'https://api.openai.com/v1'
        if not _valid_service_url(base_url, allow_local_http=True):
            return jsonify({'error': 'Use HTTPS or a loopback HTTP URL without credentials, query, or fragment'}), 400
        if not api_key:
            api_key = load_ai_config().get('api_key', '')
        if not api_key:
            return jsonify({'error': 'api_key is required for OpenAI-compatible providers'}), 400
    else:
        return jsonify({'error': 'Unknown provider'}), 400
    save_ai_config(provider, base_url, model, api_key, embedding_model)
    return jsonify(
        {
            'status': 'saved',
            'provider': provider,
            'base_url': base_url,
            'model': model,
            'embedding_model': embedding_model or os.getenv('EMBEDDING_MODEL', 'nomic-embed-text'),
            'api_key_set': bool(api_key),
            'connected': True,
        }
    )


@app.route('/api/ai/test', methods=['POST'])
def ai_test():
    data = request.json or {}
    prompt = data.get('prompt', 'Antworte nur mit: OK')
    start = time.time()
    from core.llm import chat_with_tools

    cfg = load_ai_config()
    resp = chat_with_tools(cfg['model'], [{'role': 'user', 'content': prompt}], [])
    dur = int((time.time() - start) * 1000)
    if 'error' in resp:
        return jsonify({'status': 'error', 'error': 'Model provider unavailable', 'duration_ms': dur}), 502
    content = resp.get('message', {}).get('content', '')
    return jsonify(
        {
            'status': 'ok',
            'connected': True,
            'base_url': cfg['base_url'],
            'model': cfg['model'],
            'duration_ms': dur,
            'response': content,
            'response_preview': content[:280],
        }
    )


@app.route('/api/permission/mode', methods=['GET', 'POST'])
def permission_mode():
    if request.method == 'GET':
        return jsonify({'success': True, 'mode': _ct.PERMISSION_MODE, 'help': PERMISSION_HELP})
    data = request.json or {}
    mode = data.get('mode', 'ask')
    if mode not in PERMISSION_HELP:
        return jsonify({'success': False, 'error': f'Invalid mode: {mode}'}), 400
    _ct.PERMISSION_MODE = mode
    return jsonify({'success': True, 'mode': mode})


@app.route('/api/ai/check-models', methods=['POST'])
def api_ai_check_models():
    data = request.json or {}
    base_url = str(data.get('base_url', ollama_client.base_url)).rstrip('/')
    if not (base_url.startswith('http://') or base_url.startswith('https://')):
        return jsonify({'error': 'Invalid base_url'}), 400
    parsed = urlparse(base_url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.hostname:
        return jsonify({'error': 'Invalid model provider URL'}), 400
    try:
        from core.tools import _validate_http_url

        _validate_http_url(base_url)
    except ValueError as exc:
        logger.warning('Blocked unsafe model check URL %r: %s', base_url, exc)
        return jsonify({'error': 'Model provider URL is not allowed'}), 400
    try:
        r = requests.get(f'{base_url}/api/tags', timeout=8, allow_redirects=False)
        r.raise_for_status()
        all_models = sorted(set(m['name'] for m in r.json().get('models', [])))
    except Exception:
        return jsonify({'error': 'Cannot fetch models from configured provider'}), 502
    results = []
    for model in all_models:
        supported = _cached_tool_support(model, base_url)
        results.append({'model': model, 'tool_support': supported})
    return jsonify({'base_url': base_url, 'results': results})


# ── /api/vault/* ───────────────────────────────────────────
@app.route('/api/vault/entries', methods=['GET'])
def api_vault_entries():
    try:
        vault_data = load_vault(VAULT_FILE) if VAULT_FILE.exists() else {}
        entries = [{'key': k, 'value': '__SET__'} for k in sorted(vault_data)]
        return jsonify({'entries': entries, 'count': len(entries)})
    except Exception:
        return jsonify({'error': 'Request failed', 'entries': [], 'count': 0})


@app.route('/api/vault/entries', methods=['POST'])
def api_vault_set():
    data = request.json or {}
    key = (data.get('key') or '').strip()
    value = (data.get('value') or '').strip()
    if not key or not value:
        return jsonify({'error': 'key and value required'}), 400
    vault_set(key, value)
    return jsonify({'status': 'saved', 'key': key})


@app.route('/api/vault/entries/<path:key>', methods=['DELETE'])
def api_vault_delete(key):
    vault_delete(key)
    return jsonify({'status': 'deleted', 'key': key})


# ── /api/knowledge/* ───────────────────────────────────────
@app.route('/api/knowledge/status', methods=['GET'])
def knowledge_status():
    return jsonify(
        {
            'chunks_loaded': len(knowledge_base.chunks),
            'documents_count': len(set(c.get('source', '') for c in knowledge_base.chunks)),
            'semantic_search_available': len(knowledge_base.chunks) > 0,
            'database_path': str(CHUNKS),
        }
    )


@app.route('/api/knowledge/sources', methods=['GET'])
def knowledge_sources():
    sources = list(set(c.get('source', 'Unknown') for c in knowledge_base.chunks))
    return jsonify({'sources': sources, 'total_chunks': len(knowledge_base.chunks)})


@app.route('/api/knowledge/graph-data', methods=['GET'])
def knowledge_graph_data():
    return jsonify({'chunks': knowledge_base.chunks, 'sources': []})


def _knowledge_graph():
    """Build a graph from indexed chunks + memory items."""
    by_source = {}
    for chunk in knowledge_base.chunks:
        source = str(chunk.get('source') or 'Unknown')
        entry = by_source.setdefault(source, {'chunks': 0, 'headings': set()})
        entry['chunks'] += 1
        for heading in chunk.get('headings') or []:
            if isinstance(heading, dict) and heading.get('text'):
                entry['headings'].add(str(heading['text']))

    nodes = []
    edges = []
    folder_ids = {}
    for source, metadata in sorted(by_source.items()):
        source_path = Path(source)
        parent = str(source_path.parent)
        document_id = 'document-' + hashlib.sha256(source.encode('utf-8')).hexdigest()[:16]
        nodes.append(
            {
                'id': document_id,
                'label': source_path.name or source,
                'type': 'document',
                'properties': {
                    'source': source,
                    'path': source,
                    'chunks': metadata['chunks'],
                    'headings': ', '.join(sorted(metadata['headings']))[:500],
                },
            }
        )
        if parent not in ('', '.'):
            folder_id = folder_ids.get(parent)
            if folder_id is None:
                folder_id = 'project-' + hashlib.sha256(parent.encode('utf-8')).hexdigest()[:16]
                folder_ids[parent] = folder_id
                nodes.append(
                    {
                        'id': folder_id,
                        'label': Path(parent).name or parent,
                        'type': 'project',
                        'properties': {'path': parent},
                    }
                )
            edges.append({'from': folder_id, 'to': document_id, 'type': 'contains'})

    memory_data = _load_memory()
    memory_nodes = {}
    for key, value in memory_data.items():
        mem_id = 'memory-' + hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]
        val_str = str(value)[:200]
        memory_nodes[key] = mem_id
        label = key.split('/')[-1].replace('_', ' ').title() if '/' in key else key.title()
        nodes.append(
            {
                'id': mem_id,
                'label': label[:40],
                'type': 'memory',
                'properties': {
                    'key': key,
                    'value': val_str,
                    'full_key': key,
                },
            }
        )

    memory_keys = list(memory_data.keys())
    for i, k1 in enumerate(memory_keys):
        for k2 in memory_keys[i + 1 :]:
            k1_parts = set(k1.lower().replace('/', ' ').split())
            k2_parts = set(k2.lower().replace('/', ' ').split())
            overlap = k1_parts & k2_parts
            if overlap:
                v1 = str(memory_data[k1]).lower()
                v2 = str(memory_data[k2]).lower()
                value_overlap = len(set(v1.split()) & set(v2.split())) > 1
                if value_overlap or (k1.split('/')[0] == k2.split('/')[0]):
                    edges.append(
                        {
                            'from': memory_nodes[k1],
                            'to': memory_nodes[k2],
                            'type': 'related',
                        }
                    )

    updated_at = datetime.fromtimestamp(CHUNKS.stat().st_mtime, UTC) if CHUNKS.exists() else datetime.now(UTC)
    return {
        'nodes': nodes,
        'edges': edges,
        'stats': {
            'node_count': len(nodes),
            'edge_count': len(edges),
            'last_update': updated_at.isoformat(),
        },
    }


@app.route('/api/knowledge/graph', methods=['GET'])
def knowledge_graph():
    if request.args.get('refresh', '').lower() in ('1', 'true', 'yes'):
        knowledge_base._load()
    return jsonify({'success': True, 'data': _knowledge_graph(), 'refreshing': False})


@app.route('/api/knowledge/graph/node/<node_id>', methods=['GET'])
def knowledge_graph_node(node_id):
    graph = _knowledge_graph()
    node_by_id = {node['id']: node for node in graph['nodes']}
    if node_id not in node_by_id:
        return jsonify({'success': False, 'error': 'Node not found'}), 404
    related_ids = set()
    related_edges = []
    for edge in graph['edges']:
        if edge['from'] == node_id:
            related_ids.add(edge['to'])
            related_edges.append(edge)
        elif edge['to'] == node_id:
            related_ids.add(edge['from'])
            related_edges.append(edge)
    return jsonify(
        {
            'success': True,
            'data': {
                'node': node_by_id[node_id],
                'nodes': {related_id: node_by_id[related_id] for related_id in sorted(related_ids)},
                'edges': related_edges,
            },
        }
    )


@app.route('/api/knowledge/reload', methods=['POST'])
def knowledge_reload():
    knowledge_base._load()
    return jsonify({'status': 'reloaded', 'chunks_loaded': len(knowledge_base.chunks)})


@app.route('/api/knowledge/update-embeddings', methods=['POST'])
def knowledge_update_embeddings():
    texts = [str(chunk.get('text') or '') for chunk in knowledge_base.chunks]
    if not texts:
        return jsonify({'status': 'success', 'message': 'No indexed chunks require embeddings', 'embeddings': 0})
    try:
        import numpy as np

        from core.embed import embed

        vectors = np.asarray(embed(texts))
        if vectors.ndim != 2 or vectors.shape[0] != len(texts):
            raise ValueError('Embedding provider returned an invalid result')
        fd, temporary_name = tempfile.mkstemp(prefix='.embeddings.', dir=EMBS.parent)
        try:
            with os.fdopen(fd, 'wb') as handle:
                np.save(handle, vectors)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, EMBS)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
        knowledge_base._load()
        return jsonify({'status': 'success', 'message': 'Embeddings updated', 'embeddings': len(texts)})
    except Exception:
        logger.exception('Embedding update failed')
        return jsonify({'status': 'error', 'error': 'Embedding update failed'}), 502


@app.route('/api/knowledge/txt-files', methods=['GET'])
def knowledge_txt_files():
    upload_dir = DATA_DIR / 'text_uploads'
    upload_dir.mkdir(parents=True, exist_ok=True)
    files = [
        {'id': path.name, 'name': path.name, 'size': path.stat().st_size} for path in sorted(upload_dir.glob('*.txt'))
    ]
    return jsonify({'files': files})


@app.route('/api/knowledge/upload-txt', methods=['POST'])
def knowledge_upload_txt():
    upload_dir = DATA_DIR / 'text_uploads'
    upload_dir.mkdir(parents=True, exist_ok=True)
    uploaded = []
    errors = []
    incoming = request.files.getlist('files') or request.files.getlist('file')
    for item in incoming:
        original_name = re.sub(r'[^A-Za-z0-9._-]+', '_', Path(item.filename or '').name)
        if not original_name.lower().endswith('.txt'):
            errors.append({'name': original_name or 'unnamed', 'error': 'Only .txt files are allowed'})
            continue
        raw = item.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            errors.append({'name': original_name, 'error': 'File exceeds the 2 MB limit'})
            continue
        document_id = f'{secrets.token_hex(16)}.txt'
        (upload_dir / document_id).write_text(raw.decode('utf-8', errors='replace'))
        uploaded.append({'id': document_id, 'name': original_name, 'size': len(raw)})
    status = 200 if uploaded else 400
    return jsonify({'uploaded': uploaded, 'total_chunks': 0, 'errors': errors}), status


@app.route('/api/knowledge/txt-files/<doc_id>', methods=['DELETE'])
def knowledge_txt_file_delete(doc_id):
    if not re.fullmatch(r'[0-9a-f]{32}\.txt', doc_id):
        return jsonify({'success': False, 'error': 'Invalid document id'}), 400
    upload_dir = DATA_DIR / 'text_uploads'
    known_files = {item.name: item for item in upload_dir.glob('*.txt') if item.is_file()}
    path = known_files.get(doc_id)
    if path is None:
        return jsonify({'success': False, 'error': 'Document not found'}), 404
    path.unlink()
    return jsonify({'success': True})


# ── /api/memory/* ──────────────────────────────────────────
@app.route('/api/memory', methods=['GET'])
def api_memory_list():
    m = _load_memory()
    items = [{'key': k, 'value': v} for k, v in sorted(m.items())]
    return jsonify({'items': items, 'count': len(items)})


@app.route('/api/memory/<path:key>', methods=['GET'])
def api_memory_get(key):
    m = _load_memory()
    if key in m:
        return jsonify({'key': key, 'value': m[key]})
    return jsonify({'error': 'not found'}), 404


@app.route('/api/memory', methods=['POST'])
def api_memory_set():
    data = request.get_json(silent=True) or {}
    key = data.get('key', '').strip()
    value = data.get('value', '').strip()
    if not key:
        return jsonify({'error': 'key required'}), 400
    with _ct._memory_lock:
        m = _load_memory()
        m[key] = value
        _save_memory(m)
    return jsonify({'status': 'saved', 'key': key})


@app.route('/api/memory/<path:key>', methods=['DELETE'])
def api_memory_delete(key):
    with _ct._memory_lock:
        m = _load_memory()
        if key in m:
            del m[key]
            _save_memory(m)
            return jsonify({'status': 'deleted', 'key': key})
    return jsonify({'error': 'not found'}), 404


# ── /api/indexing/* ────────────────────────────────────────
@app.route('/api/indexing/start', methods=['POST'])
def indexing_start():
    with _app_lock:
        if INDEXING_STATUS.get('status') in ('running', 'stopping'):
            return jsonify({'success': False, 'error': 'Indexing is already running'}), 409
        INDEXING_CANCEL.clear()
        run_id = secrets.token_hex(16)
        INDEXING_STATUS.clear()
        INDEXING_STATUS.update(
            {
                'status': 'running',
                'progress': 0,
                'current_file': '',
                'processed_files': 0,
                'total_files': 0,
                'errors': [],
                'elapsed_time': 0,
                'started_at': time.time(),
                'run_id': run_id,
            }
        )

    def run_index(active_run_id):
        try:
            from scripts.sync_nextcloud import main as sync_main

            logger.info('Starting Nextcloud sync...')
            with _app_lock:
                if INDEXING_STATUS.get('run_id') != active_run_id or INDEXING_CANCEL.is_set():
                    return
                INDEXING_STATUS['current_file'] = 'Syncing from Nextcloud...'
            sync_main(cancel_event=INDEXING_CANCEL)
            with _app_lock:
                if INDEXING_STATUS.get('run_id') != active_run_id:
                    return
                if INDEXING_CANCEL.is_set() or INDEXING_STATUS.get('status') == 'stopping':
                    INDEXING_STATUS['status'] = 'stopped'
                    INDEXING_STATUS['current_file'] = 'Indexing stopped'
                else:
                    INDEXING_STATUS['current_file'] = 'Indexing complete'
                    INDEXING_STATUS['status'] = 'completed'
                    INDEXING_STATUS['progress'] = 100
                INDEXING_STATUS['elapsed_time'] = time.time() - INDEXING_STATUS.get('started_at', time.time())
            if not INDEXING_CANCEL.is_set():
                knowledge_base._load()
        except Exception as e:
            with _app_lock:
                if INDEXING_STATUS.get('run_id') == active_run_id:
                    INDEXING_STATUS['status'] = 'stopped' if INDEXING_CANCEL.is_set() else 'error'
                    if not INDEXING_CANCEL.is_set():
                        INDEXING_STATUS['errors'].append('Indexing failed; check the backend log')
            logger.error(f'Indexing error: {e}')

    threading.Thread(target=run_index, args=(run_id,), daemon=True).start()
    return jsonify({'status': 'started', 'run_id': run_id, 'message': 'Indexing started'})


@app.route('/api/indexing/stop', methods=['POST'])
def indexing_stop():
    with _app_lock:
        if INDEXING_STATUS.get('status') not in ('running', 'stopping'):
            return jsonify({'status': INDEXING_STATUS.get('status', 'idle')})
        INDEXING_CANCEL.set()
        INDEXING_STATUS['status'] = 'stopping'
        INDEXING_STATUS['current_file'] = 'Stopping indexing...'
    return jsonify({'status': 'stopping'})


@app.route('/api/indexing/progress', methods=['GET'])
def indexing_progress():
    with _app_lock:
        return jsonify(
            {
                'status': INDEXING_STATUS['status'],
                'progress_percentage': INDEXING_STATUS['progress'],
                'current_file': INDEXING_STATUS.get('current_file', ''),
                'processed_files': INDEXING_STATUS.get('processed_files', 0),
                'total_files': INDEXING_STATUS.get('total_files', 0),
                'elapsed_time': INDEXING_STATUS.get('elapsed_time', 0),
                'errors': INDEXING_STATUS.get('errors', []),
            }
        )


@app.route('/api/indexing/config', methods=['GET', 'POST'])
def indexing_config():
    if request.method == 'GET':
        cfg_file = DATA_DIR / 'indexing_config.json'
        if cfg_file.exists():
            cfg = json.loads(cfg_file.read_text())
            return jsonify(
                {
                    'url': cfg.get('url', ''),
                    'username': cfg.get('username', ''),
                    'password': '***' if cfg.get('password') else '',
                }
            )
        return jsonify({'url': '', 'username': '', 'password': ''})
    data = request.json or {}
    pw = data.get('password', '')
    if pw:
        vault_set('indexing/password', pw)
    cfg = {'url': data.get('url', ''), 'username': data.get('username', ''), 'password': '***' if pw else ''}
    (DATA_DIR / 'indexing_config.json').write_text(json.dumps(cfg, indent=2))
    return jsonify({'status': 'saved'})


@app.route('/api/indexing/path', methods=['GET', 'POST'])
def indexing_path():
    config_file = DATA_DIR / 'indexing_path.json'
    if request.method == 'POST':
        path = str((request.json or {}).get('path', '')).strip()
        config_file.write_text(json.dumps({'path': path}, indent=2))
        return jsonify({'success': True, 'path': path})
    if config_file.exists():
        try:
            return jsonify(json.loads(config_file.read_text()))
        except Exception:
            pass
    return jsonify({'path': ''})


@app.route('/api/indexing/stats', methods=['GET'])
def indexing_stats():
    sources = {str(chunk.get('source') or 'Unknown') for chunk in knowledge_base.chunks}
    embeddings = 0
    embeddings_file = DATA_DIR / 'embeddings.npy'
    if embeddings_file.exists():
        try:
            import numpy as np

            embeddings = int(np.load(embeddings_file, mmap_mode='r').shape[0])
        except (OSError, ValueError, IndexError):
            embeddings = 0
    completed_at = CHUNKS.stat().st_mtime if CHUNKS.exists() else None
    runs = [{'ended_at': completed_at, 'status': 'completed'}] if completed_at else []
    return jsonify(
        {
            'success': True,
            'db_stats': {
                'documents': len(sources),
                'chunks': len(knowledge_base.chunks),
                'embeddings': embeddings,
            },
            'indexing_runs': runs,
        }
    )


@app.route('/api/indexing/status', methods=['GET'])
def indexing_status_v2():
    try:
        from data.plugins.email import _list_accounts

        stats = {'email_accounts': len(_list_accounts()), 'last_briefing': None}
        return jsonify({'success': True, 'stats': stats})
    except Exception:
        return jsonify({'success': False, 'error': 'Request failed'})


# ── /api/calendar/* ────────────────────────────────────────
@app.route('/api/calendar/status', methods=['GET'])
def calendar_status():
    ok, info = _nextcloud_status()
    return jsonify(
        {'enabled': ok, 'connected': ok, 'message': 'Nextcloud CalDAV verfügbar' if ok else 'Nextcloud nicht verbunden'}
    )


@app.route('/api/calendar/calendars', methods=['GET'])
def calendar_calendars():
    ok, info = _nextcloud_status()
    if not ok:
        return jsonify({'success': False, 'calendars': [], 'count': 0, 'error': info}), 503
    try:
        url, dav, user, pw = _nc_module._nc()
        auth = requests.auth.HTTPBasicAuth(user, pw)
        cals = _nc_module._caldav_discover(url, user, auth)
        calendars = [{'name': name, 'href': href} for name, href in cals]
        return jsonify({'success': True, 'calendars': calendars, 'count': len(calendars)})
    except Exception:
        return jsonify({'success': False, 'calendars': [], 'count': 0, 'error': 'Request failed'}), 502


@app.route('/api/calendar/create', methods=['POST'])
def calendar_create():
    data = request.json or {}
    result = _nc_module.nextcloud_caldav_create(
        data.get('summary') or data.get('title') or '',
        data.get('dtstart') or data.get('start') or '',
        data.get('dtend') or data.get('end') or '',
        data.get('description', ''),
        data.get('calendar_name') or data.get('calendarName') or 'Persönlich',
    )
    return jsonify({'success': not str(result).startswith('❌'), 'message': result, 'result': result})


@app.route('/api/calendar/create-with-details', methods=['POST'])
def calendar_create_with_details():
    return calendar_create()


@app.route('/api/calendar/update', methods=['POST'])
def calendar_update():
    data = request.get_json(silent=True) or {}
    uid = str(data.get('uid') or '').strip()
    if not uid:
        return jsonify({'success': False, 'error': 'uid is required'}), 400
    result = _nc_module.nextcloud_caldav_update(
        uid,
        summary=data.get('summary'),
        dtstart=data.get('dtstart') or data.get('start'),
        dtend=data.get('dtend') or data.get('end'),
        description=data.get('description'),
    )
    success = not str(result).startswith('❌')
    return jsonify({'success': success, 'message': result}), (200 if success else 502)


@app.route('/api/calendar/today', methods=['GET'])
def calendar_today():
    start, end = _calendar_range('today')
    payload, status = _calendar_query_response(start, end)
    payload.update(
        {
            'date': start.strftime('%d.%m.%Y'),
            'weekday': ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'][
                start.weekday()
            ],
        }
    )
    return jsonify(payload), status


@app.route('/api/calendar/tomorrow', methods=['GET'])
def calendar_tomorrow():
    start, end = _calendar_range('tomorrow')
    payload, status = _calendar_query_response(start, end)
    return jsonify(payload), status


@app.route('/api/calendar/week', methods=['GET'])
def calendar_week():
    start, end = _calendar_range('week')
    payload, status = _calendar_query_response(start, end)
    return jsonify(payload), status


@app.route('/api/calendar/next-week', methods=['GET'])
def calendar_next_week():
    start, end = _calendar_range('next-week')
    payload, status = _calendar_query_response(start, end)
    return jsonify(payload), status


@app.route('/api/calendar/day/<day_name>', methods=['GET'])
def calendar_day(day_name):
    start, end = _calendar_range('day', day_name)
    payload, status = _calendar_query_response(start, end)
    payload['day'] = day_name
    return jsonify(payload), status


@app.route('/api/calendar/config', methods=['GET', 'POST'])
def calendar_config():
    config_file = DATA_DIR / 'calendar_config.json'
    if request.method == 'POST':
        config = request.json or {}
        config_file.write_text(json.dumps(config, indent=2))
        return jsonify({'success': True, **config})
    config = {'default_calendar_name': ''}
    if config_file.exists():
        try:
            config.update(json.loads(config_file.read_text()))
        except Exception:
            pass
    return jsonify(config)


# ── /api/tasks/* ───────────────────────────────────────────
@app.route('/api/tasks/status', methods=['GET'])
def tasks_status():
    ok, info = _nextcloud_status()
    return jsonify(
        {'enabled': ok, 'connected': ok, 'message': 'Nextcloud Tasks verfügbar' if ok else 'Nextcloud nicht verbunden'}
    )


@app.route('/api/tasks/list', methods=['GET'])
def tasks_list():
    ok, info = _nextcloud_status()
    if not ok:
        return jsonify({'success': False, 'tasks': [], 'count': 0, 'enabled': False, 'error': info}), 503
    text = _nc_module.nextcloud_tasks_query()
    tasks = [{'text': line.strip()} for line in str(text).splitlines() if line.strip()]
    return jsonify(
        {'success': not str(text).startswith('❌'), 'tasks': tasks, 'count': len(tasks), 'enabled': True, 'raw': text}
    )


@app.route('/api/tasks/create', methods=['POST'])
def tasks_create():
    data = request.json or {}
    result = _nc_module.nextcloud_tasks_create(
        data.get('summary') or data.get('title') or '',
        data.get('due') or data.get('dueDate') or '',
        data.get('description', ''),
        data.get('calendar_name') or data.get('listName') or 'Aufgaben',
    )
    return jsonify({'success': not str(result).startswith('❌'), 'message': result, 'result': result})


@app.route('/api/tasks/create-with-details', methods=['POST'])
def tasks_create_with_details():
    return tasks_create()


@app.route('/api/tasks/update/<task_uid>', methods=['POST'])
def tasks_update(task_uid):
    data = request.get_json(silent=True) or {}
    result = _nc_module.nextcloud_tasks_update(
        task_uid,
        summary=data.get('summary') or data.get('title'),
        due=data.get('due'),
        description=data.get('description'),
        completed=data.get('completed'),
    )
    success = not str(result).startswith('❌')
    return jsonify({'success': success, 'message': result, 'uid': task_uid}), (200 if success else 502)


@app.route('/api/tasks/init', methods=['POST'])
def tasks_init():
    ok, info = _nextcloud_status()
    return jsonify(
        {'enabled': ok, 'success': ok, 'message': 'Nextcloud Tasks verfügbar' if ok else 'Nextcloud nicht verbunden'}
    )


@app.route('/api/tasks/complete/<task_uid>', methods=['POST'])
def tasks_complete(task_uid):
    result = _nc_module.nextcloud_tasks_update(task_uid, completed=True)
    success = not str(result).startswith('❌')
    return jsonify({'success': success, 'message': result, 'uid': task_uid}), (200 if success else 502)


@app.route('/api/tasks/sync', methods=['POST'])
def tasks_sync():
    text = _nc_module.nextcloud_tasks_query(include_completed=True)
    success = not str(text).startswith('❌')
    count = len([line for line in str(text).splitlines() if line.strip().startswith('📌')])
    return jsonify({'success': success, 'count': count, 'status': 'completed', 'message': text}), (
        200 if success else 502
    )


@app.route('/api/tasks/sync-status', methods=['GET'])
def tasks_sync_status():
    ok, info = _nextcloud_status()
    return jsonify(
        {
            'success': ok,
            'status': 'ready' if ok else 'unavailable',
            'message': info if not ok else 'Nextcloud Tasks ready',
        }
    )


@app.route('/api/tasks/db-stats', methods=['GET'])
def tasks_db_stats():
    text = _nc_module.nextcloud_tasks_query(include_completed=True)
    success = not str(text).startswith('❌')
    lines = [line for line in str(text).splitlines() if line.strip().startswith('📌')]
    completed = sum('Status: COMPLETED' in line for line in lines)
    return jsonify({'success': success, 'total': len(lines), 'completed': completed, 'open': len(lines) - completed}), (
        200 if success else 502
    )


# ── /api/security/* ────────────────────────────────────────
@app.route('/api/security/status', methods=['GET'])
def security_status():
    sm = load_security_mode()
    return jsonify(
        {
            'success': True,
            'headline': 'Sicherheitsstatus',
            'nina_warning_count': 0,
            'nina_warnings': [],
            'weather': None,
            'security_mode': sm['mode'],
        }
    )


@app.route('/api/security/mode', methods=['GET', 'POST'])
def security_mode():
    if request.method == 'POST':
        data = request.json or {}
        mode = data.get('mode', 'standard')
        if mode not in ('restricted', 'standard', 'admin'):
            return jsonify({'error': 'Invalid mode. Must be restricted, standard, or admin'}), 400
        save_security_mode(mode)
        return jsonify({'success': True, 'mode': mode})
    sm = load_security_mode()
    return jsonify({'success': True, 'mode': sm['mode']})


# ── /api/references ────────────────────────────────────────
@app.route('/api/references', methods=['GET', 'POST'])
def api_references():
    from app.config import API_REFS_PATH

    if request.method == 'POST':
        data = request.json or {}
        refs = data.get('refs')
        if refs is None:
            return jsonify({'error': 'Missing refs'}), 400
        with open(API_REFS_PATH, 'w') as f:
            json.dump(refs, f, indent=2, ensure_ascii=False)
        return jsonify({'success': True})
    with open(API_REFS_PATH) as f:
        refs = json.load(f)
    return jsonify({'success': True, 'refs': refs})


# ── Stubs (501) ────────────────────────────────────────────
_BRIEFING_CACHE = {}
_BRIEFING_TTL = 15 * 60  # seconds


def _gather_briefing_items():
    """Collect today's calendar, email, tasks and photos into dashboard items.

    Returns a banner-friendly overview item first, followed by detail items.
    Photo sections are reduced to a short text line (their markdown thumbnails
    render on the photos dashboard, not in the banner).
    """
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    sections = []
    photo_count = 0
    try:
        cal, _ = call_with_timeout(
            _nc_module.nextcloud_caldav_query, (today_str.replace('-', ''), today_str.replace('-', '')), timeout=10
        )
        if cal and '❌' not in cal:
            if 'keine' in cal.lower():
                sections.append({'key': 'calendar', 'title': '📅 Termine heute', 'content': 'Keine Termine.'})
            else:
                sections.append({'key': 'calendar', 'title': '📅 Termine heute', 'content': cal[:2000]})
    except Exception:
        pass
    try:
        accounts = _email_module._list_accounts()
        if accounts and '❌' not in str(accounts) and accounts != 'Keine E-Mail-Konten konfiguriert.':
            unread, _ = call_with_timeout(
                _email_module.email_search, (), {'query': 'UNSEEN', 'max_results': 10}, timeout=8
            )
            if unread and '❌' not in unread and '(keine)' not in unread:
                sections.append({'key': 'unread_emails', 'title': '📧 Ungelesene E-Mails', 'content': unread[:2000]})
            unanswered, _ = call_with_timeout(
                _email_module.email_search, (), {'query': 'UNANSWERED', 'max_results': 10}, timeout=8
            )
            if unanswered and '❌' not in unanswered and '(keine)' not in unanswered:
                sections.append(
                    {'key': 'unanswered_emails', 'title': '✉️ Unbeantwortete E-Mails', 'content': unanswered[:2000]}
                )
    except Exception:
        pass
    try:
        tasks, _ = call_with_timeout(_nc_module.nextcloud_tasks_query, timeout=10)
        if tasks and '❌' not in tasks and '(keine)' not in tasks:
            open_lines = [ln for ln in tasks.splitlines() if 'Status: COMPLETED' not in ln]
            if open_lines:
                sections.append(
                    {'key': 'tasks', 'title': '✅ Offene Aufgaben', 'content': '\n'.join(open_lines)[:2000]}
                )
    except Exception:
        pass
    try:
        photos, _ = call_with_timeout(
            _immich_module.immich_search_photos,
            (),
            {'date_from': today_str, 'date_to': today_str, 'size': 5},
            timeout=10,
        )
        if photos and '❌' not in photos and '(keine Ergebnisse)' not in photos:
            photo_count = photos.count('immich/thumbnail')
    except Exception:
        pass

    items = []
    if sections:
        summary_lines = [f'{s["title"]}: {s["content"].splitlines()[0][:80]}' for s in sections]
        if photo_count:
            summary_lines.append(f'📸 {photo_count} Fotos heute')
        items.append(
            {
                'key': 'overview',
                'title': '☀️ Dein Tagesüberblick',
                'content': '\n'.join(summary_lines),
            }
        )
    if photo_count:
        items.append(
            {
                'key': 'photos',
                'title': f'📸 {photo_count} Fotos heute',
                'content': f'{photo_count} Fotos heute aufgenommen.',
            }
        )
    items.extend(sections)
    return items


@app.route('/api/assistant/briefing/current', methods=['GET'])
def assistant_briefing():
    force = request.args.get('force') == 'true'
    now_ts = time.time()
    cached = _BRIEFING_CACHE.get('items')
    if not force and cached is not None and now_ts - _BRIEFING_CACHE.get('ts', 0) < _BRIEFING_TTL:
        return jsonify({'success': True, 'items': cached, 'generated_at': _BRIEFING_CACHE.get('generated_at')})
    items = _gather_briefing_items()
    _BRIEFING_CACHE['items'] = items
    _BRIEFING_CACHE['ts'] = now_ts
    _BRIEFING_CACHE['generated_at'] = datetime.now(UTC).isoformat()
    return jsonify({'success': True, 'items': items, 'generated_at': _BRIEFING_CACHE['generated_at']})


@app.route('/api/registry/email/config', methods=['GET'])
def registry_email_config():
    return jsonify(
        {
            'success': True,
            'configured': bool(_vg('email/imap_server') and _vg('email/imap_user')),
            'imap_server': _vg('email/imap_server') or '',
            'imap_user': _vg('email/imap_user') or '',
            'password_set': bool(_vg('email/imap_password')),
        }
    )


@app.route('/api/location/resolve', methods=['POST'])
def location_resolve():
    data = request.json or {}
    try:
        latitude = float(data['latitude'])
        longitude = float(data['longitude'])
    except (KeyError, TypeError, ValueError):
        return jsonify({'success': False, 'error': 'latitude and longitude are required'}), 400
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return jsonify({'success': False, 'error': 'Coordinates are out of range'}), 400
    return jsonify(
        {
            'success': True,
            'location': {'latitude': latitude, 'longitude': longitude},
            'display_name': f'{latitude:.4f}, {longitude:.4f}',
        }
    )


@app.route('/api/training/stats', methods=['GET'])
def training_stats():
    return jsonify({'success': False, 'error': 'Not implemented'}), 501


@app.route('/api/registry/apis', methods=['GET'])
def registry_apis():
    return jsonify({'success': False, 'error': 'Not implemented'}), 501


@app.route('/api/registry/health', methods=['GET'])
def registry_health():
    return jsonify({'success': False, 'error': 'Not implemented'}), 501


@app.route('/api/registry/<api_name>/config', methods=['GET', 'POST', 'DELETE'])
def registry_api_config(api_name):
    return jsonify({'success': False, 'error': 'Registry configuration is not implemented'}), 501


@app.route('/api/registry/<api_name>/test', methods=['POST'])
def registry_api_test(api_name):
    if api_name == 'nextcloud':
        ok, info = _nextcloud_status()
        return jsonify(
            {'success': ok, 'message': 'Nextcloud connection ready' if ok else '', 'error': '' if ok else info}
        ), (200 if ok else 502)
    if api_name == 'immich':
        url = str(_vg('immich/url') or '').rstrip('/')
        api_key = _vg('immich/api_key')
        if not url or not api_key:
            return jsonify({'success': False, 'error': 'Immich URL and API key are required'}), 400
        if not _valid_service_url(url, allow_local_http=True):
            return jsonify({'success': False, 'error': 'Invalid Immich URL'}), 400
        try:
            response = requests.get(
                f'{url}/api/server/ping', headers={'x-api-key': api_key}, timeout=10, allow_redirects=False
            )
            response.raise_for_status()
            return jsonify({'success': True, 'message': 'Immich connection successful'})
        except requests.RequestException:
            return jsonify({'success': False, 'error': 'Immich connection failed'}), 502
    if api_name == 'composio':
        try:
            from composio import Composio
        except ImportError:
            return jsonify({'success': False, 'error': 'composio ist nicht installiert. pip install composio'})
        api_key = _vg('composio/api_key')
        if not api_key:
            return jsonify({'success': False, 'error': 'API-Key fehlt. Trage ihn unter Integrationen > Composio ein.'})
        try:
            client = Composio(api_key=api_key)
            client.toolkits.list(limit=1)
            return jsonify({'success': True, 'message': 'Verbindung zu Composio erfolgreich!'})
        except Exception as e:
            msg = str(e)
            if '401' in msg or 'Invalid API key' in msg or 'ApiKeyError' in type(e).__name__:
                return jsonify(
                    {
                        'success': False,
                        'error': 'Composio API-Key ungültig. Bitte neuen API-Key von composio.dev holen.',
                    }
                )
            return jsonify({'success': False, 'error': f'Composio-Fehler: {msg[:200]}'})
    if api_name == 'affine':
        domain = _vg('affine/domain')
        email = _vg('affine/email')
        pw = _vg('affine/password')
        if not domain or not email or not pw:
            return jsonify({'success': False, 'error': 'Domain, E-Mail und Passwort eintragen.'})
        try:
            s = requests.Session()
            r = s.post(
                f'{domain.rstrip("/")}/api/auth/sign-in',
                json={
                    'email': email,
                    'password': pw,
                },
                headers={'Content-Type': 'application/json'},
                timeout=15,
            )
            if r.status_code == 200:
                return jsonify({'success': True, 'message': 'AFFiNE-Verbindung erfolgreich!'})
            return jsonify(
                {
                    'success': False,
                    'error': f'AFFiNE-Login fehlgeschlagen ({r.status_code}): {r.json().get("message", r.text[:200])}',
                }
            )
        except Exception as e:
            return jsonify({'success': False, 'error': f'AFFiNE nicht erreichbar: {e}'})
    return jsonify({'success': False, 'error': 'Not implemented'}), 501


@app.route('/api/email-indexing/start', methods=['POST'])
def email_indexing_start():
    return jsonify({'success': False, 'error': 'Email indexing jobs are not implemented'}), 501


@app.route('/api/email-indexing/stop', methods=['POST'])
def email_indexing_stop():
    return jsonify({'success': False, 'error': 'Email indexing jobs are not implemented'}), 501


@app.route('/api/email-indexing/progress', methods=['GET'])
def email_indexing_progress():
    return jsonify(
        {
            'status': 'idle',
            'progress_percentage': 0,
            'emails_processed': 0,
            'elapsed_time': 0,
            'current_folder': '',
            'status_message': '',
            'indexed_emails': 0,
            'skipped_emails': 0,
            'indexed_chunks': 0,
        }
    )


@app.route('/api/email-indexing/config', methods=['GET', 'POST'])
def email_indexing_config():
    config_file = DATA_DIR / 'email_indexing_config.json'
    if request.method == 'POST':
        config = request.json or {}
        config_file.write_text(json.dumps(config, indent=2))
        return jsonify({'success': True, **config})
    config = {'imap_host': '', 'imap_port': 993, 'username': '', 'folders': '', 'max_emails': 100, 'use_ssl': True}
    if config_file.exists():
        try:
            config.update(json.loads(config_file.read_text()))
        except Exception:
            pass
    return jsonify(config)


@app.route('/api/nina/regions', methods=['GET'])
def nina_regions():
    return jsonify({'success': False, 'error': 'Not implemented'}), 501


@app.route('/api/nina/dashboard', methods=['GET'])
def nina_dashboard():
    return jsonify({'success': False, 'error': 'Not implemented'}), 501


# ── /api/email/config ──────────────────────────────────────
@app.route('/api/email/config', methods=['GET', 'POST'])
def email_config():
    if request.method == 'POST':
        data = request.json or {}
        for key in (
            'imap_server',
            'imap_port',
            'imap_user',
            'imap_password',
            'smtp_server',
            'smtp_port',
            'smtp_user',
            'smtp_password',
        ):
            val = data.get(key)
            if val is not None:
                vault_set(f'email/{key}', str(val))
        return jsonify({'success': True})
    return jsonify(
        {
            'success': True,
            'config': {
                'imap_server': _vg('email/imap_server'),
                'imap_port': _vg('email/imap_port'),
                'imap_user': _vg('email/imap_user'),
                'imap_password': '••••' if _vg('email/imap_password') else '',
                'smtp_server': _vg('email/smtp_server'),
                'smtp_port': _vg('email/smtp_port'),
                'smtp_user': _vg('email/smtp_user'),
                'smtp_password': '••••' if _vg('email/smtp_password') else '',
            },
        }
    )


@app.route('/api/nextcloud/config', methods=['GET'])
def nextcloud_config():
    ok, info = _nextcloud_status()
    if not ok:
        return jsonify(
            {
                'configured': False,
                'display_name': '',
                'username': '',
                'nextcloud_url': '',
                'error': 'Nextcloud nicht verbunden',
            }
        )
    return jsonify(
        {
            'configured': True,
            'display_name': info.get('user', ''),
            'username': info.get('user', ''),
            'nextcloud_url': info.get('url', ''),
            'webdav_path': info.get('dav', ''),
        }
    )


@app.route('/api/nextcloud/oauth/config', methods=['GET'])
def nextcloud_oauth_config():
    return jsonify(
        {
            'configured': bool(_vg('nextcloud/url') and _vg('nextcloud/user') and _vg('nextcloud/password')),
            'nextcloud_url': _vg('nextcloud/url') or '',
            'login_flow': True,
        }
    )


@app.route('/api/nextcloud/login', methods=['POST'])
@require_admin
def nextcloud_login():
    data = request.get_json(silent=True) or {}
    url = (data.get('nextcloud_url') or '').strip().rstrip('/')
    username = (data.get('username') or '').strip()
    password = data.get('password', '')
    if not url or not username or not password:
        return jsonify({'success': False, 'error': 'url, username and password are required'}), 400
    if not _valid_service_url(url, allow_local_http=True):
        return jsonify({'success': False, 'error': 'Use HTTPS or a loopback HTTP Nextcloud URL'}), 400
    vault_set('nextcloud/url', url)
    vault_set('nextcloud/user', username)
    vault_set('nextcloud/password', password)
    return jsonify({'success': True, 'message': 'Nextcloud connected'})


@app.route('/api/nextcloud/loginflow/start', methods=['POST'])
def nextcloud_loginflow_start():
    data = request.get_json(silent=True) or {}
    server_url = str(data.get('nextcloud_url') or '').strip().rstrip('/')
    parsed = urlparse(server_url)
    try:
        host_ip = ipaddress.ip_address(parsed.hostname or '')
        is_loopback = host_ip.is_loopback
    except ValueError:
        is_loopback = (parsed.hostname or '').lower() in {'localhost'}
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
        return jsonify({'success': False, 'error': 'Invalid Nextcloud URL'}), 400
    if parsed.scheme != 'https' and not is_loopback:
        return jsonify({'success': False, 'error': 'Nextcloud must use HTTPS'}), 400
    try:
        response = requests.post(
            f'{server_url}/index.php/login/v2',
            timeout=15,
            allow_redirects=False,
            headers={'Accept': 'application/json'},
        )
        response.raise_for_status()
        payload = response.json()
        login_url = str(payload.get('login') or '')
        poll = payload.get('poll') if isinstance(payload.get('poll'), dict) else {}
        poll_endpoint = str(poll.get('endpoint') or '')
        poll_token = str(poll.get('token') or '')
        login_parsed = urlparse(login_url)
        poll_parsed = urlparse(poll_endpoint)
        expected_origin = (parsed.scheme, parsed.hostname, parsed.port)
        if not login_url or not poll_token or not poll_endpoint:
            raise ValueError('Incomplete login-flow response')
        if (login_parsed.scheme, login_parsed.hostname, login_parsed.port) != expected_origin:
            raise ValueError('Unexpected login URL')
        if (poll_parsed.scheme, poll_parsed.hostname, poll_parsed.port) != expected_origin:
            raise ValueError('Unexpected polling URL')
    except (requests.RequestException, ValueError, json.JSONDecodeError):
        logger.exception('Could not start Nextcloud Login Flow')
        return jsonify({'success': False, 'error': 'Nextcloud Login Flow could not be started'}), 502

    flow_id = secrets.token_urlsafe(32)
    now = time.time()
    with _NEXTCLOUD_LOGIN_FLOWS_LOCK:
        expired = [
            key
            for key, value in _NEXTCLOUD_LOGIN_FLOWS.items()
            if now - value['created_at'] > _NEXTCLOUD_LOGIN_FLOW_TTL
        ]
        for key in expired:
            _NEXTCLOUD_LOGIN_FLOWS.pop(key, None)
        _NEXTCLOUD_LOGIN_FLOWS[flow_id] = {
            'endpoint': poll_endpoint,
            'token': poll_token,
            'server_url': server_url,
            'created_at': now,
        }
    return jsonify({'success': True, 'flow_id': flow_id, 'login_url': login_url})


@app.route('/api/nextcloud/loginflow/poll', methods=['GET'])
def nextcloud_loginflow_poll():
    flow_id = str(request.args.get('flow_id') or '')
    with _NEXTCLOUD_LOGIN_FLOWS_LOCK:
        flow = dict(_NEXTCLOUD_LOGIN_FLOWS.get(flow_id) or {})
    if not flow:
        return jsonify({'success': False, 'status': 'expired', 'error': 'Unknown or expired login flow'}), 404
    if time.time() - flow['created_at'] > _NEXTCLOUD_LOGIN_FLOW_TTL:
        with _NEXTCLOUD_LOGIN_FLOWS_LOCK:
            _NEXTCLOUD_LOGIN_FLOWS.pop(flow_id, None)
        return jsonify({'success': False, 'status': 'expired', 'error': 'Login flow expired'}), 410
    try:
        response = requests.post(
            flow['endpoint'],
            data={'token': flow['token']},
            timeout=15,
            allow_redirects=False,
            headers={'Accept': 'application/json'},
        )
        if response.status_code in {404, 202}:
            return jsonify({'success': True, 'status': 'pending'}), 202
        response.raise_for_status()
        payload = response.json()
        server = str(payload.get('server') or '').rstrip('/')
        username = str(payload.get('loginName') or '')
        app_password = str(payload.get('appPassword') or '')
        expected = urlparse(flow['server_url'])
        actual = urlparse(server)
        if (actual.scheme, actual.hostname, actual.port) != (expected.scheme, expected.hostname, expected.port):
            raise ValueError('Unexpected Nextcloud server')
        if not username or not app_password:
            raise ValueError('Incomplete login response')
    except (requests.RequestException, ValueError, json.JSONDecodeError):
        logger.exception('Nextcloud Login Flow polling failed')
        return jsonify({'success': False, 'status': 'error', 'error': 'Nextcloud login could not be completed'}), 502
    vault_set('nextcloud/url', server)
    vault_set('nextcloud/user', username)
    vault_set('nextcloud/password', app_password)
    with _NEXTCLOUD_LOGIN_FLOWS_LOCK:
        _NEXTCLOUD_LOGIN_FLOWS.pop(flow_id, None)
    return jsonify({'success': True, 'status': 'connected', 'username': username, 'nextcloud_url': server})


@app.route('/api/nextcloud/disconnect', methods=['POST'])
def nextcloud_disconnect():
    for key in (
        'nextcloud/url',
        'nextcloud/client_id',
        'nextcloud/client_secret',
        'nextcloud/user',
        'nextcloud/password',
    ):
        vault_delete(key)
    (DATA_DIR / 'nextcloud_oauth.json').unlink(missing_ok=True)
    return jsonify({'success': True})


@app.route('/api/nextcloud/talk/webhook', methods=['POST'])
def nextcloud_talk_webhook():
    return jsonify({'success': False, 'error': 'Nextcloud Talk webhooks are not implemented'}), 501


# ── /api/email/test, /api/email/send, /api/email/folders ──
@app.route('/api/email/test', methods=['POST'])
def email_test():
    try:
        import imaplib
        import smtplib

        imap_ok = False
        smtp_ok = False
        errors = []
        imap_server = _vg('email/imap_server')
        imap_port = int(_vg('email/imap_port') or 993)
        imap_user = _vg('email/imap_user')
        imap_pass = _vg('email/imap_password')
        if imap_server and imap_user and imap_pass:
            try:
                c = imaplib.IMAP4_SSL(imap_server, imap_port, timeout=10)
                c.login(imap_user, imap_pass)
                c.logout()
                imap_ok = True
            except Exception:
                errors.append('IMAP connection failed')
        else:
            errors.append('IMAP unconfigured')
        smtp_server = _vg('email/smtp_server')
        smtp_port = int(_vg('email/smtp_port') or 587)
        smtp_user = _vg('email/smtp_user')
        smtp_pass = _vg('email/smtp_password')
        if smtp_server and smtp_user and smtp_pass:
            try:
                s = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
                s.starttls()
                s.login(smtp_user, smtp_pass)
                s.quit()
                smtp_ok = True
            except Exception:
                errors.append('SMTP connection failed')
        else:
            errors.append('SMTP unconfigured')
        return jsonify({'success': imap_ok or smtp_ok, 'imap': imap_ok, 'smtp': smtp_ok, 'errors': errors})
    except Exception:
        return jsonify({'success': False, 'error': 'Request failed'})


@app.route('/api/email/send', methods=['POST'])
def email_send_api():
    data = request.json or {}
    message = data.get('message') if isinstance(data.get('message'), dict) else data
    recipient = str(message.get('to') or '').strip()
    subject = str(message.get('subject') or '').strip()
    body = str(message.get('body') or '')
    if not recipient or not subject or not body:
        return jsonify({'success': False, 'error': 'to, subject, and body are required'}), 400
    result = _email_module.email_send(
        recipient,
        subject,
        body,
        str(message.get('cc') or ''),
        str(message.get('bcc') or ''),
        str(message.get('account') or 'default'),
    )
    success = not str(result).startswith('❌')
    if not success:
        return jsonify({'success': False, 'error': 'Email delivery failed'}), 502
    return jsonify({'success': True, 'message': result})


@app.route('/api/email/folders', methods=['POST'])
def email_folders():
    try:
        import imaplib

        imap_server = _vg('email/imap_server')
        imap_port = int(_vg('email/imap_port') or 993)
        imap_user = _vg('email/imap_user')
        imap_pass = _vg('email/imap_password')
        if not all([imap_server, imap_user, imap_pass]):
            return jsonify({'success': False, 'error': 'IMAP not configured'})
        c = imaplib.IMAP4_SSL(imap_server, imap_port, timeout=10)
        c.login(imap_user, imap_pass)
        _, folders = c.list()
        c.logout()
        names = []
        for f in folders:
            parts = f.decode().split(' "/" ')
            if len(parts) == 2:
                names.append(parts[1].strip())
        return jsonify({'success': True, 'folders': names or ['INBOX']})
    except Exception:
        return jsonify({'success': False, 'error': 'Request failed'})


# ── /api/email/accounts ──────────────────────────────────
@app.route('/api/email/accounts', methods=['GET', 'POST'])
def api_email_accounts():
    if request.method == 'GET':
        try:
            default = {
                'imap_server': _vg('email/imap_server') or '',
                'imap_user': _vg('email/imap_user') or '',
                'smtp_server': _vg('email/smtp_server') or '',
                'smtp_user': _vg('email/smtp_user') or '',
            }
            result = {'default': default} if default.get('imap_server') else {}
            v = load_vault(VAULT_FILE) if VAULT_FILE.exists() else {}
            for k in v:
                if k.startswith('email/accounts/') and k.endswith('/imap_server'):
                    name = k.split('/')[2]
                    if name not in result:
                        pref = f'email/accounts/{name}'
                        result[name] = {
                            'imap_server': v.get(f'{pref}/imap_server', ''),
                            'imap_port': v.get(f'{pref}/imap_port', '993'),
                            'imap_user': v.get(f'{pref}/imap_user', ''),
                            'smtp_server': v.get(f'{pref}/smtp_server', ''),
                            'smtp_port': v.get(f'{pref}/smtp_port', '587'),
                            'smtp_user': v.get(f'{pref}/smtp_user', ''),
                        }
            return jsonify({'success': True, 'accounts': result})
        except Exception:
            return jsonify({'success': False, 'error': 'Request failed'})
    data = request.json or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'error': 'Konto-Name erforderlich'}), 400
    for key in [
        'imap_server',
        'imap_port',
        'imap_user',
        'imap_password',
        'smtp_server',
        'smtp_port',
        'smtp_user',
        'smtp_password',
    ]:
        if key in data and data[key]:
            _vs(f'email/accounts/{name}/{key}', str(data[key]))
    return jsonify({'success': True, 'account': name})


@app.route('/api/email/accounts/<name>', methods=['DELETE'])
def api_email_account_delete(name):
    try:
        for key in [
            'imap_server',
            'imap_port',
            'imap_user',
            'imap_password',
            'smtp_server',
            'smtp_port',
            'smtp_user',
            'smtp_password',
        ]:
            vault_delete(f'email/accounts/{name}/{key}')
        return jsonify({'success': True})
    except Exception:
        return jsonify({'success': False, 'error': 'Request failed'})


@app.route('/api/email/index', methods=['POST'])
def email_index():
    data = request.json or {}
    account = data.get('account', 'default')
    max_emails = int(data.get('max_emails', 50))
    try:
        result = _email_module.email_search(query='ALL', max_results=max_emails, account=account)
        if result.startswith('❌'):
            return jsonify({'success': False, 'error': result})
        lines = result.split('\n')
        count = len([line for line in lines if line.startswith('ID:')])
        return jsonify({'success': True, 'indexed': count, 'account': account})
    except Exception:
        return jsonify({'success': False, 'error': 'Request failed'})


# ── /api/ui/system-config ─────────────────────────────────
@app.route('/api/ui/system-config', methods=['GET', 'POST'])
def ui_system_config():
    config_file = DATA_DIR / 'system_config.json'
    if request.method == 'POST':
        config = request.json or {}
        config_file.write_text(json.dumps(config, indent=2))
        return jsonify({'success': True, 'config': config})
    defaults = {
        'immich_url_default': '',
        'immich_api_key_default': '',
        'briefing_daily_enabled': True,
        'briefing_weekly_enabled': False,
        'briefing_morning_hour': 7,
        'briefing_send_daily': False,
        'briefing_send_weekly': False,
        'briefing_send_recipients': '',
        'briefing_send_account_id': '',
        'briefing_send_talk': False,
        'briefing_talk_room_id': '',
        'briefing_talk_webhook_secret_set': False,
    }
    if config_file.exists():
        try:
            defaults.update(json.loads(config_file.read_text()))
        except Exception:
            pass
    return jsonify({'success': True, 'config': defaults})


# ── /api/immich/* ──────────────────────────────────────────
@app.route('/api/immich/config', methods=['POST'])
def immich_config():
    data = request.json or {}
    url = (data.get('url') or '').strip()
    api_key = (data.get('api_key') or '').strip()
    if url and not _valid_service_url(url, allow_local_http=True):
        return jsonify({'success': False, 'error': 'Use HTTPS or a loopback HTTP Immich URL'}), 400
    if url:
        vault_set('immich/url', url)
    if api_key:
        vault_set('immich/api_key', api_key)
    return jsonify({'success': True, 'url_set': bool(url), 'key_set': bool(api_key)})


@app.route('/api/immich/thumbnail/<asset_id>')
def immich_thumbnail(asset_id):
    key = _vg('immich/api_key')
    url = _vg('immich/url')
    if not key or not url:
        return jsonify({'error': 'Immich not configured'}), 400
    try:
        h = {'x-api-key': key}
        base = url.rstrip('/')
        for ep in [f'{base}/api/assets/{asset_id}/thumbnail', f'{base}/api/assets/{asset_id}/original']:
            r = requests.get(ep, headers=h, timeout=10, stream=True)
            if r.ok:
                return Response(r.raw, content_type=r.headers.get('Content-Type', 'image/jpeg'), status=r.status_code)
            if r.status_code != 404:
                break
        return Response(
            b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b',
            content_type='image/gif',
        )
    except Exception:
        return jsonify({'error': 'Request failed'}), 500


@app.route('/api/immich/original/<asset_id>')
def immich_original(asset_id):
    key = _vg('immich/api_key')
    url = _vg('immich/url')
    if not key or not url:
        return jsonify({'error': 'Immich not configured'}), 400
    try:
        h = {'x-api-key': key}
        base = url.rstrip('/')
        ep = f'{base}/api/assets/{asset_id}/original'
        r = requests.get(ep, headers=h, timeout=30, stream=True)
        if r.ok:
            return Response(r.raw, content_type=r.headers.get('Content-Type', 'image/jpeg'), status=r.status_code)
        ep2 = f'{base}/api/assets/{asset_id}/download'
        r2 = requests.get(ep2, headers=h, timeout=30, stream=True)
        if r2.ok:
            return Response(r2.raw, content_type=r2.headers.get('Content-Type', 'image/jpeg'), status=r2.status_code)
        return jsonify({'error': f'Original nicht gefunden (Status {r.status_code})'}), 404
    except Exception:
        return jsonify({'error': 'Request failed'}), 500


@app.route('/api/immich/test', methods=['POST'])
def immich_test():
    url = _vg('immich/url')
    api_key = _vg('immich/api_key')
    if not url or not api_key:
        return jsonify({'success': False, 'error': 'Not configured. Store URL and API-Key first.'})
    try:
        resp = requests.post(
            url.rstrip('/') + '/api/search/metadata',
            json={'query': '', 'page': 1, 'size': 1},
            headers={'x-api-key': api_key, 'Content-Type': 'application/json'},
            timeout=10,
        )
        if resp.ok:
            data = resp.json()
            count = data.get('assets', {}).get('total', data.get('total', '?'))
            return jsonify({'success': True, 'status': 'connected', 'asset_count': count})
        return jsonify({'success': False, 'error': f'Immich responded with {resp.status_code}: {resp.text[:200]}'})
    except Exception:
        return jsonify({'success': False, 'error': 'Request failed'})


# ── /api/suggestions, /api/ai/greeting ────────────────────
@app.route('/api/suggestions/query', methods=['POST'])
def suggestions_query():
    data = request.json or {}
    lang = data.get('language', 'de')
    chat_history = data.get('chatHistory', [])
    now = datetime.now()
    hour = now.hour
    if hour < 5:
        tp = 'night'
    elif hour < 12:
        tp = 'morning'
    elif hour < 17:
        tp = 'afternoon'
    else:
        tp = 'evening'
    recent = []
    for m in (chat_history or [])[-4:]:
        c = m.get('content', '')
        if len(c) > 200:
            c = c[:200] + '…'
        recent.append(f'{m.get("role", "user")}: {c}')
    context = '\n'.join(recent)
    mem_info = ''
    mem_file = DATA_DIR / 'memory.json'
    if mem_file.exists():
        try:
            mem = json.loads(mem_file.read_text())
            if mem:
                mem_info = 'User-Memory: ' + '; '.join(f'{k}={v}' for k, v in list(mem.items())[:5])
        except Exception:
            pass
    prompt = (
        f'Generate 3 short, useful question suggestions (max 8 words each) for a personal AI assistant. '
        f'Time: {tp}. Language: {"German" if lang == "de" else "English"}. '
        f'{"Context: " + mem_info + ". " if mem_info else ""}'
        f'Recent chat:\n{context}\n\n'
        f'Return ONLY a JSON array of 3 strings, e.g. ["…", "…", "…"]. No markdown, no explanation.'
    )
    try:
        from core.llm import chat_with_tools

        cfg = load_ai_config()
        resp = chat_with_tools(cfg.get('model') or ollama_client.model, [{'role': 'user', 'content': prompt}], [])
        content = (resp.get('message') or resp).get('content', '').strip()
        if content.startswith('```'):
            content = content.split('\n', 1)[-1].rsplit('```', 1)[0]
        suggestions = json.loads(content)
        if not isinstance(suggestions, list) or len(suggestions) != 3:
            raise ValueError('unexpected format')
        return jsonify({'success': True, 'suggestions': suggestions, 'time_period': tp, 'personalized': True})
    except Exception:
        defaults_de = [
            'Was steht heute auf meinem Kalender?',
            'Zeige mir meine Aufgaben für heute',
            'Was ist neu in meinen Dateien?',
        ]
        defaults_en = ["What's on my calendar today?", 'Show me my tasks for today', "What's new in my files?"]
        return jsonify(
            {
                'success': True,
                'suggestions': defaults_de if lang == 'de' else defaults_en,
                'time_period': tp,
                'personalized': False,
            }
        )


_GREETING_CACHE = {}
_GREETING_CACHE_PERIODS = {'morning', 'afternoon', 'evening', 'night'}


@app.route('/api/ai/greeting', methods=['POST'])
def ai_greeting():
    data = request.json or {}
    lang = data.get('language', 'de')
    name = data.get('name', '')
    now = datetime.now()
    hour = now.hour
    if hour < 5:
        tp = 'night'
    elif hour < 12:
        tp = 'morning'
    elif hour < 17:
        tp = 'afternoon'
    else:
        tp = 'evening'
    cache_key = f'{tp}:{lang}:{name}'
    cached = _GREETING_CACHE.get(cache_key)
    if cached and cached[0] == now.strftime('%Y-%m-%d'):
        return jsonify({'success': True, 'greeting': cached[1]})
    weekdays_de = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']
    weekdays_en = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    wd = (weekdays_de if lang == 'de' else weekdays_en)[now.weekday()]
    name_suffix = f" The user's name is {name}." if name else ''
    prompt = f'Generate a short, warm greeting for {tp} on {wd} in {"German" if lang == "de" else "English"}. Include 1-2 fitting emojis. Max 10 words. Return ONLY the greeting text.{name_suffix}'
    try:
        from core.llm import chat_with_tools

        cfg = load_ai_config()
        resp = chat_with_tools(cfg.get('model') or ollama_client.model, [{'role': 'user', 'content': prompt}], [])
        content = (resp.get('message') or resp).get('content', '').strip()
        if not content:
            raise ValueError('empty')
    except Exception:
        greetings = {
            'morning': 'Guten Morgen' if lang == 'de' else 'Good morning',
            'afternoon': 'Guten Tag' if lang == 'de' else 'Good afternoon',
            'evening': 'Guten Abend' if lang == 'de' else 'Good evening',
            'night': 'Hallo' if lang == 'de' else 'Hello',
        }
        base = greetings.get(tp, 'Hallo' if lang == 'de' else 'Hello')
        content = f'{base}, {name}' if name else base
    _GREETING_CACHE[cache_key] = (now.strftime('%Y-%m-%d'), content)
    return jsonify({'success': True, 'greeting': content})


# ── /api/backup/* ──────────────────────────────────────────
_BACKUP_ALLOWED_FILES = frozenset(
    {
        'api_refs.json',
        'automations.json',
        'automations_history.json',
        'indexing_config.json',
        'indexing_path.json',
        'memory.json',
        'notifications.json',
        'security_mode.json',
        'timers.json',
    }
)
_BACKUP_MAX_BYTES = 50 * 1024 * 1024


@app.route('/api/backup/export', methods=['GET'])
@require_admin
def backup_export():
    files = {}
    for fname in sorted(_BACKUP_ALLOWED_FILES):
        fpath = DATA_DIR / fname
        if not fpath.is_file():
            continue
        try:
            raw = fpath.read_bytes()
            files[fname] = {'content': raw.decode('utf-8'), 'encoding': 'utf-8'}
        except (OSError, UnicodeDecodeError):
            return jsonify({'success': False, 'error': f'Could not export {fname}'}), 500
    return jsonify({'success': True, 'files': files, 'exported_at': datetime.now(UTC).isoformat()})


@app.route('/api/backup/import', methods=['POST'])
@require_admin
def backup_import():
    data = request.json or {}
    files = data.get('files', {})
    if not isinstance(files, dict):
        return jsonify({'success': False, 'error': 'files must be an object'}), 400
    errors = []
    decoded = {}
    total_bytes = 0
    for fname, meta in files.items():
        if fname not in _BACKUP_ALLOWED_FILES:
            errors.append(f'Restoring {fname} is not allowed')
            continue
        if (
            not isinstance(fname, str)
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', fname)
            or '/' in fname
            or '\\' in fname
        ):
            errors.append(f'Rejected unsafe filename: {fname}')
            continue
        if not isinstance(meta, dict):
            errors.append(f'{fname}: metadata must be an object')
            continue
        if meta.get('error'):
            errors.append(f'Skipped {fname}: source error')
            continue
        try:
            content = meta.get('content', '')
            encoding = meta.get('encoding', 'utf-8')
            if encoding == 'base64':
                raw = base64.b64decode(content, validate=True)
            elif encoding == 'utf-8':
                raw = str(content).encode('utf-8')
            else:
                errors.append(f'{fname}: unsupported encoding')
                continue
            if fname.endswith('.json'):
                parsed = json.loads(raw.decode('utf-8'))
                if not isinstance(parsed, (dict, list)):
                    raise ValueError('JSON root must be an object or array')
            total_bytes += len(raw)
            if total_bytes > _BACKUP_MAX_BYTES:
                errors.append('Backup exceeds the 50 MB limit')
                break
            decoded[fname] = raw
        except (TypeError, ValueError, UnicodeDecodeError):
            errors.append(f'{fname}: invalid backup content')
    if errors:
        return jsonify({'success': False, 'restored': 0, 'errors': errors}), 400

    stage_dir = Path(tempfile.mkdtemp(prefix='.backup-import-', dir=str(DATA_DIR)))
    originals = {}
    replaced = []
    try:
        for fname, raw in decoded.items():
            staged = stage_dir / fname
            staged.write_bytes(raw)
            target = DATA_DIR / fname
            originals[fname] = target.read_bytes() if target.exists() else None
        for fname in decoded:
            os.replace(stage_dir / fname, DATA_DIR / fname)
            replaced.append(fname)
        automation_engine.reload_all()
    except Exception:
        for fname in reversed(replaced):
            target = DATA_DIR / fname
            previous = originals.get(fname)
            if previous is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(previous)
        logger.exception('Backup import failed and was rolled back')
        return jsonify(
            {'success': False, 'restored': 0, 'error': 'Backup import failed; changes were rolled back'}
        ), 500
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)
    return jsonify({'success': True, 'restored': len(decoded), 'errors': []})


# ── /api/tool/run removed (tool confirmation dialog removed) ──


# ── /api/automations/* ─────────────────────────────────────
@app.route('/api/automations', methods=['GET'])
def list_automations():
    return jsonify({'success': True, 'automations': automation_engine.load_automations()})


@app.route('/api/automations', methods=['POST'])
def create_automation():
    data = request.json or {}
    steps = data.get('steps', [])
    trigger = data.get('trigger', {'type': 'cron', 'hour': '6', 'minute': '0'})
    if not isinstance(steps, list) or not 1 <= len(steps) <= 20:
        return jsonify({'success': False, 'error': 'Automation requires between 1 and 20 steps'}), 400
    if not isinstance(trigger, dict) or trigger.get('type') not in TRIGGER_TYPES:
        return jsonify({'success': False, 'error': 'Invalid trigger type'}), 400
    if len(json.dumps(data)) > 100_000:
        return jsonify({'success': False, 'error': 'Automation payload is too large'}), 413
    known_tools = {tool.get('function', {}).get('name') for tool in CORE_TOOLS + get_all_tools()[0]}
    known_tools.update({'notify', 'ai_task'})
    if any(not isinstance(step, dict) or step.get('tool') not in known_tools for step in steps):
        return jsonify({'success': False, 'error': 'Automation contains an unknown tool'}), 400
    auto = {
        'id': secrets.token_hex(16),
        'name': str(data.get('name', 'Neue Automation'))[:200],
        'description': str(data.get('description', ''))[:2000],
        'enabled': bool(data.get('enabled', True)),
        'trigger': trigger,
        'steps': steps,
    }
    try:
        automation_engine.add_automation(auto)
    except (TypeError, ValueError) as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
    return jsonify({'success': True, 'automation': auto})


@app.route('/api/automations/<aid>', methods=['PUT'])
def update_automation(aid):
    data = request.json or {}
    ok = automation_engine.update_automation(aid, data)
    if not ok:
        return jsonify({'success': False, 'error': 'Nicht gefunden'}), 404
    return jsonify({'success': True, 'automation': automation_engine.get_automation(aid)})


@app.route('/api/automations/<aid>', methods=['DELETE'])
def delete_automation(aid):
    try:
        automation_engine.delete_automation(aid)
        return jsonify({'success': True})
    except Exception:
        logger.exception(f'delete_automation({aid}) failed')
        return jsonify({'success': False, 'error': 'Delete failed'}), 500


@app.route('/api/automations/<aid>/test', methods=['POST'])
def test_automation(aid):
    try:
        result = automation_engine.run_automation(aid)
        if result.get('error'):
            return jsonify({'success': False, 'error': result['error']})
        return jsonify({'success': True, 'results': result.get('results', []), 'log': result.get('log', {})})
    except Exception:
        return jsonify({'success': False, 'error': 'Automation execution failed'}), 500


@app.route('/api/automations/history', methods=['GET'])
def list_automation_history():
    limit = request.args.get('limit', 50, type=int)
    history = automation_engine.load_history()
    history.sort(key=lambda h: h.get('timestamp', ''), reverse=True)
    return jsonify({'success': True, 'history': history[:limit]})


_SAFE_WEBHOOK_ERRORS = frozenset(
    {
        'Automation nicht gefunden',
        'Automation hat keinen Webhook-Trigger',
        'Ungültiges Webhook-Token',
        'Automation ist deaktiviert',
    }
)


@app.route('/api/automations/webhook/<aid>/<token>', methods=['POST'])
def automation_webhook(aid, token):
    try:
        result = automation_engine.trigger_by_token(aid, token)
        if result.get('error'):
            if result['error'] in _SAFE_WEBHOOK_ERRORS:
                return jsonify({'success': False, 'error': result['error']}), 403
            logger.warning('Webhook automation %s failed', aid)
            return jsonify({'success': False, 'error': 'Automation execution failed'}), 500
        return jsonify({'success': True, 'results': result.get('results', []), 'log': result.get('log', {})})
    except Exception:
        logger.warning('Webhook automation %s raised an exception', aid)
        return jsonify({'success': False, 'error': 'Webhook execution failed'}), 500


@app.route('/api/notifications/latest', methods=['GET'])
def list_notifications():
    try:
        limit = request.args.get('limit', 20, type=int)
        notifications = automation_engine.load_notifications()
        notifications.sort(key=lambda n: n.get('created_at', ''), reverse=True)
        return jsonify({'success': True, 'notifications': notifications[:limit]})
    except Exception:
        logger.warning('Failed to load notifications')
        return jsonify({'success': True, 'notifications': []})


@app.route('/api/notifications/read', methods=['POST'])
def read_notifications():
    data = request.json or {}
    ids = data.get('ids', [])
    if not isinstance(ids, list):
        return jsonify({'success': False, 'error': 'ids must be an array'}), 400
    notifications = automation_engine.load_notifications()
    id_set = set(str(i) for i in ids)
    for n in notifications:
        if str(n.get('id')) in id_set:
            n['read'] = True
    automation_engine.save_notifications(notifications)
    return jsonify({'success': True})


@app.route('/api/notifications/clear', methods=['POST'])
def clear_notifications():
    automation_engine.save_notifications([])
    return jsonify({'success': True})


@app.route('/api/automations/schema', methods=['GET'])
def automation_schema():
    plugin_tools, _ = get_all_tools()
    all_tools = CORE_TOOLS + plugin_tools
    plugins_info = []
    tool_groups = {}
    for t in CORE_TOOLS:
        tool_groups[t['function']['name']] = 'Core'
    for name, p in get_registry().items():
        if p is None:
            plugins_info.append({'name': name, 'description': '', 'version': '', 'tools': [], 'tool_count': 0})
            continue
        pname = p.name or name
        plugins_info.append(
            {
                'name': pname,
                'description': getattr(p, 'description', ''),
                'version': getattr(p, 'version', ''),
                'tools': [t.get('function', {}).get('name', '') for t in getattr(p, 'tools', [])],
                'tool_count': len(getattr(p, 'tools', [])),
            }
        )
        for t in getattr(p, 'tools', []):
            tname = t.get('function', {}).get('name', '')
            if tname:
                tool_groups[tname] = pname
    return jsonify(
        {
            'success': True,
            'tools': all_tools,
            'tool_groups': tool_groups,
            'plugins': plugins_info,
            'cron_help': CRON_HELP,
            'trigger_examples': TRIGGER_EXAMPLES,
            'trigger_types': sorted(TRIGGER_TYPES),
        }
    )


# ── /api/plugins/* ─────────────────────────────────────────
@app.route('/api/plugins', methods=['GET'])
def list_plugins():
    return jsonify({'success': True, 'plugins': get_all_plugins()})


@app.route('/api/plugins/install', methods=['POST'])
@require_admin
def install_plugin():
    return jsonify(
        {
            'success': False,
            'error': 'Remote plugin installation is disabled; install reviewed plugins through the repository.',
        }
    ), 410


@app.route('/api/plugins/<name>/toggle', methods=['POST'])
@require_admin
def toggle_plugin(name):
    data = request.get_json(silent=True) or {}
    enabled = data.get('enabled', True)
    if not isinstance(enabled, bool):
        return jsonify({'success': False, 'error': 'enabled must be a boolean'}), 400
    try:
        set_plugin_enabled(name, enabled)
        from app.agent_loop import refresh_tools

        refresh_tools()
        return jsonify({'success': True, 'enabled': enabled})
    except Exception:
        return jsonify({'success': False, 'error': 'Request failed'}), 400


@app.route('/api/plugins/<name>', methods=['DELETE'])
@require_admin
def delete_plugin(name):
    try:
        uninstall_plugin(name)
        from app.agent_loop import refresh_tools

        refresh_tools()
        return jsonify({'success': True})
    except Exception:
        return jsonify({'success': False, 'error': 'Request failed'}), 400


# ── /api/tts/* ─────────────────────────────────────────────
@app.route('/api/tts/synthesize', methods=['POST'])
@app.route('/api/tts/live', methods=['POST'])
def tts_unavailable():
    return jsonify(
        {'success': False, 'error': 'Server-side TTS is not configured; use browser speech synthesis instead'}
    ), 501


# ── Agent Briefing ─────────────────────────────────────────
@app.route('/api/agent/briefing', methods=['GET'])
def agent_briefing():
    try:
        now = datetime.now()
        items = _gather_briefing_items()
        _BRIEFING_CACHE['items'] = items
        _BRIEFING_CACHE['ts'] = time.time()
        _BRIEFING_CACHE['generated_at'] = now.isoformat()
        briefing = {
            'date': now.strftime('%A, %d. %B %Y'),
            'time': now.strftime('%H:%M'),
            'sections': [{'title': i['title'], 'content': i['content']} for i in items],
        }
        return jsonify({'success': True, 'briefing': briefing})
    except Exception:
        return jsonify({'success': False, 'error': 'Request failed'})
