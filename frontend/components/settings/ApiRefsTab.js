'use client';

import { useState, useEffect } from 'react';
import { apiFetch } from '../../lib/api';

export default function ApiRefsTab({ tr, language }) {
  const [apiRefsContent, setApiRefsContent] = useState('');
  const [apiRefsStatus, setApiRefsStatus] = useState('');
  const [apiRefsError, setApiRefsError] = useState('');

  const loadApiRefs = async () => {
    try {
      const res = await apiFetch('/api/references');
      const data = await res.json();
      setApiRefsContent(JSON.stringify(data, null, 2));
      setApiRefsError('');
    } catch (err) {
      setApiRefsError(tr('Fehler beim Laden', 'Error loading') + ': ' + err.message);
    }
  };

  const saveApiRefs = async () => {
    try {
      JSON.parse(apiRefsContent);
    } catch (err) {
      setApiRefsError(tr('Ungültiges JSON:', 'Invalid JSON:') + ' ' + err.message);
      return;
    }
    setApiRefsError('');
    setApiRefsStatus(tr('Speichere...', 'Saving...'));
    try {
      const res = await apiFetch('/api/references', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: apiRefsContent
      });
      if (res.ok) {
        setApiRefsStatus(tr('✓ Erfolgreich gespeichert', '✓ Saved successfully'));
      } else {
        const data = await res.json();
        setApiRefsStatus(tr('Fehler: ', 'Error: ') + (data.error || ''));
      }
    } catch (err) {
      setApiRefsStatus('Error: ' + err.message);
    }
  };

  useEffect(() => {
    loadApiRefs();
  // Load the editor contents once when the settings tab mounts.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="settings-panel">
      <div className="panel-section">
        <div className="section-title">{tr('API-Referenzen', 'API Refs')}</div>
        <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0 1rem 0'}}>
          {tr('Bearbeite die API-Referenzdefinitionen (api_refs.json).', 'Edit the API reference definitions (api_refs.json).')}
        </p>
        <div className="input-group">
          <label>api_refs.json</label>
          <textarea
            value={apiRefsContent}
            onChange={(e) => { setApiRefsContent(e.target.value); setApiRefsError(''); }}
            style={{
              width: '100%', minHeight: '400px', fontFamily: 'monospace', fontSize: '0.82rem',
              padding: '0.75rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)',
              background: 'var(--background)', color: 'var(--text)', resize: 'vertical',
              lineHeight: '1.5', tabSize: 2
            }}
            spellCheck={false}
          />
        </div>
        {apiRefsError && (
          <div style={{
            color: '#ef4444', fontSize: '0.85rem', marginTop: '0.5rem',
            padding: '0.5rem 0.75rem', background: 'rgba(239,68,68,0.08)',
            borderRadius: 'var(--radius-sm)', border: '1px solid rgba(239,68,68,0.2)'
          }}>
            <i className="fas fa-exclamation-triangle" style={{marginRight: '0.4rem'}}></i>
            {apiRefsError}
          </div>
        )}
        <div className="button-group" style={{marginTop: '1rem'}}>
          <button className="btn primary" onClick={saveApiRefs}>
            <i className="fas fa-save" style={{marginRight: '0.4rem'}}></i>
            {tr('Speichern', 'Save')}
          </button>
        </div>
        {apiRefsStatus && <div className="status-text" style={{marginTop: '0.5rem'}}>{apiRefsStatus}</div>}
      </div>
    </div>
  );
}
