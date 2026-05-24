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
  const [setupStatus, setSetupStatus] = useState(null);
  const [setupMode, setSetupMode] = useState('');
  const [setupSubmitting, setSetupSubmitting] = useState(false);
  const [setupMessage, setSetupMessage] = useState('');
  const [setupError, setSetupError] = useState('');
  const [setupForm, setSetupForm] = useState({
    adminName: '',
    adminPassword: '',
    clientId: '',
    clientSecret: '',
    nextcloudUrl: ''
  });

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
    if (!ready) return;
    fetch('/api/setup/status')
      .then((r) => r.json())
      .then((data) => {
        if (data && data.success) {
          setSetupStatus(data);
          if (data.needs_setup) {
            setSetupMode((current) => current || 'admin');
            setSetupForm((current) => ({
              ...current,
              adminName: current.adminName || data.admin_user || 'admin'
            }));
          }
        }
      })
      .catch(() => {});
  }, [ready]);

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

  const submitBootstrap = async (ev) => {
    ev.preventDefault();
    setSetupError('');
    setSetupMessage('');
    setSetupSubmitting(true);
    try {
      const payload = {
        mode: setupMode,
        admin_name: setupForm.adminName,
        admin_password: setupForm.adminPassword,
        client_id: setupForm.clientId,
        client_secret: setupForm.clientSecret,
        nextcloud_url: setupForm.nextcloudUrl
      };
      const resp = await fetch('/api/setup/bootstrap', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();
      if (!resp.ok || !data.success) {
        setSetupError((data && data.error) ? String(data.error) : 'Setup fehlgeschlagen');
        return;
      }

      if (data.admin_created) {
        setSetupMessage('Admin wurde angelegt. Danach bitte mit dem lokalen Login anmelden.');
        setLoginUser(setupStatus?.admin_user || 'admin');
        setSetupMode('');
      } else if (data.oauth_configured) {
        setSetupMessage('Nextcloud OAuth wurde gespeichert. Du kannst jetzt die Nextcloud-Anmeldung benutzen.');
        setShowNcForm(true);
        setSetupMode('');
      }

      try {
        const statusResp = await fetch('/api/setup/status');
        const statusData = await statusResp.json();
        if (statusData && statusData.success) setSetupStatus(statusData);
      } catch (err) {}
    } catch (err) {
      setSetupError('Netzwerkfehler');
    } finally {
      setSetupSubmitting(false);
    }
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

  const redirectUri = typeof window !== 'undefined'
    ? `${window.location.origin}/api/auth/nextcloud/callback`
    : '/api/auth/nextcloud/callback';

  const nextcloudHint = [
    'In Nextcloud als Admin eine OAuth2-App anlegen oder die vorhandene OAuth2-Funktion nutzen.',
    'Die Callback-URL in der Nextcloud-App muss exakt auf die unten angezeigte Redirect-URI zeigen.',
    'Danach Client ID und Client Secret hier eintragen und speichern.'
  ];
  const setupPanelVisible = Boolean(setupStatus?.needs_setup) || setupMode === 'admin' || setupMode === 'nextcloud';

  return (
    <div className="auth-overlay">
      <div className="auth-card">
        <div className="auth-header">
          <div>
            <h1 className="auth-title">Willkommen bei MYND</h1>
            <p className="auth-sub">Um Mynd gemeinsam zu nutzen, gib bitte deinen Namen ein oder melde dich an.</p>
          </div>
        </div>

        {setupPanelVisible ? (
          <div className="setup-panel">
            <div className="setup-panel-head">
              <div>
                <h2 className="setup-title">Ersteinrichtung</h2>
                <p className="setup-subtitle">Wähle zuerst, ob du das lokale Admin-Konto initialisieren oder Nextcloud OAuth konfigurieren willst.</p>
              </div>
              <div className="setup-actions">
                {setupStatus?.needs_setup ? <button type="button" className={`btn ${setupMode === 'admin' ? 'btn-primary' : ''}`} onClick={() => setSetupMode('admin')}>Admin-Konto</button> : null}
                <button type="button" className={`btn ${setupMode === 'nextcloud' ? 'btn-primary' : ''}`} onClick={() => setSetupMode('nextcloud')}>Nextcloud OAuth</button>
                {!setupStatus?.needs_setup ? <button type="button" className="btn" onClick={() => setSetupMode('')}>Schließen</button> : null}
              </div>
            </div>

            {setupMode === 'admin' ? (
              <form onSubmit={submitBootstrap} className="setup-form">
                <div className="setup-grid">
                  <label className="setup-field">
                    <span>Admin-Benutzer</span>
                    <input value={setupStatus?.admin_user || 'admin'} disabled />
                  </label>
                  <label className="setup-field">
                    <span>Admin-Passwort</span>
                    <input type="password" value={setupForm.adminPassword} onChange={(e) => setSetupForm((current) => ({ ...current, adminPassword: e.target.value }))} placeholder="Neues Admin-Passwort" />
                  </label>
                  <label className="setup-field setup-wide">
                    <span>Anzeigename</span>
                    <input value={setupForm.adminName} onChange={(e) => setSetupForm((current) => ({ ...current, adminName: e.target.value }))} placeholder="z. B. Systemadmin" />
                  </label>
                </div>
                <div className="setup-note">Dieses Konto wird als erster lokaler Administrator angelegt. Danach kannst du dich normal im Login anmelden.</div>
                <div className="setup-footer">
                  <button type="submit" className="btn btn-success" disabled={setupSubmitting}>Admin anlegen</button>
                </div>
              </form>
            ) : null}

            {setupMode === 'nextcloud' ? (
              <form onSubmit={submitBootstrap} className="setup-form">
                <div className="setup-grid">
                  <label className="setup-field setup-wide">
                    <span>Nextcloud URL</span>
                    <input value={setupForm.nextcloudUrl} onChange={(e) => setSetupForm((current) => ({ ...current, nextcloudUrl: e.target.value }))} placeholder="https://cloud.example.org" />
                  </label>
                  <label className="setup-field">
                    <span>Client ID</span>
                    <input value={setupForm.clientId} onChange={(e) => setSetupForm((current) => ({ ...current, clientId: e.target.value }))} placeholder="Client ID" />
                  </label>
                  <label className="setup-field">
                    <span>Client Secret</span>
                    <input value={setupForm.clientSecret} onChange={(e) => setSetupForm((current) => ({ ...current, clientSecret: e.target.value }))} placeholder="Client Secret" />
                  </label>
                </div>

                <div className="setup-hints">
                  {nextcloudHint.map((item) => <div key={item} className="setup-hint-item">{item}</div>)}
                </div>

                <div className="setup-redirect">
                  <span className="setup-redirect-label">Redirect-URI</span>
                  <code className="setup-redirect-code">{redirectUri}</code>
                </div>

                <div className="setup-note">Speichern aktiviert die Nextcloud-Anmeldung direkt im Webinterface. Falls du zusätzlich einen lokalen Admin brauchst, richte zuerst das Admin-Konto ein.</div>

                <div className="setup-footer">
                  <button type="submit" className="btn btn-nc" disabled={setupSubmitting}>Nextcloud speichern</button>
                </div>
              </form>
            ) : null}

            {setupMessage ? <div className="setup-message success">{setupMessage}</div> : null}
            {setupError ? <div className="setup-message error">{setupError}</div> : null}
          </div>
        ) : null}

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
          <div style={{marginTop:10, display:'flex', gap:8, flexWrap:'wrap'}}>
            <button type="button" className="btn btn-nc" onClick={() => setSetupMode('nextcloud')}>Nextcloud OAuth einrichten</button>
            {setupStatus?.needs_setup ? <button type="button" className="btn" onClick={() => setSetupMode('admin')}>Lokales Admin-Konto initialisieren</button> : null}
          </div>
        </div>
      </div>
    </div>
  );
}
