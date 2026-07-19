'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import './guide.css';

const SECTIONS = [
  { id: 'architecture', icon: 'fa-sitemap', label_de: 'Architektur', label_en: 'Architecture' },
  { id: 'getting-started', icon: 'fa-rocket', label_de: 'Erste Schritte', label_en: 'Getting Started' },
  { id: 'ai-setup', icon: 'fa-brain', label_de: 'KI-Modelle', label_en: 'AI Models' },
  { id: 'security', icon: 'fa-shield-halved', label_de: 'Sicherheit & Modi', label_en: 'Security & Modes' },
  { id: 'nextcloud', icon: 'fa-cloud', label_de: 'Nextcloud', label_en: 'Nextcloud' },
  { id: 'immich', icon: 'fa-images', label_de: 'Immich', label_en: 'Immich' },
  { id: 'homeassistant', icon: 'fa-house-signal', label_de: 'Home Assistant', label_en: 'Home Assistant' },
  { id: 'email', icon: 'fa-envelope', label_de: 'E-Mail', label_en: 'Email' },
  { id: 'spotify', icon: 'fa-spotify', label_de: 'Spotify', label_en: 'Spotify' },
  { id: 'discord', icon: 'fa-discord', label_de: 'Discord', label_en: 'Discord' },
  { id: 'truenas', icon: 'fa-database', label_de: 'TrueNAS', label_en: 'TrueNAS' },
  { id: 'browser', icon: 'fa-globe', label_de: 'Browser', label_en: 'Browser' },
];

