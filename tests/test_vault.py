import json
import stat

from cryptography.fernet import Fernet

from core.vault import load_vault, save_vault


def test_vault_is_encrypted_and_round_trips(monkeypatch, tmp_path):
    vault = tmp_path / "vault.json"
    monkeypatch.setenv("MYND_VAULT_KEY", Fernet.generate_key().decode("ascii"))

    save_vault({"service/token": "top-secret"}, vault)

    assert b"top-secret" not in vault.read_bytes()
    assert load_vault(vault) == {"service/token": "top-secret"}
    assert stat.S_IMODE(vault.stat().st_mode) == 0o600


def test_plaintext_vault_is_migrated(monkeypatch, tmp_path):
    vault = tmp_path / "vault.json"
    vault.write_text(json.dumps({"legacy/password": "secret"}))
    monkeypatch.setenv("MYND_VAULT_KEY", Fernet.generate_key().decode("ascii"))

    assert load_vault(vault) == {"legacy/password": "secret"}
    assert b"secret" not in vault.read_bytes()
