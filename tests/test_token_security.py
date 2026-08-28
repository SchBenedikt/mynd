import time
from http.cookies import SimpleCookie

import app.auth as auth
import app.routes as routes
import app.state as state
from app import app


def test_login_persists_only_token_hash(monkeypatch):
    user = {'password_hash': auth.generate_password_hash('secret'), 'role': 'user'}
    monkeypatch.setitem(state.AUTH_USERS, 'token-test', user)
    monkeypatch.setattr(routes, 'save_auth_users', lambda: None)

    with app.test_client() as client:
        response = client.post('/api/auth/login', json={'username': 'token-test', 'password': 'secret'})

    assert response.status_code == 200
    cookie = SimpleCookie(response.headers['Set-Cookie'])
    token = cookie['mynd_session'].value
    assert 'token' not in response.get_json()
    assert user.get('token') is None
    assert user['token_hash'] == state.token_hash(token)
    assert user['token_expires_at'] > time.time()
    state.AUTH_USERS.pop('token-test', None)


def test_expired_token_is_rejected_and_removed(monkeypatch):
    user = {'role': 'user', 'token_hash': state.token_hash('expired'), 'token_expires_at': time.time() - 1}
    monkeypatch.setitem(state.AUTH_USERS, 'expired-test', user)
    monkeypatch.setattr(auth, 'save_auth_users', lambda: None)

    with app.test_request_context(headers={'Authorization': 'Bearer expired'}):
        assert auth._authenticated_username() is None
    assert 'token_hash' not in user
    state.AUTH_USERS.pop('expired-test', None)


def test_refresh_rotates_hashed_token(monkeypatch):
    user = {'role': 'user', 'token_hash': state.token_hash('old'), 'token_expires_at': time.time() + 1000}
    monkeypatch.setitem(state.AUTH_USERS, 'rotate-test', user)
    monkeypatch.setattr(routes, 'save_auth_users', lambda: None)

    with app.test_client() as client:
        response = client.post('/api/auth/refresh', headers={'Authorization': 'Bearer old'})

    assert response.status_code == 200
    cookie = SimpleCookie(response.headers['Set-Cookie'])
    new_token = cookie['mynd_session'].value
    assert 'token' not in response.get_json()
    assert new_token != 'old'
    assert user['token_hash'] == state.token_hash(new_token)
    state.AUTH_USERS.pop('rotate-test', None)
