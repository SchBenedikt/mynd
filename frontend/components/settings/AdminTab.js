'use client';

import { useState, useEffect } from 'react';
import { apiFetch, getApiBase } from '../../lib/api';

function getAuthHeaders() {
  try {
    const token = localStorage.getItem('mynd_token_v1');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  } catch { return {}; }
}

export default function AdminTab({ tr, language }) {
  const [authConfig, setAuthConfig] = useState({ allowRegistration: false, requireLogin: true });
  const [authConfigMsg, setAuthConfigMsg] = useState('');
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newUser, setNewUser] = useState({ username: '', password: '', name: '' });
  const [userMsg, setUserMsg] = useState('');
  const [userError, setUserError] = useState('');

  useEffect(() => {
    apiFetch('/api/auth/config')
      .then(r => r.json())
      .then(data => {
        if (data?.success) {
          setAuthConfig({ allowRegistration: !!data.allowRegistration, requireLogin: !!data.requireLogin });
        }
      })
      .catch(() => setUserError('Auth-Konfiguration konnte nicht geladen werden'));
    const headers = getAuthHeaders();
    apiFetch('/api/admin/users', { headers })
      .then(r => r.json())
      .then(data => {
        if (data?.success) setUsers(data.users || []);
      })
      .catch(() => setUserError('Benutzerliste konnte nicht geladen werden'))
      .finally(() => setLoading(false));
  }, []);

  const saveAuthConfig = async (key, value) => {
    const updated = { ...authConfig, [key]: value };
    setAuthConfig(updated);
    setAuthConfigMsg('');
    try {
      const res = await apiFetch('/api/auth/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated)
      });
      const data = await res.json();
      if (data?.success) {
        setAuthConfigMsg(tr('Gespeichert', 'Saved'));
      } else {
        setAuthConfigMsg(data?.error || tr('Fehler', 'Error'));
        apiFetch('/api/auth/config').then(r => r.json()).then(d => {
          if (d?.success) setAuthConfig({ allowRegistration: !!d.allowRegistration, requireLogin: !!d.requireLogin });
        }).catch(() => setUserError('Auth-Konfiguration konnte nicht neu geladen werden'));
      }
    } catch (err) {
      setAuthConfigMsg(tr('Netzwerkfehler', 'Network error'));
    }
  };

  const createUser = async (e) => {
    e.preventDefault();
    setUserMsg('');
    setUserError('');
    if (!newUser.username.trim() || !newUser.password.trim()) {
      setUserError(tr('Benutzername und Passwort erforderlich', 'Username and password required'));
      return;
    }
    try {
      const res = await apiFetch('/api/admin/users/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify(newUser)
      });
      const data = await res.json();
      if (res.ok && data?.success) {
        setUserMsg(tr('Benutzer angelegt', 'User created'));
        setUsers(s => [...s, data.user]);
        setNewUser({ username: '', password: '', name: '' });
      } else {
        setUserError(data?.error || tr('Fehler', 'Error'));
      }
    } catch (err) {
      setUserError(tr('Netzwerkfehler', 'Network error'));
    }
  };

  const deleteUser = async (username) => {
    if (!confirm(tr('Benutzer wirklich löschen?', 'Really delete user?'))) return;
    setUserMsg('');
    setUserError('');
    try {
      const res = await apiFetch('/api/admin/users/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ username })
      });
      const data = await res.json();
      if (res.ok && data?.success) {
        setUserMsg(tr('Benutzer gelöscht', 'User deleted'));
        setUsers(s => s.filter(u => u.username !== username));
      } else {
        setUserError(data?.error || tr('Fehler', 'Error'));
      }
    } catch (err) {
      setUserError(tr('Netzwerkfehler', 'Network error'));
    }
  };

  const resetPassword = async (username) => {
    const password = prompt(tr('Neues Passwort für', 'New password for') + ` ${username}:`);
    if (!password || !password.trim()) return;
    setUserMsg('');
    setUserError('');
    try {
      const res = await apiFetch('/api/admin/users/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ username, password: password.trim() })
      });
      const data = await res.json();
      if (res.ok && data?.success) {
        setUserMsg(tr('Passwort zurückgesetzt', 'Password reset'));
      } else {
        setUserError(data?.error || tr('Fehler', 'Error'));
      }
    } catch (err) {
      setUserError(tr('Netzwerkfehler', 'Network error'));
    }
  };

  return (
    <div className="settings-panel">
      <div className="panel-section">
        <div className="section-title" style={{display:'flex',alignItems:'center',gap:'0.5rem'}}>
          <i className="fas fa-shield" style={{color:'var(--brand)',fontSize:'1rem'}}></i>
          {tr('Authentifizierung', 'Authentication')}
        </div>
        <p style={{fontSize:'0.9rem',color:'var(--muted)',margin:'0.5rem 0 1rem 0'}}>
          {tr('Steuere, ob sich Benutzer registrieren können und ob eine Anmeldung erforderlich ist.', 'Control whether users can register and whether login is required.')}
        </p>
        <div className="auth-toggle-group">
          <label className="auth-toggle">
            <input type="checkbox" checked={authConfig.allowRegistration}
              onChange={(e) => saveAuthConfig('allowRegistration', e.target.checked)} />
            <span className="auth-toggle-switch"></span>
            <span className="auth-toggle-label">{tr('Registrierung erlauben', 'Allow registration')}</span>
          </label>
          <label className="auth-toggle">
            <input type="checkbox" checked={authConfig.requireLogin}
              onChange={(e) => saveAuthConfig('requireLogin', e.target.checked)} />
            <span className="auth-toggle-switch"></span>
            <span className="auth-toggle-label">{tr('Anmeldung erforderlich', 'Login required')}</span>
          </label>
        </div>
        {authConfigMsg && <div className="status-text" style={{marginTop:'0.75rem',fontSize:'0.85rem',color:'var(--success)'}}>{authConfigMsg}</div>}
      </div>

      <div className="panel-section" style={{marginTop:'2rem'}}>
        <div className="section-title" style={{display:'flex',alignItems:'center',gap:'0.5rem'}}>
          <i className="fas fa-users" style={{color:'var(--brand)',fontSize:'1rem'}}></i>
          {tr('Benutzerverwaltung', 'User Management')}
        </div>
        {loading ? (
          <div className="status-text" style={{padding:'1rem 0',color:'var(--muted)'}}>{tr('Lade...', 'Loading...')}</div>
        ) : (
          <>
            <div className="user-list-admin">
              {users.map(u => (
                <div key={u.username} className="user-row-admin">
                  <div className="user-row-admin-info">
                    <div className="user-row-admin-avatar">{(u.name || u.username || '?')[0].toUpperCase()}</div>
                    <div>
                      <div className="user-row-admin-name">{u.name || u.username}</div>
                      <div className="user-row-admin-username">{u.username}{u.username === 'admin' ? ` (${tr('Admin', 'Admin')})` : ''}</div>
                    </div>
                  </div>
                  <div className="user-row-admin-actions">
                    <button className="btn-icon" onClick={() => resetPassword(u.username)}
                      title={tr('Passwort zurücksetzen', 'Reset password')}>
                      <i className="fas fa-key"></i>
                    </button>
                    {u.username !== 'admin' && (
                      <button className="btn-icon btn-icon-danger" onClick={() => deleteUser(u.username)}
                        title={tr('Löschen', 'Delete')}>
                        <i className="fas fa-trash"></i>
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>

            <div className="create-user-form">
              <div className="create-user-title">{tr('Neuen Benutzer anlegen', 'Create new user')}</div>
              <form onSubmit={createUser} className="create-user-fields">
                <input type="text" value={newUser.username} onChange={(e) => setNewUser({...newUser,username:e.target.value})}
                  placeholder={tr('Benutzername', 'Username')} />
                <input type="text" value={newUser.name} onChange={(e) => setNewUser({...newUser,name:e.target.value})}
                  placeholder={tr('Anzeigename', 'Display name')} />
                <input type="password" value={newUser.password} onChange={(e) => setNewUser({...newUser,password:e.target.value})}
                  placeholder={tr('Passwort', 'Password')} />
                <button type="submit" className="btn primary">
                  <i className="fas fa-plus" style={{marginRight:'0.4rem'}}></i>
                  {tr('Erstellen', 'Create')}
                </button>
              </form>
            </div>
            {userMsg && <div className="status-text" style={{marginTop:'0.75rem',fontSize:'0.85rem',color:'var(--success)'}}>{userMsg}</div>}
            {userError && <div className="status-text" style={{marginTop:'0.75rem',fontSize:'0.85rem',color:'#ef4444'}}>{userError}</div>}
          </>
        )}
      </div>

      <div className="panel-section" style={{marginTop:'2rem'}}>
        <div className="section-title" style={{display:'flex',alignItems:'center',gap:'0.5rem'}}>
          <i className="fas fa-brush" style={{color:'#ef4444',fontSize:'1rem'}}></i>
          {tr('App zurücksetzen', 'Reset Application')}
        </div>
        <p style={{fontSize:'0.9rem',color:'var(--muted)',margin:'0.5rem 0 1rem 0'}}>
          {tr('Setzt die gesamte Anwendung zurück: löscht alle Chats, Konfigurationen und Benutzer. Diese Aktion kann nicht rückgängig gemacht werden!', 'Resets the entire application: deletes all chats, configurations and users. This action cannot be undone!')}
        </p>
        <button className="btn btn-danger" onClick={async () => {
          if (!confirm(tr('WIRKLICH die gesamte App zurücksetzen? Alle Chats, Einstellungen und Benutzer werden gelöscht!', 'REALLY reset the entire app? All chats, settings and users will be deleted!'))) return;
          if (!confirm(tr('Wirklich sicher? Diese Aktion kann nicht rückgängig gemacht werden!', 'Are you really sure? This action cannot be undone!'))) return;
          try {
            const res = await apiFetch('/api/admin/reset', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', ...getAuthHeaders() }
            });
            const data = await res.json();
            if (res.ok && data?.success) {
              alert(tr('App zurückgesetzt. Du wirst zur Login-Seite weitergeleitet.', 'App reset. You will be redirected to the login page.'));
              try { localStorage.clear(); } catch(e) {}
              window.location.href = '/';
            } else {
              alert(data?.error || tr('Fehler beim Zurücksetzen', 'Error resetting'));
            }
          } catch (err) {
            alert(tr('Netzwerkfehler', 'Network error'));
          }
        }}>
          <i className="fas fa-brush" style={{marginRight:'0.4rem'}}></i>
          {tr('App zurücksetzen', 'Reset Application')}
        </button>
      </div>
    </div>
  );
}
