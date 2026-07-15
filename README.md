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
| **🗺️ Browser Automation** | Headless Playwright + agent-browser CLI — open pages, click, type, scroll, extract, screenshot, PDF export |
| **📷 Photo Search** | Semantic photo search via Immich |
| **🏠 Smart Home** | Home Assistant — lights, switches, sensors, cameras, scenes, scripts |
| **📅 Productivity** | CalDAV calendars & tasks (Nextcloud), timer reminders |
| **📧 Email** | IMAP/SMTP integration for reading & sending |
| **🤖 Automations** | Cron-based automations, daily briefing, scheduled actions |
| **🔌 Plugin System** | Extensible registry — install from GitHub, toggle at runtime |
| **🔐 Vault** | Encrypted credential storage for API keys, passwords, configs |
| **🧩 Sub-Agent Delegation** | `delegate()` spawns focused sub-agents for complex sub-tasks |
| **📋 Multi-Step Planning** | `create_plan()` + `think()` auto-detect complex tasks and build structured plans |
| **🛡️ Auth** | Password-based login, configurable registration, role-based access |
| **🎨 Themes** | 7 color themes × light/dark/modes |
| **🌐 Multi-language** | UI in 12 languages: DE, EN, FR, ES, IT, PT, NL, PL, TR, RU, JA, ZH |

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

### Agentic Workflow

```
User query → Think() (auto-detects complexity → plan) →
  Web research / Docs search / Browse / Delegate sub-tasks →
  Synthesize results → Respond with sources
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

---

## 🤖 Agentic Capabilities

MYND uses a **multi-round tool-calling loop** with advanced agentic features:

| Capability | Tool | Description |
|---|---|---|
| **Strategic Thinking** | `think()` | Always called first — auto-detects complexity and creates plans |
| **Multi-Step Planning** | `create_plan()` | Structured plans with step-by-step tracking |
| **Sub-Agent Delegation** | `delegate()` | Spawns focused sub-agents for complex sub-tasks |
| **Web Research** | `web_search()`, `fetch_news()` | DuckDuckGo + multi-source news |
| **Browser Automation** | `browser_*()` (29 tools) + `agent_browser()` | Open, click, type, scroll, extract, screenshot |
| **API Access** | `http_request()` | Any REST API with Basic Auth, self-signed certs |
| **Remote Execution** | `execute_ssh()` | Commands on remote hosts via SSH |
| **Code Execution** | `execute_python()`, `execute_bash()` | Run code in safe sandbox or directly |
| **Memory** | `memory_set/get/delete` | Persistent cross-session knowledge |
| **User Interaction** | `prompt_user()` | Ask for input when uncertain |
| **Credential Vault** | `vault_get/set/delete/list` | Encrypted storage for secrets |

---

## 🗺️ Browser Automation (29 Playwright Tools + agent-browser)

Headless Chromium via Playwright with anti-detection stealth, plus `agent-browser` CLI for quick tasks:

| Tool | Purpose |
|---|---|
| `browser_open` | Navigate to URL with optional ad blocking & cookie consent |
| `browser_click` / `browser_type` / `browser_select` | Interact with page elements |
| `browser_extract` | Extract text, tables, or Markdown from current page |
| `browser_screenshot` | Capture screenshot (full page or element) |
| `browser_search` | Search engine query (Google, DuckDuckGo, Bing) |
| `browser_pdf` | Export page to PDF |
| `browser_new_tab` / `browser_switch_tab` / `browser_close_tab` | Multi-tab management |
| `browser_scroll` / `browser_hover` / `browser_wait_for` | Navigation & waiting |
| `browser_fill_form` | Auto-fill entire forms |
| `browser_intercept` | Block ads / trackers via network interception |
| `browser_cookies` / `browser_set_viewport` | Browser state management |
| `browser_mobile_emulate` | Emulate mobile device viewports |
| `browser_get_performance` / `browser_network_log` | Debugging & metrics |
| `browser_get_shadow_dom` / `browser_accessibility_snapshot` | Advanced DOM access |
| `browser_dialog_handler` | Auto-accept alerts/confirm/prompt dialogs |
| `agent_browser()` | Simplified CLI wrapper — goto, click, type, snapshot, screenshot |

Screenshots are displayed inline in the chat via `BrowserPreview` component.

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

## 🛡️ Security

- Passwords stored as **salted hashes** (werkzeug)
- Integration credentials in **local encrypted vault**
- **Role-based access** (admin / user)
- **Configurable registration** — disabled by default
- CSRF protection via token-based auth
- All data stays **on your machine** — no cloud egress

> **Run only in a trusted environment.** MYND can execute shell commands, SSH into remote hosts, control smart home devices, and automate browsers.

---

## 📄 License

[MIT](LICENSE) — feel free to use, modify, and share.
