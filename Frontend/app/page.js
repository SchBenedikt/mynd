"use client";

import { useEffect, useMemo, useState } from "react";

const SUGGESTIONS = [
  "Welche Termine habe ich morgen?",
  "Fasse mir die letzten Dokumente kurz zusammen.",
  "Was steht naechste Woche im Kalender?",
  "Suche Infos zu meinen Projekten aus den Dateien."
];

function buildApiUrl(path) {
  const base = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:5001";
  return `${base}${path}`;
}

function SourceBadge({ source }) {
  const label = source === "photos" ? "Fotos" : source === "files" ? "Dateien" : "Alle Quellen";
  return <span className="source-badge">Quelle: {label}</span>;
}

export default function HomePage() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [theme, setTheme] = useState("classic");
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState([]);
  const [isThinking, setIsThinking] = useState(false);
  const [source, setSource] = useState("auto");
  const [health, setHealth] = useState({ ollama: "unknown", kb: "unknown" });
  const [statusText, setStatusText] = useState("Index: n/a");
  const [error, setError] = useState("");

  useEffect(() => {
    document.body.setAttribute("data-theme", theme);
  }, [theme]);

  useEffect(() => {
    let isMounted = true;

    async function loadStatus() {
      try {
        const [ollamaRes, kbRes] = await Promise.all([
          fetch(buildApiUrl("/api/ollama/status")),
          fetch(buildApiUrl("/api/knowledge/status"))
        ]);

        const ollama = await ollamaRes.json();
        const kb = await kbRes.json();

        if (!isMounted) return;

        setHealth({
          ollama: ollama.connected ? "ok" : "error",
          kb: kb.chunks_loaded > 0 ? "ok" : "warn"
        });
        setStatusText(`Index: ${kb.chunks_loaded || 0} Chunks | Modell: ${ollama.model || "n/a"}`);
      } catch {
        if (!isMounted) return;
        setHealth({ ollama: "error", kb: "unknown" });
        setStatusText("Index: Status nicht verfuegbar");
      }
    }

    loadStatus();
    const interval = setInterval(loadStatus, 8000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  const showConversation = useMemo(() => messages.length > 0, [messages.length]);

  async function sendMessage(textToSend) {
    const cleaned = textToSend.trim();
    if (!cleaned || isThinking) return;

    setError("");
    setMessages((prev) => [...prev, { role: "user", content: cleaned }]);
    setPrompt("");
    setIsThinking(true);

    try {
      const response = await fetch(buildApiUrl("/api/chat"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: cleaned, source })
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Unbekannter Fehler");
      }

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.response || "Keine Antwort erhalten." }
      ]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Verbindungsfehler";
      setError(msg);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `Fehler: ${msg}` }
      ]);
    } finally {
      setIsThinking(false);
    }
  }

  return (
    <>
      <header className="topbar">
        <button className="icon-btn" onClick={() => setSidebarOpen((v) => !v)} aria-label="Sidebar">
          ☰
        </button>
        <div className="brand">
          <span className="spark" />
          <h1>NextMind</h1>
        </div>
        <div className="top-status-badge">{statusText}</div>
      </header>

      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="sidebar-head">
          <strong>Kontext-Tools</strong>
          <button className="btn" onClick={() => setMessages([])}>Neu</button>
        </div>
        <div className="sidebar-section">
          <h3>Quellfokus</h3>
          <div className="row">
            <button className={`btn ${source === "auto" ? "active" : ""}`} onClick={() => setSource("auto")}>Auto</button>
            <button className={`btn ${source === "files" ? "active" : ""}`} onClick={() => setSource("files")}>Dateien</button>
            <button className={`btn ${source === "photos" ? "active" : ""}`} onClick={() => setSource("photos")}>Fotos</button>
          </div>
        </div>
        <div className="sidebar-section grow">
          <h3>Schnellaktionen</h3>
          <p className="muted">Direkt aus deinem bestehenden Flask-Backend gespeist.</p>
          <div className="status-list">
            <div>Ollama: <span className={`dot ${health.ollama}`} /> {health.ollama}</div>
            <div>Knowledge: <span className={`dot ${health.kb}`} /> {health.kb}</div>
          </div>
        </div>
      </aside>

      <button className="profile-fab" onClick={() => setProfileOpen((v) => !v)} aria-label="Profil">
        ⚙
      </button>

      <aside className={`profile-drawer ${profileOpen ? "open" : ""}`}>
        <h3>UI-Einstellungen</h3>
        <label htmlFor="theme" className="muted">Theme</label>
        <select id="theme" className="input" value={theme} onChange={(e) => setTheme(e.target.value)}>
          <option value="classic">Klassisch</option>
          <option value="ocean">Ocean</option>
          <option value="graphite">Graphite</option>
        </select>
        <p className="muted">Backend URL: {process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:5001"}</p>
      </aside>

      <main className={`shell ${sidebarOpen ? "shifted" : ""}`}>
        <div className="content-wrap">
          {!showConversation && (
            <section className="landing">
              <h2>Was soll ich fuer dich erledigen?</h2>
              <p>Das Design stammt aus deiner ui.html und laeuft jetzt als Next.js Frontend.</p>

              <div className="query">
                <SourceBadge source={source} />
                <textarea
                  className="input"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Welche Termine habe ich morgen?"
                />
                <div className="actions-row">
                  <button className="btn btn-primary" onClick={() => sendMessage(prompt)} disabled={isThinking}>
                    Fragen
                  </button>
                </div>
              </div>

              <div className="chips">
                {SUGGESTIONS.map((item) => (
                  <button key={item} className="chip" onClick={() => setPrompt(item)}>{item}</button>
                ))}
              </div>
            </section>
          )}

          {showConversation && (
            <section className="conversation">
              <div className="messages">
                <div className="messages-inner">
                  {messages.map((msg, idx) => (
                    <div className={`msg-row ${msg.role}`} key={`${msg.role}-${idx}`}>
                      <div className="bubble">{msg.content}</div>
                    </div>
                  ))}
                  {isThinking && (
                    <div className="msg-row assistant">
                      <div className="bubble">Denke nach...</div>
                    </div>
                  )}
                </div>
              </div>

              <div className="composer">
                <div className="composer-row">
                  <div className="prompt-col">
                    <SourceBadge source={source} />
                    <textarea
                      className="input"
                      value={prompt}
                      onChange={(e) => setPrompt(e.target.value)}
                      placeholder="Nachricht schreiben..."
                    />
                  </div>
                  <button className="btn btn-primary send-btn" onClick={() => sendMessage(prompt)} disabled={isThinking}>
                    {isThinking ? "..." : "➤"}
                  </button>
                </div>
              </div>
            </section>
          )}

          {error && <div className="error-box">{error}</div>}
        </div>
      </main>
    </>
  );
}
