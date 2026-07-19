'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import './developers.css';

const LANG = ['de', 'en'];

const SECTIONS = [
  { id: 'overview', icon: 'fa-cube',
    title_de: 'Plugin-Architektur', title_en: 'Plugin Architecture',
    desc_de: 'MYND lädt zur Laufzeit Plugins aus dem Verzeichnis <code>data/plugins/</code>. Jedes Plugin ist eine Python-Datei, die Tools als OpenAI-kompatible Function-Calling-Schemata bereitstellt. Die Plugin-Engine (<code>core/plugin_base.py</code>) erkennt automatisch alle Unterklassen von <code>Plugin</code>. Es gibt zwei Schreibweisen: die moderne Klasse und das Legacy-Modul.', desc_en: 'MYND loads plugins at runtime from <code>data/plugins/</code>. Each plugin is a Python file providing tools as OpenAI-compatible function-calling schemas. The plugin engine (<code>core/plugin_base.py</code>) auto-discovers all <code>Plugin</code> subclasses. Two patterns are supported: the modern class-based API and the legacy module approach.' },
  { id: 'modern', icon: 'fa-layer-group',
    title_de: 'Moderne Klasse (empfohlen)', title_en: 'Modern Class (recommended)',
    desc_de: 'Leite von <code>Plugin</code> ab, setze Klassenattribute und implementiere <code>tool_map</code>.',
    desc_en: 'Subclass <code>Plugin</code>, set class attributes, and implement <code>tool_map</code>.' },
  { id: 'legacy', icon: 'fa-code',
    title_de: 'Legacy-Modul', title_en: 'Legacy Module',
    desc_de: 'Definiere die Konstanten <code>PLUGIN_NAME</code>, <code>TOOLS</code> und <code>TOOL_MAP</code> auf Modulebene.',
    desc_en: 'Define <code>PLUGIN_NAME</code>, <code>TOOLS</code>, and <code>TOOL_MAP</code> at module level.' },
  { id: 'schema', icon: 'fa-table-cells',
    title_de: 'Tool-Schema', title_en: 'Tool Schema',
    desc_de: 'Jedes Tool wird als OpenAI-Function-Calling-Dict definiert: <code>name</code>, <code>description</code>, <code>parameters</code> (JSON Schema) und eine Handler-Funktion, die ein Dict zurückgibt.',
    desc_en: 'Each tool is defined as an OpenAI function-calling dict: <code>name</code>, <code>description</code>, <code>parameters</code> (JSON Schema), and a handler that returns a dict.' },
  { id: 'config', icon: 'fa-sliders',
    title_de: 'Konfiguration & Vault', title_en: 'Configuration & Vault',
    desc_de: 'Credentials werden sicher im Vault (<code>core/vault.py</code>) gespeichert, Konfiguration in <code>plugin_config.json</code>. Definiere <code>config_schema</code> für die UI.',
    desc_en: 'Credentials are stored securely in the vault (<code>core/vault.py</code>), config in <code>plugin_config.json</code>. Define <code>config_schema</code> for the UI.' },
  { id: 'testing', icon: 'fa-flask',
    title_de: 'Testen & Debuggen', title_en: 'Testing & Debugging',
    desc_de: 'Starte den Server, aktiviere das Plugin in den Einstellungen und führe im Chat einen Befehl aus, der das Tool triggert. Logs erscheinen im Server-Terminal.',
    desc_en: 'Start the server, enable the plugin in settings, and run a chat command that triggers the tool. Logs appear in the server terminal.' },
];

const MODERN_EXAMPLE = `from core.plugin_base import Plugin, validate_plugin_tools

PLUGIN_NAME = "example"
PLUGIN_DESC = "Example plugin"

class ExamplePlugin(Plugin):
    name = PLUGIN_NAME
    description = PLUGIN_DESC
    version = "1.0.0"

    def __init__(self, config=None):
        super().__init__(config)
        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": "example_greet",
                    "description": "Greet a user",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name to greet"
                            }
                        },
                        "required": ["name"]
                    }
                }
            }
        ]
        self.tool_map = {
            "example_greet": self.example_greet
        }

    def example_greet(self, name: str) -> dict:
        return {
            "message": f"Hello, {name}!",
            "length": len(name)
        }`;

const LEGACY_EXAMPLE = `PLUGIN_NAME = "example"
PLUGIN_DESC = "Example plugin (legacy)"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "example_greet",
            "description": "Greet a user",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name to greet"
                    }
                },
                "required": ["name"]
            }
        }
    }
]

def example_greet(name: str) -> dict:
    return {
        "message": f"Hello, {name}!",
        "length": len(name)
    }

TOOL_MAP = {
    "example_greet": example_greet
}`;

