'use client';

import { useState, useEffect } from 'react';
import './LandingPage.css';

const FEATURES = [
  { icon: 'fa-brain', title: 'KI-Chat mit Kontext', desc: 'Stell Fragen zu deinen Dokumenten, E-Mails und Dateien. MYND versteht den Zusammenhang und liefert präzise Antworten.' },
  { icon: 'fa-search', title: 'Semantische Suche', desc: 'Durchsuche tausende Fotos, PDFs und Notizen in Sekunden – ohne manuelle Verschlagwortung.' },
  { icon: 'fa-home', title: 'Smart Home Steuerung', desc: 'Steuere Lichter, Heizung und Geräte per Sprachbefehl. Home Assistant und Reolink integriert.' },
  { icon: 'fa-cloud', title: 'Nextcloud & mehr', desc: 'Kalender, Aufgaben, Kontakte und Dateien – alle deine Daten an einem Ort, lokal und privat.' },
  { icon: 'fa-database', title: 'TrueNAS & Storage', desc: 'Überwache Speicherpools, Dienste und Container. Immer den Überblick über dein NAS.' },
  { icon: 'fa-microchip', title: 'Lokale KI', desc: 'Alle Berechnungen laufen auf deinem Rechner. Keine Cloud-Abhängigkeit, maximale Privatsphäre.' }
];

const STEPS = [
  { icon: 'fa-server', title: '1. Backend starten', desc: 'MYND läuft auf deinem Mac mini oder Server – einfach per Docker oder Python starten.' },
  { icon: 'fa-wifi', title: '2. Verbinden', desc: 'Greife per Browser, Tailscale oder Cloudflare Tunnel von überall auf dein MYND zu.' },
  { icon: 'fa-plug', title: '3. Dienste anbinden', desc: 'Verbinde Immich, Nextcloud, Home Assistant und TrueNAS – ganz einfach konfiguriert.' },
  { icon: 'fa-comment', title: '4. Loslegen', desc: 'Stell Fragen, erstelle Zusammenfassungen, steuere dein Smart Home – alles per Chat.' }
];

