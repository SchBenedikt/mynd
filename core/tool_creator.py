import ast
import json
import os
import re
import tempfile
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent.parent / 'data' / 'plugins'
TOOL_NAME_RE = re.compile(r'^[A-Za-z0-9_-]{1,64}$')

CORE_TOOL_NAMES = {
    'execute_bash', 'execute_python', 'execute_ssh', 'search_documents',
    'web_search', 'fetch_news', 'read_local_file', 'write_local_file',
    'think', 'prompt_user', 'vault_get', 'vault_set', 'vault_delete',
    'vault_list', 'http_request', 'image_search',
    'memory_get', 'memory_set', 'memory_delete',
    'delegate', 'create_plan', 'agent_browser',
    'reflect_on_failure', 'learn_skill', 'recall_skills',
    'list_skills', 'delete_skill',
}

SYSTEM_PLUGINS = {
    'system', 'browser', 'email', 'immich', 'nextcloud', 'homeassistant',
    'affine', 'truenas', 'discord', 'spotify', 'composio', 'python_exec',
}

FORBIDDEN_IMPORTS = frozenset({
    'ctypes', '_ctypes', 'socket', 'multiprocessing', 'subprocess',
    '__builtins__', 'builtins',
})

_DANGEROUS_FUNCS = frozenset({
    'exec', 'eval', '__import__', 'compile', 'open', 'breakpoint', 'help', 'input',
})

DANGEROUS_CALLS = frozenset(_DANGEROUS_FUNCS - {'open'})
DANGEROUS_GETATTR_TARGETS = frozenset(_DANGEROUS_FUNCS | {'__builtins__'})

DANGEROUS_ATTR_CALLS = frozenset(
    {f'builtins.{f}' for f in _DANGEROUS_FUNCS}
    | {f'__builtins__.{f}' for f in _DANGEROUS_FUNCS}
    | {'os.system', 'os.popen', 'os.fork', 'os.exec'},
)

DANGEROUS_PATTERNS = [
    'os.system', 'os.popen', 'os.fork', 'os.exec',
    'shutil.rmtree',
    '__import__', 'eval(', 'exec(',
    'base64.b64decode',
    'compile(', 'breakpoint(', 'help(', 'input(',
]

MAX_CODE_LENGTH = 50000


def _get_call_name(node):
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        parts = []
        cur = node.func
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return '.'.join(reversed(parts))
    return None


def _normalize_code(code):
    return re.sub(r'(\w+)\s+\(', r'\1(', code)


def _has_write_mode(mode_node):
    if isinstance(mode_node, ast.Constant) and isinstance(mode_node.value, str):
        return bool(set(mode_node.value) & {'w', 'a', 'x', '+'})
    return False


class _SecurityVisitor(ast.NodeVisitor):
    def __init__(self):
        self.errors = []

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name in FORBIDDEN_IMPORTS:
                self.errors.append(f'\u274c Verbotener Import: {alias.name}')
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module in FORBIDDEN_IMPORTS:
            self.errors.append(f'\u274c Verbotener Import: {node.module}')
        self.generic_visit(node)

    def visit_Call(self, node):
        func_name = _get_call_name(node)
        if func_name:
            if func_name in DANGEROUS_CALLS or func_name in DANGEROUS_ATTR_CALLS:
                self.errors.append(f'\u274c Verbotener Aufruf: {func_name}()')

            if func_name == 'getattr' and len(node.args) >= 2:
                second = node.args[1]
                if isinstance(second, ast.Constant) and isinstance(second.value, str):
                    if second.value in DANGEROUS_GETATTR_TARGETS:
                        self.errors.append(
                            f'\u274c Verbotener getattr-Zugriff: getattr(..., {second.value!r})'
                        )

            if func_name == 'open':
                has_write = False
                if len(node.args) >= 2:
                    has_write = _has_write_mode(node.args[1])
                if not has_write:
                    for kw in node.keywords:
                        if kw.arg == 'mode' and _has_write_mode(kw.value):
                            has_write = True
                            break
                if has_write:
                    self.errors.append('\u274c open() mit Schreibmodus ist nicht erlaubt')

        self.generic_visit(node)

    def visit_Subscript(self, node):
        if (
            isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == 'sys'
            and node.value.attr == 'modules'
        ):
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                if node.slice.value in FORBIDDEN_IMPORTS | DANGEROUS_GETATTR_TARGETS:
                    self.errors.append(
                        f'\u274c Verbotener sys.modules-Zugriff: {node.slice.value!r}'
                    )

        if isinstance(node.value, ast.Name) and node.value.id == '__builtins__':
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                self.errors.append(
                    f'\u274c Verbotener __builtins__-Zugriff: __builtins__[{node.slice.value!r}]'
                )

        self.generic_visit(node)

    def visit_Name(self, node):
        if node.id == '__builtins__':
            self.errors.append('\u274c Zugriff auf __builtins__ ist nicht erlaubt')
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if node.attr == '__builtins__':
            self.errors.append('\u274c Zugriff auf __builtins__-Attribut ist nicht erlaubt')
        self.generic_visit(node)


