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
      intro: 'MYND ist deine lokale Personal-AI-Plattform. Stelle Fragen zu deinen Dateien, Geräten und Diensten — alles läuft auf deiner eigenen Infrastruktur.',
      steps: [
        { h: '1. Server starten', p: 'Starte den MYND-Backend-Server mit \'python app.py\' im Hauptverzeichnis. Der Server läuft standardmäßig auf Port 5001.' },
        { h: '2. Frontend öffnen', p: 'Öffne das Frontend im Browser. Lokal erreichst du es über http://localhost:3000. Im Produktivbetrieb konfiguriere einen Reverse Proxy (z.B. nginx).' },
        { h: '3. Account erstellen', p: 'Klicke auf "Anmelden" und dann auf "Account erstellen". Lege Benutzernamen und Passwort fest.' },
        { h: '4. KI-Modell wählen', p: 'Nach dem Login wähle im Dashboard dein KI-Modell aus. MYND unterstützt alle Ollama-Modelle sowie OpenAI-kompatible APIs.' },
        { h: '5. Integrationen aktivieren', p: 'Gehe in die Einstellungen und verbinde die gewünschten Dienste (Nextcloud, Immich, Home Assistant etc.).' },
      ],
    },
    en: {
      title: 'Getting Started',
      intro: 'MYND is your local personal AI platform. Ask questions about your files, devices and services — everything runs on your own infrastructure.',
      steps: [
        { h: '1. Start the server', p: 'Run \'python app.py\' in the root directory. The backend server starts on port 5001 by default.' },
        { h: '2. Open the frontend', p: 'Open the frontend in your browser. Locally it\'s at http://localhost:3000. For production, configure a reverse proxy (e.g. nginx).' },
        { h: '3. Create an account', p: 'Click "Sign in" then "Create account". Choose a username and password.' },
        { h: '4. Select an AI model', p: 'After login, select your AI model in the dashboard. MYND supports all Ollama models and OpenAI-compatible APIs.' },
        { h: '5. Enable integrations', p: 'Go to Settings and connect the services you use (Nextcloud, Immich, Home Assistant, etc.).' },
      ],
    },
  },
  'ai-setup': {
    de: {
      title: 'KI einrichten',
      intro: 'MYND benötigt ein laufendes Ollama oder einen OpenAI-kompatiblen Anbieter.',
      steps: [
        { h: 'Ollama installieren', p: 'Lade Ollama von https://ollama.com herunter und installiere es. Starte es mit \'ollama serve\'.' },
        { h: 'Modell pullen', p: 'Lade ein Modell herunter, z.B. \'ollama pull llama3.2\' oder \'ollama pull mistral\'. Für Werkzeug-Nutzung empfehlen wir llama3.2 oder qwen2.5.' },
        { h: 'In MYND verbinden', p: 'Gehe in den Einstellungen auf "KI". Trage die Ollama-URL ein (meist http://127.0.0.1:11434) und wähle dein Modell aus.' },
        { h: 'OpenAI-kompatible APIs', p: 'Du kannst auch jeden OpenAI-kompatiblen Anbieter nutzen (z.B. OpenAI, Groq, Together). Wähle "OpenAI" als Provider und trage Base-URL und API-Key ein.' },
      ],
    },
    en: {
      title: 'AI Setup',
      intro: 'MYND requires a running Ollama instance or an OpenAI-compatible provider.',
      steps: [
        { h: 'Install Ollama', p: 'Download Ollama from https://ollama.com and install it. Run \'ollama serve\' to start.' },
        { h: 'Pull a model', p: 'Download a model, e.g. \'ollama pull llama3.2\' or \'ollama pull mistral\'. For tool use, we recommend llama3.2 or qwen2.5.' },
        { h: 'Connect in MYND', p: 'Go to Settings → AI. Enter the Ollama URL (usually http://127.0.0.1:11434) and select your model.' },
        { h: 'OpenAI-compatible APIs', p: 'You can also use any OpenAI-compatible provider (e.g. OpenAI, Groq, Together). Select "OpenAI" as provider and enter Base URL and API key.' },
      ],
    },
  },
  nextcloud: {
    de: {
      title: 'Nextcloud',
      intro: 'Verbinde MYND mit deiner Nextcloud-Instanz, um Dateien zu durchsuchen, Kalender und Aufgaben abzurufen.',
      steps: [
        { h: 'Nextcloud-URL eintragen', p: 'Gehe in die Einstellungen → Nextcloud. Trage die URL deiner Nextcloud-Instanz ein (z.B. https://nextcloud.example.com).' },
        { h: 'Anmeldedaten hinterlegen', p: 'Gib Benutzername und Passwort ein. MYND nutzt WebDAV für Dateien und CalDAV für Kalender.' },
        { h: 'Verbindung testen', p: 'Klicke auf "Verbinden". Bei Erfolg siehst du deine Nextcloud-Dateien und Kalender.' },
        { h: 'Nutzung', p: 'Frage MYND: "Was gibt es Neues in Nextcloud?" oder "Zeige meine Termine für morgen."' },
      ],
    },
    en: {
      title: 'Nextcloud',
      intro: 'Connect MYND to your Nextcloud instance to browse files, fetch calendars and tasks.',
      steps: [
        { h: 'Enter Nextcloud URL', p: 'Go to Settings → Nextcloud. Enter your Nextcloud instance URL (e.g. https://nextcloud.example.com).' },
        { h: 'Enter credentials', p: 'Enter your username and password. MYND uses WebDAV for files and CalDAV for calendars.' },
        { h: 'Test the connection', p: 'Click "Connect". On success, you\'ll see your Nextcloud files and calendars.' },
        { h: 'Usage', p: 'Ask MYND: "What\'s new in Nextcloud?" or "Show my appointments for tomorrow."' },
      ],
    },
  },
  immich: {
    de: {
      title: 'Immich',
      intro: 'Verbinde MYND mit Immich für KI-gestützte Fotoverwaltung und -Suche.',
      steps: [
        { h: 'Immich-URL eintragen', p: 'Gehe zu den Einstellungen → Immich. Trage die URL deines Immich-Servers ein.' },
        { h: 'API-Key erstellen', p: 'In Immich: Gehe zu Einstellungen → API-Key und erstelle einen neuen Key. Kopiere ihn nach MYND.' },
        { h: 'Verbindung testen', p: 'Klicke auf "Verbinden". Bei Erfolg siehst du deine Fotobibliothek.' },
        { h: 'Nutzung', p: 'Frage: "Zeige Fotos von letzter Woche" oder "Finde Bilder mit Hunden."' },
      ],
    },
    en: {
      title: 'Immich',
      intro: 'Connect MYND to Immich for AI-powered photo management and search.',
      steps: [
        { h: 'Enter Immich URL', p: 'Go to Settings → Immich. Enter your Immich server URL.' },
        { h: 'Create API key', p: 'In Immich: Go to Settings → API Key and create a new key. Copy it into MYND.' },
        { h: 'Test connection', p: 'Click "Connect". On success, your photo library will be available.' },
        { h: 'Usage', p: 'Ask: "Show photos from last week" or "Find pictures with dogs."' },
      ],
    },
  },
  homeassistant: {
    de: {
      title: 'Home Assistant',
      intro: 'Steuere dein Smart Home über MYND — frage nach Zuständen und schalte Geräte.',
      steps: [
        { h: 'Long-Lived Token erstellen', p: 'In Home Assistant: Gehe zu deinem Profil → "Langzeit-Zugriffstoken" und erstelle einen neuen Token.' },
        { h: 'URL und Token eintragen', p: 'In MYND-Einstellungen → Home Assistant: Trage die URL (z.B. http://homeassistant.local:8123) und den Token ein.' },
        { h: 'Nutzung', p: 'Frage: "Wie ist die Temperatur im Wohnzimmer?" oder "Schalte das Licht im Büro aus."' },
      ],
    },
    en: {
      title: 'Home Assistant',
      intro: 'Control your smart home through MYND — query states and toggle devices.',
      steps: [
        { h: 'Create Long-Lived Token', p: 'In Home Assistant: Go to your profile → "Long-Lived Access Token" and create a new token.' },
        { h: 'Enter URL and Token', p: 'In MYND Settings → Home Assistant: Enter the URL (e.g. http://homeassistant.local:8123) and the token.' },
        { h: 'Usage', p: 'Ask: "What\'s the temperature in the living room?" or "Turn off the office light."' },
      ],
    },
  },
  email: {
    de: {
      title: 'E-Mail',
      intro: 'Verbinde MYND mit deinem E-Mail-Postfach über IMAP/SMTP.',
      steps: [
        { h: 'IMAP/SMTP-Daten bereithalten', p: 'Du benötigst: IMAP-Server (für Empfang), SMTP-Server (für Versand), Benutzername und Passwort.' },
        { h: 'Konto einrichten', p: 'In MYND-Einstellungen → E-Mail: Lege ein neues Konto an. Gängige Anbieter (Gmail, Outlook, etc.) haben vorgegebene Ports.' },
        { h: 'Verbindung testen', p: 'Klicke auf "Verbinden". MYND testet IMAP und SMTP getrennt.' },
        { h: 'Hinweis', p: 'Bei Gmail benötigst du ein App-Passwort. Bei selbstgehosteten Servern stelle sicher, dass IMAP und SMTP freigegeben sind.' },
      ],
    },
    en: {
      title: 'Email',
      intro: 'Connect MYND to your email inbox via IMAP/SMTP.',
      steps: [
        { h: 'Prepare IMAP/SMTP details', p: 'You need: IMAP server (for receiving), SMTP server (for sending), username and password.' },
        { h: 'Set up account', p: 'In MYND Settings → Email: Create a new account. Common providers (Gmail, Outlook, etc.) have preset ports.' },
        { h: 'Test connection', p: 'Click "Connect". MYND tests IMAP and SMTP separately.' },
        { h: 'Note', p: 'For Gmail you need an app password. For self-hosted servers, make sure IMAP and SMTP are enabled.' },
      ],
    },
  },
  spotify: {
    de: {
      title: 'Spotify',
      intro: 'Steuere Spotify über MYND — suche Titel, steuere die Wiedergabe und verwalte Playlists.',
      steps: [
        { h: 'Client-ID und Secret besorgen', p: 'Gehe zum Spotify Developer Dashboard (https://developer.spotify.com/dashboard) und erstelle eine App. Kopiere Client-ID und Client-Secret.' },
        { h: 'Redirect-URI setzen', p: 'Setze in der Spotify-App die Redirect-URI auf http://localhost:5001/callback/spotify (oder deine Produktions-URL).' },
        { h: 'In MYND einrichten', p: 'Gehe zu den Einstellungen → Spotify. Trage Client-ID und Secret ein und autorisiere die Verbindung.' },
        { h: 'Nutzung', p: 'Frage: "Spiele Musik von [Künstler]" oder "Was läuft gerade in meinen Playlists?"' },
      ],
    },
    en: {
      title: 'Spotify',
      intro: 'Control Spotify through MYND — search tracks, control playback and manage playlists.',
      steps: [
        { h: 'Get Client ID and Secret', p: 'Go to the Spotify Developer Dashboard (https://developer.spotify.com/dashboard) and create an app. Copy the Client ID and Client Secret.' },
        { h: 'Set Redirect URI', p: 'In the Spotify app, set the Redirect URI to http://localhost:5001/callback/spotify (or your production URL).' },
        { h: 'Set up in MYND', p: 'Go to Settings → Spotify. Enter Client ID and Secret and authorize the connection.' },
        { h: 'Usage', p: 'Ask: "Play music by [artist]" or "What\'s playing in my playlists?"' },
      ],
    },
  },
  discord: {
    de: {
      title: 'Discord',
      intro: 'Verbinde MYND mit Discord, um Nachrichten zu lesen, zu senden und Kanäle zu durchsuchen.',
      steps: [
        { h: 'Discord-App erstellen', p: 'Gehe zum Discord Developer Portal (https://discord.com/developers/applications) und erstelle eine neue App.' },
        { h: 'Bot erstellen', p: 'Gehe zu "Bot" und erstelle einen Bot. Kopiere den Token.' },
        { h: 'Bot einladen', p: 'Erstelle einen OAuth2-Link mit den Berechtigungen "Send Messages", "Read Message History", "View Channels". Lade den Bot auf deinen Server ein.' },
        { h: 'In MYND einrichten', p: 'Gehe zu den Einstellungen → Discord. Trage den Bot-Token ein.' },
      ],
    },
    en: {
      title: 'Discord',
      intro: 'Connect MYND to Discord to read and send messages and search channels.',
      steps: [
        { h: 'Create Discord App', p: 'Go to the Discord Developer Portal (https://discord.com/developers/applications) and create a new app.' },
        { h: 'Create Bot', p: 'Go to "Bot" and create a bot. Copy the token.' },
        { h: 'Invite Bot', p: 'Create an OAuth2 URL with "Send Messages", "Read Message History", "View Channels" permissions. Invite the bot to your server.' },
        { h: 'Set up in MYND', p: 'Go to Settings → Discord. Enter the bot token.' },
      ],
    },
  },
  truenas: {
    de: {
      title: 'TrueNAS',
      intro: 'Überwache dein TrueNAS-System über MYND — Speicherstatus, Dienste und Alerts.',
      steps: [
        { h: 'TrueNAS-Zugang vorbereiten', p: 'Stelle sicher, dass SSH auf deinem TrueNAS-Server aktiviert ist und du die Zugangsdaten hast.' },
        { h: 'Zugangsdaten hinterlegen', p: 'In MYND-Einstellungen → TrueNAS: Trage die IP, den Benutzernamen und das Passwort ein.' },
        { h: 'Nutzung', p: 'Frage: "Wie ist der Speicherstatus?" oder "Zeige aktuelle TrueNAS-Alerts."' },
      ],
    },
    en: {
      title: 'TrueNAS',
      intro: 'Monitor your TrueNAS system through MYND — storage status, services and alerts.',
      steps: [
        { h: 'Prepare TrueNAS access', p: 'Make sure SSH is enabled on your TrueNAS server and you have the credentials ready.' },
        { h: 'Enter credentials', p: 'In MYND Settings → TrueNAS: Enter the IP, username and password.' },
        { h: 'Usage', p: 'Ask: "What\'s the storage status?" or "Show current TrueNAS alerts."' },
      ],
    },
  },
  browser: {
    de: {
      title: 'Browser',
      intro: 'MYND enthält einen vollwertigen Cloud-Browser mit Stealth-Modus für Web-Recherche.',
      steps: [
        { h: 'Browser-Konfiguration', p: 'MYND nutzt einen browserlosen Cloud-Browser. Keine Einrichtung nötig — er funktioniert sofort.' },
        { h: 'Verfügbare Aktionen', p: 'MYND kann: Webseiten öffnen, Screenshots machen, Texte extrahieren, Formulare ausfüllen, PDFs exportieren, Downloads verwalten.' },
        { h: 'Stealth-Modus', p: 'Der Browser verwendet einen separaten User-Agent und Proxy. Keine Cookies oder Sitzungen werden zwischen MYND und deinem normalen Browser geteilt.' },
        { h: 'Nutzung', p: 'Frage: "Öffne die Seite [URL]" oder "Suche nach [Suchbegriff]" oder "Mach einen Screenshot von [URL]".' },
      ],
    },
    en: {
      title: 'Browser',
      intro: 'MYND includes a full cloud browser with stealth mode for web research.',
      steps: [
        { h: 'Browser setup', p: 'MYND uses a headless cloud browser. No setup required — it works out of the box.' },
        { h: 'Available actions', p: 'MYND can: open websites, take screenshots, extract text, fill forms, export PDFs, manage downloads.' },
        { h: 'Stealth mode', p: 'The browser uses a separate user-agent and proxy. No cookies or sessions are shared between MYND and your normal browser.' },
        { h: 'Usage', p: 'Ask: "Open the page [URL]" or "Search for [query]" or "Take a screenshot of [URL]".' },
      ],
    },
  },
};

