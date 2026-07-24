'use client';

import { useState, useEffect } from 'react';
import { apiFetch } from '../../lib/api';
import {
  getModelBaseName,
  normalizeModelName,
  splitModelOptions,
  uniqueSortedModels
} from '../../lib/modelUtils';

const TTS_PROVIDER_STORAGE_KEY = 'mynd_tts_provider_v1';
const DISPLAY_NAME_STORAGE_KEY = 'mynd_display_name';

const normalizeTtsProvider = (value) => {
  return String(value || '').trim().toLowerCase() === 'gemini' ? 'gemini' : 'browser';
};

const formatVoiceLabel = (voice) => {
  const name = String(voice?.name || '').trim();
  const lang = String(voice?.lang || '').trim();
  if (name && lang) return `${name} (${lang})`;
  return name || lang || 'System Voice';
};

const resolveModelOption = (models, preferredModel) => {
  const uniqueModels = uniqueSortedModels(models);
  const preferredName = normalizeModelName(preferredModel);
  if (!preferredName) return '';

  const exactMatch = uniqueModels.find((model) => model === preferredName);
  if (exactMatch) return exactMatch;

  const preferredBase = getModelBaseName(preferredName);
  const baseMatch = uniqueModels.find((model) => getModelBaseName(model) === preferredBase);
  return baseMatch || preferredName;
};

const geminiVoices = [
  'Achernar', 'Achird', 'Algenib', 'Algieba', 'Alnilam', 'Aoede', 'Autonoe', 'Callirrhoe', 'Charon', 'Despina',
  'Enceladus', 'Erinome', 'Fenrir', 'Gacrux', 'Iapetus', 'Kore', 'Laomedeia', 'Leda', 'Orus', 'Pulcherrima',
  'Puck', 'Rasalgethi', 'Sadachbia', 'Sadaltager', 'Schedar', 'Sulafat', 'Umbriel', 'Vindemiatrix', 'Zephyr', 'Zubenelgenubi'
];

