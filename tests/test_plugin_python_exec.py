"""Test python_exec plugin: code execution, script management, safety checks."""


from data.plugins.python_exec import (
    SCRIPTS_DIR,
    _check_dangerous,
    python_create_script,
    python_execute,
    python_list_packages,
    python_list_scripts,
    python_read_script,
    python_run_script,
)


class TestSafetyChecks:
    def test_dangerous_imports_blocked(self):
        safe, msg = _check_dangerous('import socket')
        assert not safe, 'socket should be blocked'

    def test_subprocess_blocked(self):
        safe, msg = _check_dangerous('import subprocess\nsubprocess.run("ls")')
        assert not safe, 'subprocess should be blocked'

    def test_harmless_code_passes(self):
        safe, msg = _check_dangerous('print("hello world")\nx = 1 + 2')
        assert safe
        assert msg == ''

    def test_os_system_warned(self):
        safe, msg = _check_dangerous('os.system("ls")')
        assert safe
        assert 'os.system' in msg

    def test_eval_warned(self):
        safe, msg = _check_dangerous('eval("1+1")')
        assert safe
        assert 'eval' in msg


class TestExecuteCode:
    def test_simple_print(self):
        result = python_execute('print("Hello World")')
        assert 'Hello World' in result

    def test_calculation(self):
        result = python_execute('print(1 + 2 * 3)')
        assert '7' in result

    def test_multiline_execution(self):
        code = '''x = 5
y = 10
print(f"Summe: {x + y}")
'''
        result = python_execute(code)
        assert 'Summe: 15' in result

    def test_timeout_on_infinite_loop(self):
        result = python_execute('while True: pass', timeout=3)
        assert 'Timeout' in result

    def test_error_traceback_returned(self):
        result = python_execute('print(1/0)')
        assert 'ZeroDivisionError' in result or 'division by zero' in result

    def test_empty_code_returns_error(self):
        result = python_execute('')
        assert 'Kein Code' in result or '❌' in result

    def test_forbidden_import_rejected(self):
        result = python_execute('import socket\nsocket.gethostname()')
        assert 'Verbotene' in result or '❌' in result


class TestScriptManagement:
    def test_create_and_read_script(self):
        result = python_create_script('test_script.py', 'print("hello from script")')
        assert 'erstellt' in result

        result = python_read_script('test_script.py')
        assert 'hello from script' in result

    def test_create_duplicate_fails(self):
        python_create_script('dup_test.py', 'x=1')
        result = python_create_script('dup_test.py', 'x=2')
        assert 'existiert bereits' in result or '❌' in result

    def test_run_script(self):
        python_create_script('run_me.py', 'import sys\nprint(f"Args: {sys.argv[1:]}")')
        result = python_run_script('run_me.py', args='hello world')
        assert 'Args:' in result
        assert 'hello' in result

    def test_list_scripts(self):
        result = python_list_scripts()
        assert 'test_script' in result or 'run_me' in result or 'Keine' in result

    def test_read_nonexistent_script(self):
        result = python_read_script('nonexistent_12345.py')
        assert 'nicht gefunden' in result

    def test_run_nonexistent_script(self):
        result = python_run_script('nonexistent_12345.py')
        assert 'nicht gefunden' in result

    def test_create_script_adds_py_extension(self):
        result = python_create_script('auto_ext', 'print("ok")')
        assert 'auto_ext.py' in result or 'erstellt' in result

    def test_create_script_blocked_dangerous(self):
        result = python_create_script('evil.py', 'import subprocess\nsubprocess.run("rm -rf /")')
        assert 'Verbotene' in result or '❌' in result


class TestPackageManagement:
    def test_list_packages_returns_packages(self):
        result = python_list_packages()
        assert 'Package' in result or 'pip' in result or '📦' in result

    def test_execute_uses_requests_library(self):
        result = python_execute('import requests; print(requests.__version__[:10])', timeout=15)
        assert len(result) > 0


# Cleanup test scripts after test run
def teardown_module():
    for f in SCRIPTS_DIR.glob('test_*.py'):
        f.unlink(missing_ok=True)
    for f in SCRIPTS_DIR.glob('run_me.py'):
        f.unlink(missing_ok=True)
    for f in SCRIPTS_DIR.glob('dup_test.py'):
        f.unlink(missing_ok=True)
    for f in SCRIPTS_DIR.glob('auto_ext.py'):
        f.unlink(missing_ok=True)
