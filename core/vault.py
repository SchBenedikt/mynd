import json
import os
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from .config import VAULT_FILE, C

_VAULT_HEADER = b'MYND_VAULT_V1\n'


def _key_file() -> Path:
    configured = os.getenv('MYND_VAULT_KEY_FILE', '').strip()
    if configured:
        return Path(configured).expanduser()
    return Path.home() / '.config' / 'mynd' / 'vault.key'


def _vault_key() -> bytes:
    from_env = os.getenv('MYND_VAULT_KEY', '').strip()
    if from_env:
        key = from_env.encode('ascii')
        Fernet(key)
        return key

    key_file = _key_file()
    key_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(key_file.parent, 0o700)
    except OSError:
        pass
    if not key_file.exists():
        key = Fernet.generate_key()
        fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(key + b'\n')
    key = key_file.read_bytes().strip()
    Fernet(key)
    try:
        os.chmod(key_file, 0o600)
    except OSError:
        pass
    return key


def load_vault(path: Path | None = None, *, migrate: bool = True) -> dict:
    target = Path(path or VAULT_FILE)
    if not target.exists():
        return {}
    raw = target.read_bytes()
    if raw.startswith(_VAULT_HEADER):
        try:
            plaintext = Fernet(_vault_key()).decrypt(raw[len(_VAULT_HEADER):])
        except InvalidToken as exc:
            raise ValueError('Vault decryption failed; check MYND_VAULT_KEY or MYND_VAULT_KEY_FILE') from exc
        data = json.loads(plaintext.decode('utf-8'))
    else:
        data = json.loads(raw.decode('utf-8'))
        if migrate:
            save_vault(data, target)
    if not isinstance(data, dict):
        raise ValueError('Vault content must be a JSON object')
    return data


def save_vault(values: dict, path: Path | None = None) -> None:
    target = Path(path or VAULT_FILE)
    target.parent.mkdir(parents=True, exist_ok=True)
    plaintext = json.dumps(values, indent=2, ensure_ascii=False).encode('utf-8')
    encrypted = _VAULT_HEADER + Fernet(_vault_key()).encrypt(plaintext)
    fd, temporary = tempfile.mkstemp(prefix=f'.{target.name}.', dir=target.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'wb') as handle:
            handle.write(encrypted)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def vault_get(key=''):
    try:
        values = load_vault()
        if not key:
            groups = {}
            for item_key in sorted(values):
                prefix = item_key.split('/')[0]
                groups.setdefault(prefix, []).append(item_key)
            lines = ['Verfügbare Vault-Keys:']
            for group in sorted(groups):
                lines.append(f'  {group}:')
                for item_key in groups[group]:
                    lines.append(f'    {item_key}: ***')
            return '\n'.join(lines)
        return values.get(key, '')
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return '❌ Fehler'


def vault_set(key, value):
    try:
        values = load_vault()
        values[key] = value
        save_vault(values)
        return f'✅ `{key}` gespeichert'
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return f'❌ Vault write failed: {exc}'


def vault_delete(key):
    try:
        values = load_vault()
        if key not in values:
            return f'❌ `{key}` nicht gefunden'
        del values[key]
        save_vault(values)
        return f'🗑 `{key}` gelöscht'
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return f'❌ Vault delete failed: {exc}'


def vault_list(group=''):
    try:
        values = load_vault()
        if not values:
            return '(leer)'
        groups = {}
        for item_key in sorted(values):
            if '/' in item_key:
                item_group, _, rest = item_key.partition('/')
                groups.setdefault(item_group, {})[rest or item_key] = values[item_key]
            else:
                groups.setdefault('_all', {})[item_key] = values[item_key]
        if group:
            entries = groups.get(group, {})
            return '\n'.join(f'  {key}: ***' for key in entries) if entries else f"(Gruppe '{group}' leer)"
        lines = []
        for item_group in sorted(groups):
            lines.append(f'\n  {C.CYAN}{item_group}{C.RESET}')
            for key in sorted(groups[item_group]):
                lines.append(f'    {key}: ***')
        return '\n'.join(lines) if lines else '(leer)'
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return '❌ Fehler'


def _vault_get(key):
    value = vault_get(key)
    return '' if value == '❌ Fehler' else value
