"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from 'next/navigation';
import './AuthGate.css';

const STORAGE_KEY = 'mynd_user_v1';
const TOKEN_KEY = 'mynd_token_v1';

export default function AuthGate({ children }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState(null);
  const [name, setName] = useState('');
  const [loginUser, setLoginUser] = useState('');
  const [loginPass, setLoginPass] = useState('');
  const [loginError, setLoginError] = useState('');
  const [showNcForm, setShowNcForm] = useState(false);
  const [ncDomain, setNcDomain] = useState('');
  const [forceOpen, setForceOpen] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setUser(JSON.parse(raw));
      fetch('/api/auth/me')
        .then((r) => r.json())
        .then((data) => {
          if (data && data.authenticated && data.user) {
            setUser({ name: data.user.name, username: data.user.username });
          }
        })
        .catch(() => {});

      // handle OAuth error in query params
      try {
        const params = new URLSearchParams(window.location.search);
        const err = params.get('error') || params.get('auth_error');
        if (err) setLoginError(decodeURIComponent(err));
      } catch (e) {}

      // fragment token handling
      try {
        if (typeof window !== 'undefined' && window.location && window.location.hash) {
          const hash = window.location.hash.replace(/^#/, '');
          const parts = new URLSearchParams(hash);
          const fragToken = parts.get('token') || parts.get('access_token');
          if (fragToken) {
            localStorage.setItem(TOKEN_KEY, fragToken);
            try { window.history.replaceState({}, document.title, window.location.pathname + window.location.search); } catch (err) {}
            fetch('/api/auth/me', { headers: { 'Authorization': `Bearer ${fragToken}` } })
              .then((r) => r.json())
              .then((data) => {
                if (data && data.authenticated && data.user) {
                  setUser({ name: data.user.name, username: data.user.username, token: fragToken });
                  setForceOpen(false);
                }
              })
              .catch(() => {});
          }
        }
      } catch (err) {}
    } catch (err) {}
    setReady(true);
  }, []);

  useEffect(() => {
    const openHandler = () => {
      try {
        setForceOpen(true);
        setShowNcForm(false);
        setLoginError('');
        setTimeout(() => {
          const el = document.querySelector('.auth-card input[aria-label="Name"]') || document.querySelector('.auth-card input[aria-label="Benutzer"]');
          if (el && typeof el.focus === 'function') el.focus();
        }, 50);
      } catch (e) {}
    };
    window.addEventListener('open-auth', openHandler);
    return () => window.removeEventListener('open-auth', openHandler);
  }, []);

  if (!ready) return null;
  if (pathname?.startsWith('/setup')) return children;
  if (user && !forceOpen) return children;

  const submit = (ev) => {
    ev.preventDefault();
    const finalName = (String(name || '').trim()) || 'Gast';
    const payload = { name: finalName, createdAt: Date.now() };
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(payload)); } catch (err) {}
    setUser(payload);
    setForceOpen(false);
  };

  const submitCredentials = async (ev) => {
    ev && ev.preventDefault();
    setLoginError('');
    try {
      const resp = await fetch('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: loginUser, password: loginPass }) });
      const data = await resp.json();
      if (resp.ok) {
        try {
          const me = await fetch('/api/auth/me');
          const meData = await me.json();
          if (me.ok && meData.authenticated) { setUser({ name: meData.user.name, username: meData.user.username }); setForceOpen(false); return; }
        } catch (err) { setUser({ name: data.user?.name || loginUser, username: data.user?.username || loginUser }); setForceOpen(false); return; }
      }
      setLoginError((data && data.error) ? String(data.error) : 'Login fehlgeschlagen');
    } catch (err) { setLoginError('Netzwerkfehler'); }
  };

  const startNextcloudFlow = (domain) => {
    const redirect = window.location.origin + window.location.pathname;
    const loginUrl = `/api/auth/nextcloud/login?nextcloud_url=${encodeURIComponent(domain)}&redirect_to=${encodeURIComponent(redirect)}`;
    const checkUrl = `/api/auth/nextcloud/check?nextcloud_url=${encodeURIComponent(domain)}`;
    // verify backend config first
    fetch(checkUrl).then(async (r) => {
      try {
        const j = await r.json();
        if (r.ok && j && j.success) {
          window.location.assign(loginUrl);
        } else {
          setLoginError(j && j.error ? String(j.error) : 'Nextcloud OAuth nicht konfiguriert');
        }
      } catch (err) {
        setLoginError('Fehler beim Prüfen der Nextcloud-Konfiguration');
      }
    }).catch(() => setLoginError('Fehler beim Prüfen der Nextcloud-Konfiguration'));
  };

  const onNcSubmit = (ev) => {
    ev.preventDefault();
    setLoginError('');
    const domain = String(ncDomain || '').trim();
    if (!domain) { setLoginError('Bitte eine Nextcloud-Domain angeben.'); return; }
    // basic validation
    if (!/^https?:\/\//.test(domain)) { setLoginError('Domain muss mit https:// oder http:// beginnen.'); return; }
    startNextcloudFlow(domain);
  };

  return (
    <div className="auth-overlay">
      <div className="auth-card">
        <div className="auth-header">
          <div className="auth-header-copy">
            <div className="auth-kicker">MYND</div>
            <h1 className="auth-title">Willkommen zurück</h1>
            <p className="auth-sub">Nutze MYND als Gast, mit lokalem Login oder richte die Instanz direkt neu ein.</p>
          </div>
          <div className="auth-header-actions">
            <button type="button" className="btn btn-nc" onClick={() => router.push('/setup?mode=nextcloud')}>Setup öffnen</button>
            <button type="button" className="btn" onClick={() => router.push('/setup')}>Einrichtungsseite</button>
          </div>
        </div>

        <div className="auth-body auth-body-grid">
          <div className="auth-intro">
            <div className="auth-spotlight">
              <div className="auth-spotlight-title">Wähle deinen Einstieg</div>
              <div className="auth-spotlight-text">Gastzugang ist schnell, lokales Login ist dauerhaft, Nextcloud verbindet MYND mit deiner bestehenden Umgebung.</div>
            </div>

            <div className="auth-feature-grid">
              <div className="auth-feature-card">
                <div className="auth-feature-title">Gast</div>
                <p>Direkt loslegen ohne Konto.</p>
              </div>
              <div className="auth-feature-card">
                <div className="auth-feature-title">Login</div>
                <p>Für persönliche Daten und Rechte.</p>
              </div>
              <div className="auth-feature-card">
                <div className="auth-feature-title">Nextcloud</div>
                <p>OAuth und bestehende Infrastruktur nutzen.</p>
              </div>
            </div>

            <div className="auth-callout">
              <div className="auth-callout-title">Erste Installation?</div>
              <p>Öffne die Setup-Seite und richte zuerst Admin oder Nextcloud ein. Danach kehrst du hierher zurück.</p>
            </div>
          </div>

          <div className="auth-panels">
            <div className="auth-panel">
              <div className="panel-badge">Gast</div>
              <form onSubmit={submit} className="panel-form">
                <label className="label">Als Gast starten</label>
                <input aria-label="Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Dein Name" />
                <button type="submit" className="btn btn-primary">Weiter als Gast</button>
              </form>
            </div>

            <div className="auth-panel auth-panel-accent">
              <div className="panel-badge">Login</div>
              <form onSubmit={submitCredentials} className="panel-form">
                <label className="label">Mit Benutzerkonto anmelden</label>
                <input aria-label="Benutzer" value={loginUser} onChange={(e) => setLoginUser(e.target.value)} placeholder="Benutzername" />
                <input aria-label="Passwort" value={loginPass} onChange={(e) => setLoginPass(e.target.value)} placeholder="Passwort" type="password" />
                <button type="submit" className="btn btn-success">Anmelden</button>
                {loginError ? <div className="error">{loginError}</div> : null}
              </form>

              <div className="nc-block">
                {!showNcForm ? (
                  <button className="btn btn-nc" onClick={() => setShowNcForm(true)}>Mit Nextcloud anmelden</button>
                ) : (
                  <form onSubmit={onNcSubmit} className="nc-form">
                    <input aria-label="Nextcloud-Domain" value={ncDomain} onChange={(e) => setNcDomain(e.target.value)} placeholder="https://cloud.example.org" />
                    <div style={{display:'flex',gap:8}}>
                      <button type="submit" className="btn btn-nc">Weiter</button>
                      <button type="button" className="btn" onClick={() => setShowNcForm(false)}>Abbrechen</button>
                    </div>
                  </form>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="auth-footer">
          <small>Für die Ersteinrichtung nutze die Setup-Seite. Danach kannst du hier zwischen Gast, Login und Nextcloud wechseln.</small>
          <div style={{marginTop:10, display:'flex', gap:8, flexWrap:'wrap'}}>
            <button type="button" className="btn btn-nc" onClick={() => router.push('/setup?mode=nextcloud')}>Nextcloud OAuth einrichten</button>
            <button type="button" className="btn" onClick={() => router.push('/setup?mode=admin')}>Admin einrichten</button>
          </div>
        </div>
      </div>
    </div>
  );
}
