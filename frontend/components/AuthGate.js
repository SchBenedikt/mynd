"use client";

import { useEffect, useState, useRef } from "react";
import { usePathname, useRouter } from 'next/navigation';
import './AuthGate.css';

const TOKEN_KEY = 'mynd_token_v1';
const SETUP_FLOW_KEY = 'mynd_setup_flow_v1';

export default function AuthGate({ children }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [setupRequired, setSetupRequired] = useState(false);
  const [authMode, setAuthMode] = useState('local');
  const [nextcloudUrl, setNextcloudUrl] = useState('');
  const [user, setUser] = useState(null);
  const [loginUser, setLoginUser] = useState('');
  const [loginPass, setLoginPass] = useState('');
  const [loginError, setLoginError] = useState('');
  const [forceOpen, setForceOpen] = useState(false);
  const [setupFlowActive, setSetupFlowActive] = useState(false);
  const [showLocalLogin, setShowLocalLogin] = useState(false);
  const lastReplaceRef = useRef(0);
  const [setupStatusRefresh, setSetupStatusRefresh] = useState(0);

  const guardedReplace = (url) => {
    const now = Date.now();
    if (now - lastReplaceRef.current < 2000) return;
    lastReplaceRef.current = now;
    router.replace(url);
  };

  useEffect(() => {
    let cancelled = false;
    try {
      try { localStorage.removeItem('mynd_user_v1'); } catch (err) {}
      fetch('/api/auth/me')
        .then((r) => r.json())
        .then((data) => {
          if (data && data.authenticated && data.user) {
            setUser({ name: data.user.name, username: data.user.username });
          }
        })
        .catch(() => {});

      try {
        const params = new URLSearchParams(window.location.search);
        const err = params.get('error') || params.get('auth_error');
        if (err) setLoginError(decodeURIComponent(err));
      } catch (e) {}

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

        fetch('/api/setup/status')
          .then((r) => r.json())
          .then((data) => {
            if (cancelled) return;
            const needsSetup = Boolean(data && data.success && data.needs_setup);
            const oauthConfigured = Boolean(data && data.success && data.oauth_configured && data.nextcloud_url);
            setSetupRequired(needsSetup);
            setAuthMode(oauthConfigured ? 'nextcloud' : 'local');
            setNextcloudUrl(String(data && data.nextcloud_url ? data.nextcloud_url : '').trim());
            try {
              setSetupFlowActive(Boolean(sessionStorage.getItem(SETUP_FLOW_KEY)));
            } catch (err) {
              setSetupFlowActive(false);
            }
            if (needsSetup && pathname !== '/setup') {
              guardedReplace('/setup');
            }
          })
          .catch(() => {});
    } catch (err) {}
    setReady(true);

      return () => {
        cancelled = true;
      };
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (setupRequired && pathname !== '/setup') {
      guardedReplace('/setup');
    }
  }, [ready, pathname, setupRequired]);

  useEffect(() => {
    const openHandler = () => {
      try {
        setForceOpen(true);
        setLoginError('');
        setTimeout(() => {
          const el = document.querySelector('.auth-panel input') || document.querySelector('.auth-panel .btn');
          if (el && typeof el.focus === 'function') el.focus();
        }, 50);
      } catch (e) {}
    };
    window.addEventListener('open-auth', openHandler);
    return () => window.removeEventListener('open-auth', openHandler);
  }, []);

  if (!ready) return null;
  if (setupRequired && pathname !== '/setup') return null;
  if (pathname?.startsWith('/setup') && !setupRequired && !setupFlowActive) return null;
  if (pathname?.startsWith('/setup')) return children;
  if (user && !forceOpen) return children;

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

  const startNextcloudFlow = () => {
    const redirect = window.location.origin + window.location.pathname;
    const loginUrl = `/api/auth/nextcloud/login?redirect_to=${encodeURIComponent(redirect)}`;
    window.location.assign(loginUrl);
  };

  const displayUrl = (url) => {
    try {
      return url.replace(/^https?:\/\//, '');
    } catch (e) { return url; }
  };

  return (
    <div className="auth-overlay">
      <div className="auth-card">
        <div className="auth-body">
          <div className="auth-intro">
            <div className="auth-badge">
              <span>MYND</span>
            </div>
            <h1>Willkommen zurück</h1>
            <p className="auth-sub">
              Melde dich an, um auf deine persönliche KI-Umgebung zuzugreifen.
            </p>
            <div className="auth-features">
              <div className="auth-feature">
                <div className="auth-feature-icon">🧠</div>
                <div className="auth-feature-text">
                  <strong>KI-gestützte Suche</strong>
                  Durchsuche deine Dokumente, E-Mails und Chatverläufe mit semantischer Suche.
                </div>
              </div>
              <div className="auth-feature">
                <div className="auth-feature-icon">☁️</div>
                <div className="auth-feature-text">
                  <strong>Nextcloud Integration</strong>
                  Verbinde deine Nextcloud für kalender-, Aufgaben- und Datei-Zugriff.
                </div>
              </div>
              <div className="auth-feature">
                <div className="auth-feature-icon">🔒</div>
                <div className="auth-feature-text">
                  <strong>Lokal & Privat</strong>
                  Deine Daten bleiben auf deinem Server – keine Cloud-Abhängigkeit.
                </div>
              </div>
            </div>
          </div>

          <div className="auth-panel-wrap">
            <div className="auth-panel">
              {authMode === 'nextcloud' && !showLocalLogin ? (
                <>
                  <h2 className="auth-panel-title">Nextcloud Login</h2>
                  <p className="auth-panel-desc">
                    Melde dich mit deinem Nextcloud-Konto an, um alle integrierten Funktionen zu nutzen.
                  </p>
                  <div className="panel-form">
                    <div className="nc-chip">
                      <span className="nc-icon">☁️</span>
                      <span>{displayUrl(nextcloudUrl)}</span>
                    </div>
                    <button type="button" className="btn btn-nc" onClick={startNextcloudFlow}>
                      <span>→</span>
                      Mit Nextcloud anmelden
                    </button>
                    <div className="auth-switch">
                      <button type="button" onClick={() => setShowLocalLogin(true)}>
                        Stattdessen mit lokalem Konto anmelden
                      </button>
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <h2 className="auth-panel-title">Lokaler Login</h2>
                  <p className="auth-panel-desc">
                    Melde dich mit deinem lokalen Benutzerkonto an.
                  </p>
                  <form onSubmit={submitCredentials} className="panel-form">
                    <label htmlFor="auth-user">Benutzername</label>
                    <input id="auth-user" value={loginUser} onChange={(e) => setLoginUser(e.target.value)} placeholder="Benutzername" autoFocus />
                    <label htmlFor="auth-pass">Passwort</label>
                    <input id="auth-pass" value={loginPass} onChange={(e) => setLoginPass(e.target.value)} placeholder="Passwort" type="password" />
                    <button type="submit" className="btn btn-success">Anmelden</button>
                    {authMode === 'nextcloud' && (
                      <div className="auth-switch">
                        <button type="button" onClick={() => setShowLocalLogin(false)}>
                          Zurück zu Nextcloud-Login
                        </button>
                      </div>
                    )}
                  </form>
                </>
              )}
              {loginError ? <div className="auth-error">{loginError}</div> : null}
            </div>
          </div>
        </div>

        <div className="auth-footer">
          <small>Die Anmeldung erfolgt ausschließlich auf deinem lokalen Server. Es werden keine Daten an Dritte weitergegeben.</small>
        </div>
      </div>
    </div>
  );
}