export default function ConfigTab({ tr, language }) {
  const [aiProtocol, setAiProtocol] = useState('http');
  const [aiHost, setAiHost] = useState('127.0.0.1');
  const [aiPort, setAiPort] = useState('11434');
  const [aiModel, setAiModel] = useState('');
  const [aiModels, setAiModels] = useState([]);
  const [aiProvider, setAiProvider] = useState('ollama');
  const [openaiBaseUrl, setOpenaiBaseUrl] = useState('');
  const [openaiApiKey, setOpenaiApiKey] = useState('');
  const [openaiApiKeySet, setOpenaiApiKeySet] = useState(false);
  const [embeddingModel, setEmbeddingModel] = useState('nomic-embed-text');
  const [aiStatus, setAiStatus] = useState('');
  const [modelCheckResults, setModelCheckResults] = useState(null);
  const [modelCheckLoading, setModelCheckLoading] = useState(false);
  const [securityMode, setSecurityModeState] = useState('standard');
  const [securityModeStatus, setSecurityModeStatus] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [speechSynthesisSupported, setSpeechSynthesisSupported] = useState(false);
  const [availableVoices, setAvailableVoices] = useState([]);
  const [selectedVoiceUri, setSelectedVoiceUri] = useState('');
  const [ttsProvider, setTtsProvider] = useState('browser');
  const [geminiTtsModel, setGeminiTtsModel] = useState('gemini-2.5-flash-tts');
  const [geminiTtsVoice, setGeminiTtsVoice] = useState('Kore');
  const [geminiTtsLanguageCode, setGeminiTtsLanguageCode] = useState('de-DE');
  const [geminiTtsStylePrompt, setGeminiTtsStylePrompt] = useState('');
  const [geminiTtsAudioEncoding, setGeminiTtsAudioEncoding] = useState('MP3');
  const [geminiTtsApiKey, setGeminiTtsApiKey] = useState('');
  const [geminiTtsApiKeySet, setGeminiTtsApiKeySet] = useState(false);
  const [factoryResetStep, setFactoryResetStep] = useState('idle');
  const [factoryResetPassword, setFactoryResetPassword] = useState('');
  const [factoryResetLoading, setFactoryResetLoading] = useState(false);
  const [factoryResetMessage, setFactoryResetMessage] = useState('');
  const [embeddingCoverage, setEmbeddingCoverage] = useState(null);
  const [backupMsg, setBackupMsg] = useState('');
  const [backupLoading, setBackupLoading] = useState(false);
  const [backupImportMsg, setBackupImportMsg] = useState('');
  const [backendUrl, setBackendUrlState] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('backendUrl');
      if (saved) return saved;
      try {
        const u = new URL(window.location.href);
        if (u.hostname !== 'localhost' && u.hostname !== '127.0.0.1') {
          return `${u.protocol}//${u.hostname}:5001`;
        }
      } catch {}
      return 'http://127.0.0.1:5001';
    }
    return 'http://127.0.0.1:5001';
  });

  const setBackendUrl = (url) => {
    setBackendUrlState(url);
    localStorage.setItem('backendUrl', url);
  };

  const visibleVoices = language === 'de'
    ? availableVoices.filter((voice) => String(voice.lang || '').toLowerCase().startsWith('de'))
    : availableVoices;
  const { chatModels: aiModelOptions, embeddingModels: embeddingModelOptions } = splitModelOptions(aiModels);
  const embeddingCoverageDetail = embeddingCoverage
    ? embeddingCoverage.complete
      ? tr('Alle Embeddings sind generiert.', 'All embeddings are generated.')
      : tr(
          `${embeddingCoverage.missing_embeddings || 0} Embeddings fehlen noch.`,
          `${embeddingCoverage.missing_embeddings || 0} embeddings are still missing.`
        )
    : tr('Embeddings-Status wird geladen...', 'Loading embedding status...');

  const loadAIConfig = async () => {
    try {
      const res = await apiFetch('/api/ai/config');
      const config = await res.json();
      const url = new URL(config.base_url);
      setAiProtocol(url.protocol.replace(':', ''));
      setAiHost(url.hostname);
      setAiPort(url.port || '11434');
      const provider = config.provider || 'ollama';
      setAiProvider(provider);
      if (provider === 'openai') {
        setOpenaiBaseUrl(config.base_url || '');
        setOpenaiApiKeySet(Boolean(config.api_key_set));
        setOpenaiApiKey('');
      } else {
        const url = new URL(config.base_url);
        setAiProtocol(url.protocol.replace(':', ''));
        setAiHost(url.hostname);
        setAiPort(url.port || '11434');
      }
      setAiModel(config.model);
      setEmbeddingModel(String(config.embedding_model || 'nomic-embed-text'));
      const storedTtsProvider = typeof window !== 'undefined' ? window.localStorage.getItem(TTS_PROVIDER_STORAGE_KEY) : '';
      const resolvedTtsProvider = Object.prototype.hasOwnProperty.call(config, 'tts_provider')
        ? normalizeTtsProvider(config.tts_provider)
        : normalizeTtsProvider(storedTtsProvider);
      setTtsProvider(resolvedTtsProvider);
      if (typeof window !== 'undefined') window.localStorage.setItem(TTS_PROVIDER_STORAGE_KEY, resolvedTtsProvider);
      setSelectedVoiceUri(String(config.browser_tts_voice_uri || ''));
      setGeminiTtsModel(String(config.gemini_tts_model || 'gemini-2.5-flash-tts'));
      setGeminiTtsVoice(String(config.gemini_tts_voice || 'Kore'));
      setGeminiTtsLanguageCode(String(config.gemini_tts_language_code || 'de-DE'));
      setGeminiTtsStylePrompt(String(config.gemini_tts_style_prompt || ''));
      setGeminiTtsAudioEncoding(String(config.gemini_tts_audio_encoding || 'MP3'));
      setGeminiTtsApiKeySet(Boolean(config.gemini_tts_api_key_set));
      setGeminiTtsApiKey('');
      setAiStatus(tr('Geladen', 'Loaded'));
    } catch (err) {
      setAiStatus(tr('Fehler beim Laden der Konfiguration', 'Error loading config'));
    }
  };

  const loadOllamaModels = async () => {
    try {
      const res = await apiFetch('/api/ollama/models');
      const data = await res.json();
      setAiModels(Array.isArray(data.models) ? data.models : []);
    } catch (err) {
      console.error('Error loading models:', err);
    }
  };

  const loadEmbeddingStatus = async () => {
    try {
      const kbRes = await apiFetch('/api/knowledge/status');
      const kb = await kbRes.json();
      const totalChunks = Number(kb.chunks_loaded || 0);
      const generatedEmbeddings = Number(kb.generated_embeddings ?? kb.embeddings_count ?? 0);
      const missingEmbeddings = Number(kb.missing_embeddings ?? Math.max(totalChunks - generatedEmbeddings, 0));
      const embeddingsComplete = Boolean(kb.embeddings_complete ?? (totalChunks > 0 && missingEmbeddings === 0));
      setEmbeddingCoverage({
        model: kb.model_name || '',
        total_chunks: totalChunks,
        generated_embeddings: generatedEmbeddings,
        missing_embeddings: missingEmbeddings,
        completion_percentage: Number(kb.completion_percentage || (totalChunks ? Math.round((generatedEmbeddings / totalChunks) * 100) : 0)),
        complete: embeddingsComplete
      });
    } catch (err) {
      setEmbeddingCoverage(null);
    }
  };

  const checkModelToolSupport = async () => {
    setModelCheckLoading(true);
    setModelCheckResults(null);
    try {
      const res = await apiFetch('/api/ai/check-models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          base_url: `${aiProtocol}://${aiHost}:${aiPort}`
        })
      });
      const data = await res.json();
      setModelCheckResults(data);
    } catch (err) {
      setModelCheckResults({ error: err.message });
    } finally {
      setModelCheckLoading(false);
    }
  };

  const loadSecurityMode = async () => {
    try {
      const res = await apiFetch('/api/security/mode');
      const data = await res.json();
      if (data.mode) setSecurityModeState(data.mode);
    } catch (err) {
      console.error('Error loading security mode:', err);
    }
  };

  const setSecurityMode = async (mode) => {
    setSecurityModeState(mode);
    try {
      const res = await apiFetch('/api/security/mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode })
      });
      const data = await res.json();
      if (data.success) {
        setSecurityModeStatus(tr('Gespeichert', 'Saved'));
      } else {
        setSecurityModeStatus(data.error || 'Error');
      }
    } catch (err) {
      setSecurityModeStatus(err.message);
    }
  };

  const saveAIConfig = async () => {
    try {
      let baseUrl, payload;
      if (aiProvider === 'openai') {
        baseUrl = openaiBaseUrl || 'https://api.openai.com/v1';
        payload = {
          provider: 'openai', base_url: baseUrl, model: aiModel, api_key: openaiApiKey,
          embedding_model: embeddingModel,
          tts_provider: ttsProvider, browser_tts_voice_uri: selectedVoiceUri,
          gemini_tts_model: geminiTtsModel, gemini_tts_voice: geminiTtsVoice,
          gemini_tts_language_code: geminiTtsLanguageCode, gemini_tts_style_prompt: geminiTtsStylePrompt,
          gemini_tts_audio_encoding: geminiTtsAudioEncoding
        };
      } else {
        baseUrl = `${aiProtocol}://${aiHost}:${aiPort}`;
        payload = {
          provider: 'ollama', base_url: baseUrl, model: aiModel, embedding_model: embeddingModel,
          tts_provider: ttsProvider, browser_tts_voice_uri: selectedVoiceUri,
          gemini_tts_model: geminiTtsModel, gemini_tts_voice: geminiTtsVoice,
          gemini_tts_language_code: geminiTtsLanguageCode, gemini_tts_style_prompt: geminiTtsStylePrompt,
          gemini_tts_audio_encoding: geminiTtsAudioEncoding
        };
      }
      if (geminiTtsApiKey.trim()) payload.gemini_tts_api_key = geminiTtsApiKey.trim();
      const res = await apiFetch('/api/ai/config', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok) {
        setAiStatus(tr('Erfolgreich gespeichert', 'Saved successfully'));
        const pTts = normalizeTtsProvider(data?.tts_provider || ttsProvider);
        if (typeof window !== 'undefined') window.localStorage.setItem(TTS_PROVIDER_STORAGE_KEY, pTts);
        setGeminiTtsApiKey('');
        setGeminiTtsApiKeySet(Boolean(data?.gemini_tts_api_key_set || geminiTtsApiKeySet || geminiTtsApiKey.trim()));
        loadOllamaModels();
        loadEmbeddingStatus();
      } else {
        setAiStatus(`Error: ${data?.error || tr('Fehler beim Speichern', 'Error saving')}`);
      }
    } catch (err) {
      setAiStatus('Error: ' + err.message);
    }
  };

  const updateEmbeddings = async () => {
    try {
      setAiStatus(tr('Embeddings werden aktualisiert...', 'Updating embeddings...'));
      const res = await apiFetch('/api/knowledge/update-embeddings', { method: 'POST' });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data?.status === 'success') {
        setAiStatus(tr('Embeddings erfolgreich aktualisiert', 'Embeddings updated successfully'));
      } else {
        setAiStatus(`Error: ${data?.error || tr('Embeddings konnten nicht aktualisiert werden', 'Could not update embeddings')}`);
      }
    } catch (err) {
      setAiStatus('Error: ' + err.message);
    }
  };

  const saveDisplayName = () => {
    const trimmed = displayName.trim();
    if (!trimmed) return;
    try {
      localStorage.setItem(DISPLAY_NAME_STORAGE_KEY, trimmed);
      setDisplayName(trimmed);
    } catch (err) {
      console.error('Error saving display name:', err);
    }
  };

  const executeFactoryReset = async () => {
    if (!factoryResetPassword.trim()) {
      setFactoryResetMessage(tr('Passwort eingeben', 'Enter password'));
      return;
    }
    setFactoryResetLoading(true);
    setFactoryResetMessage('');
    try {
      const res = await apiFetch('/api/auth/factory-reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: factoryResetPassword })
      });
      const data = await res.json();
      if (!data.success) {
        setFactoryResetMessage(data.error || tr('Falsches Passwort', 'Wrong password'));
        setFactoryResetLoading(false);
        return;
      }
      const keys = Object.keys(localStorage);
      const myndKeys = keys.filter(k => k.startsWith('mynd_'));
      myndKeys.forEach(k => localStorage.removeItem(k));
      setFactoryResetMessage(tr('✓ App zurückgesetzt. Leite weiter...', '✓ App reset. Redirecting...'));
      setTimeout(() => { window.location.href = '/'; }, 1500);
    } catch (err) {
      setFactoryResetMessage(tr('Fehler: ', 'Error: ') + err.message);
      setFactoryResetLoading(false);
    }
  };

  useEffect(() => {
    loadAIConfig();
    loadOllamaModels();
    loadEmbeddingStatus();
    loadSecurityMode();
    try {
      const storedName = localStorage.getItem(DISPLAY_NAME_STORAGE_KEY);
      if (storedName) setDisplayName(storedName);
    } catch (err) {
      console.error('Error loading display name:', err);
    }
    const statusInterval = setInterval(() => {
      loadEmbeddingStatus();
    }, 8000);
    return () => clearInterval(statusInterval);
  // Configuration bootstrap and its polling interval are installed once and cleaned up on unmount.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!aiModels.length) return;
    setAiModel((currentValue) => resolveModelOption(aiModelOptions, currentValue));
    setEmbeddingModel((currentValue) => resolveModelOption(embeddingModelOptions, currentValue));
  }, [aiModels, aiModelOptions, embeddingModelOptions]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const supports = 'speechSynthesis' in window && typeof window.SpeechSynthesisUtterance !== 'undefined';
    setSpeechSynthesisSupported(supports);
    if (!supports) return;
    const updateVoices = () => {
      const voices = window.speechSynthesis.getVoices();
      setAvailableVoices(voices.map((v) => ({ voiceURI: v.voiceURI, name: v.name, lang: v.lang, default: v.default })));
    };
    updateVoices();
    window.speechSynthesis.addEventListener('voiceschanged', updateVoices);
    return () => window.speechSynthesis.removeEventListener('voiceschanged', updateVoices);
  }, []);

  useEffect(() => {
    if (!selectedVoiceUri) return;
    if (!visibleVoices.some((v) => v.voiceURI === selectedVoiceUri)) {
      setSelectedVoiceUri('');
    }
  }, [selectedVoiceUri, visibleVoices]);

  return (
    <div className="settings-panel">
      <div className="panel-section">
        <div className="section-title">{tr('Verbindung', 'Connection')}</div>
        <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0 1rem 0'}}>
          {tr(
            'Adresse des lokalen Backend-Servers (Flask). Bei statischem Export (Cloudflare) muss hier die URL des Mac mini eingetragen werden.',
            'Address of the local backend server (Flask). For static export (Cloudflare), enter the Mac mini URL here.'
          )}
        </p>
        <div className="input-group">
          <label>{tr('Backend-URL', 'Backend URL')}</label>
          <input type="text" value={backendUrl} onChange={(e) => setBackendUrl(e.target.value)}
            placeholder="http://127.0.0.1:5001" />
        </div>
      </div>

      <div className="panel-section">
        <div className="section-title">{tr('KI-Modell', 'AI Model')}</div>
        <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0 1rem 0'}}>
          {tr(
            'Das Chat-Modell beantwortet Fragen und schreibt Text. Das Embedding-Modell erzeugt Vektoren für semantische Suche, Ähnlichkeit und Fotosuche.',
            'The chat model answers questions and writes text. The embedding model creates vectors for semantic search, similarity, and photo search.'
          )}
        </p>
        <div className="input-group">
          <label>{tr('Anbieter', 'Provider')}</label>
          <select value={aiProvider} onChange={(e) => setAiProvider(e.target.value)}>
            <option value="ollama">Ollama (Lokal)</option>
            <option value="openai">OpenAI-kompatibel</option>
          </select>
        </div>
        {aiProvider === 'openai' ? (
          <>
            <div className="input-group">
              <label>{tr('Base URL', 'Base URL')}</label>
              <input type="text" value={openaiBaseUrl} onChange={(e) => setOpenaiBaseUrl(e.target.value)}
                placeholder="https://api.openai.com/v1" />
            </div>
            <div className="input-group">
              <label>{tr('API Key', 'API Key')}</label>
              <input type="password" value={openaiApiKey} onChange={(e) => setOpenaiApiKey(e.target.value)}
                placeholder={openaiApiKeySet ? tr('API-Key ist gesetzt (neu eingeben zum Ändern)', 'API key is set (enter new to change)') : tr('API-Key eingeben', 'Enter API key')} />
            </div>
          </>
        ) : (
          <>
            <div className="input-group">
              <label>{tr('Protokoll', 'Protocol')}</label>
              <select value={aiProtocol} onChange={(e) => setAiProtocol(e.target.value)}>
                <option>http</option>
                <option>https</option>
              </select>
            </div>
            <div className="input-group">
              <label>{tr('Host', 'Host')}</label>
              <input type="text" value={aiHost} onChange={(e) => setAiHost(e.target.value)} />
            </div>
            <div className="input-group">
              <label>{tr('Port', 'Port')}</label>
              <input type="text" value={aiPort} onChange={(e) => setAiPort(e.target.value)} />
            </div>
          </>
        )}
        <div className="input-group">
          <label>{tr('Chat-/KI-Modell', 'Chat / AI model')}</label>
          <div style={{display: 'flex', gap: 6}}>
            <select value={aiModel} onChange={(e) => setAiModel(e.target.value)} style={{flex: 1}}>
              <option value="">{tr('Modell auswählen...', 'Select model...')}</option>
              {aiModelOptions.map(model => <option key={model} value={model}>{model}</option>)}
            </select>
            <button className="btn secondary" onClick={loadOllamaModels} title={tr('Modelle neu abrufen', 'Refresh models')}
              style={{padding: '0 12px', whiteSpace: 'nowrap', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: 4}}>
              <i className="fas fa-rotate" /> {tr('Neu laden', 'Refresh')}
            </button>
          </div>
        </div>
        <div className="input-group">
          <label>{tr('Embedding-Modell', 'Embedding model')}</label>
          <select value={embeddingModel} onChange={(e) => setEmbeddingModel(e.target.value)}>
            <option value="">{tr('Embedding-Modell auswählen...', 'Select embedding model...')}</option>
            {embeddingModelOptions.map(model => <option key={model} value={model}>{model}</option>)}
          </select>
          <small style={{color: 'var(--muted)', display: 'block', marginTop: '0.25rem'}}>
            {tr(
              'Für semantische Suche und Ähnlichkeit. In der Regel ist das ein separates Modell vom Chat-Modell.',
              'Used for semantic search and similarity. This is usually a separate model from the chat model.'
            )}
          </small>
          <small style={{color: 'var(--muted)', display: 'block', marginTop: '0.35rem'}}>
            {embeddingCoverage
              ? `${embeddingCoverageDetail} ${embeddingCoverage.model ? tr('Aktives Modell: ', 'Active model: ') + embeddingCoverage.model : ''}`
              : tr('Der Status wird nach dem Laden der Konfiguration angezeigt.', 'The status is shown after the configuration is loaded.')}
          </small>
        </div>
        <div className="button-group">
          <button className="btn primary" onClick={saveAIConfig}>{tr('Speichern', 'Save')}</button>
          <button className="btn secondary" onClick={updateEmbeddings}>{tr('Embeddings aktualisieren', 'Update Embeddings')}</button>
          <button className="btn secondary" onClick={checkModelToolSupport} disabled={modelCheckLoading}>
            {modelCheckLoading ? tr('Prüfe...', 'Checking...') : tr('Models auf Tool-Support prüfen', 'Check Models Tool Support')}
          </button>
        </div>
        {aiStatus && <div className="status-text">{aiStatus}</div>}
        {modelCheckResults && (
          <div style={{marginTop: '1rem', padding: '0.75rem', borderRadius: 'var(--radius)', background: 'var(--chip-bg)', border: '1px solid var(--line)'}}>
            <div style={{fontWeight: 600, marginBottom: '0.5rem', fontSize: '0.85rem'}}>
              {tr('Tool-Support-Ergebnisse', 'Tool Support Results')}
            </div>
            {modelCheckResults.error ? (
              <div style={{color: '#ef4444', fontSize: '0.85rem'}}>{modelCheckResults.error}</div>
            ) : (
              <div style={{display: 'flex', flexDirection: 'column', gap: '0.35rem'}}>
                {Array.isArray(modelCheckResults.results) && modelCheckResults.results.map((r, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: '0.5rem',
                    fontSize: '0.85rem', padding: '0.3rem 0.5rem',
                    borderRadius: 'var(--radius-sm)',
                    background: r.tool_support ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.06)'
                  }}>
                    <span style={{
                      width: 8, height: 8, borderRadius: '50%',
                      background: r.tool_support ? '#22c55e' : '#ef4444',
                      flexShrink: 0
                    }} />
                    <span style={{flex: 1, fontWeight: 500}}>{r.model}</span>
                    <span style={{fontSize: '0.75rem', color: r.tool_support ? '#16a34a' : '#dc2626'}}>
                      {r.tool_support ? '✓ Tools' : '✗ Keine Tools'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="panel-section" style={{marginTop: '2rem'}}>
        <div className="section-title">{tr('Sicherheitsmodus', 'Security Mode')}</div>
        <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0 1rem 0'}}>
          {tr(
            'Legt fest, welche Werkzeuge der KI zur Verfügung stehen.',
            'Determines which tools the AI can use.'
          )}
        </p>
        <div style={{display: 'flex', gap: '0.5rem', flexWrap: 'wrap'}}>
          {[
            { id: 'restricted', label: tr('Eingeschränkt', 'Restricted'), desc: tr('Nur Dokumentensuche + Gedächtnis', 'Only document search + memory') },
            { id: 'standard', label: tr('Standard', 'Standard'), desc: tr('Vault + Tools, kein SSH/Admin', 'Vault + tools, no SSH/admin') },
            { id: 'admin', label: tr('Admin', 'Admin'), desc: tr('Voller Zugriff inkl. SSH', 'Full access including SSH') }
          ].map((opt) => (
            <button
              key={opt.id}
              type="button"
              className={`chat-design-btn ${securityMode === opt.id ? 'active' : ''}`}
              onClick={() => setSecurityMode(opt.id)}
              title={opt.desc}
              style={{flex: '1 1 140px', textAlign: 'center', padding: '0.6rem 0.8rem', borderRadius: 'var(--radius)'}}
            >
              <div style={{fontWeight: 600, fontSize: '0.85rem'}}>{opt.label}</div>
              <div style={{fontSize: '0.7rem', color: 'var(--muted)', marginTop: '0.2rem'}}>{opt.desc}</div>
            </button>
          ))}
        </div>
        {securityModeStatus && <div className="status-text" style={{marginTop: '0.5rem'}}>{securityModeStatus}</div>}
      </div>

      <div className="panel-section" style={{marginTop: '2rem'}}>
        <div className="section-title">{tr('Personalisierung', 'Personalization')}</div>
        <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
          {tr('Dieser Name wird für die persönliche Begrüßung auf der Startseite genutzt.', 'This name is used for the personalized greeting on the homepage.')}
        </p>
        <div className="input-group">
          <label>{tr('Anzeigename', 'Display Name')}</label>
          <input type="text" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="z.B. Max" />
        </div>
        <div className="button-group">
          <button className="btn primary" onClick={saveDisplayName}>{tr('Speichern', 'Save')}</button>
        </div>
      </div>

      <div className="panel-section" style={{marginTop: '2rem'}}>
        <div className="section-title">{tr('Sprachausgabe (TTS)', 'Text-to-Speech')}</div>
        <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
          {tr('Wähle den TTS-Anbieter und die Stimme für Sprachausgaben.', 'Choose the TTS provider and voice for speech output.')}
        </p>

        <div className="input-group">
          <label>{tr('TTS-Anbieter', 'TTS Provider')}</label>
          <select value={ttsProvider} onChange={(e) => setTtsProvider(e.target.value)}>
            <option value="browser">{tr('Browser-Sprachausgabe', 'Browser Speech')}</option>
            <option value="gemini">Gemini TTS</option>
          </select>
        </div>

        {ttsProvider === 'browser' && speechSynthesisSupported && (
          <div className="input-group">
            <label>{tr('Stimme', 'Voice')}</label>
            <select value={selectedVoiceUri} onChange={(e) => setSelectedVoiceUri(e.target.value)}>
              <option value="">{tr('System-Standard', 'System Default')}</option>
              {visibleVoices.map((voice) => (
                <option key={voice.voiceURI} value={voice.voiceURI}>
                  {formatVoiceLabel(voice)}
                </option>
              ))}
            </select>
            <small style={{color: 'var(--muted)', display: 'block', marginTop: '0.25rem'}}>
              {tr('Es werden nur deutschsprachige Stimmen angezeigt.', 'Only German-language voices are shown.')}
            </small>
          </div>
        )}

        {!speechSynthesisSupported && ttsProvider === 'browser' && (
          <p style={{color: 'var(--muted)'}}>{tr('Browser-Sprachausgabe wird in diesem Browser nicht unterstützt.', 'Browser speech synthesis is not supported in this browser.')}</p>
        )}

        {ttsProvider === 'gemini' && (
          <>
            <div className="input-group">
              <label>{tr('Gemini TTS Modell', 'Gemini TTS Model')}</label>
              <select value={geminiTtsModel} onChange={(e) => setGeminiTtsModel(e.target.value)}>
                <option value="gemini-2.5-flash-tts">Gemini 2.5 Flash TTS</option>
                <option value="gemini-2.0-flash-tts">Gemini 2.0 Flash TTS</option>
              </select>
            </div>
            <div className="input-group">
              <label>{tr('Gemini TTS Stimme', 'Gemini TTS Voice')}</label>
              <select value={geminiTtsVoice} onChange={(e) => setGeminiTtsVoice(e.target.value)}>
                {geminiVoices.map((voice) => <option key={voice} value={voice}>{voice}</option>)}
              </select>
            </div>
            <div className="input-group">
              <label>{tr('Sprachcode', 'Language Code')}</label>
              <input type="text" value={geminiTtsLanguageCode} onChange={(e) => setGeminiTtsLanguageCode(e.target.value)} placeholder="de-DE" />
            </div>
            <div className="input-group">
              <label>{tr('Style Prompt (optional)', 'Style Prompt (optional)')}</label>
              <input type="text" value={geminiTtsStylePrompt} onChange={(e) => setGeminiTtsStylePrompt(e.target.value)} placeholder={tr('z.B. ruhig, freundlich', 'e.g. calm, friendly')} />
            </div>
            <div className="input-group">
              <label>{tr('Audio-Encoding', 'Audio Encoding')}</label>
              <select value={geminiTtsAudioEncoding} onChange={(e) => setGeminiTtsAudioEncoding(e.target.value)}>
                <option value="MP3">MP3</option>
                <option value="PCM">PCM</option>
                <option value="LINEAR16">LINEAR16</option>
              </select>
            </div>
            <div className="input-group">
              <label>Gemini TTS API Key</label>
              <input type="password" value={geminiTtsApiKey} onChange={(e) => setGeminiTtsApiKey(e.target.value)}
                placeholder={geminiTtsApiKeySet ? tr('API-Key ist gesetzt (neu eingeben zum Ändern)', 'API key is set (enter new to change)') : tr('API-Key eingeben', 'Enter API key')} />
            </div>
          </>
        )}
      </div>

      <div className="panel-section" style={{marginTop:'2rem'}}>
        <div className="section-title">{tr('Backup & Wiederherstellung', 'Backup & Restore')}</div>
        <p style={{fontSize:'0.9rem',color:'var(--muted)',margin:'0.5rem 0 1rem 0'}}>
          {tr(
            'Exportiere alle Konfigurationsdaten als Sicherung oder stelle ein früheres Backup wieder her.',
            'Export all configuration data as a backup or restore a previous backup.'
          )}
        </p>
        <div style={{display:'flex',gap:'12px',flexWrap:'wrap',alignItems:'center'}}>
          <button className="btn primary" onClick={async () => {
            setBackupLoading(true); setBackupMsg('');
            try {
              const r = await apiFetch('/api/backup/export'); const d = await r.json();
              if (!d.success) throw new Error(d.error);
              const blob = new Blob([JSON.stringify(d, null, 2)], {type:'application/json'});
              const url = URL.createObjectURL(blob);
              const a = document.createElement('a'); a.href = url; a.download = `mynd-backup-${new Date().toISOString().slice(0,10)}.json`;
              a.click(); URL.revokeObjectURL(url);
              setBackupMsg(tr('Backup heruntergeladen.','Backup downloaded.'));
            } catch(err) { setBackupMsg(tr('Fehler: ','Error: ')+err.message); }
            finally { setBackupLoading(false); }
          }} disabled={backupLoading}>
            <i className="fas fa-download" style={{marginRight:6}}></i>
            {backupLoading ? (tr('Lade…','Loading…')) : (tr('Backup exportieren','Export Backup'))}
          </button>
          <label className="btn secondary" style={{cursor:'pointer',display:'inline-flex',alignItems:'center',gap:'6px',padding:'8px 16px',border:'1px solid var(--line)',background:'var(--chip-bg)',fontSize:'0.875rem',fontWeight:500}}>
            <i className="fas fa-upload"></i>
            {tr('Backup importieren','Import Backup')}
            <input type="file" accept=".json" style={{display:'none'}} onChange={(e) => {
              const file = e.target.files?.[0]; if (!file) return;
              const reader = new FileReader();
              reader.onload = async (ev) => {
                try {
                  const data = JSON.parse(ev.target.result);
                  if (!data?.files) { setBackupImportMsg(tr('Ungültiges Backup-Format.','Invalid backup format.')); return; }
                  const r = await apiFetch('/api/backup/import', {
                    method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)
                  });
                  const d = await r.json();
                  if (!d.success) throw new Error(d.error);
                  setBackupImportMsg(tr(`Backup wiederhergestellt (${d.restored} Dateien).`,`Backup restored (${d.restored} files).`));
                } catch(err) { setBackupImportMsg(tr('Fehler: ','Error: ')+err.message); }
              };
              reader.readAsText(file);
              e.target.value = '';
            }} />
          </label>
        </div>
        {backupMsg && <div className="status-text" style={{marginTop:'0.5rem'}}>{backupMsg}</div>}
        {backupImportMsg && <div className="status-text" style={{marginTop:'0.5rem',color:backupImportMsg.startsWith('Fehler')||backupImportMsg.startsWith('Error')||backupImportMsg.startsWith('Ungültig')||backupImportMsg.startsWith('Invalid')?'#ef4444':'var(--success)'}}>{backupImportMsg}</div>}
      </div>

      <div className="panel-section danger-zone" style={{marginTop:'2.5rem',borderColor:'rgba(239,68,68,0.3)'}}>
        <div className="section-title" style={{color:'#ef4444'}}>{tr('Gefahrenzone', 'Danger Zone')}</div>
        <p style={{fontSize:'0.85rem',color:'var(--muted)',margin:'0.3rem 0 1rem 0'}}>
          {tr('Setzt die gesamte Anwendung zurück. Alle Chats, Projekte, Einstellungen und Konfigurationen werden gelöscht. Das Admin-Passwort wird benötigt.', 'Resets the entire application. All chats, projects, settings and configurations will be deleted. Admin password required.')}
        </p>
        {factoryResetStep === 'confirm' ? (
          <div style={{display:'flex',flexDirection:'column',gap:'0.5rem',maxWidth:'360px'}}>
            <input
              type="password"
              placeholder={tr('Admin-Passwort eingeben', 'Enter admin password')}
              value={factoryResetPassword}
              onChange={(e) => setFactoryResetPassword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && executeFactoryReset()}
            />
            <div style={{display:'flex',gap:'0.5rem'}}>
              <button className="btn danger" onClick={executeFactoryReset} disabled={factoryResetLoading}>
                {factoryResetLoading ? '...' : tr('Zurücksetzen', 'Reset')}
              </button>
              <button className="btn secondary" onClick={() => { setFactoryResetStep('idle'); setFactoryResetPassword(''); setFactoryResetMessage(''); }}>
                {tr('Abbrechen', 'Cancel')}
              </button>
            </div>
            {factoryResetMessage && <div className="status-text" style={{color: factoryResetMessage.startsWith('✓') ? 'var(--success, #22c55e)' : '#ef4444'}}>{factoryResetMessage}</div>}
          </div>
        ) : (
          <button className="btn danger" onClick={() => setFactoryResetStep('confirm')}>
            <i className="fas fa-exclamation-triangle"></i> {tr('App zurücksetzen', 'Reset Application')}
          </button>
        )}
      </div>
    </div>
  );
}
