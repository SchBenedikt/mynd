"use client";

import { useEffect, useState } from 'react';

const TOKEN_KEY = 'mynd_token_v1';
const STORAGE_KEY = 'mynd_user_v1';

export default function UserBar() {
  const [user, setUser] = useState(null);

  useEffect(() => {
    try {
      // Prefer server-side cookie session
      fetch('/api/auth/me')
        .then((r) => r.json())
        .then((data) => {
          if (data && data.authenticated && data.user) {
            setUser({ name: data.user.name, username: data.user.username });
            return;
          }
          const raw = localStorage.getItem(STORAGE_KEY);
          if (raw) setUser(JSON.parse(raw));
        })
        .catch(() => {
          const raw = localStorage.getItem(STORAGE_KEY);
          if (raw) setUser(JSON.parse(raw));
        });
    } catch (err) {
      // ignore
    }
  }, []);

  const logout = async () => {
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
    } catch (err) {
      // ignore
    }
    try {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(STORAGE_KEY);
    } catch (err) {}
    window.location.reload();
  };

  if (!user) return null;

  return (
    <div style={{position: 'fixed', right: 12, top: 12, zIndex: 9998}}>
      <div style={{background: 'rgba(255,255,255,0.9)', borderRadius: 8, padding: '6px 10px', display: 'flex', gap: 8, alignItems: 'center', boxShadow: '0 4px 10px rgba(0,0,0,0.08)'}}>
        <div style={{fontSize: 13, color: '#222'}}>{user.name || user.username}</div>
        <button onClick={logout} style={{padding: '6px 8px', borderRadius: 6, border: 'none', background: '#ef4444', color: 'white', fontSize: 12}}>Logout</button>
      </div>
    </div>
  );
}
