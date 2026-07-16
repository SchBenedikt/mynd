'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { apiFetch } from '../../lib/api';

function getAuthHeaders() {
  try {
    const token = localStorage.getItem('mynd_token_v1');
    return token ? { 'Authorization': `Bearer ${token}` } : {};
  } catch { return {}; }
}

export default function ProfileTab({ tr, language }) {
  const router = useRouter();
  const [profile, setProfile] = useState({ name: '', username: '' });
  const [password, setPassword] = useState('');
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    apiFetch('/api/auth/profile', { headers: getAuthHeaders() })
      .then(r => r.json())
      .then(data => {
        if (data?.success) setProfile({ name: data.user.name || '', username: data.user.username });
      })
      .catch(() => setError('Profil konnte nicht geladen werden'));
  }, []);

  const saveProfile = async (e) => {
    e.preventDefault();
    setMsg('');
    setError('');
    const body = {};
    if (profile.name.trim()) body.name = profile.name.trim();
    if (password.trim()) body.password = password.trim();
    if (Object.keys(body).length === 0) return;
    setSaving(true);
    try {
      const res = await apiFetch('/api/auth/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify(body)
      });
      const data = await res.json();
      if (res.ok && data?.success) {
        setMsg(tr('Gespeichert', 'Saved'));
        setPassword('');
        if (data.user) setProfile({ name: data.user.name || '', username: data.user.username });
        setTimeout(() => setMsg(''), 3000);
      } else {
        setError(data?.error || tr('Fehler', 'Error'));
      }
    } catch (err) {
      setError(tr('Netzwerkfehler', 'Network error'));
    } finally {
      setSaving(false);
    }
  };

  const resetForm = () => {
    setError('');
    setMsg('');
    setPassword('');
  };

  return (
    <div className="settings-panel">
      <div className="panel-section">
        <div className="section-title" style={{display:'flex',alignItems:'center',gap:'0.6rem'}}>
          <div style={{
            width: 36, height: 36, borderRadius: '50%',
            background: 'var(--brand)', color: '#fff',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '1rem', fontWeight: 600,
            flexShrink: 0
          }}>
            {profile.name ? profile.name[0].toUpperCase() : profile.username?.[0]?.toUpperCase() || '?'}
          </div>
          <div>
            <div style={{fontWeight:600,fontSize:'1.05rem'}}>{tr('Mein Profil', 'My Profile')}</div>
            <div style={{fontSize:'0.82rem',color:'var(--muted)',marginTop:'0.1rem'}}>
              {tr('Verwalte deine persönlichen Einstellungen', 'Manage your personal settings')}
            </div>
          </div>
        </div>

        <form onSubmit={saveProfile} className="profile-form">
          <div className="profile-field">
            <label className="profile-label">{tr('Benutzername', 'Username')}</label>
            <div className="profile-input-wrap disabled">
              <i className="fas fa-user"></i>
              <input type="text" value={profile.username} disabled />
            </div>
          </div>

          <div className="profile-field">
            <label className="profile-label">{tr('Anzeigename', 'Display name')}</label>
            <div className="profile-input-wrap">
              <i className="fas fa-id-card"></i>
              <input type="text" value={profile.name}
                onChange={(e) => { setProfile({...profile, name: e.target.value}); resetForm(); }}
                placeholder={tr('Dein Anzeigename', 'Your display name')} />
            </div>
          </div>

          <div className="profile-field">
            <label className="profile-label">{tr('Neues Passwort', 'New password')}</label>
            <div className="profile-input-wrap">
              <i className="fas fa-lock"></i>
              <input type="password" value={password}
                onChange={(e) => { setPassword(e.target.value); resetForm(); }}
                placeholder={tr('Leer lassen um zu behalten', 'Leave empty to keep current')} />
            </div>
          </div>

          <div className="profile-actions">
            <button type="submit" className="btn primary" disabled={saving}>
              {saving ? (
                <><i className="fas fa-spinner fa-pulse" style={{marginRight:'0.4rem'}}></i>{tr('Speichern...', 'Saving...')}</>
              ) : (
                <><i className="fas fa-check" style={{marginRight:'0.4rem'}}></i>{tr('Speichern', 'Save')}</>
              )}
            </button>
          </div>

          {msg && <div className="profile-msg success"><i className="fas fa-check-circle"></i> {msg}</div>}
          {error && <div className="profile-msg error"><i className="fas fa-exclamation-circle"></i> {error}</div>}
        </form>
      </div>

      <div className="panel-section" style={{marginTop:'2rem',borderTop:'1px solid var(--line)',paddingTop:'1.5rem'}}>
        <button className="btn danger" onClick={() => {
          try { localStorage.removeItem('mynd_token_v1'); } catch (e) {}
          try { localStorage.removeItem('mynd_user_v1'); } catch (e) {}
          router.push('/');
        }} style={{width:'100%',padding:'0.6rem'}}>
          <i className="fas fa-sign-out-alt" style={{marginRight:'0.4rem'}}></i>
          {tr('Abmelden', 'Log out')}
        </button>
      </div>
    </div>
  );
}
