"use client";

import { useEffect, useState } from 'react';

export default function StatusPill() {
  const [status, setStatus] = useState({ ollama: 'unknown', kb: 'unknown' });

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const [oRes, kRes] = await Promise.all([
          fetch('/api/ollama/status').catch(() => null),
          fetch('/api/knowledge/status').catch(() => null)
        ]);
        const o = oRes && oRes.ok ? await oRes.json() : null;
        const k = kRes && kRes.ok ? await kRes.json() : null;
        if (!mounted) return;
        setStatus({ ollama: o && o.status ? o.status : 'offline', kb: k && k.status ? k.status : 'offline' });
      } catch (err) {
        if (!mounted) return;
        setStatus({ ollama: 'offline', kb: 'offline' });
      }
    };
    load();
    const iv = setInterval(load, 10000);
    return () => { mounted = false; clearInterval(iv); };
  }, []);

  const dot = (s) => {
    if (s === 'online' || s === 'ready' || s === 'ok') return 'var(--status-green, #16a34a)';
    if (s === 'starting' || s === 'connecting' || s === 'loading') return 'var(--status-amber, #f59e0b)';
    return 'var(--status-red, #ef4444)';
  };

  return (
    <div className="status-pill" aria-hidden>
      <div className="status-chip" title={`Ollama: ${status.ollama}`}>
        <span className="status-dot" style={{background: dot(status.ollama)}} />
        <span className="status-label">LLM</span>
      </div>
      <div className="status-chip" title={`Knowledge: ${status.kb}`}>
        <span className="status-dot" style={{background: dot(status.kb)}} />
        <span className="status-label">KB</span>
      </div>
    </div>
  );
}
