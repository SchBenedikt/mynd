# MYND - Technische Dokumentation

Dieses Dokument beschreibt den aktuellen Ist-Zustand des Repositories auf Codebasis. Es enthält keine absichtlich erfundenen Features.

## 1. Projektüberblick

### 1.1 Was das Projekt macht
MYND ist eine lokale KI-Assistenzplattform mit folgenden Schwerpunkten:
- Chat-Interaktion über ein Next.js-Frontend
- zentraler Flask-Backend-Endpunkt zur Intent-Erkennung und Query-Routing
- RAG-ähnliche Wissenssuche über lokal indizierte Dokumente
- Integration externer und selbst gehosteter Dienste (Nextcloud, Immich, Home Assistant, Uptime Kuma, Wetter-/Warn-APIs)

### 1.2 Hauptzweck und Use Cases
- Dokumentenbasierte Antworten aus persönlicher Wissensbasis
- Foto-Suche aus Immich per natürlicher Sprache
- Aufgaben- und Kalenderabfragen
- Lokale Lageeinschätzung (NINA + OpenWeather)
- Betriebs-/Monitoring-Abfragen (Uptime Kuma, Home Assistant)

### 1.3 Key Features
- Unified Agent Query (`/api/agent/query`) mit Intent-Logik
- API Registry mit konfigurierbaren Integrationen
- Nextcloud Login Flow v2 und Direct Login
- Background Indexing mit Progress-Tracking
- SQLite-Datenhaltung mit FTS5 und WAL
- UI-Konfigurationsendpunkte für System-/Runtime-/Profileinstellungen

### 1.4 Zielnutzer
- Entwickler, die lokale KI-Anwendungen erweitern
- technisch fortgeschrittene Anwender mit Self-Hosted-Stack

---

## 2. Architekturüberblick

### 2.1 Systemstruktur
- Frontend: Next.js App in `frontend/`
- Backend: Flask in `backend/core/app.py`
- Persistenz: SQLite (`knowledge_base.db`) über `backend/core/database.py`
- Integrationen: API-Clients in `backend/features/integration/`
- Dokumentenverarbeitung: `backend/features/documents/parser.py`
- Suche: `backend/features/knowledge/search.py`

### 2.2 Hauptkomponenten
- `OllamaClient`: Modellaufrufe und Verbindungscheck
- `KnowledgeBase`: Laden, Chunking, Suche, Quellenverwaltung
- `TaskManager`: Nextcloud-Task-Anbindung, DB-Sync, Caching
- `IndexingManager`: asynchrone Nextcloud-Dokumentindexierung
- `APIRegistry`: zentrale Verwaltung von API-Typen, Konfigs, Health

### 2.3 Interaktion der Komponenten
1. Frontend sendet API-Calls über Rewrite (`/api/*` -> Flask).
2. Flask evaluiert Anfrage (Intent/Regeln/Shortcuts).
3. Je nach Intent werden Kontextquellen abgefragt (Fotos, Dateien, Kalender, Tasks, Security/Weather).
4. Antwort:
- direkt (z. B. reine Wetter-/Security-/Task- oder Foto-Shortcuts)
- oder über Ollama mit Systemkontext.

### 2.4 Datenfluss (vereinfacht)
1. Nextcloud/Dateiquellen -> `DocumentParser` -> Chunks.
2. Chunks -> SQLite (`documents`, `chunks`, optional `embeddings`, `chunks_fts`).
3. Query -> FTS-Suche + heuristische Kontextzusammenstellung.
4. Kontext + Prompt -> Ollama -> finale Antwort.

---

## 3. Setup und Installation

### 3.1 Anforderungen
- Python 3.10+ empfohlen
- Node.js 18+ und npm
- laufender Ollama-Dienst
- optional: Nextcloud, Immich, Home Assistant, Uptime Kuma

### 3.2 Backend Installation
```bash
cd /Users/vinzenz.schaechner/MYND/mynd
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### 3.3 Backend Start
```bash
source .venv/bin/activate
python run_app.py
```

Backend-Port: `5001`.

### 3.4 Frontend Installation und Start
```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Frontend-Port: `3000`.

