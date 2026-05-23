"use client";

import './admin.css';
import { useEffect, useState } from 'react';

export default function AdminPage() {
  const [users, setUsers] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [oauthCfg, setOauthCfg] = useState({ client_id: null, has_secret: false, nextcloud_url: '' });
  const [oauthClientId, setOauthClientId] = useState('');
  const [oauthClientSecret, setOauthClientSecret] = useState('');
  const [oauthNextcloudUrl, setOauthNextcloudUrl] = useState('');
  const [oauthMessage, setOauthMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [newUser, setNewUser] = useState({ username: '', password: '', name: '' });
  const [resetUser, setResetUser] = useState({ username: '', password: '' });
  const [message, setMessage] = useState('');
  const [rotateKeyValue, setRotateKeyValue] = useState('');

  useEffect(() => {
    fetch('/api/admin/users')
      .then((r) => r.json())
      .then((data) => {
        if (data && data.success) setUsers(data.users || []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
    // load nextcloud accounts
    fetch('/api/admin/nextcloud/accounts')
      .then((r) => r.json())
      .then((data) => {
        if (data && data.success) setAccounts(data.accounts || []);
      })
      .catch(() => {});
    // load oauth config
    fetch('/api/admin/nextcloud/config')
      .then((r) => r.json())
      .then((data) => {
        if (data && data.success) {
          setOauthCfg({ client_id: data.client_id || null, has_secret: !!data.has_secret, nextcloud_url: data.nextcloud_url || '' });
          setOauthClientId(data.client_id || '');
          setOauthNextcloudUrl(data.nextcloud_url || '');
        }
      })
      .catch(() => {});
  }, []);

  const createUser = async (e) => {
    e.preventDefault();
    setMessage('');
    try {
      const res = await fetch('/api/admin/users/create', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(newUser) });
      const data = await res.json();
      if (res.ok && data.success) {
        setMessage('Benutzer angelegt');
        setUsers((s) => [...s, data.user]);
      } else {
        setMessage(data.error || 'Fehler');
      }
    } catch (err) {
      setMessage('Netzwerkfehler');
    }
  };

  const resetPassword = async (e) => {
    e.preventDefault();
    setMessage('');
    try {
      const res = await fetch('/api/admin/users/reset', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(resetUser) });
      const data = await res.json();
      if (res.ok && data.success) {
        setMessage('Passwort zurückgesetzt');
      } else {
        setMessage(data.error || 'Fehler');
      }
    } catch (err) {
      setMessage('Netzwerkfehler');
    }
  };

  const deleteUser = async (username) => {
    setMessage('');
    try {
      const res = await fetch('/api/admin/users/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username }) });
      const data = await res.json();
      if (res.ok && data.success) {
        setMessage('Benutzer gelöscht');
        setUsers((s) => s.filter((u) => u.username !== username));
      } else {
        setMessage(data.error || 'Fehler');
      }
    } catch (err) { setMessage('Netzwerkfehler'); }
  };

  const deleteAccount = async (key) => {
    setMessage('');
    try {
      const res = await fetch('/api/admin/nextcloud/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ key }) });
      const data = await res.json();
      if (res.ok && data.success) {
        setMessage('Account gelöscht');
        setAccounts((s) => s.filter((a) => a.key !== key));
      } else { setMessage(data.error || 'Fehler'); }
    } catch (err) { setMessage('Netzwerkfehler'); }
  };

  const rotateKey = async (e) => {
    e.preventDefault();
    setMessage('');
    try {
      const res = await fetch('/api/admin/nextcloud/rotate_key', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ new_key: rotateKeyValue }) });
      const data = await res.json();
      if (res.ok && data.success) setMessage('Key rotiert'); else setMessage(data.error || 'Fehler');
    } catch (err) { setMessage('Netzwerkfehler'); }
  };

  const saveOauthConfig = async (e) => {
    e.preventDefault();
    setOauthMessage('');
    try {
      const res = await fetch('/api/admin/nextcloud/config', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ client_id: oauthClientId, client_secret: oauthClientSecret, nextcloud_url: oauthNextcloudUrl }) });
      const data = await res.json();
      if (res.ok && data.success) {
        setOauthMessage('OAuth-Konfiguration gespeichert');
        setOauthClientSecret('');
        setOauthCfg((s) => ({ ...s, client_id: oauthClientId, has_secret: true, nextcloud_url: oauthNextcloudUrl }));
      } else {
        setOauthMessage(data.error || 'Fehler');
      }
    } catch (err) {
      setOauthMessage('Netzwerkfehler');
    }
  };

  return (
    <div className="admin-container">
      <h2 className="admin-title">Admin: Benutzerverwaltung</h2>
      <p className="admin-subtitle">Verwalte lokale Benutzer und gespeicherte Nextcloud-Accounts. Nur <code>ADMIN_USER</code> kann diese Seite nutzen.</p>

      <div className="admin-grid">
        <div className="card">
          <h3>Bestehende Nutzer</h3>
          {loading ? <div>lade...</div> : (
            <div>
              <ul className="user-list">
                {users.map((u) => (
                  <li key={u.username} className="user-item">
                    <div className="user-meta">{u.username} <span className="muted">— {u.name}</span></div>
                    <div><button className="btn btn-danger" onClick={() => { if (confirm('Benutzer wirklich löschen?')) deleteUser(u.username); }}>Löschen</button></div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="divider" />

          <div className="forms-row">
            <form onSubmit={createUser} className="form-vertical">
              <h4>Neuen Nutzer anlegen</h4>
              <input placeholder="Benutzername" value={newUser.username} onChange={(e) => setNewUser({...newUser, username: e.target.value})} />
              <input placeholder="Anzeigename" value={newUser.name} onChange={(e) => setNewUser({...newUser, name: e.target.value})} />
              <input placeholder="Passwort" type="password" value={newUser.password} onChange={(e) => setNewUser({...newUser, password: e.target.value})} />
              <div className="form-actions"><button type="submit" className="btn btn-primary">Erstellen</button></div>
            </form>

            <form onSubmit={resetPassword} className="form-vertical narrow">
              <h4>Passwort zurücksetzen</h4>
              <input placeholder="Benutzername" value={resetUser.username} onChange={(e) => setResetUser({...resetUser, username: e.target.value})} />
              <input placeholder="Neues Passwort" type="password" value={resetUser.password} onChange={(e) => setResetUser({...resetUser, password: e.target.value})} />
              <button type="submit" className="btn btn-success">Zurücksetzen</button>
            </form>
          </div>

          {message ? <div className="message">{message}</div> : null}
        </div>

        <div className="right-column">
          <div className="card">
            <h3>Nextcloud-Konten</h3>
            <div className="accounts-scroll">
              <ul className="account-list">
                {accounts.map((a) => (
                  <li key={a.key} className="account-item">
                    <div className="account-meta"><strong>{a.domain}</strong><div className="muted small">{a.username} — {a.display_name}</div></div>
                    <div><button className="btn btn-danger" onClick={() => { if (confirm('Account wirklich löschen?')) deleteAccount(a.key); }}>Löschen</button></div>
                  </li>
                ))}
              </ul>
            </div>
              <form onSubmit={rotateKey} className="rotate-form">
                <input placeholder="Neue NEXTCLOUD_ACCOUNTS_KEY (Base64)" value={rotateKeyValue} onChange={(e) => setRotateKeyValue(e.target.value)} />
                <button type="submit" className="btn btn-primary">Key rotieren</button>
              </form>
          </div>

            <div className="card">
              <h3>Nextcloud OAuth Konfiguration</h3>
              <form onSubmit={saveOauthConfig} className="form-vertical">
                <label className="label">Client ID</label>
                <input placeholder="Client ID" value={oauthClientId} onChange={(e) => setOauthClientId(e.target.value)} />
                <label className="label">Client Secret</label>
                <input placeholder="Client Secret" value={oauthClientSecret} onChange={(e) => setOauthClientSecret(e.target.value)} />
                <label className="label">Default Nextcloud URL</label>
                <input placeholder="https://cloud.example.org" value={oauthNextcloudUrl} onChange={(e) => setOauthNextcloudUrl(e.target.value)} />
                <div className="form-actions">
                  <button type="submit" className="btn btn-primary">Speichern</button>
                </div>
                {oauthMessage ? <div className="message">{oauthMessage}</div> : null}
                <div style={{marginTop:8, color:'#555', fontSize:13}}>{oauthCfg.client_id ? `Client ID gesetzt: ${oauthCfg.client_id}` : 'Client ID nicht gesetzt'} — {oauthCfg.has_secret ? 'Secret gesetzt' : 'Secret nicht gesetzt'}</div>
              </form>
            </div>

          <div className="card">
            <h3>Sicherheit & Hinweise</h3>
            <ul className="hint-list">
              <li>Setze <strong>AUTH_COOKIE_SECURE=true</strong> in Produktion und betreibe HTTPS.</li>
              <li>Generiere einen sicheren Fernet-Key und setze <strong>NEXTCLOUD_ACCOUNTS_KEY</strong>.</li>
              <li>Erzeuge einen Admin-Benutzer via Admin-UI und ändere <strong>ADMIN_USER</strong> entsprechend.</li>
            </ul>
            <details>
              <summary className="summary">Beispiel: Key generieren</summary>
              <pre className="code">{`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`}</pre>
            </details>
          </div>
        </div>
      </div>
    </div>
  );
}
