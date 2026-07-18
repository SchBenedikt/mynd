'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import './LandingPage.css';

const LANGUAGES = ['de', 'en'];

const FEATURES = [
  {
    number: '01', icon: 'fa-comment-dots',
    title: { de: 'Privater KI-Chat', en: 'Private AI chat' },
    desc: {
      de: 'Sprich mit einer KI, die deine freigegebenen Quellen versteht – ohne den Überblick über sensible Daten zu verlieren.',
      en: 'Talk to an AI that understands the sources you approve—without losing sight of where sensitive data goes.'
    },
    detail: { de: 'Kontext statt Copy & Paste', en: 'Context, not copy & paste' }
  },
  {
    number: '02', icon: 'fa-diagram-project',
    title: { de: 'Wissen über Quellen hinweg', en: 'Knowledge across sources' },
    desc: {
      de: 'Dokumente, Fotos, E-Mails und Notizen werden zu einem durchsuchbaren persönlichen Kontext verbunden.',
      en: 'Documents, photos, email and notes become one searchable layer of personal context.'
    },
    detail: { de: 'Antworten mit Herkunft', en: 'Answers with provenance' }
  },
  {
    number: '03', icon: 'fa-list-check',
    title: { de: 'Aufgaben, die weiterdenken', en: 'Tasks that think ahead' },
    desc: {
      de: 'Finde offene Punkte, fasse Wochen zusammen und verbinde Routinen mit deinen vorhandenen Diensten.',
      en: 'Surface open loops, recap your week and connect routines to the services you already use.'
    },
    detail: { de: 'Automationen unter Kontrolle', en: 'Automations under control' }
  },
  {
    number: '04', icon: 'fa-shield-halved',
    title: { de: 'Erlaubnis vor Aktion', en: 'Permission before action' },
    desc: {
      de: 'Du entscheidest, welches Plugin lesen darf und wann eine schreibende Aktion bestätigt werden muss.',
      en: 'You decide which plugin may read data and when a write action needs explicit confirmation.'
    },
    detail: { de: 'Nachvollziehbar & widerrufbar', en: 'Visible and revocable' }
  }
];

const INTEGRATIONS = [
  { icon: 'fa-cloud', type: 'fas', name: 'Nextcloud', desc: { de: 'Dateien, Kalender & Aufgaben', en: 'Files, calendar & tasks' } },
  { icon: 'fa-images', type: 'fas', name: 'Immich', desc: { de: 'Deine private Fotobibliothek', en: 'Your private photo library' } },
  { icon: 'fa-house-signal', type: 'fas', name: 'Home Assistant', desc: { de: 'Zuhause verstehen & steuern', en: 'Understand & control your home' } },
  { icon: 'fa-envelope', type: 'fas', name: 'E-Mail', desc: { de: 'Postfach als Kontext', en: 'Inbox as context' } },
  { icon: 'fa-spotify', type: 'fab', name: 'Spotify', desc: { de: 'Musik mit einem Satz', en: 'Music in one sentence' } },
  { icon: 'fa-discord', type: 'fab', name: 'Discord', desc: { de: 'Communities im Blick', en: 'Keep up with communities' } },
  { icon: 'fa-database', type: 'fas', name: 'TrueNAS', desc: { de: 'Speicher & Dienste', en: 'Storage & services' } },
  { icon: 'fa-globe', type: 'fas', name: 'Browser', desc: { de: 'Das Web als Werkzeug', en: 'The web as a tool' } }
];

const ORBIT_NODES = [
  { key: 'chat', icon: 'fa-comment-dots', label: { de: 'Chat', en: 'Chat' } },
  { key: 'knowledge', icon: 'fa-book-open', label: { de: 'Wissen', en: 'Knowledge' } },
  { key: 'tasks', icon: 'fa-list-check', label: { de: 'Aufgaben', en: 'Tasks' } },
  { key: 'home', icon: 'fa-house', label: { de: 'Zuhause', en: 'Home' } },
  { key: 'photos', icon: 'fa-images', label: { de: 'Fotos', en: 'Photos' } },
  { key: 'spotify', icon: 'fa-spotify', type: 'fab', label: { de: 'Spotify', en: 'Spotify' } },
  { key: 'discord', icon: 'fa-discord', type: 'fab', label: { de: 'Discord', en: 'Discord' } }
];