const GUIDE = {
  'architecture': {
    en: {
      title: 'Architecture',
      intro: 'MYND is a full-stack personal AI platform. Understanding the architecture helps you set it up correctly and get the most out of it.',
      steps: [
        { h: 'Overview', p: 'MYND consists of three main layers: a Python Flask backend (API server on port 5001), a Next.js frontend (web UI on port 3000), and a local AI model provider (Ollama or OpenAI-compatible API). All three can run on the same machine or be distributed across your network.' },
        { h: 'Backend (Flask)', p: 'The backend at `app/routes.py` handles all API requests: authentication, AI model communication, plugin management, file storage, vault/credentials, and the agent loop that orchestrates multi-tool AI reasoning. Plugins in `data/plugins/` extend the backend with 25+ tools across 11 integrations.' },
        { h: 'Frontend (Next.js)', p: 'The React-based UI at `frontend/` provides the chat interface, settings panels, plugin manager, and landing/marketing pages. It communicates with the backend via REST API calls and server-sent events (SSE) for real-time streaming of AI responses.' },
        { h: 'AI Agent Loop', p: 'When you ask a question, MYND: (1) sends your prompt + available tool definitions to the AI model, (2) the model decides which tools to call and with what arguments, (3) MYND executes each tool and feeds results back to the model, (4) the model produces the final answer. This loop runs up to 100 rounds per query.' },
        { h: 'Plugin System', p: 'Each integration (Nextcloud, Immich, etc.) is a self-contained plugin in `data/plugins/`. Plugins register tools with OpenAI-compatible function schemas. The system auto-discovers installed plugins at startup. You can write custom plugins in Python — see the Developers page.', tip: 'The system plugin (`system.py`) provides OS-level tools like timers, weather, web search, and disk monitoring — always available, no configuration needed.' },
      ],
    },
    de: {
      title: 'Architektur',
      intro: 'MYND ist eine Full-Stack Personal-AI-Plattform. Das Verständnis der Architektur hilft bei der Einrichtung und optimalen Nutzung.',
      steps: [
        { h: 'Überblick', p: 'MYND besteht aus drei Hauptschichten: Einem Python Flask Backend (API-Server auf Port 5001), einem Next.js Frontend (Web-UI auf Port 3000) und einem lokalen KI-Modellanbieter (Ollama oder OpenAI-kompatibel). Alle drei können auf demselben Rechner oder verteilt laufen.' },
        { h: 'Backend (Flask)', p: 'Das Backend in `app/routes.py` verarbeitet alle API-Anfragen: Authentifizierung, KI-Modell-Kommunikation, Plugin-Verwaltung, Dateispeicher, Tresor/Zugangsdaten und die Agenten-Schleife, die mehrstufige KI-Argumentation orchestriert. Plugins in `data/plugins/` erweitern das Backend um 25+ Tools in 11 Integrationen.' },
        { h: 'Frontend (Next.js)', p: 'Die React-basierte UI in `frontend/` bietet die Chat-Oberfläche, Einstellungen, Plugin-Manager und Marketing-Seiten. Sie kommuniziert mit dem Backend über REST-API-Aufrufe und Server-Sent-Events (SSE) für Echtzeit-Streaming von KI-Antworten.' },
        { h: 'KI-Agenten-Schleife', p: 'Wenn du eine Frage stellst, führt MYND folgende Schritte aus: (1) Prompt + verfügbare Tool-Definitionen an das KI-Modell senden, (2) das Modell entscheidet, welche Tools aufgerufen werden, (3) MYND führt jedes Tool aus und gibt die Ergebnisse zurück, (4) das Modell erzeugt die endgültige Antwort. Bis zu 100 Runden pro Anfrage.' },
        { h: 'Plugin-System', p: 'Jede Integration ist ein eigenständiges Plugin in `data/plugins/`. Plugins registrieren Tools mit OpenAI-kompatiblen Funktionsschemata. Das System erkennt installierte Plugins automatisch beim Start. Du kannst eigene Plugins in Python schreiben — siehe Entwickler-Seite.', tip: 'Das System-Plugin (`system.py`) stellt Betriebssystem-Tools wie Timer, Wetter, Websuche und Festplatten-Überwachung bereit — immer verfügbar, keine Konfiguration nötig.' },
      ],
    },
  },
  'getting-started': {
    en: {
      title: 'Getting Started',
      intro: 'Get MYND up and running on your own infrastructure in minutes. All steps work on Linux, macOS, and Windows.',
      steps: [
        { h: '1. Check system requirements', p: 'Python 3.10+, Node.js 18+, 4 GB RAM minimum (8+ GB recommended), 20+ GB free disk space. For local AI models, you need additional RAM: ~4 GB for small models (Phi, TinyLlama), ~8 GB for medium models (Llama 3.2, Mistral), ~16 GB for large models (Qwen 2.5, Llama 3.1).' },
        { h: '2. Clone and install backend', p: 'Run these commands:\n\n```\ngit clone https://github.com/SchBenedikt/mynd.git\ncd mynd\npython -m venv .venv\nsource .venv/bin/activate  # Windows: .venv\\Scripts\\activate\npip install -r requirements.txt\n```\n\nThe backend dependencies include Flask, NumPy, requests, and Werkzeug — all standard Python libraries for web servers and data processing.' },
        { h: '3. Start the backend', p: 'Run `python app.py` from the project root. Expected output: `Running on http://0.0.0.0:5001`. The first run creates a `config.yaml` automatically. The backend is now ready to receive API requests.', tip: 'Keep this terminal open. For production, use a process manager like supervisord or systemd.' },
        { h: '4. Start the frontend', p: 'Open a second terminal, navigate to `frontend/`, and run:\n\n```\nnpm install\nnpm run dev\n```\n\nThe UI is available at http://localhost:3000. For production: `npm run build && npm start`. The dev mode supports hot-reload for development.' },
        { h: '5. Set up AI and create account', p: 'Open http://localhost:3000, click "Sign in" → "Create account". After login, go to Settings → AI and configure your model provider (Ollama or OpenAI-compatible). Then go to Settings → Integrations to connect your services.' },
      ],
    },
    de: {
      title: 'Erste Schritte',
      intro: 'MYND in wenigen Minuten auf deiner eigenen Infrastruktur einrichten.',
      steps: [
        { h: '1. Systemvoraussetzungen prüfen', p: 'Python 3.10+, Node.js 18+, mindestens 4 GB RAM (8+ GB empfohlen), 20+ GB freier Speicher. Für lokale KI-Modelle zusätzlicher RAM: ~4 GB für kleine Modelle (Phi, TinyLlama), ~8 GB für mittlere (Llama 3.2, Mistral), ~16 GB für große (Qwen 2.5, Llama 3.1).' },
        { h: '2. Repository klonen und Backend installieren', p: 'Führe diese Befehle aus:\n\n```\ngit clone https://github.com/SchBenedikt/mynd.git\ncd mynd\npython -m venv .venv\nsource .venv/bin/activate\npip install -r requirements.txt\n```' },
        { h: '3. Backend starten', p: 'Führe `python app.py` aus. Erwartete Ausgabe: `Running on http://0.0.0.0:5001`. Beim ersten Start wird automatisch eine `config.yaml` erstellt.', tip: 'Dieses Terminal geöffnet lassen. Für Produktivbetrieb einen Prozess-Manager wie systemd verwenden.' },
        { h: '4. Frontend installieren und starten', p: 'Öffne ein zweites Terminal, wechsle in `frontend/` und führe aus:\n\n```\nnpm install\nnpm run dev\n```\n\nDie UI ist unter http://localhost:3000 erreichbar.' },
        { h: '5. KI einrichten und Account erstellen', p: 'Öffne http://localhost:3000, klicke "Sign in" → "Create account". Gehe zu Settings → AI und konfiguriere den Modellanbieter. Danach unter Settings → Integrations die gewünschten Dienste verbinden.' },
      ],
    },
  },
  'ai-setup': {
    en: {
      title: 'AI Models',
      intro: 'MYND works with any Ollama model or OpenAI-compatible API. Choosing the right model depends on your hardware and use case. Here is everything you need to know.',
      steps: [
        { h: '1. Install Ollama (recommended)', p: 'Ollama runs AI models locally on your hardware. Install it:\n\n- **Linux**: `curl -fsSL https://ollama.com/install.sh | sh`\n- **macOS**: Download from https://ollama.com\n- **Windows**: Download from https://ollama.com\n\nAfter installation, Ollama runs as a background service on port 11434. Verify with `curl http://127.0.0.1:11434/api/tags`.' },
        { h: '2. Choose and pull a model', p: 'Your choice depends on your hardware and needs:\n\n**Hardware** | **Recommended Model** | **RAM** | **Tool Support**\n---|---|---|---\n8 GB RAM | `phi` (2.7 GB) | ~4 GB | Basic\n8 GB RAM | `tinyllama` (0.6 GB) | ~2 GB | No\n16 GB RAM | `llama3.2` (4.7 GB) | ~8 GB | Yes\n16 GB RAM | `mistral` (4.1 GB) | ~7 GB | Yes\n32 GB RAM | `qwen2.5` (4.9 GB) | ~9 GB | Excellent\n32 GB RAM | `llama3.1` (6.4 GB) | ~12 GB | Yes\n\nPull a model: `ollama pull llama3.2`', tip: 'For the best tool-use experience (required for integrations), choose a model with "Yes" or "Excellent" tool support. Models like `phi`, `gemma`, and `tinyllama` do NOT support tool calling.' },
        { h: '3. Connect MYND to Ollama', p: 'Go to Settings → AI. Select "Ollama" as the provider. Enter `http://127.0.0.1:11434` (or your Ollama host). Click "Fetch Models" and select your downloaded model from the dropdown. Save the config.' },
        { h: '4. OpenAI-compatible providers', p: 'MYND works with any OpenAI-compatible API. Supported providers include:\n\n- **OpenAI**: `https://api.openai.com/v1` (models: gpt-4o, gpt-4o-mini, o3-mini)\n- **Groq**: `https://api.groq.com/openai/v1` (models: llama-3.3-70b, mixtral-8x7b)\n- **Together**: `https://api.together.xyz/v1` (models: llama-3.3-70b, qwen-2.5-72b)\n- **Anthropic**: `https://api.anthropic.com/v1` (models: claude-3.5-sonnet)\n- **Google Gemini**: Via OpenAI-compatible proxy\n\nSelect "OpenAI Compatible" in Settings → AI, enter the Base URL and API key.', tip: 'Cloud models (OpenAI, Groq) are faster and more capable than local models but cost per request. Local models are free and private.' },
        { h: '5. Test and verify', p: 'In Settings → AI, use "Test Connection" to verify the provider works. Use "Check Tool Support" to see which models support tool calling. A model without tool support can still answer questions but cannot access your integrations (Nextcloud, Immich, etc.).', tip: 'If a model fails tool support but you believe it should work, check your Ollama version (needs 0.3.0+ for tool calling).' },
      ],
    },
    de: {
      title: 'KI-Modelle',
      intro: 'MYND funktioniert mit allen Ollama-Modellen und OpenAI-kompatiblen APIs. Die Wahl des richtigen Modells hängt von deiner Hardware und deinem Einsatzzweck ab.',
      steps: [
        { h: '1. Ollama installieren (empfohlen)', p: 'Ollama führt KI-Modelle lokal auf deiner Hardware aus. Installation:\n\n- **Linux**: `curl -fsSL https://ollama.com/install.sh | sh`\n- **macOS/Windows**: Download von https://ollama.com\n\nOllama läuft als Hintergrunddienst auf Port 11434. Prüfe mit `curl http://127.0.0.1:11434/api/tags`.' },
        { h: '2. Modell auswählen und pullen', p: 'Die Wahl hängt von Hardware und Anforderungen ab:\n\n**Hardware** | **Empfohlenes Modell** | **RAM** | **Tool-Support**\n---|---|---|---\n8 GB RAM | `phi` (2.7 GB) | ~4 GB | Basis\n8 GB RAM | `tinyllama` (0.6 GB) | ~2 GB | Nein\n16 GB RAM | `llama3.2` (4.7 GB) | ~8 GB | Ja\n16 GB RAM | `mistral` (4.1 GB) | ~7 GB | Ja\n32 GB RAM | `qwen2.5` (4.9 GB) | ~9 GB | Hervorragend\n32 GB RAM | `llama3.1` (6.4 GB) | ~12 GB | Ja\n\nModell pullen: `ollama pull llama3.2`', tip: 'Für die Nutzung von Integrationen (Nextcloud, Immich etc.) ist Tool-Support erforderlich. Modelle wie `phi`, `gemma` und `tinyllama` unterstützen keine Tools.' },
        { h: '3. MYND mit Ollama verbinden', p: 'Gehe zu Settings → AI. Wähle "Ollama" als Anbieter. Trage `http://127.0.0.1:11434` ein. Klicke "Fetch Models" und wähle dein Modell aus. Speichern.' },
        { h: '4. OpenAI-kompatible Anbieter', p: 'MYND funktioniert mit allen OpenAI-kompatiblen APIs:\n\n- **OpenAI**: `https://api.openai.com/v1` (gpt-4o, gpt-4o-mini)\n- **Groq**: `https://api.groq.com/openai/v1` (llama-3.3-70b)\n- **Together**: `https://api.together.xyz/v1`\n\nWähle "OpenAI Compatible" in Settings → AI, trage Base-URL und API-Key ein.', tip: 'Cloud-Modelle sind schneller und leistungsfähiger als lokale, kosten aber pro Anfrage. Lokale Modelle sind kostenlos und privat.' },
        { h: '5. Testen und prüfen', p: 'Nutze "Test Connection" in Settings → AI, um die Verbindung zu prüfen. "Check Tool Support" zeigt, welche Modelle Tool-Aufrufe unterstützen. Ein Modell ohne Tool-Support kann keine Integrationen nutzen.', tip: 'Ollama benötigt Version 0.3.0+ für Tool-Unterstützung.' },
      ],
    },
  },
  'security': {
    en: {
      title: 'Security & Modes',
      intro: 'MYND offers multiple security layers and operating modes. Understanding these lets you balance convenience and safety.',
      steps: [
        { h: '1. Security Modes', p: 'Settings → AI → Security Mode controls which tools the AI can access:\n\n- **Restricted**: Only document search and memory. No external tools. Safest for untrusted environments.\n- **Standard** (default): Vault access + most tools, excluding SSH. Good balance of capability and safety.\n- **Admin**: Full access including SSH. All tools available, no confirmation prompts. Maximum capability.\n\nChange the mode at any time — it takes effect immediately.' },
        { h: '2. Tool Confirmation System', p: 'In Standard and Restricted modes, certain tools require your confirmation before execution. These include: file operations (write, delete), email sending, home assistant state changes, SSH commands, and browser interactions. The confirmation dialog blocks execution until you approve or deny.', tip: 'In Admin mode, all tools run without confirmation. This is the "fully autonomous" mode described on the landing page.' },
        { h: '3. Permission Mode (Bash/SSH)', p: 'Environment variable `MYND_PERMISSION_MODE` controls confirmation for bash and SSH commands:\n\n- **auto**: All commands allowed without confirmation\n- **semi**: Confirmation only for critical commands (rm, sudo, dd, mkfs, shutdown)\n- **ask**: Confirmation for every command (default)\n\nSet this in your `.env` file or export it before starting MYND.' },
        { h: '4. Authentication', p: 'All API endpoints except login, registration, and health checks require authentication. Users can have role `user` or `admin`. Admin users can manage plugins, create/delete users, and reset the application. Registration can be enabled/disabled in Settings → Admin.', tip: 'Session tokens expire after 30 days of inactivity. Use Settings → Profile to change your password.' },
        { h: '5. Data Privacy', p: 'All your data stays on your infrastructure. MYND never sends files or credentials to external servers (unless you configure an external AI provider). The cloud browser runs in a sandboxed environment on your server. Plugin state is stored locally in `plugin_state.json`.' },
      ],
    },
    de: {
      title: 'Sicherheit & Modi',
      intro: 'MYND bietet mehrere Sicherheitsebenen und Betriebsmodi. Das Verständnis hilft dir, Komfort und Sicherheit optimal zu balancieren.',
      steps: [
        { h: '1. Sicherheitsmodi', p: 'Settings → AI → Security Mode kontrolliert, welche Tools die KI nutzen darf:\n\n- **Eingeschränkt**: Nur Dokumentsuche und Gedächtnis. Keine externen Tools.\n- **Standard** (Standard): Vault-Zugriff + die meisten Tools, außer SSH.\n- **Admin**: Voller Zugriff inkl. SSH. Alle Tools, keine Bestätigungsdialoge.' },
        { h: '2. Tool-Bestätigung', p: 'Im Standard-Modus benötigen bestimmte Tools deine Bestätigung: Datei-Operationen, E-Mail-Versand, Home-Assistant-Schaltbefehle, Browser-Interaktionen. Der Bestätigungsdialog blockiert die Ausführung bis zur Freigabe.', tip: 'Im Admin-Modus laufen alle Tools ohne Bestätigung — der "vollautonome" Modus.' },
        { h: '3. Berechtigungsmodus (Bash/SSH)', p: 'Die Umgebungsvariable `MYND_PERMISSION_MODE` steuert die Bestätigung für Bash- und SSH-Befehle:\n\n- **auto**: Alle Befehle erlaubt\n- **semi**: Nur bei kritischen Befehlen (rm, sudo, dd)\n- **ask**: Bei jedem Befehl (Standard)' },
        { h: '4. Authentifizierung', p: 'Alle API-Endpunkte außer Login, Registrierung und Health-Check erfordern Authentifizierung. Benutzer haben die Rolle `user` oder `admin`. Admins verwalten Plugins, Benutzer und können die App zurücksetzen.' },
        { h: '5. Datenschutz', p: 'Alle deine Daten bleiben auf deiner Infrastruktur. MYND sendet niemals Dateien oder Zugangsdaten an externe Server (außer bei Konfiguration eines externen KI-Anbieters).' },
      ],
    },
  },
  nextcloud: {
    en: {
      title: 'Nextcloud',
      intro: 'Connect MYND to your Nextcloud instance to browse files, manage calendars and tasks, and search your cloud storage.',
      steps: [
        { h: '1. Create an app password', p: 'In Nextcloud, go to Settings → Security → "Create app password". Enter a name like "MYND" and copy the generated password. App passwords are preferred over your main password because they can be revoked individually.' },
        { h: '2. Enter connection details in MYND', p: 'Go to Settings → Integrations → Nextcloud. Enter your Nextcloud URL (e.g. `https://nextcloud.example.com`), your username, and the app password. Click "Connect". MYND tests WebDAV and CalDAV connectivity.' },
        { h: '3. Browse and search files', p: 'MYND accesses your files via WebDAV. Supported formats: PDF, TXT, DOCX, ODT, Markdown, JSON, YAML, XML, HTML, CSV, and source code files. Ask: "Search my Nextcloud for the budget spreadsheet" or "What documents were modified this week?"' },
        { h: '4. Calendars and Tasks', p: 'Via CalDAV, MYND reads your calendars and task lists. Ask: "What appointments do I have tomorrow?", "Show my open tasks", "Create an event for Friday at 3 PM".', tip: 'Calendar events and tasks are read-only for safety. Use the Nextcloud UI for modifications, or ask MYND to draft the event details.' },
        { h: '5. Example queries', p: '— "Search my Nextcloud for files containing invoice2025"\n— "Show me files shared with me"\n— "What changed in the Projects folder this week?"\n— "List my upcoming calendar events"\n— "Find the document tagged with important"', tip: 'The initial indexing scans recent files. For deeper searches across all files, allow a few minutes for full indexing.' },
      ],
    },
    de: {
      title: 'Nextcloud',
      intro: 'Verbinde MYND mit deiner Nextcloud-Instanz für Dateisuche, Kalender- und Aufgabenverwaltung.',
      steps: [
        { h: '1. App-Passwort erstellen', p: 'In Nextcloud unter Einstellungen → Sicherheit → "App-Passwort erstellen". Namen wie "MYND" vergeben und das generierte Passwort kopieren.' },
        { h: '2. Verbindung in MYND einrichten', p: 'Settings → Integrations → Nextcloud. URL (z.B. `https://nextcloud.example.com`), Benutzername und App-Passwort eintragen. "Connect" klicken.' },
        { h: '3. Dateien durchsuchen', p: 'MYND greift über WebDAV auf Dateien zu. Unterstützte Formate: PDF, TXT, DOCX, ODT, Markdown, Code-Dateien. Frage: "Suche in Nextcloud nach der Budget-Tabelle".' },
        { h: '4. Kalender und Aufgaben', p: 'Über CalDAV liest MYND Kalender und Aufgabenlisten. Frage: "Was habe ich morgen für Termine?", "Zeige meine offenen Aufgaben".', tip: 'Kalender und Aufgaben sind schreibgeschützt. Änderungen im Nextcloud-UI vornehmen.' },
        { h: '5. Beispiel-Abfragen', p: '— "Suche in Nextcloud nach Rechnung 2025"\n— "Zeige meine geteilten Dateien"\n— "Was hat sich diese Woche im Projekte-Ordner geändert?"' },
      ],
    },
  },
  immich: {
    en: {
      title: 'Immich',
      intro: 'Connect MYND to Immich for AI-powered photo search using natural language.',
      steps: [
        { h: '1. Create an API key', p: 'In Immich, go to Settings → Users → API Key. Create a new key named "MYND" and copy it. The key is shown only once.' },
        { h: '2. Enter details in MYND', p: 'Settings → Integrations → Immich. Enter your Immich URL and the API key. Click "Connect". MYND will verify it can access your library.' },
        { h: '3. Search your photos', p: 'MYND queries Immich\'s search API which automatically tags faces, objects, places, and scenes. Ask: "Show photos from last summer", "Find pictures with dogs", "What photos did I take in Paris?"' },
        { h: '4. Filter by metadata', p: 'You can combine filters: camera model, date range, location, people, and objects. Ask: "Show photos from 2024 taken with my Sony camera", "Find pictures of Anna from the beach vacation".', tip: 'MYND searches metadata only — your original photos stay in Immich. No images are transferred to MYND.' },
      ],
    },
    de: {
      title: 'Immich',
      intro: 'Verbinde MYND mit Immich für KI-gestützte Fotosuche in natürlicher Sprache.',
      steps: [
        { h: '1. API-Key erstellen', p: 'In Immich unter Settings → Users → API Key. Neuen Key mit Name "MYND" erstellen und kopieren.' },
        { h: '2. Verbindung einrichten', p: 'Settings → Integrations → Immich. URL und API-Key eintragen. "Connect" klicken.' },
        { h: '3. Fotos durchsuchen', p: 'MYND nutzt die Immich-Suche mit automatischer Gesichts-, Objekt- und Ortserkennung. Frage: "Zeige Fotos vom letzten Sommer", "Finde Bilder mit Hunden".' },
        { h: '4. Nach Metadaten filtern', p: 'Kombiniere Filter: Kameramodell, Datumsbereich, Ort, Personen. Frage: "Zeige Fotos von 2024 mit meiner Sony-Kamera".', tip: 'MYND durchsucht nur Metadaten — Originalfotos bleiben in Immich.' },
      ],
    },
  },
  homeassistant: {
    en: {
      title: 'Home Assistant',
      intro: 'Control your smart home through MYND — check sensors, toggle devices, and trigger automations.',
      steps: [
        { h: '1. Create a Long-Lived Access Token', p: 'In Home Assistant, click your profile (bottom-left) → "Long-Lived Access Token". Create a token named "MYND" and copy it.' },
        { h: '2. Enter details in MYND', p: 'Settings → Integrations → Home Assistant. Enter the URL (e.g. `http://homeassistant.local:8123`) and the token. Click "Connect".' },
        { h: '3. Check states', p: 'MYND reads all entity states. Ask: "What is the temperature in the living room?", "Is the front door locked?", "What is the energy consumption today?"' },
        { h: '4. Control devices', p: 'Toggle devices and set values. Ask: "Turn off all lights", "Set the thermostat to 21 degrees", "Activate the good night scene".', tip: 'In Standard mode, state-changing actions require your confirmation. Switch to Admin mode in Settings → AI for autonomous control.' },
      ],
    },
    de: {
      title: 'Home Assistant',
      intro: 'Steuere dein Smart Home über MYND — Sensoren abfragen, Geräte schalten und Automationen auslösen.',
      steps: [
        { h: '1. Long-Lived Token erstellen', p: 'In Home Assistant Profil → "Langzeit-Zugriffstoken". Token mit Name "MYND" erstellen und kopieren.' },
        { h: '2. Verbindung einrichten', p: 'Settings → Integrations → Home Assistant. URL (z.B. `http://homeassistant.local:8123`) und Token eintragen.' },
        { h: '3. Zustände abfragen', p: 'Frage: "Wie ist die Temperatur im Wohnzimmer?", "Ist die Haustür verriegelt?", "Wie hoch ist der Stromverbrauch heute?"' },
        { h: '4. Geräte steuern', p: 'Frage: "Schalte alle Lichter aus", "Stelle den Thermostat auf 21 Grad", "Aktiviere die Gute-Nacht-Szene".', tip: 'Im Standard-Modus benötigen Schaltbefehle Bestätigung. Admin-Modus für autonome Steuerung.' },
      ],
    },
  },
  email: {
    en: {
      title: 'Email',
      intro: 'Connect MYND to your mailbox via IMAP/SMTP — search, read, and send emails.',
      steps: [
        { h: '1. Prepare your credentials', p: 'You need IMAP/SMTP server addresses, ports, and credentials. Common providers:\n\n- **Gmail**: imap.gmail.com:993, smtp.gmail.com:587 (requires app password)\n- **Outlook**: outlook.office365.com:993, smtp.office365.com:587\n- **Custom**: Use your mail server addresses' },
        { h: '2. Add account in MYND', p: 'Settings → Integrations → Email → "Add Account". Enter server details and credentials. MYND tests both IMAP (receiving) and SMTP (sending) connections.' },
        { h: '3. Search and read', p: 'MYND indexes recent emails. Ask: "Show my unread emails", "Find the invoice from last month", "Summarize emails from [sender]"', tip: 'For Gmail, use an App Password (Settings → Security → App Passwords). Your regular password may not work with IMAP/SMTP.' },
        { h: '4. Send emails', p: 'MYND can send emails on your behalf. Ask: "Send an email to john@example.com with subject Meeting and body: Let us meet at 3 PM tomorrow."' },
      ],
    },
    de: {
      title: 'E-Mail',
      intro: 'Verbinde MYND mit deinem Postfach — E-Mails suchen, lesen und senden.',
      steps: [
        { h: '1. Zugangsdaten vorbereiten', p: 'IMAP/SMTP-Server, Ports und Anmeldedaten. Übliche Anbieter:\n\n- **Gmail**: imap.gmail.com:993, smtp.gmail.com:587 (App-Passwort nötig)\n- **Outlook**: outlook.office365.com:993, smtp.office365.com:587' },
        { h: '2. Konto hinzufügen', p: 'Settings → Integrations → Email → "Add Account". Server-Daten eintragen. MYND testet IMAP und SMTP getrennt.' },
        { h: '3. Suchen und lesen', p: 'Frage: "Zeige meine ungelesenen E-Mails", "Finde die Rechnung vom letzten Monat".', tip: 'Bei Gmail ein App-Passwort verwenden (Settings → Sicherheit → App-Passwörter).' },
        { h: '4. E-Mails senden', p: 'Frage: "Sende eine E-Mail an max@example.com mit Betreff Besprechung und Inhalt: Treffen morgen um 15 Uhr."' },
      ],
    },
  },
  spotify: {
    en: {
      title: 'Spotify',
      intro: 'Control Spotify playback through MYND — search, play, and manage playlists via the official Spotify Web API.',
      steps: [
        { h: '1. Create a Spotify app', p: 'Go to https://developer.spotify.com/dashboard → "Create App". Name it "MYND". Set the Redirect URI to `http://localhost:5001/callback/spotify`. Copy the Client ID and Client Secret.' },
        { h: '2. Connect in MYND', p: 'Settings → Integrations → Spotify. Enter Client ID and Secret. Click "Connect" — you will be redirected to Spotify to authorize. MYND stores the refresh token for permanent access.' },
        { h: '3. Control playback', p: 'Ask: "Play [song] by [artist]", "Pause", "Next track", "What is currently playing?", "Play my Discover Weekly playlist".', tip: 'Spotify Premium is required for playback control. The free tier only allows read access.' },
        { h: '4. Manage playlists', p: 'Ask: "Create a playlist called Morning Vibes", "Add this song to my Favorites playlist".', tip: 'For production, update the Redirect URI to your actual domain in the Spotify Developer Dashboard.' },
      ],
    },
    de: {
      title: 'Spotify',
      intro: 'Steuere Spotify über MYND — Titel suchen, abspielen und Playlists verwalten.',
      steps: [
        { h: '1. Spotify-App erstellen', p: 'https://developer.spotify.com/dashboard → "Create App". Name "MYND". Redirect-URI: `http://localhost:5001/callback/spotify`. Client-ID und Secret kopieren.' },
        { h: '2. In MYND verbinden', p: 'Settings → Integrations → Spotify. Client-ID und Secret eintragen. "Connect" — du wirst zu Spotify weitergeleitet.' },
        { h: '3. Wiedergabe steuern', p: 'Frage: "Spiele [Song] von [Künstler]", "Pausiere", "Nächster Titel", "Spiele meine Discover Weekly Playlist".', tip: 'Spotify Premium erforderlich für Wiedergabesteuerung.' },
        { h: '4. Playlists verwalten', p: 'Frage: "Erstelle eine Playlist mit Namen", "Füge diesen Song zu meiner Favorites-Playlist hinzu".' },
      ],
    },
  },
  discord: {
    en: {
      title: 'Discord',
      intro: 'Connect MYND to Discord — read messages, search channels, and send messages via a dedicated bot.',
      steps: [
        { h: '1. Create a Discord bot', p: 'Go to https://discord.com/developers/applications → "New Application" → "Bot" → "Add Bot". Copy the token. Enable "Message Content Intent" and "Server Members Intent".' },
        { h: '2. Invite the bot', p: 'Go to "OAuth2" → "URL Generator". Select "bot" with permissions: Send Messages, Read Message History, View Channels, Read Messages. Open the URL and select your server.', tip: 'You need "Manage Server" permissions to invite the bot.' },
        { h: '3. Enter token in MYND', p: 'Settings → Integrations → Discord. Enter the bot token. Click "Connect". MYND will list your servers and channels.' },
        { h: '4. Use it', p: 'Ask: "What is new on the [server] server?", "Search Discord for the project link", "Send a message to #general: I will be there in 5 minutes".', tip: 'MYND cannot read DMs — only channels the bot is a member of.' },
      ],
    },
    de: {
      title: 'Discord',
      intro: 'Verbinde MYND mit Discord — Nachrichten lesen, Kanäle durchsuchen und senden.',
      steps: [
        { h: '1. Discord-Bot erstellen', p: 'https://discord.com/developers/applications → "New Application" → "Bot" → "Add Bot". Token kopieren. "Message Content Intent" aktivieren.' },
        { h: '2. Bot einladen', p: '"OAuth2" → "URL Generator". "bot" auswählen mit Berechtigungen: Send Messages, Read Message History, View Channels.', tip: '"Manage Server"-Rechte erforderlich.' },
        { h: '3. Token eintragen', p: 'Settings → Integrations → Discord. Bot-Token eintragen. "Connect".' },
        { h: '4. Nutzung', p: 'Frage: "Was gibt es Neues auf [Server]?", "Suche in Discord nach dem Projekt-Link".' },
      ],
    },
  },
  truenas: {
    en: {
      title: 'TrueNAS',
      intro: 'Monitor your TrueNAS system — storage pools, disk health, SMART data, services, and alerts via the TrueNAS API.',
      steps: [
        { h: '1. Create an API key', p: 'In TrueNAS, go to Settings → API Keys → "Add". Name it "MYND" and copy the key. It is shown only once.' },
        { h: '2. Enter details in MYND', p: 'Settings → Integrations → TrueNAS. Enter your TrueNAS URL (e.g. `http://truenas.local:8080`) and the API key. Click "Connect".' },
        { h: '3. Check storage', p: 'Ask: "How is my storage pool doing?", "How much free space do I have?", "Show me all pools and their usage".' },
        { h: '4. Monitor health', p: 'Ask: "Are there any disk alerts?", "Show SMART status of all drives", "What services are running?".', tip: 'SMART long tests can take hours. MYND reports the most recent test results.' },
      ],
    },
    de: {
      title: 'TrueNAS',
      intro: 'Überwache dein TrueNAS-System — Speicherpools, Festplatten, SMART-Werte und Alarme.',
      steps: [
        { h: '1. API-Key erstellen', p: 'In TrueNAS unter Settings → API Keys → "Add". Namen "MYND" vergeben und Key kopieren.' },
        { h: '2. Verbindung einrichten', p: 'Settings → Integrations → TrueNAS. URL (z.B. `http://truenas.local:8080`) und API-Key eintragen.' },
        { h: '3. Speicher prüfen', p: 'Frage: "Wie ist der Stand meines Speicherpools?", "Wie viel Speicher ist noch frei?"' },
        { h: '4. Gesundheit überwachen', p: 'Frage: "Gibt es Festplatten-Alarme?", "Zeige SMART-Status aller Festplatten".', tip: 'SMART-Tests können Stunden dauern. MYND zeigt die letzten Ergebnisse.' },
      ],
    },
  },
  browser: {
    en: {
      title: 'Browser',
      intro: 'MYND includes a built-in cloud browser for web research — navigate pages, take screenshots, extract text, and interact with forms.',
      steps: [
        { h: '1. How it works', p: 'The cloud browser is a headless Chromium instance running on your server. It opens websites, executes JavaScript, and captures screenshots — completely isolated from your regular browser with separate cookies, sessions, and extensions.' },
        { h: '2. Browse and capture', p: 'Ask: "Open [URL]", "Take a screenshot of [URL]", "Summarize the content of [URL]". The browser renders JavaScript-heavy pages (React, Vue SPAs) before capturing.' },
        { h: '3. Extract and search', p: 'Ask: "Extract all links from [URL]", "Search the page for [keyword]", "What is the main content of this article?"' },
        { h: '4. Interact and download', p: 'Ask: "Fill the search form with [query] on [URL]", "Click the login button", "Download the PDF from this page".', tip: 'Browser interactions (clicks, form fills) require confirmation in Standard mode. Switch to Admin mode for autonomous browsing.' },
      ],
    },
    de: {
      title: 'Browser',
      intro: 'MYND enthält einen integrierten Cloud-Browser für Web-Recherche — navigieren, Screenshots machen, Texte extrahieren.',
      steps: [
        { h: '1. Funktionsweise', p: 'Der Cloud-Browser ist eine server-seitige, isolierte Chromium-Instanz. Keine Cookies oder Sitzungen werden mit deinem normalen Browser geteilt.' },
        { h: '2. Navigieren und Screenshots', p: 'Frage: "Öffne [URL]", "Mach einen Screenshot von [URL]", "Fasse den Inhalt von [URL] zusammen".' },
        { h: '3. Extrahieren und suchen', p: 'Frage: "Extrahiere alle Links von [URL]", "Suche auf der Seite nach [Suchbegriff]".' },
        { h: '4. Interagieren und herunterladen', p: 'Frage: "Fülle das Suchformular auf [URL] mit [Suchbegriff]", "Lade das PDF herunter".', tip: 'Browser-Interaktionen benötigen Bestätigung im Standard-Modus.' },
      ],
    },
  },
};

