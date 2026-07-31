"""Test Flask app routes and API endpoints using the test client."""

import io
import re
import threading
import time

import pytest

import app as app_module
import app.routes as app_routes
import app.state as app_state
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
        monkeypatch.setattr(app_state, "AUTH_FILE", auth_file)
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
        monkeypatch.setattr(app_routes, "_load_memory", lambda: {})

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

    def test_api_allows_any_browser_origin_without_csp(self, client, monkeypatch):
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")
        response = client.get(
            "/api/capabilities",
            headers={"Origin": "https://any-domain.example"},
        )

        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Origin"] == "https://any-domain.example"
        assert "Content-Security-Policy" not in response.headers

    def test_sensitive_routes_require_authentication(self, client):
        response = client.get("/api/vault/entries", headers={"Authorization": ""})
        assert response.status_code == 401
        assert response.get_json()["authenticated"] is False

    def test_browser_downloads_require_auth_and_confine_paths(self, client, monkeypatch, tmp_path):
        downloads = tmp_path / "downloads"
        downloads.mkdir()
        (downloads / "report.txt").write_text("safe")
        (tmp_path / "secret.txt").write_text("secret")
        monkeypatch.setattr(app_routes, "BROWSER_DOWNLOADS_DIR", downloads)

        unauthenticated = client.get(
            "/data/browser_downloads/report.txt",
            headers={"Authorization": ""},
        )
        assert unauthenticated.status_code == 401

        download = client.get("/data/browser_downloads/report.txt")
        assert download.status_code == 200
        assert download.data == b"safe"

        traversal = client.get("/data/browser_downloads/../secret.txt")
        assert traversal.status_code == 404

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

    def test_assistant_briefing_returns_items(self, client, monkeypatch):
        resp = client.get("/api/assistant/briefing/current")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert isinstance(data["items"], list)
        assert "generated_at" in data

    def test_assistant_briefing_forwards_gathered_items(self, client, monkeypatch):
        fake_items = [{"key": "calendar", "title": "📅 Termine", "content": "10:00 Meeting"}]
        monkeypatch.setattr(app_routes, "_gather_briefing_items", lambda: fake_items)
        monkeypatch.setattr(app_routes, "_BRIEFING_CACHE", {})
        resp = client.get("/api/assistant/briefing/current")
        assert resp.status_code == 200
        assert resp.get_json()["items"] == fake_items

    def test_assistant_briefing_force_refreshes(self, client, monkeypatch):
        calls = []
        monkeypatch.setattr(app_routes, "_gather_briefing_items",
                            lambda: calls.append(1) or [{"key": "x", "title": "T", "content": "C"}])
        monkeypatch.setattr(app_routes, "_BRIEFING_CACHE", {})
        client.get("/api/assistant/briefing/current?force=true")
        client.get("/api/assistant/briefing/current?force=true")
        assert len(calls) == 2

    def test_greeting_cached_per_period(self, client, monkeypatch):
        calls = []
        monkeypatch.setattr(app_routes.ollama_client, "model", "test-model")
        monkeypatch.setattr(app_routes, "_GREETING_CACHE", {})
        monkeypatch.setattr("core.llm.chat_with_tools",
                            lambda *a, **k: (calls.append(1), {"message": {"content": "Hallo"}})[1])
        resp = client.post("/api/ai/greeting", json={"language": "de"})
        assert resp.status_code == 200
        resp2 = client.post("/api/ai/greeting", json={"language": "de"})
        assert resp2.get_json()["greeting"] == "Hallo"
        assert len(calls) == 1

    def test_gather_briefing_filters_completed_tasks(self, monkeypatch):
        monkeypatch.setattr(
            app_routes._nc_module, "nextcloud_caldav_query",
            lambda *a, **k: ("10:00 Meeting", None))
        monkeypatch.setattr(app_routes._email_module, "_list_accounts",
                            lambda: "Keine E-Mail-Konten konfiguriert.")
        monkeypatch.setattr(
            app_routes._nc_module, "nextcloud_tasks_query",
            lambda: "📌 [Schule] Offen | Fällig: ? | Status: NEEDS-ACTION\n📌 [Schule] Alt | Fällig: ? | Status: COMPLETED")
        monkeypatch.setattr(
            app_routes._immich_module, "immich_search_photos",
            lambda *a, **k: ("(keine Ergebnisse)", None))
        items = app_routes._gather_briefing_items()
        keys = [i["key"] for i in items]
        assert keys[0] == "overview"
        tasks_item = next(i for i in items if i["key"] == "tasks")
        assert "COMPLETED" not in tasks_item["content"]
        assert "Offen" in tasks_item["content"]
        assert "Status: COMPLETED" not in items[0]["content"]


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
        monkeypatch.setattr(app_state, "AUTH_FILE", auth_file)
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