### 3.5 Environment Variablen
Backend (relevant im Code):
- `FLASK_SECRET_KEY`
- `OLLAMA_BASE_URL` (Default: `http://127.0.0.1:11434`)
- `OLLAMA_MODEL` (Default: `gemma3:latest`)
- `CALENDAR_ENABLED`
- `TASKS_AUTO_SYNC_ENABLED`
- `TASKS_AUTO_SYNC_INTERVAL_SECONDS`
- `TASKS_AUTO_SYNC_LIST_NAME`
- optional fallback: `NEXTCLOUD_URL`, `NEXTCLOUD_USERNAME`, `NEXTCLOUD_PASSWORD`

Frontend:
- `NEXT_PUBLIC_BACKEND_URL` (in `.env.local.example`)

### 3.6 Build/Run
Frontend:
```bash
npm run build
npm run start
```
Backend ist ein klassischer Flask-Run über `run_app.py` (kein separates Build-Artefakt).

---

## 4. Usage

### 4.1 Basisworkflow
1. Backend starten
2. Frontend starten
3. Integrationen in Settings konfigurieren
4. Optional: Indexing starten
5. Chat über `/api/agent/query`

### 4.2 Beispiel Agent Query
```bash
curl -X POST http://127.0.0.1:5001/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Welche Aufgaben habe ich diese Woche?",
    "username": "vinzenz",
    "language": "de",
    "preferred_source": "auto"
  }'
```

### 4.3 Häufige Workflows
- Nextcloud verbinden: `/api/nextcloud/loginflow/start` -> `/api/nextcloud/loginflow/poll`
- Indexing starten: `/api/indexing/start` und Fortschritt über `/api/indexing/progress`
- Immich testen: `/api/immich/test`
- API-Health prüfen: `/api/registry/health`

---

## 5. Code-Struktur

### 5.1 Wichtige Verzeichnisse
- `backend/core/`: App-Entry, DB-Layer, zentrale Laufzeitlogik
- `backend/features/`: Featuremodule (Integration, Kalender, Knowledge, Tasks, Training)
- `backend/config/`: persistierte JSON-Konfiguration
- `frontend/app/`: Next.js App Router Seiten
- `frontend/components/`: UI-Komponenten
- `tests/` und `test_*.py`: scriptbasierte Tests/Utilities

### 5.2 Schlüsseldateien
- `run_app.py`: Python-Startskript
- `backend/core/app.py`: zentrale Flask-App mit allen Routen
- `backend/core/database.py`: SQLite-Schema + Zugriffsfunktionen
- `backend/features/integration/api_registry.py`: API-Typregistrierung, Config- und Health-Management
- `backend/features/documents/parser.py`: Multi-Format-Dokumentparser
- `backend/features/knowledge/search.py`: FTS-basierte Suche
- `frontend/app/page.js`: Chat-UI
- `frontend/app/settings/page.js`: Integrations-/Systemkonfiguration

### 5.3 Wichtige Klassen/Funktionen
- `KnowledgeBase`
- `TaskManager`
- `IndexingManager`
- `APIRegistry` / `APIClient`
- `detect_query_intent()`
- `agent_query()`

---

## 6. API-Dokumentation

Hinweis: Die API ist in Domänen gegliedert. Responses folgen häufig einem Schema mit `success`, `error`, `status` und fachlichen Datenfeldern.

### 6.1 Indexing

| Name | Methode & Pfad | Parameter | Rückgabe |
|---|---|---|---|
| Indexing starten | `POST /api/indexing/start` | body: `nextcloud_config` optional | Startstatus oder Fehler |
| Indexing stoppen | `POST /api/indexing/stop` | - | Stopstatus |
| Indexing Fortschritt | `GET /api/indexing/progress` | - | Progress-Objekt |
| Indexing Konfig lesen/schreiben | `GET/POST /api/indexing/config` | body (POST): `url`, `username`, `password`, `path` | Konfig oder Save-Status |

### 6.2 Nextcloud Auth und Verbindung

| Name | Methode & Pfad | Parameter | Rückgabe |
|---|---|---|---|
| OAuth2 autorisieren | `POST /api/nextcloud/oauth/authorize` | body: `nextcloud_url`, `client_id`, `client_secret` | `authorization_url`, `state` |
| OAuth2 Callback | `GET /api/nextcloud/oauth/callback` | query: `code`, `state` | Verbindungsstatus |
| OAuth2 Konfig lesen | `GET /api/nextcloud/oauth/config` | - | sichere Konfig oder `configured=false` |
| Login Flow starten | `POST /api/nextcloud/loginflow/start` | body: `nextcloud_url` | `login_url` |
| Login Flow pollen | `GET /api/nextcloud/loginflow/poll` | - | `pending`/`connected` |
| Direct Login | `POST /api/nextcloud/login` | body: `nextcloud_url`, `username`, `password` | Loginstatus |
| Nextcloud Konfig lesen | `GET /api/nextcloud/config` | - | sichere Konfig |
| Nextcloud trennen | `POST /api/nextcloud/disconnect` | - | Entfernte Dateien/Status |