export default function GuidePage() {
  const [lang, setLang] = useState('en');
  const [activeSection, setActiveSection] = useState('getting-started');

  useEffect(() => {
    const mode = (() => { try { return localStorage.getItem('darkMode') || 'light'; } catch { return 'light'; } })();
    document.documentElement.setAttribute('data-mode', mode);
  }, []);

  const t = (de, en) => lang === 'de' ? de : en;
  const content = GUIDE[activeSection]?.[lang] || GUIDE[activeSection]?.en;

  return (
    <div className="lp-guide" lang={lang}>
      <nav className="lp-nav">
        <div className="lp-nav-inner">
          <Link href="/" className="lp-logo">
            <span className="lp-logo-mark"><i /></span>
            <span>MYND</span>
          </Link>
          <div className="lp-nav-links">
            <Link href="/guide">{t('Anleitung', 'Guide')}</Link>
            <Link href="/developers">{t('Entwickler', 'Developers')}</Link>
          </div>
          <div className="lp-nav-actions">
            <button className="lp-language" type="button" onClick={() => setLang(l => l === 'de' ? 'en' : 'de')}>
              <span className={lang === 'de' ? 'active' : ''}>DE</span>
              <i />
              <span className={lang === 'en' ? 'active' : ''}>EN</span>
            </button>
            <Link href="/login" className="lp-signin">
              {t('Anmelden', 'Sign in')} <i className="fas fa-arrow-right" />
            </Link>
          </div>
        </div>
      </nav>

      <div className="lp-guide-layout lp-shell">
        <aside className="lp-guide-sidebar">
          <nav aria-label={t('Navigation', 'Navigation')}>
            {SECTIONS.map(s => (
              <button
                key={s.id}
                className={`lp-guide-sidebar-link${activeSection === s.id ? ' active' : ''}`}
                onClick={() => setActiveSection(s.id)}
              >
                <i className={`fas ${s.icon}`} />
                {s[`label_${lang}`] || s.label_en}
              </button>
            ))}
          </nav>
        </aside>

        <main className="lp-guide-main">
          {content && (
            <div className="lp-guide-section">
              <h1 className="lp-guide-title">
                <i className={`fas ${SECTIONS.find(s => s.id === activeSection)?.icon}`} />
                {' '}{content.title}
              </h1>
              <p className="lp-guide-intro">{content.intro}</p>
              <div className="lp-guide-steps">
                {content.steps.map((step, i) => (
                  <div key={i} className="lp-guide-step">
                    <h2 className="lp-guide-step-heading">
                      <span className="step-num">{String(i + 1).padStart(2, '0')}</span>
                      {step.h.replace(/^\d+\.\s*/, '')}
                    </h2>
                    <p>{step.p}</p>
                    {step.tip && <div className="lp-guide-tip"><strong>{t('Tipp', 'Tip')}:</strong> {step.tip}</div>}
                  </div>
                ))}
              </div>
            </div>
          )}
          <div className="lp-guide-footer">
            <Link href="https://github.com/SchBenedikt/mynd" target="_blank">GitHub</Link>
            {' · '}
            <Link href="/developers">{t('Entwickler-Dokumentation', 'Developer Docs')}</Link>
            {' · '}
            <Link href="/login">{t('Zum Login', 'Go to Login')}</Link>
          </div>
        </main>
      </div>
    </div>
  );
}
