# MYND - Integrierte KI-gestützte Produktivitätsplattform

Ein modernes System zur Integration von Nextcloud, Immich, Kalender und KI-gestützter Aufgabenverwaltung mit lokalem Ollama-Backend.

## Quick Start (3 Minuten)

### 1. Umgebung einrichten
```bash
cp .env.example .env
# .env mit eigenen Zugangsdaten füllen
```

### 2. Backend starten
```bash
pip install -r backend/requirements.txt
python scripts/run_app.py
# Backend läuft unter: http://localhost:5001
```

### 3. Frontend starten (neues Terminal)
```bash
cd frontend
npm install
npm run dev
# Frontend läuft unter: http://localhost:3000
```

## Projektstruktur (Übersicht)

| Bereich | Pfad | Zweck |
|---------|------|-------|
| **Backend** | `backend/` | Python Flask Server |
| **Frontend** | `frontend/` | Next.js React App |
| **Tests** | `tests/` | Unit & Integration Tests |
| **Dokumentation** | `docs/` | Guides, API, Security, Onboarding |
| **Scripts** | `scripts/` | Setup, Debug, Demo |
| **Daten** | `data/` | Laufzeitdaten (Cache, Training) |

Vollständiger Überblick: [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md)

## Features

- **Chat mit KI** - Lokales Ollama (Gemma, Llama, etc.) mit RAG-Kontext
- **Nextcloud-Integration** - Dokumenten-Indexierung, Kalender (CalDAV), Tasks (Tasks.org), Aktivitäten, Benachrichtigungen
- **Immich-Integration** - Foto-Suche und -Verwaltung
- **Kalender** - Terminübersicht und -erstellung via Chat
- **Aufgaben/Todos** - Nextcloud Tasks mit Sync, Fälligkeitsdaten, Filter
- **Wissensdatenbank** - SQLite-basiert mit semantischer Suche
- **Dokumenten-Parser** - PDF, DOCX, XLSX, PPTX, MD, HTML
- **Authentifizierung** - OAuth2 (PKCE), Login Flow v2, Basic Auth
- **Docker-Setup** - Einfacher Start mit `docker-compose`

## Docker (Optional)

```bash
docker-compose up -d
# Backend: http://localhost:5001
# Frontend: http://localhost:3000
```

## API Endpunkte

### Chat & KI
| Endpunkt | Methode | Beschreibung |
|----------|---------|--------------|
| `/api/chat` | POST | Chat-Anfrage mit Kontext |
| `/api/ollama/status` | GET | Ollama-Verbindungsstatus |
| `/api/ollama/models` | GET | Verfügbare Modelle |
| `/api/ai/config` | GET/POST | AI-Konfiguration lesen/speichern |
| `/api/ai/test` | POST | AI-Verbindung testen |

### Wissen & Indexierung
| Endpunkt | Methode | Beschreibung |
|----------|---------|--------------|
| `/api/knowledge/status` | GET | Wissensdatenbank-Status |
| `/api/knowledge/sources` | GET | Geladene Quellen |
| `/api/knowledge/reload` | POST | Wissensbasis neu laden |
| `/api/knowledge/migrate` | POST | JSON-Cache migrieren |
| `/api/knowledge/update-embeddings` | POST | Embeddings aktualisieren |
| `/api/indexing/start` | POST | Nextcloud-Indexierung starten |
| `/api/indexing/stop` | POST | Indexierung stoppen |
| `/api/indexing/progress` | GET | Indexierungs-Fortschritt |
| `/api/indexing/config` | GET/POST | Indexierungs-Konfiguration |

### Kalender
| Endpunkt | Methode | Beschreibung |
|----------|---------|--------------|
| `/api/calendar/status` | GET | Kalender-Status |
| `/api/calendar/today` | GET | Heutige Termine |
| `/api/calendar/tomorrow` | GET | Morgige Termine |
| `/api/calendar/week` | GET | Termine diese Woche |
| `/api/calendar/next-week` | GET | Termine nächste Woche |
| `/api/calendar/create` | POST | Termin via Chat erstellen |
| `/api/calendar/calendars` | GET | Verfügbare Kalender |

### Aufgaben (Todos)
| Endpunkt | Methode | Beschreibung |
|----------|---------|--------------|
| `/api/tasks/list` | GET | Alle offenen Aufgaben |
| `/api/tasks/create` | POST | Aufgabe erstellen |
| `/api/tasks/complete/<uid>` | POST | Aufgabe abschließen |
| `/api/tasks/status` | GET | Task-Integration Status |
| `/api/tasks/sync` | POST | Tasks in DB synchronisieren |
| `/api/tasks/db-stats` | GET | Datenbank-Statistiken |

### Nextcloud-Integration
| Endpunkt | Methode | Beschreibung |
|----------|---------|--------------|
| `/api/auth/nextcloud/login` | POST | Nextcloud-Login (Basic/OAuth) |
| `/api/auth/nextcloud/callback` | GET | OAuth2-Callback |
| `/api/auth/nextcloud/status` | GET | Auth-Status |
| `/api/auth/nextcloud/logout` | POST | Logout |

### Sonstige
| Endpunkt | Methode | Beschreibung |
|----------|---------|--------------|
| `/api/health` | GET | Health-Check |
| `/api/training/stats` | GET | Trainings-Statistiken |

## Konfiguration

### Environment (.env)
Wichtige Variablen in `.env.example`:
- **Nextcloud**: `NEXTCLOUD_URL`, `NEXTCLOUD_USERNAME`, `NEXTCLOUD_PASSWORD`
- **Ollama**: `OLLAMA_BASE_URL`, `OLLAMA_MODEL` (default: `gemma3:latest`)
- **Immich**: `IMMICH_URL`, `IMMICH_API_KEY`
- **Security**: `JWT_SECRET`, `SESSION_SECRET`, `CORS_ORIGINS`
- **Frontend**: `NEXT_PUBLIC_BACKEND_URL`

## Tests

```bash
cd tests
python -m pytest . -v

# Bestimmte Testkategorien
python -m pytest test_auth_unit.py test_todos.py -v
```

## Dokumentation

| Bereich | Pfad |
|---------|------|
| **Onboarding & Setup** | `docs/ONBOARDING/` |
| **Guides & Tutorials** | `docs/GUIDES/` |
| **API-Referenz** | `docs/API/` |
| **Security** | `docs/SECURITY/` |
| **Beitragen** | `CONTRIBUTING.md` |

## Lizenz

Siehe `LICENSE`.
