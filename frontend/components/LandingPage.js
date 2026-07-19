'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import './LandingPage.css';

const LANGUAGES = ['de', 'en'];

const SCENARIOS = [
  {
    id: 'server',
    icon: 'fa-house-signal',
    service_de: 'Home Assistant',
    service_en: 'Home Assistant',
    q_de: 'Läuft der Server noch?',
    q_en: 'Is the server still up?',
    answer_de: 'Der Server ist online. Im Wohnzimmer sind 21,3 °C, die Werkstatt-Steckdose ist aus, und die PV hat heute 7,2 kWh eingespeist.',
    answer_en: 'The server is online. Living room is 21.3 °C, the workshop socket is off, and solar fed in 7.2 kWh today.',
    tools: [
      { name: 'homeassistant_get_states', result: '33 entities found', duration: '0.4s' },
      { name: 'think', thought_de: 'Der Nutzer fragt nach dem Server-Status. Suche nach System-Sensoren und den wichtigsten Räumen.', thought_en: 'User asks for server status. Looking for system sensors and main rooms.' },
      { name: 'homeassistant_get_history', result: 'PV-Tagesertrag: 7,2 kWh · Temperatur Wohnzimmer: 21,3 °C', duration: '0.3s' },
    ],
    sources: [
      { service: 'Home Assistant', icon: 'fa-house-signal', entries: [
        { label_de: 'System', label_en: 'System', state_de: 'online · 3h uptime', state_en: 'online · 3h uptime' },
        { label_de: 'Wohnzimmer', label_en: 'Living room', state_de: '21,3 °C · 42 %', state_en: '21.3 °C · 42 %' },
        { label_de: 'Werkstatt', label_en: 'Workshop', state_de: 'Steckdose aus', state_en: 'socket off' },
        { label_de: 'PV-Heute', label_en: 'Solar today', state_de: '7,2 kWh', state_en: '7.2 kWh' },
      ]}
    ]
  },
  {
    id: 'search',
    icon: 'fa-globe',
    service_de: 'Browser + Immich',
    service_en: 'Browser + Immich',
    q_de: 'Was gibt es Neues bei den KI-Modellen?',
    q_en: 'Whats new in AI models?',
    answer_de: 'Claude 4 und GPT-5 wurden verglichen. Claude 4 führt in Reasoning-Benchmarks, GPT-5 bei Multimodalität. Hier die Details mit Screenshot.',
    answer_en: 'Claude 4 and GPT-5 have been compared. Claude 4 leads in reasoning benchmarks, GPT-5 in multimodality. Here are the details with a screenshot.',
    tools: [
      { name: 'browser_search', result: 'heise.de: Claude 4 vs GPT-5 im Vergleich · 3 weitere Quellen', duration: '1.2s' },
      { name: 'browser_open', result: 'https://heise.de/ki-vergleich', duration: '0.8s' },
      { name: 'browser_screenshot', result: '📸 Benchmark-Tabelle erfasst', duration: '0.5s' },
      { name: 'think', thought_de: 'Die Seite enthält eine Vergleichstabelle. Extrahiere die wichtigsten Kennzahlen und habe einen Screenshot gemacht.', thought_en: 'The page has a comparison table. Extracting key metrics and took a screenshot.' },
      { name: 'browser_extract', result: 'Claude 4: 89,2 % · GPT-5: 91,7 % (MMLU) · Preis: gleich', duration: '0.6s' },
    ],
    sources: [
      { service: 'Browser', icon: 'fa-globe', entries: [
        { label_de: 'heise.de', label_en: 'heise.de', state_de: 'KI-Vergleich 2026', state_en: 'AI comparison 2026' },
        { label_de: 'Screenshot', label_en: 'Screenshot', state_de: 'Benchmark-Tabelle', state_en: 'benchmark table' },
      ]}
    ]
  },
  {
    id: 'files',
    icon: 'fa-cloud',
    service_de: 'Nextcloud',
    service_en: 'Nextcloud',
    q_de: 'Was gab es diese Woche Neues in Nextcloud?',
    q_en: 'Whats new in Nextcloud this week?',
    answer_de: 'Seit Montag sind 3 Dateien dazugekommen: eine Rechnung (PDF), 12 Urlaubsfotos und aktualisierte Notizen.',
    answer_en: '3 new files since Monday: an invoice (PDF), 12 vacation photos and updated notes.',
    tools: [
      { name: 'nextcloud_list', result: '12 Einträge im Wurzelverzeichnis', duration: '0.3s' },
      { name: 'nextcloud_search', result: '3 Dateien seit Montag geändert', duration: '0.5s' },
      { name: 'think', thought_de: 'Suche nach Dateien, die seit Montag neu sind oder geändert wurden. Sortiere nach Änderungsdatum.', thought_en: 'Looking for files new or modified since Monday. Sorting by modification date.' },
      { name: 'nextcloud_read_file', result: 'Notizen.md · 1.240 Zeichen · Metadaten gelesen', duration: '0.4s' },
    ],
    sources: [
      { service: 'Nextcloud', icon: 'fa-cloud', entries: [
        { label_de: 'Rechnung_März.pdf', label_en: 'invoice_March.pdf', state_de: 'heute · 320 KB', state_en: 'today · 320 KB' },
        { label_de: 'Urlaub_2026/', label_en: 'vacation_2026/', state_de: '12 Fotos · 8 MB', state_en: '12 photos · 8 MB' },
        { label_de: 'Notizen.md', label_en: 'notes.md', state_de: 'gestern · 1,2 KB', state_en: 'yesterday · 1.2 KB' },
      ]}
    ]
  },
];

