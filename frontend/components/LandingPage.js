'use client';

import { useState, useEffect } from 'react';
import './LandingPage.css';

const FEATURES = [
  { icon: 'fa-brain', title: 'KI-Chat', desc: 'Frag deine Dokumente, E-Mails und Dateien – MYND versteht Kontext und liefert präzise Antworten.' },
  { icon: 'fa-search', title: 'Semantische Suche', desc: 'Durchsuche tausende Fotos, PDFs und Notizen in Sekunden.' },
  { icon: 'fa-home', title: 'Smart Home', desc: 'Steuere Lichter, Heizung und Geräte per Sprachbefehl.' },
  { icon: 'fa-cloud', title: 'Nextcloud', desc: 'Kalender, Aufgaben, Kontakte und Dateien zentral angebunden.' },
  { icon: 'fa-database', title: 'TrueNAS', desc: 'Überwache Speicherpools, Dienste und Container.' },
  { icon: 'fa-microchip', title: 'Lokale KI', desc: 'Alle Berechnungen auf deinem Rechner. Maximale Privatsphäre.' }
];

const STEPS = [
  { icon: 'fa-server', title: 'Backend starten', desc: 'Läuft auf deinem Mac mini – per Docker oder Python.' },
  { icon: 'fa-wifi', title: 'Verbinden', desc: 'Greife per Browser, Tailscale oder Cloudflare Tunnel zu.' },
  { icon: 'fa-puzzle-piece', title: 'Anbinden', desc: 'Immich, Nextcloud, Home Assistant, TrueNAS konfigurieren.' },
  { icon: 'fa-comment', title: 'Loslegen', desc: 'Fragen, Zusammenfassen, Steuern – alles per Chat.' }
];

const INTEGRATIONS = [
  { icon: 'fa-home', label: 'Home Assistant' },
  { icon: 'fa-camera', label: 'Immich' },
  { icon: 'fa-cloud', label: 'Nextcloud' },
  { icon: 'fa-database', label: 'TrueNAS' },
  { icon: 'fa-video', label: 'Reolink' },
  { icon: 'fa-envelope', label: 'E-Mail' },
  { icon: 'fa-code', label: 'Python' },
  { icon: 'fa-docker', label: 'Docker' }
];

const LANGUAGES = ['de', 'en'];

