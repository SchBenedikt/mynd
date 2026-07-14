# MYND

MYND is a local-first AI workspace for conversations, personal knowledge retrieval, research, browser automation, connected services, and scheduled workflows. The application runs on your hardware; optional model providers and integrations can still send data to services you configure.

[![CI](https://github.com/SchBenedikt/mynd/actions/workflows/ci.yml/badge.svg)](https://github.com/SchBenedikt/mynd/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12%2B-3776ab)
![Node.js](https://img.shields.io/badge/Node.js-22%2B-339933)
![License](https://img.shields.io/badge/license-MIT-blue)

![MYND language selection](screenshots/login.png)

## What you can do

- Chat with local Ollama models or an OpenAI-compatible provider.
- Search indexed documents semantically and inspect a knowledge graph.
- Research the web, automate a browser, and keep source links with answers.
- Connect Nextcloud, Immich, Home Assistant, email, TrueNAS, Reolink, and other APIs.
- Create calendar events, tasks, reminders, and scheduled automations.
- Store integration credentials in the local vault and manage users with role-based access.
- Use the interface in 12 languages and choose from multiple themes.

See [FEATURES.md](FEATURES.md) for a complete feature and integration reference.

![MYND chat workspace](screenshots/app-main.png)

## Quick start

Prerequisites: Python 3.12+, Node.js 22+, npm 10+, [uv](https://docs.astral.sh/uv/), and optionally [Ollama](https://ollama.com/).

```bash
git clone https://github.com/SchBenedikt/mynd.git
cd mynd

uv sync --locked --extra dev
npm install

# Required only for browser automation
uv run playwright install chromium

make dev
```

Open `http://localhost:3000`. The API listens on `http://127.0.0.1:5001` by default.

On a fresh installation, MYND opens the setup wizard. Create the administrator account there. Existing installations that predate the wizard write a temporary administrator password to the backend log; change it immediately under **Settings → Profile**.

## Configuration

Copy the example environment file before changing defaults:

```bash
cp .env.example .env
```

Important options:

| Variable | Purpose | Default |
|---|---|---|
| `OLLAMA_BASE_URL` | Ollama endpoint | `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | Default chat model | `gemma3:latest` |
| `CORS_ALLOWED_ORIGINS` | Comma-separated browser origins | localhost ports |
| `MYND_WORKSPACE_DIR` | Allowed root for AI file tools | `data/workspace` |
| `MYND_HTTP_ALLOW_PRIVATE_HOSTS` | Explicit private-host allowlist for the HTTP tool | empty |

Most model, indexing, user, integration, theme, and voice settings are available in the web interface.

## Local-first and data egress

“Local-first” means that MYND stores its application state on the machine where the backend runs and supports a fully local model stack. It does **not** mean that every configuration is offline.

| Capability | Possible external transfer |
|---|---|
| Local Ollama chat and embeddings | None, unless Ollama itself points elsewhere |
| OpenAI-compatible model provider | Prompts, selected context, and responses go to that provider |
| Web search and browser automation | Queries, visited URLs, form input, and normal network metadata go to visited services |
| Email, Nextcloud, Immich, Home Assistant, TrueNAS, Reolink | Requests and selected content go to the configured service |
| Generic HTTP and plugin tools | Data goes to the destination selected by the tool or plugin |

For offline operation, use a local model and local embeddings, disable external integrations, and avoid web/browser tools. Review [SECURITY.md](SECURITY.md) before exposing MYND beyond a trusted network.

## Development

```bash
make test            # Python tests
make lint            # Ruff
make typecheck       # Mypy
make frontend-lint   # ESLint
make check           # Tests, lint, and frontend build
```

The backend is a Flask application in `app.py`; reusable services live in `core/`, integrations in `data/plugins/`, the Next.js application in `frontend/`, and tests in `tests/`.

## Security notes

MYND can execute tools, control browsers, connect to remote systems, and send messages. Keep it on a trusted network, use strong credentials, enable only required integrations, and back up the sensitive `data/` directory securely. API routes are authenticated by default after setup, raw HTML in model output is not rendered, HTTP tool access to private networks requires an explicit allowlist, SSH host keys are verified, and file tools are confined to `MYND_WORKSPACE_DIR`.

These controls reduce risk but do not make arbitrary code execution or third-party plugins safe. Container-grade tool and plugin isolation remains recommended for high-risk or multi-user deployments.

## Contributing and license

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request. MYND is available under the [MIT License](LICENSE).