const METHOD_STEPS = [
  { icon: 'fa-message', title_de: 'Du stellst eine Frage', title_en: 'You ask a question', desc_de: 'Die Frage bestimmt, welche Quelle MYND anzapft.', desc_en: 'The question determines which source MYND queries.' },
  { icon: 'fa-puzzle-piece', title_de: 'MYND sucht in der richtigen Quelle', title_en: 'MYND searches the right source', desc_de: 'Nur aktive und freigegebene Plugins werden verwendet.', desc_en: 'Only active and approved plugins are used.' },
  { icon: 'fa-list-check', title_de: 'Die Antwort zeigt die Herkunft', title_en: 'The answer shows its origin', desc_de: 'Jede Info bleibt mit Zeit und Quelle verknüpfbar.', desc_en: 'Every piece stays linked to its time and source.' },
  { icon: 'fa-shield-halved', title_de: 'Änderungen brauchen dein OK', title_en: 'Changes need your OK', desc_de: 'Bevor MYND etwas schreibt oder schaltet, fragt es nach.', desc_en: 'Before MYND writes or switches anything, it asks.' },
];

const INTEGRATIONS = [
  { icon: 'fa-cloud', type: 'fas', name: 'Nextcloud', detail_de: 'Dateien · Kalender · Aufgaben', detail_en: 'Files · Calendar · Tasks',
    desc_de: 'Vollständige Dateiverwaltung: Ordner durchsuchen, Dokumente lesen, PDFs extrahieren, Kalender-Termine und Aufgaben abrufen. Inklusive Volltextsuche und Datei-Versionierung.',
    desc_en: 'Full file management: browse folders, read documents, extract PDFs, query calendar events and tasks. Includes full-text search and file versioning.',
    tools_de: ['nextcloud_list', 'nextcloud_read_file', 'nextcloud_write_file', 'nextcloud_search', 'nextcloud_caldav_query', 'nextcloud_tasks_query', 'nextcloud_contact_search'],
    tools_en: ['nextcloud_list', 'nextcloud_read_file', 'nextcloud_write_file', 'nextcloud_search', 'nextcloud_caldav_query', 'nextcloud_tasks_query', 'nextcloud_contact_search'] },
  { icon: 'fa-images', type: 'fas', name: 'Immich', detail_de: 'Fotos · Metadaten', detail_en: 'Photos · Metadata',
    desc_de: 'KI-gestützte Fotoverwaltung: Gesichtserkennung, Objekt-Suche, Alben verwalten, Duplikate finden. 270+ API-Endpoints für alles von Metadaten bis zu Erinnerungen.',
    desc_en: 'AI-powered photo management: face recognition, object search, album management, duplicate detection. 270+ API endpoints for everything from metadata to memories.',
    tools_de: ['immich_search_photos', 'immich_list_albums', 'immich_list_people', 'immich_get_server_stats', 'immich_api_request'],
    tools_en: ['immich_search_photos', 'immich_list_albums', 'immich_list_people', 'immich_get_server_stats', 'immich_api_request'] },
  { icon: 'fa-house-signal', type: 'fas', name: 'Home Assistant', detail_de: 'Geräte · Zustände', detail_en: 'Devices · States',
    desc_de: 'Smarthome-Steuerung: Geräte abfragen und schalten, Energieverbrauch, Automatisierungen, Kamera-Streams, History und Logbuch.',
    desc_en: 'Smart home control: query and toggle devices, energy monitoring, automations, camera streams, history and logbook.',
    tools_de: ['homeassistant_get_states', 'homeassistant_turn_on', 'homeassistant_turn_off', 'homeassistant_get_history', 'homeassistant_get_energy'],
    tools_en: ['homeassistant_get_states', 'homeassistant_turn_on', 'homeassistant_turn_off', 'homeassistant_get_history', 'homeassistant_get_energy'] },
  { icon: 'fa-envelope', type: 'fas', name: 'E-Mail', detail_de: 'Postfach · Threads', detail_en: 'Inbox · Threads',
    desc_de: 'IMAP/SMTP-Integration: E-Mails lesen, suchen, senden. Signatur-Erkennung, Thread-Ansicht und Anhänge.',
    desc_en: 'IMAP/SMTP integration: read, search and send emails. Signature detection, thread view and attachments.',
    tools_de: ['email_search', 'email_read', 'email_send', 'email_list_folders', 'email_get_unread'],
    tools_en: ['email_search', 'email_read', 'email_send', 'email_list_folders', 'email_get_unread'] },
  { icon: 'fa-spotify', type: 'fab', name: 'Spotify', detail_de: 'Suche · Wiedergabe', detail_en: 'Search · Playback',
    desc_de: 'Musiksteuerung: Titel suchen und abspielen, Playlists verwalten, Empfehlungen, Lautstärke, Warteschlange.',
    desc_en: 'Music control: search and play tracks, manage playlists, get recommendations, adjust volume, manage queue.',
    tools_de: ['spotify_play', 'spotify_search', 'spotify_get_playlists', 'spotify_get_recommendations', 'spotify_set_volume'],
    tools_en: ['spotify_play', 'spotify_search', 'spotify_get_playlists', 'spotify_get_recommendations', 'spotify_set_volume'] },
  { icon: 'fa-discord', type: 'fab', name: 'Discord', detail_de: 'Kanäle · Nachrichten', detail_en: 'Channels · Messages',
    desc_de: 'Discord-Integration: Nachrichten lesen und senden, Kanäle und Mitglieder auflisten, Threads erstellen, Nachrichten durchsuchen.',
    desc_en: 'Discord integration: read and send messages, list channels and members, create threads, search messages.',
    tools_de: ['discord_send_message', 'discord_read_messages', 'discord_list_channels', 'discord_search_messages', 'discord_list_members'],
    tools_en: ['discord_send_message', 'discord_read_messages', 'discord_list_channels', 'discord_search_messages', 'discord_list_members'] },
  { icon: 'fa-database', type: 'fas', name: 'TrueNAS', detail_de: 'Speicher · Dienste', detail_en: 'Storage · Services',
    desc_de: 'NAS-Verwaltung: Speicher-Status, Dienste steuern, SMART-Daten, Pool- und Dataset-Informationen, Aktualisierungen.',
    desc_en: 'NAS management: storage status, service control, SMART data, pool and dataset info, system updates.',
    tools_de: ['truenas_get_system_info', 'truenas_list_pools', 'truenas_start_service', 'truenas_stop_service', 'truenas_get_alerts'],
    tools_en: ['truenas_get_system_info', 'truenas_list_pools', 'truenas_start_service', 'truenas_stop_service', 'truenas_get_alerts'] },
  { icon: 'fa-globe', type: 'fas', name: 'Browser', detail_de: 'Webseiten · Recherche', detail_en: 'Pages · Research',
    desc_de: 'Vollwertiger Cloud-Browser mit Stealth-Modus: Webseiten öffnen, Screenshots, Formulare ausfüllen, PDFs, Cookies verwalten.',
    desc_en: 'Full cloud browser with stealth mode: open websites, take screenshots, fill forms, PDF export, cookie management.',
    tools_de: ['browser_open', 'browser_search', 'browser_screenshot', 'browser_extract', 'browser_pdf', 'browser_list_downloads'],
    tools_en: ['browser_open', 'browser_search', 'browser_screenshot', 'browser_extract', 'browser_pdf', 'browser_list_downloads'] },
];