### 6.3 Knowledge und Training

| Name | Methode & Pfad | Parameter | Rückgabe |
|---|---|---|---|
| Quellen | `GET /api/knowledge/sources` | - | Quellenliste + Chunkanzahl |
| Status | `GET /api/knowledge/status` | - | Statistik/Verfügbarkeit |
| Graph Data | `GET /api/knowledge/graph-data` | - | Chunks + Sources |
| Migration | `POST /api/knowledge/migrate` | - | Migrationsstatistik |
| Embeddings updaten | `POST /api/knowledge/update-embeddings` | - | Success/Error |
| Knowledge neu laden | `POST /api/knowledge/reload` | - | Reload-Quelle + Chunks |
| Trainingsstatistik | `GET /api/training/stats` | - | Trainingsmetriken |

### 6.4 Kalender

| Name | Methode & Pfad | Parameter | Rückgabe |
|---|---|---|---|
| Event erstellen (NLP) | `POST /api/calendar/create` | body: `message` | direktes Ergebnis oder `requires_input` |
| Event mit Details erstellen | `POST /api/calendar/create-with-details` | body: `title`, `start_time`, optional `end_time`, `calendar_name`, `location`, `description` | Erstellungsresultat |
| Kalenderliste | `GET /api/calendar/calendars` | - | `calendars`, `count` |
| Kalender-Konfig | `GET/POST /api/calendar/config` | body (POST): `default_calendar_name` | Konfig/Save-Status |
| Kalender-Debug | `GET /api/calendar/debug/calendars` | - | Rohdaten/Resource-Typen |
| Kalenderstatus | `GET /api/calendar/status` | - | Verbindungs- und Tagesinfos |
| Heute | `GET /api/calendar/today` | - | Tagesevents |
| Morgen | `GET /api/calendar/tomorrow` | - | Events |
| Diese Woche | `GET /api/calendar/week` | - | Events |
| Nächste Woche | `GET /api/calendar/next-week` | - | Events |
| Wochentag | `GET /api/calendar/day/<day_name>` | path: `day_name` | Events |

### 6.5 Tasks

| Name | Methode & Pfad | Parameter | Rückgabe |
|---|---|---|---|
| Initialisieren | `POST /api/tasks/init` | - | enabled/message |
| Liste | `GET /api/tasks/list` | - | `tasks`, `count` |
| Erstellen | `POST /api/tasks/create` | body: `title` (pflicht), optional `description`, `due_date`, `priority`, `list_name` | Status |
| Abschließen | `POST /api/tasks/complete/<task_uid>` | path: `task_uid`, optional body `list_name` | Status |
| Tasks Status | `GET /api/tasks/status` | - | Integration + Auto-Sync |
| Sync starten | `POST /api/tasks/sync` | body: optional `list_name`, `batch_size` | Syncstatus |
| Sync Status | `GET /api/tasks/sync-status` | - | Ladevorgang |
| DB Stats | `GET /api/tasks/db-stats` | - | Task-DB-Metriken |

### 6.6 AI/Ollama

| Name | Methode & Pfad | Parameter | Rückgabe |
|---|---|---|---|
| Ollama Status | `GET /api/ollama/status` | - | connected/base_url/model |
| Ollama Modelle | `GET /api/ollama/models` | - | Modellliste |
| AI Konfig | `GET/POST /api/ai/config` | body (POST): `base_url`, `model` | Konfig + Verbindungsstatus |
| AI Test | `POST /api/ai/test` | body: optional `prompt` | Laufzeit + Antwort |

### 6.7 Immich

