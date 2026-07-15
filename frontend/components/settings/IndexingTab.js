'use client';

import { useState, useEffect } from 'react';
import { apiFetch, getApiBase } from '../../lib/api';

const API_BASE = () => getApiBase();
const EMAIL_INDEXING_ENABLED = false;

export default function IndexingTab({ tr, language }) {
  const [ncUrl, setNcUrl] = useState('');
  const [ncUser, setNcUser] = useState('');
  const [ncPassword, setNcPassword] = useState('');
  const [ncPasswordSet, setNcPasswordSet] = useState(false);
  const [ncConfigStatus, setNcConfigStatus] = useState('');
  const [indexingProgress, setIndexingProgress] = useState(0);
  const [indexingStatus, setIndexingStatus] = useState('idle');
  const [indexingStats, setIndexingStats] = useState('');
  const [indexingDetails, setIndexingDetails] = useState({ currentFile: '', processedFiles: 0, totalFiles: 0, elapsedTime: 0, errors: [], chunksCreated: 0, documentsProcessed: 0, processingSpeed: 0, estimatedTimeRemaining: 0, lastIndexingStart: 0, lastIndexingEnd: 0, lastIndexingDuration: 0 });
  const [indexingPath, setIndexingPath] = useState('');
  const [indexingPathStatus, setIndexingPathStatus] = useState('');
  const [persistentIndexStats, setPersistentIndexStats] = useState({ db_stats: {}, indexing_runs: [] });

  const loadNcConfig = async () => {
    try {
      const res = await apiFetch('/api/indexing/config');
      if (res.ok) {
        const data = await res.json();
        setNcUrl(data.url || '');
        setNcUser(data.username || '');
        setNcPasswordSet(Boolean(data.password === '***'));
        setNcPassword('');
      }
    } catch (err) {
      console.error('Error loading Nextcloud config:', err);
    }
  };

  const saveNcConfig = async () => {
    try {
      setNcConfigStatus(tr('Speichere...', 'Saving...'));
      const res = await apiFetch('/api/indexing/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: ncUrl.trim(),
          username: ncUser.trim(),
          password: ncPassword
        })
      });
      if (res.ok) {
        setNcPasswordSet(Boolean(ncPassword));
        setNcPassword('');
        setNcConfigStatus(tr('✓ Konfiguration gespeichert', '✓ Configuration saved'));
      } else {
        const data = await res.json();
        setNcConfigStatus(tr('Fehler: ', 'Error: ') + (data.error || ''));
      }
    } catch (err) {
      setNcConfigStatus('Error: ' + err.message);
    }
  };

  const loadIndexingConfig = async () => {
    try {
      const res = await apiFetch('/api/indexing/path');
      if (res.ok) {
        const data = await res.json();
        setIndexingPath(data.path || '');
      }
    } catch (err) {
      console.error('Error loading indexing path:', err);
    }
  };

  const saveIndexingConfig = async () => {
    try {
      const res = await apiFetch('/api/indexing/path', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: indexingPath })
      });
      if (res.ok) {
        setIndexingPathStatus(tr('✓ Pfad gespeichert', '✓ Path saved'));
      } else {
        const data = await res.json();
        setIndexingPathStatus(tr('Fehler: ', 'Error: ') + (data.error || 'Unknown error'));
      }
    } catch (err) {
      setIndexingPathStatus('Error: ' + err.message);
    }
  };

  const loadIndexingStats = async () => {
    try {
      const res = await apiFetch('/api/indexing/stats');
      if (res.ok) {
        const data = await res.json();
        setPersistentIndexStats(data || {});
      }
    } catch (err) {
      // ignore transient errors
    }
  };

  const startIndexing = async () => {
    try {
      const configRes = await apiFetch('/api/indexing/config');
      if (configRes.ok) {
        const config = await configRes.json();
        if (!config.url || !config.username) {
          setIndexingStatus('error: Nextcloud configuration required. Please configure your Nextcloud connection first.');
          return;
        }
      }
      const res = await apiFetch('/api/indexing/start', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: indexingPath || undefined })
      });
      if (res.ok) {
        setIndexingStatus('running');
        const progressInterval = setInterval(async () => {
          try {
            const res = await apiFetch('/api/indexing/progress');
            if (res.ok) {
              const data = await res.json();
              setIndexingProgress(Math.round(data.progress_percentage || 0));
              const processingSpeed = data.elapsed_time > 0 ? (data.processed_files / data.elapsed_time).toFixed(1) : 0;
              const timeRemaining = data.progress_percentage > 0 && data.elapsed_time > 0
                ? Math.round((data.elapsed_time / data.progress_percentage) * (100 - data.progress_percentage))
                : 0;
              setIndexingDetails({
                currentFile: data.current_file || '',
                processedFiles: data.processed_files || 0,
                totalFiles: data.total_files || 0,
                elapsedTime: Math.round(data.elapsed_time) || 0,
                errors: data.errors || [],
                chunksCreated: 0,
                documentsProcessed: data.processed_files || 0,
                processingSpeed: parseFloat(processingSpeed),
                estimatedTimeRemaining: timeRemaining,
                lastIndexingStart: data.last_indexing_start || 0,
                lastIndexingEnd: data.last_indexing_end || 0,
                lastIndexingDuration: data.last_indexing_duration || 0
              });
              setIndexingStats(
                `${data.processed_files || 0}/${data.total_files || 0} files | ${Math.round(data.elapsed_time || 0)}s elapsed | ${processingSpeed} files/s | ${timeRemaining > 0 ? `~${timeRemaining}s remaining` : 'calculating...'}`
              );
              if (data.status === 'completed' || data.status === 'error') {
                setIndexingStatus(data.status);
                if (data.status === 'completed') {
                  setIndexingDetails(prev => ({ ...prev, chunksCreated: data.processed_files * 10 }));
                }
                clearInterval(progressInterval);
              }
            } else if (res.status === 500) {
              setIndexingStatus('error: Server error');
              clearInterval(progressInterval);
            } else {
              setIndexingStatus(`error: ${res.status}`);
              clearInterval(progressInterval);
            }
          } catch (err) {
            if (err.message.includes('JSON')) {
              setIndexingStatus('error: Invalid response from server');
              clearInterval(progressInterval);
            }
          }
        }, 500);
      } else {
        const data = await res.json();
        setIndexingStatus('error: ' + data.error);
      }
    } catch (err) {
      setIndexingStatus('error: ' + err.message);
    }
  };

  useEffect(() => {
    loadIndexingConfig();
    loadNcConfig();
    loadIndexingStats();
    const statsInterval = setInterval(() => {
      loadIndexingStats();
    }, 10000);
    return () => clearInterval(statsInterval);
  }, []);

  return (
    <div className="settings-panel">
      <div className="panel-section">
        <div className="section-title">{tr('Nextcloud-Verbindung', 'Nextcloud Connection')}</div>
        <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
          {tr('Die Zugangsdaten werden im Tresor gespeichert und von der Indexierung verwendet.', 'Credentials are stored in the vault and used by the indexing engine.')}
        </p>
        <div className="input-group">
          <label>{tr('Nextcloud-URL', 'Nextcloud URL')}</label>
          <input type="text" value={ncUrl} onChange={(e) => setNcUrl(e.target.value)}
            placeholder="https://cloud.example.com" />
        </div>
        <div className="input-group">
          <label>{tr('Benutzername', 'Username')}</label>
          <input type="text" value={ncUser} onChange={(e) => setNcUser(e.target.value)}
            placeholder={tr('z.B. admin', 'e.g. admin')} />
        </div>
        <div className="input-group">
          <label>{tr('Passwort / App-Passwort', 'Password / App Password')}</label>
          <input type="password" value={ncPassword} onChange={(e) => setNcPassword(e.target.value)}
            placeholder={ncPasswordSet ? tr('******** (neu eingeben zum Ändern)', '******** (enter new to change)') : tr('Passwort eingeben', 'Enter password')} />
        </div>
        <div className="button-group">
          <button className="btn primary" onClick={saveNcConfig}>{tr('Verbindung speichern', 'Save Connection')}</button>
        </div>
        {ncConfigStatus && <div className="status-text">{ncConfigStatus}</div>}
      </div>

      {EMAIL_INDEXING_ENABLED && <div className="panel-section" style={{marginTop: '2rem'}}>
        <div className="section-title">{tr('E-Mail-Indexierung', 'Email Indexing')}</div>
        <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
          {tr('Indiziere E-Mails für die semantische Suche.', 'Index emails for semantic search.')}
        </p>
        <div style={{display: 'flex', gap: '0.75rem', flexWrap: 'wrap'}}>
          <button className="btn primary" onClick={async () => {
            try {
              const r = await apiFetch('/api/email-indexing/start', {method: 'POST'});
              const d = await r.json();
              if(d.success) alert(tr('E-Mail-Indexierung gestartet!', 'Email indexing started!'));
            } catch(e) { alert('Error: '+e.message); }
          }}>
            <i className="fas fa-sync" style={{marginRight: 6}}></i>
            {tr('Jetzt indizieren', 'Index Now')}
          </button>
          <button className="btn secondary" onClick={async () => {
            await apiFetch('/api/email-indexing/stop', {method: 'POST'});
          }}>
            {tr('Stoppen', 'Stop')}
          </button>
        </div>
      </div>}

      <div className="panel-section" style={{marginTop: '2rem'}}>
        <div className="section-title">{tr('Dokumenten-Indexierung', 'Document Indexing')}</div>
        <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
          {tr('Indexiere deine Dokumente aus Nextcloud für die semantische Suche.', 'Index your documents from Nextcloud for semantic search.')}
        </p>
        <div style={{display: 'flex', gap: '0.75rem', marginBottom: '1rem', flexWrap: 'wrap'}}>
          <div style={{padding: '0.6rem 0.8rem', background: 'var(--background)', borderRadius: 'var(--radius)', border: '1px solid var(--line)'}}>
            <div style={{fontSize: '0.95rem', fontWeight: '700'}}>{persistentIndexStats?.db_stats?.documents || 0}</div>
            <div style={{fontSize: '0.75rem', color: 'var(--muted)'}}>{tr('Dokumente indexiert', 'Documents indexed')}</div>
          </div>
          <div style={{padding: '0.6rem 0.8rem', background: 'var(--background)', borderRadius: 'var(--radius)', border: '1px solid var(--line)'}}>
            <div style={{fontSize: '0.95rem', fontWeight: '700'}}>{persistentIndexStats?.db_stats?.chunks || 0}</div>
            <div style={{fontSize: '0.75rem', color: 'var(--muted)'}}>{tr('Chunks insgesamt', 'Total chunks')}</div>
          </div>
          <div style={{padding: '0.6rem 0.8rem', background: 'var(--background)', borderRadius: 'var(--radius)', border: '1px solid var(--line)'}}>
            <div style={{fontSize: '0.95rem', fontWeight: '700'}}>{persistentIndexStats?.db_stats?.embeddings || 0}</div>
            <div style={{fontSize: '0.75rem', color: 'var(--muted)'}}>{tr('Embeddings', 'Embeddings')}</div>
          </div>
          {persistentIndexStats?.indexing_runs?.length > 0 && (
            <div style={{padding: '0.6rem 0.8rem', background: 'var(--background)', borderRadius: 'var(--radius)', border: '1px solid var(--line)'}}>
              <div style={{fontSize: '0.75rem', color: 'var(--muted)'}}>Letzte Indexierung</div>
              <div style={{fontSize: '0.8rem'}}>{new Date((persistentIndexStats.indexing_runs[0].ended_at || 0) * 1000).toLocaleString('de-DE')}</div>
            </div>
          )}
        </div>

        <div className="input-group">
          <label>{tr('Indexierungs-Pfad (optional)', 'Indexing Path (optional)')}</label>
          <input type="text" value={indexingPath} onChange={(e) => setIndexingPath(e.target.value)}
            placeholder={tr('z.B. /Documents', 'e.g. /Documents')} />
          <small style={{color: 'var(--muted)', display: 'block', marginTop: '0.25rem'}}>
            {tr('Spezifischer Pfad in der Nextcloud, der indexiert werden soll. Leer lassen für alle Dateien.', 'Specific path in Nextcloud to index. Leave empty to index all files.')}
          </small>
        </div>

        <div className="button-group">
          <button className="btn primary" onClick={saveIndexingConfig}>
            {tr('Pfad speichern', 'Save Path')}
          </button>
        </div>
        {indexingPathStatus && <div className="status-text">{indexingPathStatus}</div>}

        <div className="button-group" style={{marginTop: '1.5rem'}}>
          <button className="btn primary" onClick={startIndexing} disabled={indexingStatus === 'running'}>
            {indexingStatus === 'running' ? tr('Indexierung läuft...', 'Indexing...') : tr('Indexierung starten', 'Start Indexing')}
          </button>
          {indexingStatus === 'running' && (
            <button className="btn secondary" onClick={() => apiFetch('/api/indexing/stop', {method: 'POST'})}>
              {tr('Stoppen', 'Stop')}
            </button>
          )}
        </div>

        {(indexingStatus !== 'idle' || indexingDetails.processedFiles > 0) && (
          <div style={{marginTop: '1.5rem', padding: '1rem', background: 'var(--surface)', borderRadius: 'var(--radius)', border: '1px solid var(--border)'}}>
            <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem'}}>
              <h4 style={{margin: 0, fontSize: '1rem', fontWeight: '600'}}>
                <i className="fas fa-chart-line" style={{marginRight: '0.5rem'}}></i>
                {tr('Indexierungsfortschritt', 'Indexing Progress')}
              </h4>
              <span style={{
                fontSize: '0.8rem', padding: '0.25rem 0.75rem', borderRadius: 'var(--radius-full)',
                background: indexingStatus === 'running' ? 'var(--primary)' :
                  indexingStatus === 'completed' ? 'var(--success)' :
                  indexingStatus === 'error' ? 'var(--error)' : 'var(--muted)',
                color: 'white', fontWeight: '500'
              }}>
                {indexingStatus.toUpperCase()}
              </span>
            </div>

            {indexingStatus === 'running' && (
              <div className="progress-bar-wrapper" style={{marginBottom: '1rem'}}>
                <div className="progress-bar" style={{height: '8px', background: 'var(--border)', borderRadius: 'var(--radius-sm)', overflow: 'hidden'}}>
                  <div className="progress-fill" style={{
                    height: '100%', background: 'linear-gradient(90deg, var(--primary), var(--primary-light))',
                    transition: 'width 0.5s ease', width: `${indexingProgress}%`, borderRadius: 'var(--radius-sm)'
                  }}></div>
                </div>
                <div style={{display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--muted)', marginTop: '0.5rem'}}>
                  <span>{indexingProgress}% {tr('abgeschlossen', 'Complete')}</span>
                  <span>{indexingDetails.processedFiles} / {indexingDetails.totalFiles} {tr('Dateien', 'files')}</span>
                </div>
              </div>
            )}

            <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem', marginBottom: '1rem'}}>
              <div style={{textAlign: 'center', padding: '0.75rem', background: 'var(--background)', borderRadius: 'var(--radius-sm)'}}>
                <div style={{fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--primary)'}}>{indexingDetails.processedFiles}</div>
                <div style={{fontSize: '0.75rem', color: 'var(--muted)'}}>{tr('Dateien verarbeitet', 'Files Processed')}</div>
              </div>
              <div style={{textAlign: 'center', padding: '0.75rem', background: 'var(--background)', borderRadius: 'var(--radius-sm)'}}>
                <div style={{fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--success)'}}>{indexingDetails.processingSpeed}</div>
                <div style={{fontSize: '0.75rem', color: 'var(--muted)'}}>{tr('Dateien/Sekunde', 'Files/Second')}</div>
              </div>
              <div style={{textAlign: 'center', padding: '0.75rem', background: 'var(--background)', borderRadius: 'var(--radius-sm)'}}>
                <div style={{fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--accent)'}}>
                  {Math.floor(indexingDetails.elapsedTime / 60)}:{(indexingDetails.elapsedTime % 60).toString().padStart(2, '0')}
                </div>
                <div style={{fontSize: '0.75rem', color: 'var(--muted)'}}>{tr('Verstrichene Zeit', 'Time Elapsed')}</div>
              </div>
              <div style={{textAlign: 'center', padding: '0.75rem', background: 'var(--background)', borderRadius: 'var(--radius-sm)'}}>
                <div style={{fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--warning)'}}>
                  {indexingDetails.estimatedTimeRemaining > 0 ? `${Math.floor(indexingDetails.estimatedTimeRemaining / 60)}:${(indexingDetails.estimatedTimeRemaining % 60).toString().padStart(2, '0')}` : '--:--'}
                </div>
                <div style={{fontSize: '0.75rem', color: 'var(--muted)'}}>{tr('Restzeit', 'Time Remaining')}</div>
              </div>
            </div>

            {indexingDetails.currentFile && (
              <div style={{marginBottom: '1rem', padding: '0.75rem', background: 'var(--background)', borderRadius: 'var(--radius-sm)', fontSize: '0.85rem'}}>
                <div style={{fontWeight: '600', marginBottom: '0.25rem', color: 'var(--text)'}}>
                  <i className="fas fa-file-alt" style={{marginRight: '0.5rem'}}></i>
                  {tr('Wird gerade verarbeitet:', 'Currently Processing:')}
                </div>
                <div style={{color: 'var(--muted)', wordBreak: 'break-all'}}>{indexingDetails.currentFile}</div>
              </div>
            )}

            <div style={{fontSize: '0.8rem', color: 'var(--muted)'}}>
              {indexingStats && <div style={{marginBottom: '0.5rem', fontWeight: '500'}}>{indexingStats}</div>}
              <div style={{display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem'}}>
                <span><strong>{tr('Dokumente', 'Documents')}:</strong> {indexingDetails.documentsProcessed}</span>
                <span><strong>{tr('Chunks erstellt', 'Chunks Created')}:</strong> ~{indexingDetails.chunksCreated}</span>
                {indexingDetails.errors.length > 0 && (
                  <span style={{color: 'var(--error)'}}><strong>{tr('Fehler', 'Errors')}:</strong> {indexingDetails.errors.length}</span>
                )}
              </div>

              {indexingDetails.lastIndexingEnd > 0 && (
                <div style={{marginTop: '1rem', padding: '0.75rem', background: 'var(--background)', borderRadius: 'var(--radius-sm)', fontSize: '0.8rem'}}>
                  <div style={{fontWeight: '600', marginBottom: '0.5rem', color: 'var(--text)'}}>
                    <i className="fas fa-history" style={{marginRight: '0.5rem'}}></i>
                    Letzte Indexierung:
                  </div>
                  <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.5rem', color: 'var(--muted)'}}>
                    <div><strong>Start:</strong> {new Date(indexingDetails.lastIndexingStart * 1000).toLocaleString('de-DE')}</div>
                    <div><strong>Ende:</strong> {new Date(indexingDetails.lastIndexingEnd * 1000).toLocaleString('de-DE')}</div>
                    <div><strong>Dauer:</strong> {Math.round(indexingDetails.lastIndexingDuration)}s</div>
                  </div>
                </div>
              )}
            </div>

            {indexingDetails.errors.length > 0 && (
              <div style={{marginTop: '1rem', padding: '0.75rem', background: 'var(--error-bg)', border: '1px solid var(--error)', borderRadius: 'var(--radius-sm)'}}>
                <div style={{fontWeight: '600', marginBottom: '0.5rem', color: 'var(--error)'}}>
                  <i className="fas fa-exclamation-triangle" style={{marginRight: '0.5rem'}}></i>
                  {tr('Letzte Fehler:', 'Recent Errors:')}
                </div>
                <div style={{fontSize: '0.75rem', color: 'var(--error)', maxHeight: '100px', overflowY: 'auto'}}>
                  {indexingDetails.errors.slice(-3).map((error, index) => (
                    <div key={index} style={{marginBottom: '0.25rem'}}>• {error}</div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
