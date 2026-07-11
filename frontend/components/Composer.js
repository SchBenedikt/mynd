'use client';

const SOURCE_OPTIONS = [
  { value: 'auto', icon: 'fa-globe', label: 'Auto' },
  { value: 'web', icon: 'fa-globe', label: 'Web' },
  { value: 'deep', icon: 'fa-magnifying-glass', label: 'Deep' },
  { value: 'local', icon: 'fa-database', label: 'Lokal' }
];

export default function Composer({
  inputValue, setInputValue, inputRef,
  canSend, queueReady, isThinking, isListening,
  voiceStatusText, source, setSource,
  model, setModel, aiModels,
  onSend, onStartVoiceInput, tr,
  fileInputRef, onFileUpload,
  uploadedFiles, setUploadedFiles,
  onRemoveUploadedFile
}) {
  const handleFileSelect = async (e) => {
    const files = Array.from(e.target.files || []);
    if (onFileUpload) {
      await onFileUpload(files);
    }
    e.target.value = '';
  };
  return (
    <div className="composer-shell">
      {(isThinking || voiceStatusText || (uploadedFiles?.length > 0)) && (
        <div className="composer-hint">
          {isThinking && <span id="thinking-text">Anfrage läuft · Strg+C zum Abbrechen</span>}
          {isThinking && voiceStatusText ? ' | ' : ''}
          {voiceStatusText}
          {uploadedFiles?.length > 0 && (
            <span style={{marginLeft: 8, color: '#6c8'}}>
              <i className="fas fa-paperclip"></i> {uploadedFiles.length} Datei{uploadedFiles.length !== 1 ? 'en' : ''}
            </span>
          )}
        </div>
      )}
      <div className="source-toggle-row">
        {SOURCE_OPTIONS.map(opt => (
          <button key={opt.value}
            className={`source-btn ${source === opt.value ? 'active' : ''}`}
            onClick={() => setSource(opt.value)}
            title={tr(opt.desc || '', '')}>
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
      <div className={`composer ${isThinking ? 'is-thinking' : ''}${inputValue.trim() ? ' has-text' : ''}`}>
        <input
          type="text"
          ref={inputRef}
          value={inputValue}
          placeholder={''}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && !e.ctrlKey && onSend(e.target.value)}
        />
        <button
          type="button"
          className="upload-btn"
          onClick={() => fileInputRef?.current?.click()}
          disabled={isThinking}
          title={'Datei anhängen'}
        >
          <i className="fas fa-paperclip"></i>
        </button>
        <input
          type="file"
          ref={fileInputRef}
          style={{display: 'none'}}
          onChange={handleFileSelect}
          multiple
        />
        <button
          type="button"
          className={`voice-btn ${isListening ? 'listening' : ''}`}
          onClick={onStartVoiceInput}
          disabled={false}
          title={isListening ? 'Aufnahme stoppen' : 'Mit Sprache sprechen'}
        >
          <i className={`fas ${isListening ? 'fa-wave-square' : 'fa-microphone'}`}></i>
        </button>
        <button
          onClick={() => onSend(inputRef.current?.value || '')}
          disabled={!canSend}
          className={queueReady ? 'queue-ready' : ''}
          title={queueReady ? 'In die Warteschlange' : undefined}
        >
          <i className={`fas ${queueReady ? 'fa-arrow-up' : 'fa-arrow-right'}`}></i>
          {queueReady && <span className="queue-tooltip">In die Warteschlange</span>}
        </button>
      </div>
    </div>
  );
}
