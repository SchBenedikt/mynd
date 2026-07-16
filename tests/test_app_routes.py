"""Test Flask app routes and API endpoints using the test client."""

import io
import re
import time

import pytest

import app as app_module
import app.auth as app_auth
import app.routes as app_routes
from app import app
from core.tools import _parse_tool_code_fallback


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app_module.AUTH_USERS["test-client"] = {
        "name": "Test Client",
        "role": "admin",
        "token": "test-client-token",
    }
    with app.test_client() as client:
        client.environ_base["HTTP_AUTHORIZATION"] = "Bearer test-client-token"
        yield client
    app_module.AUTH_USERS.pop("test-client", None)


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
        resp = client.get("/api/auth/me", headers={"Authorization": ""})
        # Should return 401 or 200 with no user
        assert resp.status_code in (200, 401)

    def test_auth_me_exposes_role_for_ui_authorization(self, client):
        response = client.get("/api/auth/me")

        assert response.status_code == 200
        assert response.get_json()["user"]["role"] == "admin"

    def test_refresh_rotates_token(self, client, monkeypatch, tmp_path):
        auth_file = tmp_path / "auth_users.json"
        monkeypatch.setattr(app_module, "AUTH_FILE", auth_file)
        monkeypatch.setattr(app_auth, "AUTH_FILE", auth_file)
        monkeypatch.setattr(app_routes, "AUTH_FILE", auth_file)
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


class TestToolFallbackParser:
    def test_plain_model_response_has_no_fallback_calls(self):
        assert _parse_tool_code_fallback("OK") == []

    def test_browser_tool_code_is_parsed(self):
        text = "<tool_code>browser_open https://example.com</tool_code>"

        assert _parse_tool_code_fallback(text) == [
            {"name": "browser_open", "args": {"url": "https://example.com"}}
        ]

    def test_structured_tool_formats_are_parsed(self):
        text = (
            '<tool_code><tool name="memory_set" key="topic" value="safe"/></tool_code>'
            '<tool_call><tool name="search_documents">'
            '<param name="query">release notes</param></tool></tool_call>'
        )

        assert _parse_tool_code_fallback(text) == [
            {'name': 'memory_set', 'args': {'key': 'topic', 'value': 'safe'}},
            {'name': 'search_documents', 'args': {'query': 'release notes'}},
        ]


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

    def test_txt_upload_uses_server_generated_id(self, client, monkeypatch, tmp_path):
        monkeypatch.setattr(app_routes, "DATA_DIR", tmp_path)
        response = client.post(
            "/api/knowledge/upload-txt",
            data={"files": (io.BytesIO(b"hello"), "../user-name.txt")},
            content_type="multipart/form-data",
        )
        assert response.status_code == 200
        document = response.get_json()["uploaded"][0]
        assert re.fullmatch(r"[0-9a-f]{32}\.txt", document["id"])
        assert document["name"] == "user-name.txt"
        assert (tmp_path / "text_uploads" / document["id"]).read_text() == "hello"
        assert client.delete(f"/api/knowledge/txt-files/{document['id']}").status_code == 200

    def test_graph_contract_and_node_details(self, client, monkeypatch):
        monkeypatch.setattr(
            app_routes.knowledge_base,
            "chunks",
            [{"source": "Projects/Mynd/README.md", "text": "hello", "headings": []}],
        )

        response = client.get("/api/knowledge/graph")
        assert response.status_code == 200
        graph = response.get_json()["data"]
        assert set(graph) == {"nodes", "edges", "stats"}
        assert graph["stats"]["node_count"] == 2
        document = next(node for node in graph["nodes"] if node["type"] == "document")

        detail = client.get(f"/api/knowledge/graph/node/{document['id']}")
        assert detail.status_code == 200
        assert detail.get_json()["data"]["node"] == document
        assert client.get("/api/knowledge/graph/node/missing").status_code == 404


class TestSecurityAPI:
    def test_security_status(self, client):
        resp = client.get("/api/security/status")
        assert resp.status_code == 200

    def test_sensitive_routes_require_authentication(self, client):
        response = client.get("/api/vault/entries", headers={"Authorization": ""})
        assert response.status_code == 401
        assert response.get_json()["authenticated"] is False

    def test_tool_confirmation_is_owner_bound_and_single_use(self, client):
        app_module.AUTH_USERS["other-user"] = {
            "name": "Other",
            "role": "user",
            "token": "other-token",
        }
        confirmation_id = "test-confirmation"
        app_module._PENDING_TOOL_CONFIRMS[confirmation_id] = {
            "tool": "think",
            "args": {"thought": "test"},
            "owner": "test-client",
            "created_at": time.time(),
        }
        payload = {"confirmation_id": confirmation_id, "confirmed": False}

        forbidden = client.post(
            "/api/tool/run",
            json=payload,
            headers={"Authorization": "Bearer other-token"},
        )
        assert forbidden.status_code == 403
        assert confirmation_id in app_module._PENDING_TOOL_CONFIRMS

        accepted = client.post("/api/tool/run", json=payload)
        assert accepted.status_code == 200
        assert confirmation_id not in app_module._PENDING_TOOL_CONFIRMS
        assert client.post("/api/tool/run", json=payload).status_code == 404
        app_module.AUTH_USERS.pop("other-user", None)


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
    @pytest.mark.skip(reason="Requires running Ollama and Nextcloud")
    def test_briefing_returns(self, client):
        """Briefing should return quickly. May fail if Ollama unavailable."""
        resp = client.get("/api/agent/briefing")
        assert resp.status_code in (200, 500, 502)


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

    @pytest.mark.parametrize(
        "path",
        [
            "/api/chat/summarize",
            "/api/calendar/update",
            "/api/tasks/update/example",
            "/api/email/send",
            "/api/tts/live",
            "/api/tts/synthesize",
        ],
    )
    def test_visible_frontend_actions_have_backend_routes(self, client, path):
        response = client.post(path, json={})
        assert response.status_code != 404


class TestBackupSecurity:
    def test_backup_requires_admin(self, client):
        no_auth = {"Authorization": ""}
        assert client.get("/api/backup/export", headers=no_auth).status_code == 401
        assert client.post("/api/backup/import", json={"files": {}}, headers=no_auth).status_code == 401

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
