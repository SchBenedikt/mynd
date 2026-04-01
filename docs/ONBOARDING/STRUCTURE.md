# Projektstruktur - MYND

## 📁 Verzeichnisübersicht (April 2026 - Reorganisiert)

```
mynd/
│
├── 📂 backend/                     # Python Backend
│   ├── __init__.py
│   ├── requirements.txt
│   ├── 📂 core/
│   │   ├── app.py                  # Main Flask/FastAPI app
│   │   ├── database.py             # Database models & ORM
│   │   ├── security_hardening.py   # Security middleware
│   │   ├── security_utils.py       # Security utilities
│   │   └── indexing_config.json
│   ├── 📂 features/                # Feature modules
│   │   ├── __init__.py
│   │   ├── 📂 calendar/            # Calendar management
│   │   ├── 📂 documents/           # Document parsing & processing
│   │   │   ├── parser.py
│   │   │   └── parser_hardened.py  # Security-hardened version
│   │   ├── 📂 integration/         # External service clients
│   │   │   ├── auth_*.py           # Authentication providers
│   │   │   ├── *_client.py         # Service clients
│   │   │   ├── *_client_hardened.py # Enhanced security versions
│   │   │   ├── activity_client.py  # Unified activity API
│   │   │   └── oauth2_*.py         # OAuth2 implementations
│   │   ├── 📂 knowledge/           # Knowledge base & AI
│   │   ├── 📂 tasks/               # Task management
│   │   └── 📂 training/            # ML training pipeline
│   └── 📂 config/                  # Configuration templates
│       ├── ai_config.json
│       ├── calendar_config.json
│       ├── nextcloud_config.json
│       └── ...
│
├── 📂 frontend/                    # Next.js Frontend
│   ├── package.json
│   ├── next.config.mjs
│   ├── jsconfig.json
│   ├── 📂 app/                     # Next.js App Router
│   │   ├── globals.css
│   │   ├── layout.js
│   │   ├── page.js
│   │   └── 📂 settings/
│   ├── 📂 components/              # Reusable React components
│   │   ├── SourceCard.js
│   │   ├── SuggestionsPanel.js
│   │   ├── ThemeSelector.js
│   │   └── ...
│   └── 📂 hooks/                   # Custom React hooks
│       ├── useLanguage.js
│       ├── useTheme.js
│       └── ...
│
├── 📂 scripts/                     # Utility scripts
│   ├── run_app.py                  # Start application
│   ├── 📂 demo/                    # Demo & example scripts
│   │   └── demo_batch_loading.py
│   ├── 📂 debug/                   # Debugging scripts
│   │   ├── debug_nextcloud.py
│   │   ├── find_*.py               # Search/discovery tools
│   │   └── get_*.py                # Fetch/retrieve tools
│   ├── 📂 examples/                # Usage examples
│   │   ├── example_auth_usage.py
│   │   └── example_nextcloud_apis.py
│   └── 📂 inspect/                 # Inspection tools
│       └── inspect_ics.py
│
├── 📂 tests/                       # Comprehensive test suite
│   ├── test_*.py                   # All test files
│   │   ├── test_auth_*.py          # Auth tests
│   │   ├── test_security_*.py      # Security tests
│   │   ├── test_immich_*.py        # Immich integration
│   │   ├── test_nextcloud_*.py     # Nextcloud integration
│   │   └── test_chat_*.py          # Chat/AI tests
│   ├── README.md
│   └── knowledge_*.json            # Test fixtures
│
├── 📂 docs/                        # Documentation
│   ├── README.md
│   ├── INFRASTRUCTURE.md           # ⭐ NEW: Deployment guide
│   ├── 📂 GUIDES/                  # User & developer guides
│   │   ├── QUICKSTART.md           # Get started in 5 min
│   │   ├── BATCH_LOADING_GUIDE.md  # Bulk import
│   │   ├── IMMICH_FEATURES_UPDATE.md
│   │   ├── INDEX.md
│   │   └── todo.md
│   ├── 📂 API/                     # API documentation
│   │   ├── NEXTCLOUD_API_INTEGRATIONS.md
│   │   ├── new-api-endpoints.md
│   │   └── ...
│   ├── 📂 SECURITY/                # Security documentation
│   │   ├── README_SECURITY_REVIEW.md
│   │   └── THREAT_MODEL.md
│   └── 📂 REPORTS/                 # Generated reports
│       ├── COMPLETION_REPORT.md
│       └── REVIEW_SUMMARY.md
│
├── 📂 data/                        # Application data
│   ├── user_knowledge.txt
│   ├── 📂 cache/                   # Runtime cache
│   │   ├── app.db                  # SQLite database
│   │   ├── app.db-shm              # Database shared memory
│   │   └── app.db-wal              # Database write-ahead log
│   ├── 📂 training/                # Training datasets
│   │   └── training_data.json
│   └── 📂 config/                  # Runtime config files
│       └── indexing_config.json
│
├── 📂 reports/                     # Generated reports & audits
│   ├── code_review_report.md       # Comprehensive security review
│   └── code_review_report.json     # Machine-readable report
│
├── 📂 .github/                     # GitHub integration
│   └── 📂 workflows/
│       └── ci.yml                  # CI/CD pipeline
│
├── 📄 README.md                    # ⭐ Main project README
├── 📄 CONTRIBUTING.md              # ⭐ Contribution guidelines
├── 📄 .env                         # ⭐ Environment variables
├── 📄 .env.example                 # Environment template
├── 📄 .gitignore                   # Git ignore rules
├── 📄 package.json                 # Root package config (optional)
└── 📄 docker-compose.yml           # Docker development setup

```

