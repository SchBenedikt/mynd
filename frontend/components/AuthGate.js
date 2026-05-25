"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from 'next/navigation';
import './AuthGate.css';

const TOKEN_KEY = 'mynd_token_v1';

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

        fetch('/api/setup/status')
          .then((r) => r.json())
          .then((data) => {
            if (cancelled) return;
            const needsSetup = Boolean(data && data.success && data.needs_setup);
              const oauthConfigured = Boolean(data && data.success && data.oauth_configured && data.nextcloud_url);
            setSetupRequired(needsSetup);
              setAuthMode(oauthConfigured ? 'nextcloud' : 'local');
              setNextcloudUrl(String(data && data.nextcloud_url ? data.nextcloud_url : '').trim());
            if (needsSetup && pathname !== '/setup') {
              router.replace('/setup');
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
      router.replace('/setup');
      return;
    }
    if (!setupRequired && pathname?.startsWith('/setup')) {
      router.replace('/');
    }
  }, [ready, pathname, router, setupRequired]);

  useEffect(() => {
    const openHandler = () => {
      try {
        setForceOpen(true);
        setLoginError('');
        setTimeout(() => {
          const el = document.querySelector('.auth-card input[aria-label="Benutzer"]') || document.querySelector('.auth-card button.btn-success');
          if (el && typeof el.focus === 'function') el.focus();
        }, 50);
      } catch (e) {}
    };
    window.addEventListener('open-auth', openHandler);
    return () => window.removeEventListener('open-auth', openHandler);
  }, []);

  if (!ready) return null;
  if (setupRequired && pathname !== '/setup') return null;
  if (pathname?.startsWith('/setup') && !setupRequired) return null;
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

  return (
    <div className="auth-overlay">
      <div className="auth-card">
        <div className="auth-header">
          <div className="auth-header-copy">
            <div className="auth-kicker">MYND</div>
            <h1 className="auth-title">Willkommen zurück</h1>
            <p className="auth-sub">{authMode === 'nextcloud' ? 'Melde dich mit deinem Nextcloud-Konto an.' : 'Melde dich mit deinem lokalen Konto an.'}</p>
          </div>
        </div>

        <div className="auth-body auth-body-grid auth-body-single">
          <div className="auth-panel auth-panel-accent auth-panel-login">
            <div className="panel-badge">Login</div>
            {authMode === 'nextcloud' ? (
              <div className="panel-form">
                <div className="login-mode-chip">Nextcloud{nextcloudUrl ? ` · ${nextcloudUrl}` : ''}</div>
                <p className="auth-single-copy">Die Anmeldung erfolgt über deine konfigurierte Nextcloud-Instanz.</p>
                <button type="button" className="btn btn-nc" onClick={startNextcloudFlow}>Mit Nextcloud anmelden</button>
              </div>
            ) : (
              <form onSubmit={submitCredentials} className="panel-form">
                <label className="label">Mit Benutzerkonto anmelden</label>
                <input aria-label="Benutzer" value={loginUser} onChange={(e) => setLoginUser(e.target.value)} placeholder="Benutzername" />
                <input aria-label="Passwort" value={loginPass} onChange={(e) => setLoginPass(e.target.value)} placeholder="Passwort" type="password" />
                <button type="submit" className="btn btn-success">Anmelden</button>
              </form>
            )}
            {loginError ? <div className="error">{loginError}</div> : null}
          </div>
        </div>

        <div className="auth-footer">
          <small>{authMode === 'nextcloud' ? 'Die Anmeldung erfolgt über Nextcloud.' : 'Die Anmeldung erfolgt über dein lokales Benutzerkonto.'}</small>
        </div>
      </div>
    </div>
  );
}
