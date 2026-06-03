
# MYND

MYND ist eine lokal betreibbare, integrationsstarke KI-Assistenz mit Chat-UI. Sie kombiniert ein Flask-Backend, ein Next.js-Frontend und mehrere Integrationen (Nextcloud, Kalender, Tasks, Immich, Home Assistant, OpenWeather u. a.).

Kurz: MYND hilft, lokale Daten (Dokumente, Termine, Fotos, Tasks) per natürlicher Sprache zu durchsuchen und zu verknüpfen.

Weitere technische Details und Architektur findest du in der Entwicklerdokumentation: [docs/technical_documentation.md](docs/technical_documentation.md).

## Inhalt
- **Projekt:** kurzer Überblick und Hauptfunktionalitäten
- **Schnellstart:** lokal entwickeln und testen
- **Produktion:** Docker-Setup
- **Konfiguration:** wichtige Dateien & Umgebungsvariablen
- **APIs & Beispiele:** typische Requests
- **Tests & Beitrag:** wie du mitarbeitest

## Hauptfunktionen
- Unified Chat-API: `POST /api/agent/query`
- Quellen-orientierte Antworten (Fotos, Dateien, Kalender, Tasks, Wetter, Sicherheit)
- Hintergrund-Indexierung (Nextcloud)
- Lokale Persistenz: SQLite (FTS5)
- Konfigurierbare Integrationen über `backend/config/`
- Web-UI (Next.js) zum Konfigurieren und Interagieren

## Schnellstart (lokale Entwicklung)

Voraussetzungen
- Python 3.10+ (empfohlen)
- Node.js 18+ und npm
- Optional: Ollama (für lokale LLM-Hosts)

Repository einrichten

```bash
cd ./
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

Backend starten (Entwicklung)

```bash
source .venv/bin/activate
python run_app.py
```

Standard-URL: `http://127.0.0.1:5001`

Frontend starten

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Frontend: `http://localhost:3000`

Hinweis: In der Dev-Umgebung leitet Next.js ` /api/*`-Anfragen an das Backend weiter.

## Produktion mit Docker

Führe im Projekt-Root aus:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Typische Endpunkte nach Start:
- Frontend: `http://localhost:3001`
- Backend: `http://localhost:5001`

Wichtig: Ollama muss erreichbar sein; auf macOS ist `http://host.docker.internal:11434` ein üblicher Default. Setze `OLLAMA_BASE_URL` passend.

Persistente Pfade
- `data/` (z. B. `knowledge_base.db`)
- `backend/config/`

## Konfiguration

Wichtige Konfigurationsdateien
- `backend/config/ai_config.json` — Modell- und Systemkonfiguration
- `backend/config/nextcloud_config.json` — Nextcloud-Zugangsdaten
- `backend/config/indexing_config.json` — Indexierungsregeln

Wichtige Umgebungsvariablen
- `FLASK_SECRET_KEY` — zwingend für produktiven Betrieb
- `OLLAMA_BASE_URL` — URL zu Ollama
- `OLLAMA_MODEL` — Modellname
- `NEXT_PUBLIC_BACKEND_URL` — URL, die das Frontend für API-Requests nutzt

Optional / Feature-Flags
- `CALENDAR_ENABLED`, `TASKS_AUTO_SYNC_ENABLED`, `TASKS_AUTO_SYNC_INTERVAL_SECONDS`

Sensible Daten
- Versioniere niemals echte Secrets. Nutze `.env` oder ein Secret-Manager.

## API-Beispiele

Unified Chat-Request

```bash
curl -X POST http://127.0.0.1:5001/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Zeig mir Fotos vom letzten Urlaub",
    "username": "alice",
    "language": "de",
    "preferred_source": "auto"
  }'
```

Status-Endpoints

```bash
curl http://127.0.0.1:5001/api/ollama/status
curl http://127.0.0.1:5001/api/knowledge/status
```

Nextcloud Login Flow (Beispiel)

```bash
curl -X POST http://127.0.0.1:5001/api/nextcloud/loginflow/start \
  -H "Content-Type: application/json" \
  -d '{"nextcloud_url":"https://cloud.example.com"}'
```

Weitere Endpunkte und Details: siehe `backend/core/routes` und die Entwicklerdokumentation.

## Tests

Projekt-spezifische Tests sind im Root als Scripts vorhanden. Beispiel:

```bash
source .venv/bin/activate
python test_auth_unit.py
python test_chat_with_todos.py
```

Für CI: Tests in ein `pytest`-Setup überführen und GitHub Actions ergänzen (auf Wunsch erstelle ich ein Template).

## Sicherheit & Datenschutz

- Sensible Konfiguration nicht in Git speichern
- Verwende HTTPS in Produktivumgebungen
- Rollen- und Berechtigungsmodell ist begrenzt — produktive Multi-User-Setups benötigen Anpassungen

## Beitragen

Beiträge sind willkommen. Vorschlag:

1. Issue erstellen oder Diskussion starten
2. Branch vom `main` anlegen
3. Kleinen, gut dokumentierten Pull-Request senden

Siehe auch: [CONTRIBUTING.md] (falls vorhanden)

## Weiterführende Dokumentation
- [docs/technical_documentation.md](docs/technical_documentation.md)
- [docs/IMMICH_INTEGRATION.md](docs/IMMICH_INTEGRATION.md)
- [docs/NEXTCLOUD_AUTH_PLUGIN.md](docs/NEXTCLOUD_AUTH_PLUGIN.md)

## Lizenz

Siehe LICENSE im Repository.

---

README aktualisiert. Wenn du möchtest, kann ich zusätzlich ein kurzes `CONTRIBUTING.md`-Template oder ein GitHub Actions CI-Workflow anlegen.