export default function LandingPage() {
  const [langIdx, setLangIdx] = useState(0);

  useEffect(() => {
    try {
      const stored = localStorage.getItem('mynd_language');
      const idx = LANGUAGES.indexOf(stored);
      if (idx >= 0) setLangIdx(idx);
    } catch {}
  }, []);

  const lang = LANGUAGES[langIdx];
  const _ = (de, en) => lang === 'de' ? de : en;

  const toggleLang = () => {
    const next = lang === 'de' ? 'en' : 'de';
    setLangIdx(LANGUAGES.indexOf(next));
    try { localStorage.setItem('mynd_language', next); } catch {}
  };

  const scrollTo = (id) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div className="lp">
      <nav className="lp-nav">
        <div className="lp-nav-inner">
          <div className="lp-logo">
            <span className="lp-logo-icon">◆</span>
            <span>MYND</span>
          </div>
          <div className="lp-nav-links">
            <button onClick={() => scrollTo('features')}>{_('Features', 'Features')}</button>
            <button onClick={() => scrollTo('how')}>{_('Ablauf', 'Setup')}</button>
            <button onClick={() => scrollTo('tech')}>{_('Technik', 'Tech')}</button>
          </div>
          <div className="lp-nav-right">
            <button className="lp-lang-toggle" onClick={toggleLang}>
              {lang === 'de' ? 'EN' : 'DE'}
            </button>
            <a href="/login" className="lp-btn lp-btn-primary">{_('Anmelden', 'Login')}</a>
          </div>
        </div>
      </nav>

      <section className="lp-hero">
        <div className="lp-hero-content">
          <div className="lp-hero-badge">{_('Lokal & Privat', 'Local & Private')}</div>
          <h1 className="lp-hero-title">
            {_('Dein', 'Your')} <em>{_('Second Brain', 'Second Brain')}</em>
          </h1>
          <p className="lp-hero-sub">
            {_(
              'KI-Chat, Smart Home und Wissensmanagement in einer lokalen Plattform – ohne Cloud.',
              'AI chat, smart home and knowledge management – all local, no cloud.'
            )}
          </p>
          <div className="lp-hero-actions">
            <a href="/login" className="lp-btn lp-btn-primary">
              {_('Jetzt starten', 'Get Started')}
            </a>
            <button className="lp-btn lp-btn-secondary" onClick={() => scrollTo('features')}>
              {_('Mehr erfahren', 'Learn more')}
            </button>
          </div>
        </div>
      </section>

      <section className="lp-section" id="features">
        <div className="lp-section-header">
          <h2>{_('Features', 'Features')}</h2>
          <p>{_('Lokal, sicher, intelligent.', 'Local, secure, intelligent.')}</p>
        </div>
        <div className="lp-features">
          {FEATURES.map((f, i) => (
            <div key={i} className="lp-feature-card" style={{ animationDelay: `${i * 0.06}s` }}>
              <div className="lp-feature-icon">
                <i className={`fas ${f.icon}`} />
              </div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="lp-section" id="how">
        <div className="lp-section-header">
          <h2>{_('Setup', 'Setup')}</h2>
          <p>{_('In Minuten einsatzbereit.', 'Ready in minutes.')}</p>
        </div>
        <div className="lp-steps">
          {STEPS.map((s, i) => (
            <div key={i} className="lp-step">
              <div className="lp-step-icon">
                <i className={`fas ${s.icon}`} />
              </div>
              <h3>{s.title}</h3>
              <p>{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="lp-section" id="tech">
        <div className="lp-section-header">
          <h2>{_('Technik', 'Tech')}</h2>
          <p>{_('Modernste Technologie, maximale Kontrolle.', 'Cutting-edge tech, maximum control.')}</p>
        </div>
        <div className="lp-numbers">
          <div className="lp-number-item">
            <div className="lp-number-value">76+</div>
            <div className="lp-number-label">{_('Tools', 'Tools')}</div>
          </div>
          <div className="lp-number-item">
            <div className="lp-number-value">8</div>
            <div className="lp-number-label">{_('Dienste', 'Services')}</div>
          </div>
          <div className="lp-number-item">
            <div className="lp-number-value">306k</div>
            <div className="lp-number-label">{_('Fotos', 'Photos')}</div>
          </div>
          <div className="lp-number-item">
            <div className="lp-number-value">24/7</div>
            <div className="lp-number-label">{_('Verfügbar', 'Available')}</div>
          </div>
        </div>
        <div className="lp-intro">
          {INTEGRATIONS.map((int, i) => (
            <div key={i} className="lp-intro-item">
              <i className={`fas ${int.icon}`} />
              {int.label}
            </div>
          ))}
        </div>
      </section>

      <div className="lp-cta">
        <h2>{_('Bereit für dein Second Brain?', 'Ready for your Second Brain?')}</h2>
        <p>{_('Starte jetzt.', 'Start now.')}</p>
        <a href="/login" className="lp-btn lp-btn-primary">
          {_('Jetzt starten', 'Get Started')}
        </a>
      </div>

      <footer className="lp-footer">
        <div className="lp-footer-inner">
          <div className="lp-logo" style={{ justifyContent: 'center', marginBottom: '0.5rem' }}>
            <span className="lp-logo-icon">◆</span>
            <span>MYND</span>
          </div>
          <p>{_('Lokal. Privat. Dein Second Brain.', 'Local. Private. Your Second Brain.')}</p>
        </div>
      </footer>
    </div>
  );
}
