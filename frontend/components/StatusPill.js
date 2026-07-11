"use client";

import { useEffect, useState } from 'react';
import { apiFetch, getApiBase } from '../lib/api';

export default function StatusPill() {
  const [status, setStatus] = useState({ ollama: 'unknown', kb: 'unknown' });
  const [user, setUser] = useState(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const [oRes, kRes, meRes] = await Promise.all([
          apiFetch('/api/ollama/status').catch(() => null),
          apiFetch('/api/knowledge/status').catch(() => null),
          apiFetch('/api/auth/me').catch(() => null)
        ]);
        const o = oRes && oRes.ok ? await oRes.json() : null;
        const k = kRes && kRes.ok ? await kRes.json() : null;
        const me = meRes && meRes.ok ? await meRes.json() : null;
        if (!mounted) return;
        setStatus({ ollama: o && o.status ? o.status : 'offline', kb: k && (k.status || k.connected) ? (k.status || 'connected') : 'offline' });
        if (me && me.authenticated && me.user) {
          setUser(me.user);
        } else {
          try {
            const raw = localStorage.getItem('mynd_user_v1');
            if (raw) setUser(JSON.parse(raw));
          } catch (e) {}
        }
      } catch (err) {
        if (!mounted) return;
        setStatus({ ollama: 'offline', kb: 'offline' });
      }
    };
    load();
    const iv = setInterval(load, 10000);
    return () => { mounted = false; clearInterval(iv); };
  }, []);

  const dotColor = (s) => {
    if (!s) return 'var(--status-red, #ef4444)';
    const st = String(s).toLowerCase();
    if (st === 'online' || st === 'ready' || st === 'ok' || st === 'connected') return 'var(--status-green, #16a34a)';
    if (st === 'starting' || st === 'connecting' || st === 'loading') return 'var(--status-amber, #f59e0b)';
    return 'var(--status-red, #ef4444)';
  };

  const isOnline = (s) => {
    if (!s) return false;
    const st = String(s).toLowerCase();
    return ['online', 'ready', 'ok', 'connected'].includes(st);
  };

  const logout = async () => {
    try { await apiFetch('/api/auth/logout', { method: 'POST' }); } catch(e) {}
    try { localStorage.removeItem('mynd_user_v1'); localStorage.removeItem('mynd_token_v1'); } catch(e){}
    window.location.reload();
  };

  // If both services are offline (or unknown) and no user is logged in, hide the panel entirely
  if (!isOnline(status.ollama) && !isOnline(status.kb) && !user) return null;

  return (
    <div className="status-widget">
      <div className="status-panel">
        <div className="status-row">
          <div className="status-chip" title={`Ollama: ${status.ollama}`}>
            <span className="status-dot" style={{background: dotColor(status.ollama)}} />
            <span className="status-label">Ollama</span>
            <span style={{marginLeft:8, fontWeight:500, color:'var(--muted)', fontSize:12}}>{String(status.ollama).charAt(0).toUpperCase()+String(status.ollama).slice(1)}</span>
          </div>
          <div className="status-chip" title={`Knowledge: ${status.kb}`}>
            <span className="status-dot" style={{background: dotColor(status.kb)}} />
            <span className="status-label">KB</span>
            <span style={{marginLeft:8, fontWeight:500, color:'var(--muted)', fontSize:12}}>{String(status.kb).charAt(0).toUpperCase()+String(status.kb).slice(1)}</span>
          </div>
        </div>
        <div style={{marginTop:8, display:'flex', gap:8, alignItems:'center', justifyContent:'space-between'}}>
          <div style={{fontSize:13, color:'var(--muted)'}}>{user ? `${user.name || user.username} — ${user.username}` : 'Nicht angemeldet'}</div>
          {user ? <button className="btn btn-ghost" onClick={logout}>Logout</button> : null}
        </div>
      </div>
    </div>
  );
}
