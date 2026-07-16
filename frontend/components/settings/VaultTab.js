'use client';

import { useState, useEffect } from 'react';
import { apiFetch } from '../../lib/api';

export default function VaultTab({ tr, language }) {
  const [vaultEntries, setVaultEntries] = useState([]);
  const [vaultStatus, setVaultStatus] = useState('');
  const [vaultNewKey, setVaultNewKey] = useState('');
  const [vaultNewValue, setVaultNewValue] = useState('');
  const [vaultRevealed, setVaultRevealed] = useState({});

  const loadVaultEntries = async () => {
    try {
      const res = await apiFetch('/api/vault/entries');
      const data = await res.json();
      if (res.ok) {
        setVaultEntries(data.entries || []);
      } else {
        setVaultStatus(tr('Fehler beim Laden', 'Error loading') + ': ' + (data.error || ''));
      }
    } catch (err) {
      setVaultStatus('Error: ' + err.message);
    }
  };

  const addVaultEntry = async () => {
    const key = vaultNewKey.trim();
    const value = vaultNewValue.trim();
    if (!key || !value) {
      setVaultStatus(tr('Key und Value dürfen nicht leer sein', 'Key and value must not be empty'));
      return;
    }
    try {
      const res = await apiFetch('/api/vault/entries', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, value })
      });
      const data = await res.json();
      if (res.ok) {
        setVaultStatus(tr('✓ Gespeichert', '✓ Saved'));
        setVaultNewKey('');
        setVaultNewValue('');
        loadVaultEntries();
      } else {
        setVaultStatus(tr('Fehler: ', 'Error: ') + (data.error || ''));
      }
    } catch (err) {
      setVaultStatus('Error: ' + err.message);
    }
  };

  const deleteVaultEntry = async (key) => {
    if (!confirm(tr(`"${key}" wirklich löschen?`, `Really delete "${key}"?`))) return;
    try {
      const res = await apiFetch(`/api/vault/entries/${encodeURIComponent(key)}`, { method: 'DELETE' });
      if (res.ok) {
        setVaultStatus(tr('✓ Gelöscht', '✓ Deleted'));
        loadVaultEntries();
      } else {
        const data = await res.json();
        setVaultStatus(tr('Fehler: ', 'Error: ') + (data.error || ''));
      }
    } catch (err) {
      setVaultStatus('Error: ' + err.message);
    }
  };

  const toggleReveal = (key) => {
    setVaultRevealed(prev => ({ ...prev, [key]: !prev[key] }));
  };

  useEffect(() => {
    loadVaultEntries();
  // Load vault metadata once when the tab mounts.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="settings-panel">
      <div className="panel-section">
        <div className="section-title">{tr('Tresor', 'Vault')}</div>
        <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
          {tr('Gespeicherte Zugangsdaten und Konfigurationswerte. Diese werden vom System für Verbindungen zu Diensten genutzt.', 'Stored credentials and configuration values. These are used by the system for connections to services.')}
        </p>

        <div style={{display: 'flex', gap: '0.5rem', marginBottom: '1rem', flexWrap: 'wrap', alignItems: 'flex-end'}}>
          <div className="input-group" style={{flex: '1 1 200px', marginBottom: 0}}>
            <label style={{fontSize: '0.8rem'}}>{tr('Key', 'Key')}</label>
            <input type="text" value={vaultNewKey} onChange={(e) => setVaultNewKey(e.target.value)}
              placeholder={tr('z.B. mydienst/api-key', 'e.g. myservice/api-key')} />
          </div>
          <div className="input-group" style={{flex: '1 1 250px', marginBottom: 0}}>
            <label style={{fontSize: '0.8rem'}}>{tr('Wert', 'Value')}</label>
            <input type="text" value={vaultNewValue} onChange={(e) => setVaultNewValue(e.target.value)}
              placeholder={tr('Wert eingeben', 'Enter value')} />
          </div>
          <button className="btn primary" onClick={addVaultEntry} style={{height: 'fit-content'}}>
            <i className="fas fa-plus" style={{marginRight: '0.4rem'}}></i>
            {tr('Hinzufügen', 'Add')}
          </button>
        </div>

        {vaultStatus && <div className="status-text" style={{marginBottom: '0.75rem'}}>{vaultStatus}</div>}

        {vaultEntries.length === 0 ? (
          <p style={{color: 'var(--muted)'}}>{tr('Keine Einträge im Tresor.', 'No entries in the vault.')}</p>
        ) : (() => {
          const groups = {};
          for (const entry of vaultEntries) {
            const slashIdx = entry.key.indexOf('/');
            const group = slashIdx > 0 ? entry.key.slice(0, slashIdx) : tr('Allgemein', 'General');
            if (!groups[group]) groups[group] = [];
            groups[group].push(entry);
          }
          return Object.entries(groups).map(([groupName, entries]) => (
            <div key={groupName} style={{marginBottom: '1.25rem'}}>
              <div style={{
                fontSize: '0.85rem', fontWeight: '700', textTransform: 'uppercase',
                letterSpacing: '0.05em', color: 'var(--muted)', marginBottom: '0.6rem',
                paddingBottom: '0.3rem', borderBottom: '1px solid var(--line)'
              }}>
                <i className={`fas ${groupName === tr('Allgemein', 'General') ? 'fa-folder' : 'fa-cube'}`}
                  style={{marginRight: '0.4rem', fontSize: '0.75rem'}}></i>
                {groupName}
                <span style={{fontWeight: '400', fontSize: '0.75rem', marginLeft: '0.4rem'}}>({entries.length})</span>
              </div>
              <div style={{display: 'flex', flexDirection: 'column', gap: '0.35rem'}}>
                {entries.map(entry => (
                  <div key={entry.key} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '0.5rem 0.7rem', background: 'var(--background)',
                    borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', fontSize: '0.875rem'
                  }}>
                    <div style={{display: 'flex', alignItems: 'center', gap: '0.6rem', overflow: 'hidden', flex: 1}}>
                      <span style={{
                        fontWeight: '500', fontSize: '0.8rem', color: 'var(--muted)',
                        minWidth: '80px', flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis'
                      }}>
                        {entry.key.slice(groupName.length + 1)}
                      </span>
                      <span style={{
                        fontFamily: 'monospace', fontSize: '0.82rem', color: 'var(--text)',
                        overflow: 'hidden', textOverflow: 'ellipsis'
                      }}>
                        {vaultRevealed[entry.key] ? entry.value : '••••••••'}
                      </span>
                      <button className="btn" style={{padding: '0.15rem 0.4rem', fontSize: '0.7rem', flexShrink: 0}}
                        onClick={() => toggleReveal(entry.key)}
                        title={vaultRevealed[entry.key] ? tr('Verstecken', 'Hide') : tr('Anzeigen', 'Show')}>
                        <i className={`fas fa-eye${vaultRevealed[entry.key] ? '-slash' : ''}`}></i>
                      </button>
                    </div>
                    <button className="btn secondary" style={{padding: '0.2rem 0.5rem', fontSize: '0.75rem', flexShrink: 0, marginLeft: '0.5rem'}}
                      onClick={() => deleteVaultEntry(entry.key)}>
                      <i className="fas fa-trash-alt" style={{fontSize: '0.75rem'}}></i>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          ));
        })()}
      </div>
    </div>
  );
}
