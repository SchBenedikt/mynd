"use client";

import { useEffect, useState } from 'react';
import { apiFetch, getApiBase } from '../lib/api';

const TOKEN_KEY = 'mynd_token_v1';
const STORAGE_KEY = 'mynd_user_v1';

export default function UserBar() {
  const [user, setUser] = useState(null);

  useEffect(() => {
    try {
      // Prefer server-side cookie session
      apiFetch('/api/auth/me')
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
      await apiFetch('/api/auth/logout', { method: 'POST' });
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
    <div className="userbar">
      <div className="userbar-inner">
        <div className="user-avatar" aria-hidden>{(user.name || user.username || '').slice(0,1).toUpperCase()}</div>
        <div className="user-info">
          <div className="user-name">{user.name || user.username}</div>
        </div>
        <button className="btn btn-ghost logout-btn" onClick={logout} title="Abmelden">Logout</button>
      </div>
    </div>
  );
}
