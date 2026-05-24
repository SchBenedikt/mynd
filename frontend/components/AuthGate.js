"use client";

import { useEffect, useState } from "react";
import './AuthGate.css';

const STORAGE_KEY = 'mynd_user_v1';
const TOKEN_KEY = 'mynd_token_v1';

export default function AuthGate({ children }) {
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
          <div>
            <h1 className="auth-title">Willkommen bei MYND</h1>
            <p className="auth-sub">Um Mynd gemeinsam zu nutzen, gib bitte deinen Namen ein oder melde dich an.</p>
          </div>
        </div>

        <div className="auth-body">
          <div className="guest-col">
            <form onSubmit={submit} className="guest-form">
              <label className="label">Als Gast</label>
              <input aria-label="Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Dein Name (Gast)" />
              <button type="submit" className="btn btn-primary">Weiter als Gast</button>
            </form>
          </div>

          <div className="divider-vertical" />

          <div className="login-col">
            <form onSubmit={submitCredentials} className="login-form">
              <label className="label">Login</label>
              <input aria-label="Benutzer" value={loginUser} onChange={(e) => setLoginUser(e.target.value)} placeholder="Benutzername" />
              <input aria-label="Passwort" value={loginPass} onChange={(e) => setLoginPass(e.target.value)} placeholder="Passwort" type="password" />
              <button type="submit" className="btn btn-success">Login</button>
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

        <div className="auth-footer">
          <small>Das Backend unterstützt serverseitige Authentifizierung (JWT + Nextcloud OAuth). Verwende "Login" oder "Mit Nextcloud anmelden"; Admin-Einstellungen findest du in der Admin-UI.</small>
        </div>
      </div>
    </div>
  );
}