| Name | Methode & Pfad | Parameter | Rückgabe |
|---|---|---|---|
| Connection Test | `POST /api/immich/test` | body: optional `username` | success/message/error |
| Foto-Suche | `POST /api/immich/search` | body: `query`, optional `username`, `limit` | Treffer inkl. Proxy-Thumbnail |
| Personen | `GET /api/immich/people` | query: optional `username` | Personenliste |
| Assets | `GET /api/immich/assets` | query: optional `username`, `limit`, `skip` | Assetliste |
| Thumbnail Proxy | `GET /api/immich/thumbnail/<asset_id>` | path: `asset_id`, query: optional `username`, `size` | Binärbild |
| Download Proxy | `GET /api/immich/download/<asset_id>` | path: `asset_id`, query: optional `username` | Binärdownload |
| Kontextsuche | `POST /api/immich/search-by-context` | body: `query`, optional `username`, `limit` | Treffer |

### 6.8 API Registry

| Name | Methode & Pfad | Parameter | Rückgabe |
|---|---|---|---|
| Alle APIs | `GET /api/registry/apis` | query: optional `username` | APIs + Konfigurationsstatus |
| Health aller APIs | `GET /api/registry/health` | query: optional `username` | Healthmap |
| Health einer API | `GET /api/registry/<api_name>/health` | path: `api_name`, query: optional `username`, `use_cache` | Health |
| API-Konfig verwalten | `GET/POST/DELETE /api/registry/<api_name>/config` | path: `api_name`, optional `username`, body (POST): `config` | Konfigurationsstatus |
| API-Test | `POST /api/registry/<api_name>/test` | path: `api_name`, body: `config`, optional `username` | Health-Info |

### 6.9 Home Assistant

| Name | Methode & Pfad | Parameter | Rückgabe |
|---|---|---|---|
| States | `GET /api/homeassistant/states` | query: optional `username` | Entity-States |
| Einzelstate | `GET /api/homeassistant/state/<entity_id>` | path: `entity_id`, query: optional `username` | Entity-State |
| Service Call | `POST /api/homeassistant/service` | body: `domain`, `service`, optional `entity_id`, `data`, `username` | Erfolgsmeldung |
| Entity-Suche | `POST /api/homeassistant/search` | body: `query`, optional `domains`, `username` | Treffer |

### 6.10 Uptime Kuma

| Name | Methode & Pfad | Parameter | Rückgabe |
|---|---|---|---|
| Monitore | `GET /api/uptimekuma/monitors` | query: optional `username` | Monitorliste |
| Einzelmonitor | `GET /api/uptimekuma/monitor/<monitor_id>` | path: `monitor_id`, query: optional `username` | Monitor |
| Statistiken | `GET /api/uptimekuma/stats` | query: optional `username`, `monitor_id` | Uptime-Stats |
| Suche | `POST /api/uptimekuma/search` | body: `query`, optional `username` | Treffer |

### 6.11 Standort, Wetter, Warnung, Public Data

| Name | Methode & Pfad | Parameter | Rückgabe |
|---|---|---|---|
| Standort auflösen | `POST /api/location/resolve` | body: `lat`, `lon`, optional `save` | Adressdaten + NINA/OpenWeather Mapping |
| DWD Warnungen | `GET /api/dwd/warnings/nowcast` | query: optional `lang` | DWD Payload |
| DWD Stationsübersicht | `GET /api/dwd/station-overview` | query: `station_ids` (oder Konfig-Fallback) | Stationsdaten |
| NINA Event-Codes | `GET /api/nina/event-codes` | - | Event-Codes |
| NINA Dashboard | `GET /api/nina/dashboard` | query: `ars` (oder Konfig-Fallback) | Dashboard + Fallbackinfo |
| NINA Map Data | `GET /api/nina/map-data` | query: `source` | MapData |
| NINA Regionen | `GET /api/nina/regions` | query: optional `query`, `limit` | ARS-Liste |
| Sicherheitsstatus | `GET /api/security/status` | - | aggregierte Sicherheitslage |
| Wetter aktuell | `GET /api/weather/current` | - | Wetterstatus |
| Autobahn Roads | `GET /api/autobahn/roads` | - | Straßenliste |
| Autobahn Service | `GET /api/autobahn/road-services` | query: `road_id`, `service` | Servicedaten |
| Dashboard Deutschland | `GET /api/dashboard-deutschland/dashboard` | - | Dashboardeinträge |
| Dashboard Indikatoren | `GET /api/dashboard-deutschland/indicators` | query: `ids` | Indikatordaten |
| Dashboard GeoJSON | `GET /api/dashboard-deutschland/geojson` | - | GeoJSON |
| Deutschland Atlas Service Info | `GET /api/deutschland-atlas/service-info` | query: `service` | Servicedaten |

