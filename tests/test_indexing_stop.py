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


def test_syncer_honours_cancellation_before_network_call(tmp_path):
    from scripts.sync_nextcloud import NextcloudSyncer

    class FailingClient:
        def list_folder(self, _folder):
            raise AssertionError("network should not be called after cancellation")

    event = threading.Event()
    event.set()
    syncer = NextcloudSyncer(FailingClient(), tmp_path / "docs", tmp_path / "state.json", {".txt"}, ["Documents"])

    assert syncer.full_sync(event) == {"stats": syncer.stats, "files": []}