def _load_main_script():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location(
        "mynd_main_script", Path(__file__).resolve().parents[1] / "app.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestModelWarmUp:
    def test_warm_up_calls_ollama_and_handles_ok(self, monkeypatch):
        _main = _load_main_script()
        _ollama = _main.ollama_client
        calls = []

        def fake_chat(messages):
            calls.append(messages)
            return {"response": "OK"}

        monkeypatch.setattr(_ollama, "chat", fake_chat)
        _main._warm_up_model()
        assert len(calls) == 1
        assert calls[0][0]["content"] == "Reply only with: OK"

    def test_warm_up_handles_error_result_without_raising(self, monkeypatch, caplog):
        _main = _load_main_script()
        _ollama = _main.ollama_client
        monkeypatch.setattr(
            _ollama,
            "chat",
            lambda messages: {"error": "model not loaded"},
        )
        _main._warm_up_model()
        assert any("Model warm-up" in r.message for r in caplog.records)

    def test_warm_up_handles_exception_without_raising(self, monkeypatch, caplog):
        _main = _load_main_script()
        _ollama = _main.ollama_client
        def boom(messages):
            raise RuntimeError("ollama unreachable")

        monkeypatch.setattr(_ollama, "chat", boom)
        _main._warm_up_model()
        assert any("Model warm-up failed" in r.message for r in caplog.records)

    def test_warm_up_runs_in_daemon_thread(self, monkeypatch):
        _main = _load_main_script()
        _ollama = _main.ollama_client
        started = threading.Event()
        real_chat = _ollama.chat

        def slow_chat(messages):
            started.set()
            time.sleep(5)
            return real_chat(messages)

        monkeypatch.setattr(_ollama, "chat", slow_chat)
        t = threading.Thread(target=_main._warm_up_model, daemon=True, name="model-warmup")
        t.start()
        assert started.wait(timeout=2)
        assert t.daemon is True
        assert t.name == "model-warmup"
        t.join(timeout=0.1)

class TestOllamaClient410:
    def test_chat_retries_once_on_410(self, monkeypatch):
        from app.ollama_client import OllamaClient

        class _Resp:
            def __init__(self, status, payload=None):
                self.status_code = status
                self._payload = payload or {}

            def json(self):
                return self._payload

            def raise_for_status(self):
                if self.status_code >= 400:
                    import requests
                    raise requests.exceptions.HTTPError(
                        f"{self.status_code} Client Error", response=self
                    )

        calls = []

        def fake_post(url, json=None, timeout=None):
            calls.append(json)
            if len(calls) == 1:
                return _Resp(410)
            return _Resp(200, {"message": {"role": "assistant", "content": "recovered"}})

        monkeypatch.setattr("app.ollama_client.requests.post", fake_post)
        client = OllamaClient(base_url="http://127.0.0.1:11434", model="gemma3")
        result = client.chat([{"role": "user", "content": "hi"}])
        assert len(calls) == 2
        assert calls[0].get("keep_alive") == "30m"
        assert result["message"]["content"] == "recovered"

    def test_chat_410_twice_returns_friendly_error(self, monkeypatch):
        from app.ollama_client import OllamaClient

        class _Resp:
            status_code = 410

            def raise_for_status(self):
                import requests
                raise requests.exceptions.HTTPError("410 Client Error: Gone", response=self)

        monkeypatch.setattr("app.ollama_client.requests.post", lambda *a, **k: _Resp())
        client = OllamaClient(base_url="http://127.0.0.1:11434", model="gemma3")
        result = client.chat([{"role": "user", "content": "hi"}])
        assert result.get("error") and "entladen" in result["error"]

