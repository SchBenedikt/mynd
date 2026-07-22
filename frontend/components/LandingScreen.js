'use client';

import { useState } from 'react';
import './LandingScreen.css';

const SOURCE_OPTIONS = [
  { value: 'auto', icon: 'fa-globe', label: { en: 'Auto', de: 'Auto' } },
  { value: 'web', icon: 'fa-globe', label: { en: 'Web', de: 'Web' } },
  { value: 'deep', icon: 'fa-magnifying-glass', label: { en: 'Deep', de: 'Tief' } },
  { value: 'local', icon: 'fa-database', label: { en: 'Local', de: 'Lokal' } }
];

const SUGGESTIONS = [
  { icon: 'fa-cloud-sun', en: 'What\'s the weather today?', de: 'Wie wird das Wetter heute?' },
  { icon: 'fa-calendar-day', en: 'Schedule a meeting for tomorrow', de: 'Erstelle einen Termin für morgen' },
  { icon: 'fa-envelope', en: 'Check my emails', de: 'Prüfe meine E-Mails' },
  { icon: 'fa-brain', en: 'Summarize the latest news', de: 'Fasse die aktuellen News zusammen' },
  { icon: 'fa-image', en: 'Show photos from last week', de: 'Zeige Fotos von letzter Woche' },
  { icon: 'fa-file-lines', en: 'Help me write a draft', de: 'Hilf mir einen Entwurf zu schreiben' },
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
  const [showSuggestions, setShowSuggestions] = useState(true);

  const handleSuggestion = (text) => {
    setInputValue(text);
    if (inputRef.current) inputRef.current.value = text;
    setTimeout(() => onSend(text), 50);
  };

  const l = (obj) => obj[language] || obj.en;

  return (
    <div className="landing">
      <div className="landing-glow" />
      <div className="landing-brand">
        <span className="landing-brand-icon">◆</span>
        <span className="landing-brand-text">MYND</span>
      </div>

      <div className="landing-greeting">
        {personalGreeting && (
          <div className="landing-greeting-text">{personalGreeting}</div>
        )}
        <div className="landing-tagline">{t('tagline')}</div>
      </div>

      <div className="landing-input-section">
        <div className="source-toggle-row">
          {SOURCE_OPTIONS.map(opt => (
            <button key={opt.value}
              className={`source-btn ${source === opt.value ? 'active' : ''}`}
              onClick={() => setSource(opt.value)}
              title={l(opt.label)}>
              <i className={`fas ${opt.icon}`}></i>
              {l(opt.label)}
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
            onKeyDown={(e) => e.key === 'Enter' && onSend(e.target.value)}
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

      {showSuggestions && (
        <div className="landing-suggestions">
          <div className="landing-suggestions-header">
            <span>{t('suggestions')}</span>
            <button className="landing-suggestions-hide" onClick={() => setShowSuggestions(false)} title={language === 'de' ? 'Ausblenden' : 'Hide'}>
              <i className="fas fa-times"></i>
            </button>
          </div>
          <div className="landing-suggestions-grid">
            {SUGGESTIONS.map((s, i) => (
              <button key={i} className="landing-suggestion-card" onClick={() => handleSuggestion(l({ en: s.en, de: s.de }))}>
                <i className={`fas ${s.icon}`}></i>
                <span>{l({ en: s.en, de: s.de })}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="landing-features">
        <div className="landing-feature">
          <i className="fas fa-robot"></i>
          <div className="landing-feature-text">
            <strong>{t('multiModel')}</strong>
            <span>{t('multiModelDesc')}</span>
          </div>
        </div>
        <div className="landing-feature">
          <i className="fas fa-plug"></i>
          <div className="landing-feature-text">
            <strong>{t('integrations')}</strong>
            <span>{t('integrationsDesc')}</span>
          </div>
        </div>
        <div className="landing-feature">
          <i className="fas fa-lock"></i>
          <div className="landing-feature-text">
            <strong>{t('privacy')}</strong>
            <span>{t('privacyDesc')}</span>
          </div>
        </div>
      </div>

      <div className="landing-shortcuts">
        <span><kbd>⌘K</kbd> {t('search')}</span>
        <span><kbd>⌘⏎</kbd> {t('send')}</span>
        <span><kbd>⌘⇧F</kbd> {t('files')}</span>
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
