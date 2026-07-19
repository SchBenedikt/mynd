'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import './guide.css';

const SECTIONS = [
  { id: 'getting-started', icon: 'fa-rocket', label_de: 'Erste Schritte', label_en: 'Getting Started' },
  { id: 'ai-setup', icon: 'fa-brain', label_de: 'KI einrichten', label_en: 'AI Setup' },
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
  'getting-started': {
    de: {
      title: 'Erste Schritte',
      intro: 'MYND ist deine lokale Personal-AI-Plattform. Stelle Fragen zu deinen Dateien, Geräten und Diensten — alles läuft auf deiner eigenen Infrastruktur. Nachfolgend erfährst du, wie du in wenigen Minuten startest.',
      steps: [
        { h: '1. Systemvoraussetzungen prüfen', p: 'MYND läuft auf jedem Linux-, macOS- oder Windows-System Python 3.10+. Empfohlen: 4 GB RAM, 20 GB freier Speicher (für Ki-Modelle je nach Modell mehr). Für Produktivbetrieb empfehlen wir einen dedizierten Server oder VPS.', tip: 'Für Ollama-Modelle werden zusätzlich zur MYND-Installation ca. 4–16 GB RAM benötigt. Plane entsprechend.' },
        { h: '2. Repository klonen und Umgebung einrichten', p: 'Klone das Repository: `git clone https://github.com/SchBenedikt/mynd.git && cd mynd`. Erstelle ein virtuelles Environment: `python -m venv .venv && source .venv/bin/activate`. Installiere die Abhängigkeiten: `pip install -r requirements.txt`.' },
        { h: '3. Backend starten', p: 'Starte den Server mit `python app.py` aus dem Hauptverzeichnis. Der Server läuft standardmäßig auf Port 5001. Erwartete Ausgabe: `Running on http://0.0.0.0:5001`. Nach dem ersten Start wird automatisch ein `config.yaml` erstellt, das du für die Konfiguration nutzen kannst.' },
        { h: '4. Frontend installieren und starten', p: 'Öffne ein zweites Terminal. Wechsle ins `frontend`-Verzeichnis und führe `npm install && npm run dev` aus. Das Frontend ist dann unter http://localhost:3000 erreichbar. Für die Produktion verwende `npm run build && npm start`.' },
        { h: '5. Account erstellen und loslegen', p: 'Öffne http://localhost:3000, klicke auf "Sign in" und wähle "Create account". Nach dem Login konfiguriere unter Settings → AI dein Modell. Danach kannst du bereits Fragen stellen.' },
      ],
    },
    en: {
      title: 'Getting Started',
      intro: 'MYND is your local personal AI platform. Ask questions about your files, devices and services — everything runs on your own infrastructure. Here\'s how to get up and running in minutes.',
      steps: [
        { h: '1. Check system requirements', p: 'MYND runs on any Linux, macOS or Windows system with Python 3.10+. Recommended: 4 GB RAM, 20 GB free storage (more for AI model inference). For production, we recommend a dedicated server or VPS.', tip: 'Ollama models require roughly 4–16 GB additional RAM on top of the MYND base install. Plan accordingly.' },
        { h: '2. Clone the repo and set up the environment', p: 'Clone the repository: `git clone https://github.com/SchBenedikt/mynd.git && cd mynd`. Create a virtual environment: `python -m venv .venv && source .venv/bin/activate`. Install dependencies: `pip install -r requirements.txt`.' },
        { h: '3. Start the backend', p: 'Run `python app.py` from the project root. The server starts on port 5001 by default. Expected output: `Running on http://0.0.0.0:5001`. A `config.yaml` is auto-created on first startup for configuration.' },
        { h: '4. Install and start the frontend', p: 'Open a second terminal. Navigate to the `frontend` directory and run `npm install && npm run dev`. The frontend is then available at http://localhost:3000. For production, use `npm run build && npm start`.' },
        { h: '5. Create an account and start using MYND', p: 'Open http://localhost:3000, click "Sign in" and choose "Create account". After logging in, configure your AI model under Settings → AI. You can now start asking questions.' },
      ],
    },
  },
  'ai-setup': {
    de: {
      title: 'KI einrichten',
      intro: 'MYND benötigt ein laufendes Ollama oder einen OpenAI-kompatiblen Anbieter. Hier erfährst du, wie du beide Optionen einrichtest und optimierst.',
      steps: [
        { h: '1. Ollama installieren', p: 'Lade Ollama von https://ollama.com herunter und installiere es. Auf Linux: `curl -fsSL https://ollama.com/install.sh | sh`. Auf macOS: lade die .dmg-Datei herunter. Starte den Service: `ollama serve` (auf macOS läuft er automatisch).', tip: 'Prüfe mit `curl http://127.0.0.1:11434/api/tags`, ob Ollama antwortet.' },
        { h: '2. Ein Modell herunterladen', p: 'Wähle ein passendes Modell: `ollama pull llama3.2` (ca. 4,7 GB) für Allzweck-Aufgaben oder `ollama pull qwen2.5` (ca. 4,9 GB) für bessere Tool-Unterstützung. Für schwächere Hardware: `ollama pull phi` oder `ollama pull tinyllama`.', tip: 'Mit `ollama list` siehst du alle heruntergeladenen Modelle. `ollama rm <name>` entfernt ein Modell.' },
        { h: '3. Modell in MYND verbinden', p: 'Gehe zu Settings → AI. Wähle als Provider "Ollama". Trage die Ollama-URL ein (standardmäßig http://127.0.0.1:11434). Klicke auf "Fetch Models" und wähle dein gewünschtes Modell aus der Liste.' },
        { h: '4. OpenAI-kompatible Anbieter nutzen', p: 'Wähle als Provider "OpenAI Compatible". Du benötigst die Base-URL des Anbieters und einen API-Key. Beliebte Anbieter: OpenAI (https://api.openai.com/v1), Groq (https://api.groq.com/openai/v1), Together (https://api.together.xyz/v1).', tip: 'OpenAI-Modelle wie GPT-4o liefern die besten Ergebnisse, kosten aber pro Anfrage. Lokale Modelle sind kostenlos, aber langsamer.' },
        { h: '5. Erweiterte Einstellungen', p: 'Unter Settings → AI kannst du System-Prompt, Kontextlänge, Temperatur und andere Parameter anpassen. Der System-Prompt definiert, wie sich MYND verhalten soll. Eine kürzere Kontextlänge spart RAM für lokale Modelle.' },
      ],
    },
    en: {
      title: 'AI Setup',
      intro: 'MYND requires a running Ollama instance or an OpenAI-compatible provider. Here\'s how to set up and optimize both options.',
      steps: [
        { h: '1. Install Ollama', p: 'Download Ollama from https://ollama.com and install it. On Linux: `curl -fsSL https://ollama.com/install.sh | sh`. On macOS: download the .dmg file. Start the service: `ollama serve` (runs automatically on macOS).', tip: 'Verify with `curl http://127.0.0.1:11434/api/tags` — if you get a JSON response, Ollama is ready.' },
        { h: '2. Pull a model', p: 'Choose a model: `ollama pull llama3.2` (~4.7 GB) for general-purpose tasks or `ollama pull qwen2.5` (~4.9 GB) for better tool-use support. For weaker hardware: `ollama pull phi` or `ollama pull tinyllama`.', tip: 'Use `ollama list` to see all downloaded models. `ollama rm <name>` removes one.' },
        { h: '3. Connect the model in MYND', p: 'Go to Settings → AI. Select "Ollama" as provider. Enter the Ollama URL (default http://127.0.0.1:11434). Click "Fetch Models" and select your model from the list.' },
        { h: '4. Use OpenAI-compatible providers', p: 'Select "OpenAI Compatible" as provider. You need the provider\'s Base URL and an API key. Popular providers: OpenAI (https://api.openai.com/v1), Groq (https://api.groq.com/openai/v1), Together (https://api.together.xyz/v1).', tip: 'OpenAI models like GPT-4o deliver the best results but cost per request. Local models are free but slower.' },
        { h: '5. Advanced settings', p: 'In Settings → AI you can customize the system prompt, context length, temperature and other parameters. The system prompt defines how MYND behaves. Shorter context length saves RAM for local models.' },
      ],
    },
  },
  nextcloud: {
    de: {
      title: 'Nextcloud',
      intro: 'Verbinde MYND mit deiner Nextcloud-Instanz, um Dateien zu durchsuchen, Kalender und Aufgaben abzurufen sowie Benachrichtigungen auszulesen.',
      steps: [
        { h: '1. Verbindungsdaten vorbereiten', p: 'Du benötigst: (a) die URL deiner Nextcloud-Instanz (z. B. https://nextcloud.example.com), (b) deinen Nextcloud-Benutzernamen und (c) ein App-Passwort. App-Passwörter erstellst du in Nextcloud unter Einstellungen → Sicherheit → "App-Passwort erstellen".', tip: 'Verwende ein App-Passwort statt deines Hauptpassworts, damit MYND nur auf die freigegebenen Ressourcen zugreift.' },
        { h: '2. Integration in MYND aktivieren', p: 'Gehe zu Settings → Integrations → Nextcloud. Trage die URL, den Benutzernamen und das App-Passwort ein. Klicke auf "Connect". MYND testet die Verbindung und zeigt bei Erfolg die verfügbaren Datenquellen an.' },
        { h: '3. WebDAV-Zugriff auf Dateien', p: 'MYND greift über WebDAV auf deine Nextcloud-Dateien zu. Du kannst Dateien durchsuchen, lesen und nach Inhalten durchsuchen. Unterstützte Formate: PDF, TXT, DOCX, ODT, Markdown, Code-Dateien und viele mehr.', tip: 'Bilder in Nextcloud werden nicht über WebDAV verarbeitet — nutze dafür die Immich-Integration.' },
        { h: '4. Kalender und Aufgaben', p: 'Über CalDAV greift MYND auf deine Kalender und Aufgaben zu. Frage: "Was steht morgen an?" oder "Zeige meine offenen Aufgaben". MYND kann auch Termine in deinem Kalender erstellen.' },
        { h: '5. Beispiele für Abfragen', p: '— "Durchsuche meine Nextcloud nach dem Dokument mit der Steuererklärung"\n— "Was gibt es Neues im Nextcloud-Ordner Projekte?"\n— "Erstelle einen Termin für nächsten Montag um 10 Uhr"\n— "Zeige meine geteilten Dateien"', tip: 'Je mehr Dateien du in Nextcloud hast, desto länger dauert die erste Indexierung. Nachfolgende Abfragen sind deutlich schneller.' },
      ],
    },
    en: {
      title: 'Nextcloud',
      intro: 'Connect MYND to your Nextcloud instance to browse files, fetch calendars and tasks, and read notifications.',
      steps: [
        { h: '1. Prepare connection details', p: 'You need: (a) your Nextcloud instance URL (e.g. https://nextcloud.example.com), (b) your Nextcloud username, and (c) an app password. Create app passwords in Nextcloud under Settings → Security → "Create app password".', tip: 'Use an app password instead of your main password so MYND only accesses the permitted resources.' },
        { h: '2. Enable the integration in MYND', p: 'Go to Settings → Integrations → Nextcloud. Enter the URL, username and app password. Click "Connect". MYND tests the connection and shows available data sources on success.' },
        { h: '3. WebDAV file access', p: 'MYND accesses your Nextcloud files via WebDAV. You can browse, read and search file contents. Supported formats: PDF, TXT, DOCX, ODT, Markdown, code files and many more.', tip: 'Images in Nextcloud are not processed via WebDAV — use the Immich integration instead.' },
        { h: '4. Calendars and Tasks', p: 'Via CalDAV, MYND accesses your calendars and tasks. Ask: "What\'s on my schedule tomorrow?" or "Show my open tasks". MYND can also create calendar events.' },
        { h: '5. Example queries', p: '— "Search my Nextcloud for the tax return document"\n— "What\'s new in my Projects folder?"\n— "Create an event for next Monday at 10 AM"\n— "Show me my shared files"', tip: 'The more files in Nextcloud, the longer the initial indexing. Subsequent queries are much faster.' },
      ],
    },
  },
  immich: {
    de: {
      title: 'Immich',
      intro: 'Verbinde MYND mit Immich für KI-gestützte Fotoverwaltung und -Suche. Durchsuche deine gesamte Fotobibliothek mit natürlicher Sprache.',
      steps: [
        { h: '1. API-Key in Immich erstellen', p: 'Öffne deine Immich-Instanz im Browser. Gehe zu Einstellungen → Benutzer → API-Key. Klicke auf "Neuer API-Key", gib einen Namen wie "MYND" ein und kopiere den generierten Key. Notiere ihn sicher.', tip: 'Der API-Key wird nur einmal angezeigt. Wenn du ihn verlierst, erstelle einen neuen.' },
        { h: '2. Immich-URL und Key in MYND eintragen', p: 'Gehe zu Settings → Integrations → Immich. Trage deine Immich-Server-URL ein (z. B. https://immich.example.com) und den API-Key. Klicke auf "Connect".', tip: 'Stelle sicher, dass MYND die Immich-API erreichen kann — bei Docker-Konfigurationen kann ein internes Netzwerk nötig sein.' },
        { h: '3. Fotobibliothek durchsuchen', p: 'MYND nutzt die Immich-API, um Metadaten zu deinen Fotos abzurufen: Aufnahmedatum, Kameramodell, Ort, Tags, Gesichter. Die Bilder selbst bleiben in Immich — MYND speichert nur die Metadaten. Aus Datenschutzgründen werden Bilder nicht nach MYND übertragen.', tip: 'Immich analysiert Gesichter und Objekte automatisch. Je länger Immich läuft, desto besser sind die Suchergebnisse.' },
        { h: '4. Beispiele für Abfragen', p: '— "Zeige Fotos von letzter Woche"\n— "Finde alle Bilder mit Strand"\n— "Welche Fotos habe ich im letzten Urlaub gemacht?"\n— "Finde Fotos von [Person]"' },
        { h: '5. Metadaten-Suche und Filter', p: 'Du kannst nach Datumsbereichen, Kameramodellen, Orten und Objekten suchen. MYND kombiniert die Suchparameter intelligent: "Zeige Fotos von letztem Sommer in Italien, die mit einer Sony gemacht wurden."' },
      ],
    },
    en: {
      title: 'Immich',
      intro: 'Connect MYND to Immich for AI-powered photo management and search. Search your entire photo library using natural language.',
      steps: [
        { h: '1. Create an API key in Immich', p: 'Open your Immich instance in the browser. Go to Settings → Users → API Key. Click "New API Key", enter a name like "MYND" and copy the generated key. Store it safely.', tip: 'The API key is shown only once. If you lose it, create a new one.' },
        { h: '2. Enter Immich URL and key in MYND', p: 'Go to Settings → Integrations → Immich. Enter your Immich server URL (e.g. https://immich.example.com) and the API key. Click "Connect".', tip: 'Make sure MYND can reach the Immich API — with Docker setups you may need internal networking.' },
        { h: '3. Search your photo library', p: 'MYND uses the Immich API to retrieve photo metadata: date taken, camera model, location, tags, faces. Images remain in Immich — MYND only stores metadata for privacy reasons.', tip: 'Immich auto-analyzes faces and objects. The longer Immich runs, the better the search results.' },
        { h: '4. Example queries', p: '— "Show photos from last week"\n— "Find all pictures with beaches"\n— "What photos did I take on my last vacation?"\n— "Find photos of [person]"' },
        { h: '5. Metadata search filters', p: 'You can search by date ranges, camera models, locations and objects. MYND combines parameters intelligently: "Show photos from last summer in Italy taken with a Sony camera."' },
      ],
    },
  },
  homeassistant: {
    de: {
      title: 'Home Assistant',
      intro: 'Steuere dein Smart Home über MYND — frage nach Sensordaten, schalte Geräte und führe Automatisierungen aus.',
      steps: [
        { h: '1. Long-Lived Token in Home Assistant erstellen', p: 'Öffne Home Assistant im Browser. Klicke auf dein Profil (unten links in der Sidebar) → "Langzeit-Zugriffstoken". Klicke auf "Token erstellen", gib "MYND" ein und kopiere den Token.', tip: 'Der Token hat volle API-Berechtigung — bewahre ihn sicher auf. Er funktioniert bis zum Widerruf.' },
        { h: '2. URL und Token in MYND eintragen', p: 'Gehe zu Settings → Integrations → Home Assistant. Trage die URL deines Home Assistant ein (z.B. http://homeassistant.local:8123) und den Token. Klicke auf "Connect".', tip: 'Lokale IP-Adressen funktionieren nur, wenn MYND im selben Netzwerk läuft. Verwende bei Bedarf einen Reverse Proxy mit HTTPS.' },
        { h: '3. Verfügbare Entitäten verstehen', p: 'MYND erkennt automatisch alle Entitäten in Home Assistant: Lampen, Thermostate, Sensoren, Schalter, Media Player und mehr. Jede Entität hat Attribute wie Status, Wert, Einheit und letzte Aktualisierung.', tip: 'Wenn eine Entität nicht gefunden wird, prüfe in Home Assistant unter Entwicklerwerkzeuge → Zustände, ob sie existiert.' },
        { h: '4. Aktionen ausführen', p: 'MYND kann Geräte schalten, Werte setzen und Dienste aufrufen. Alle Aktionen werden mit deinem Home-Assistant-Benutzer ausgeführt und im Log protokolliert. Frage: "Schalte das Licht im Wohnzimmer auf 50%", "Stelle den Thermostat auf 21 Grad".' },
        { h: '5. Beispiele für Abfragen', p: '— "Wie ist die Temperatur im Büro?"\n— "Schalte alle Lichter aus"\n— "Ist die Haustür verriegelt?"\n— "Starte die Guten-Morgen-Automation"\n— "Wie viel Strom verbraucht mein Haus gerade?"' },
      ],
    },
    en: {
      title: 'Home Assistant',
      intro: 'Control your smart home through MYND — query sensor data, toggle devices and trigger automations.',
      steps: [
        { h: '1. Create a Long-Lived Token in Home Assistant', p: 'Open Home Assistant in your browser. Click your profile (bottom left in the sidebar) → "Long-Lived Access Token". Click "Create Token", enter "MYND" and copy the token.', tip: 'The token has full API access — store it securely. It works until revoked.' },
        { h: '2. Enter URL and Token in MYND', p: 'Go to Settings → Integrations → Home Assistant. Enter your Home Assistant URL (e.g. http://homeassistant.local:8123) and the token. Click "Connect".', tip: 'Local IPs only work if MYND is on the same network. Use a reverse proxy with HTTPS if needed.' },
        { h: '3. Understand available entities', p: 'MYND automatically discovers all Home Assistant entities: lights, thermostats, sensors, switches, media players and more. Each entity has attributes like state, value, unit and last update.', tip: 'If an entity isn\'t found, check it exists in Home Assistant under Developer Tools → States.' },
        { h: '4. Perform actions', p: 'MYND can toggle devices, set values and call services. All actions are logged against your Home Assistant user. Ask: "Set the living room light to 50%", "Set the thermostat to 21°C".' },
        { h: '5. Example queries', p: '— "What\'s the temperature in the office?"\n— "Turn off all lights"\n— "Is the front door locked?"\n— "Run my good morning automation"\n— "How much power is my house using right now?"' },
      ],
    },
  },
  email: {
    de: {
      title: 'E-Mail',
      intro: 'Verbinde MYND mit deinem E-Mail-Postfach über IMAP/SMTP. Lese Nachrichten, durchsuche das Postfach und sende E-Mails per Sprachbefehl.',
      steps: [
        { h: '1. IMAP/SMTP-Daten bereithalten', p: 'Du benötigst: IMAP-Server-Adresse und Port (für Empfang), SMTP-Server-Adresse und Port (für Versand), sowie Benutzername und Passwort. Typische Server: Gmail (imap.gmail.com:993, smtp.gmail.com:587), Outlook (outlook.office365.com:993, smtp.office365.com:587).', tip: 'Für Gmail benötigst du ein App-Passwort (2FA erforderlich). Erstelle es unter https://myaccount.google.com/apppasswords.' },
        { h: '2. E-Mail-Konto in MYND einrichten', p: 'Gehe zu Settings → Integrations → Email. Klicke auf "Add Account". Wähle einen Anzeigenamen, trage IMAP/SMTP-Daten ein. MYND testet beide Protokolle separat und zeigt bei Erfolg eine grüne Bestätigung.', tip: 'Bei selbstgehosteten Servern: Stelle sicher, dass IMAP und SMTP im Mailserver-Konfiguration aktiviert und vom MYND-Netzwerk aus erreichbar sind.' },
        { h: '3. Postfach durchsuchen', p: 'MYND indiziert E-Mails im Posteingang und in von dir konfigurierten Ordnern. Du kannst nach Absender, Betreff, Datum und Inhalt suchen. PDF-Anhänge werden ebenfalls durchsucht.', tip: 'Standardmäßig werden die letzten 30 Tage indiziert. In den Einstellungen kannst du den Zeitraum vergrößern.' },
        { h: '4. E-Mails senden', p: 'MYND kann in deinem Namen E-Mails senden. Frage: "Sende eine E-Mail an [Adresse] mit dem Betreff [Betreff] und folgendem Inhalt: [Text]". MYND zeigt dir den Entwurf zur Bestätigung, bevor er gesendet wird.', tip: 'Im Zweifelsfall zeigt MYND dir den E-Mail-Entwurf und fragt, ob er gesendet werden soll.' },
        { h: '5. Beispiele für Abfragen', p: '— "Habe ich E-Mails von [Person]?"\n— "Suche die E-Mail mit der Rechnung vom letzten Monat"\n— "Fasse meine ungelesenen E-Mails zusammen"\n— "Sende eine E-Mail an Max: Besprechung morgen um 14 Uhr"', tip: 'MYND kann auch mehrere Postfächer verwalten — lege einfach mehrere Konten an.' },
      ],
    },
    en: {
      title: 'Email',
      intro: 'Connect MYND to your email inbox via IMAP/SMTP. Read messages, search your mailbox and send emails by voice command.',
      steps: [
        { h: '1. Prepare IMAP/SMTP details', p: 'You need: IMAP server address and port (for receiving), SMTP server address and port (for sending), username and password. Typical servers: Gmail (imap.gmail.com:993, smtp.gmail.com:587), Outlook (outlook.office365.com:993, smtp.office365.com:587).', tip: 'For Gmail you need an app password (2FA required). Create one at https://myaccount.google.com/apppasswords.' },
        { h: '2. Set up the email account in MYND', p: 'Go to Settings → Integrations → Email. Click "Add Account". Enter a display name and IMAP/SMTP details. MYND tests both protocols separately and shows a green confirmation on success.', tip: 'For self-hosted servers: make sure IMAP and SMTP are enabled in your mail server config and reachable from MYND\'s network.' },
        { h: '3. Search your mailbox', p: 'MYND indexes emails in the inbox and configured folders. You can search by sender, subject, date and content. PDF attachments are also searchable.', tip: 'By default the last 30 days are indexed. You can increase the window in settings.' },
        { h: '4. Send emails', p: 'MYND can send emails on your behalf. Ask: "Send an email to [address] with subject [subject] and body: [text]". MYND shows you the draft for confirmation before sending.', tip: 'When in doubt, MYND will show the email draft and ask if it should be sent.' },
        { h: '5. Example queries', p: '— "Do I have any emails from [person]?"\n— "Find the invoice email from last month"\n— "Summarize my unread emails"\n— "Send an email to Max: meeting tomorrow at 2 PM"', tip: 'MYND can manage multiple mailboxes — just add multiple accounts.' },
      ],
    },
  },
  spotify: {
    de: {
      title: 'Spotify',
      intro: 'Steuere Spotify über MYND — suche Titel, steuere die Wiedergabe und verwalte Playlists. MYND nutzt die offizielle Spotify-Web-API.',
      steps: [
        { h: '1. Spotify-App im Developer Dashboard erstellen', p: 'Gehe zu https://developer.spotify.com/dashboard und klicke auf "Create App". Gib einen Namen (z.B. "MYND") und eine Beschreibung ein. Setze die Redirect-URI auf http://localhost:5001/callback/spotify', tip: 'Für Produktivbetrieb musst du die Redirect-URI auf deine tatsächliche Domain anpassen, z.B. https://meinedomain.de/callback/spotify.' },
        { h: '2. Client-ID und Client-Secret notieren', p: 'Nach dem Erstellen der App siehst du die Client-ID und kannst das Client-Secret anzeigen. Kopiere beide Werte. Das Secret wird nur einmal vollständig angezeigt.', tip: 'Teile das Client-Secret niemals. Es ist der geheime Schlüssel für die Spotify-API.' },
        { h: '3. Integration in MYND aktivieren', p: 'Gehe zu Settings → Integrations → Spotify. Trage Client-ID und Client-Secret ein und klicke auf "Connect". Du wirst zu Spotify weitergeleitet, um die Verbindung zu autorisieren. MYND speichert das Refresh-Token für dauerhaften Zugriff.' },
        { h: '4. Wiedergabe steuern', p: 'MYND steuert die aktive Wiedergabe auf deinem Spotify-Konto. Du benötigst ein aktives Gerät (Spotify Connect). Frage: "Spiele [Titel] von [Künstler]", "Pausiere die Musik", "Nächster Titel", "Erhöhe die Lautstärke".', tip: 'Spotify Premium ist für die Wiedergabesteuerung erforderlich. Der Free-Tarif erlaubt nur lesenden Zugriff.' },
        { h: '5. Beispiele für Abfragen', p: '— "Spiele meine Discover Weekly Playlist"\n— "Was läuft gerade?"\n— "Suche nach [Song/Artist]"\n— "Erstelle eine Playlist mit dem Namen [Name]"\n— "Füge diesen Song zu meiner Playlist [Name] hinzu"' },
      ],
    },
    en: {
      title: 'Spotify',
      intro: 'Control Spotify through MYND — search tracks, control playback and manage playlists. MYND uses the official Spotify Web API.',
      steps: [
        { h: '1. Create a Spotify app in the Developer Dashboard', p: 'Go to https://developer.spotify.com/dashboard and click "Create App". Enter a name (e.g. "MYND") and description. Set the Redirect URI to http://localhost:5001/callback/spotify', tip: 'For production, update the Redirect URI to your actual domain, e.g. https://mydomain.com/callback/spotify.' },
        { h: '2. Note your Client ID and Client Secret', p: 'After creating the app, you\'ll see the Client ID and can reveal the Client Secret. Copy both values. The secret is shown in full only once.', tip: 'Never share the Client Secret. It\'s the key to the Spotify API.' },
        { h: '3. Enable the integration in MYND', p: 'Go to Settings → Integrations → Spotify. Enter Client ID and Client Secret and click "Connect". You\'ll be redirected to Spotify to authorize the connection. MYND stores the refresh token for permanent access.' },
        { h: '4. Control playback', p: 'MYND controls active playback on your Spotify account. You need an active device (Spotify Connect). Ask: "Play [song] by [artist]", "Pause the music", "Next track", "Increase volume".', tip: 'Spotify Premium is required for playback control. The free tier only allows read-only access.' },
        { h: '5. Example queries', p: '— "Play my Discover Weekly playlist"\n— "What\'s currently playing?"\n— "Search for [song/artist]"\n— "Create a playlist called [name]"\n— "Add this song to my [name] playlist"' },
      ],
    },
  },
  discord: {
    de: {
      title: 'Discord',
      intro: 'Verbinde MYND mit Discord, um Nachrichten zu lesen, zu senden und Kanäle zu durchsuchen — über einen eigenen Bot.',
      steps: [
        { h: '1. Discord-App und Bot erstellen', p: 'Gehe zu https://discord.com/developers/applications. Klicke auf "New Application", gib "MYND" ein. Gehe zu "Bot" → "Add Bot". Kopiere den Bot-Token. Aktiviere unter Bot-Einstellungen "Server Members Intent" und "Message Content Intent".', tip: 'Die Intents sind essenziell — ohne sie kann der Bot keine Mitgliederliste lesen oder Nachrichteninhalte sehen.' },
        { h: '2. Bot auf deinen Server einladen', p: 'Gehe zu "OAuth2" → "URL Generator". Wähle "bot" und dann folgende Berechtigungen: "Send Messages", "Read Message History", "View Channels", "Read Messages". Kopiere die generierte URL und öffne sie — wähle deinen Server aus.', tip: 'Du benötigst "Manage Server"-Rechte auf dem Zielserver, um den Bot einzuladen.' },
        { h: '3. Bot-Token in MYND eintragen', p: 'Gehe zu Settings → Integrations → Discord. Trage den Bot-Token ein und klicke auf "Connect". MYND verbindet sich mit der Discord-API und zeigt die verfügbaren Server und Kanäle an.' },
        { h: '4. Funktionen', p: 'MYND kann: Letzte Nachrichten in Kanälen lesen, Nachrichten senden, nach Inhalten suchen, Erwähnungen anzeigen. Frage: "Was gibt es Neues auf dem [Server]-Server?", "Suche in Discord nach [Suchbegriff]".', tip: 'MYND kann keine Direktnachrichten lesen — es ist auf Kanäle beschränkt, in denen der Bot Mitglied ist.' },
        { h: '5. Beispiele für Abfragen', p: '— "Zeige die letzten Nachrichten im #allgemein Kanal"\n— "Suche in Discord nach dem Link zum Projekt"\n— "Sende eine Nachricht an #team: Ich bin in 5 Minuten da"\n— "Wo wurde [Name] zuletzt erwähnt?"' },
      ],
    },
    en: {
      title: 'Discord',
      intro: 'Connect MYND to Discord to read and send messages and search channels — via a dedicated bot.',
      steps: [
        { h: '1. Create a Discord application and bot', p: 'Go to https://discord.com/developers/applications. Click "New Application", enter "MYND". Go to "Bot" → "Add Bot". Copy the bot token. Under Bot settings, enable "Server Members Intent" and "Message Content Intent".', tip: 'The intents are essential — without them the bot cannot read member lists or message content.' },
        { h: '2. Invite the bot to your server', p: 'Go to "OAuth2" → "URL Generator". Select "bot" and then these permissions: "Send Messages", "Read Message History", "View Channels", "Read Messages". Copy the generated URL and open it — select your server.', tip: 'You need "Manage Server" permissions on the target server to invite the bot.' },
        { h: '3. Enter the bot token in MYND', p: 'Go to Settings → Integrations → Discord. Enter the bot token and click "Connect". MYND connects to the Discord API and shows available servers and channels.' },
        { h: '4. Features', p: 'MYND can: read recent messages in channels, send messages, search content, show mentions. Ask: "What\'s new on the [server] server?", "Search Discord for [query]".', tip: 'MYND cannot read DMs — it\'s limited to channels the bot is a member of.' },
        { h: '5. Example queries', p: '— "Show the latest messages in #general"\n— "Search Discord for the project link"\n— "Send a message to #team: I\'ll be there in 5 minutes"\n— "Where was [name] last mentioned?"' },
      ],
    },
  },
  truenas: {
    de: {
      title: 'TrueNAS',
      intro: 'Überwache dein TrueNAS-System über MYND — Speicherstatus, Dienste, Alerts und SMART-Werte per API.',
      steps: [
        { h: '1. API-Zugang in TrueNAS vorbereiten', p: 'MYND greift über die TrueNAS-API zu. Stelle sicher, dass die API aktiviert ist (Standard ab TrueNAS 12.0+). Du benötigst einen API-Key: Erstelle ihn in TrueNAS unter Einstellungen → API Keys → "Add". Gib einen Namen wie "MYND" ein und kopiere den Key.', tip: 'Der API-Key ersetzt Benutzername/Passwort und ist sicherer. Er wird nur einmal vollständig angezeigt.' },
        { h: '2. TrueNAS-URL und API-Key in MYND eintragen', p: 'Gehe zu Settings → Integrations → TrueNAS. Trage die URL deines TrueNAS-Servers ein (z.B. http://truenas.local:8080 oder https://truenas.example.com). Füge den API-Key ein und klicke auf "Connect".', tip: 'Stelle sicher, dass das MYND-System Netzwerkzugriff auf deinen TrueNAS-Server hat.' },
        { h: '3. Datenspeicher-Status abfragen', p: 'MYND kann den Status aller Pools, Datenträger und Datasets abrufen. Frage: "Wie ist der Speicherstatus?", "Zeige die verfügbaren Pools", "Wie voll ist der Hauptspeicherpool?"', tip: 'Wenn du detaillierte Informationen zu einem bestimmten Pool benötigst, nenne den Namen in der Frage.' },
        { h: '4. SMART-Werte und Alerts überwachen', p: 'MYND liest die SMART-Werte aller Festplatten und zeigt Alerts an. Frage: "Gibt es kritische Alerts?", "Zeige SMART-Status aller Festplatten", "Wie ist der Zustand von [pool]-Pool?"', tip: 'SMART-Langzeittests können je nach Festplattengröße mehrere Stunden dauern.' },
        { h: '5. Beispiele für Abfragen', p: '— "Wie viel Speicher ist noch frei?"\n— "Zeige aktive Dienste auf TrueNAS"\n— "Gibt es fehlerhafte Festplatten?"\n— "Starte ein SMART-Test für [pool]"\n— "Liste alle NFS-Freigaben auf"' },
      ],
    },
    en: {
      title: 'TrueNAS',
      intro: 'Monitor your TrueNAS system through MYND — storage status, services, alerts and SMART values via API.',
      steps: [
        { h: '1. Prepare API access in TrueNAS', p: 'MYND accesses TrueNAS via its API. Make sure the API is enabled (default from TrueNAS 12.0+). You need an API key: Create it in TrueNAS under Settings → API Keys → "Add". Enter a name like "MYND" and copy the key.', tip: 'The API key replaces username/password and is more secure. It is shown in full only once.' },
        { h: '2. Enter TrueNAS URL and API key in MYND', p: 'Go to Settings → Integrations → TrueNAS. Enter your TrueNAS server URL (e.g. http://truenas.local:8080 or https://truenas.example.com). Paste the API key and click "Connect".', tip: 'Make sure the MYND system has network access to your TrueNAS server.' },
        { h: '3. Query storage status', p: 'MYND can retrieve the status of all pools, disks and datasets. Ask: "What\'s the storage status?", "Show available pools", "How full is the main storage pool?"', tip: 'If you need details on a specific pool, mention the name in your question.' },
        { h: '4. Monitor SMART values and alerts', p: 'MYND reads SMART values of all disks and shows alerts. Ask: "Are there any critical alerts?", "Show SMART status of all disks", "What\'s the health of [pool] pool?"', tip: 'SMART long tests can take several hours depending on disk size.' },
        { h: '5. Example queries', p: '— "How much free storage is available?"\n— "Show active services on TrueNAS"\n— "Are there any failing disks?"\n— "Start a SMART test on [pool]"\n— "List all NFS shares"' },
      ],
    },
  },
  browser: {
    de: {
      title: 'Browser',
      intro: 'MYND enthält einen vollwertigen Cloud-Browser mit Stealth-Modus für Web-Recherche. Er kann Seiten öffnen, Screenshots machen und Formulare ausfüllen.',
      steps: [
        { h: '1. Funktionsweise', p: 'Der MYND-Cloud-Browser ist ein kopfloser (headless) Chromium-Browser, der serverseitig läuft. Keine lokale Installation nötig. Er öffnet Webseiten, führt JavaScript aus und erstellt Screenshots — alles isoliert von deinem normalen Browser.', tip: 'Der Cloud-Browser läuft in einer isolierten Umgebung und teilt keine Cookies, Sitzungen oder Erweiterungen mit deinem normalen Browser.' },
        { h: '2. Navigieren und Screenshots', p: 'MYND kann jede öffentlich erreichbare URL öffnen. Bei Seiten, die JS benötigen (SPAs wie React, Vue), wird die Seite vollständig gerendert, bevor ein Screenshot erstellt wird. Frage: "Öffne die Seite [URL]", "Mach einen Screenshot von [URL]".', tip: 'Seiten mit Login-Barrieren können nicht vollständig erfasst werden, wenn MYND keine Zugangsdaten hat.' },
        { h: '3. Textextraktion und Formulare', p: 'MYND kann Text aus Webseiten extrahieren, um Zusammenfassungen zu erstellen. Es kann auch Formulare ausfüllen, wenn genügend Kontext gegeben wird. Frage: "Fasse den Inhalt von [URL] zusammen", "Suche in der Seite nach [Suchbegriff]".' },
        { h: '4. Download-Management', p: 'MYND kann Dateien aus dem Browser herunterladen: `wget` und der integrierte Browser-Download-Manager werden unterstützt. DYI-Dateien, PDFs und andere Dokumente können direkt gespeichert werden.', tip: 'Große Downloads (über 100 MB) werden asynchron verarbeitet — frage nach dem Status.' },
        { h: '5. Technische Details', p: 'Der Cloud-Browser verwendet puppeteer/Playwright unter der Haube. Konfigurierbare Optionen: Viewport-Größe (Standard: 1920x1080), User-Agent, Proxy, Timeout (Standard: 30s), Screenshot-Qualität. Diese Einstellungen findest du in der config.yaml.', tip: 'Bei langsamen Seiten kannst du das Timeout in den Einstellungen erhöhen.' },
      ],
    },
    en: {
      title: 'Browser',
      intro: 'MYND includes a full cloud browser with stealth mode for web research. It can open pages, take screenshots and fill forms.',
      steps: [
        { h: '1. How it works', p: 'The MYND cloud browser is a headless Chromium instance running server-side. No local installation needed. It opens websites, executes JavaScript and captures screenshots — all isolated from your regular browser.', tip: 'The cloud browser runs in an isolated environment and shares no cookies, sessions or extensions with your normal browser.' },
        { h: '2. Navigation and screenshots', p: 'MYND can open any publicly reachable URL. For JS-rendered sites (SPAs like React, Vue), the page is fully rendered before capturing. Ask: "Open [URL]", "Take a screenshot of [URL]".', tip: 'Pages behind logins cannot be fully captured if MYND has no credentials.' },
        { h: '3. Text extraction and forms', p: 'MYND can extract text from web pages to create summaries. It can also fill forms when given enough context. Ask: "Summarize the content of [URL]", "Search the page for [query]".' },
        { h: '4. Download management', p: 'MYND can download files through the browser: `wget` and the built-in browser download manager are both supported. PDFs and other documents can be saved directly.', tip: 'Large downloads (over 100 MB) are processed asynchronously — ask for the status.' },
        { h: '5. Technical details', p: 'The cloud browser uses puppeteer/Playwright under the hood. Configurable options: viewport size (default: 1920x1080), user agent, proxy, timeout (default: 30s), screenshot quality. These settings are in config.yaml.', tip: 'For slow pages, increase the timeout in settings.' },
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