### 6.12 UI-/Meta-Endpunkte

| Name | Methode & Pfad | Parameter | Rückgabe |
|---|---|---|---|
| System-Konfig | `GET/POST /api/ui/system-config` | body optional (POST): Immich-/AI-Felder | Konfigstatus |
| Runtime-Konfig | `GET/POST /api/ui/runtime-config` | body optional (POST): `base_url`, `model` | Runtime-Status |
| Profil-Konfig | `GET/POST /api/ui/profile-config` | GET query: `username`; POST body: `username` + Profilfelder | Profilstatus |
| Connectivity | `GET /api/ui/connectivity-status` | query: optional `username` | Dienststatus |
| Index-Status | `GET /api/ui/index-status` | - | Dokument-/Chunk-Metriken |
| UI Suggestions | `GET /api/ui/suggestions` | query: optional `username` | Vorschläge |
| UI Immich Status | `GET /api/ui/immich` | query: `username` | Immich-Status |
| Tool Test | `POST /api/tools/test/<tool_name>` | path: `tool_name`, body je Tool | Tool-Ergebnis |
| Agent Query | `POST /api/agent/query` | body: `prompt`, optional `username`, `language`, `context`, `preferred_source` | KI-/Direktantwort |
| Query Suggestions | `POST /api/suggestions/query` | body: optional `username`, `language`, `chatHistory` | personalisierte Vorschläge |

### 6.13 Beispiel Requests/Responses

#### Agent Query
Request:
```json
{
  "prompt": "Zeig mir Fotos von Anna",
  "username": "vinzenz",
  "language": "de",
  "preferred_source": "auto"
}
```

Beispiel-Response:
```json
{
  "success": true,
  "response": "Hier sind passende Fotos ...",
  "context_used": true,
  "context_count": 1,
  "intent": "photos",
  "sources_used": {
    "photos": true,
    "files": false,
    "calendar": false,
    "todos": false
  }
}
```

#### API Registry Config Update
Request:
```json
{
  "config": {
    "url": "http://homeassistant.local:8123",
    "access_token": "***"
  }
}
```

Beispiel-Response:
```json
{
  "success": true,
  "message": "homeassistant configuration saved successfully"
}
```

---

## 7. Konfiguration

### 7.1 Konfigurationsdateien
- `backend/config/ai_config.json`
- `backend/config/nextcloud_config.json`
- `backend/config/calendar_config.json`
- `backend/config/indexing_config.json`
- benutzerspezifisch: `backend/config/user_<username>.json`
- API Registry: `backend/config/<api>_config.json` bzw. `<api>_<username>.json`

### 7.2 API Registry Schema-Prinzip
Jeder API-Client implementiert `get_config_schema()` mit Feldtyp, Pflichtstatus, Beschreibung und optional `secret=true`.

### 7.3 Anpassbare Optionen (Auszug)
- Modell-Endpunkt/Modellname (Ollama)
- Immich Defaults global und userbezogen
- Nextcloud Auth-Modus
- Standort-/ARS-Konfiguration für Wetter/Warnungen
- Task Auto-Sync Interval/Listenname

---

## 8. Fehlerbehandlung und Troubleshooting

### 8.1 Häufige Fehler
- `Immich nicht konfiguriert`: URL/API-Key fehlen (global oder userbezogen)
- `Tasks nicht verfügbar`: Tasks nicht initialisiert oder Nextcloud-Tasks nicht erreichbar
- `Kalender nicht verfügbar`: Kalender deaktiviert oder Credentials ungültig
- `base_url muss mit http:// oder https:// beginnen`: ungültige AI-Konfig
- `ars required`: NINA Dashboard ohne ARS und ohne Konfigfallback
- `station_ids required`: DWD Station Overview ohne Query/Konfig

### 8.2 Fehlerquellen im Betrieb
- externe Service-Unerreichbarkeit (Timeouts, Auth-Fehler)
- veraltete Credentials in JSON-Konfiguration
- inkonsistente parallele Konfigurationspfade (Umgebung + JSON)

### 8.3 Troubleshooting-Schritte
1. `/api/ui/connectivity-status` aufrufen.
2. Einzeltests über `/api/registry/<api>/test` durchführen.
3. AI-Verbindung über `/api/ai/test` und `/api/ollama/status` prüfen.
4. Indexing-Konfig (`/api/indexing/config`) validieren.
5. Logs im Backend auf konkrete Client-Fehler prüfen.

