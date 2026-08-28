from unittest.mock import Mock
import time

import pytest

import app.routes as routes
from app import app


@pytest.fixture(autouse=True)
def add_authenticated_user():
    import app.state as state
    state.AUTH_USERS["security-test"] = {"role": "admin", "token_hash": state.token_hash("security-test-token"), "token_expires_at": time.time() + 3600}
    yield
    state.AUTH_USERS.pop("security-test", None)


def test_check_models_rejects_private_url_without_request(monkeypatch):
    monkeypatch.setattr(routes, "_authenticated_username", lambda: "security-test")
    requested = Mock(side_effect=AssertionError("unsafe URL was requested"))
    monkeypatch.setattr(routes.requests, "get", requested)
    monkeypatch.setattr(routes, "_request_has_admin_token", lambda: True)

    with app.test_client() as client:
        response = client.post("/api/ai/check-models", json={"base_url": "http://127.0.0.1:11434"}, headers={"Authorization": "Bearer security-test-token"})

    assert response.status_code == 400
    assert response.get_json()["error"] == "Model provider URL is not allowed"
    requested.assert_not_called()


def test_check_models_rejects_credentials_and_redirects(monkeypatch):
    monkeypatch.setattr(routes, "_authenticated_username", lambda: "security-test")
    monkeypatch.setattr(routes, "_request_has_admin_token", lambda: True)

    with app.test_client() as client:
        credentials = client.post("/api/ai/check-models", json={"base_url": "https://user:pass@example.com"}, headers={"Authorization": "Bearer security-test-token"})
        assert credentials.status_code == 400

        response = client.post("/api/ai/check-models", json={"base_url": "https://example.com"}, headers={"Authorization": "Bearer security-test-token"})

    assert response.status_code in (502, 400)
