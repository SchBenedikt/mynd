import json
import sys
from unittest.mock import MagicMock

import pytest

import app.audit as audit
import core.tools as tools
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
    assert any(message in denied_read.stderr for message in ('Operation not permitted', 'No such file or directory'))

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


def test_ssrf_redirect_chain_blocked(monkeypatch):
    monkeypatch.delenv('MYND_HTTP_ALLOW_PRIVATE_HOSTS', raising=False)

    redirect_response = MagicMock()
    redirect_response.is_redirect = True
    redirect_response.is_permanent_redirect = False
    redirect_response.headers = {'Location': 'http://internal.admin/service'}
    redirect_response.status_code = 301

    call_count = 0

    def mock_request(method, url, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return redirect_response
        raise AssertionError('Second request issued — redirect was not validated')

    monkeypatch.setattr('core.tools.requests.request', mock_request)

    res_map = {
        'example.test': [('family', 'type', 'proto', 'canonname', ('203.0.113.1', 0))],
        'internal.admin': [('family', 'type', 'proto', 'canonname', ('10.0.0.99', 0))],
    }

    def mock_getaddrinfo(host, port, *args, **kwargs):
        return res_map.get(host.rstrip('.').lower(), [(None, None, None, None, ('127.0.0.1', 0))])

    monkeypatch.setattr('core.tools.socket.getaddrinfo', mock_getaddrinfo)

    result = tools.http_request(url='http://example.test/page')
    assert '❌' in result
    assert 'blocked' in result.lower()


def test_ssrf_dns_rebinding_detected(monkeypatch):
    monkeypatch.delenv('MYND_HTTP_ALLOW_PRIVATE_HOSTS', raising=False)

    import socket as _sock

    call_count = 0

    def mock_getaddrinfo(host, port, *args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return [(_sock.AF_INET, _sock.SOCK_STREAM, _sock.IPPROTO_TCP, '', ('1.2.3.4', 0))]
        return [(_sock.AF_INET, _sock.SOCK_STREAM, _sock.IPPROTO_TCP, '', ('5.6.7.8', 0))]

    monkeypatch.setattr('core.tools.socket.getaddrinfo', mock_getaddrinfo)

    result = tools.http_request(url='http://example.test/resource')
    assert '❌' in result
    assert 'blocked' in result.lower()


def test_shell_injection_patterns(monkeypatch):
    monkeypatch.setattr(tools, 'PERMISSION_MODE', 'auto')
    dangerous_patterns = [
        ('$(cat /etc/passwd)', 'blocked'),
        ('`cat /etc/passwd`', 'blocked'),
        ('${HOME}', 'blocked'),
    ]
    for cmd, expected_sub in dangerous_patterns:
        result = tools.execute_bash(cmd)
        assert '❌' in result and expected_sub in result, f'Pattern {cmd!r} should be blocked'


def test_null_byte_injection_blocked(monkeypatch, tmp_path):
    workspace = tmp_path / 'workspace'
    monkeypatch.setenv('MYND_WORKSPACE_DIR', str(workspace))
    workspace.mkdir()

    result_read = tools.read_local_file('safe.txt\x00evil')
    assert result_read.startswith('❌')

    result_write = tools.write_local_file('safe.txt\x00evil', 'data')
    assert result_write.startswith('❌')


def test_very_long_input_handling():
    very_long = 'x' * 200000

    result = tools.execute_bash(very_long)
    assert result.startswith('❌')
    assert 'maximum' in result or 'exceeds' in result or 'Länge' in result

    result = tools.http_request(url=f'http://example.com/{very_long[:50000]}')
    assert result.startswith('❌')

    very_long_100k = 'x' * 200000
    result = tools.write_local_file('test_long.txt', very_long_100k)
    assert isinstance(result, str)
    assert len(result) > 0


def test_html_injection_in_outputs(monkeypatch, tmp_path):
    workspace = tmp_path / 'workspace'
    monkeypatch.setenv('MYND_WORKSPACE_DIR', str(workspace))
    workspace.mkdir()

    html_file = workspace / 'page.html'
    html_file.write_text('<script>alert(1)</script>')

    result = tools.read_local_file('page.html')
    assert '<script>' in result
    assert result == '<script>alert(1)</script>'

    html_path = workspace / '<img src=x onerror=alert(1)>.txt'
    html_path.write_text('content')

    result = tools.read_local_file('<img src=x onerror=alert(1)>.txt')
    assert 'content' in result or '❌' in result