export default function LandingPage() {
  const [lang, setLang] = useState('de');

  useEffect(() => {
    try {
      const stored = localStorage.getItem('mynd_language');
      if (stored === 'en' || stored === 'de') setLang(stored);
    } catch {}
  }, []);

  const _ = (de, en) => lang === 'de' ? de : en;

  const scrollTo = (id) => {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div className="lp">
      <nav className="lp-nav">
        <div className="lp-nav-inner">
          <div className="lp-logo">
            <span className="lp-logo-icon">◆</span>
            <span className="lp-logo-text">MYND</span>
          </div>
          <div className="lp-nav-links">
            <button onClick={() => scrollTo('features')}>{_('Funktionen', 'Features')}</button>
            <button onClick={() => scrollTo('how')}>{_('Ablauf', 'How it works')}</button>
            <button onClick={() => scrollTo('tech')}>{_('Technik', 'Tech')}</button>
          </div>
          <div className="lp-nav-right">
            <button className="lp-lang" onClick={() => setLang(lang === 'de' ? 'en' : 'de')}>
              {lang === 'de' ? 'EN' : 'DE'}
            </button>
            <a href="/login" className="lp-btn lp-btn-primary">
              {_('Anmelden', 'Login')}
            </a>
          </div>
        </div>
      </nav>

      <section className="lp-hero">
        <div className="lp-hero-bg" />
        <div className="lp-hero-content">
          <div className="lp-hero-badge">
            <i className="fas fa-shield-alt" />
            {_('Lokal & Privat', 'Local & Private')}
          </div>
          <h1 className="lp-hero-title">
            {_('Dein', 'Your')}{' '}
            <span className="lp-hero-gradient">{_('Second Brain', 'Second Brain')}</span>
          </h1>
          <p className="lp-hero-sub">
            {_(
              'MYND verbindet KI-Chat, Smart Home Steuerung und Wissensmanagement in einer lokalen Plattform – datenschutzkonform und ohne Cloud-Zwang.',
              'MYND combines AI chat, smart home control and knowledge management in one local platform – privacy-first and cloud-free.'
            )}
          </p>
          <div className="lp-hero-actions">
            <a href="/login" className="lp-btn lp-btn-primary lp-btn-lg">
              {_('Jetzt starten', 'Get Started')}
              <i className="fas fa-arrow-right" />
            </a>
            <button className="lp-btn lp-btn-secondary lp-btn-lg" onClick={() => scrollTo('features')}>
              {_('Mehr erfahren', 'Learn more')}
            </button>
          </div>
        </div>
      </section>

      <section className="lp-section" id="features">
        <div className="lp-section-header">
          <h2>{_('Was MYND kann', 'What MYND can do')}</h2>
          <p>{_('Alles aus einer Hand – lokal, sicher, intelligent.', 'All in one – local, secure, intelligent.')}</p>
        </div>
        <div className="lp-features">
          {FEATURES.map((f, i) => (
            <div key={i} className="lp-feature-card" style={{ animationDelay: `${i * 0.08}s` }}>
              <div className="lp-feature-icon">
                <i className={`fas ${f.icon}`} />
              </div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="lp-section lp-section-dark" id="how">
        <div className="lp-section-header">
          <h2>{_('So funktioniert es', 'How it works')}</h2>
          <p>{_('In wenigen Minuten einsatzbereit.', 'Ready in minutes.')}</p>
        </div>
        <div className="lp-steps">
          {STEPS.map((s, i) => (
            <div key={i} className="lp-step">
              <div className="lp-step-num">{i + 1}</div>
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
          <h2>{_('Technische Highlights', 'Technical Highlights')}</h2>
          <p>{_('Modernste Technologie für maximale Kontrolle.', 'Cutting-edge tech for maximum control.')}</p>
        </div>
        <div className="lp-tech-grid">
          <div className="lp-tech-item">
            <div className="lp-tech-value">76+</div>
            <div className="lp-tech-label">{_('Tools & Plugins', 'Tools & Plugins')}</div>
          </div>
          <div className="lp-tech-item">
            <div className="lp-tech-value">8</div>
            <div className="lp-tech-label">{_('Integrierte Dienste', 'Integrated Services')}</div>
          </div>
          <div className="lp-tech-item">
            <div className="lp-tech-value">306k</div>
            <div className="lp-tech-label">{_('Fotos indexiert', 'Photos Indexed')}</div>
          </div>
          <div className="lp-tech-item">
            <div className="lp-tech-value">24/7</div>
            <div className="lp-tech-label">{_('Verfügbarkeit', 'Availability')}</div>
          </div>
        </div>
      </section>

      <section className="lp-cta">
        <h2>{_('Bereit für dein Second Brain?', 'Ready for your Second Brain?')}</h2>
        <p>{_('Starte noch heute und entdecke, wie MYND deinen digitalen Alltag vereinfacht.', 'Start today and discover how MYND simplifies your digital life.')}</p>
        <a href="/login" className="lp-btn lp-btn-primary lp-btn-lg">
          {_('Jetzt starten', 'Get Started')}
          <i className="fas fa-arrow-right" />
        </a>
      </section>

      <footer className="lp-footer">
        <div className="lp-footer-inner">
          <div className="lp-logo">
            <span className="lp-logo-icon">◆</span>
            <span className="lp-logo-text">MYND</span>
          </div>
          <p className="lp-footer-tagline">{_('Dein lokaler KI-Assistent', 'Your local AI assistant')}</p>
          <p className="lp-footer-copy">
            {_('Läuft auf deinem Mac mini hinter Tailscale. Keine Cloud, keine Kompromisse.', 'Runs on your Mac mini behind Tailscale. No cloud, no compromises.')}
          </p>
        </div>
      </footer>
    </div>
  );
}
