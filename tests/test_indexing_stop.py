import threading
import time

import pytest

import app.routes as routes
import app.state as state
from app import app


@pytest.fixture(autouse=True)
def authenticated_user(monkeypatch):
    state.AUTH_USERS["index-test"] = {"role": "admin", "token_hash": state.token_hash("test-client-token"), "token_expires_at": time.time() + 3600}
    yield
    state.AUTH_USERS.pop("index-test", None)


def test_indexing_stop_sets_cancellation_event(monkeypatch):
    routes.INDEXING_CANCEL.clear()
    monkeypatch.setattr(routes, "INDEXING_STATUS", {"status": "running", "run_id": "run-1"})

    with app.test_client() as client:
        response = client.post("/api/indexing/stop", headers={"Authorization": "Bearer test-client-token"})

    assert response.status_code == 200
    assert response.get_json()["status"] == "stopping"
    assert routes.INDEXING_CANCEL.is_set()
    assert routes.INDEXING_STATUS["status"] == "stopping"
    routes.INDEXING_CANCEL.clear()


def test_indexing_start_rejects_parallel_run(monkeypatch):
    monkeypatch.setattr(routes, "INDEXING_STATUS", {"status": "running", "run_id": "run-1"})

    with app.test_client() as client:
        response = client.post("/api/indexing/start", headers={"Authorization": "Bearer test-client-token"})

    assert response.status_code == 409
    assert response.get_json()["success"] is False


def test_indexing_start_requires_complete_saved_nextcloud_config(monkeypatch, tmp_path):
    monkeypatch.setattr(routes, "INDEXING_STATUS", {"status": "idle"})
    monkeypatch.setattr(routes, "DATA_DIR", tmp_path)
    monkeypatch.setattr(routes, "_vg", lambda _key: "")

    with app.test_client() as client:
        response = client.post("/api/indexing/start", headers={"Authorization": "Bearer test-client-token"})

    assert response.status_code == 400
    assert "app password" in response.get_json()["error"]


def test_indexing_progress_reports_real_result_metrics(monkeypatch):
    monkeypatch.setattr(
        routes,
        "INDEXING_STATUS",
        {
            "status": "completed",
            "progress": 100,
            "processed_files": 3,
            "total_files": 3,
            "chunks_created": 7,
            "documents_processed": 3,
        },
    )

    with app.test_client() as client:
        payload = client.get("/api/indexing/progress", headers={"Authorization": "Bearer test-client-token"}).get_json()

    assert payload["chunks_created"] == 7
    assert payload["documents_processed"] == 3


def test_indexing_config_rejects_insecure_remote_url(monkeypatch, tmp_path):
    monkeypatch.setattr(routes, "DATA_DIR", tmp_path)
    monkeypatch.setattr(routes, "_vg", lambda _key: "stored-password")

    with app.test_client() as client:
        response = client.post(
            "/api/indexing/config",
            headers={"Authorization": "Bearer test-client-token"},
            json={"url": "http://cloud.example", "username": "alice", "password": ""},
        )

    assert response.status_code == 400
    assert "HTTPS" in response.get_json()["error"]


def test_syncer_honours_cancellation_before_network_call(tmp_path):
    from scripts.sync_nextcloud import NextcloudSyncer

    class FailingClient:
        def list_folder(self, _folder):
            raise AssertionError("network should not be called after cancellation")

    event = threading.Event()
    event.set()
    syncer = NextcloudSyncer(FailingClient(), tmp_path / "docs", tmp_path / "state.json", {".txt"}, ["Documents"])

    assert syncer.full_sync(event) == {"stats": syncer.stats, "files": []}


def test_syncer_does_not_delete_local_files_after_failed_remote_listing(tmp_path):
    from scripts.sync_nextcloud import NextcloudSyncer, SyncState

    local_file = tmp_path / "docs" / "Documents" / "kept.txt"
    local_file.parent.mkdir(parents=True)
    local_file.write_text("keep me")
    state_file = tmp_path / "state.json"
    state = SyncState(files={"Documents/kept.txt": {"hash": "old", "size": 7, "modified": None}})
    state.save(state_file)

    class FailingClient:
        def list_folder(self, _folder):
            raise RuntimeError("temporary network error")

    syncer = NextcloudSyncer(FailingClient(), tmp_path / "docs", state_file, {".txt"}, ["Documents"])
    result = syncer.full_sync()

    assert result["stats"]["errors"] == 1
    assert local_file.read_text() == "keep me"


def test_syncer_rejects_paths_outside_local_directory(tmp_path):
    from scripts.sync_nextcloud import NextcloudSyncer

    syncer = NextcloudSyncer(object(), tmp_path / "docs", tmp_path / "state.json", {".txt"}, [""])

    with pytest.raises(ValueError, match="escapes"):
        syncer._safe_local_path("../../outside.txt")


def test_syncer_folder_filter_supports_root_and_nested_paths(tmp_path):
    from scripts.sync_nextcloud import NextcloudSyncer

    root_syncer = NextcloudSyncer(object(), tmp_path / "root", tmp_path / "root-state.json", {".md"}, [""])
    nested_syncer = NextcloudSyncer(
        object(),
        tmp_path / "nested",
        tmp_path / "nested-state.json",
        {".md"},
        ["Documents/Work"],
    )

    assert root_syncer._should_sync("Documents/note.md") is True
    assert nested_syncer._should_sync("Documents/Work/note.md") is True
    assert nested_syncer._should_sync("Documents/Private/note.md") is False
