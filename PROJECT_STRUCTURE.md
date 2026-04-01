# 📁 Projectstruktur - MYND Assistant

## 🎯 Quick Navigation

| Bereich | Pfad | Beschreibung |
|---------|------|-------------|
| **Starten Sie hier** | [`docs/ONBOARDING/`](docs/ONBOARDING/) | Setup, Deployment, Geheimnisse |
| **Backend Code** | [`backend/`](backend/) | Python FastAPI Server |
| **Frontend Code** | [`frontend/`](frontend/) | Next.js React Application |
| **Tests** | [`tests/`](tests/) | Unit & Integration Tests |
| **Dokumentation** | [`docs/`](docs/) | Vollständige Dokumentation |
| **Scripts** | [`scripts/`](scripts/) | Utility & Setup Scripts |
| **Daten** | [`data/`](data/) | Runtime Data (Cache, Training) |

---

## 📂 Detaillierte Struktur

### 🚀 Root-Verzeichnis (Sauber & Minimal)

```
.
├── README.md                 # Projekt-Übersicht
├── CONTRIBUTING.md           # Developer-Guidelines
├── .env.example              # Environment Template
├── .gitignore               # Git Ignore-Regeln
├── TREE.txt                 # ASCII-Übersicht
├── knowledge_base.db*       # SQLite Datenbank (gitignored)
```

### 📚 docs/ - Vollständige Dokumentation

```
docs/
├── README.md                # Dokumentation Übersicht
├── ONBOARDING/              # ⭐ STARTEN SIE HIER
│   ├── SECRETS_QUICKSTART.md
│   ├── DEPLOYMENT_CHECKLIST.md
│   ├── STATUS_DASHBOARD.md
│   └── [7 weitere Onboarding-Docs]
├── API/                     # API-Schnittstellen
│   ├── new-api-endpoints.md
│   └── NEXTCLOUD_API_INTEGRATIONS.md
├── GUIDES/                  # Tutorials & How-Tos
│   ├── QUICKSTART.md
│   ├── BATCH_LOADING_GUIDE.md
│   ├── IMMICH_FEATURES_UPDATE.md
│   └── [3 weitere Guides]
├── SECURITY/                # 🔐 Security & Threat Models
│   ├── README_SECURITY_REVIEW.md
│   ├── SECRET_MANAGEMENT.md
│   └── THREAT_MODEL.md
└── REPORTS/                 # Audit & Code Reviews
    ├── COMPLETION_REPORT.md
    └── REVIEW_SUMMARY.md
```

### 🐍 backend/ - Python FastAPI Server

```
backend/
├── requirements.txt         # Python Dependencies
├── __init__.py
├── core/                    # ⭐ Hauptserver
│   ├── app.py              # FastAPI App Entry Point
│   ├── database.py         # SQLite/ORM Logic
│   ├── security_*.py       # Security Utilities
│   └── training_data.json  # ML Training Data
├── config/                  # Konfigurationsdateien (GITIGNORED!)
│   ├── *.example.json       # Sichere Templates
│   └── .gitkeep            # Verzeichnis-Marker
├── features/               # Feature-Module
│   ├── calendar/           # Kalender-Integration
│   ├── documents/          # Dokument-Verarbeitung
│   ├── integration/        # Externe Integrationen
│   ├── knowledge/          # Knowledge Graph
│   ├── tasks/              # Task Management
│   └── training/           # ML Training
└── [andere Module]
```

### ⚛️ frontend/ - Next.js React App

```
frontend/
├── package.json            # Node Dependencies
├── next.config.mjs         # Next.js Config
├── jsconfig.json          # JavaScript Config
├── app/                    # Next.js App Router
│   ├── layout.js          # Root Layout
│   ├── page.js            # Home Page
│   ├── globals.css        # Global Styles
│   └── settings/          # Settings Pages
├── components/            # React Components
├── hooks/                 # Custom React Hooks
└── README.md             # Frontend Guide
```

### 🧪 tests/ - Testsuite

```
tests/
├── README.md
├── test_*.py              # Unit Tests für Backend
├── test_auth_*.py         # Authentication Tests
├── test_immich_*.py       # Immich Integration Tests
├── test_chat_*.py         # Chat/Agent Tests
├── test_todos.py          # Task Management Tests
├── fix_database.py        # DB Fixtures
└── knowledge_*            # Test Data
```

