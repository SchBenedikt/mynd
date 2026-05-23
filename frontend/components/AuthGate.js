"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = 'mynd_user_v1';
const TOKEN_KEY = 'mynd_token_v1';

export default function AuthGate({ children }) {
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState(null);
  const [name, setName] = useState('');
  const [loginUser, setLoginUser] = useState('');
  const [loginPass, setLoginPass] = useState('');
  const [loginError, setLoginError] = useState('');

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setUser(JSON.parse(raw));
      // Try server-side cookie-based session first
      try {
        fetch('/api/auth/me')
          .then((r) => r.json())
          .then((data) => {
            if (data && data.authenticated && data.user) {
              setUser({ name: data.user.name, username: data.user.username });
            }
          })
          .catch(() => {});
      } catch (err) {
        // ignore
      }
      // If redirected back from OAuth with token in fragment (#token=...), capture it
      try {
        if (typeof window !== 'undefined' && window.location && window.location.hash) {
          const hash = window.location.hash.replace(/^#/, '');
          const parts = new URLSearchParams(hash);
          const fragToken = parts.get('token') || parts.get('access_token');
          if (fragToken) {
            localStorage.setItem(TOKEN_KEY, fragToken);
            // clean fragment
            try {
              window.history.replaceState({}, document.title, window.location.pathname + window.location.search);
            } catch (err) {}
            // validate and set user
            fetch('/api/auth/me', { headers: { 'Authorization': `Bearer ${fragToken}` } })
              .then((r) => r.json())
              .then((data) => {
                if (data && data.authenticated && data.user) {
                  setUser({ name: data.user.name, username: data.user.username, token: fragToken });
                }
              })
              .catch(() => {});
          }
        }
      } catch (err) {
        // ignore fragment parsing errors
      }
    } catch (err) {
      // ignore
    }
    setReady(true);
  }, []);

  if (!ready) return null;

  if (user) {
    return children;
  }

  const submit = (ev) => {
    ev.preventDefault();
    const finalName = (String(name || '').trim()) || 'Gast';
    const payload = { name: finalName, createdAt: Date.now() };
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
    } catch (err) {
      console.error('Could not persist user:', err);
    }
    setUser(payload);
  };

  const submitCredentials = async (ev) => {
    ev && ev.preventDefault();
    setLoginError('');
    try {
      const resp = await fetch('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: loginUser, password: loginPass }) });
      const data = await resp.json();
      if (resp.ok) {
        // server sets HttpOnly cookie; fetch /api/auth/me to get user
        try {
          const me = await fetch('/api/auth/me');
          const meData = await me.json();
          if (me.ok && meData.authenticated) {
            setUser({ name: meData.user.name, username: meData.user.username });
            return;
          }
        } catch (err) {
          // fallback to returned user info
          setUser({ name: data.user?.name || loginUser, username: data.user?.username || loginUser });
          return;
        }
      }
      setLoginError((data && data.error) ? String(data.error) : 'Login fehlgeschlagen');
    } catch (err) {
      setLoginError('Netzwerkfehler');
    }
  };

  const loginNextcloud = () => {
    // ask for domain like indexing flow, then redirect to backend OAuth start
    const domain = window.prompt('Nextcloud-Domain (inkl. https://), z.B. https://cloud.example.org');
    if (!domain) return;
    const redirect = window.location.origin + window.location.pathname;
    const url = `/api/auth/nextcloud/login?nextcloud_url=${encodeURIComponent(domain)}&redirect_to=${encodeURIComponent(redirect)}`;
    window.location.assign(url);
  };

  return (
    <div style={{position: 'fixed', inset: 0, background: 'rgba(10,10,10,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999}}>
      <div style={{width: 'min(720px, 94%)', background: 'white', borderRadius: 12, padding: 28, boxShadow: '0 10px 30px rgba(0,0,0,0.25)'}}>
        <h1 style={{margin: '0 0 8px 0'}}>Willkommen bei MYND</h1>
        <p style={{marginTop: 0, color: '#444'}}>Um Mynd gemeinsam zu nutzen, gib bitte deinen Namen ein oder melde dich an.</p>

        <div style={{display: 'flex', gap: 12, marginTop: 16}}>
          <form onSubmit={submit} style={{display: 'flex', gap: 8, flex: 1}}>
            <input aria-label="Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Dein Name (Gast)" style={{flex: 1, padding: '10px 12px', borderRadius: 8, border: '1px solid #ddd'}} />
            <button type="submit" style={{padding: '10px 14px', borderRadius: 8, border: 'none', background: '#2f63ff', color: 'white'}}>Als Gast</button>
          </form>

          <div style={{width: 1, background: '#eee'}} />

          <div style={{width: 300}}>
            <form onSubmit={submitCredentials} style={{display: 'flex', flexDirection: 'column', gap: 8}}>
              <input aria-label="Benutzer" value={loginUser} onChange={(e) => setLoginUser(e.target.value)} placeholder="Benutzername" style={{padding: '8px 10px', borderRadius: 6, border: '1px solid #ddd'}} />
              <input aria-label="Passwort" value={loginPass} onChange={(e) => setLoginPass(e.target.value)} placeholder="Passwort" type="password" style={{padding: '8px 10px', borderRadius: 6, border: '1px solid #ddd'}} />
              <button type="submit" style={{padding: '8px 10px', borderRadius: 6, border: 'none', background: '#16a34a', color: 'white'}}>Login</button>
              {loginError ? <div style={{color: 'crimson', fontSize: 13}}>{loginError}</div> : null}
            </form>

            <div style={{display: 'flex', marginTop: 10}}>
              <button onClick={loginNextcloud} style={{flex: 1, padding: '8px 10px', borderRadius: 6, border: 'none', background: '#0b6abf', color: 'white'}}>Mit Nextcloud anmelden</button>
            </div>
          </div>
        </div>

        <div style={{marginTop: 16, fontSize: 13, color: '#666'}}>
          <p style={{margin: 0}}>Hinweis: Dies ist eine einfache lokale Anmeldung. Für echten Mehrbenutzer-Betrieb sollte ein Backend-gestütztes Authentifizierungsverfahren (z. B. OAuth, NextAuth oder JWT) eingerichtet werden.</p>
        </div>
      </div>
    </div>
  );
}
