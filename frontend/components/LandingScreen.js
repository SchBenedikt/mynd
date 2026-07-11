'use client';

import './LandingScreen.css';

const SOURCE_OPTIONS = [
  { value: 'auto', icon: 'fa-globe', label: 'Auto' },
  { value: 'web', icon: 'fa-globe', label: 'Web' },
  { value: 'deep', icon: 'fa-magnifying-glass', label: 'Deep' },
  { value: 'local', icon: 'fa-database', label: 'Lokal' }
];

export default function LandingScreen({
  personalGreeting, t, language, chats,
  inputValue, setInputValue, inputRef,
  canSend, isListening,
  onSend, onStartVoiceInput,
  indexingStatus, indexingProgress, indexingDetails, indexingStats,
  source, setSource,
  model, setModel, aiModels
}) {
  return (
    <div className="landing">
      <div className="landing-brand">◆ MYND</div>
      <div className="landing-input-section">
        <div className="source-toggle-row">
          {SOURCE_OPTIONS.map(opt => (
            <button key={opt.value}
              className={`source-btn ${source === opt.value ? 'active' : ''}`}
              onClick={() => setSource(opt.value)}
              title={opt.label}>
              <i className={`fas ${opt.icon}`}></i>
              {opt.label}
            </button>
          ))}
          <div className="composer-model-wrapper">
            <i className="fas fa-microchip"></i>
            <select className="composer-model-select" value={model} onChange={e => setModel(e.target.value)}>
              {aiModels.length > 0 ? aiModels.map(m => (
                <option key={m.name || m} value={m.name || m}>{m.name || m}</option>
              )) : (
                <option value={model}>{model || 'Modell'}</option>
              )}
            </select>
          </div>
        </div>
        <div className="input-wrapper">
          <input
            type="text"
            ref={inputRef}
            value={inputValue}
            placeholder={t('askPlaceholder')}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && onSend(e.target.value)}
          />
          <button type="button" className={`voice-btn ${isListening ? 'listening' : ''}`}
            onClick={onStartVoiceInput}
            disabled={false}
            title={isListening ? 'Aufnahme stoppen' : 'Mit Sprache sprechen'}>
            <i className={`fas ${isListening ? 'fa-wave-square' : 'fa-microphone'}`}></i>
          </button>
          <button onClick={() => onSend(inputRef.current?.value || '')} disabled={!canSend}
            className={''} title={undefined}>
            <i className="fas fa-arrow-right"></i>
          </button>
        </div>
      </div>

      {(indexingStatus !== 'idle' || indexingDetails.processedFiles > 0) && (
        <div className="indexing-panel" style={{marginTop: '2rem', padding: '1rem', background: 'var(--surface)', borderRadius: '8px', border: '1px solid var(--border)'}}>
          <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem'}}>
            <h4 style={{margin: 0, fontSize: '0.9rem', fontWeight: '600'}}>
              <i className="fas fa-database" style={{marginRight: '0.5rem'}}></i>{t('documentIndexing')}
            </h4>
            <span style={{fontSize: '0.8rem', padding: '0.25rem 0.5rem', borderRadius: '4px',
              background: indexingStatus === 'running' ? 'var(--primary)' : indexingStatus === 'completed' ? 'var(--success)' : indexingStatus === 'error' ? 'var(--error)' : 'var(--muted)', color: 'white'}}>
              {indexingStatus}
            </span>
          </div>
          {indexingStatus === 'running' && (
            <div className="progress-bar-wrapper" style={{marginBottom: '0.5rem'}}>
              <div className="progress-bar" style={{height: '4px', background: 'var(--border)', borderRadius: '2px', overflow: 'hidden'}}>
                <div className="progress-fill" style={{height: '100%', background: 'var(--primary)', transition: 'width 0.3s ease', width: `${indexingProgress}%`}}></div>
              </div>
            </div>
          )}
          <div style={{fontSize: '0.8rem', color: 'var(--muted)'}}>
            {indexingStats && <div style={{marginBottom: '0.5rem'}}>{indexingStats}</div>}
            {indexingDetails.currentFile && (<div style={{marginBottom: '0.25rem'}}><strong>{t('current')}:</strong> {indexingDetails.currentFile}</div>)}
            <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.75rem'}}>
              <div><strong>{t('files')}:</strong> {indexingDetails.processedFiles}/{indexingDetails.totalFiles}</div>
              <div><strong>{t('speed')}:</strong> {indexingDetails.processingSpeed} files/s</div>
              <div><strong>{t('elapsed')}:</strong> {indexingDetails.elapsedTime}s</div>
              <div><strong>{t('chunks')}:</strong> ~{indexingDetails.chunksCreated}</div>
            </div>
            {indexingDetails.lastIndexingEnd > 0 && (
              <div style={{marginTop: '0.5rem', padding: '0.5rem', background: 'var(--background)', borderRadius: '4px', fontSize: '0.7rem'}}>
                <div style={{fontWeight: '600', marginBottom: '0.25rem', color: 'var(--text)'}}><i className="fas fa-history" style={{marginRight: '0.25rem'}}></i>Letzte Indexierung:</div>
                <div style={{color: 'var(--muted)'}}>
                  <div><strong>Start:</strong> {new Date(indexingDetails.lastIndexingStart * 1000).toLocaleString('de-DE')}</div>
                  <div><strong>Ende:</strong> {new Date(indexingDetails.lastIndexingEnd * 1000).toLocaleString('de-DE')}</div>
                  <div><strong>Dauer:</strong> {Math.round(indexingDetails.lastIndexingDuration)}s</div>
                </div>
              </div>
            )}
            {indexingDetails.errors.length > 0 && (<div style={{marginTop: '0.5rem', color: 'var(--error)'}}><strong>{t('errors')}:</strong> {indexingDetails.errors.length}</div>)}
          </div>
        </div>
      )}
    </div>
  );
}
