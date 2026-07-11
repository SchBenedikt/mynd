# MYND — Second Brain

A local-first AI assistant with smart home control, internet research, file generation, photo search, daily briefings, automations, a plugin system, local tool-calling fallback, and Python code execution.

## Features

- **Chat with any model** — Ollama (local) or OpenAI-compatible via API key
- **Web search** — DuckDuckGo (no API key needed) + RSS news feeds
- **Deep Research Mode** — multi-query search, cross-referencing, fact-checking, detailed analysis
- **76 tools** across 8 plugins: email, Home Assistant, Immich, Nextcloud, Python execution, Reolink, system, TrueNAS
- **Document RAG** — sync from Nextcloud, parse PDF/DOCX/MD, LightRAG index with graph retrieval
- **Plugin system** — Nextcloud (calendar/tasks/contacts), email (IMAP), Immich (photo search), Home Assistant (smart home), Reolink (cameras), TrueNAS (storage)
- **File generation** — Excel, Word, PowerPoint, HTML, CSV via Python execution
- **Settings** — AI provider, Nextcloud, Immich, Home Assistant, security mode, theme
- **Chat history** — editable messages, copyable responses, chat IDs in URL
- **Code syntax highlighting**, side-by-side images, file cards with download/preview

## Architecture

```
mynd-2new/
├── app.py                 # Flask backend (API routes, agent loop, SSE streaming)
├── core/
│   ├── config.py          # Paths, constants, OpenAI helpers
│   ├── embed.py           # Embedding (Ollama bge-m3)
│   ├── llm.py             # chat_with_tools + streaming
│   ├── model.py           # Model selection, tool support detection
│   ├── tools.py           # 18 core tools
│   ├── utils.py           # call_with_timeout utility
│   └── vault.py           # JSON key-value store
├── data/plugins/
│   ├── nextcloud.py       # Calendar, tasks, contacts
│   ├── email.py           # IMAP search, read, send
│   ├── immich.py          # Photo search, albums, people
│   ├── homeassistant.py   # Device status, control
│   ├── reolink.py         # Camera snapshot, PTZ
│   ├── truenas.py         # Pool, dataset, service status
│   └── python_exec.py     # Sandboxed Python execution
├── frontend/              # Next.js 16 + React 19
│   └── app/
│       ├── (main)/page.js     # Main chat page + SSE streaming
│       ├── (main)/layout.js   # Persistent sidebar layout
│       └── (main)/settings/   # Settings page
└── tests/                 # 76 pytest tests
```

## Quick Start

```bash
# Install dependencies
make setup

# Start both servers
make dev
# → Backend: http://localhost:5001
# → Frontend: http://localhost:3000
```

### Prerequisites

- Python 3.14+
- Node.js 22+
- Ollama (for local models)

## Configuration

### AI Provider

Configure in Settings (`/settings`):

| Provider | Base URL | API Key |
|----------|----------|---------|
| Ollama (local) | `http://127.0.0.1:11434` | – |
| OpenAI-compatible | any (e.g. `https://api.openai.com/v1`) | required |

### Environment Variables

```env
NEXTCLOUD_URL=https://your-nextcloud-instance.com
NEXTCLOUD_USERNAME=your_username
NEXTCLOUD_PASSWORD=your_password
LLM_MODEL=qwen2.5:7b
EMBEDDING_MODEL=nomic-embed-text
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

### Plugins

Configure via Settings UI or vault commands:
- **Nextcloud**: `vault_set nextcloud/url`, `vault_set nextcloud/username`, `vault_set nextcloud/password`
- **Immich**: `vault_set immich/url`, `vault_set immich/api-key`
- **Home Assistant**: `vault_set homeassistant/url`, `vault_set homeassistant/token`
- **Email**: `vault_set email/imap_server` etc.

## API Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/api/agent/query` | POST | AI query (non-streaming) |
| `/api/agent/query/stream` | POST | AI query (SSE streaming) |
| `/api/ai/models` | GET | Available models + tool support |
| `/api/ai/config` | GET/PUT | AI provider configuration |
| `/api/auth/profile` | GET/PUT | User profile |
| `/api/admin/users` | GET | List users |
| `/api/admin/reset` | POST | Reset entire application |
| `/api/knowledge/status` | GET | RAG index status |
| `/api/security/status` | GET | Security mode status |

## Plugins & Tools

### Core Tools (18)

| Tool | Description |
|------|-------------|
| `think` | Reasoning log |
| `web_search` | DuckDuckGo search |
| `fetch_news` | RSS/Atom news |
| `execute_python` | Python code in sandbox |
| `http_request` | HTTP requests |
| `execute_bash` | Shell commands (restricted) |
| `ssh_execute` | SSH on remote hosts |
| `file_read` / `file_write` | File I/O |
| `vault_get/set/delete/list` | Key-value store |
| `search_documents` | RAG full-text search |
| `get_date` | Current date/time |
| `ask_user_for_input` | Ask user for input |

### Plugin Tools (58)

- **Nextcloud** (15): calendar, tasks, contacts, file search, notifications
- **Home Assistant** (13): entity states, service calls, camera snapshots
- **TrueNAS** (13): pools, datasets, services, apps, alerts
- **Immich** (8): photo search, albums, people, timeline
- **Python Execution** (7): execute, create script, run, list, read, install, list packages
- **Reolink** (6): camera snapshot, PTZ control, system info
- **Email** (4): search, read, send, list folders
- **System** (11): save text, weather, timer, screenshot, briefing

## Development

```bash
make dev       # Start both servers
make test      # Run all tests
make lint      # Run ruff linter
make clean     # Clean build artifacts
```

## License

Private / internal.
