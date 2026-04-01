# 🔐 SECURITY GUIDE: Environment Variables & Secret Management

## Problem
Vorher wurden sensible Daten (API-Keys, Passwörter, URLs) direkt in JSON-Dateien gespeichert, die ins Git kamen.

## Lösung: Environment Variables

### 1. Setup für lokale Entwicklung

Kopiere `.env.example` zu `.env`:
```bash
cp .env.example .env
```

Bearbeite `.env` mit deinen realen Werten:
```env
IMMICH_URL=https://fotos.example.com
IMMICH_API_KEY=your_actual_api_key_here
NEXTCLOUD_URL=https://cloud.example.com
NEXTCLOUD_USERNAME=your_username
NEXTCLOUD_PASSWORD=your_password
OPENWEATHER_API_KEY=your_key_here
```

### 2. CI/CD Pipeline (GitHub)

Speichere Secrets in GitHub → Settings → Secrets and variables → Actions:
```bash
IMMICH_URL
IMMICH_API_KEY
NEXTCLOUD_URL
NEXTCLOUD_USERNAME
NEXTCLOUD_PASSWORD
OPENWEATHER_API_KEY
JWT_SECRET
SESSION_SECRET
```

Verwende in `.github/workflows/ci.yml`:
```yaml
env:
  IMMICH_URL: ${{ secrets.IMMICH_URL }}
  IMMICH_API_KEY: ${{ secrets.IMMICH_API_KEY }}
```

### 3. Production Deployment

#### Docker / Docker Compose
```bash
docker run -e IMMICH_URL=$IMMICH_URL \
           -e IMMICH_API_KEY=$IMMICH_API_KEY \
           -e NEXTCLOUD_URL=$NEXTCLOUD_URL \
           mynd-backend
```

#### Kubernetes
```yaml
env:
  - name: IMMICH_URL
    valueFrom:
      secretKeyRef:
        name: mynd-secrets
        key: immich-url
  - name: IMMICH_API_KEY
    valueFrom:
      secretKeyRef:
        name: mynd-secrets
        key: immich-api-key
```

#### Environment Files (.env)
```bash
# Production .env loaded by systemd or docker
export IMMICH_URL="https://production-immich.com"
export IMMICH_API_KEY="production-key"
export NEXTCLOUD_URL="https://production-nextcloud.com"
export DB_PATH="/var/lib/mynd/knowledge_base.db"
```

### 4. Configuration Hierarchy (Priority)

```
1. Environment Variables (.env file)
   ↓
2. Configuration Files (backend/config/*.json)
   ↓
3. Internal Defaults (in code)
```

### 5. What NOT to do

❌ **NEVER:**
- Commit `.env` files to Git
- Push API keys to GitHub
- Use hardcoded credentials in code
- Log sensitive data (credentials, tokens, URLs)
- Commit private configuration files

✅ **DO:**
- Use `.env.example` as template
- Add `*.env*` to `.gitignore`
- Rotate secrets regularly
- Use strong, randomly generated tokens
- Use `.gitignore` to exclude config files
- Review git history before pushing

### 6. Checking for Secrets in Git

Before pushing, check for secrets:

```bash
# Install git-secrets
brew install git-secrets

# Scan current repo
git secrets --scan

# Set up hooks
git secrets --install
git secrets --register-aws
```

Or use:
```bash
# Check for common patterns
git grep -i "password\|api_key\|secret" | grep -v ".example"
```

### 7. If Secrets Were Already Leaked

🚨 **IMMEDIATE ACTIONS:**

1. **Revoke all exposed credentials:**
   - Rotate Immich API key
   - Change Nextcloud password
   - Generate new JWT secrets
   - Revoke any OpenWeather API keys

2. **Remove from Git history:**
```bash
# Using git-filter-repo (recommended)
brew install git-filter-repo
git filter-repo --path backend/config/ai_config.json --invert-paths

# Push with force
git push origin main --force-with-lease
```

3. **Notify:**
   - GitHub advanced security alerts
   - Check git logs for other exposed files
   - Update all deployments with new secrets

### 8. Environment Variable Reference

| Variable | Example | Required | Sensitivity |
|----------|---------|----------|-------------|
| `IMMICH_URL` | `https://fotos.example.com` | Optional | Medium |
| `IMMICH_API_KEY` | `r8hRtGPc8CvdLD...` | Optional | 🔴 CRITICAL |
| `NEXTCLOUD_URL` | `https://cloud.example.com` | Optional | Low |
| `NEXTCLOUD_USERNAME` | `user` | Optional | Medium |
| `NEXTCLOUD_PASSWORD` | `pass123` | Optional | 🔴 CRITICAL |
| `OPENWEATHER_API_KEY` | `key123...` | Optional | 🔴 CRITICAL |
| `JWT_SECRET` | (32+ random chars) | Production | 🔴 CRITICAL |
| `SESSION_SECRET` | (32+ random chars) | Production | 🔴 CRITICAL |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Yes | Low |
| `OLLAMA_MODEL` | `gemma2:latest` | Yes | Low |

### 9. Automatic Secret Detection

Add pre-commit hook (`.git/hooks/pre-commit`):
```bash
#!/bin/bash
# Check for secrets before commit
patterns='password|api_key|secret|apikey|AUTH|Bearer|token'
if git diff --cached | grep -E "$patterns" | grep -v ".example"; then
    echo "❌ Potential secrets detected! Commit refused."
    exit 1
fi
exit 0
```

Install: `chmod +x .git/hooks/pre-commit`

---

## Current Status ✅

- ✅ `.env.example` erstellt
- ✅ `.gitignore` aktualisiert
- ✅ Config-Dateien anonymisiert
- ✅ Backend nutzt Env-Variablen
- ✅ Security-Guide dokumentiert

## Next Steps

1. Erstelle `.env` Datei lokal (nicht committen!)
2. Stelle sicher, dass `.gitignore` korrekt ist
3. Vor jedem Push: `git diff --cached | grep -i secret`
4. Reviewe git history: `git log --all -p`
