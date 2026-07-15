# MYND – Complete AI Tool Reference

This document lists **every function the AI agent can call**, grouped by category. Total: **128 tools** across 10 source files.

---

## Agentic Capabilities

MYND uses a **multi-round tool-calling loop** where the AI model autonomously decides which tools to invoke, processes results, and continues until a task is complete. The loop is driven by four core capabilities:

| Capability | Tool | Description |
|---|---|---|
| **Strategic Thinking** | `think()` | Always called first — auto-detects complexity and creates plans, then executes step by step |
| **Multi-Step Planning** | `create_plan()` | Builds structured plans with step-by-step tracking across multiple tool calls |
| **Sub-Agent Delegation** | `delegate()` | Spawns a focused sub-agent for a complex sub-task while the main agent continues working |
| **Web Research** | `web_search()` + `fetch_news()` + `image_search()` | DuckDuckGo search, news aggregation, image search |
| **User Interaction** | `prompt_user()` | Ask the user for input or clarification mid-conversation |
| **Memory** | `memory_get/set/delete` | Persistent cross-session knowledge the model can read and write |
| **Credential Vault** | `vault_get/set/delete/list` | Encrypted storage for API keys, passwords, and configs the model can access |
| **Remote Execution** | `execute_ssh()` | Execute commands on remote hosts via SSH |
| **Code Execution** | `execute_python()` / `execute_bash()` | Run Python or shell code, capture stdout/stderr |
| **API Access** | `http_request()` | Generic HTTP client for any REST API |
| **File Operations** | `read_local_file()` / `write_local_file()` | Read and write files inside the workspace |
| **Document Search** | `search_documents()` | Semantic search across indexed Nextcloud documents |

The agent automatically decides when to browse the web, search documents, execute code, control smart home devices, or delegate sub-tasks — all in a single conversation.

---

## 1. Core Agent Tools (`core/tools.py`) — 22 tools

Always available. Foundation of the agentic loop.

| Tool | Description |
|------|-------------|
| `think()` | First-step analysis; auto-creates plans for complex tasks (3+ steps or keywords) |
| `create_plan()` | Build a structured multi-step plan with tracking |
| `delegate()` | Spawn a focused sub-agent for a complex sub-task |
| `prompt_user()` | Ask the user interactively for input (supports secret masking) |
| `web_search()` | Internet search via DuckDuckGo |
| `fetch_news()` | Multi-source news retrieval with RSS fallback |
| `image_search()` | Image search via DuckDuckGo (thumbnails + source links) |
| `http_request()` | Generic HTTP client (REST APIs, page content, Basic Auth, self-signed certs) |
| `execute_bash()` | Run shell commands (with permission modes) |
| `execute_python()` | Execute Python code (captures stdout/stderr) |
| `execute_ssh()` | Run commands on remote hosts via SSH (host-key verification) |
| `search_documents()` | Semantic search across indexed Nextcloud documents |
| `read_local_file()` | Read a local file within `MYND_WORKSPACE_DIR` |
| `write_local_file()` | Write content to a local file within `MYND_WORKSPACE_DIR` |
| `vault_get()` | Read a stored credential/configuration value |
| `vault_set()` | Store a credential/configuration value |
| `vault_delete()` | Delete a stored credential/configuration value |
| `vault_list()` | List all stored values (grouped) |
| `memory_get()` | Read a persistent fact from cross-session memory |
| `memory_set()` | Store a persistent fact in memory |
| `memory_delete()` | Delete a persistent fact from memory |
| `agent_browser()` | Simplified browser CLI wrapper — goto, click, type, snapshot, screenshot, extract, back, scroll |

---

## 2. Playwright Browser Automation (`data/plugins/browser.py`) — 29 tools

Full browser automation via headless Chromium with stealth anti-detection, ad blocking, cookie-consent dismissal, and screenshot streaming.