export default function GuidePage() {
  const [lang, setLang] = useState('de');
  const [activeSection, setActiveSection] = useState('getting-started');

  useEffect(() => {
    try {
      const stored = localStorage.getItem('mynd_language');
      if (stored === 'en' || stored === 'de') setLang(stored);
    } catch {}
    const mode = (() => { try { return localStorage.getItem('darkMode') || 'light'; } catch(e) { return 'light'; } })();
    document.documentElement.setAttribute('data-mode', mode);
  }, []);

  const t = (de, en) => lang === 'de' ? de : en;
  const content = GUIDE[activeSection]?.[lang] || GUIDE[activeSection]?.de;

  return (
    <div className="guide-page" lang={lang}>
      <nav className="guide-nav">
        <div className="guide-nav-inner">
          <Link href="/" className="guide-logo">
            <span className="guide-logo-mark" aria-hidden="true"><i /></span>
            <span>MYND</span>
          </Link>
          <button className="guide-lang-toggle" type="button" onClick={() => setLang(l => l === 'de' ? 'en' : 'de')}>
            {lang === 'de' ? 'EN' : 'DE'}
          </button>
        </div>
      </nav>

      <div className="guide-layout">
        <aside className="guide-sidebar">
          <nav aria-label={t('Navigation', 'Navigation')}>
            {SECTIONS.map(s => (
              <button
                key={s.id}
                className={`guide-sidebar-link${activeSection === s.id ? ' active' : ''}`}
                onClick={() => setActiveSection(s.id)}
              >
                <i className={`fas ${s.icon}`} />
                {s[`label_${lang}`] || s.label_de}
              </button>
            ))}
          </nav>
        </aside>

        <main className="guide-main">
          {content && (
            <>
              <h1 className="guide-title">
                <i className={`fas ${SECTIONS.find(s => s.id === activeSection)?.icon}`} />
                {' '}{content.title}
              </h1>
              <p className="guide-intro">{content.intro}</p>
              <div className="guide-steps">
                {content.steps.map((step, i) => (
                  <div key={i} className="guide-step">
                    <h2 className="guide-step-heading">{step.h}</h2>
                    <p>{step.p}</p>
                  </div>
                ))}
              </div>
            </>
          )}
          <div className="guide-footer">
            <Link href="/developers">{t('Entwickler-Dokumentation', 'Developer Documentation')}</Link>
            {' · '}
            <Link href="/login">{t('Zum Login', 'Go to Login')}</Link>
          </div>
        </main>
      </div>
    </div>
  );
}
