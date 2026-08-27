import io
import re

import app as app_module
from app import app


def _client(username, token):
    app.config['TESTING'] = True
    app_module.AUTH_USERS[username] = {'name': username, 'role': 'user', 'token': token}
    client = app.test_client()
    client.environ_base['HTTP_AUTHORIZATION'] = f'Bearer {token}'
    return client


def test_uploads_are_randomized_and_isolated(monkeypatch, tmp_path):
    monkeypatch.setattr('app.routes.UPLOAD_DIR', tmp_path)
    alice = _client('alice-upload-test', 'alice-upload-token')
    bob = _client('bob-upload-test', 'bob-upload-token')
    try:
        first = alice.post('/api/upload', data={'file': (io.BytesIO(b'alice'), 'report.txt')}, content_type='multipart/form-data')
        second = alice.post('/api/upload', data={'file': (io.BytesIO(b'alice-2'), 'report.txt')}, content_type='multipart/form-data')
        assert first.status_code == 200
        assert second.status_code == 200
        first_data = first.get_json()
        second_data = second.get_json()
        assert first_data['filename'] == 'report.txt'
        assert first_data['object_id'] != second_data['object_id']
        assert re.fullmatch(r'[0-9a-f]{32}_report\.txt', first_data['object_id'])
        assert alice.get(first_data['url']).data == b'alice'
        assert bob.get(first_data['url']).status_code == 404
        assert not (tmp_path / 'report.txt').exists()
    finally:
        app_module.AUTH_USERS.pop('alice-upload-test', None)
        app_module.AUTH_USERS.pop('bob-upload-test', None)


def test_upload_requires_authentication(monkeypatch, tmp_path):
    monkeypatch.setattr('app.routes.UPLOAD_DIR', tmp_path)
    with app.test_client() as client:
        response = client.post('/api/upload', data={'file': (io.BytesIO(b'x'), 'x.txt')}, content_type='multipart/form-data')
    assert response.status_code == 401
