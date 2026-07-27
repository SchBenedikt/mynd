"""Regression tests for tool security boundaries."""

import app.agent_loop as agent_loop
import core.tool_creator as creator
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


def test_symlink_traversal_blocked(monkeypatch, tmp_path):
    workspace = tmp_path / "workspace"
    monkeypatch.setenv("MYND_WORKSPACE_DIR", str(workspace))
    workspace.mkdir()

    outside_file = tmp_path / "secret.txt"
    outside_file.write_text("leaked")
    link = workspace / "leak"
    link.symlink_to(outside_file)

    result = tools.read_local_file("leak")
    assert result.startswith("❌")
    assert "outside" in result or "außerhalb" in result or "blocked" in result

    result_write = tools.write_local_file("leak", "data")
    assert result_write.startswith("❌")


def test_rate_limiting_enforced():
    tools._rate_limit_data.clear()
    test_name = "_test_rate_limit"

    results = []
    for _ in range(15):
        ok, err = tools._check_rate_limit(test_name)
        results.append((ok, err))

    for i in range(10):
        assert results[i][0], f"Call {i} should be allowed: {results[i][1]}"
    for i in range(10, 15):
        assert not results[i][0], f"Call {i} should be rate limited: {results[i][1]}"
        assert "Rate limit" in results[i][1]


def test_message_context_limit_enforced():
    small_msgs = [{"role": "user", "content": "hello"}]
    unchanged = agent_loop._enforce_context_limit(small_msgs)
    assert unchanged is small_msgs

    tool_msgs = [{"role": "tool", "content": "x" * 5000, "name": "test"} for _ in range(200)]
    original_size = agent_loop._context_size(tool_msgs)
    assert original_size > agent_loop.MAX_CONTEXT_CHARS

    truncated = agent_loop._enforce_context_limit(tool_msgs)
    assert agent_loop._context_size(truncated) < original_size
    assert agent_loop._context_size(truncated) <= agent_loop.MAX_CONTEXT_CHARS

    truncated_count = sum(1 for m in truncated if m.get("content") == "<truncated_tool_result>")
    assert truncated_count >= 190


def test_vault_key_length_handling(monkeypatch):
    vault_data = {}
    monkeypatch.setattr('core.vault.load_vault', lambda *a, **kw: vault_data)
    monkeypatch.setattr('core.vault.save_vault', lambda v, *a, **kw: vault_data.update(v))

    long_key = "k" * 50000
    long_value = "v" * 500000

    result = tools.vault_set(long_key, long_value)
    assert "gespeichert" in result
    assert vault_data.get(long_key) == long_value

    get_result = tools.vault_get(long_key)
    assert get_result == long_value


def test_tool_creator_remaining_bypasses():
    valid_name = "test_sec_tool"
    valid_desc = "Security validation test tool"
    valid_params = {"input": {"type": "string", "description": "test input"}}

    test_cases = [
        (
            "os.system in code",
            """
def my_tool(input):
    import os
    os.system("ls")
""",
            "os.system",
        ),
        (
            "exec( with space",
            """
def my_tool(input):
    exec ("print('hello')")
""",
            "exec",
        ),
        (
            "sys.modules access",
            """
def my_tool(input):
    import sys
    m = sys.modules['subprocess']
""",
            "sys.modules",
        ),
        (
            "getattr __builtins__ exec",
            """
def my_tool(input):
    b = __builtins__
    f = getattr(b, 'exec')
""",
            "builtins",
        ),
    ]

    for name, code, expected_sub in test_cases:
        error = creator._validate(valid_name, valid_desc, valid_params, code)
        assert error is not None, f"Expected {name} to be blocked, but no error returned"
        assert expected_sub.lower() in error.lower() or '\u274c' in error, (
            f"Expected error containing {expected_sub!r}, got: {error}"
        )


def test_tool_creator_allows_safe_code():
    error = creator._validate(
        "safe_tool",
        "A perfectly safe tool",
        {"msg": {"type": "string", "description": "a message"}},
        """
def safe_tool(msg):
    return f"Hello, {msg}!"
""",
    )
    assert error is None, f"Safe code should not produce an error, got: {error}"
