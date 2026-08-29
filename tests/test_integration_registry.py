import time
from unittest.mock import Mock

import pytest

import app as app_module
import app.routes as routes
import app.state as app_state
from app import app


@pytest.fixture
def client():
    app.config['TESTING'] = True
    app_module.AUTH_USERS['registry-test'] = {
        'name': 'Registry Test',
        'role': 'admin',
        'token_hash': app_state.token_hash('registry-test-token'),
        'token_expires_at': time.time() + 3600,
    }
    with app.test_client() as test_client:
        test_client.environ_base['HTTP_AUTHORIZATION'] = 'Bearer registry-test-token'
        yield test_client
    app_module.AUTH_USERS.pop('registry-test', None)


def _vault_store(monkeypatch, initial=None):
    store = dict(initial or {})
    monkeypatch.setattr(routes, '_vg', lambda key: store.get(key, ''))
    monkeypatch.setattr(routes, 'vault_set', lambda key, value: store.__setitem__(key, value))
    monkeypatch.setattr(routes, 'vault_delete', lambda key: store.pop(key, None))
    return store


def test_registry_lists_configuration_without_secrets(client, monkeypatch):
    _vault_store(
        monkeypatch,
        {
            'immich/url': 'https://photos.example',
            'immich/api_key': 'secret-key',
        },
    )

    listing = client.get('/api/registry/apis').get_json()
    config = client.get('/api/registry/immich/config').get_json()

    immich = next(item for item in listing['integrations'] if item['id'] == 'immich')
    assert listing['success'] is True
    assert immich['configured'] is True
    assert config['configured'] is True
    assert config['values'] == {'url': 'https://photos.example', 'api_key': '***'}
    assert 'secret-key' not in str(listing)


def test_registry_config_validates_and_persists_known_fields(client, monkeypatch):
    store = _vault_store(monkeypatch)

    invalid = client.post('/api/registry/immich/config', json={'values': {'unknown': 'value'}})
    saved = client.post(
        '/api/registry/immich/config',
        json={'values': {'url': 'https://photos.example', 'api_key': 'secret-key'}},
    )

    assert invalid.status_code == 400
    assert saved.status_code == 200
    assert saved.get_json()['configured'] is True
    assert store == {'immich/url': 'https://photos.example', 'immich/api_key': 'secret-key'}


def test_registry_rejects_invalid_payload_before_writing(client, monkeypatch):
    store = _vault_store(monkeypatch)

    list_payload = client.post('/api/registry/immich/config', json=['not', 'an', 'object'])
    invalid_url = client.post(
        '/api/registry/immich/config',
        json={'values': {'api_key': 'would-be-partial', 'url': 'ftp://photos.example'}},
    )

    assert list_payload.status_code == 400
    assert invalid_url.status_code == 400
    assert store == {}


def test_registry_homeassistant_connection_test(client, monkeypatch):
    _vault_store(
        monkeypatch,
        {
            'homeassistant/url': 'https://ha.example',
            'homeassistant/token': 'token',
        },
    )
    response = Mock()
    response.raise_for_status.return_value = None
    get = Mock(return_value=response)
    monkeypatch.setattr(routes.requests, 'get', get)

    result = client.post('/api/registry/homeassistant/test')

    assert result.status_code == 200
    assert result.get_json()['success'] is True
    get.assert_called_once_with(
        'https://ha.example/api/config',
        headers={'Authorization': 'Bearer token'},
        timeout=10,
        allow_redirects=False,
    )


def test_registry_unknown_integration_returns_404(client):
    assert client.get('/api/registry/unknown/config').status_code == 404
    assert client.post('/api/registry/unknown/test').status_code == 404


def test_email_account_rejects_unsafe_names_and_ports(client, monkeypatch):
    store = _vault_store(monkeypatch)

    unsafe_name = client.post('/api/email/accounts', json={'name': '../nextcloud', 'imap_server': 'mail.test'})
    invalid_port = client.post('/api/email/accounts', json={'name': 'work', 'imap_port': '70000'})

    assert unsafe_name.status_code == 400
    assert invalid_port.status_code == 400
    assert store == {}


def test_default_email_account_uses_primary_keys_and_preserves_blank_secrets(client, monkeypatch):
    store = _vault_store(monkeypatch, {'email/imap_password': 'existing-secret'})

    saved = client.post(
        '/api/email/accounts',
        json={
            'name': 'default',
            'imap_server': 'imap.example.com',
            'imap_port': '993',
            'imap_user': 'person@example.com',
            'imap_password': '',
        },
    )

    assert saved.status_code == 200
    assert store['email/imap_server'] == 'imap.example.com'
    assert store['email/imap_port'] == '993'
    assert store['email/imap_password'] == 'existing-secret'
    assert not any(key.startswith('email/accounts/default/') for key in store)

    deleted = client.delete('/api/email/accounts/default')
    assert deleted.status_code == 200
    assert not any(key.startswith('email/') for key in store)


def test_truenas_plugin_supports_flat_settings_keys(monkeypatch):
    from data.plugins import truenas

    monkeypatch.setattr(
        truenas,
        'load_vault',
        lambda _path: {'truenas/ip': '192.168.1.10', 'truenas/user': 'admin', 'truenas/password': 'secret'},
    )

    assert truenas._find_ip() == ('192.168.1.10', 'admin', 'secret')
