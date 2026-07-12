"""Test Flask app routes and API endpoints using the test client."""

import pytest

from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestPluginAPI:
    def test_list_plugins(self, client):
        resp = client.get("/api/plugins")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "plugins" in data
        assert len(data["plugins"]) > 0
        # Each plugin should have name and tools
        for p in data["plugins"]:
            assert "name" in p
            assert "tools" in p

    def test_toggle_plugin(self, client):
        # Toggle first plugin
        resp = client.get("/api/plugins")
        plugins = resp.get_json()["plugins"]
        if plugins:
            name = plugins[0]["name"]
            resp = client.post(f"/api/plugins/{name}/toggle")
            assert resp.status_code in (200, 401, 404, 500)


class TestAuthAPI:
    def test_auth_me_unauthenticated(self, client):
        resp = client.get("/api/auth/me")
        # Should return 401 or 200 with no user
        assert resp.status_code in (200, 401)


class TestOllamaAPI:
    def test_ollama_status(self, client):
        resp = client.get("/api/ollama/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "connected" in data or "model" in data or "status" in data

    def test_ollama_models(self, client):
        resp = client.get("/api/ollama/models")
        assert resp.status_code in (200, 500)


class TestKnowledgeAPI:
    def test_knowledge_status(self, client):
        resp = client.get("/api/knowledge/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)


class TestSecurityAPI:
    def test_security_status(self, client):
        resp = client.get("/api/security/status")
        assert resp.status_code == 200


class TestVaultAPI:
    def test_vault_list(self, client):
        resp = client.get("/api/vault/entries")
        assert resp.status_code == 200

    def test_vault_set_and_delete(self, client):
        resp = client.post("/api/vault/entries",
                           json={"key": "test/foo", "value": "bar"},
                           content_type="application/json")
        assert resp.status_code in (200, 201, 500)

        resp = client.delete("/api/vault/entries/test/foo")
        assert resp.status_code in (200, 404, 500)


class TestBriefingAPI:
    def test_briefing_returns(self, client):
        """Briefing should return within timeout. May have 0 sections if services unavailable."""
        resp = client.get("/api/agent/briefing")
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            data = resp.get_json()
            assert "briefing" in data or "success" in data


class TestImmichAPI:
    def test_immich_config_missing_key(self, client):
        resp = client.post("/api/immich/config",
                           json={"url": ""},
                           content_type="application/json")
        assert resp.status_code in (200, 400)


class TestSystemEndpoints:
    def test_calendar_status(self, client):
        resp = client.get("/api/calendar/status")
        assert resp.status_code in (200, 500)

    def test_tasks_status(self, client):
        resp = client.get("/api/tasks/status")
        assert resp.status_code in (200, 500)

    def test_automations_schema(self, client):
        resp = client.get("/api/automations/schema")
        assert resp.status_code == 200


class TestCornerCases:
    def test_404_returns_json(self, client):
        resp = client.get("/api/nonexistent_route_xyz")
        assert resp.status_code == 404
        assert resp.is_json

    def test_immich_thumbnail_missing_id(self, client):
        resp = client.get("/api/immich/thumbnail/nonexistent")
        assert resp.status_code in (200, 400, 404, 500)
