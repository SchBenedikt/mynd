"use client";

import { useEffect, useState } from 'react';

export default function AdminPage() {
  const [users, setUsers] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newUser, setNewUser] = useState({ username: '', password: '', name: '' });
  const [resetUser, setResetUser] = useState({ username: '', password: '' });
  const [message, setMessage] = useState('');
  const [rotateKeyValue, setRotateKeyValue] = useState('');
  const cardStyle = { background: 'white', borderRadius: 10, padding: 16, boxShadow: '0 6px 18px rgba(15,15,15,0.08)' };
  const btnPrimary = { background: '#2f63ff', color: 'white', border: 'none', padding: '8px 12px', borderRadius: 8 };
  const btnDanger = { background: '#ef4444', color: 'white', border: 'none', padding: '6px 10px', borderRadius: 8 };

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

  return (
    <div style={{padding: 28, maxWidth: 980, margin: '0 auto'}}>
      <h2 style={{marginBottom: 6}}>Admin: Benutzerverwaltung</h2>
      <p style={{color: '#666', marginTop: 0}}>Verwalte lokale Benutzer und gespeicherte Nextcloud-Accounts. Nur `ADMIN_USER` kann diese Seite nutzen.</p>

      <div style={{display: 'grid', gridTemplateColumns: '1fr 360px', gap: 20, marginTop: 18}}>
        <div style={cardStyle}>
          <h3 style={{marginTop: 0}}>Bestehende Nutzer</h3>
          {loading ? <div>lade...</div> : (
            <div>
              <ul style={{paddingLeft: 16}}>
                {users.map((u) => (
                  <li key={u.username} style={{marginBottom: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                    <div>{u.username} <span style={{color: '#666'}}>— {u.name}</span></div>
                    <div><button style={btnDanger} onClick={() => { if (confirm('Benutzer wirklich löschen?')) deleteUser(u.username); }}>Löschen</button></div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div style={{height: 1, background: '#f0f0f0', margin: '12px 0'}} />

          <div style={{display: 'flex', gap: 12}}>
            <form onSubmit={createUser} style={{display: 'flex', flexDirection: 'column', gap: 8, flex: 1}}>
              <h4 style={{margin: 0}}>Neuen Nutzer anlegen</h4>
              <input placeholder="Benutzername" value={newUser.username} onChange={(e) => setNewUser({...newUser, username: e.target.value})} />
              <input placeholder="Anzeigename" value={newUser.name} onChange={(e) => setNewUser({...newUser, name: e.target.value})} />
              <input placeholder="Passwort" type="password" value={newUser.password} onChange={(e) => setNewUser({...newUser, password: e.target.value})} />
              <div style={{display: 'flex', gap: 8}}>
                <button type="submit" style={btnPrimary}>Erstellen</button>
              </div>
            </form>

            <form onSubmit={resetPassword} style={{display: 'flex', flexDirection: 'column', gap: 8, width: 220}}>
              <h4 style={{margin: 0}}>Passwort zurücksetzen</h4>
              <input placeholder="Benutzername" value={resetUser.username} onChange={(e) => setResetUser({...resetUser, username: e.target.value})} />
              <input placeholder="Neues Passwort" type="password" value={resetUser.password} onChange={(e) => setResetUser({...resetUser, password: e.target.value})} />
              <button type="submit" style={{...btnPrimary, background: '#16a34a'}}>Zurücksetzen</button>
            </form>
          </div>

          {message ? <div style={{marginTop: 12, color: 'crimson'}}>{message}</div> : null}
        </div>

        <div style={{display: 'flex', flexDirection: 'column', gap: 20}}>
          <div style={cardStyle}>
            <h3 style={{marginTop: 0}}>Nextcloud-Konten</h3>
            <div style={{maxHeight: 220, overflow: 'auto'}}>
              <ul style={{paddingLeft: 12}}>
                {accounts.map((a) => (
                  <li key={a.key} style={{marginBottom: 8}}>
                    <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                      <div style={{fontSize: 13}}><strong>{a.domain}</strong><div style={{color: '#666', fontSize: 12}}>{a.username} — {a.display_name}</div></div>
                      <div><button style={btnDanger} onClick={() => { if (confirm('Account wirklich löschen?')) deleteAccount(a.key); }}>Löschen</button></div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>

            <form onSubmit={rotateKey} style={{display: 'flex', gap: 8, marginTop: 12}}>
              <input placeholder="Neue NEXTCLOUD_ACCOUNTS_KEY (Base64)" value={rotateKeyValue} onChange={(e) => setRotateKeyValue(e.target.value)} style={{flex: 1}} />
              <button type="submit" style={btnPrimary}>Key rotieren</button>
            </form>
          </div>

          <div style={cardStyle}>
            <h3 style={{marginTop: 0}}>Sicherheit & Hinweise</h3>
            <ul style={{color: '#444'}}>
              <li>Setze <strong>AUTH_COOKIE_SECURE=true</strong> in Produktion und betreibe HTTPS.</li>
              <li>Generiere einen sicheren Fernet-Key und setze <strong>NEXTCLOUD_ACCOUNTS_KEY</strong>.</li>
              <li>Erzeuge einen Admin-Benutzer via Admin-UI und ändere <strong>ADMIN_USER</strong> entsprechend.</li>
            </ul>
            <details>
              <summary style={{cursor: 'pointer', marginTop: 8}}>Beispiel: Key generieren</summary>
              <pre style={{background: '#f7f7f7', padding: 8, borderRadius: 6, marginTop: 8}}>
                {"python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""}
              </pre>
            </details>
          </div>
        </div>
      </div>
    </div>
  );
}
