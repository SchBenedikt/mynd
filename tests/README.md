# Tests

Test-Dateien für das MYND-Backend.

## Ausführung

```bash
cd tests
python -m pytest . -v

# Einzelne Tests
python -m pytest test_auth_unit.py -v
python -m pytest test_todos.py test_chat_with_todos.py -v
```

## Test-Kategorien

| Datei | Beschreibung |
|-------|-------------|
| `test_auth_unit.py` | Unit-Tests für Authentifizierung |
| `test_auth_plugin.py` | Integrationstests Auth-Plugin |
| `test_todos.py` | Aufgaben/Todos-Manager |
| `test_chat_with_todos.py` | Chat mit Todo-Kontext |
| `test_init_tasks.py` | Task-Initialisierung |
| `test_immich_direct.py` | Immich-Direktverbindung |
| `test_immich_features.py` | Immich-Feature-Tests |
| `test_nextcloud_apis.py` | Nextcloud-API-Tests |
| `test_agent_photo_search.py` | Foto-Suche via Agent |
| `test_secrets_management.py` | Secrets-Management |
| `test_security_hardening.py` | Security-Härtung |
| `fix_database.py` | DB-Reparatur-Skript |
