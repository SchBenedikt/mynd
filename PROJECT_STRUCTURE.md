# Projektstruktur - MYND

## Quick Navigation

| Bereich | Pfad | Beschreibung |
|---------|------|-------------|
| **Start hier** | `docs/ONBOARDING/` | Setup, Deployment, Secrets |
| **Backend** | `backend/` | Python Flask Server |
| **Frontend** | `frontend/` | Next.js React App |
| **Tests** | `tests/` | Unit & Integration Tests |
| **Dokumentation** | `docs/` | Vollständige Dokumentation |
| **Scripts** | `scripts/` | Utility & Setup Scripts |
| **Daten** | `data/` | Laufzeitdaten |

## Detaillierte Struktur

### Root-Verzeichnis

```
.
├── README.md                 # Projekt-Übersicht
├── CONTRIBUTING.md           # Developer-Guidelines
├── PROJECT_STRUCTURE.md      # Diese Datei
├── .env.example              # Environment Template
├── .gitignore                # Git-Ignore-Regeln
├── app.py                    # Legacy-Flask-App (root)
├── docker-compose.yml        # Docker-Compose (Dev)
├── docker-compose.prod.yml   # Docker-Compose (Production)
├── deploy.sh                 # Deployment-Skript
├── LICENSE                   # Lizenz
├── backend/                  # Python Backend
├── frontend/                 # Next.js Frontend
├── docs/                     # Dokumentation
├── scripts/                  # Hilfsskripte
├── tests/                    # Tests
├── data/                     # Laufzeitdaten
└── .github/                  # CI/CD-Workflows
```

### Backend (`backend/`)

```
backend/
├── __init__.py
├── requirements.txt         # Python-Abhängigkeiten
├── Dockerfile               # Docker-Build für Backend
├── config/                  # Laufzeit-Konfiguration (nicht in Git!)
│   ├── ai_config.json
│   ├── indexing_config.json
│   ├── nextcloud_config.json
│   ├── nextcloud_oauth2.json
│   ├── runtime_config.json
│   └── users.json
├── core/                    # Haupt-App
│   ├── app.py              # Flask-App (Haupteinstiegspunkt)
│   ├── database.py         # SQLite-Datenbanklogik
│   ├── security_hardening.py
│   ├── security_utils.py
│   ├── autonomous/         # Autonomer Agent
│   │   └── agent.py
│   ├── context/            # Kontext-Gatherer
│   │   └── gatherers.py
│   └── routes/             # API-Routen (Erweiterungen)
│       └── __init__.py
├── features/               # Feature-Module
│   ├── calendar/           # Kalender-Integration (CalDAV)
│   │   ├── manager.py
│   │   └── simple.py
│   ├── documents/          # Dokumenten-Parser
│   │   ├── parser.py
│   │   └── parser_hardened.py
│   ├── integration/        # Externe Integrationen
│   │   ├── nextcloud_client.py
│   │   ├── nextcloud_client_hardened.py
│   │   ├── nextcloud_accounts.py
│   │   ├── auth_manager.py
│   │   ├── auth_provider.py
│   │   ├── auth_basic.py
│   │   ├── auth_nextcloud_direct.py
│   │   ├── oauth2_nextcloud.py
│   │   ├── oauth2_nextcloud_pkce.py
│   │   ├── loginflow_state.py
│   │   ├── immich_client.py
│   │   ├── talk_client.py
│   │   ├── activity_client.py
│   │   ├── notifications_client.py
│   │   ├── carddav_client.py
│   │   ├── search_client.py
│   │   ├── api_registry.py
│   │   ├── email_client.py
│   │   ├── autobahn_client.py
│   │   ├── openweather_client.py
│   │   ├── dwd_client.py
│   │   ├── nina_client.py
│   │   ├── dashboard_deutschland_client.py
│   │   ├── deutschland_atlas_client.py
│   │   ├── uptimekuma_client.py
│   │   └── homeassistant_client.py
│   ├── knowledge/          # Wissensdatenbank & Indexierung
│   │   ├── indexing.py
│   │   ├── search.py
│   │   ├── engine.py
│   │   ├── graph.py
│   │   ├── metadata.py
│   │   └── email_indexing.py
│   ├── tasks/              # Aufgaben/Todos (Nextcloud Tasks)
│   │   ├── manager.py
│   │   ├── batch_loader.py
│   │   └── simple.py
│   └── training/           # ML-Training
│       └── manager.py
└── templates/              # HTML-Templates (Fallback)
```

### Frontend (`frontend/`)

```
frontend/
├── package.json            # Node.js-Abhängigkeiten
├── next.config.mjs         # Next.js-Konfiguration
├── jsconfig.json
├── Dockerfile
├── .env.local.example
├── app/                    # Next.js App Router
│   ├── layout.js          # Root-Layout
│   ├── page.js            # Startseite (Chat)
│   ├── globals.css        # Globale Styles
│   ├── admin/             # Admin-Seiten
│   ├── settings/          # Einstellungen
│   ├── setup/             # Setup-Wizard
│   ├── internal/          # Interne Tools
│   └── knowledge-graph/   # Knowledge-Graph-Visualisierung
├── components/            # React-Komponenten
│   ├── AuthGate.js
│   ├── AuthGate.css
│   ├── ContextDataCard.js
│   ├── KnowledgeGraph.js
│   ├── KnowledgeGraph.module.css
│   ├── SetupWizard.js
│   ├── SourceCard.js
│   ├── StatusPill.js
│   ├── SuggestionsPanel.js
│   ├── ThemeSelector.js
│   └── UserBar.js
├── hooks/                 # Custom React Hooks
└── data/                  # Frontend-Daten
```

