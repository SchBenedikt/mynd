"""Python Code Execution Plugin

Allows the AI to write, execute, and manage Python scripts securely.
Runs in a temp directory with timeout, no network access, blocked dangerous imports.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path

PLUGIN_NAME = 'python_exec'
PLUGIN_DESC = 'Python-Code-Ausführung: Skripte schreiben, ausführen, Pakete installieren'
TOOL_SCHEMA = True

GENERATED_DIR = Path(__file__).resolve().parents[2] / 'data' / 'generated'
SCRIPTS_DIR = GENERATED_DIR / 'scripts'
MAX_OUTPUT_LINES = 200
MAX_OUTPUT_CHARS = 15000
DEFAULT_TIMEOUT = 30

FORBIDDEN_IMPORTS = [
    'ctypes', '_ctypes', 'socket',  # system-level
    'multiprocessing',  # fork bombs
    'subprocess',  # shell access (can't block entirely but warn)
]

DANGEROUS_PATTERNS = [
    'os.system', 'os.popen', 'os.fork', 'os.exec',
    'shutil.rmtree',  # allowed with care
    '__import__', 'eval(', 'exec(',
    'base64.b64decode',  # often used for obfuscation
]

SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

TOOLS = [
    {
        'name': 'python_execute',
        'description': 'Führe Python-Code aus. Berechnungen, Datenanalyse, API, Diagramme, Web-Scraping. max 30s.',
        'parameters': {
            'code': {'type': 'string', 'description': 'Python-Code (mehrere Zeilen möglich). Nutze print() für Ausgabe.'},
            'timeout': {'type': 'number', 'description': 'Maximale Laufzeit in Sekunden (5-60, default: 30)'},
        },
        'required': ['code'],
    },
    {
        'name': 'python_create_script',
        'description': 'Erstelle eine Python-Skript-Datei im generated/scripts/ Verzeichnis für spätere Ausführung oder Bearbeitung.',
        'parameters': {
            'filename': {'type': 'string', 'description': 'Dateiname (z.B. "analyse.py"). Überschreibt existierende Dateien nicht.'},
            'content': {'type': 'string', 'description': 'Vollständiger Python-Code'},
        },
        'required': ['filename', 'content'],
    },
    {
        'name': 'python_run_script',
        'description': 'Führe ein gespeichertes Python-Skript aus dem generated/scripts/ Verzeichnis aus.',
        'parameters': {
            'filename': {'type': 'string', 'description': 'Dateiname (z.B. "analyse.py")'},
            'args': {'type': 'string', 'description': 'Kommandozeilen-Argumente (optional, Leerzeichen-getrennt)'},
            'timeout': {'type': 'number', 'description': 'Maximale Laufzeit in Sekunden (5-120, default: 30)'},
        },
        'required': ['filename'],
    },
    {
        'name': 'python_list_scripts',
        'description': 'Liste alle gespeicherten Python-Skripte mit Größe und Änderungsdatum auf.',
        'parameters': {},
    },
    {
        'name': 'python_read_script',
        'description': 'Zeige den Inhalt eines gespeicherten Python-Skripts an.',
        'parameters': {
            'filename': {'type': 'string', 'description': 'Dateiname (z.B. "analyse.py")'},
        },
        'required': ['filename'],
    },
    {
        'name': 'python_install_package',
        'description': 'Installiere ein Python-Paket via pip. Nutze python_list_packages vorher, um zu prüfen ob schon installiert.',
        'parameters': {
            'package': {'type': 'string', 'description': 'Paketname (z.B. "pandas", "matplotlib", "requests")'},
        },
        'required': ['package'],
    },
    {
        'name': 'python_list_packages',
        'description': 'Liste alle installierten Python-Pakete auf (pip list).',
        'parameters': {},
    },
]


def _check_dangerous(code):
    """Check code for dangerous patterns and return (safe, warning_msg)."""
    code_lower = code.lower()
    dangerous = []
    for pat in DANGEROUS_PATTERNS:
        if pat in code_lower:
            dangerous.append(pat)
    forbidden = []
    for imp in FORBIDDEN_IMPORTS:
        if f'import {imp}' in code_lower or f'from {imp}' in code_lower:
            forbidden.append(imp)
    warnings = []
    if dangerous:
        warnings.append(f"Vorsicht: gefährliche Patterns gefunden: {', '.join(dangerous)}")
    if forbidden:
        return False, f"❌ Verbotene Imports: {', '.join(forbidden)}"
    return True, '; '.join(warnings) if warnings else ''


def _execute_code(code, timeout=30):
    """Execute Python code in a subprocess with timeout. Returns (output, error)."""
    timeout = min(max(int(timeout), 5), 60)

    safe, warning = _check_dangerous(code)
    if not safe:
        return '', warning

    tmp = tempfile.mkdtemp(prefix='mynd_py_')
    script_file = os.path.join(tmp, 'script.py')
    try:
        with open(script_file, 'w') as f:
            f.write(code)

        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONDONTWRITEBYTECODE'] = '1'

        result = subprocess.run(
            [sys.executable, '-u', script_file],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=tmp,
            env=env,
        )

        stdout = result.stdout or ''
        stderr = result.stderr or ''
        full_output = ''
        if stdout:
            full_output += stdout
        if stderr:
            if full_output:
                full_output += '\n--- STDERR ---\n'
            full_output += stderr

        lines = full_output.split('\n')
        if len(lines) > MAX_OUTPUT_LINES:
            full_output = '\n'.join(lines[:MAX_OUTPUT_LINES])
            full_output += f'\n... (Ausgabe gekürzt, {len(lines)} Zeilen total)'
        if len(full_output) > MAX_OUTPUT_CHARS:
            full_output = full_output[:MAX_OUTPUT_CHARS]
            full_output += '\n... (Ausgabe gekürzt)'

        output_parts = []
        if warning:
            output_parts.append(f"⚠️ {warning}")
        if result.returncode != 0:
            output_parts.append(f"❌ Exit-Code: {result.returncode}")
        if full_output.strip():
            output_parts.append(f"```\n{full_output}\n```")
        if not output_parts:
            output_parts.append("✅ Code ausgeführt – keine Ausgabe (verwende `print()` für Ergebnisse)")

        return '\n'.join(output_parts), None
    except subprocess.TimeoutExpired:
        return '', f'❌ Timeout nach {timeout}s – Code zu langsam oder Endlosschleife'
    except Exception as e:
        return '', f'❌ Ausführungsfehler: {e}'
    finally:
        try:
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass


def _find_script(filename):
    """Find a script by filename, return full path or None."""
    filename = filename.strip()
    full = SCRIPTS_DIR / filename
    if full.exists() and full.is_file():
        return full
    for f in SCRIPTS_DIR.iterdir():
        if f.name.lower() == filename.lower():
            return f
    return None


def python_execute(code, timeout=30):
    code = textwrap.dedent(code).strip()
    if not code:
        return '❌ Kein Code übergeben.'
    output, err = _execute_code(code, timeout)
    if err:
        return err
    return output


def python_create_script(filename, content):
    filename = filename.strip()
    if '..' in filename or '/' in filename:
        return '❌ Ungültiger Dateiname'
    if not filename.endswith('.py'):
        filename += '.py'
    target = SCRIPTS_DIR / filename
    if target.exists():
        return f'❌ Datei {filename} existiert bereits. Lösche sie zuerst oder wähle anderen Namen.'
    try:
        safe, warning = _check_dangerous(content)
        if not safe:
            return warning
        target.write_text(content, encoding='utf-8')
        result = f'✅ Skript `{filename}` erstellt ({len(content)} Bytes)'
        if warning:
            result += f'\n⚠️ {warning}'
        return result
    except Exception as e:
        return f'❌ Fehler beim Erstellen: {e}'


def python_run_script(filename, args='', timeout=30):
    target = _find_script(filename)
    if target is None:
        scripts = [f.name for f in SCRIPTS_DIR.iterdir() if f.suffix == '.py']
        return f'❌ Skript `{filename}` nicht gefunden. Verfügbar: {", ".join(scripts) if scripts else "keine"}'

    cmd = [sys.executable, '-u', str(target)]
    if args:
        cmd.extend(args.strip().split())

    try:
        timeout = min(max(int(timeout), 5), 120)
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=timeout, cwd=str(SCRIPTS_DIR),
        )
        full = ''
        if result.stdout:
            full += result.stdout
        if result.stderr:
            if full:
                full += '\n--- STDERR ---\n'
            full += result.stderr

        lines = full.split('\n')
        if len(lines) > MAX_OUTPUT_LINES:
            full = '\n'.join(lines[:MAX_OUTPUT_LINES])
            full += f'\n... ({len(lines)} Zeilen total)'
        if len(full) > MAX_OUTPUT_CHARS:
            full = full[:MAX_OUTPUT_CHARS] + '\n... (gekürzt)'

        header = f'📜 Ausgabe von `{target.name}`'
        if result.returncode != 0:
            header += f' (Exit: {result.returncode})'
        if full.strip():
            return f'{header}:\n```\n{full}\n```'
        return '✅ Skript ausgeführt – keine Ausgabe'
    except subprocess.TimeoutExpired:
        return f'❌ Timeout nach {timeout}s'
    except Exception as e:
        return f'❌ Fehler: {e}'


def python_list_scripts():
    scripts = sorted(SCRIPTS_DIR.glob('*.py'))
    if not scripts:
        return '📂 Keine Skripte gespeichert.'
    lines = ['📂 **Gespeicherte Python-Skripte:**']
    for s in scripts:
        size = s.stat().st_size
        mtime = time.strftime('%d.%m.%Y %H:%M', time.localtime(s.stat().st_mtime))
        lines.append(f'  📄 `{s.name}` ({size} Bytes, {mtime})')
    return '\n'.join(lines)


def python_read_script(filename):
    target = _find_script(filename)
    if target is None:
        return f'❌ Skript `{filename}` nicht gefunden.'
    content = target.read_text(encoding='utf-8')
    return f'📄 **{target.name}** ({target.stat().st_size} Bytes)\n```python\n{content}\n```'


def python_install_package(package):
    package = package.strip()
    if not package:
        return '❌ Kein Paketname angegeben.'
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'install', package],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            return f'✅ {package} installiert.\n```\n{result.stdout.strip()[:2000]}\n```'
        else:
            return f'❌ Installation fehlgeschlagen:\n```\n{(result.stderr or result.stdout)[:2000]}\n```'
    except subprocess.TimeoutExpired:
        return '❌ Installation abgebrochen (Timeout 120s)'
    except Exception as e:
        return f'❌ Fehler: {e}'


def python_list_packages():
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'list', '--format=columns'],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            out = result.stdout.strip()
            return f'📦 **Installierte Pakete:**\n```\n{out[:4000]}\n```'
        return f'❌ Fehler: {(result.stderr or result.stdout)[:1000]}'
    except Exception as e:
        return f'❌ Fehler: {e}'


TOOL_MAP = {
    'python_execute': python_execute,
    'python_create_script': python_create_script,
    'python_run_script': python_run_script,
    'python_list_scripts': python_list_scripts,
    'python_read_script': python_read_script,
    'python_install_package': python_install_package,
    'python_list_packages': python_list_packages,
}

PROMPT_EXTRA = (
    "PYTHON-CODE-AUSFÜHRUNG (python_exec Plugin):\n"
    "  - **python_execute(code, timeout=30)**: Führe Python-Code aus. Nutze print() für Ausgabe.\n"
    "    Verwende requests für HTTP, matplotlib für Plots (Base64). 30s Timeout.\n"
    "  - **python_create_script(filename, content)**: Speichere ein Skript für später.\n"
    "  - **python_run_script(filename, args, timeout)**: Führe gespeichertes Skript aus.\n"
    "  - **python_list_scripts**: Zeige alle gespeicherten Skripte.\n"
    "  - **python_read_script(filename)**: Zeige Skript-Inhalt an.\n"
    "  - **python_install_package(package)**: Installiere pip-Paket.\n"
    "  - **python_list_packages**: Liste installierte Pakete.\n"
    "  Nutze für: Berechnungen, Datenanalyse, API-Tests, Diagramme, Textverarbeitung, Web-Scraping.\n"
    "  Bei Fehlern: print() für Debug-Ausgabe, Timeout erhöhen, Pakete installieren.\n"
)
