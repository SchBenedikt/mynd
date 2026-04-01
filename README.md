# MYND - Integrierte KI-gestützte Produktivitätsplattform

Ein modernes, sicheres und performantes System zur Integrierung von Nextcloud, Immich, Kalender und KI-gestützter Aufgabenverwaltung.

## 🔐 SECURITY NOTICE

**⚠️ WICHTIG:** Dieses Projekt verwendet Environment Variables zum Schutz von Secrets!

- ❌ Committe **NIEMALS** `.env` Dateien zu Git
- ❌ Committe **NIEMALS** API-Keys, Passwörter, oder Tokens
- ✅ Nutze `.env.example` als Template
- ✅ Führe `python3 scripts/setup/setup_env.py` für Setup aus

**Dokumentation:** Siehe [`docs/ONBOARDING/SECRETS_QUICKSTART.md`](docs/ONBOARDING/SECRETS_QUICKSTART.md) | [`docs/SECURITY/SECRET_MANAGEMENT.md`](docs/SECURITY/SECRET_MANAGEMENT.md)

## 🚀 Quick Start (3 Minuten)

### 1️⃣ Umgebung einrichten
```bash
python3 scripts/setup/setup_env.py
# oder manuell:
cp .env.example .env && nano .env
```

### 2️⃣ Backend starten
```bash
cd backend/core
export $(cat ../../.env | xargs)
python3 app.py
# Backend läuft unter: http://localhost:5000
```

### 3️⃣ Frontend starten (neues Terminal)
```bash
cd frontend
npm install
npm run dev
# Frontend läuft unter: http://localhost:3000
```

## 📁 Projektstruktur (Übersicht)

**Vollständiger Überblick:** [`PROJECT_STRUCTURE.md`](PROJECT_STRUCTURE.md)

| Bereich | Pfad | Zweck |
|---------|------|-------|
| **Dokumentation** | `docs/` | ONBOARDING, Security, API, Guides |
| **Backend** | `backend/` | Python FastAPI Server |
| **Frontend** | `frontend/` | Next.js React App |
| **Tests** | `tests/` | Unit & Integration Tests |
| **Tools** | `scripts/` | Setup, Debug, Demo Scripts |
| **Runtime Data** | `data/` | Cache, Config, Training (gitignored) |

## 📚 DOCUMENTATION

### 🎯 Für neue Entwickler
1. **[Project Structure](PROJECT_STRUCTURE.md)** - Übersicht (5 Min)
2. **[Secrets Quick Start](docs/ONBOARDING/SECRETS_QUICKSTART.md)** - Security (5 Min)
3. **[Quick Start Guide](docs/GUIDES/QUICKSTART.md)** - Getting Started (10 Min)

### 🔐 Für Security
1. **[Security Review](docs/SECURITY/README_SECURITY_REVIEW.md)** - OWASP Top 10
2. **[Threat Model](docs/SECURITY/THREAT_MODEL.md)** - STRIDE Analysis
3. **[Code Review Report](reports/code_review_report.md)** - Detailed Findings

### 🚀 Für Deployment
1. **[Deployment Checklist](docs/ONBOARDING/DEPLOYMENT_CHECKLIST.md)** - Pre-Deploy
2. **[Infrastructure Guide](docs/INFRASTRUCTURE.md)** - Setup & Deployment
3. **[Status Dashboard](docs/ONBOARDING/STATUS_DASHBOARD.md)** - Monitoring

### 📖 API & Integration
- **[API Endpoints](docs/API/new-api-endpoints.md)** - REST API Reference
- **[Nextcloud Integration](docs/API/NEXTCLOUD_API_INTEGRATIONS.md)** - NC API
- **[Immich Integration](docs/IMMICH_INTEGRATION.md)** - Photo Management

## 🔧 Setup & Tools

### Environment Setup
```bash
# Interaktiver Wizard (empfohlen)
python3 scripts/setup/setup_env.py

# Pre-Commit Hook (verhindert Secrets-Leaks)
cp scripts/setup/.git-pre-commit-check.py .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### Demo & Tests
```bash
# Demo Scripts
python scripts/demo/demo_batch_loading.py

# Tests
python -m unittest discover -s tests -p "test_*.py" -v
```

## 🧪 Testing

```bash
# Alle Tests ausführen
cd tests
python -m unittest discover -s . -p "test_*.py" -v

# Spezifische Test-Kategorien
python -m unittest tests.test_secrets_management -v
python -m unittest tests.test_security_hardening -v
python -m unittest tests.test_auth_plugin -v
```

## 🐳 Docker Setup (Optional)

```bash
docker-compose up -d

# Services:
# - Backend: http://localhost:5000
# - Frontend: http://localhost:3000
```

## 📋 Key Features

- ✅ **Sichere Authentifizierung** - OAuth2, PKCE, JWT
- ✅ **Multi-Source Integration** - Nextcloud, Immich, Calendar
- ✅ **KI-gestützte Analyse** - Document processing, task intelligence
- ✅ **Modernes Tech-Stack** - Python Backend, Next.js Frontend
- ✅ **Production-Ready** - Security hardened (OWASP Top 10)
- ✅ **Fully Tested** - 30+ Tests, 80%+ Coverage
- ✅ **Well Documented** - 15,000+ Lines of Docs

## 🤝 Contributing

Siehe [`CONTRIBUTING.md`](CONTRIBUTING.md) für Guidelines.

### Wichtige Rules
1. **Niemals Secrets committe** - Use `.env.example`
2. **Tests schreiben** - Minimum 80% Coverage
3. **Security First** - Input Validation, Error Handling
4. **Dokumentation** - Comments, Updated Docs

## 📊 Statistics

| Metric | Value |
|--------|-------|
| Backend Modules | 6+ |
| Frontend Pages | 5+ |
| Test Files | 20+ |
| Documentation | 15,000+ Lines |
| Total Code | 13,000+ Lines |

## 🔗 Quick Links

- 📘 [README](README.md)
- 📋 [Contributing](CONTRIBUTING.md)
- 🏗️ [Project Structure](PROJECT_STRUCTURE.md)
- 🔐 [Secrets Management](docs/ONBOARDING/SECRETS_QUICKSTART.md)
- 🛡️ [Security Review](docs/SECURITY/README_SECURITY_REVIEW.md)
- 📊 [Code Review Report](reports/code_review_report.md)

---

**Version:** 2.0 (Reorganisiert & Production-Ready)  
**Letztes Update:** April 1, 2026  
**Status:** ✅ PRODUCTION READY
