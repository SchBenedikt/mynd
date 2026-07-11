'use client';

import { useState, useEffect } from 'react';

export default function MemoryTab({ tr, language }) {
  const [items, setItems] = useState([]);
  const [status, setStatus] = useState('');
  const [newKey, setNewKey] = useState('');
  const [newValue, setNewValue] = useState('');

  const loadMemory = async () => {
    try {
      const res = await fetch('/api/memory');
      const data = await res.json();
      if (res.ok) {
        setItems(data.items || []);
      } else {
        setStatus(tr('Fehler beim Laden', 'Error loading') + ': ' + (data.error || ''));
      }
    } catch (err) {
      setStatus('Error: ' + err.message);
    }
  };

  const saveMemory = async () => {
    const key = newKey.trim();
    const value = newValue.trim();
    if (!key || !value) {
      setStatus(tr('Key und Value dürfen nicht leer sein', 'Key and value must not be empty'));
      return;
    }
    try {
      const res = await fetch('/api/memory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, value })
      });
      const data = await res.json();
      if (res.ok) {
        setStatus(tr('✓ Gespeichert', '✓ Saved'));
        setNewKey('');
        setNewValue('');
        loadMemory();
      } else {
        setStatus(tr('Fehler: ', 'Error: ') + (data.error || ''));
      }
    } catch (err) {
      setStatus('Error: ' + err.message);
    }
  };

  const deleteMemory = async (key) => {
    if (!confirm(tr(`"${key}" wirklich löschen?`, `Really delete "${key}"?`))) return;
    try {
      const res = await fetch(`/api/memory/${encodeURIComponent(key)}`, { method: 'DELETE' });
      if (res.ok) {
        setStatus(tr('✓ Gelöscht', '✓ Deleted'));
        loadMemory();
      } else {
        const data = await res.json();
        setStatus(tr('Fehler: ', 'Error: ') + (data.error || ''));
      }
    } catch (err) {
      setStatus('Error: ' + err.message);
    }
  };

  useEffect(() => {
    loadMemory();
  }, []);

  return (
    <div className="settings-panel">
      <div className="panel-section">
        <div className="section-title">{tr('Persistentes Gedächtnis', 'Persistent Memory')}</div>
        <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
          {tr('Die KI kann sich über Chats hinweg Dinge merken (z.B. deinen Namen, Präferenzen, Server-Adressen). Hier siehst du, was gemerkt wurde, und kannst Einträge bearbeiten oder löschen.', 'The AI can remember things across chats (e.g. your name, preferences, server addresses). Here you can view, edit, or delete what has been remembered.')}
        </p>

        <div style={{display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap', alignItems: 'flex-end'}}>
          <div className="input-group" style={{flex: '1 1 200px', marginBottom: 0}}>
            <label style={{fontSize: '0.8rem'}}>{tr('Key', 'Key')}</label>
            <input type="text" value={newKey} onChange={(e) => setNewKey(e.target.value)}
              placeholder={tr('z.B. user/name', 'e.g. user/name')} />
          </div>
          <div className="input-group" style={{flex: '1 1 250px', marginBottom: 0}}>
            <label style={{fontSize: '0.8rem'}}>{tr('Wert', 'Value')}</label>
            <input type="text" value={newValue} onChange={(e) => setNewValue(e.target.value)}
              placeholder={tr('Wert eingeben', 'Enter value')} />
          </div>
          <button className="btn primary" onClick={saveMemory} style={{height: 'fit-content'}}>
            <i className="fas fa-brain" style={{marginRight: '0.4rem'}}></i>
            {tr('Merken', 'Remember')}
          </button>
        </div>

        {status && <div className="status-text" style={{marginBottom: '0.75rem'}}>{status}</div>}

        {items.length === 0 ? (
          <p style={{color: 'var(--muted)'}}>
            {tr('Keine gespeicherten Erinnerungen. Sage der KI z.B. "Merke dir, dass ich Max heiße" – dann erscheint es hier.', 'No saved memories. Tell the AI e.g. "Remember that my name is Max" – it will appear here.')}
          </p>
        ) : (
          <div style={{display: 'flex', flexDirection: 'column', gap: '0.35rem'}}>
            {items.map(item => (
              <div key={item.key} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '0.5rem 0.7rem', background: 'var(--background)',
                    borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', fontSize: '0.875rem'
              }}>
                <div style={{display: 'flex', alignItems: 'center', gap: '0.6rem', overflow: 'hidden', flex: 1}}>
                  <i className="fas fa-brain" style={{fontSize: '0.8rem', color: 'var(--muted)', flexShrink: 0}}></i>
                  <span style={{
                    fontWeight: '500', fontSize: '0.8rem', color: 'var(--muted)',
                    flexShrink: 0
                  }}>
                    {item.key}
                  </span>
                  <span style={{
                    fontSize: '0.85rem', color: 'var(--text)',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'
                  }}>
                    {item.value}
                  </span>
                </div>
                <button className="btn secondary" style={{padding: '0.2rem 0.5rem', fontSize: '0.75rem', flexShrink: 0, marginLeft: '0.5rem'}}
                  onClick={() => deleteMemory(item.key)}>
                  <i className="fas fa-trash-alt" style={{fontSize: '0.75rem'}}></i>
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
