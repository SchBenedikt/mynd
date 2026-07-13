# 🧠 MYND

**Local-first AI workspace** — Chat, search, automate, and control your smart home, all running on your own hardware.

![GitHub last commit](https://img.shields.io/github/last-commit/SchBenedikt/mynd)
![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![Node](https://img.shields.io/badge/node-22%2B-green)

MYND combines a conversational AI agent with personal knowledge retrieval, file generation, photo search, smart-home control, automations, and a plugin system — fully local, no cloud dependency.

---

## ✨ Features

| | |
|---|---|
| **💬 Chat & Agent** | Streaming AI chat with tool-calling, web research, document Q&A |
| **🧠 Knowledge Base** | Semantic search across your documents (Ollama embeddings) |
| **📷 Photo Search** | Semantic photo search via Immich (self-hosted Google Photos alternative) |
| **🏠 Smart Home** | Home Assistant integration — lights, switches, sensors, cameras |
| **📅 Productivity** | CalDAV calendars & tasks (Nextcloud), timer reminders |
| **📧 Email** | IMAP/SMTP integration for reading & sending |
| **🤖 Automations** | Cron-based automations, daily briefing, scheduled actions |
| **🔌 Plugin System** | Extensible registry — install from GitHub, toggle at runtime |
| **🛡️ Auth** | Password-based login, configurable registration, role-based access |
| **🎨 Themes** | 7 color themes × light/dark modes |
| **🌐 Multi-language** | UI in German & English |

---

## 🚀 Quick Start

```bash
git clone https://github.com/SchBenedikt/mynd.git
cd mynd

# Backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'

# Frontend
npm install && npm install --prefix frontend

# Start both
make dev
```

Open **http://localhost:3000**. The API runs at `http://127.0.0.1:5001`.

On first launch, the admin password is printed to the backend log. Change it immediately in **Settings → Profile**.

---

## 📦 Requirements

- **Python** 3.12+
- **Node.js** 22+ / npm 10+
- **Ollama** (optional) — for local embeddings & inference

---

## 🏗️ Architecture

```
mynd/
├── app.py                  ← Flask API, auth, agent orchestration, SSE streaming
├── core/                   ← Model client, retrieval, tools, vault, scheduler, plugins
│   ├── ollama_client.py
│   ├── tools.py
│   ├── vault.py
│   ├── plugin_base.py
│   └── ...
├── data/                   ← Runtime data (gitignored): vault, configs, uploads
│   └── plugins/            ← Built-in integrations (Home Assistant, Nextcloud, Immich, …)
├── frontend/               ← Next.js 16 / React 19 application
│   ├── app/                ← Pages, layout, globals.css
│   ├── components/         ← Reusable UI components
│   ├── hooks/              ← Custom React hooks
│   └── lib/                ← API fetch helpers, contexts
├── scripts/                ← Document sync & ingestion
└── tests/                  ← Backend pytest suite
```

### Data Flow

```
Browser ──HTTP/SSE──> Flask API ──> Ollama / OpenAI
                              │
                              ├──> Knowledge Base (embeddings)
                              ├──> Tools (search, home, files, …)
                              ├──> Plugins (HA, Nextcloud, Immich, …)
                              └──> Vault (credentials, encrypted)
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `OLLAMA_BASE_URL` | Ollama API endpoint | `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | Default chat model | `gemma3:latest` |
| `CORS_ALLOWED_ORIGINS` | Allowed frontend origins | `http://localhost:3000` |
| `NEXTCLOUD_URL` | Nextcloud instance URL | — |
| `NEXTCLOUD_USERNAME` | Nextcloud username | — |
| `NEXTCLOUD_PASSWORD` | Nextcloud app password | — |

See [.env.example](.env.example) for all options.

### Settings UI

Most configuration is available from the web UI:
- **AI Provider** — Ollama, OpenAI-compatible
- **Integrations** — Nextcloud, Home Assistant, Immich, Reolink, TrueNAS, Email
- **Theme** — 7 color themes, light/dark/auto
- **Users** — Registration toggle, role management
- **Indexing** — Document sync & embedding

---

## 🧪 Development

```bash
make test              # Backend tests (pytest)
make frontend-lint     # Frontend lint (next build)
make check             # Full CI check
make clean             # Remove caches & build output
```

### Manual setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
npm install
npm install --prefix frontend
```

---

## 🛡️ Security

- Passwords stored as **salted hashes** (werkzeug)
- Integration credentials in **local encrypted vault**
- **Role-based access** (admin / user)
- **Configurable registration** — disabled by default
- CSRF protection via token-based auth
- All data stays **on your machine** — no cloud egress

> **Run only in a trusted environment.** MYND can execute shell commands and connect to private services.

---

## 📄 License

[MIT](LICENSE) — feel free to use, modify, and share.
