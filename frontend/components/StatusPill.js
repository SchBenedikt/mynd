"use client";

import { useEffect, useState } from 'react';

export default function StatusPill() {
  const [status, setStatus] = useState({ ollama: 'unknown', kb: 'unknown' });
  const [expanded, setExpanded] = useState(false);

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

  const dotColor = (s) => {
    if (!s) return 'var(--status-red, #ef4444)';
    const st = String(s).toLowerCase();
    if (st === 'online' || st === 'ready' || st === 'ok') return 'var(--status-green, #16a34a)';
    if (st === 'starting' || st === 'connecting' || st === 'loading') return 'var(--status-amber, #f59e0b)';
    return 'var(--status-red, #ef4444)';
  };

  // aggregated color when collapsed: green if both ok, orange if one bad, red if both bad
  const aggregateColor = () => {
    const ok1 = ['online','ready','ok'].includes(String(status.ollama).toLowerCase());
    const ok2 = ['online','ready','ok'].includes(String(status.kb).toLowerCase());
    if (ok1 && ok2) return 'var(--status-green, #16a34a)';
    if (ok1 || ok2) return 'var(--status-amber, #f59e0b)';
    return 'var(--status-red, #ef4444)';
  };

  return (
    <div className={`status-widget ${expanded ? 'expanded' : 'collapsed'}`}>
      {!expanded ? (
        <button className="status-collapse" title={`Status: LLM=${status.ollama}, KB=${status.kb}`} onClick={() => setExpanded(true)}>
          <span className="status-aggregated-dot" style={{background: aggregateColor()}} />
        </button>
      ) : (
        <div className="status-panel">
          <div className="status-row">
            <div className="status-chip" title={`Ollama: ${status.ollama}`}>
              <span className="status-dot" style={{background: dotColor(status.ollama)}} />
              <span className="status-label">LLM</span>
            </div>
            <div className="status-chip" title={`Knowledge: ${status.kb}`}>
              <span className="status-dot" style={{background: dotColor(status.kb)}} />
              <span className="status-label">KB</span>
            </div>
          </div>
          <div className="status-actions">
            <button className="btn btn-ghost" onClick={() => setExpanded(false)}>Schließen</button>
          </div>
        </div>
      )}
    </div>
  );
}
