# MYND

MYND is a local-first AI workspace that combines chat, personal knowledge retrieval,
automations, file generation, photo search, and smart-home integrations in one web
application. The backend is built with Flask; the frontend uses Next.js and React.

> [!IMPORTANT]
> MYND can execute tools and connect to private services. Run it only in a trusted
> environment, review enabled plugins, and never commit your `.env` or `data/` directory.

## Highlights

- Local Ollama models and OpenAI-compatible providers
- Streaming chat, web research, document retrieval, and a knowledge graph
- Integrations for Nextcloud, Immich, Home Assistant, email, Reolink, and TrueNAS
- Automations, timers, daily briefings, and generated documents
- Authentication, configurable security controls, and an extensible plugin registry

## Requirements

- Python 3.12 or newer
- Node.js 22 or newer
- npm 10 or newer
- Optional: [Ollama](https://ollama.com/) for local inference

## Quick start

```bash
git clone <repository-url>
cd mynd-2new
cp .env.example .env
make setup
make dev
```

Open `http://localhost:3000`. The API runs at `http://127.0.0.1:5001`.
On a new installation, the backend writes the generated temporary administrator
password to its startup log. Change it immediately in the profile settings.

## Configuration

The application can be configured from the settings UI. Environment variables are
useful for the initial local setup:

| Variable | Purpose | Default |
| --- | --- | --- |
| `OLLAMA_BASE_URL` | Ollama API endpoint | `http://127.0.0.1:11434` |
| `OLLAMA_MODEL` | Initial chat model | `gemma3:latest` |
| `CORS_ALLOWED_ORIGINS` | Comma-separated trusted frontend origins | local port 3000 |
| `NEXTCLOUD_URL` | Nextcloud instance URL | — |
| `NEXTCLOUD_USERNAME` | Nextcloud username | — |
| `NEXTCLOUD_PASSWORD` | Nextcloud app password | — |

See [.env.example](.env.example) for document-sync settings. Secrets and runtime state
are stored locally below `data/`, which is intentionally ignored by Git.

## Architecture

```text
app.py                  Flask API, authentication, agent orchestration, streaming
core/                   model, retrieval, tools, vault, plugins, scheduler
data/plugins/           built-in service integrations (runtime directory is ignored)
frontend/               Next.js 16 / React 19 application
scripts/                document synchronization and ingestion utilities
tests/                  backend route and plugin regression tests
```

The browser talks to the Flask API. The agent combines core tools with enabled plugin
tools, while credentials remain in the local vault. Document embeddings are requested
from the configured Ollama endpoint.

## Development

```bash
make test              # backend test suite
make frontend-lint     # frontend static analysis
make check             # tests, frontend lint, and production build
make clean             # remove local caches and build output
```

For a dedicated Python environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
npm install
npm install --prefix frontend
```

Pull requests are checked with GitHub Actions on Python 3.12 and Node.js 22. More
details are in [CONTRIBUTING.md](CONTRIBUTING.md).

## Security

Passwords are stored as salted hashes. Existing installations using the older
clear-text format are migrated after a successful login. Authentication tokens and
integration credentials are still sensitive local data; back up and protect `data/`
accordingly. Please report vulnerabilities as described in [SECURITY.md](SECURITY.md).

## License

Licensed under the [MIT License](LICENSE).
