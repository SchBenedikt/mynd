"""Fail-closed subprocess sandboxing for agent-controlled code and commands."""

import os
import platform
import resource
import shutil
import subprocess
import sys
from pathlib import Path


class SandboxUnavailableError(RuntimeError):
    pass


def _resource_limits():
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024 * 1024, 16 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    if platform.system() != 'Darwin':
        try:
            resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024, 1024 * 1024 * 1024))
        except (OSError, ValueError):
            pass


def _sandbox_quote(path):
    return str(path).replace('\\', '\\\\').replace('"', '\\"')


def _macos_command(argv, cwd, allow_network):
    executable = shutil.which('sandbox-exec')
    if not executable:
        raise SandboxUnavailableError('sandbox-exec is unavailable')
    profile = [
        '(version 1)',
        '(deny default)',
        '(allow process*)',
        '(allow sysctl-read)',
        '(allow mach-lookup)',
        '(allow file-read*)',
        f'(deny file-read* (subpath "{_sandbox_quote(Path.home())}"))',
        '(deny file-read* (subpath "/Volumes"))',
        f'(allow file-read* (subpath "{_sandbox_quote(Path(sys.prefix).resolve())}"))',
        f'(allow file-read* (subpath "{_sandbox_quote(Path(sys.base_prefix).resolve())}"))',
        f'(allow file-read* (literal "{_sandbox_quote(Path(sys.executable))}"))',
        f'(allow file-read* (literal "{_sandbox_quote(Path(sys.executable).resolve())}"))',
        f'(allow file-read* (subpath "{_sandbox_quote(cwd)}"))',
    ]
    profile.extend([
        f'(allow file-write* (subpath "{_sandbox_quote(cwd)}"))',
        '(allow file-write* (literal "/dev/null"))',
    ])
    if allow_network:
        profile.append('(allow network*)')
    return [executable, '-p', '\n'.join(profile), *argv]


def _linux_command(argv, cwd, allow_network):
    executable = shutil.which('bwrap')
    if not executable:
        raise SandboxUnavailableError('bubblewrap is unavailable')
    command = [
        executable, '--die-with-parent', '--new-session', '--proc', '/proc', '--dev', '/dev',
        '--tmpfs', '/tmp',  # nosec B108
        '--bind', str(cwd), str(cwd), '--chdir', str(cwd),
    ]
    for path in ('/usr', '/bin', '/lib', '/lib64', '/etc'):
        if Path(path).exists():
            command.extend(['--ro-bind', path, path])
    if not allow_network:
        command.append('--unshare-net')
    return [*command, '--', *argv]


def sandbox_command(argv, cwd, *, allow_network=False):
    cwd = Path(cwd).resolve()
    argv = list(argv)
    executable = Path(argv[0])
    if executable.is_absolute():
        argv[0] = str(executable.resolve())
    system = platform.system()
    if system == 'Darwin':
        return _macos_command(argv, cwd, allow_network)
    if system == 'Linux':
        return _linux_command(argv, cwd, allow_network)
    raise SandboxUnavailableError(f'No supported sandbox backend for {system}')


def run_sandboxed(argv, *, cwd, timeout=60, allow_network=False, env=None):
    command = sandbox_command(argv, cwd, allow_network=allow_network)
    safe_env = {
        'PATH': os.defpath,
        'LANG': 'C.UTF-8',
        'LC_ALL': 'C.UTF-8',
        'PYTHONIOENCODING': 'utf-8',
        'PYTHONDONTWRITEBYTECODE': '1',
    }
    if env:
        safe_env.update(env)
    return subprocess.run(
        command,
        cwd=str(Path(cwd).resolve()),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=safe_env,
        preexec_fn=_resource_limits,
    )
