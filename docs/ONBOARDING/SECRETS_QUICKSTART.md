# 🚀 Quick Start: Secrets Management

## TL;DR - Das Wichtigste

### ⚠️ Problem erkannt
Folgende Dateien hatten echte Secrets:
- ❌ `backend/config/ai_config.json` (Immich API Key, URLs)
- ❌ `backend/config/nextcloud_config.json` (Password, Username)
- ❌ `backend/config/indexing_config.json` (Credentials)
- ❌ `backend/config/openweather_config.json` (Geostandort)

### ✅ Gelöst

1. **Alle Secrets anonymisiert** - JSON-Dateien enthalten nur noch Placeholders
2. **`.env.example` hinzugefügt** - Template für Entwickler
3. **`.gitignore` aktualisiert** - `*.env*` und `backend/config/*.json` ausgeschlossen
4. **Setup-Scripts erstellt**:
   - `setup_env.py` - Interaktive Konfiguration
   - `.git-pre-commit-check.py` - Secret-Detection vor Commits

---

## 3 Schritte zum Start

### 1️⃣  Lokale `.env` erstellen

```bash
# Führe Setup interaktiv durch
python3 setup_env.py

# Oder kopiere & bearbeite manuell
cp .env.example .env
nano .env
```

### 2️⃣  Backend starten

```bash
cd backend/core
python3 app.py
```

Backend liest jetzt:
- `.env` Variablen (höchste Priority)
- `backend/config/*.json` (fallback)
- Code Defaults (lowest)

### 3️⃣  Frontend starten

```bash
cd frontend
npm install
npm run dev
```

---

## Neue Dateien

| Datei | Zweck |
|-------|-------|
| `.env.example` | Template für alle Env Variables |
| `.env` | **GITIGNORE** - Deine lokalen Secrets |
| `setup_env.py` | Setup-Wizard für neue Entwickler |
| `.git-pre-commit-check.py` | Verhindert Secrets im Repo |
| `docs/SECURITY/SECRET_MANAGEMENT.md` | Vollständiger Sicherheitsguide |
| `SECRETS_MANAGEMENT_CHECKLIST.md` | Diese Checkliste |

---

## Wichtige Env-Variablen

```env
# Backend
BACKEND_HOST=0.0.0.0
BACKEND_PORT=5000

# AI Model (Ollama)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma2:latest

# Optional: Immich Integration
IMMICH_URL=https://your-immich.com
IMMICH_API_KEY=your-api-key-here

# Optional: Nextcloud Integration
NEXTCLOUD_URL=https://your-nextcloud.com
NEXTCLOUD_USERNAME=user
NEXTCLOUD_PASSWORD=password

# Optional: Weather
OPENWEATHER_API_KEY=your-key-here

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:5000
```

---

## Safety Features

### Pre-Commit Hook
```bash
# Wird automatisch aufgerufen beim commit
# Verhindert versehentliche Secrets
git commit -m "my changes"
# 🔍 Checking for secrets...
# ✅ No secrets detected - proceeding
```

### Git-Ignore Protection
```bash
# Diese Dateien können NIEMALS committed werden:
.env
backend/config/ai_config.json
backend/config/nextcloud_config.json
# etc.
```

---

## Team Workflows

### Für GitHub Collaborators

1. **Clone repo:**
   ```bash
   git clone https://github.com/SchBenedikt/mynd.git
   cd mynd
   ```

2. **Setup environment:**
   ```bash
   python3 setup_env.py  # Interactive setup
   ```

3. **Start development:**
   ```bash
   # Backend
   cd backend/core && python3 app.py
   
   # Frontend (in neuem Terminal)
   cd frontend && npm run dev
   ```

### Für CI/CD (GitHub Actions)

1. **Gehe zu:** Settings → Secrets and variables → Actions

2. **Erstelle Secrets:**
   ```
   IMMICH_API_KEY
   IMMICH_URL
   NEXTCLOUD_PASSWORD
   NEXTCLOUD_USERNAME
   JWT_SECRET
   SESSION_SECRET
   ```

3. **Nutze in Workflows:**
   ```yaml
   - name: Build CLI
     env:
       IMMICH_API_KEY: ${{ secrets.IMMICH_API_KEY }}
   ```

---

## Häufig gestellte Fragen

### F: Kann ich `.env` committen?
**A:** Niemals! `.env` ist in `.gitignore` und enthält persönliche Secrets.

### F: Was ist der Unterschied zwischen `.env` und `.env.example`?
**A:** 
- `.env` - DEINE persönlichen Secrets (nicht committen!)
- `.env.example` - öffentliches Template (IS im Repo)

### F: Muss ich `setup_env.py` nutzen?
**A:** Nein, du kannst auch manuell `.env` bearbeiten. Das Script macht es nur einfacher.

### F: Was wenn ich ein Secret committet habe?
**A:** Siehe [`docs/SECURITY/SECRET_MANAGEMENT.md`](docs/SECURITY/SECRET_MANAGEMENT.md) - "If Secrets Were Already Leaked"

### F: Wie deaktiviere ich den Pre-Commit Hook?
**A:** `git commit --no-verify` (wirk NOT recommended!)

---

## Nächste Schritte

- [ ] Führe `setup_env.py` aus
- [ ] Starte Backend & Frontend
- [ ] Teste dass API funktioniert
- [ ] Commitee diese Änderungen: `git add docs/ && git commit`
- [ ] Aktualisiere Team über neue `.env` Requirements

---

## Support

**Fragen?** Siehe:
- 📘 [`docs/SECURITY/SECRET_MANAGEMENT.md`](docs/SECURITY/SECRET_MANAGEMENT.md)
- 📋 [`SECRETS_MANAGEMENT_CHECKLIST.md`](SECRETS_MANAGEMENT_CHECKLIST.md)
- 🚀 [`CONTRIBUTING.md`](CONTRIBUTING.md)

---

✅ **Dein Projekt ist jetzt GitHub-ready!** 🎉
