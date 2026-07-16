import json
import sys

import pytest

import app.audit as audit
from app.agent_loop import _tool_requires_confirmation
from core.sandbox import _linux_command, run_sandboxed
from core.tools import _validate_http_url


def test_private_and_non_http_urls_are_blocked(monkeypatch):
    monkeypatch.delenv('MYND_HTTP_ALLOW_PRIVATE_HOSTS', raising=False)
    monkeypatch.setattr('socket.getaddrinfo', lambda *args: [(None, None, None, None, ('127.0.0.1', 0))])

    with pytest.raises(ValueError, match='Private or reserved'):
        _validate_http_url('http://example.test/resource')
    with pytest.raises(ValueError, match='Only absolute'):
        _validate_http_url('file:///etc/passwd')


def test_sandbox_denies_home_reads_and_network(tmp_path):
    script = tmp_path / 'script.py'
    script.write_text("from pathlib import Path; Path.home().joinpath('.zshrc').read_text()")
    denied_read = run_sandboxed([sys.executable, '-I', '-S', str(script)], cwd=tmp_path)
    assert denied_read.returncode != 0
    assert 'Operation not permitted' in denied_read.stderr

    script.write_text("import socket; socket.create_connection(('example.com', 80))")
    denied_network = run_sandboxed([sys.executable, '-I', '-S', str(script)], cwd=tmp_path)
    assert denied_network.returncode != 0


def test_linux_sandbox_mounts_hosted_python_read_only(monkeypatch, tmp_path):
    monkeypatch.setattr('core.sandbox.shutil.which', lambda name: '/usr/bin/bwrap')

    command = _linux_command(['/opt/python/bin/python', '-V'], tmp_path, False)

    assert command[command.index('/opt') - 1] == '--ro-bind'
    assert command[command.index('/opt') + 1] == '/opt'


def test_audit_redacts_nested_secrets_and_omits_results(monkeypatch, tmp_path):
    monkeypatch.setattr(audit, 'DATA_DIR', tmp_path)
    audit.audit_tool(
        'http_request', 'alice',
        {'url': 'https://example.com', 'headers': {'Authorization': 'Bearer secret'}, 'token': 'secret'},
        True, result_preview='must never be logged', confirmation='confirmed', request_id='request-1',
    )

    event = json.loads((tmp_path / 'audit.jsonl').read_text())
    assert event['arguments']['headers']['Authorization'] == '***'
    assert event['arguments']['token'] == '***'
    assert 'must never be logged' not in json.dumps(event)
    assert 'result_preview' not in event


def test_mutating_tools_require_confirmation():
    assert _tool_requires_confirmation('email_send', {})
    assert _tool_requires_confirmation('http_request', {'method': 'POST'})
    assert not _tool_requires_confirmation('http_request', {'method': 'GET'})
    assert not _tool_requires_confirmation('search_documents', {})
