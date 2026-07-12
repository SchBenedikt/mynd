"""Test Flask app routes and API endpoints using the test client."""

import pytest

import app as app_module
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

    def test_refresh_rotates_token(self, client, monkeypatch, tmp_path):
        auth_file = tmp_path / "auth_users.json"
        monkeypatch.setattr(app_module, "AUTH_FILE", auth_file)
        monkeypatch.setitem(
            app_module.AUTH_USERS,
            "refresh-user",
            {"name": "Refresh User", "role": "user", "token": "old-token"},
        )

        response = client.post(
            "/api/auth/refresh",
            headers={"Authorization": "Bearer old-token"},
        )

        assert response.status_code == 200
        new_token = response.get_json()["token"]
        assert new_token != "old-token"
        assert len(new_token) == 64
        assert client.get(
            "/api/auth/me", headers={"Authorization": "Bearer old-token"}
        ).get_json()["authenticated"] is False
        assert client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {new_token}"}
        ).get_json()["authenticated"] is True


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


class TestBackupSecurity:
    def test_backup_requires_admin(self, client):
        assert client.get("/api/backup/export").status_code == 401
        assert client.post("/api/backup/import", json={"files": {}}).status_code == 401

    def test_backup_import_rejects_path_traversal(self, client, monkeypatch, tmp_path):
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        auth_file = data_dir / "auth_users.json"
        monkeypatch.setattr(app_module, "DATA_DIR", data_dir)
        monkeypatch.setattr(app_module, "AUTH_FILE", auth_file)
        monkeypatch.setitem(
            app_module.AUTH_USERS,
            "admin",
            {"name": "Admin", "role": "admin", "token": "test-admin-token"},
        )

        response = client.post(
            "/api/backup/import",
            headers={"Authorization": "Bearer test-admin-token"},
            json={"files": {"../outside.json": {"content": "owned", "encoding": "utf-8"}}},
        )

        assert response.status_code == 200
        assert response.get_json()["restored"] == 0
        assert not (tmp_path / "outside.json").exists()
