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
  const [indexingDetails, setIndexingDetails] = useState({
    currentFile: '',
    processedFiles: 0,
    totalFiles: 0,
    elapsedTime: 0,
    errors: [],
    chunksCreated: 0,
    documentsProcessed: 0,
    processingSpeed: 0,
    estimatedTimeRemaining: 0,
    lastIndexingStart: 0,
    lastIndexingEnd: 0,
    lastIndexingDuration: 0
  });
  
  const [nextcloudConfig, setNextcloudConfig] = useState({
    url: '',
    username: '',
    password: '',
    path: '/'
  });
  const [nextcloudStatus, setNextcloudStatus] = useState('');

  useEffect(() => {
    loadAIConfig();
    loadOllamaModels();
    loadNextcloudConfig();
    updateStatus();
    
    const statusInterval = setInterval(updateStatus, 8000);
    return () => {
      clearInterval(statusInterval);
    };
  }, []);

  const loadNextcloudConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/indexing/config`);
      if (res.ok) {
        const config = await res.json();
        setNextcloudConfig({
          url: config.url || '',
          username: config.username || '',
          password: config.password || '',
          path: config.path || '/'
        });
      }
    } catch (err) {
      console.error('Error loading Nextcloud config:', err);
    }
  };

  const saveNextcloudConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/indexing/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(nextcloudConfig)
      });
      if (res.ok) {
        setNextcloudStatus('Configuration saved successfully');
      } else {
        const data = await res.json();
        setNextcloudStatus('Error: ' + data.error);
      }
    } catch (err) {
      setNextcloudStatus('Error: ' + err.message);
    }
  };

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
      // First check if there's a configuration
      const configRes = await fetch(`${API_BASE}/api/indexing/config`);
      if (configRes.ok) {
        const config = await configRes.json();
        if (!config.url || !config.username || !config.password) {
          setIndexingStatus('error: Nextcloud configuration required. Please configure your Nextcloud connection first.');
          return;
        }
      }
      
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
              setIndexingProgress(Math.round(data.progress_percentage || 0));
              
              // Calculate processing speed (files per second)
              const processingSpeed = data.elapsed_time > 0 ? (data.processed_files / data.elapsed_time).toFixed(1) : 0;
              
              // Calculate estimated time remaining
              const timeRemaining = data.progress_percentage > 0 && data.elapsed_time > 0 
                ? Math.round((data.elapsed_time / data.progress_percentage) * (100 - data.progress_percentage))
                : 0;
              
              setIndexingDetails({
                currentFile: data.current_file || '',
                processedFiles: data.processed_files || 0,
                totalFiles: data.total_files || 0,
                elapsedTime: Math.round(data.elapsed_time) || 0,
                errors: data.errors || [],
                chunksCreated: 0, // Will be updated when indexing completes
                documentsProcessed: data.processed_files || 0,
                processingSpeed: parseFloat(processingSpeed),
                estimatedTimeRemaining: timeRemaining,
                lastIndexingStart: data.last_indexing_start || 0,
                lastIndexingEnd: data.last_indexing_end || 0,
                lastIndexingDuration: data.last_indexing_duration || 0
              });
              
              // Enhanced stats display
              setIndexingStats(
                `${data.processed_files || 0}/${data.total_files || 0} files | ` +
                `${Math.round(data.elapsed_time || 0)}s elapsed | ` +
                `${processingSpeed} files/s | ` +
                (timeRemaining > 0 ? `~${timeRemaining}s remaining` : 'calculating...')
              );
              
              if (data.status === 'completed' || data.status === 'error') {
                setIndexingStatus(data.status);
                if (data.status === 'completed') {
                  setIndexingDetails(prev => ({
                    ...prev,
                    chunksCreated: data.processed_files * 10 // Estimate chunks
                  }));
                }
                clearInterval(progressInterval);
              }
            } else if (res.status === 500) {
              // Handle server errors gracefully
              console.error('Server error during indexing progress check');
              setIndexingStatus('error: Server error');
              clearInterval(progressInterval);
            } else {
              console.error('Unexpected response:', res.status, res.statusText);
              const errorText = await res.text();
              console.error('Error response:', errorText);
              setIndexingStatus(`error: ${res.status}`);
              clearInterval(progressInterval);
            }
          } catch (err) {
            console.error('Update progress error:', err);
            // Don't immediately set error status, might be temporary network issue
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
                  <div className="section-title">Nextcloud Configuration</div>
                  <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
                    Configure your Nextcloud connection for document indexing
                  </p>
                  <div className="input-group">
                    <label>Nextcloud URL</label>
                    <input 
                      type="text" 
                      value={nextcloudConfig.url} 
                      onChange={(e) => setNextcloudConfig(prev => ({...prev, url: e.target.value}))}
                      placeholder="https://cloud.example.com"
                    />
                  </div>
                  <div className="input-group">
                    <label>Username</label>
                    <input 
                      type="text" 
                      value={nextcloudConfig.username} 
                      onChange={(e) => setNextcloudConfig(prev => ({...prev, username: e.target.value}))}
                      placeholder="your-username"
                    />
                  </div>
                  <div className="input-group">
                    <label>Password</label>
                    <input 
                      type="password" 
                      value={nextcloudConfig.password} 
                      onChange={(e) => setNextcloudConfig(prev => ({...prev, password: e.target.value}))}
                      placeholder="your-password"
                    />
                  </div>
                  <div className="input-group">
                    <label>Remote Path (optional)</label>
                    <input 
                      type="text" 
                      value={nextcloudConfig.path} 
                      onChange={(e) => setNextcloudConfig(prev => ({...prev, path: e.target.value}))}
                      placeholder="/Documents"
                    />
                  </div>
                  <div className="button-group">
                    <button className="btn primary" onClick={saveNextcloudConfig}>Save Configuration</button>
                  </div>
                  {nextcloudStatus && <div className="status-text">{nextcloudStatus}</div>}
                </div>
                
                <div className="panel-section" style={{marginTop: '2rem'}}>
                  <div className="section-title">Document Indexing</div>
                  <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
                    Index your documents for semantic search with detailed progress tracking
                  </p>
                  <div className="button-group">
                    <button className="btn primary" onClick={startIndexing} disabled={indexingStatus === 'running'}>
                      {indexingStatus === 'running' ? 'Indexing...' : 'Start Indexing'}
                    </button>
                    {indexingStatus === 'running' && (
                      <button className="btn secondary" onClick={() => fetch(`${API_BASE}/api/indexing/stop`, {method: 'POST'})}>
                        Stop
                      </button>
                    )}
                  </div>
                  
                  {/* Progress Section */}
                  {(indexingStatus !== 'idle' || indexingDetails.processedFiles > 0) && (
                    <div style={{marginTop: '1.5rem', padding: '1rem', background: 'var(--surface)', borderRadius: '8px', border: '1px solid var(--border)'}}>
                      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem'}}>
                        <h4 style={{margin: 0, fontSize: '1rem', fontWeight: '600'}}>
                          <i className="fas fa-chart-line" style={{marginRight: '0.5rem'}}></i>
                          Indexing Progress
                        </h4>
                        <span style={{
                          fontSize: '0.8rem',
                          padding: '0.25rem 0.75rem',
                          borderRadius: '12px',
                          background: indexingStatus === 'running' ? 'var(--primary)' : 
                                     indexingStatus === 'completed' ? 'var(--success)' : 
                                     indexingStatus === 'error' ? 'var(--error)' : 'var(--muted)',
                          color: 'white',
                          fontWeight: '500'
                        }}>
                          {indexingStatus.toUpperCase()}
                        </span>
                      </div>
                      
                      {indexingStatus === 'running' && (
                        <div className="progress-bar-wrapper" style={{marginBottom: '1rem'}}>
                          <div className="progress-bar" style={{
                            height: '8px',
                            background: 'var(--border)',
                            borderRadius: '4px',
                            overflow: 'hidden',
                            position: 'relative'
                          }}>
                            <div className="progress-fill" style={{
                              height: '100%',
                              background: 'linear-gradient(90deg, var(--primary), var(--primary-light))',
                              transition: 'width 0.5s ease',
                              width: `${indexingProgress}%`,
                              borderRadius: '4px'
                            }}></div>
                          </div>
                          <div style={{display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--muted)', marginTop: '0.5rem'}}>
                            <span>{indexingProgress}% Complete</span>
                            <span>{indexingDetails.processedFiles} / {indexingDetails.totalFiles} files</span>
                          </div>
                        </div>
                      )}
                      
                      {/* Detailed Statistics Grid */}
                      <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem', marginBottom: '1rem'}}>
                        <div style={{textAlign: 'center', padding: '0.75rem', background: 'var(--background)', borderRadius: '6px'}}>
                          <div style={{fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--primary)'}}>
                            {indexingDetails.processedFiles}
                          </div>
                          <div style={{fontSize: '0.75rem', color: 'var(--muted)'}}>Files Processed</div>
                        </div>
                        <div style={{textAlign: 'center', padding: '0.75rem', background: 'var(--background)', borderRadius: '6px'}}>
                          <div style={{fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--success)'}}>
                            {indexingDetails.processingSpeed}
                          </div>
                          <div style={{fontSize: '0.75rem', color: 'var(--muted)'}}>Files/Second</div>
                        </div>
                        <div style={{textAlign: 'center', padding: '0.75rem', background: 'var(--background)', borderRadius: '6px'}}>
                          <div style={{fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--accent)'}}>
                            {Math.floor(indexingDetails.elapsedTime / 60)}:{(indexingDetails.elapsedTime % 60).toString().padStart(2, '0')}
                          </div>
                          <div style={{fontSize: '0.75rem', color: 'var(--muted)'}}>Time Elapsed</div>
                        </div>
                        <div style={{textAlign: 'center', padding: '0.75rem', background: 'var(--background)', borderRadius: '6px'}}>
                          <div style={{fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--warning)'}}>
                            {indexingDetails.estimatedTimeRemaining > 0 ? `${Math.floor(indexingDetails.estimatedTimeRemaining / 60)}:${(indexingDetails.estimatedTimeRemaining % 60).toString().padStart(2, '0')}` : '--:--'}
                          </div>
                          <div style={{fontSize: '0.75rem', color: 'var(--muted)'}}>Time Remaining</div>
                        </div>
                      </div>
                      
                      {/* Current File and Additional Details */}
                      {indexingDetails.currentFile && (
                        <div style={{marginBottom: '1rem', padding: '0.75rem', background: 'var(--background)', borderRadius: '6px', fontSize: '0.85rem'}}>
                          <div style={{fontWeight: '600', marginBottom: '0.25rem', color: 'var(--text)'}}>
                            <i className="fas fa-file-alt" style={{marginRight: '0.5rem'}}></i>
                            Currently Processing:
                          </div>
                          <div style={{color: 'var(--muted)', wordBreak: 'break-all'}}>{indexingDetails.currentFile}</div>
                        </div>
                      )}
                      
                      {/* Summary Stats */}
                      <div style={{fontSize: '0.8rem', color: 'var(--muted)'}}>
                        {indexingStats && <div style={{marginBottom: '0.5rem', fontWeight: '500'}}>{indexingStats}</div>}
                        
                        <div style={{display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem'}}>
                          <span><strong>Documents:</strong> {indexingDetails.documentsProcessed}</span>
                          <span><strong>Chunks Created:</strong> ~{indexingDetails.chunksCreated}</span>
                          {indexingDetails.errors.length > 0 && (
                            <span style={{color: 'var(--error)'}}><strong>Errors:</strong> {indexingDetails.errors.length}</span>
                          )}
                        </div>
                        
                        {/* Last Indexing Times */}
                        {indexingDetails.lastIndexingEnd > 0 && (
                          <div style={{marginTop: '1rem', padding: '0.75rem', background: 'var(--background)', borderRadius: '6px', fontSize: '0.8rem'}}>
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
                      
                      {/* Error Details */}
                      {indexingDetails.errors.length > 0 && (
                        <div style={{marginTop: '1rem', padding: '0.75rem', background: 'var(--error-bg)', border: '1px solid var(--error)', borderRadius: '6px'}}>
                          <div style={{fontWeight: '600', marginBottom: '0.5rem', color: 'var(--error)'}}>
                            <i className="fas fa-exclamation-triangle" style={{marginRight: '0.5rem'}}></i>
                            Recent Errors:
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