---

## 9. Testing

### 9.1 Testausführung
Es sind vorrangig ausführbare Python-Testskripte vorhanden.

```bash
source .venv/bin/activate
python test_auth_unit.py
python test_additional_apis.py
python test_chat_with_todos.py
```

### 9.2 Teststruktur
- Unit-nahe Tests: z. B. Auth-Provider/Manager
- Integrationsnahe Tests: API-Clients, Chatfluss, Nextcloud/Immich
- Hilfs-/Debugskripte im Root und in `tests/`

### 9.3 Sichtbare Coverage
Es liegt keine explizite Coverage-Konfiguration im gezeigten Stand vor (kein sichtbar integriertes Coverage-Reporting im Repository-Root).

---

## 10. Performance Considerations

### 10.1 Charakteristik
- Fokus auf praktikable lokale Latenz
- FTS5-basierte Suche statt schwergewichtigem Vektorpfad als robuster Fallback
- Hintergrund-Indexierung parallelisiert (`ThreadPoolExecutor`)
- Task-Sync mit DB-Caching für schnelle Folgeabfragen

### 10.2 Mögliche Bottlenecks
- monolithische Request-Logik in `agent_query`
- externe API-Latenzen
- große Kontextblöcke vor LLM-Aufruf
- potenziell teure Bild-/Datei-Proxys bei hoher Last

### 10.3 Optimierungsansätze
- Aufspaltung von `app.py` in Blueprints/Service-Layer
- Response-Caching je Integrationsdomäne
- engeres Context-Budgeting vor LLM-Aufruf
- asynchrone IO/Worker-Queues für Proxy-lastige Endpunkte

---

## 11. Security Notes

### 11.1 Sensible Bereiche
- Konfigurationsdateien enthalten Zugangsdaten/API-Keys
- User-Profile speichern potenziell Credentials
- proxierte Endpunkte greifen mit Server-Credentials auf externe Dienste zu

### 11.2 Risiken
- Secret-Leakage über versionierte JSON-Dateien
- fehlende starke Mandantentrennung auf API-Ebene
- Session-Sicherheit abhängig von `FLASK_SECRET_KEY`

### 11.3 Best Practices
- Secrets rotieren und aus dem Repository entfernen
- Secret-Store/.env-Management einführen
- API-Zugriffe authn/authz-härten
- sensible Felder in Logs strikt maskieren
- HTTPS/TLS für alle externen Integrationen erzwingen

---

## 12. Limitations

- Zentrale App-Logik ist stark monolithisch (`backend/core/app.py`)
- Kein explizites rollenbasiertes Zugriffskonzept im gezeigten Backend
- testseitig überwiegend skriptbasierte Ausführung statt standardisiertem Testframework-Flow
- mehrere Konfigurationsquellen erhöhen Komplexität (Env + JSON + User-Profile)
- DWD Station Overview benötigt `station_ids`; ohne Wert ist der Endpunkt nicht nutzbar

---

## 13. Future Improvements

### 13.1 Architektur
- Flask Blueprints pro Domäne (AI, Knowledge, Integrations, UI)
- Service-/Repository-Layer zur Entkopplung von HTTP und Domänenlogik

### 13.2 Skalierung
- Queue-basiertes Background-Processing (z. B. Celery/RQ)
- Caching von Health/Status-Requests
- selektive Streaming-Antworten für lange Agent-Operationen

### 13.3 Qualität
- konsolidierte Tests mit pytest + fixtures + Mocking
- strukturiertes Fehler-/Event-Logging
- OpenAPI-Spezifikation aus Routen ableiten

### 13.4 Sicherheit
- zentrale Secret-Verwaltung
- API-Authentifizierung und Berechtigungsmodell
- persistente Datenverschlüsselung für sensible Konfigurationsfelder

---

## 14. Annahmen

- Der primäre produktive Einstieg ist `run_app.py` mit Flask auf Port 5001.
- Das Frontend nutzt im Dev-Modus Rewrite auf das lokale Backend.
- Die in JSON-Dateien vorhandenen Werte sind Laufzeitkonfigurationen und nicht nur Dummydaten.
- `dwd` ist als Integration vorgesehen; die Registrierung im `__init__` ist im gezeigten Ausschnitt nicht sichtbar, die Endpunkte existieren jedoch in `app.py`.
