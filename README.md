# 🧠 MYND

**Local-first AI workspace** — Chat, search, automate, browser automation, smart home control, and sub-agent delegation — all running on your own hardware.

![GitHub last commit](https://img.shields.io/github/last-commit/SchBenedikt/mynd)
![Python](https://img.shields.io/badge/python-3.14%2B-blue)
![Node](https://img.shields.io/badge/node-22%2B-green)

<p align="center">
  <img src="screenshots/login.png" alt="Login" width="280" />
  <img src="screenshots/app-main.png" alt="Chat Interface" width="280" />
  <img src="screenshots/chat-response.png" alt="Chat with AI Response" width="280" />
</p>

MYND combines a conversational AI agent with personal knowledge retrieval, file generation, photo search, smart-home control, automations, browser automation, and a plugin system — fully local, no cloud dependency.

---

## ✨ Features

| | |
|---|---|
| **💬 Agentic Chat** | Streaming AI chat with tool-calling, multi-round planning, sub-agent delegation |
| **🧠 Knowledge Base** | Semantic search across your documents (Ollama embeddings) |
| **🌐 Web Research** | DuckDuckGo search, news aggregation, multi-source research |
| **🗺️ Browser Automation** | Headless Playwright + agent-browser CLI — [128 tools total](features.md) |
| **📷 Photo Search** | Semantic photo search via Immich |
| **🏠 Smart Home** | Home Assistant — lights, switches, sensors, cameras, scenes, scripts |
| **📅 Productivity** | CalDAV calendars & tasks (Nextcloud), timer reminders |
| **📧 Email** | IMAP/SMTP integration for reading & sending |
| **🤖 Automations** | Cron-based automations, daily briefing, scheduled actions |
| **🔌 Plugin System** | Extensible registry — install from GitHub, toggle at runtime |
| **🔐 Vault** | Encrypted credential storage for API keys, passwords, configs |
| **🛡️ Auth** | Password-based login, configurable registration, role-based access |
| **🎨 Themes** | 7 color themes × light/dark/modes |
| **🌐 Multi-language** | UI in 12 languages: DE, EN, FR, ES, IT, PT, NL, PL, TR, RU, JA, ZH |

> All 128 AI-callable tools documented in **[features.md](features.md)** — agentic capabilities, browser automation, and all integrations.

---

## 🚀 Quick Start

```bash
git clone https://github.com/SchBenedikt/mynd.git
cd mynd

# Backend
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
playwright install chromium      # only for browser automation

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
│   ├── ollama_client.py    ← Ollama / OpenAI API client with tool-calling support
│   ├── tools.py            ← Core tools: bash, ssh, web, memory, vault, delegate, plan, agent-browser
│   ├── vault.py            ← Encrypted credential storage
│   ├── plugin_base.py      ← Plugin discovery & hot-reload
│   └── ...
├── data/                   ← Runtime data (gitignored): vault, configs, uploads
│   └── plugins/            ← Built-in integrations (Browser, HA, Nextcloud, Immich, …)
├── frontend/               ← Next.js 16 / React 19 application
│   ├── app/                ← Pages, layout, globals.css
│   ├── components/         ← Reusable UI components
│   │   └── BrowserPreview.js  ← Screenshot viewer in LiveTools
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
                              ├──> Tools (bash, ssh, web, files, …)
                              ├──> Browser (Playwright + agent-browser)
                              ├──> Plugins (HA, Nextcloud, Immich, …)
                              └──> Vault (credentials, encrypted)
```

For a complete reference of all 128 AI-callable tools (agentic capabilities, browser automation, integrations), see **[features.md](features.md)**.

---

## 💡 Usage Examples

```bash
# Start the system
make dev

# Then open http://localhost:3000 and try:
#   "Open spiegel.de and take a screenshot"
#   "What's in the news today?"
#   "Find the photo from last summer in Italy"
#   "Show me my calendar for this week"
#   "Compare server load between TrueNAS and Proxmox"
#   "Create a plan: backup Nextcloud, update all containers, send report"
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
- **Language** — 12 languages available

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
playwright install chromium   # for browser automation
```

---

## 🛡️ Security & Privacy

### Data Locality

MYND is **local-first**: your credentials, files, and configuration stay on your machine. However, some features intentionally communicate with external services:

| Feature | Data Sent | External Service |
|---|---|---|
| **Web Search** | Search query | DuckDuckGo |
| **News Fetch** | None (pulls RSS feeds) | Tagesschau, Heise, etc. |
| **Web Browsing** | Target URL | Requested websites |
| **AI Model** | Conversations | Configurable Ollama / OpenAI endpoint |
| **Email** | Credentials + messages | Your IMAP/SMTP server |
| **Smart Home** | API commands | Your Home Assistant instance |
| **Immich** | Search queries | Your Immich server |

> ⚠️ When using cloud-based AI providers (OpenAI, etc.), your conversation text is sent to their API. For full local operation, use Ollama with a local model.

### Security

- Passwords stored as **salted hashes** (werkzeug)
- Integration credentials in **local encrypted vault**
- **Role-based access** (admin / user)
- **Configurable registration** — disabled by default
- CSRF protection via token-based auth
- All `/api/` routes authenticated by default
- Tool confirmation required for privileged actions
- Audit log for all privileged tool calls (`data/audit.jsonl`)

> **Run only in a trusted environment.** MYND can execute shell commands, SSH into remote hosts, control smart home devices, and automate browsers.

---

## 📄 License

[MIT](LICENSE) — feel free to use, modify, and share.