| Tool | Description |
|------|-------------|
| `browser_open` | Navigate to URL with stealth, ad-blocking & cookie-consent dismissal |
| `browser_screenshot` | Capture screenshot (full page or element) |
| `browser_extract` | Extract content: text, links, images, tables, code, meta, readability, forms, structured data |
| `browser_click` | Click element by CSS selector (supports iframes) |
| `browser_type` | Type text into an input field |
| `browser_evaluate` | Execute JavaScript in page context |
| `browser_search` | Search web via real browser (DuckDuckGo, Google, Bing) |
| `browser_navigate` | Alias for browser_open |
| `browser_back` | Go back in browser history |
| `browser_forward` | Go forward in browser history |
| `browser_scroll` | Scroll page up/down by pixel amount |
| `browser_select` | Select a dropdown option |
| `browser_hover` | Hover over element (triggers menus/tooltips) |
| `browser_wait_for` | Wait for element (visible/attached/detached/hidden) |
| `browser_list_tabs` | List all open tabs |
| `browser_new_tab` | Open a new tab (optionally with URL) |
| `browser_switch_tab` | Switch to a tab by ID |
| `browser_close_tab` | Close a tab (or active tab) |
| `browser_fill_form` | Fill multiple form fields at once (JSON field map) |
| `browser_pdf` | Save current page as PDF |
| `browser_cookies` | Manage cookies: get, set, delete, clear |
| `browser_set_viewport` | Set browser viewport size |
| `browser_get_performance` | Page performance metrics + Core Web Vitals |
| `browser_network_log` | Log network requests (start/stop/get with domain filter) |
| `browser_mobile_emulate` | Emulate mobile device (iPhone, iPad, Pixel, Galaxy) |
| `browser_get_shadow_dom` | Extract Shadow DOM content |
| `browser_intercept` | Configure network interception (block domains, mock responses) |
| `browser_dialog_handler` | Auto-accept/dismiss JS dialogs (alert/confirm/prompt) |
| `browser_accessibility_snapshot` | Get accessibility tree of current page |

Screenshots are streamed to the chat UI in real time via the `BrowserPreview` component.

---

## 3. Nextcloud Integration (`nextcloud.py`) — 15 tools

File management, calendar, contacts, and tasks via WebDAV, CalDAV, CardDAV, and OCS APIs.

| Tool | Description |
|------|-------------|
| `nextcloud_list` | List folder contents (WebDAV) |
| `nextcloud_read_file` | Read file content (.md, .txt, .docx, .pdf) |
| `nextcloud_write_file` | Create or overwrite a file |
| `nextcloud_delete` | Delete a file or empty folder |
| `nextcloud_mkdir` | Create a new folder |
| `nextcloud_move` | Move/rename a file or folder |
| `nextcloud_request` | Arbitrary HTTP request to Nextcloud API (WebDAV/CalDAV/CardDAV/OCS) |
| `nextcloud_caldav_query` | Query calendar events from all calendars (optional date filter) |
| `nextcloud_caldav_create` | Create a new calendar event |
| `nextcloud_tasks_query` | Query tasks/todos from all calendars |
| `nextcloud_tasks_create` | Create a new task/todo |
| `nextcloud_contact_search` | Search contacts by name/email/phone across all address books |
| `nextcloud_contact_get` | Get a single contact by UID (full vCard) |
| `nextcloud_share_link` | Create a public share link for a file/folder |
| `nextcloud_search` | Full-text search in Nextcloud files (filename + content) |

---

## 4. Home Assistant Integration (`homeassistant.py`) — 13 tools

Smart home control: lights, switches, sensors, scenes, scripts, cameras.

| Tool | Description |
|------|-------------|
| `homeassistant_get_states` | List ALL entities filtered by domain (light/sensor/switch/'') |
| `homeassistant_get_state` | Get detailed state of a single entity |
| `homeassistant_find` | Search entities by name, room, or manufacturer |
| `homeassistant_turn_on` | Turn an entity ON |
| `homeassistant_turn_off` | Turn an entity OFF |
| `homeassistant_toggle` | Toggle an entity ON/OFF |
| `homeassistant_light_set` | Set light color, brightness, or color temperature |
| `homeassistant_call_service` | Call any Home Assistant service (domain/service/entity_id) |
| `homeassistant_list_scenes` | List all scenes (lighting moods) |
| `homeassistant_activate_scene` | Activate a scene |
| `homeassistant_list_scripts` | List all scripts/automations |
| `homeassistant_run_script` | Execute a script |
| `homeassistant_get_camera_snapshot` | Get live camera snapshot (Base64 image) |

---

## 5. TrueNAS Scale Integration (`truenas.py`) — 13 tools

Storage, services, alerts, apps, network, and system management via TrueNAS API v2.0.

