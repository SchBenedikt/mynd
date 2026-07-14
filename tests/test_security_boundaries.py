"""Regression tests for tool security boundaries."""

import core.tools as tools


def test_pending_confirmation_stops_bash(monkeypatch):
    monkeypatch.setattr(tools, "PERMISSION_MODE", "ask")
    monkeypatch.setattr(
        tools,
        "_request_tool_confirmation",
        lambda *_: "⏳ TOOL_CONFIRM_REQUIRED: confirm",
    )
    monkeypatch.setattr(
        tools.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("command executed")),
    )
    assert tools.execute_bash("echo unsafe").startswith("⏳ TOOL_CONFIRM_REQUIRED")


def test_file_tools_cannot_escape_workspace(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("MYND_WORKSPACE_DIR", str(workspace))
    result = tools.write_local_file("../outside.txt", "blocked")
    assert result.startswith("❌")
    assert not (tmp_path / "outside.txt").exists()


def test_file_tools_allow_workspace_files(monkeypatch, tmp_path):
    monkeypatch.setenv("MYND_WORKSPACE_DIR", str(tmp_path))
    assert "geschrieben" in tools.write_local_file("notes/example.txt", "hello")
    assert tools.read_local_file("notes/example.txt") == "hello"


def test_http_tool_blocks_private_addresses(monkeypatch):
    monkeypatch.delenv("MYND_HTTP_ALLOW_PRIVATE_HOSTS", raising=False)
    monkeypatch.setattr(
        tools.socket,
        "getaddrinfo",
        lambda *_: [(None, None, None, None, ("127.0.0.1", 80))],
    )
    result = tools.http_request(url="http://example.test/private")
    assert result.startswith("❌ Request blocked")