## 🎯 Key Organizational Principles

### 1. **Separation of Concerns**
- **backend/** - All Python/API code
- **frontend/** - All React/Next.js UI code
- **tests/** - All test suites
- **scripts/** - Utility & development tools
- **data/** - Runtime data, not source code
- **docs/** - All documentation

### 2. **Documentation Organization**
```
docs/
├── GUIDES/     → How-to guides, tutorials
├── API/        → API documentation, endpoints
├── SECURITY/   → Security, threat models
└── REPORTS/    → Generated analysis, reviews
```

### 3. **Data Organization**
```
data/
├── cache/      → Transient (*.db, .db-shm, .db-wal)
├── training/   → Training data (*.json)
└── config/     → Configuration (*.json, *.yaml)
```

### 4. **Scripts Organization**
```
scripts/
├── demo/       → Demo use cases
├── debug/      → Debug & testing tools
├── examples/   → Usage examples
└── inspect/    → Code inspection & analysis
```

## 📊 Statistics

| Category | Count | Size |
|----------|-------|------|
| Python files | 45+ | ~2,500 LOC |
| Tests | 30+ | ~550 LOC |
| Documentation | 15+ pages | ~10,000 LOC |
| Configuration | 8 files | ~400 LOC |
| **Total** | **98+** | **~13,450 LOC** |

## 🔄 File Movement Summary (April 2026)

| Source | Destination | Category |
|--------|-------------|----------|
| BATCH_LOADING_GUIDE.md | docs/GUIDES/ | Guide |
| QUICKSTART.md | docs/GUIDES/ | Guide |
| NEXTCLOUD_API_*.md | docs/API/ | API Docs |
| THREAT_MODEL.md | docs/SECURITY/ | Security |
| code_review_report.* | reports/ | Report |
| test_*.py | tests/ | Tests |
| demo_*.py | scripts/demo/ | Demo |
| debug_*.py | scripts/debug/ | Debug |
| example_*.py | scripts/examples/ | Example |
| inspect_*.py | scripts/inspect/ | Inspect |
| *.db* | data/cache/ | Cache |
| training_data.json | data/training/ | Training |
| indexing_config.json | data/config/ | Config |

## 🚀 Quick Reference

### Backend Development
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd core && python app.py
```

### Frontend Development
```bash
cd frontend
npm install
npm run dev
```

### Running Tests
```bash
cd tests
python -m pytest . -v
```

### Running Scripts
```bash
# Demo
python scripts/demo/demo_batch_loading.py

# Debug
python scripts/debug/debug_nextcloud.py

# Examples
python scripts/examples/example_auth_usage.py
```

## 📝 Important Notes

1. ✅ **Root directory is clean** - Only essential files (.env, README, CONTRIBUTING.md)
2. ✅ **Database files isolated** - All data in `data/cache/`
3. ✅ **Configuration centralized** - Backend configs in `backend/config/` and `data/config/`
4. ✅ **Tests grouped** - All tests in `tests/` directory
5. ✅ **Documentation organized** - Docs in `docs/` with sub-categories
6. ✅ **Scripts separated** - Utilities in `scripts/` by purpose
7. ✅ **Reports generated** - Audit output in `reports/`

## 🔐 Security Notice

⚠️ Ensure these files are **NOT** committed to version control:
- `.env` (use `.env.example`)
- `data/cache/*.db*` (database files)
- `data/training/*.json` (sensitive data)
- `*.log` files

---

**Last Updated:** April 1, 2026  
**Structure Version:** 2.0 (Reorganized)