| Tool | Description |
|------|-------------|
| `truenas_api_request` | Generic TrueNAS API v2.0 call (any endpoint) |
| `truenas_get_system_info` | System information (CPU, RAM, hostname, uptime, license) |
| `truenas_get_version` | Get TrueNAS version string |
| `truenas_list_pools` | List storage pools (size, usage, status, topology) |
| `truenas_list_datasets` | List datasets (size, compression, dedup, encryption) |
| `truenas_list_disks` | List physical disks (size, model, temperature, type) |
| `truenas_list_services` | List services (running/stopped status) |
| `truenas_list_alerts` | List active alerts (Critical, Warning, Info) |
| `truenas_list_shares` | List shares (NFS, SMB, iSCSI) |
| `truenas_list_users` | List users (UID, shell, groups, lock status) |
| `truenas_list_apps` | List installed apps (version, status) |
| `truenas_list_network` | List network interfaces (IP addresses, link state) |
| `truenas_check_update` | Check for available TrueNAS updates + release notes |

---

## 6. Immich Photo Search (`immich.py`) — 8 tools

Semantic photo search, album management, uploads, and server stats.

| Tool | Description |
|------|-------------|
| `immich_api_request` | Generic Immich API call (any of 270+ endpoints) |
| `immich_search_photos` | Search photos by text/person/date/smart search or random |
| `immich_list_albums` | List all albums with photo count and ID |
| `immich_get_album_photos` | List photos in a specific album |
| `immich_list_people` | List all recognized people |
| `immich_get_server_stats` | Server statistics (version, photo/video counts, storage) |
| `immich_upload_photo` | Upload a photo from a URL into Immich |
| `immich_create_album` | Create a new album |

---

## 7. System Tools (`system.py`) — 11 tools

Server information, timers, weather, and file saving.

| Tool | Description |
|------|-------------|
| `system_get_info` | Server information (disk, RAM, CPU, uptime, OS, Python version) |
| `system_get_disk_usage` | Disk usage of all important mountpoints |
| `system_get_processes` | Top processes by CPU usage |
| `system_get_network` | Network interfaces and IP addresses |
| `timer_set` | Set a timer/reminder (seconds/minutes/hours) |
| `timer_list` | Show all active and expired timers |
| `timer_remove` | Remove/delete a timer by ID |
| `weather_get` | Get current weather (HA sensors or Open-Meteo fallback) |
| `weather_forecast` | Get weather forecast for next 1–7 days |
| `web_search` | Internet search via DuckDuckGo (in-plugin variant) |
| `system_save_text` | Save text/content to a file in the generated/ directory |

---

## 8. Python Execution (`python_exec.py`) — 7 tools

Run, create, and manage Python scripts on the server.

| Tool | Description |
|------|-------------|
| `python_execute` | Execute Python code (subprocess with timeout, safety checks) |
| `python_create_script` | Create a Python script file for later execution |
| `python_run_script` | Run a saved Python script file |
| `python_list_scripts` | List all saved Python scripts with size and date |
| `python_read_script` | Show the content of a saved Python script |
| `python_install_package` | Install a Python package via pip |
| `python_list_packages` | List all installed Python packages (pip list) |

---

## 9. Email Integration (`email.py`) — 4 tools

IMAP/SMTP email reading and sending with multi-account support.

| Tool | Description |
|------|-------------|
| `email_search` | Search IMAP mailbox (FROM, SUBJECT, SINCE, UNSEEN, etc.) |
| `email_read` | Read an email by ID |
| `email_send` | Send an email via SMTP |
| `email_list_accounts` | List all configured email accounts |

---

## 10. Reolink Camera Integration (`reolink.py`) — 6 tools

Live snapshots, AI detection, RTSP streams, and recordings.

| Tool | Description |
|------|-------------|
| `reolink_get_channels` | List all Reolink cameras with online/sleep status |
| `reolink_get_snapshot` | Get snapshot from a camera (Base64) |
| `reolink_get_ai_state` | Get AI detection status (person/vehicle/animal) |
| `reolink_get_rtsp_url` | Get RTSP stream URL for live view |
| `reolink_get_device_info` | Device information (model, firmware, channels) |
| `reolink_get_records` | Get recordings for a channel on a specific date |

---

## Tool Registration

All tools above are registered in `AGENT_TOOLS` (app.py:123) and available to the AI model via function calling:

```
AGENT_TOOLS = [*CORE_TOOLS, *PLUGIN_TOOLS]
WEB_TOOL_MAP = {**CORE_MAP, **PLUGIN_TOOL_MAP, 'prompt_user': web_prompt_user}
```

**Total: 128 tools** (22 core + 106 plugin)
