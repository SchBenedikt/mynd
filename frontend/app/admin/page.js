"use client";

import { useEffect, useState } from 'react';

export default function AdminPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newUser, setNewUser] = useState({ username: '', password: '', name: '' });
  const [resetUser, setResetUser] = useState({ username: '', password: '' });
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetch('/api/admin/users')
      .then((r) => r.json())
      .then((data) => {
        if (data && data.success) setUsers(data.users || []);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
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

      {message ? <div style={{marginTop: 20, color: 'crimson'}}>{message}</div> : null}
    </div>
  );
}
