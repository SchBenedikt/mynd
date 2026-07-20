'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import './guide.css';

const SECTIONS = [
  { id: 'getting-started', icon: 'fa-rocket',
    title_de: 'Erste Schritte', title_en: 'Getting Started',
    desc_de: 'MYND in wenigen Minuten auf deiner eigenen Infrastruktur einrichten.', desc_en: 'Get MYND running on your own infrastructure in minutes.' },
  { id: 'architecture', icon: 'fa-sitemap',
    title_de: 'Architektur', title_en: 'Architecture',
    desc_de: 'Wie MYND aufgebaut ist: Backend, Frontend, KI-Agent und Plugin-System.', desc_en: 'How MYND is built: backend, frontend, AI agent, and plugin system.' },
  { id: 'ai-models', icon: 'fa-brain',
    title_de: 'KI-Modelle', title_en: 'AI Models',
    desc_de: 'Ollama oder OpenAI-kompatibel — welches Modell für deine Hardware und Anforderungen.', desc_en: 'Ollama or OpenAI-compatible — which model for your hardware and needs.' },
  { id: 'security', icon: 'fa-shield-halved',
    title_de: 'Sicherheit & Modi', title_en: 'Security & Modes',
    desc_de: 'Sicherheitsmodi, Berechtigungen und Datenschutz.', desc_en: 'Security modes, permissions and privacy.' },
  { id: 'nextcloud', icon: 'fa-cloud',
    title_de: 'Nextcloud', title_en: 'Nextcloud',
    desc_de: 'Dateien durchsuchen, Kalender und Aufgaben verwalten.', desc_en: 'Browse files, manage calendars and tasks.' },
  { id: 'immich', icon: 'fa-images',
    title_de: 'Immich', title_en: 'Immich',
    desc_de: 'KI-gestützte Fotosuche in natürlicher Sprache.', desc_en: 'AI-powered photo search using natural language.' },
  { id: 'homeassistant', icon: 'fa-house-signal',
    title_de: 'Home Assistant', title_en: 'Home Assistant',
    desc_de: 'Smart Home steuern — Sensoren, Geräte und Automationen.', desc_en: 'Control your smart home — sensors, devices, automations.' },
  { id: 'email', icon: 'fa-envelope',
    title_de: 'E-Mail', title_en: 'Email',
    desc_de: 'Postfach verbinden, E-Mails suchen und senden.', desc_en: 'Connect your mailbox, search and send emails.' },
  { id: 'spotify', icon: 'fa-spotify',
    title_de: 'Spotify', title_en: 'Spotify',
    desc_de: 'Wiedergabe steuern, Playlists verwalten.', desc_en: 'Control playback, manage playlists.' },
  { id: 'discord', icon: 'fa-discord',
    title_de: 'Discord', title_en: 'Discord',
    desc_de: 'Nachrichten lesen, Kanäle durchsuchen.', desc_en: 'Read messages, search channels.' },
  { id: 'truenas', icon: 'fa-database',
    title_de: 'TrueNAS', title_en: 'TrueNAS',
    desc_de: 'Speicher, Festplatten, SMART-Werte überwachen.', desc_en: 'Monitor storage, disks, SMART values.' },
  { id: 'browser', icon: 'fa-globe',
    title_de: 'Browser', title_en: 'Browser',
    desc_de: 'Web-Recherche, Screenshots, Formulare.', desc_en: 'Web research, screenshots, forms.' },
];

