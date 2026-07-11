'use client';

import { useState, useEffect } from 'react';
import { apiFetch, getApiBase } from '../../lib/api';
import './login.css';

const TOKEN_KEY = 'mynd_token_v1';

export default function LoginPage() {
  const [loginUser, setLoginUser] = useState('');
  const [loginPass, setLoginPass] = useState('');
  const [loginError, setLoginError] = useState('');
  const [loading, setLoading] = useState(false);
  const [backendUrl, setBackendUrl] = useState('http://127.0.0.1:5001');
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem('backendUrl');
      if (stored) setBackendUrl(stored);
    } catch {}
  }, []);

  const submitCredentials = async (e) => {
    e.preventDefault();
    setLoading(true);
    setLoginError('');
    try {
      const resp = await apiFetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: loginUser, password: loginPass })
      });
      const data = await resp.json();
      if (resp.ok && data.token) {
        try { localStorage.setItem(TOKEN_KEY, data.token); } catch {}
        window.location.href = '/';
        return;
      }
      setLoginError((data && data.error) ? String(data.error) : 'Login fehlgeschlagen');
    } catch (err) {
      setLoginError('Netzwerkfehler – Backend nicht erreichbar');
    }
    setLoading(false);
  };

  const changeBackendUrl = (url) => {
    setBackendUrl(url);
    try { localStorage.setItem('backendUrl', url); } catch {}
  };

  return (
    <div className="login-page">
      <div className="login-bg" />
      <div className="login-card">
        <div className="login-header">
          <div className="login-logo">◆</div>
          <h1>MYND</h1>
          <p className="login-subtitle">Melde dich an, um fortzufahren</p>
        </div>

        <form onSubmit={submitCredentials} className="login-form">
          <div className="login-field">
            <label htmlFor="login-user">Benutzername</label>
            <input
              id="login-user"
              value={loginUser}
              onChange={(e) => setLoginUser(e.target.value)}
              placeholder="Benutzername"
              autoFocus
            />
          </div>
          <div className="login-field">
            <label htmlFor="login-pass">Passwort</label>
            <input
              id="login-pass"
              value={loginPass}
              onChange={(e) => setLoginPass(e.target.value)}
              placeholder="Passwort"
              type="password"
            />
          </div>
          <button type="submit" className="login-btn" disabled={loading || !loginUser || !loginPass}>
            {loading ? 'Anmelden...' : 'Anmelden'}
          </button>
          {loginError && <div className="login-error">{loginError}</div>}
        </form>

        <div className="login-footer">
          <button className="login-details-toggle" onClick={() => setShowDetails(!showDetails)}>
            Server-Verbindung
          </button>
          {showDetails && (
            <div className="login-details">
              <input
                type="text"
                value={backendUrl}
                onChange={(e) => changeBackendUrl(e.target.value)}
                placeholder="http://127.0.0.1:5001"
              />
              <small>Adresse des lokalen Backend-Servers</small>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