### 🛠️ scripts/ - Utilities & Tools

```
scripts/
├── run_app.py             # Start Backend & Frontend
├── setup/                 # Setup Tools
│   ├── setup_env.py       # Environment Wizard
│   └── .git-pre-commit-check.py  # Secret Scanner
├── debug/                 # Debugging Tools
│   ├── [Debug Scripts]
├── demo/                  # Demo Scripts
├── examples/              # Example Usage
└── inspect/               # Inspection Tools
```

### 📊 data/ - Runtime Data

```
data/
├── user_knowledge.txt     # Benutzer-Wissensdatenbank
├── cache/                 # Daten-Cache (gitignored)
│   └── .gitkeep
├── config/                # Runtime Config (gitignored)
│   └── .gitkeep
├── training/              # ML Training Data (gitignored)
│   └── .gitkeep
└── [andere Runtime-Daten]
```

### 📈 reports/ - Generierte Reports

```
reports/                    # (GITIGNORED)
├── code_review_report.md
├── code_review_report.json
└── [andere Audit-Reports]
```

### 🔄 .github/ - CI/CD Pipeline

```
.github/
└── workflows/
    └── ci.yml            # GitHub Actions CI/CD
```

---

## 🔐 Wichtige Sicherheitsnoten

### ❌ Niemals committed:
- `.env` - Lokale Umgebungsvariablen
- `backend/config/*.json` - Konfigurationen mit Secrets
- `data/cache/`, `data/training/`, `reports/`
- `*.db*` - Datenbank-Dateien

### ✅ Diese existieren:
- `.env.example` - Sichere Template
- `backend/config/*.example.json` - Sichere Templates

### 🚀 Setup:
```bash
# 1. Environment konfigurieren
python3 scripts/setup/setup_env.py

# 2. Backend starten
cd backend/core && python3 app.py

# 3. Frontend starten (neues Terminal)
cd frontend && npm run dev
```

---

## 📖 Zu lesende Dokumentation

1. **[ONBOARDING](docs/ONBOARDING/)** (5-15 Min)
   - Schnelle Setup & Geheimnis-Verwaltung

2. **[QUICKSTART Guide](docs/GUIDES/QUICKSTART.md)** (10 Min)
   - Erste Schritte

3. **[Security Review](docs/SECURITY/README_SECURITY_REVIEW.md)** (20 Min)
   - Sicherheitsarchitektur

4. **[API Dokumentation](docs/API/)** (15 Min)
   - Schnittstellen & Integrationen

5. **[Threat Model](docs/SECURITY/THREAT_MODEL.md)** (25 Min)
   - Sicherheitsanalyse

---

## 🎯 Typische Workflows

### Entwickler starten:
```
docs/ONBOARDING/SECRETS_QUICKSTART.md
    → docs/GUIDES/QUICKSTART.md
        → backend/core/app.py
            → frontend/app/page.js
```

### Deployment:
```
docs/ONBOARDING/DEPLOYMENT_CHECKLIST.md
    → scripts/setup/setup_env.py
        → docker-compose up
            → Production Monitor
```

### Sicherheitsreview:
```
docs/SECURITY/README_SECURITY_REVIEW.md
    → docs/SECURITY/THREAT_MODEL.md
        → reports/code_review_report.md
            → Issues beheben
```

### Testing:
```
tests/
    → pytest
        → Coverage Report
            → CI/CD (GitHub Actions)
```

---

## 📊 Statistik

| Metrik | Wert |
|--------|------|
| **Backend Module** | 6+ |
| **Frontend Pages** | 5+ |
| **Test Files** | 20+ |
| **Documentation Pages** | 15+ |
| **Configuration Templates** | 5+ |
| **Gesamt LOC** | 13,000+ |

---

### 🔗 Schnelle Links

- 📘 [Projekt README](README.md)
- 📝 [CONTRIBUTING Guide](CONTRIBUTING.md)
- 🔐 [Secrets Management](docs/ONBOARDING/SECRETS_QUICKSTART.md)
- 🚀 [Deployment Checklist](docs/ONBOARDING/DEPLOYMENT_CHECKLIST.md)
- 🛡️ [Security Review](docs/SECURITY/README_SECURITY_REVIEW.md)

---

**Zuletzt aktualisiert:** April 1, 2026  
**Version:** 2.0 (Umstrukturiert & Reorganisiert)