const MODES = [
  {
    tier: 'A', icon: 'fa-robot',
    title_de: 'Voll autonom',
    title_en: 'Fully autonomous',
    desc_de: 'MYND entscheidet selbstständig, führt Aktionen aus, schreibt Nachrichten, schaltet Geräte und löscht Dateien — ohne vorherige Rückfrage. Maximale Geschwindigkeit, minimale Kontrolle.',
    desc_en: 'MYND decides independently, executes actions, sends messages, toggles devices and deletes files — without asking first. Maximum speed, minimum oversight.',
    tag_de: 'Unbeaufsichtigt',
    tag_en: 'Unsupervised',
  },
  {
    tier: 'B', icon: 'fa-shield-halved',
    title_de: 'Halb autonom',
    title_en: 'Semi-autonomous',
    desc_de: 'MYND sucht und analysiert selbstständig, legt aber vor jedem schreibenden Schritt — Senden, Löschen, Schalten — eine Bestätigung vor. Der Standard-Modus für den Alltag.',
    desc_en: 'MYND searches and analyses independently but presents a confirmation before every write step — send, delete, toggle. The default mode for everyday use.',
    tag_de: 'Rückfragepflichtig',
    tag_en: 'Confirmation required',
  },
  {
    tier: 'C', icon: 'fa-eye',
    title_de: 'Nicht autonom',
    title_en: 'Non-autonomous',
    desc_de: 'MYND zeigt nur Vorschläge und Entwürfe an. Jede Aktion — vom Nachricht-Senden bis zum Lichtschalten — musst du manuell auslösen. Volle Kontrolle, maximale Transparenz.',
    desc_en: 'MYND only shows suggestions and drafts. Every action — from sending a message to toggling a light — must be triggered manually. Full control, maximum transparency.',
    tag_de: 'Nur Vorschläge',
    tag_en: 'Suggestions only',
  },
];

