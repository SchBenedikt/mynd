# Quick Start - Security-Hardened MYND Backend

**Timeline:** This is your deployment guide for the comprehensive security review.  
**Status:** All code is production-ready and tested.

---

## 🚨 CRITICAL: Immediate Actions (Do First!)

### 1. Stop Credential Leakage (5 minutes)

**BEFORE Anything Else:**

```bash
# 1. Rotate ALL exposed credentials
# The following are currently exposed in ai_config.json:
# Quick Start — MYND (aktualisiert)

Kurz: Diese Anleitung zeigt, wie du MYND lokal startest und pro Nextcloud‑Nutzer eine eigene Indexierung aktivierst.

Wichtiges Prinzip: Nextcloud‑Accounts werden pro Benutzer gespeichert. Jeder Benutzer kann seine eigene Nextcloud‑Instanz/Anmeldedaten hinterlegen; die Index‑Chunks werden mit dem Feld `owner` in der Datenbank markiert und bei Suchen standardmäßig nach diesem Besitzer gefiltert.

## 1) Voraussetzungen

- Python 3.10+ (virtuelle Umgebung empfohlen)
- SQLite (wird zur lokalen Index‑Speicherung genutzt)
- Optional: Ollama für Embeddings/LLM

## 2) Einrichtung (minimal)

1. Virtuelle Umgebung anlegen und aktivieren:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

2. Environment‑Variablen (`.env`) anlegen (NICHT in Git):

```bash
# Beispiel (.env)
FLASK_SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
OLLAMA_BASE_URL=http://127.0.0.1:11434
ALLOW_PRIVATE_NETWORK_TARGETS=false
```

3. Sicherstellen, dass `backend/config` in `.gitignore` steht:

```bash
echo "backend/config/*.json" >> .gitignore
```

## 3) Starten der Anwendung

Im Projekt‑Root:

```bash
source .venv/bin/activate
export FLASK_APP=backend/core/app.py
flask run --host=0.0.0.0 --port=5000
```

Alternativ (Debug/Dev):

```bash
python backend/core/app.py  # falls die Datei als Flask-App runner konfiguriert ist
```

## 4) Pro‑User Nextcloud einrichten (kurz)

1. Im Frontend oder per API starte den Nextcloud Login Flow oder Direct Login: `/api/nextcloud/loginflow/start` bzw. `/api/nextcloud/login`.
2. Nach erfolgreicher Auth speichert MYND die Account‑Daten pro Benutzer in `backend/config/nextcloud_accounts.json`.
3. Indexierung wird angestoßen und die resultierenden Chunks bekommen das Metadatum `owner = <nextcloud-username>`.

Hinweis: Die globale Datei `backend/config/nextcloud_config.json` wird weiterhin für Kompatibilität aktualisiert, die eigentlichen Nutzer‑Accounts werden aber in `nextcloud_accounts.json` abgelegt.

## 5) Suche und Kontext (wie Nutzer ihre eigenen Daten sehen)

- Suchen werden automatisch nach dem aktuell konfigurierten Nextcloud‑Benutzer gefiltert (SQL JSON‑Filter `json_extract(metadata, '$.owner')`).
- Entwickler können in den Erweiterungen die Suche explizit für einen Nutzer aufrufen: `knowledge_base.search_knowledge_for_user(query, k=..., owner='alice')`.

## 6) Nächste Schritte / Sicherheit

- Rotieren und sichern aller API‑Schlüssel (falls bereits in Repos oder Logs vorhanden).
- `.env` und `backend/config/*.json` dürfen niemals in VCS eingecheckt werden.
- Für Produktionsbetrieb: setze HTTPS, sichere Sessions, und nutze OS‑level Dateiberechtigungen für Config‑Dateien (0o600).

## Hilfe / Troubleshooting

- Logs: `tail -f ./mynd.log` oder die Flask‑Konsolenausgabe
- DB‑Check: `sqlite3 knowledge_base.db "SELECT COUNT(*) FROM documents;"`
- Wenn Indizierung nicht startet: Prüfe `backend/config/nextcloud_accounts.json` und `backend/config/indexing_config.json`.

---
Wenn du möchtest, übernehme ich noch das Migrationsskript, damit `documents` eine eigene `owner`-Spalte bekommt (empfohlen), oder passe ich weitere APIs an, damit Nutzer sich per Session eindeutig identifizieren können.
**Q: How long does deployment take?**  
A: Phase 1 (credentials): ~1 hour  
Phase 2 (code update): ~40 hours (should span a sprint)  
Phase 3 (hardening): ~30 hours

**Q: What if something breaks?**  
A: Roll back is easy - just revert to old client classes. Security tests will catch issues in staging.

---

**Ready? Start with Section "🚨 CRITICAL" above!**
