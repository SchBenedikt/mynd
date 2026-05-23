"use client";

import { useEffect, useState } from 'react';

export default function AdminPage() {
  const [users, setUsers] = useState([]);
  const [accounts, setAccounts] = useState([]);
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
    <div style={{padding: 20}}>
      <h2>Admin: Benutzerverwaltung</h2>
      {loading ? <div>lade...</div> : (
        <div>
          <h3>Bestehende Nutzer</h3>
          <ul>
            {users.map((u) => <li key={u.username}>{u.username} — {u.name}</li>)}
          </ul>
        </div>
      )}

      <div style={{display: 'flex', gap: 20, marginTop: 20}}>
        <form onSubmit={createUser} style={{display: 'flex', flexDirection: 'column', gap: 8}}>
          <h4>Neuen Nutzer anlegen</h4>
          <input placeholder="Benutzername" value={newUser.username} onChange={(e) => setNewUser({...newUser, username: e.target.value})} />
          <input placeholder="Anzeigename" value={newUser.name} onChange={(e) => setNewUser({...newUser, name: e.target.value})} />
          <input placeholder="Passwort" type="password" value={newUser.password} onChange={(e) => setNewUser({...newUser, password: e.target.value})} />
          <button type="submit">Erstellen</button>
        </form>

        <form onSubmit={resetPassword} style={{display: 'flex', flexDirection: 'column', gap: 8}}>
          <h4>Passwort zurücksetzen</h4>
          <input placeholder="Benutzername" value={resetUser.username} onChange={(e) => setResetUser({...resetUser, username: e.target.value})} />
          <input placeholder="Neues Passwort" type="password" value={resetUser.password} onChange={(e) => setResetUser({...resetUser, password: e.target.value})} />
          <button type="submit">Zurücksetzen</button>
        </form>
      </div>

      <div style={{marginTop: 24}}>
        <h3>Nextcloud-Konten</h3>
        <ul>
          {accounts.map((a) => (
            <li key={a.key}>{a.domain} — {a.username} — {a.display_name} — {a.fetched_at ? new Date(a.fetched_at*1000).toLocaleString() : 'n/a'} <button onClick={() => deleteAccount(a.key)}>Löschen</button></li>
          ))}
        </ul>

        <form onSubmit={rotateKey} style={{display: 'flex', gap: 8, marginTop: 12}}>
          <input placeholder="Neue NEXTCLOUD_ACCOUNTS_KEY (Base64)" value={rotateKeyValue} onChange={(e) => setRotateKeyValue(e.target.value)} style={{flex: 1}} />
          <button type="submit">Key rotieren</button>
        </form>
      </div>

      {message ? <div style={{marginTop: 20, color: 'crimson'}}>{message}</div> : null}
    </div>
  );
}
