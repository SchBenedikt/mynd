# Infrastructure & Architecture Guide

## System Architecture

### Backend Stack
- **Runtime:** Python 3.11+
- **Framework:** Flask/FastAPI
- **Database:** SQLite (configurable)
- **Authentication:** OAuth2, OIDC, Basic Auth
- **APIs:** RESTful endpoints

### Frontend Stack
- **Framework:** Next.js 14+
- **Language:** JavaScript/React
- **Styling:** CSS Modules, Tailwind (configurable)
- **Package Manager:** npm/yarn
- **Deployment:** Vercel, self-hosted

### Integration Clients
```
backend/features/integration/
├── auth_*.py              # Authentication providers
├── *_client.py            # Service clients
├── *_client_hardened.py   # Security-enhanced versions
└── activity_client.py    # Unified activity API
```

Supported Integrations:
- ✅ Nextcloud (WebDAV, API)
- ✅ Immich (Photo Management)
- ✅ CalDAV (Calendar)
- ✅ CardDAV (Contacts)

## Deployment

### Local Development
```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd core
python app.py

# Frontend
cd frontend
npm install
npm run dev
```

### Docker Compose
```bash
docker-compose up -d
```

Services started:
- Backend API: http://localhost:5000
- Frontend: http://localhost:3000
- PostgreSQL: localhost:5432 (if configured)

### Production Deployment

#### Backend (Linux/macOS)
```bash
# Using gunicorn
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 backend.core.app:app

# Using systemd service
[Service]
ExecStart=/path/to/venv/bin/gunicorn \
  -w 4 -b 127.0.0.1:5000 \
  backend.core.app:app
```

#### Frontend (Vercel)
```bash
npm run build
npm start
```

#### Environment Variables

Required in `.env`:
```
# Database
DATABASE_URL=sqlite:///data/cache/app.db

# Authentication
NEXTCLOUD_URL=https://nextcloud.example.com
NEXTCLOUD_USER=admin
NEXTCLOUD_PASSWORD=***

IMMICH_URL=https://immich.example.com
IMMICH_API_KEY=***

# Security
SECRET_KEY=*** (generate with secrets.token_urlsafe(32))
JWT_SECRET=***

# API Settings
API_HOST=0.0.0.0
API_PORT=5000
API_DEBUG=false

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:5000
```

## Security Hardening

### Backend Security Features
- ✅ Input validation & sanitization
- ✅ SQL injection prevention (parameterized queries)
- ✅ CSRF protection via tokens
- ✅ XSS prevention via output escaping
- ✅ Rate limiting per endpoint
- ✅ Secure headers (HSTS, CSP, X-Frame-Options)
- ✅ Authentication & authorization checks
- ✅ Secret masking in logs
- ✅ Path traversal prevention
- ✅ SSRF validation

### Frontend Security
- ✅ Content Security Policy (CSP)
- ✅ Secure cookie flags
- ✅ Input validation
- ✅ HTTPS enforcement
- ✅ No hardcoded secrets

## Monitoring & Logging

### Log Locations
```
backend/
  logs/
    ├── app.log           # Application logs
    ├── security.log      # Security-relevant logs
    └── error.log         # Error traces

tests/
  ├── test_*.log         # Test execution logs
```

### Monitoring Endpoints
```python
# Health check
GET /api/health

# API metrics
GET /api/metrics

# Status dashboard
GET /api/admin/status
```

### Alerting
Configure monitoring for:
- Authentication failures
- Authorization violations
- Database errors
- API rate limit breaches
- File system access issues

## Database Management

### SQLite (Development)
```bash
# Location
data/cache/app.db

# Backup
cp data/cache/app.db data/cache/app.db.backup

# Migrations
python backend/core/database.py migrate
```

### PostgreSQL (Production)
```sql
-- Create database
CREATE DATABASE mynd_production;

-- Create user
CREATE USER mynd_user WITH PASSWORD '***';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE mynd_production TO mynd_user;
```

## Backup & Recovery

### Automated Backups
```bash
#!/bin/bash
# Daily backup script
BACKUP_DIR="/backups/mynd"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Database
cp data/cache/app.db \
   "$BACKUP_DIR/app_$TIMESTAMP.db"

# Configuration
tar -czf "$BACKUP_DIR/config_$TIMESTAMP.tar.gz" \
    data/config/

# Cleanup old backups (30 days)
find "$BACKUP_DIR" -mtime +30 -delete
```

### Recovery
```bash
# Restore database
cp backups/app_TIMESTAMP.db data/cache/app.db

# Restore configuration
tar -xzf backups/config_TIMESTAMP.tar.gz
```

## Performance Optimization

### Caching Strategy
```python
# Redis caching (if available)
from functools import lru_cache

@lru_cache(maxsize=128)
def get_user_tasks(user_id):
    return query_tasks(user_id)
```

### Database Indexing
```sql
CREATE INDEX idx_user_tasks ON tasks(user_id, created_at);
CREATE INDEX idx_nextcloud_path ON files(path);
```

### API Response Compression
```python
# Enable GZIP compression
from flask import Flask
app = Flask(__name__)
app.config['COMPRESS_LEVEL'] = 6  # 1-9
```

## Scaling Considerations

### Horizontal Scaling
- Stateless backend nodes
- Shared database (PostgreSQL)
- Load balancer (nginx, HAProxy)
- Distributed caching (Redis)

### Vertical Scaling
- Increase backend workers (gunicorn -w 8)
- Database optimization (indexes, partitioning)
- Memory allocation for API server

## CI/CD Pipeline

### GitHub Actions (.github/workflows/ci.yml)
1. **Lint & Format**
   - Python: flake8, black
   - JavaScript: ESLint, Prettier

2. **Tests**
   - Unit tests (pytest)
   - Integration tests
   - Security tests

3. **Security Scan**
   - Dependency audit
   - SAST scanning
   - Secret scanning

4. **Build & Deploy**
   - Docker image build
   - Registry push
   - Kubernetes deployment (if applicable)

## Troubleshooting

### Backend won't start
```bash
# Check Python version
python --version  # Should be 3.11+

# Check dependencies
pip install -r backend/requirements.txt

# Check database connection
python -c "from backend.core.database import db; print(db)"
```

### Frontend build failures
```bash
# Clear node_modules
rm -rf frontend/node_modules package-lock.json
npm install

# Check Node version
node --version  # Should be 18+
```

### Integration client errors
```bash
# Check credentials in .env
grep "NEXTCLOUD\|IMMICH" .env

# Test connectivity
python scripts/debug/debug_nextcloud.py
```

---

**Last Updated:** April 2026
