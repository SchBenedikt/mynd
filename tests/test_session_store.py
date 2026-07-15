import time

from app.session_store import AgentSessionStore


def test_session_is_owner_bound_and_single_use():
    store = AgentSessionStore()
    session_id = store.create("alice", {"value": 1})

    assert store.consume("bob", session_id) == (None, "forbidden")
    assert store.consume("alice", session_id) == ({"value": 1}, None)
    assert store.consume("alice", session_id) == (None, "not_found")


def test_session_expires(monkeypatch):
    store = AgentSessionStore(ttl_seconds=1)
    monkeypatch.setattr(time, "time", lambda: 10)
    session_id = store.create("alice", {"value": 1})
    monkeypatch.setattr(time, "time", lambda: 12)

    assert store.consume("alice", session_id) == (None, "not_found")