### Tests (`tests/`)

```
tests/
├── README.md
├── test_auth_plugin.py
├── test_auth_unit.py
├── test_agent_photo_search.py
├── test_chat_with_todos.py
├── test_immich_direct.py
├── test_immich_features.py
├── test_init_tasks.py
├── test_nextcloud_apis.py
├── test_secrets_management.py
├── test_security_hardening.py
├── test_todos.py
└── fix_database.py
```

### Scripts (`scripts/`)

```
scripts/
├── run_app.py             # App-Start (empfohlen)
├── setup/                 # Setup-Tools
│   ├── setup_env.py       # Environment-Wizard
│   ├── setup_nextcloud.py # Nextcloud-Setup
│   ├── check_backend_endpoints.py
│   └── .git-pre-commit-check.py
├── demo/
│   └── demo_batch_loading.py
├── debug/
├── examples/
├── inspect/
├── demo_batch_loading.py
├── debug_nextcloud.py
├── inspect_ics.py
├── find_open_tasks.py
├── find_assets_endpoint.py
├── find_immich_endpoints.py
├── get_immich_version.py
├── test_auth_plugin.py
├── test_auth_unit.py
├── test_chat_with_todos.py
├── test_immich_direct.py
├── test_immich_features.py
├── test_init_tasks.py
├── test_nextcloud_apis.py
├── test_todos.py
├── test_additional_apis.py
├── test_agent_photo_search.py
├── example_auth_usage.py
└── example_nextcloud_apis.py
```

### Dokumentation (`docs/`)

```
docs/
├── README.md              # Doku-Übersicht
├── ADMIN_SETUP.md
├── AUTONOMOUS_AGENT.md
├── BATCH_LOADING_GUIDE.md
├── BENUTZERHANDBUCH_AUTONOMOUS.md
├── CALENDAR_IMPROVEMENTS.md
├── IMMICH_COMPLETION.md
├── IMMICH_FEATURES_UPDATE.md
├── IMMICH_INTEGRATION.md
├── INFRASTRUCTURE.md
├── NEXTCLOUD_API_INTEGRATIONS.md
├── NEXTCLOUD_AUTH_PLUGIN.md
├── nextcloud-talk-bot.md
├── SECRETS.md
├── TALK_BOT_SETUP_GUIDE.md
├── technical_documentation.md
├── API/
│   ├── new-api-endpoints.md
│   └── NEXTCLOUD_API_INTEGRATIONS.md
├── GUIDES/
│   ├── BATCH_LOADING_GUIDE.md
│   ├── IMMICH_FEATURES_UPDATE.md
│   ├── INDEX.md
│   ├── NEXTCLOUD_INTEGRATION_GUIDE.md
│   ├── QUICKSTART.md
│   └── todo.md
├── ONBOARDING/
│   ├── DEPLOYMENT_CHECKLIST.md
│   ├── REORGANIZATION_SUMMARY.md
│   ├── SECRETS_FIX_SUMMARY.md
│   ├── SECRETS_IMPLEMENTATION_COMPLETE.md
│   ├── SECRETS_MANAGEMENT_CHECKLIST.md
│   ├── SECRETS_QUICKSTART.md
│   ├── STATUS_DASHBOARD.md
│   └── STRUCTURE.md
└── SECURITY/
    ├── README_SECURITY_REVIEW.md
    ├── SECRET_MANAGEMENT.md
    └── THREAT_MODEL.md
```

### Daten (`data/`)

```
data/
└── user_knowledge.txt     # Benutzer-Wissensdatenbank
```

Laufzeitdaten (in `.gitignore`, nicht eingecheckt):
- `data/cache/` - Daten-Cache
- `data/training/` - ML-Training-Daten
- Reports in `reports/`

### CI/CD (`.github/`)

```
.github/
└── workflows/
    └── ci.yml            # GitHub Actions
```

## Wichtige Sicherheitshinweise

### Niemals committed:
- `.env` - Lokale Umgebungsvariablen
- `backend/config/*.json` - Konfigurationen mit Secrets
- `data/cache/`, `data/training/`
- `*.db*` - Datenbank-Dateien

### Vorhandene Templates:
- `.env.example` - Environment-Template
- `frontend/.env.local.example` - Frontend-Env-Template

## Setup

```bash
# 1. Environment konfigurieren
python scripts/setup/setup_env.py

# 2. Backend starten
python scripts/run_app.py
# -> http://localhost:5001

# 3. Frontend starten (neues Terminal)
cd frontend && npm run dev
# -> http://localhost:3000
```

## API-Übersicht

Siehe `README.md` für die vollständige API-Referenz oder `docs/API/new-api-endpoints.md`.
