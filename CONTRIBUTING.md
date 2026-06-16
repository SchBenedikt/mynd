# Contributing to MYND

## Branch Strategy

- `main` - Production-ready code
- `develop` - Development branch
- `feature/*` - Feature branches
- `bugfix/*` - Bug fix branches
- `claude/*` - KI-assistierte Entwicklung

## Development Setup

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Before Submitting PR

1. **Run Tests**
   ```bash
   cd tests
   python -m pytest . -v
   ```

2. **Code Quality**
   - Follow Python PEP 8
   - Use meaningful variable names
   - Add docstrings to functions
   - Keep methods focused and small

3. **Security**
   - Validate all inputs
   - Don't commit secrets
   - Use security utilities from `backend/core/security_utils.py`
   - Check OWASP Top 10 implications

4. **Documentation**
   - Update `docs/` if behavior changes
   - Add docstrings and type hints
   - Keep README.md and PROJECT_STRUCTURE.md in sync

## File Organization

```
backend/
├── core/          → Haupt-App (app.py, database.py, security*)
├── features/      → Feature-Module (calendar, documents, integration, knowledge, tasks, training)
└── config/        → Laufzeit-Konfiguration (gitignored)

frontend/
├── app/           → Next.js App Router
└── components/    → React-Komponenten

scripts/           → Setup, Debug, Demo
tests/             → Test-Dateien
docs/              → Dokumentation
data/              → Laufzeitdaten (gitignored)
```

## Testing Requirements

### Unit Tests
- Test single functions in isolation
- Use meaningful test names
- Test positive and negative cases

### Security Tests
- Test injection attempts
- Validate input handling
- Check authentication/authorization

### Edge Cases
- Boundary conditions
- Null/undefined handling
- Error scenarios

## Commit Messages

```
[TYPE] Kurze Beschreibung

Optionale ausführliche Erklärung
- Aufzählung der Änderungen

Fixes: #123
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `security`, `chore`

## PR Review Checklist

- [ ] Tests added/updated
- [ ] Docs updated
- [ ] No hardcoded secrets
- [ ] Security implications considered
- [ ] Code formatted properly
- [ ] Breaking changes documented

## Architecture

- **Backend**: Flask (Python) mit SQLite + semantischer Suche
- **Frontend**: Next.js (React) mit App Router
- **AI**: Ollama (lokales LLM) via REST-API
- **Integrationen**: Nextcloud (CalDAV, WebDAV, Tasks, Activity), Immich, OpenWeather, DWD, Home Assistant
- **Auth**: OAuth2 (PKCE), Login Flow v2, Basic Auth

## Questions?

- Check documentation in `/docs`
- Review security guidelines in `/docs/SECURITY`
