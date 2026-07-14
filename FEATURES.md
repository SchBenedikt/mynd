# MYND feature reference

This document describes the user-facing capabilities currently represented by the MYND backend and web application. A feature may require an optional dependency, local service, or integration account. Features marked **experimental** can have incomplete provider-specific operations.

## AI chat and agent runtime

MYND provides streaming and non-streaming chat, model selection, multi-round tool calling, conversation summaries, response source cards, generated-file cards, and research statistics. The agent can reason through multi-step work, build plans, delegate focused subtasks, ask the user for missing input, and request confirmation before privileged tool calls.

The default model runtime is Ollama. An OpenAI-compatible endpoint can be selected in settings. Tool support depends on the chosen model. Models without native tool calling use a reduced workflow.

## Knowledge and memory

- Semantic search across indexed documents using local embeddings.
- Source inventory, index status, reloading, and embedding rebuild operations.
- Knowledge-graph visualization for relationships in indexed content.
- Persistent key/value memory with create, read, and delete controls.
- Document ingestion scripts for local or Nextcloud-backed content.

Memory and document context can be included in model requests. If a remote model is configured, that selected context may be transferred to the provider.

## Research and browsing

- DuckDuckGo-backed web and image search.
- Multi-source news retrieval.
- Playwright browser tools for navigation, clicking, typing, selecting, scrolling, extraction, screenshots, PDF export, tabs, cookies, viewport changes, mobile emulation, network logs, performance data, dialogs, accessibility trees, and Shadow DOM inspection.
- Inline browser screenshot previews in chat.
- Generic HTTP requests with Basic Authentication.

The generic HTTP tool accepts only HTTP(S), validates every redirect target, blocks private/reserved addresses by default, and never disables TLS verification automatically. Administrators can allow required internal hosts with `MYND_HTTP_ALLOW_PRIVATE_HOSTS`.

## Files and generated artifacts

The agent can read and write text files inside `MYND_WORKSPACE_DIR`. Canonical-path checks prevent traversal and symlink escapes outside this directory. Uploads and generated artifacts can be displayed in chat. Python and shell tools can also create output, but they are powerful capabilities and should only be enabled in a trusted deployment.

## Integrations

### Nextcloud

WebDAV file operations, CalDAV queries and event creation, VTODO queries and task creation, contact search, and setup/configuration views are available. Event and task editing, Talk webhooks, and the browser-based Nextcloud Login Flow are currently marked unavailable rather than reporting false success.

### Immich

Configure and test an Immich connection, run semantic photo searches, and display thumbnails or original assets in the MYND interface.

### Home Assistant

Inspect entities and control supported lights, switches, scenes, scripts, sensors, and cameras through the plugin tool registry.

### Email

Configure IMAP and SMTP accounts, test connections, list folders, search/read mail, manage multiple accounts, and send messages. Sending from a context card uses the same backend SMTP implementation as the agent email tool.

### Infrastructure and cameras

Plugins provide tools for TrueNAS, Reolink, SSH-managed hosts, and generic REST APIs. SSH verifies host keys against the user's normal `known_hosts` file. Password authentication uses `sshpass` environment input so the password is not included in the command line.

## Productivity and automation

- Calendar views for today, tomorrow, a week, next week, or a named day.
- Event and task creation through Nextcloud.
- Timers and reminders.
- Cron-based automations with create, update, delete, test, history, and schema endpoints.
- Optional briefing and suggestion surfaces.

Provider-specific editing operations that are not implemented return HTTP 501 so the UI can show a clear unavailable state.

## Authentication and administration

- Setup wizard for the first administrator account and model configuration.
- Password hashing with Werkzeug and transparent migration from legacy plaintext records.
- Bearer-token login, logout, profile changes, registration control, and role-based administration.
- API authentication is deny-by-default after setup; only health, setup status, login, registration, and public auth configuration are exempt.
- User creation, deletion, and password reset for administrators.
- Backup export/import and full application reset controls.

The frontend automatically attaches the current token to API requests and immediately returns to the login page when a token is rejected.

## Internationalization and accessibility

The language selector supports German, English, French, Spanish, Italian, Portuguese, Dutch, Polish, Turkish, Russian, Japanese, and Chinese. Core navigation and workspace strings have native translations. The login flow also follows the selected language, with English fallback for untranslated strings. The document language is updated at runtime for assistive technology.

The interface includes responsive layouts, keyboard-compatible controls, accessible labels in key workflows, light/dark modes, seven theme families, configurable contrast, and reduced or dynamic motion options.

## Voice and text to speech

Browser speech recognition and speech synthesis are supported where the browser exposes them. Provider-backed server TTS routes explicitly return “not configured” until a server provider is implemented; the client can use browser speech synthesis instead.

## Plugin system

MYND discovers built-in plugins and exposes their tools through a shared registry. Plugins can be enabled, disabled, installed, or removed at runtime. Remote plugins execute code and therefore require the same trust as the backend itself; use only audited sources. Strong process/container isolation is not yet guaranteed.

## Security boundaries and known limitations

MYND sanitizes the browser rendering path by leaving raw HTML disabled and adds browser security headers. Privileged tool confirmations stop execution while approval is pending. File, HTTP, SSH, authentication, and secret-redaction safeguards provide defense in depth.

The shell and Python tools are not a container sandbox, and plugin imports are not isolated from the backend process. Multi-user deployments should disable those tools or place the whole backend inside a hardened container with restricted mounts, networking, users, and resource limits. See [SECURITY.md](SECURITY.md) and the open GitHub security issues for the current hardening roadmap.
