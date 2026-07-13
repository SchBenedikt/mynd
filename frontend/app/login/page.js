'use client';

import { useState, useEffect } from 'react';
import { apiFetch } from '../../lib/api';
import './login.css';

const TOKEN_KEY = 'mynd_token_v1';

function Spinner() {
  return <span className="login-btn-spinner" />;
}

export default function LoginPage() {
  const [loginUser, setLoginUser] = useState('');
  const [loginPass, setLoginPass] = useState('');
  const [loginPassConfirm, setLoginPassConfirm] = useState('');
  const [loginName, setLoginName] = useState('');
  const [loginError, setLoginError] = useState('');
  const [loginSuccess, setLoginSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState('login');
  const [registrationAllowed, setRegistrationAllowed] = useState(false);
  const [backendUrl, setBackendUrl] = useState('http://127.0.0.1:5001');
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem('backendUrl');
      if (stored) setBackendUrl(stored);
    } catch {}
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    apiFetch('/api/auth/config')
      .then(r => r.json())
      .then(data => {
        if (data?.allowRegistration) setRegistrationAllowed(true);
      })
      .catch(() => {});
  }, []);

  const validate = () => {
    if (!loginUser || !loginPass) return 'Benutzername und Passwort erforderlich';
    if (loginUser.length < 2) return 'Benutzername zu kurz (min. 2 Zeichen)';
    if (tab === 'register') {
      if (loginPass.length < 4) return 'Passwort zu kurz (min. 4 Zeichen)';
      if (loginPass !== loginPassConfirm) return 'Passwörter stimmen nicht überein';
    }
    return '';
  };

  const switchTab = (newTab) => {
    if (newTab === tab) return;
    setTab(newTab);
    setLoginError('');
    setLoginSuccess('');
    setLoginPassConfirm('');
  };

  const submitCredentials = async (e) => {
    e.preventDefault();
    const validationError = validate();
    if (validationError) {
      setLoginError(validationError);
      return;
    }
    setLoading(true);
    setLoginError('');
    setLoginSuccess('');
    try {
      const endpoint = tab === 'register' ? '/api/auth/register' : '/api/auth/login';
      const body = tab === 'register'
        ? { username: loginUser, password: loginPass, name: loginName || loginUser }
        : { username: loginUser, password: loginPass };
      const resp = await apiFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const data = await resp.json();
      if (resp.ok && data.token) {
        try { localStorage.setItem(TOKEN_KEY, data.token); } catch {}
        if (tab === 'register') {
          setLoginSuccess('Account erstellt! Du wirst weitergeleitet...');
          await new Promise(r => setTimeout(r, 800));
        }
        window.location.href = '/';
        return;
      }
      setLoginError((data && data.error) ? String(data.error) : (tab === 'register' ? 'Registrierung fehlgeschlagen' : 'Login fehlgeschlagen'));
    } catch (err) {
      setLoginError('Netzwerkfehler – Backend nicht erreichbar');
    }
    setLoading(false);
  };

  const changeBackendUrl = (url) => {
    setBackendUrl(url);
    try { localStorage.setItem('backendUrl', url); } catch {}
  };

  const isRegister = tab === 'register';
  const canSubmit = !loading && loginUser && loginPass && (!isRegister || loginPassConfirm);

  return (
    <div className="login-page">
      <div className="login-bg" />
      <div className="login-card">
        <div className="login-header">
          <div className="login-logo">◆</div>
          <h1>MYND</h1>
          <p className="login-subtitle">
            {isRegister ? 'Neuen Account erstellen' : 'Melde dich an'}
          </p>
        </div>

        {registrationAllowed && (
          <div className="login-tabs">
            <button
              className={'login-tab' + (tab === 'login' ? ' active' : '')}
              onClick={() => switchTab('login')}
              type="button"
            >
              Anmelden
            </button>
            <button
              className={'login-tab' + (tab === 'register' ? ' active' : '')}
              onClick={() => switchTab('register')}
              type="button"
            >
              Registrieren
            </button>
          </div>
        )}

        <form onSubmit={submitCredentials} className="login-form">
          <div className="login-field">
            <label htmlFor="login-user">Benutzername</label>
            <input
              id="login-user"
              value={loginUser}
              onChange={(e) => setLoginUser(e.target.value)}
              placeholder="Benutzername"
              autoFocus
              autoComplete="username"
            />
          </div>
          {isRegister && (
            <div className="login-field">
              <label htmlFor="login-name">Anzeigename (optional)</label>
              <input
                id="login-name"
                value={loginName}
                onChange={(e) => setLoginName(e.target.value)}
                placeholder="Wie möchtest du angezeigt werden?"
              />
            </div>
          )}
          <div className="login-field">
            <label htmlFor="login-pass">Passwort</label>
            <input
              id="login-pass"
              value={loginPass}
              onChange={(e) => setLoginPass(e.target.value)}
              placeholder="Passwort"
              type="password"
              autoComplete={isRegister ? 'new-password' : 'current-password'}
            />
            {isRegister && loginPass.length > 0 && loginPass.length < 4 && (
              <p className="login-hint">Mindestens 4 Zeichen</p>
            )}
          </div>
          {isRegister && (
            <div className="login-field">
              <label htmlFor="login-pass-confirm">Passwort bestätigen</label>
              <input
                id="login-pass-confirm"
                value={loginPassConfirm}
                onChange={(e) => setLoginPassConfirm(e.target.value)}
                placeholder="Passwort wiederholen"
                type="password"
                autoComplete="new-password"
              />
            </div>
          )}
          <button type="submit" className="login-btn" disabled={!canSubmit}>
            {loading && <Spinner />}
            {loading
              ? (isRegister ? 'Account wird erstellt...' : 'Anmeldung läuft...')
              : (isRegister ? 'Account erstellen' : 'Anmelden')}
          </button>
          {loginError && <div className="login-error">{loginError}</div>}
          {loginSuccess && <div className="login-success">{loginSuccess}</div>}
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