def create_tool(name, description, parameters, code):
    error = _validate(name, description, parameters, code)
    if error:
        return error
    plugin_code = _generate_plugin(name, description, parameters, code)
    plugin_path = PLUGIN_DIR / f'{name}.py'
    if plugin_path.exists():
        return f'\u274c Tool {name!r} existiert bereits.'
    PLUGIN_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp_path_str = tempfile.mkstemp(dir=str(PLUGIN_DIR), suffix='.py')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(plugin_code)
        os.replace(tmp_path_str, str(plugin_path))
    except Exception:
        try:
            os.unlink(tmp_path_str)
        except Exception:
            pass
        raise
    try:
        core_result = _verify_and_load(plugin_path, name)
        if core_result:
            return core_result
    except Exception as e:
        plugin_path.unlink()
        return f'\u274c Tool erstellt, aber Laden fehlgeschlagen: {e}'
    try:
        from app.agent_loop import refresh_tools as _refresh
        _refresh()
    except Exception:
        pass
    return f'\u2705 Tool "{name}" erstellt und geladen.'


def delete_tool(name):
    plugin_path = PLUGIN_DIR / f'{name}.py'
    if not plugin_path.exists():
        return f'\u274c Tool {name!r} nicht gefunden.'
    if name in SYSTEM_PLUGINS:
        return f'\u274c {name!r} ist ein System-Plugin und kann nicht gel\u00f6scht werden.'
    plugin_path.unlink()
    try:
        from core.plugin_base import reload_plugins
        reload_plugins()
    except Exception:
        pass
    try:
        from app.agent_loop import refresh_tools as _refresh
        _refresh()
    except Exception:
        pass
    return f'\U0001f5d1 Tool "{name}" gel\u00f6scht.'


def list_created_tools():
    created = []
    for f in sorted(PLUGIN_DIR.glob('*.py')):
        if f.stem in SYSTEM_PLUGINS or f.stem in CORE_TOOL_NAMES:
            continue
        if f.stem == '__init__' or f.stem.startswith('_'):
            continue
        try:
            content = f.read_text()
            if 'TOOL_SCHEMA' in content or 'TOOLS' in content:
                created.append(f.stem)
        except Exception:
            pass
    return created


def _validate(name, description, parameters, code):
    if not isinstance(name, str) or not TOOL_NAME_RE.match(name):
        return '\u274c Ung\u00fcltiger Tool-Name. Erlaubt: A-Z, a-z, 0-9, _, - (max 64 Zeichen)'
    if name in CORE_TOOL_NAMES:
        return f'\u274c {name!r} ist ein reservierter Core-Tool-Name.'
    if not isinstance(description, str) or len(description) < 5:
        return '\u274c Beschreibung muss mindestens 5 Zeichen lang sein.'
    if not isinstance(parameters, dict):
        return '\u274c Parameter m\u00fcssen ein JSON-Objekt sein.'
    for pname, pval in parameters.items():
        if not isinstance(pname, str) or not TOOL_NAME_RE.match(pname):
            return f'\u274c Ung\u00fcltiger Parameter-Name: {pname!r}'
        if not isinstance(pval, dict):
            return f'\u274c Parameter {pname!r} muss ein Objekt sein.'
        if 'type' not in pval:
            return f'\u274c Parameter {pname!r} ben\u00f6tigt ein "type"-Feld.'
    if not isinstance(code, str) or len(code.strip()) < 5:
        return '\u274c Code muss mindestens 5 Zeichen lang sein.'
    if len(code) > MAX_CODE_LENGTH:
        return f'\u274c Code \u00fcberschreitet maximale L\u00e4nge von {MAX_CODE_LENGTH} Zeichen.'
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f'\u274c Syntaxfehler: {e}'
    visitor = _SecurityVisitor()
    visitor.visit(tree)
    if visitor.errors:
        return visitor.errors[0]
    normalized = _normalize_code(code)
    for pattern in DANGEROUS_PATTERNS:
        if pattern in normalized:
            return f'\u274c Verd\u00e4chtiges Pattern gefunden: {pattern!r}'
    return None


def _verify_and_load(plugin_path, name):
    try:
        from core.plugin_base import get_all_tools, get_registry, reload_plugins
        reload_plugins()
        registry = get_registry()
        if name not in registry:
            plugin_path.unlink()
            return f'\u274c Tool {name!r} wurde nicht geladen. \u00dcberpr\u00fcfe die Code-Syntax.'
        tools, _ = get_all_tools()
        tool_names = [t.get('function', {}).get('name', '') for t in tools]
        if name not in tool_names:
            plugin_path.unlink()
            return f'\u274c Tool {name!r} nicht in Tool-Liste. \u00dcberpr\u00fcfe TOOLS-Definition.'
    except Exception as e:
        plugin_path.unlink()
        return f'\u274c Validierung fehlgeschlagen: {e}'
    return None


def _generate_plugin(name, description, parameters, code):
    param_names = sorted(parameters.keys()) if parameters else []
    func_params = ', '.join(param_names)
    tool_entry = {
        'name': name,
        'description': description[:500],
        'parameters': {
            p: {
                'type': params.get('type', 'string'),
                'description': params.get('description', ''),
            }
            for p, params in parameters.items()
        },
    }
    return (
        f'"""Auto-generated tool: {name}"""\n'
        f'TOOL_SCHEMA = True\n'
        f'PLUGIN_NAME = {json.dumps(name)}\n'
        f'\n'
        f'def {name}({func_params}):\n'
        f'{_indent(code, 1)}\n'
        f'\n'
        f'TOOLS = [\n'
        f'    {json.dumps(tool_entry, indent=2)},\n'
        f']\n'
        f'\n'
        f'TOOL_MAP = {{\n'
        f'    {json.dumps(name)}: {name},\n'
        f'}}\n'
    )


def _indent(code, level=1):
    lines = code.split('\n')
    indented = []
    for line in lines:
        if line.strip():
            indented.append('    ' * level + line)
        else:
            indented.append('')
    return '\n'.join(indented)