export default function LandingPage() {
  const [lang, setLang] = useState('de');

  useEffect(() => {
    try {
      const stored = localStorage.getItem('mynd_language');
      if (LANGUAGES.includes(stored)) setLang(stored);
    } catch {}
  }, []);

  const text = (copy) => copy[lang];
  const tr = (de, en) => lang === 'de' ? de : en;

  const toggleLanguage = () => {
    const next = lang === 'de' ? 'en' : 'de';
    setLang(next);
    try { localStorage.setItem('mynd_language', next); } catch {}
  };

  return (
    <main className="lp" lang={lang} data-auth-view="public">
      <a className="lp-skip" href="#main-content">{tr('Zum Inhalt', 'Skip to content')}</a>

      <header className="lp-nav">
        <nav className="lp-nav-inner" aria-label={tr('Hauptnavigation', 'Main navigation')}>
          <a className="lp-logo" href="#top" aria-label="MYND Home">
            <span className="lp-logo-mark" aria-hidden="true" />
            <span>MYND</span>
          </a>
          <div className="lp-nav-links">
            <a href="#features">{tr('Funktionen', 'Features')}</a>
            <a href="#integrations">{tr('Integrationen', 'Integrations')}</a>
            <a href="#privacy">{tr('Privatsphäre', 'Privacy')}</a>
          </div>
          <div className="lp-nav-actions">
            <button className="lp-language" type="button" onClick={toggleLanguage} aria-label={tr('Switch to English', 'Auf Deutsch wechseln')}>
              <span className={lang === 'de' ? 'active' : ''}>DE</span><i aria-hidden="true" /><span className={lang === 'en' ? 'active' : ''}>EN</span>
            </button>
            <Link href="/login" className="lp-signin lp-signin-nav" data-testid="landing-login">
              {tr('Anmelden', 'Sign in')} <i className="fas fa-arrow-right" aria-hidden="true" />
            </Link>
          </div>
        </nav>
      </header>

      <section className="lp-hero" id="top">
        <div className="lp-hero-grid" id="main-content">
          <div className="lp-hero-copy">
            <p className="lp-eyebrow"><span /> {tr('Lokale Intelligenz. Persönlicher Kontext.', 'Local intelligence. Personal context.')}</p>
            <h1>{tr('Dein digitales Leben,', 'Your digital life,')} <em>{tr('endlich verbunden.', 'finally connected.')}</em></h1>
            <p className="lp-hero-lede">
              {tr(
                'MYND bringt Chats, Wissen, Aufgaben und dein Zuhause in einen privaten KI-Arbeitsraum – auf deiner Infrastruktur und unter deiner Kontrolle.',
                'MYND brings chats, knowledge, tasks and your home into one private AI workspace—on your infrastructure and under your control.'
              )}
            </p>
            <div className="lp-hero-actions">
              <Link href="/login" className="lp-primary-cta">
                <span>{tr('Bei MYND anmelden', 'Sign in to MYND')}</span>
                <i className="fas fa-arrow-right" aria-hidden="true" />
              </Link>
              <a href="#features" className="lp-text-cta">
                {tr('Entdecken, was MYND verbindet', 'Explore what MYND connects')}
                <i className="fas fa-arrow-down" aria-hidden="true" />
              </a>
            </div>
            <p className="lp-hero-note"><i className="fas fa-lock" aria-hidden="true" /> {tr('Deine Daten bleiben dort, wo du sie haben willst.', 'Your data stays where you want it.')}</p>
          </div>

          <div className="lp-constellation" aria-label={tr('MYND verbindet deine persönlichen Dienste zu einem Kontext.', 'MYND connects your personal services into one context.')}>
            <div className="lp-orbit lp-orbit-one" aria-hidden="true" />
            <div className="lp-orbit lp-orbit-two" aria-hidden="true" />
            <div className="lp-orbit lp-orbit-three" aria-hidden="true" />
            <div className="lp-core">
              <span className="lp-core-mark" aria-hidden="true" />
              <strong>MYND</strong>
              <small>{tr('Dein Kontext', 'Your context')}</small>
            </div>
            {ORBIT_NODES.map((node) => (
              <div className={`lp-node lp-node-${node.key}`} key={node.key}>
                <i className={`${node.type || 'fas'} ${node.icon}`} aria-hidden="true" />
                <span>{text(node.label)}</span>
              </div>
            ))}
            <div className="lp-signal lp-signal-a" aria-hidden="true" />
            <div className="lp-signal lp-signal-b" aria-hidden="true" />
            <div className="lp-signal lp-signal-c" aria-hidden="true" />
          </div>
        </div>
      </section>

      <aside className="lp-proof" aria-label={tr('Produktprinzipien', 'Product principles')}>
        <div className="lp-proof-inner">
          <p><i className="fas fa-server" aria-hidden="true" /><span><strong>{tr('Local-first', 'Local-first')}</strong>{tr('Auf deiner Infrastruktur', 'On your infrastructure')}</span></p>
          <p><i className="fas fa-puzzle-piece" aria-hidden="true" /><span><strong>{tr('Erweiterbar', 'Extensible')}</strong>{tr('Plugins für deine Dienste', 'Plugins for your services')}</span></p>
          <p><i className="fas fa-fingerprint" aria-hidden="true" /><span><strong>{tr('Explizit', 'Explicit')}</strong>{tr('Berechtigungen pro Aktion', 'Permissions per action')}</span></p>
        </div>
      </aside>

      <section className="lp-features" id="features">
        <div className="lp-section-intro">
          <p className="lp-kicker">{tr('Ein Gedächtnis mit Grenzen', 'A memory with boundaries')}</p>
          <h2>{tr('Mehr Zusammenhang. Weniger Suchen.', 'More context. Less searching.')}</h2>
          <p>{tr('MYND macht aus verteilten Informationen einen nutzbaren Kontext – und lässt dich bestimmen, wie weit dieser reicht.', 'MYND turns scattered information into useful context—and lets you decide exactly how far that context reaches.')}</p>
        </div>

        <div className="lp-feature-list">
          {FEATURES.map((feature, index) => (
            <article className={`lp-feature lp-feature-${index + 1}`} key={feature.number}>
              <div className="lp-feature-index">{feature.number}</div>
              <div className="lp-feature-icon"><i className={`fas ${feature.icon}`} aria-hidden="true" /></div>
              <div className="lp-feature-copy">
                <h3>{text(feature.title)}</h3>
                <p>{text(feature.desc)}</p>
              </div>
              <div className="lp-feature-detail"><span />{text(feature.detail)}</div>
            </article>
          ))}
        </div>
      </section>

      <section className="lp-integrations" id="integrations">
        <div className="lp-integrations-head">
          <div>
            <p className="lp-kicker">{tr('Deine Dienste. Eine Sprache.', 'Your services. One language.')}</p>
            <h2>{tr('Verbindungen, die du auswählst.', 'Connections you choose.')}</h2>
          </div>
          <p>{tr('MYND wächst mit deinem Setup. Aktiviere nur die Werkzeuge, die du wirklich brauchst.', 'MYND grows with your setup. Enable only the tools you actually need.')}</p>
        </div>
        <div className="lp-integration-rail">
          {INTEGRATIONS.map((integration) => (
            <article className="lp-integration" key={integration.name}>
              <i className={`${integration.type} ${integration.icon}`} aria-hidden="true" />
              <div><h3>{integration.name}</h3><p>{text(integration.desc)}</p></div>
            </article>
          ))}
        </div>
      </section>

      <section className="lp-privacy" id="privacy">
        <div className="lp-privacy-visual" aria-hidden="true">
          <div className="lp-vault-ring lp-vault-ring-outer" />
          <div className="lp-vault-ring lp-vault-ring-inner" />
          <div className="lp-vault-core"><i className="fas fa-fingerprint" /></div>
          <span className="lp-vault-label lp-vault-label-one">LOCAL</span>
          <span className="lp-vault-label lp-vault-label-two">READ</span>
          <span className="lp-vault-label lp-vault-label-three">CONFIRM</span>
        </div>
        <div className="lp-privacy-copy">
          <p className="lp-kicker">{tr('Privat by design', 'Private by design')}</p>
          <h2>{tr('Dein Kontext gehört nicht in eine Blackbox.', 'Your context does not belong in a black box.')}</h2>
          <p>{tr('MYND ist für den Betrieb auf deiner eigenen Infrastruktur gedacht. Datenquellen werden bewusst verbunden, Rechte bleiben sichtbar und sensible Aktionen verlangen deine Freigabe.', 'MYND is designed to run on your own infrastructure. Sources are connected deliberately, permissions stay visible and sensitive actions require your approval.')}</p>
          <ul>
            <li><i className="fas fa-check" aria-hidden="true" />{tr('Lokale und selbst gehostete Modelle einbinden', 'Connect local and self-hosted models')}</li>
            <li><i className="fas fa-check" aria-hidden="true" />{tr('Plugins einzeln aktivieren oder widerrufen', 'Enable or revoke plugins individually')}</li>
            <li><i className="fas fa-check" aria-hidden="true" />{tr('Schreibende Aktionen bewusst bestätigen', 'Explicitly confirm write actions')}</li>
          </ul>
        </div>
      </section>

      <section className="lp-final">
        <p className="lp-kicker">{tr('Bereit, den Kontext zusammenzubringen?', 'Ready to bring the context together?')}</p>
        <h2>{tr('Ein Arbeitsraum. Deine Regeln.', 'One workspace. Your rules.')}</h2>
        <Link href="/login" className="lp-primary-cta lp-final-cta">
          <span>{tr('Anmeldung öffnen', 'Open sign in')}</span><i className="fas fa-arrow-right" aria-hidden="true" />
        </Link>
      </section>

      <footer className="lp-footer">
        <a className="lp-logo" href="#top"><span className="lp-logo-mark" aria-hidden="true" /><span>MYND</span></a>
        <p>© {new Date().getFullYear()} MYND · {tr('Lokal. Privat. Verbunden.', 'Local. Private. Connected.')}</p>
        <a href="#privacy">{tr('Privatsphäre', 'Privacy')}</a>
      </footer>
    </main>
  );
}