export default function DevelopersPage() {
  const [lang, setLang] = useState('de');
  const [activeSection, setActiveSection] = useState('overview');

  useEffect(() => {
    try {
      const stored = localStorage.getItem('mynd_language');
      if (LANG.includes(stored)) setLang(stored);
    } catch {}
  }, []);

  useEffect(() => {
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          setActiveSection(entry.target.id);
        }
      }
    }, { rootMargin: '-100px 0px -60%' });
    const els = document.querySelectorAll('.lp-dev-section');
    els.forEach(el => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  const t = (de, en) => lang === 'de' ? de : en;

  const toggleLanguage = () => {
    const next = lang === 'de' ? 'en' : 'de';
    setLang(next);
    try { localStorage.setItem('mynd_language', next); } catch {}
  };

  return (
    <main className="lp-dev" lang={lang}>
      <header className="lp-dev-nav">
        <nav className="lp-dev-nav-inner">
          <Link href="/" className="lp-dev-logo" aria-label="MYND Home">
            <span className="lp-dev-logo-mark" aria-hidden="true"><i /></span>
            <span>MYND</span>
          </Link>
          <div className="lp-dev-nav-links">
            {SECTIONS.map(s => (
              <a key={s.id} href={`#${s.id}`}
                className={activeSection === s.id ? 'is-active' : ''}>
                {t(s.title_de, s.title_en)}
              </a>
            ))}
          </div>
          <div className="lp-dev-nav-actions">
            <button className="lp-dev-lang" type="button" onClick={toggleLanguage}
              aria-label={t('Switch to English', 'Auf Deutsch wechseln')}>
              <span className={lang === 'de' ? 'active' : ''}>DE</span>
              <i aria-hidden="true" />
              <span className={lang === 'en' ? 'active' : ''}>EN</span>
            </button>
          </div>
        </nav>
      </header>

      <section className="lp-dev-hero">
        <div className="lp-dev-shell">
          <p className="lp-dev-eyebrow">
            <span className="lp-dev-live-dot" />
            {t('Entwicklerdokumentation', 'Developer Documentation')}
          </p>
          <h1>{t('Eigene Integrationen bauen.', 'Build your own integrations.')}</h1>
          <p className="lp-dev-lede">
            {t('MYNDs Plugin-System erlaubt dir, beliebige Dienste anzubinden. Schreibe eine Python-Datei, definiere Tools — fertig.', 'MYND\'s plugin system lets you connect any service. Write a Python file, define tools — done.')}
          </p>
          <div className="lp-dev-hero-actions">
            <a href="#overview" className="lp-dev-primary-cta">
              <span>{t('Loslegen', 'Get started')}</span>
              <i className="fas fa-arrow-right" aria-hidden="true" />
            </a>
            <Link href="/" className="lp-dev-secondary-cta">
              <i className="fas fa-arrow-left" aria-hidden="true" />
              {t('Zurück zur Startseite', 'Back to home')}
            </Link>
          </div>
        </div>
      </section>

      <aside className="lp-dev-ticker">
        <div className="lp-dev-shell lp-dev-ticker-track">
          <p><span>01</span><strong>{t('Python 3.11+', 'Python 3.11+')}</strong><small>{t('Keine externen Build-Tools nötig', 'No external build tools required')}</small></p>
          <p><span>02</span><strong>{t('OpenAI Schema', 'OpenAI Schema')}</strong><small>{t('Standard-kompatibles Function Calling', 'Standard-compatible function calling')}</small></p>
          <p><span>03</span><strong>{t('Hot Reload', 'Hot Reload')}</strong><small>{t('Plugin aktivieren/deaktivieren ohne Neustart', 'Enable/disable without restart')}</small></p>
        </div>
      </aside>

      <div className="lp-dev-content">
        <nav className="lp-dev-sidebar" aria-label={t('Sektionen', 'Sections')}>
          <ol>
            {SECTIONS.map(s => (
              <li key={s.id}>
                <a href={`#${s.id}`} className={activeSection === s.id ? 'is-active' : ''}>
                  <span className="lp-dev-sidebar-num">{String(SECTIONS.indexOf(s) + 1).padStart(2, '0')}</span>
                  <i className={`fas ${s.icon}`} aria-hidden="true" />
                  <span>{t(s.title_de, s.title_en)}</span>
                </a>
              </li>
            ))}
          </ol>
        </nav>

        <div className="lp-dev-articles">
          <article className="lp-dev-section" id="overview">
            <h2>{t(SECTIONS[0].title_de, SECTIONS[0].title_en)}</h2>
            <p dangerouslySetInnerHTML={{ __html: t(SECTIONS[0].desc_de, SECTIONS[0].desc_en) }} />
            <h3>{t('Verfügbare Plugins', 'Available Plugins')}</h3>
            <div className="lp-dev-table">
              <div className="lp-dev-tr lp-dev-th">
                <span>{t('Plugin', 'Plugin')}</span>
                <span>{t('Beschreibung', 'Description')}</span>
                <span>{t('Tools', 'Tools')}</span>
              </div>
              {[
                { name: 'homeassistant', desc: t('Smarthome-Steuerung: Geräte, Energie, Automatisierungen', 'Smart home: devices, energy, automations'), tools: '~25' },
                { name: 'nextcloud', desc: t('Dateien, Kalender, Aufgaben, Kontakte', 'Files, calendar, tasks, contacts'), tools: '~24' },
                { name: 'immich', desc: t('KI-Fotoverwaltung: Gesichter, Alben, Metadaten', 'AI photo mgmt: faces, albums, metadata'), tools: '~21' },
                { name: 'browser', desc: t('Cloud-Browser mit Stealth-Modus', 'Cloud browser with stealth mode'), tools: '~18' },
                { name: 'email', desc: t('IMAP/SMTP: Lesen, Suchen, Senden', 'IMAP/SMTP: read, search, send'), tools: '~10' },
                { name: 'spotify', desc: t('Musik-Suche, Playback, Playlists', 'Music search, playback, playlists'), tools: '~12' },
                { name: 'discord', desc: t('Nachrichten, Kanäle, Mitglieder', 'Messages, channels, members'), tools: '~12' },
                { name: 'truenas', desc: t('NAS-Status, Dienste, Alerts', 'NAS status, services, alerts'), tools: '~8' },
                { name: 'system', desc: t('System-Info, Logs, Prozesse', 'System info, logs, processes'), tools: '~15' },
              ].map(p => (
                <div key={p.name} className="lp-dev-tr">
                  <span className="lp-dev-tool-name">{p.name}</span>
                  <span>{p.desc}</span>
                  <span className="lp-dev-mono">{p.tools}</span>
                </div>
              ))}
            </div>
          </article>

          <article className="lp-dev-section" id="modern">
            <h2>{t(SECTIONS[1].title_de, SECTIONS[1].title_en)}</h2>
            <p>{t(
              'Erstelle eine neue Datei <code>data/plugins/mein_plugin.py</code>. Leite von <code>Plugin</code> ab, setze Klassenattribute und fülle <code>self.tools</code> und <code>self.tool_map</code> im Konstruktor.',
              'Create a new file <code>data/plugins/my_plugin.py</code>. Subclass <code>Plugin</code>, set class attributes, and populate <code>self.tools</code> and <code>self.tool_map</code> in the constructor.'
            )}</p>
            <pre className="lp-dev-code"><code>{MODERN_EXAMPLE}</code></pre>
            <p>{t(
              'Das Plugin wird automatisch erkannt, sobald der Server startet oder Plugins neu geladen werden. Aktiviere es in den Einstellungen unter "Integrationen → Plugin-Manager".',
              'The plugin is auto-discovered when the server starts or plugins are reloaded. Enable it in Settings under "Integrations → Plugin Manager".'
            )}</p>
          </article>

          <article className="lp-dev-section" id="legacy">
            <h2>{t(SECTIONS[2].title_de, SECTIONS[2].title_en)}</h2>
            <p>{t(
              'Der Legacy-Stil definiert <code>PLUGIN_NAME</code>, <code>PLUGIN_DESC</code>, <code>TOOLS</code> und <code>TOOL_MAP</code> direkt auf Modulebene. Ideal für schnelle Experimente.',
              'The legacy style defines <code>PLUGIN_NAME</code>, <code>PLUGIN_DESC</code>, <code>TOOLS</code> and <code>TOOL_MAP</code> directly at module level. Great for quick experiments.'
            )}</p>
            <pre className="lp-dev-code"><code>{LEGACY_EXAMPLE}</code></pre>
          </article>

          <article className="lp-dev-section" id="schema">
            <h2>{t(SECTIONS[3].title_de, SECTIONS[3].title_en)}</h2>
            <p>{t(
              'Jedes Tool-Dict folgt dem OpenAI Function Calling Standard. Pflichtfelder sind <code>name</code> (eindeutig, 1-64 Zeichen), <code>description</code> und <code>parameters</code> mit JSON Schema Properties. Die Handler-Funktion bekommt die entpackten Parameter und muss ein serialisierbares Dict (oder String/Liste) zurückgeben.',
              'Each tool dict follows the OpenAI Function Calling standard. Required fields are <code>name</code> (unique, 1-64 chars), <code>description</code>, and <code>parameters</code> with JSON Schema properties. The handler receives unpacked parameters and must return a serializable dict (or string/list).'
            )}</p>
            <h3>{t('Wichtige Regeln', 'Important Rules')}</h3>
            <ul className="lp-dev-rules">
              <li>{t('Tool-Namen müssen eindeutig sein (über alle Plugins hinweg).', 'Tool names must be unique across all plugins.')}</li>
              <li>{t('Die Handler-Funktion muss im <code>tool_map</code> registriert sein.', 'The handler function must be registered in <code>tool_map</code>.')}</li>
              <li>{t('Rückgabewerte müssen JSON-serialisierbar sein (dict, str, list, int, float, bool, None).', 'Return values must be JSON-serializable (dict, str, list, int, float, bool, None).')}</li>
              <li>{t('Credentials nicht hartcodieren — Vault oder <code>plugin_config.json</code> nutzen.', 'Do not hardcode credentials — use Vault or <code>plugin_config.json</code>.')}</li>
              <li>{t('Lange Operationen (>10s) sollten in Hintergrund-Threads laufen.', 'Long operations (>10s) should run in background threads.')}</li>
            </ul>
          </article>

          <article className="lp-dev-section" id="config">
            <h2>{t(SECTIONS[4].title_de, SECTIONS[4].title_en)}</h2>
            <p>{t(
              'Definiere <code>config_schema</code> als Dict von Felddefinitionen. Die UI zeigt dann in den Integrationseinstellungen die passenden Eingabefelder an. Für sensible Daten (Tokens, Passwörter) nutze den Vault (<code>core/vault.py</code>) mit Typ <code>"password"</code>.',
              'Define <code>config_schema</code> as a dict of field definitions. The UI will then show the appropriate input fields in the integration settings. For sensitive data (tokens, passwords), use the Vault (<code>core/vault.py</code>) with <code>"password"</code> type.'
            )}</p>
            <pre className="lp-dev-code"><code>{`PLUGIN_CONFIG_SCHEMA = {
    "url": {
        "label": "Server URL",
        "type": "text",
        "placeholder": "https://example.com"
    },
    "token": {
        "label": "API Token",
        "type": "password"
    }
}`}</code></pre>
          </article>

          <article className="lp-dev-section" id="testing">
            <h2>{t(SECTIONS[5].title_de, SECTIONS[5].title_en)}</h2>
            <p>{t(
              'Starte den Backend-Server, aktiviere das Plugin im Plugin-Manager und öffne den Chat. Stelle eine Frage, die dein Tool triggert — z. B. "Sag Hallo zu Max" für das Beispiel oben. Die Ausführung erscheint als Tool-Call in der Antwort. Fehler und Logs siehst du im Server-Terminal.',
              'Start the backend server, enable the plugin in the Plugin Manager, and open the chat. Ask a question that triggers your tool — e.g. "Say hello to Max" for the example above. The execution appears as a tool call in the response. Errors and logs appear in the server terminal.'
            )}</p>
            <div className="lp-dev-test-note">
              <i className="fas fa-lightbulb" aria-hidden="true" />
              <span>{t(
                'Tipp: Verwende <code style="background:transparent;padding:0;border:0;color:var(--lp-accent)">print()</code> oder <code style="background:transparent;padding:0;border:0;color:var(--lp-accent)">logging</code> in deinem Plugin. Die Ausgabe erscheint im Server-Log.',
                'Tip: Use <code style="background:transparent;padding:0;border:0;color:var(--lp-accent)">print()</code> or <code style="background:transparent;padding:0;border:0;color:var(--lp-accent)">logging</code> in your plugin. Output appears in the server log.'
              )}</span>
            </div>
          </article>

          <footer className="lp-dev-article-footer">
            <p>{t('Noch Fragen? Schau in den bestehenden Plugin-Code unter <code>data/plugins/</code> — er ist die beste Dokumentation.', 'Questions? Check the existing plugin code in <code>data/plugins/</code> — it\'s the best documentation.')}</p>
            <Link href="/" className="lp-dev-primary-cta">
              <i className="fas fa-arrow-left" aria-hidden="true" />
              {t('Zurück zur Startseite', 'Back to home')}
            </Link>
          </footer>
        </div>
      </div>

      <footer className="lp-dev-footer">
        <div className="lp-dev-shell lp-dev-footer-inner">
          <Link href="/" className="lp-dev-logo"><span className="lp-dev-logo-mark" aria-hidden="true"><i /></span><span>MYND</span></Link>
          <p>© {new Date().getFullYear()} MYND · {t('Plugin-Dokumentation', 'Plugin documentation')}</p>
        </div>
      </footer>
    </main>
  );
}