export default function LandingPage() {
  const [lang, setLang] = useState('de');
  const [active, setActive] = useState(0);
  const [expandedInt, setExpandedInt] = useState(null);

  useEffect(() => {
    try {
      const stored = localStorage.getItem('mynd_language');
      if (LANGUAGES.includes(stored)) setLang(stored);
    } catch {}
  }, []);

  useEffect(() => {
    const id = setInterval(() => {
      setActive((prev) => (prev + 1) % SCENARIOS.length);
    }, 6000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (typeof window !== 'undefined' && window.document) {
      const ld = {
        '@context': 'https://schema.org',
        '@type': 'SoftwareApplication',
        name: 'MYND',
        applicationCategory: 'AIApplication',
        operatingSystem: 'Linux, macOS, Windows',
        offers: { '@type': 'Offer', price: '0', priceCurrency: 'EUR' },
        description: lang === 'de'
          ? 'MYND ist eine lokale Personal-AI-Plattform. Stelle Fragen zu deinen Nextcloud-Dateien, Home-Assistant-Geräten, Immich-Fotos, E-Mails, Discord-Nachrichten, Spotify und mehr — alles auf deiner eigenen Infrastruktur.'
          : 'MYND is a local personal AI platform. Ask questions about your Nextcloud files, Home Assistant devices, Immich photos, emails, Discord messages, Spotify and more — all on your own infrastructure.',
        featureList: SCENARIOS.map(s => lang === 'de' ? s.q_de : s.q_en),
        screenshot: 'https://mynd.ai/og-image.png',
      };
      let el = document.getElementById('lp-ld-json');
      if (!el) {
        el = document.createElement('script');
        el.id = 'lp-ld-json';
        el.type = 'application/ld+json';
        document.head.appendChild(el);
      }
      el.textContent = JSON.stringify(ld);
    }
  }, [lang]);

  const t = (de, en) => lang === 'de' ? de : en;
  const s = SCENARIOS[active];
  const tt = (tool) => tool.thought ? t(tool.thought_de, tool.thought_en) : null;

  const toggleLanguage = () => {
    const next = lang === 'de' ? 'en' : 'de';
    setLang(next);
    try { localStorage.setItem('mynd_language', next); } catch {}
  };

  return (
    <main className="lp" lang={lang} data-auth-view="public">
      <a className="lp-skip" href="#method">{t('Zum Inhalt', 'Skip to content')}</a>

      <header className="lp-nav">
        <nav className="lp-nav-inner" aria-label={t('Hauptnavigation', 'Main navigation')}>
          <a className="lp-logo" href="#top" aria-label="MYND Home">
            <span className="lp-logo-mark" aria-hidden="true"><i /></span>
            <span>MYND</span>
          </a>
        <div className="lp-nav-links">
            <a href="#method">{t('So funktionierts', 'How it works')}</a>
            <a href="#integrations">{t('Integrationen', 'Integrations')}</a>
            <a href="#modes">{t('Betriebsmodi', 'Modes')}</a>
            <Link href="/developers">{t('Entwickler', 'Developers')}</Link>
          </div>
          <div className="lp-nav-actions">
            <button className="lp-language" type="button" onClick={toggleLanguage} aria-label={t('Switch to English', 'Auf Deutsch wechseln')}>
              <span className={lang === 'de' ? 'active' : ''}>DE</span>
              <i aria-hidden="true" />
              <span className={lang === 'en' ? 'active' : ''}>EN</span>
            </button>
            <Link href="/login" className="lp-signin" data-testid="landing-login">
              {t('Anmelden', 'Sign in')} <i className="fas fa-arrow-right" aria-hidden="true" />
            </Link>
          </div>
        </nav>
      </header>

      <section className="lp-hero" id="top">
        <div className="lp-shell lp-hero-grid" id="main-content">
          <div className="lp-hero-copy">
            <p className="lp-eyebrow"><span className="lp-live-dot" /> {t('Personal AI · auf deiner Infrastruktur', 'Personal AI · on your infrastructure')}</p>
            <h1>{t('Nutze dein zweites Gehirn.', 'Use your second brain.')} <em>{t('Nicht irgendeine KI.', 'Not just any AI.')}</em></h1>
            <p className="lp-hero-lede">
              {t(
                'MYND durchsucht genau die Dienste, die du freigibst — und zeigt dir, woher jede Antwort kommt.',
                'MYND searches exactly the services you approve — and shows where every answer came from.'
              )}
            </p>
            <div className="lp-hero-actions">
              <Link href="/login" className="lp-primary-cta">
                <span>{t('Anmelden', 'Sign in')}</span>
                <i className="fas fa-arrow-right" aria-hidden="true" />
              </Link>
              <a href="#method" className="lp-secondary-cta">
                {t('So läuft eine Abfrage ab', 'See how a query runs')}
                <i className="fas fa-arrow-down" aria-hidden="true" />
              </a>
            </div>
          </div>

          <div className="lp-trace" role="region" aria-label={t('Beispiel-Abfrage', 'Example query')} aria-live="polite">
            <div className="lp-trace-topline">
              <div>
                <span className="lp-trace-status" />
                <span>{t('BEISPIEL', 'EXAMPLE')}</span>
                <span className="lp-trace-service">{t(s.service_de, s.service_en)}</span>
              </div>
              <div className="lp-trace-dots">
                {SCENARIOS.map((_, i) => (
                  <button key={i} className={`lp-trace-dot${i === active ? ' is-active' : ''}`}
                    onClick={() => setActive(i)} aria-label={t(`Szenario ${i + 1}`, `Scenario ${i + 1}`)} />
                ))}
              </div>
            </div>

            <div className="lp-trace-query">
              <span className="lp-trace-prompt">Q</span>
              <h2>{t(s.q_de, s.q_en)}</h2>
            </div>

            <div className="lp-trace-tools">
              {s.tools.map((tool, i) => (
                <div key={i} className={`lp-trace-tool${tool.name === 'think' ? ' think' : ''}`}>
                  <span className="lp-trace-tool-icon">{tool.name === 'think' ? '⟳' : '✓'}</span>
                  <span className="lp-trace-tool-name">{tool.name === 'think' ? '' : tool.name}</span>
                  {tt(tool) ? (
                    <span className="lp-trace-tool-thought">{tt(tool)}</span>
                  ) : (
                    <span className="lp-trace-tool-result">{tool.result}</span>
                  )}
                  {tool.duration && <span className="lp-trace-tool-dur">{tool.duration}</span>}
                </div>
              ))}
            </div>

            <div className="lp-trace-map">
              <ol>
                {s.sources.map((group, gi) => (
                  group.entries.map((entry, ei) => (
                    <li key={`${gi}-${ei}`}>
                      <span className="lp-source-icon"><i className={`fas ${group.icon}`} aria-hidden="true" /></span>
                      <div>
                        <strong>{t(entry.label_de, entry.label_en)}</strong>
                        <span>{t(entry.state_de, entry.state_en)}</span>
                      </div>
                    </li>
                  ))
                ))}
              </ol>
            </div>

            <div className="lp-trace-answer">
              <span className="lp-trace-answer-label">{t('ANTWORT', 'ANSWER')}</span>
              <p>{t(s.answer_de, s.answer_en)}</p>
              <div className="lp-trace-sources">
                <span>{s.sources.length} {t('Quelle(n)', 'source(s)')}</span>
                <span><i className={`fas ${s.icon}`} aria-hidden="true" /> {t(s.service_de, s.service_en)}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <aside className="lp-ticker" aria-label={t('Systemprinzipien', 'System principles')}>
        <div className="lp-shell lp-ticker-track">
          <p><span>01</span><strong>{t('Lokal betrieben', 'Runs locally')}</strong><small>{t('Auf deinem Server oder Rechner', 'On your own server or machine')}</small></p>
          <p><span>02</span><strong>{t('Quellen bleiben sichtbar', 'Sources stay visible')}</strong><small>{t('Antworten mit Herkunftsnachweis', 'Answers with source attribution')}</small></p>
          <p><span>03</span><strong>{t('Drei Betriebsmodi', 'Three operating modes')}</strong><small>{t('Von voll autonom bis reiner Vorschlagsmodus', 'From fully autonomous to suggestions only')}</small></p>
        </div>
      </aside>

      <section className="lp-method lp-section" id="method">
        <div className="lp-shell">
          <header className="lp-method-header">
            <div>
              <p className="lp-kicker">{t('Vom Satz zur Antwort', 'From sentence to answer')}</p>
              <h2>{t('Vier Schritte. Eine Frage.', 'Four steps. One question.')}</h2>
            </div>
            <p>{t('Du sagst, was du wissen willst. MYND sucht in den freigegebenen Quellen, zeigt die Fundstellen und fragt, bevor es etwas ändert.', 'You say what you want to know. MYND searches approved sources, shows the findings and asks before changing anything.')}</p>
          </header>
          <ol className="lp-method-steps">
            {METHOD_STEPS.map((step, i) => (
              <li key={i}>
                <div className="lp-step-top"><span>{String(i + 1).padStart(2, '0')}</span><i className={`fas ${step.icon}`} aria-hidden="true" /></div>
                <h3>{t(step.title_de, step.title_en)}</h3>
                <p>{t(step.desc_de, step.desc_en)}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="lp-integrations lp-section" id="integrations">
        <div className="lp-shell">
          <header className="lp-integrations-header">
            <div>
              <p className="lp-kicker">{t('Anbindungen', 'Connections')}</p>
              <h2>{t('Deine Dienste, deine Regeln.', 'Your services, your rules.')}</h2>
            </div>
            <p>{t('Jedes Plugin arbeitet nur, wenn du es einrichtest und freigibst. Tippe auf eine Karte für Details.', 'Every plugin only works after you set it up and approve it. Tap a card for details.')}</p>
          </header>
          <div className="lp-integration-matrix">
            {INTEGRATIONS.map((item, i) => (
              <article key={item.name} className={`lp-integration${expandedInt === i ? ' is-expanded' : ''}`}
                onClick={() => setExpandedInt(expandedInt === i ? null : i)}
                role="button" tabIndex={0} aria-expanded={expandedInt === i}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setExpandedInt(expandedInt === i ? null : i); } }}>
                <span className="lp-integration-index">{String(i + 1).padStart(2, '0')}</span>
                <i className={`${item.type} ${item.icon}`} aria-hidden="true" />
                <div><h3>{item.name}</h3><p>{t(item.detail_de, item.detail_en)}</p></div>
                <span className="lp-integration-port" aria-hidden="true"><i className="fas fa-chevron-down" /></span>
                {expandedInt === i && (
                  <div className="lp-integration-detail">
                    <p className="lp-integration-desc">{t(item.desc_de, item.desc_en)}</p>
                    <div className="lp-integration-tools">
                      <span className="lp-meta-label">{t('WERKZEUGE', 'TOOLS')}</span>
                      {t(item.tools_de, item.tools_en).map((tool) => (
                        <span className="lp-source-chip" key={tool}>{tool}</span>
                      ))}
                    </div>
                  </div>
                )}
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="lp-modes lp-section" id="modes">
        <div className="lp-shell">
          <header className="lp-modes-header">
            <div>
              <p className="lp-kicker">{t('Betriebsmodi', 'Operating modes')}</p>
              <h2>{t('So viel Kontrolle, wie du willst.', 'As much control as you want.')}</h2>
            </div>
            <p>{t('MYND kann in drei Stufen arbeiten. Du entscheidest, wie viel Eigenständigkeit die KI bekommt — von völlig frei bis jede Aktion manuell.', 'MYND can operate at three levels. You decide how much autonomy the AI has — from completely free to every action manual.')}</p>
          </header>
          <div className="lp-modes-grid">
            {MODES.map((mode) => (
              <article key={mode.tier} className="lp-mode-card">
                <div className="lp-mode-tag">{t(mode.tag_de, mode.tag_en)}</div>
                <div className="lp-mode-top">
                  <span className="lp-mode-tier">{mode.tier}</span>
                  <i className={`fas ${mode.icon}`} aria-hidden="true" />
                </div>
                <h3>{t(mode.title_de, mode.title_en)}</h3>
                <p>{t(mode.desc_de, mode.desc_en)}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="lp-final">
        <div className="lp-final-rule" aria-hidden="true"><span /></div>
        <p className="lp-kicker">{t('Bereit für eine echte Frage?', 'Ready for a real question?')}</p>
        <h2>{t('Los gehts.', 'Lets go.')}</h2>
        <Link href="/login" className="lp-primary-cta lp-final-cta">
          <span>{t('Anmelden', 'Sign in')}</span><i className="fas fa-arrow-right" aria-hidden="true" />
        </Link>
      </section>

      <footer className="lp-footer">
        <div className="lp-shell lp-footer-inner">
          <a className="lp-logo" href="#top"><span className="lp-logo-mark" aria-hidden="true"><i /></span><span>MYND</span></a>
          <p>© {new Date().getFullYear()} MYND</p>
          <a href="#modes">{t('Betriebsmodi', 'Operating modes')}</a>
        </div>
      </footer>
    </main>
  );
}
