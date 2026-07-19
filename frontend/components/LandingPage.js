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
      { name: 'think', thought: 'Der Nutzer fragt nach dem Server-Status. Ich suche nach System-Sensoren + den wichtigsten Räumen.' },
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
      { name: 'think', thought: 'Die Seite enthält eine Vergleichstabelle. Ich extrahiere die wichtigsten Kennzahlen und habe einen Screenshot gemacht.' },
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
      { name: 'nextcloud_search', result: `3 Dateien seit Montag geändert`, duration: '0.5s' },
      { name: 'think', thought: 'Ich suche nach Dateien, die seit Montag neu sind oder geändert wurden. Sortiere nach Änderungsdatum.' },
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
  { icon: 'fa-cloud', type: 'fas', name: 'Nextcloud', detail_de: 'Dateien · Kalender · Aufgaben', detail_en: 'Files · Calendar · Tasks' },
  { icon: 'fa-images', type: 'fas', name: 'Immich', detail_de: 'Fotos · Metadaten', detail_en: 'Photos · Metadata' },
  { icon: 'fa-house-signal', type: 'fas', name: 'Home Assistant', detail_de: 'Geräte · Zustände', detail_en: 'Devices · States' },
  { icon: 'fa-envelope', type: 'fas', name: 'E-Mail', detail_de: 'Postfach · Threads', detail_en: 'Inbox · Threads' },
  { icon: 'fa-spotify', type: 'fab', name: 'Spotify', detail_de: 'Suche · Wiedergabe', detail_en: 'Search · Playback' },
  { icon: 'fa-discord', type: 'fab', name: 'Discord', detail_de: 'Kanäle · Nachrichten', detail_en: 'Channels · Messages' },
  { icon: 'fa-database', type: 'fas', name: 'TrueNAS', detail_de: 'Speicher · Dienste', detail_en: 'Storage · Services' },
  { icon: 'fa-globe', type: 'fas', name: 'Browser', detail_de: 'Webseiten · Recherche', detail_en: 'Pages · Research' },
];

const CONTROLS = [
  { title_de: 'Freigabe pro Quelle', title_en: 'Per-source approval', desc_de: 'Jeder Dienst bleibt ausgeschaltet, bis du ihn aktivierst.', desc_en: 'Every service stays off until you enable it.' },
  { title_de: 'Kein Rundumschlag', title_en: 'No blanket scan', desc_de: 'MYND fragt nur den Dienst ab, den die Frage braucht.', desc_en: 'MYND only queries the service the question needs.' },
  { title_de: 'Bestätigung vor Eingriff', title_en: 'Confirm before action', desc_de: 'Senden, löschen, schalten — erst nach deiner Bestätigung.', desc_en: 'Send, delete, toggle — only after your confirmation.' },
];

export default function LandingPage() {
  const [lang, setLang] = useState('de');
  const [active, setActive] = useState(0);

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

  const t = (de, en) => lang === 'de' ? de : en;
  const s = SCENARIOS[active];

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
            <a href="#control">{t('Kontrolle', 'Control')}</a>
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
                  {tool.thought ? (
                    <span className="lp-trace-tool-thought">{tool.thought}</span>
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
          <p><span>03</span><strong>{t('Aktionen brauchen Zustimmung', 'Actions need consent')}</strong><small>{t('Bestätigung vor schreibenden Schritten', 'Confirmation before write steps')}</small></p>
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
            <p>{t('Jedes Plugin arbeitet nur, wenn du es einrichtest und freigibst.', 'Every plugin only works after you set it up and approve it.')}</p>
          </header>
          <div className="lp-integration-matrix">
            {INTEGRATIONS.map((item, i) => (
              <article className="lp-integration" key={item.name}>
                <span className="lp-integration-index">{String(i + 1).padStart(2, '0')}</span>
                <i className={`${item.type} ${item.icon}`} aria-hidden="true" />
                <div><h3>{item.name}</h3><p>{t(item.detail_de, item.detail_en)}</p></div>
                <span className="lp-integration-port" aria-hidden="true" />
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="lp-control lp-section" id="control">
        <div className="lp-shell lp-control-grid">
          <header className="lp-control-header">
            <p className="lp-kicker">{t('Kontrolle', 'Control')}</p>
            <h2>{t('Du behältst den Überblick.', 'You stay in control.')}</h2>
            <p>{t('MYND läuft lokal. Was freigegeben ist, bestimmst du — und was MYND damit macht, siehst du vorher.', 'MYND runs locally. You decide what is shared — and you see what MYND does with it beforehand.')}</p>
          </header>
          <div className="lp-control-list">
            {CONTROLS.map((item, i) => (
              <article key={i}>
                <span>{['A', 'B', 'C'][i]}</span>
                <div><h3>{t(item.title_de, item.title_en)}</h3><p>{t(item.desc_de, item.desc_en)}</p></div>
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
          <a href="#control">{t('Kontrolle & Privatsphäre', 'Control & privacy')}</a>
        </div>
      </footer>
    </main>
  );
}