export default function GuidePage() {
  const [lang, setLang] = useState('en');
  const [activeId, setActiveId] = useState('getting-started');

  useEffect(() => {
    const mode = (() => { try { return localStorage.getItem('darkMode') || 'light'; } catch { return 'light'; } })();
    document.documentElement.setAttribute('data-mode', mode);
    const observer = new IntersectionObserver(
      entries => { for (const e of entries) { if (e.isIntersecting) { setActiveId(e.target.id); break; } } },
      { rootMargin: '-100px 0px -66% 0px' }
    );
    for (const s of SECTIONS) {
      const el = document.getElementById(s.id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, []);

  const t = (de, en) => lang === 'de' ? de : en;

  return (
    <div className="lp-guide" lang={lang}>
      <nav className="lp-guide-nav">
        <div className="lp-guide-nav-inner">
          <Link href="/" className="lp-guide-logo">
            <span className="lp-guide-logo-mark"><i /></span>
            <span>MYND</span>
          </Link>
          <div className="lp-guide-nav-links">
            <Link href="/guide" className="is-active">{t('Anleitung', 'Guide')}</Link>
            <Link href="/developers">{t('Entwickler', 'Developers')}</Link>
          </div>
          <div className="lp-guide-nav-actions">
            <button className="lp-guide-lang" type="button" onClick={() => setLang(l => l === 'de' ? 'en' : 'de')}>
              <span className={lang === 'de' ? 'active' : ''}>DE</span>
              <i />
              <span className={lang === 'en' ? 'active' : ''}>EN</span>
            </button>
          </div>
        </div>
      </nav>

      <section className="lp-guide-hero">
        <div className="lp-guide-shell">
          <p className="lp-guide-eyebrow">
            <span className="lp-guide-live-dot" />
            {t('Dokumentation', 'Documentation')}
          </p>
          <h1>{t('MYND einrichten & nutzen', 'Setting up & using MYND')}</h1>
          <p className="lp-guide-lede">{t(
            'Von der Installation über die KI-Konfiguration bis zu allen Integrationen — hier findest du Schritt-für-Schritt-Anleitungen.',
            'From installation to AI configuration to all integrations — find step-by-step guides here.'
          )}</p>
          <div className="lp-guide-hero-actions">
            <Link href="#getting-started" className="lp-guide-primary-cta">
              <span>{t('Loslegen', 'Get started')}</span>
              <i className="fas fa-arrow-down" />
            </Link>
            <Link href="/developers" className="lp-guide-secondary-cta">
              <i className="fas fa-code" />
              <span>{t('Plugin-Entwicklung', 'Plugin Development')}</span>
            </Link>
          </div>
        </div>
      </section>

      <aside className="lp-guide-ticker" aria-label={t('Übersicht', 'Overview')}>
        <div className="lp-guide-shell lp-guide-ticker-track">
          <p><span>01</span><strong>{t('Lokal & privat', 'Local & private')}</strong><small>{t('Alles läuft auf deiner Infrastruktur', 'Everything runs on your infrastructure')}</small></p>
          <p><span>02</span><strong>{t('Alle Dienste vernetzt', 'All services connected')}</strong><small>{t('Nextcloud, Home Assistant, Immich, E-Mail und mehr', 'Nextcloud, Home Assistant, Immich, Email and more')}</small></p>
          <p><span>03</span><strong>{t('Volle Kontrolle', 'Full control')}</strong><small>{t('Sicherheitsmodi, Tool-Bestätigung, Admin-Rechte', 'Security modes, tool confirmation, admin privileges')}</small></p>
        </div>
      </aside>

      <div className="lp-guide-content">
        <aside className="lp-guide-sidebar">
          <nav aria-label={t('Sektionen', 'Sections')}>
            <ol>
              {SECTIONS.map((s, i) => (
                <li key={s.id}>
                  <a href={`#${s.id}`} className={activeId === s.id ? 'is-active' : ''}
                    onClick={(e) => { e.preventDefault(); document.getElementById(s.id)?.scrollIntoView({ behavior: 'smooth' }); setActiveId(s.id); }}>
                    <span className="lp-guide-sidebar-num">{String(i + 1).padStart(2, '0')}</span>
                    <i className={`fas ${s.icon}`} />
                    <span>{s[`title_${lang}`]}</span>
                  </a>
                </li>
              ))}
            </ol>
          </nav>
        </aside>

        <div className="lp-guide-articles">
          {/* Getting Started */}
          <article className="lp-guide-section" id="getting-started">
            <h2><i className="fas fa-rocket" /> {t('Erste Schritte', 'Getting Started')}</h2>
            <p>{t(
              'MYND ist deine lokale Personal-AI-Plattform. Stelle Fragen zu deinen Dateien, Geräten und Diensten — alles läuft auf deiner eigenen Infrastruktur.',
              'MYND is your local personal AI platform. Ask questions about your files, devices and services — everything runs on your own infrastructure.'
            )}</p>
            <h3>{t('1. Systemvoraussetzungen', '1. System requirements')}</h3>
            <p>{t('Python 3.10+, Node.js 18+, 4 GB RAM (8+ empfohlen), 20+ GB Speicher.', 'Python 3.10+, Node.js 18+, 4 GB RAM (8+ recommended), 20+ GB storage.')}</p>
            <h3>{t('2. Backend installieren & starten', '2. Install & start the backend')}</h3>
            <pre className="lp-guide-code"><code>{`git clone https://github.com/SchBenedikt/mynd.git
cd mynd
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py`}</code></pre>
            <p>{t('Der Server läuft auf http://0.0.0.0:5001.', 'The server runs on http://0.0.0.0:5001.')}</p>
            <h3>{t('3. Frontend starten', '3. Start the frontend')}</h3>
            <pre className="lp-guide-code"><code>{`cd frontend
npm install
npm run dev`}</code></pre>
            <p>{t('Die UI ist erreichbar unter http://localhost:3000.', 'The UI is at http://localhost:3000.')}</p>
            <h3>{t('4. Account erstellen & KI konfigurieren', '4. Create account & configure AI')}</h3>
            <p>{t(
              'Öffne die UI, klicke "Sign in" → "Create account". Gehe zu Settings → AI und wähle deinen Modellanbieter (Ollama oder OpenAI-kompatibel). Danach unter Settings → Integrations die gewünschten Dienste verbinden.',
              'Open the UI, click "Sign in" → "Create account". Go to Settings → AI and choose your model provider (Ollama or OpenAI-compatible). Then connect your services under Settings → Integrations.'
            )}</p>
            <div className="lp-guide-tip"><i className="fas fa-lightbulb" /><span>{t('Für Produktivbetrieb: Nutze einen Reverse Proxy (nginx) und einen Prozess-Manager (systemd).', 'For production: Use a reverse proxy (nginx) and a process manager (systemd).')}</span></div>
          </article>

          {/* Architecture */}
          <article className="lp-guide-section" id="architecture">
            <h2><i className="fas fa-sitemap" /> {t('Architektur', 'Architecture')}</h2>
            <p>{t(
              'MYND besteht aus drei Schichten: einem Python-Flask-Backend (API, Port 5001), einem Next.js-Frontend (UI, Port 3000) und einem KI-Modellanbieter (Ollama oder OpenAI-kompatibel).',
              'MYND consists of three layers: a Python Flask backend (API, port 5001), a Next.js frontend (UI, port 3000), and an AI model provider (Ollama or OpenAI-compatible).'
            )}</p>
            <h3>{t('Backend', 'Backend')}</h3>
            <p>{t(
              'Das Backend in app/routes.py verarbeitet API-Anfragen, Authentifizierung, KI-Kommunikation, Plugin-Verwaltung und die Agenten-Schleife. Plugins in data/plugins/ erweitern es um 25+ Tools in 11 Integrationen.',
              'The backend in app/routes.py handles API requests, authentication, AI communication, plugin management, and the agent loop. Plugins in data/plugins/ extend it with 25+ tools across 11 integrations.'
            )}</p>
            <h3>{t('Frontend', 'Frontend')}</h3>
            <p>{t(
              'Die React-basierte UI bietet Chat, Einstellungen, Plugin-Manager und Marketing-Seiten. Sie kommuniziert per REST-API und SSE für Echtzeit-Streaming.',
              'The React-based UI provides chat, settings, plugin manager, and marketing pages. It communicates via REST API and SSE for real-time streaming.'
            )}</p>
            <h3>{t('KI-Agenten-Schleife', 'AI Agent Loop')}</h3>
            <p>{t(
              'Bei einer Frage: (1) Prompt + Tool-Definitionen ans Modell senden, (2) Modell entscheidet über Tool-Aufrufe, (3) MYND führt Tools aus und gibt Ergebnisse zurück, (4) Modell erzeugt finale Antwort. Bis zu 100 Runden pro Anfrage.',
              'When you ask: (1) send prompt + tool definitions to the model, (2) model decides tool calls, (3) MYND executes tools and returns results, (4) model produces final answer. Up to 100 rounds per query.'
            )}</p>
            <div className="lp-guide-tip"><i className="fas fa-lightbulb" /><span>{t('Das System-Plugin (system.py) stellt Timer, Wetter, Websuche und Festplatten-Überwachung bereit — immer verfügbar, keine Konfiguration nötig.', 'The system plugin (system.py) provides timers, weather, web search, and disk monitoring — always available, no config needed.')}</span></div>
          </article>

          {/* AI Models */}
          <article className="lp-guide-section" id="ai-models">
            <h2><i className="fas fa-brain" /> {t('KI-Modelle', 'AI Models')}</h2>
            <p>{t(
              'MYND funktioniert mit Ollama (lokal) und allen OpenAI-kompatiblen APIs. Die Wahl des Modells bestimmt Geschwindigkeit, Qualität und ob Tool-Aufrufe möglich sind.',
              'MYND works with Ollama (local) and all OpenAI-compatible APIs. Your model choice determines speed, quality, and whether tool calling is available.'
            )}</p>

            <h3>{t('Tool-Support — worauf es ankommt', 'Tool Support — what matters')}</h3>
            <p>{t(
              'Nicht alle Modelle unterstützen Tool-Calling (Funktionsaufrufe). Ohne diese Fähigkeit kann MYND keine Timer stellen, Dateien durchsuchen, Smart-Home-Geräte schalten oder andere Aktionen ausführen — es kann nur Text generieren. Ein Modell muss explizit für Tool-Calling trainiert sein.',
              'Not all models support tool-calling (function calling). Without it, MYND cannot set timers, search files, toggle smart home devices, or execute any actions — it can only generate text. A model must be explicitly trained for tool-calling.'
            )}</p>
            <div className="lp-guide-table">
              <div className="lp-guide-tr lp-guide-th"><span>{t('Unterstützung', 'Support')}</span><span>{t('Bedeutung', 'Meaning')}</span></div>
              <div className="lp-guide-tr"><span className="lp-guide-mono">{t('Ja', 'Yes')}</span><span>{t('MYND kann Tools zuverlässig aufrufen und Ergebnisse verarbeiten.', 'MYND can reliably call tools and process results.')}</span></div>
              <div className="lp-guide-tr"><span className="lp-guide-mono">{t('Eingeschränkt', 'Limited')}</span><span>{t('Funktioniert teilweise, aber unzuverlässig — MYND fällt dann auf Text-Antwort zurück.', 'Works partially but unreliably — MYND falls back to text-only.')}</span></div>
              <div className="lp-guide-tr"><span className="lp-guide-mono">{t('Nein', 'No')}</span><span>{t('MYND kann keine Aktionen ausführen — nur Chat / Text-Antworten.', 'MYND cannot perform any actions — chat / text only.')}</span></div>
            </div>

            <h3>{t('Ollama installieren', 'Install Ollama')}</h3>
            <pre className="lp-guide-code"><code>{`# Linux
curl -fsSL https://ollama.com/install.sh | sh
# macOS/Windows: Download von https://ollama.com`}</code></pre>

            <h3>{t('Lokale Modell-Empfehlungen (Ollama)', 'Local model recommendations (Ollama)')}</h3>
            <p>{t(
              'Lokale Modelle laufen auf deiner Hardware, sind kostenlos und privat. Benötigen Ollama 0.3.0+ für Tool-Support. Je größer das Modell, desto besser die Tool-Kompetenz — aber auch mehr RAM.',
              'Local models run on your hardware, are free and private. Require Ollama 0.3.0+ for tool support. Larger models mean better tool competence — but also more RAM.'
            )}</p>
            <div className="lp-guide-table">
              <div className="lp-guide-tr lp-guide-th"><span>{t('Hardware', 'Hardware')}</span><span>{t('Modell', 'Model')}</span><span>{t('RAM', 'RAM')}</span><span>{t('Tool-Support', 'Tool Support')}</span><span>{t('Bewertung', 'Rating')}</span></div>
              <div className="lp-guide-tr"><span>8 GB</span><span className="lp-guide-mono">phi</span><span>~4 GB</span><span>{t('Ja', 'Yes')}</span><span>{t('Gut für einfache Tools', 'Good for simple tools')}</span></div>
              <div className="lp-guide-tr"><span>8 GB</span><span className="lp-guide-mono">tinyllama</span><span>~2 GB</span><span>{t('Nein', 'No')}</span><span>{t('Nur Chat, keine Aktionen', 'Chat only, no actions')}</span></div>
              <div className="lp-guide-tr"><span>8 GB</span><span className="lp-guide-mono">llama3.2:3b</span><span>~3 GB</span><span>{t('Ja', 'Yes')}</span><span>{t('Tools + schnell', 'Tools + fast')}</span></div>
              <div className="lp-guide-tr"><span>16 GB</span><span className="lp-guide-mono">llama3.2</span><span>~8 GB</span><span>{t('Ja', 'Yes')}</span><span>{t('Gut für tägliche Nutzung', 'Good for daily use')}</span></div>
              <div className="lp-guide-tr"><span>16 GB</span><span className="lp-guide-mono">mistral</span><span>~7 GB</span><span>{t('Ja', 'Yes')}</span><span>{t('Sehr guter Tool-Support', 'Very good tool support')}</span></div>
              <div className="lp-guide-tr"><span>16 GB</span><span className="lp-guide-mono">qwen2.5:7b</span><span>~6 GB</span><span>{t('Ja', 'Yes')}</span><span>{t('Hervorragend + multilingual', 'Excellent + multilingual')}</span></div>
              <div className="lp-guide-tr"><span>32 GB</span><span className="lp-guide-mono">qwen2.5</span><span>~9 GB</span><span>{t('Ja', 'Yes')}</span><span>{t('Bester Tool-Support (lokal)', 'Best tool support (local)')}</span></div>
              <div className="lp-guide-tr"><span>32 GB</span><span className="lp-guide-mono">llama3.1</span><span>~12 GB</span><span>{t('Ja', 'Yes')}</span><span>{t('Solide, aber RAM-intensiv', 'Solid but RAM-heavy')}</span></div>
              <div className="lp-guide-tr"><span>48+ GB</span><span className="lp-guide-mono">qwen2.5:72b</span><span>~45 GB</span><span>{t('Ja', 'Yes')}</span><span>{t('Beste Qualität, viel RAM', 'Best quality, heavy RAM')}</span></div>
            </div>
            <div className="lp-guide-tip"><i className="fas fa-lightbulb" /><span>{t('Tipp: Starte mit qwen2.5:7b (16 GB RAM) — es bietet den besten Tool-Support bei moderatem RAM-Verbrauch. Für 8 GB ist llama3.2:3b die beste Wahl.', 'Tip: Start with qwen2.5:7b (16 GB RAM) — best tool support at moderate RAM. For 8 GB, llama3.2:3b is the best choice.')}</span></div>

            <h3>{t('Cloud-Anbieter', 'Cloud providers')}</h3>
            <p>{t(
              'Cloud-Modelle werden extern gehostet — schneller, leistungsfähiger, aber mit Kosten verbunden. Alle gängigen Anbieter unterstützen Tool-Calling. Konfiguriere Base-URL und API-Key in Settings → AI.',
              'Cloud models are externally hosted — faster, more capable, but incur costs. All major providers support tool-calling. Configure Base URL and API key in Settings → AI.'
            )}</p>

            <h3>{t('OpenAI', 'OpenAI')}</h3>
            <p>{t(
              'Bester Tool-Support am Markt. GPT-4o und GPT-4o-mini beherrschen parallele Tool-Aufrufe, strukturierte Outputs und komplexe Workflows. Einfach API-Key in Settings → AI eintragen.',
              'Best tool support on the market. GPT-4o and GPT-4o-mini handle parallel tool calls, structured outputs, and complex workflows. Just add your API key in Settings → AI.'
            )}</p>

            <h3>{t('Anthropic (Claude)', 'Anthropic (Claude)')}</h3>
            <p>{t(
              'Claude 3.5 Sonnet / Haiku haben exzellenten Tool-Support mit hoher Zuverlässigkeit. Claude denkt zuerst nach (Extended Thinking) und ruft dann präzise Tools auf. API-Key + https://api.anthropic.com als Base-URL.',
              'Claude 3.5 Sonnet / Haiku have excellent tool support with high reliability. Claude thinks first (Extended Thinking) then calls tools precisely. API key + https://api.anthropic.com as Base URL.'
            )}</p>

            <h3>{t('Google Gemini', 'Google Gemini')}</h3>
            <p>{t(
              'Gemini 2.0 Flash / Pro unterstützen nativen Tool-Calling. Sehr schnell, günstig, gut für Echtzeit-Anwendungen. API-Key + https://generativelanguage.googleapis.com/v1beta/openai/ als Base-URL.',
              'Gemini 2.0 Flash / Pro support native tool-calling. Very fast, cheap, great for real-time applications. API key + https://generativelanguage.googleapis.com/v1beta/openai/ as Base URL.'
            )}</p>

            <h3>{t('Groq', 'Groq')}</h3>
            <p>{t(
              'Groq bietet Llama-3.3-70B und andere Modelle mit extrem niedriger Latenz durch spezielle Hardware (LPU). Exzellenter Tool-Support. Kostenloser Tier verfügbar. Base-URL: https://api.groq.com/openai.',
              'Groq runs Llama-3.3-70B and other models on specialized LPU hardware for extremely low latency. Excellent tool support. Free tier available. Base URL: https://api.groq.com/openai.'
            )}</p>

            <h3>{t('Together AI', 'Together AI')}</h3>
            <p>{t(
              'Together hostet 100+ Open-Source-Modelle (Llama, Qwen, DeepSeek, Mixtral) mit Tool-Calling. Flexible Auswahl, gute Preise. Base-URL: https://api.together.xyz/v1.',
              'Together hosts 100+ open-source models (Llama, Qwen, DeepSeek, Mixtral) with tool-calling. Flexible selection, good pricing. Base URL: https://api.together.xyz/v1.'
            )}</p>

            <h3>{t('Ollama Cloud / OpenRouter', 'Ollama Cloud / OpenRouter')}</h3>
            <p>{t(
              'OpenRouter ist ein Aggregator, der über 200 Modelle von 20+ Anbietern bündelt — inklusive aller lokalen Modelle (Qwen, Llama, DeepSeek) als Cloud-API. Du zahlst nur pro Token. Tool-Calling wird von den meisten Modellen unterstützt. Base-URL: https://openrouter.ai/api/v1. Auch andere Anbieter wie DeepSeek, Perplexity oder Azure OpenAI sind kompatibel — solange sie eine OpenAI-kompatible API bereitstellen.',
              'OpenRouter is an aggregator unifying 200+ models from 20+ providers — including all local models (Qwen, Llama, DeepSeek) as cloud APIs. Pay per token. Most models support tool-calling. Base URL: https://openrouter.ai/api/v1. Other providers like DeepSeek, Perplexity, or Azure OpenAI work too — as long as they offer an OpenAI-compatible API.'
            )}</p>

            <h3>{t('Cloud-Anbieter Vergleich', 'Cloud provider comparison')}</h3>
            <div className="lp-guide-table">
              <div className="lp-guide-tr lp-guide-th"><span>{t('Anbieter', 'Provider')}</span><span>{t('Tool-Support', 'Tool Support')}</span><span>{t('Latenz', 'Latency')}</span><span>{t('Kosten', 'Cost')}</span><span>{t('Modelle', 'Models')}</span></div>
              <div className="lp-guide-tr"><span className="lp-guide-mono">OpenAI</span><span>{t('Hervorragend', 'Excellent')}</span><span>{t('Niedrig', 'Low')}</span><span>{t('Mittel', 'Medium')}</span><span>GPT-4o, GPT-4o-mini, o3</span></div>
              <div className="lp-guide-tr"><span className="lp-guide-mono">Anthropic</span><span>{t('Hervorragend', 'Excellent')}</span><span>{t('Mittel', 'Medium')}</span><span>{t('Mittel', 'Medium')}</span><span>Claude 3.5 Sonnet/Haiku</span></div>
              <div className="lp-guide-tr"><span className="lp-guide-mono">Google</span><span>{t('Sehr gut', 'Very good')}</span><span>{t('Niedrig', 'Low')}</span><span>{t('Niedrig', 'Low')}</span><span>Gemini 2.0 Flash/Pro</span></div>
              <div className="lp-guide-tr"><span className="lp-guide-mono">Groq</span><span>{t('Sehr gut', 'Very good')}</span><span>{t('Sehr niedrig', 'Very low')}</span><span>{t('Kostenlos / Niedrig', 'Free / Low')}</span><span>Llama 3.3-70B, Mixtral</span></div>
              <div className="lp-guide-tr"><span className="lp-guide-mono">Together</span><span>{t('Gut', 'Good')}</span><span>{t('Niedrig', 'Low')}</span><span>{t('Niedrig', 'Low')}</span><span>100+ Open-Source</span></div>
              <div className="lp-guide-tr"><span className="lp-guide-mono">OpenRouter</span><span>{t('Variiert', 'Varies')}</span><span>{t('Variiert', 'Varies')}</span><span>{t('Pro Token', 'Per token')}</span><span>200+ Modelle</span></div>
            </div>

            <div className="lp-guide-tip"><i className="fas fa-lightbulb" /><span>{t('Cloud-Modelle sind schneller und leistungsfähiger, aber Daten verlassen deine Infrastruktur. Lokale Modelle sind kostenlos und privat. Für Tool-Support wird Ollama 0.3.0+ benötigt.', 'Cloud models are faster and more capable, but data leaves your infrastructure. Local models are free and private. Tool support requires Ollama 0.3.0+.')}</span></div>
          </article>

          {/* Security & Modes */}
          <article className="lp-guide-section" id="security">
            <h2><i className="fas fa-shield-halved" /> {t('Sicherheit & Modi', 'Security & Modes')}</h2>
            <p>{t(
              'MYND bietet mehrere Sicherheitsebenen. Der richtige Modus balanciert Komfort und Sicherheit.',
              'MYND offers multiple security layers. Choosing the right mode balances convenience and safety.'
            )}</p>
            <h3>{t('Sicherheitsmodi (Settings → AI)', 'Security Modes (Settings → AI)')}</h3>
            <div className="lp-guide-table">
              <div className="lp-guide-tr lp-guide-th"><span>{t('Modus', 'Mode')}</span><span>{t('Beschreibung', 'Description')}</span></div>
              <div className="lp-guide-tr"><span className="lp-guide-mono">{t('Restricted', 'Restricted')}</span><span>{t('Nur Dokumentsuche + Gedächtnis. Keine externen Tools.', 'Only document search + memory. No external tools.')}</span></div>
              <div className="lp-guide-tr"><span className="lp-guide-mono">{t('Standard', 'Standard')}</span><span>{t('Vault + Tools, kein SSH/Admin.', 'Vault + tools, no SSH/admin.')}</span></div>
              <div className="lp-guide-tr"><span className="lp-guide-mono">{t('Admin', 'Admin')}</span><span>{t('Voller Zugriff inkl. SSH – vollautonom.', 'Full access including SSH – fully autonomous.')}</span></div>
            </div>
            <h3>{t('Berechtigungsmodus (Bash/SSH)', 'Permission Mode (Bash/SSH)')}</h3>
            <p>{t(
              'MYND_PERMISSION_MODE=auto (alle erlaubt) / semi (nur rm,sudo,dd) / ask (jeder Befehl). Setzbar in .env oder als Umgebungsvariable.',
              'MYND_PERMISSION_MODE=auto (all allowed) / semi (only rm,sudo,dd) / ask (every command). Set in .env or as environment variable.'
            )}</p>
            <h3>{t('Authentifizierung', 'Authentication')}</h3>
            <p>{t(
              'API-Endpunkte benötigen Authentifizierung (außer Login/Register/Health). Rollen: user (eingeschränkt) und admin (volle Kontrolle). Admins können andere Admins erstellen, Plugins verwalten und die App zurücksetzen.',
              'API endpoints require authentication (except login/register/health). Roles: user (restricted) and admin (full control). Admins can create other admins, manage plugins, and reset the app.'
            )}</p>
            <div className="lp-guide-tip"><i className="fas fa-lightbulb" /><span>{t('Alle Daten bleiben auf deiner Infrastruktur. MYND sendet nichts an externe Server (außer deinem konfigurierten KI-Anbieter).', 'All data stays on your infrastructure. MYND sends nothing to external servers (except your configured AI provider).')}</span></div>
          </article>

          {/* Nextcloud */}
          <article className="lp-guide-section" id="nextcloud">
            <h2><i className="fas fa-cloud" /> {t('Nextcloud', 'Nextcloud')}</h2>
            <p>{t('Verbinde MYND mit deiner Nextcloud, um Dateien zu durchsuchen, Kalender und Aufgaben abzurufen.', 'Connect MYND to your Nextcloud to browse files, fetch calendars and tasks.')}</p>
            <h3>{t('1. App-Passwort erstellen', '1. Create app password')}</h3>
            <p>{t('In Nextcloud: Einstellungen → Sicherheit → "App-Passwort erstellen". Namen "MYND" vergeben.', 'In Nextcloud: Settings → Security → "Create app password". Name it "MYND".')}</p>
            <h3>{t('2. Verbindung einrichten', '2. Configure connection')}</h3>
            <p>{t('Settings → Integrations → Nextcloud. URL, Benutzername und App-Passwort eintragen. "Connect" klicken.', 'Settings → Integrations → Nextcloud. Enter URL, username and app password. Click "Connect".')}</p>
            <h3>{t('3. Nutzung', '3. Usage')}</h3>
            <p>{t(
              'Frage: "Suche in Nextcloud nach der Budget-Tabelle", "Was gibt es Neues im Projekte-Ordner?", "Zeige meine Termine für morgen", "Erstelle einen Termin für Freitag 15 Uhr".',
              'Ask: "Search my Nextcloud for the budget spreadsheet", "What is new in the Projects folder?", "Show my appointments for tomorrow", "Create an event for Friday 3 PM".'
            )}</p>
            <div className="lp-guide-tip"><i className="fas fa-lightbulb" /><span>{t('Unterstützte Formate: PDF, TXT, DOCX, ODT, Markdown, Code-Dateien. Kalender und Aufgaben sind lesend verfügbar.', 'Supported formats: PDF, TXT, DOCX, ODT, Markdown, code files. Calendars and tasks are read-only.')}</span></div>
          </article>

          {/* Immich */}
          <article className="lp-guide-section" id="immich">
            <h2><i className="fas fa-images" /> {t('Immich', 'Immich')}</h2>
            <p>{t('KI-gestützte Fotosuche — durchsuche deine gesamte Bibliothek mit natürlicher Sprache.', 'AI-powered photo search — search your entire library with natural language.')}</p>
            <h3>{t('1. API-Key erstellen', '1. Create API key')}</h3>
            <p>{t('In Immich: Settings → Users → API Key. Namen "MYND" vergeben. Key wird nur einmal angezeigt.', 'In Immich: Settings → Users → API Key. Name it "MYND". Key shown once.')}</p>
            <h3>{t('2. Verbinden', '2. Connect')}</h3>
            <p>{t('Settings → Integrations → Immich. URL und API-Key eintragen. "Connect".', 'Settings → Integrations → Immich. Enter URL and API key. Click "Connect".')}</p>
            <h3>{t('3. Nutzung', '3. Usage')}</h3>
            <p>{t(
              'Frage: "Zeige Fotos vom letzten Sommer", "Finde Bilder mit Strand", "Welche Fotos habe ich in Paris gemacht?", "Finde Fotos von [Person]".',
              'Ask: "Show photos from last summer", "Find pictures with beaches", "What photos did I take in Paris?", "Find photos of [person]".'
            )}</p>
            <div className="lp-guide-tip"><i className="fas fa-lightbulb" /><span>{t('MYND durchsucht Metadaten — Originalfotos bleiben in Immich. Keine Bilder werden übertragen.', 'MYND searches metadata — original photos stay in Immich. No images are transferred.')}</span></div>
          </article>

          {/* Home Assistant */}
          <article className="lp-guide-section" id="homeassistant">
            <h2><i className="fas fa-house-signal" /> {t('Home Assistant', 'Home Assistant')}</h2>
            <p>{t('Smart Home steuern — Sensoren abfragen, Geräte schalten, Automationen auslösen.', 'Control your smart home — query sensors, toggle devices, trigger automations.')}</p>
            <h3>{t('1. Long-Lived Token erstellen', '1. Create Long-Lived Token')}</h3>
            <p>{t('In Home Assistant: Profil (unten links) → "Langzeit-Zugriffstoken". Token erstellen und kopieren.', 'In Home Assistant: Profile (bottom left) → "Long-Lived Access Token". Create and copy.')}</p>
            <h3>{t('2. Verbinden', '2. Connect')}</h3>
            <p>{t('Settings → Integrations → Home Assistant. URL (z.B. http://homeassistant.local:8123) und Token eintragen.', 'Settings → Integrations → Home Assistant. Enter URL (e.g. http://homeassistant.local:8123) and token.')}</p>
            <h3>{t('3. Nutzung', '3. Usage')}</h3>
            <p>{t(
              'Frage: "Wie ist die Temperatur im Wohnzimmer?", "Schalte alle Lichter aus", "Ist die Haustür verriegelt?", "Starte die Guten-Morgen-Automation".',
              'Ask: "What is the temperature in the living room?", "Turn off all lights", "Is the front door locked?", "Run the good morning automation".'
            )}</p>
            <div className="lp-guide-tip"><i className="fas fa-lightbulb" /><span>{t('MYND kann Sensoren abfragen und Geräte schalten — im Admin-Modus vollautonom.', 'MYND can query sensors and toggle devices — fully autonomous in Admin mode.')}</span></div>
          </article>

          {/* Email */}
          <article className="lp-guide-section" id="email">
            <h2><i className="fas fa-envelope" /> {t('E-Mail', 'Email')}</h2>
            <p>{t('Postfach per IMAP/SMTP anbinden — E-Mails suchen, lesen und senden.', 'Connect mailbox via IMAP/SMTP — search, read and send emails.')}</p>
            <h3>{t('1. Zugangsdaten', '1. Credentials')}</h3>
            <p>{t('Du benötigst: IMAP-Server (Empfang), SMTP-Server (Versand), Benutzername und Passwort.', 'You need: IMAP server (receiving), SMTP server (sending), username and password.')}</p>
            <h3>{t('2. Konto hinzufügen', '2. Add account')}</h3>
            <p>{t('Settings → Integrations → Email → "Add Account". Server-Daten eintragen und verbinden.', 'Settings → Integrations → Email → "Add Account". Enter server details and connect.')}</p>
            <h3>{t('3. Nutzung', '3. Usage')}</h3>
            <p>{t(
              'Frage: "Zeige meine ungelesenen E-Mails", "Finde die Rechnung vom letzten Monat", "Sende eine E-Mail an max@example.com mit Betreff Meeting und Inhalt: Morgen 15 Uhr".',
              'Ask: "Show my unread emails", "Find the invoice from last month", "Send an email to max@example.com with subject Meeting and body: Tomorrow 3 PM".'
            )}</p>
            <div className="lp-guide-tip"><i className="fas fa-lightbulb" /><span>{t('Bei Gmail ein App-Passwort verwenden (google.com/apppasswords).', 'For Gmail, use an app password (google.com/apppasswords).')}</span></div>
          </article>

          {/* Spotify */}
          <article className="lp-guide-section" id="spotify">
            <h2><i className="fas fa-spotify" /> {t('Spotify', 'Spotify')}</h2>
            <p>{t('Wiedergabe steuern, Titel suchen und Playlists verwalten.', 'Control playback, search tracks and manage playlists.')}</p>
            <h3>{t('1. Spotify-App erstellen', '1. Create Spotify app')}</h3>
            <p>{t('https://developer.spotify.com/dashboard → "Create App". Redirect-URI: http://localhost:5001/callback/spotify. Client-ID und Secret kopieren.', 'https://developer.spotify.com/dashboard → "Create App". Redirect URI: http://localhost:5001/callback/spotify. Copy Client ID and Secret.')}</p>
            <h3>{t('2. Verbinden', '2. Connect')}</h3>
            <p>{t('Settings → Integrations → Spotify. Client-ID und Secret eintragen → "Connect".', 'Settings → Integrations → Spotify. Enter Client ID and Secret → "Connect".')}</p>
            <h3>{t('3. Nutzung', '3. Usage')}</h3>
            <p>{t(
              'Frage: "Spiele [Song] von [Künstler]", "Pausiere", "Nächster Titel", "Spiele meine Discover Weekly Playlist", "Erstelle eine Playlist mit Namen".',
              'Ask: "Play [song] by [artist]", "Pause", "Next track", "Play my Discover Weekly playlist", "Create a playlist called".'
            )}</p>
            <div className="lp-guide-tip"><i className="fas fa-lightbulb" /><span>{t('Spotify Premium erforderlich für Wiedergabesteuerung. Für Produktivbetrieb Redirect-URI anpassen.', 'Spotify Premium required for playback control. Update Redirect URI for production.')}</span></div>
          </article>

          {/* Discord */}
          <article className="lp-guide-section" id="discord">
            <h2><i className="fas fa-discord" /> {t('Discord', 'Discord')}</h2>
            <p>{t('Nachrichten lesen, Kanäle durchsuchen und Nachrichten senden.', 'Read messages, search channels and send messages.')}</p>
            <h3>{t('1. Bot erstellen', '1. Create bot')}</h3>
            <p>{t('https://discord.com/developers → "New Application" → "Bot". Token kopieren. "Message Content Intent" aktivieren.', 'https://discord.com/developers → "New Application" → "Bot". Copy token. Enable "Message Content Intent".')}</p>
            <h3>{t('2. Bot einladen', '2. Invite bot')}</h3>
            <p>{t('OAuth2 → URL Generator. "bot" mit Berechtigungen: Send Messages, Read Message History, View Channels.', 'OAuth2 → URL Generator. Select "bot" with permissions: Send Messages, Read Message History, View Channels.')}</p>
            <h3>{t('3. Verbinden', '3. Connect')}</h3>
            <p>{t('Settings → Integrations → Discord. Bot-Token eintragen. "Connect".', 'Settings → Integrations → Discord. Enter bot token. Click "Connect".')}</p>
            <div className="lp-guide-tip"><i className="fas fa-lightbulb" /><span>{t('MYND kann keine DMs lesen — nur Kanäle, in denen der Bot Mitglied ist.', 'MYND cannot read DMs — only channels the bot is a member of.')}</span></div>
          </article>

          {/* TrueNAS */}
          <article className="lp-guide-section" id="truenas">
            <h2><i className="fas fa-database" /> {t('TrueNAS', 'TrueNAS')}</h2>
            <p>{t('Speicher, Festplatten und SMART-Werte über die TrueNAS-API überwachen.', 'Monitor storage, disks and SMART values via the TrueNAS API.')}</p>
            <h3>{t('1. API-Key erstellen', '1. Create API key')}</h3>
            <p>{t('In TrueNAS: Settings → API Keys → "Add". Namen "MYND" vergeben.', 'In TrueNAS: Settings → API Keys → "Add". Name it "MYND".')}</p>
            <h3>{t('2. Verbinden', '2. Connect')}</h3>
            <p>{t('Settings → Integrations → TrueNAS. URL (z.B. http://truenas.local:8080) und API-Key eintragen.', 'Settings → Integrations → TrueNAS. Enter URL (e.g. http://truenas.local:8080) and API key.')}</p>
            <h3>{t('3. Nutzung', '3. Usage')}</h3>
            <p>{t(
              'Frage: "Wie ist der Speicherstatus?", "Wie voll ist der Hauptpool?", "Gibt es Festplatten-Alarme?", "Zeige SMART-Status aller Festplatten".',
              'Ask: "What is the storage status?", "How full is the main pool?", "Are there any disk alerts?", "Show SMART status of all drives".'
            )}</p>
          </article>

          {/* Browser */}
          <article className="lp-guide-section" id="browser">
            <h2><i className="fas fa-globe" /> {t('Browser', 'Browser')}</h2>
            <p>{t('MYND enthält einen integrierten Cloud-Browser für Web-Recherche.', 'MYND includes a built-in cloud browser for web research.')}</p>
            <h3>{t('Funktionsweise', 'How it works')}</h3>
            <p>{t('Eine server-seitige, isolierte Chromium-Instanz. Keine Cookies oder Sitzungen werden mit deinem normalen Browser geteilt.', 'A server-side, isolated Chromium instance. No cookies or sessions shared with your regular browser.')}</p>
            <h3>{t('Nutzung', 'Usage')}</h3>
            <p>{t(
              'Frage: "Öffne [URL]", "Mach einen Screenshot von [URL]", "Fasse den Inhalt von [URL] zusammen", "Suche auf der Seite nach [Suchbegriff]".',
              'Ask: "Open [URL]", "Take a screenshot of [URL]", "Summarize the content of [URL]", "Search the page for [query]".'
            )}</p>
            <div className="lp-guide-tip"><i className="fas fa-lightbulb" /><span>{t('Der integrierte Browser läuft isoliert auf dem Server und teilt keine Cookies mit deinem lokalen Browser.', 'The built-in browser runs isolated on the server and does not share cookies with your local browser.')}</span></div>
          </article>

          <footer className="lp-guide-article-footer">
            <p>{t(
              'Noch Fragen? Das Developer Portal und der Quellcode auf GitHub enthalten weitere Details.',
              'Questions? The Developer Portal and source code on GitHub have more details.'
            )}</p>
            <Link href="/" className="lp-guide-primary-cta">
              <i className="fas fa-arrow-left" />
              {t('Zurück zur Startseite', 'Back to home')}
            </Link>
          </footer>
        </div>
      </div>

      <footer className="lp-guide-footer">
        <div className="lp-guide-shell lp-guide-footer-inner">
          <Link href="/" className="lp-guide-logo"><span className="lp-guide-logo-mark"><i /></span><span>MYND</span></Link>
          <p>© {new Date().getFullYear()} MYND · {t('Setup-Anleitung', 'Setup guide')}</p>
          <Link href="/developers">{t('Entwickler-Dokumentation', 'Developer Docs')}</Link>
        </div>
      </footer>
    </div>
  );
}
