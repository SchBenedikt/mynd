'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useTheme } from '../../hooks/useTheme';
import { ThemeSelector } from '../../components/ThemeSelector';

const API_BASE = '';

export default function SettingsPage() {
  const router = useRouter();
  const { theme, darkMode, contrastColor, setTheme, setDarkMode, setContrastColor } = useTheme();
  const [activeTab, setActiveTab] = useState('config');
  const [source, setSource] = useState('auto');
  const [health, setHealth] = useState({ ollama: 'unknown', kb: 'unknown' });
  
  const [aiProtocol, setAiProtocol] = useState('http');
  const [aiHost, setAiHost] = useState('127.0.0.1');
  const [aiPort, setAiPort] = useState('11434');
  const [aiModel, setAiModel] = useState('');
  const [aiModels, setAiModels] = useState([]);
  const [aiStatus, setAiStatus] = useState('');
  
  const [indexingProgress, setIndexingProgress] = useState(0);
  const [indexingStatus, setIndexingStatus] = useState('idle');
  const [indexingStats, setIndexingStats] = useState('');

  useEffect(() => {
    loadAIConfig();
    loadOllamaModels();
    updateStatus();
    
    const statusInterval = setInterval(updateStatus, 8000);
    return () => {
      clearInterval(statusInterval);
    };
  }, []);

  const loadAIConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ai/config`);
      const config = await res.json();
      const url = new URL(config.base_url);
      setAiProtocol(url.protocol.replace(':', ''));
      setAiHost(url.hostname);
      setAiPort(url.port || '11434');
      setAiModel(config.model);
      setAiStatus('Loaded');
    } catch (err) {
      setAiStatus('Error loading config');
    }
  };

  const loadOllamaModels = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ollama/models`);
      const data = await res.json();
      setAiModels(data.models || []);
    } catch (err) {
      console.error('Error loading models:', err);
    }
  };

  const saveAIConfig = async () => {
    try {
      const baseUrl = `${aiProtocol}://${aiHost}:${aiPort}`;
      const res = await fetch(`${API_BASE}/api/ai/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ base_url: baseUrl, model: aiModel })
      });
      if (res.ok) {
        setAiStatus('Saved successfully');
        updateStatus();
      } else {
        setAiStatus('Error saving');
      }
    } catch (err) {
      setAiStatus('Error: ' + err.message);
    }
  };

  const updateStatus = async () => {
    try {
      const [ollamaRes, kbRes] = await Promise.all([
        fetch(`${API_BASE}/api/ollama/status`),
        fetch(`${API_BASE}/api/knowledge/status`)
      ]);
      const ollama = await ollamaRes.json();
      const kb = await kbRes.json();
      setHealth({
        ollama: ollama.connected ? 'ok' : 'error',
        kb: kb.chunks_loaded > 0 ? 'ok' : 'error'
      });
    } catch (err) {
      setHealth({ ollama: 'error', kb: 'error' });
    }
  };

  const startIndexing = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/indexing/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      if (res.ok) {
        setIndexingStatus('running');
        const progressInterval = setInterval(async () => {
          try {
            const res = await fetch(`${API_BASE}/api/indexing/progress`);
            if (res.ok) {
              const data = await res.json();
              setIndexingProgress(Math.round(data.progress_percentage));
              setIndexingStats(`${data.processed_files}/${data.total_files} files | ${Math.round(data.elapsed_time)}s`);
              if (data.status === 'completed' || data.status === 'error') {
                setIndexingStatus(data.status);
                clearInterval(progressInterval);
              }
            }
          } catch (err) {
            console.error('Update progress error:', err);
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

  const startNewChat = () => {
    router.push('/');
  };

  const goToSettings = () => {
    // Already on settings, do nothing
  };

  return (
    <div className="container">
      {/* LEFT SIDEBAR */}
      <div className="left-sidebar">
        <div className="sidebar-header">
          <div className="brand">
            <div className="brand-icon">M</div>
            <span>MYND</span>
          </div>
        </div>
        <button className="new-chat-btn" onClick={startNewChat}>
          <i className="fas fa-plus"></i> New Chat
        </button>
        <button 
          className="new-chat-btn settings-btn active"
          onClick={goToSettings}
        >
          <i className="fas fa-cog"></i> Settings
        </button>
        <div className="chat-history">
          <div className="history-item">
            <i className="fas fa-message"></i>
            <span>Current Chat</span>
          </div>
        </div>
        <div className="sidebar-footer">
          <div className="status-badges">
            <div className="status-badge">
              <div className={`status-dot ${health.ollama === 'ok' ? 'ok' : 'error'}`}></div>
              <span>Ollama</span>
            </div>
            <div className="status-badge">
              <div className={`status-dot ${health.kb === 'ok' ? 'ok' : 'error'}`}></div>
              <span>KB</span>
            </div>
          </div>
        </div>
      </div>

      {/* CENTER - Settings Full Screen */}
      <div className="center-area">
        <div className="settings-full">
          <div className="settings-tabs">
            <button className={`tab-btn ${activeTab === 'config' ? 'active' : ''}`} onClick={() => setActiveTab('config')}>Config</button>
            <button className={`tab-btn ${activeTab === 'indexing' ? 'active' : ''}`} onClick={() => setActiveTab('indexing')}>Indexing</button>
            <button className={`tab-btn ${activeTab === 'sources' ? 'active' : ''}`} onClick={() => setActiveTab('sources')}>Sources</button>
            <button className={`tab-btn ${activeTab === 'design' ? 'active' : ''}`} onClick={() => setActiveTab('design')}>Design</button>
          </div>
          <div className="settings-content">
            {activeTab === 'config' && (
              <div className="settings-panel">
                <div className="panel-section">
                  <div className="section-title">AI Model</div>
                  <div className="input-group">
                    <label>Protocol</label>
                    <select value={aiProtocol} onChange={(e) => setAiProtocol(e.target.value)}>
                      <option>http</option>
                      <option>https</option>
                    </select>
                  </div>
                  <div className="input-group">
                    <label>Host</label>
                    <input type="text" value={aiHost} onChange={(e) => setAiHost(e.target.value)} />
                  </div>
                  <div className="input-group">
                    <label>Port</label>
                    <input type="text" value={aiPort} onChange={(e) => setAiPort(e.target.value)} />
                  </div>
                  <div className="input-group">
                    <label>Model</label>
                    <select value={aiModel} onChange={(e) => setAiModel(e.target.value)}>
                      <option value="">Select model...</option>
                      {aiModels.map(model => <option key={model} value={model}>{model}</option>)}
                    </select>
                  </div>
                  <div className="button-group">
                    <button className="btn primary" onClick={saveAIConfig}>Save</button>
                  </div>
                  {aiStatus && <div className="status-text">{aiStatus}</div>}
                </div>
              </div>
            )}
            {activeTab === 'indexing' && (
              <div className="settings-panel">
                <div className="panel-section">
                  <div className="section-title">Document Indexing</div>
                  <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
                    Index your documents for semantic search
                  </p>
                  <div className="button-group">
                    <button className="btn primary" onClick={startIndexing}>Start</button>
                  </div>
                  <div className="progress-bar-wrapper">
                    <div className="progress-bar">
                      <div className="progress-fill" style={{width: `${indexingProgress}%`}}></div>
                    </div>
                    <div className="progress-text">
                      <span>{indexingStatus}</span>
                      <span>{indexingProgress}%</span>
                    </div>
                  </div>
                  {indexingStats && <div className="status-text">{indexingStats}</div>}
                </div>
              </div>
            )}
            {activeTab === 'sources' && (
              <div className="settings-panel">
                <div className="panel-section">
                  <div className="section-title">Message Sources</div>
                  <div className="input-group">
                    <label><input type="radio" name="source" value="auto" checked={source === 'auto'} onChange={(e) => setSource(e.target.value)} /> Auto</label>
                    <label><input type="radio" name="source" value="files" checked={source === 'files'} onChange={(e) => setSource(e.target.value)} /> Files</label>
                    <label><input type="radio" name="source" value="photos" checked={source === 'photos'} onChange={(e) => setSource(e.target.value)} /> Photos</label>
                  </div>
                </div>
              </div>
            )}
            {activeTab === 'design' && (
              <div className="settings-panel">
                <ThemeSelector
                  currentTheme={theme}
                  onThemeChange={setTheme}
                  currentDarkMode={darkMode}
                  onDarkModeChange={setDarkMode}
                  contrastColor={contrastColor}
                  onContrastColorChange={setContrastColor}
                  showContrastColor={true}
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
