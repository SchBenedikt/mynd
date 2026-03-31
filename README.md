# MYND

MYND ist eine lokale, integrationsstarke KI-Assistenz mit Chat-UI. Das System kombiniert ein Flask-Backend, eine Next.js-Frontend-Anwendung und mehrere Datenquellen wie Nextcloud, Kalender, Tasks, Immich-Fotos sowie externe APIs (z. B. OpenWeather, NINA, Home Assistant, Uptime Kuma).

Die ausführliche Entwicklerdokumentation befindet sich in [docs/technical_documentation.md](docs/technical_documentation.md).

## Projektüberblick

### Was das Projekt macht
MYND beantwortet natürlichsprachige Anfragen und zieht dafür je nach Intention Informationen aus:
- lokaler Wissensbasis (dokumentenbasiert, inkl. Chunking und Suche)
- Nextcloud (Dateien, Aktivitäten, Benachrichtigungen, Tasks)
- Kalenderdaten
- Immich-Fotobibliothek
- Zusatzintegrationen (Home Assistant, Uptime Kuma, OpenWeather, NINA, Autobahn, Dashboard Deutschland, Deutschland Atlas)

### Hauptzweck und Use Cases
- Persönlicher Assistent für Dokumente, Termine und Aufgaben
- Foto-Suche per natürlicher Sprache
- Lokale Sicherheits-/Wetterübersicht mit Standortbezug
- Einheitliches Interface für mehrere APIs

### Zielgruppen
- Entwickler, die lokale KI-Assistenz erweitern möchten
- Power User mit selbst gehosteter Infrastruktur (Nextcloud, Immich, Home Assistant, Uptime Kuma)

## Kernfunktionen

- Unified Chat-Endpunkt: `POST /api/agent/query`
- Intent-basierte Quellenauswahl (Fotos, Dateien, Kalender, Tasks, Sicherheit, Wetter)
- Hintergrund-Indexierung von Dokumenten aus Nextcloud
- SQLite-basierte Wissens- und Task-Persistenz
- API Registry für konfigurierbare Integrationen
- Settings-UI für Konfiguration und Verbindungschecks

## Architektur auf einen Blick

- Backend: Flask-App in `backend/core/app.py`
- Frontend: Next.js in `frontend/`
- Persistenz: `knowledge_base.db` (SQLite, FTS5, WAL)
- Konfiguration: JSON-Dateien unter `backend/config/`
- Integrationen: `backend/features/integration/`

## Setup und Installation

### Voraussetzungen
- Python 3.10+ (empfohlen)
- Node.js 18+ und npm
- Ollama (laufend erreichbar)

### 1. Repository vorbereiten
```bash
cd /Users/vinzenz.schaechner/MYND/mynd
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### 2. Backend starten
```bash
source .venv/bin/activate
python run_app.py
```

Backend läuft standardmäßig auf `http://127.0.0.1:5001`.

### 3. Frontend starten
```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Frontend läuft auf `http://localhost:3000`.

Hinweis: In der Dev-Konfiguration werden `/api/*`-Requests aus Next.js per Rewrite auf das Flask-Backend weitergeleitet.

## Konfiguration

### Wichtige Dateien
- `backend/config/ai_config.json`: Modell-/Systemkonfiguration, Immich-Defaults
- `backend/config/nextcloud_config.json`: gespeicherte Nextcloud-Credentials
- `backend/config/calendar_config.json`: Standardkalender
- `backend/config/indexing_config.json`: Nextcloud-Indexing-Konfiguration

### Relevante Umgebungsvariablen
- `FLASK_SECRET_KEY`
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`
- `CALENDAR_ENABLED`
- `TASKS_AUTO_SYNC_ENABLED`
- `TASKS_AUTO_SYNC_INTERVAL_SECONDS`
- `TASKS_AUTO_SYNC_LIST_NAME`
- optional/fallback: `NEXTCLOUD_URL`, `NEXTCLOUD_USERNAME`, `NEXTCLOUD_PASSWORD`
- Frontend: `NEXT_PUBLIC_BACKEND_URL`

## Nutzung

### Chat-Anfrage (Unified)
```bash
curl -X POST http://127.0.0.1:5001/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Zeig mir Fotos vom letzten Urlaub",
    "username": "vinzenz",
    "language": "de",
    "preferred_source": "auto"
  }'
```

### API-Status prüfen
```bash
curl http://127.0.0.1:5001/api/ollama/status
curl http://127.0.0.1:5001/api/knowledge/status
```

### Nextcloud Login Flow starten
```bash
curl -X POST http://127.0.0.1:5001/api/nextcloud/loginflow/start \
  -H "Content-Type: application/json" \
  -d '{"nextcloud_url":"https://cloud.example.com"}'
```

## Testing

Im Projekt sind primär scriptbasierte Tests vorhanden (`test_*.py`).

Beispiele:
```bash
source .venv/bin/activate
python test_auth_unit.py
python test_additional_apis.py
python test_chat_with_todos.py
```

## Sicherheitshinweise

- Aktuelle Konfigurationsdateien im Repository enthalten sensible Werte. Für produktive Nutzung:
  - Secrets rotieren
  - keine echten Tokens/Passwörter versionieren
  - Secret-Management nutzen
- Session- und API-Secrets ausschließlich über sichere Kanäle bereitstellen.

## Einschränkungen (Kurzfassung)

- Kein feingranulares Multi-User-/RBAC-Modell im Backend
- Große `backend/core/app.py` als monolithischer Einstiegspunkt
- Teilweise Legacy-/Fallback-Pfade (z. B. parallel bestehende Auth-Flows)
- Abhängigkeit von externen Diensten (Ollama, Nextcloud, Immich, APIs)

## Weitere Informationen

- Detaildokumentation: [docs/technical_documentation.md](docs/technical_documentation.md)
- Zusatzdokus:
  - [docs/IMMICH_INTEGRATION.md](docs/IMMICH_INTEGRATION.md)
  - [docs/NEXTCLOUD_AUTH_PLUGIN.md](docs/NEXTCLOUD_AUTH_PLUGIN.md)
  - [docs/CALENDAR_IMPROVEMENTS.md](docs/CALENDAR_IMPROVEMENTS.md)
