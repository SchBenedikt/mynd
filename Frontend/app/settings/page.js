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
  const [immichUrlDefault, setImmichUrlDefault] = useState('');
  const [immichApiKeyDefault, setImmichApiKeyDefault] = useState('');
  const [immichStatus, setImmichStatus] = useState('');
  
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
  
  const [nextcloudUrl, setNextcloudUrl] = useState('');
  const [nextcloudStatus, setNextcloudStatus] = useState('');
  const [nextcloudConfigured, setNextcloudConfigured] = useState(false);
  const [nextcloudDisplayName, setNextcloudDisplayName] = useState('');
  const [nextcloudLoggingIn, setNextcloudLoggingIn] = useState(false);

  useEffect(() => {
    loadAIConfig();
    loadImmichConfig();
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
      // Check if Nextcloud is configured from the backend
      const configRes = await fetch(`${API_BASE}/api/nextcloud/config`);
      if (configRes.ok) {
        const config = await configRes.json();
        if (config.configured) {
          setNextcloudConfigured(true);
          setNextcloudDisplayName(config.display_name || config.username || '');
          setNextcloudUrl(config.nextcloud_url || '');
        }
      }
    } catch (err) {
      console.error('Error loading Nextcloud config:', err);
    }
    
    // Also check for auth parameters in URL (from OAuth2 callback redirect)
    const params = new URLSearchParams(window.location.search);
    if (params.has('nc_auth_success')) {
      setNextcloudStatus('✓ Successfully logged in! Redirecting...');
      setTimeout(() => window.location.reload(), 1000);
    } else if (params.has('nc_auth_error')) {
      setNextcloudStatus('Error: ' + decodeURIComponent(params.get('nc_auth_error')));
    }
  };

  const handleNextcloudLogin = async () => {
    if (!nextcloudUrl.trim()) {
      setNextcloudStatus('Please enter your Nextcloud URL');
      return;
    }

    try {
      setNextcloudLoggingIn(true);
      setNextcloudStatus('Opening Nextcloud login...');

      const startRes = await fetch(`${API_BASE}/api/nextcloud/loginflow/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nextcloud_url: nextcloudUrl.trim() })
      });

      const startData = await startRes.json();
      if (!startRes.ok) {
        setNextcloudLoggingIn(false);
        setNextcloudStatus('Error: ' + (startData.error || 'Could not start Nextcloud login flow'));
        return;
      }

      window.open(startData.login_url, '_blank', 'noopener,noreferrer');
      setNextcloudStatus('Please confirm login in the opened Nextcloud tab...');

      let attempts = 0;
      const maxAttempts = 120;
      const pollInterval = setInterval(async () => {
        attempts += 1;
        try {
          const pollRes = await fetch(`${API_BASE}/api/nextcloud/loginflow/poll`);
          const pollData = await pollRes.json();

          if (!pollRes.ok) {
            clearInterval(pollInterval);
            setNextcloudLoggingIn(false);
            setNextcloudStatus('Error: ' + (pollData.error || 'Login flow failed'));
            return;
          }

          if (pollData.status === 'connected') {
            clearInterval(pollInterval);
            setNextcloudConfigured(true);
            setNextcloudDisplayName(pollData.display_name || pollData.username || '');
            setNextcloudUrl(pollData.nextcloud_url || nextcloudUrl.trim());
            setNextcloudLoggingIn(false);
            setNextcloudStatus(`✓ Connected as ${pollData.display_name || pollData.username}`);
            return;
          }

          if (attempts >= maxAttempts) {
            clearInterval(pollInterval);
            setNextcloudLoggingIn(false);
            setNextcloudStatus('Login timeout. Please try again.');
          }
        } catch (pollErr) {
          clearInterval(pollInterval);
          setNextcloudLoggingIn(false);
          setNextcloudStatus('Error: ' + pollErr.message);
        }
      }, 2000);
      
    } catch (err) {
      setNextcloudLoggingIn(false);
      setNextcloudStatus('Error: ' + err.message);
    }
  };

  const handleNextcloudDisconnect = async () => {
    try {
      setNextcloudStatus('Disconnecting...');
      const res = await fetch(`${API_BASE}/api/nextcloud/disconnect`, {
        method: 'POST'
      });

      if (!res.ok) {
        const data = await res.json();
        setNextcloudStatus('Error: ' + (data.error || 'Disconnect failed'));
        return;
      }

      setNextcloudConfigured(false);
      setNextcloudDisplayName('');
      setNextcloudUrl('');
      setNextcloudLoggingIn(false);
      setNextcloudStatus('Nextcloud connection removed');
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

  const loadImmichConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ui/system-config`);
      const data = await res.json();
      if (res.ok && data?.success && data?.config) {
        setImmichUrlDefault(data.config.immich_url_default || '');
        setImmichApiKeyDefault(data.config.immich_api_key_default || '');
        setImmichStatus('Loaded');
      } else {
        setImmichStatus('Error loading Immich config');
      }
    } catch (err) {
      setImmichStatus('Error loading Immich config');
    }
  };

  const saveImmichConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/ui/system-config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          immich_url_default: immichUrlDefault,
          immich_api_key_default: immichApiKeyDefault
        })
      });

      const data = await res.json();
      if (res.ok && data?.success) {
        setImmichStatus('Saved successfully');
      } else {
        setImmichStatus(`Error: ${data?.error || 'Could not save Immich config'}`);
      }
    } catch (err) {
      setImmichStatus('Error: ' + err.message);
    }
  };

  const testImmichConnection = async () => {
    try {
      setImmichStatus('Testing connection...');
      const res = await fetch(`${API_BASE}/api/immich/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });

      const data = await res.json();
      if (res.ok && data?.success) {
        setImmichStatus('Connection successful');
      } else {
        setImmichStatus(`Connection failed: ${data?.error || data?.message || 'Unknown error'}`);
      }
    } catch (err) {
      setImmichStatus('Connection failed: ' + err.message);
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

                <div className="panel-section" style={{marginTop: '2rem'}}>
                  <div className="section-title">Immich Integration</div>
                  <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
                    Configure global Immich defaults for photo search.
                  </p>
                  <div className="input-group">
                    <label>Immich URL</label>
                    <input
                      type="text"
                      value={immichUrlDefault}
                      onChange={(e) => setImmichUrlDefault(e.target.value)}
                      placeholder="https://immich.example.com"
                    />
                  </div>
                  <div className="input-group">
                    <label>Immich API Key</label>
                    <input
                      type="password"
                      value={immichApiKeyDefault}
                      onChange={(e) => setImmichApiKeyDefault(e.target.value)}
                      placeholder="immich-api-key"
                    />
                  </div>
                  <div className="button-group">
                    <button className="btn primary" onClick={saveImmichConfig}>Save Immich</button>
                    <button className="btn" onClick={testImmichConnection}>Test Connection</button>
                  </div>
                  {immichStatus && <div className="status-text">{immichStatus}</div>}
                </div>
              </div>
            )}
            {activeTab === 'indexing' && (
              <div className="settings-panel">
                <div className="panel-section">
                  <div className="section-title">Nextcloud Login</div>
                  <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
                    Connect to your Nextcloud instance for document indexing
                  </p>

                  {nextcloudConfigured ? (
                    <div style={{padding: '1rem', background: 'var(--background)', borderRadius: '8px', border: '2px solid var(--success)', marginBottom: '1.5rem'}}>
                      <div style={{display: 'flex', alignItems: 'center', marginBottom: '0.5rem'}}>
                        <i className="fas fa-check-circle" style={{color: 'var(--success)', marginRight: '0.5rem', fontSize: '1.4rem'}}></i>
                        <span style={{fontWeight: '600', fontSize: '1.1rem'}}>Connected</span>
                      </div>
                      <div style={{marginLeft: '2rem', color: 'var(--muted)'}}>
                        <p style={{margin: '0.25rem 0'}}>
                          <strong>{nextcloudDisplayName}</strong>
                        </p>
                        <p style={{margin: '0.25rem 0', fontSize: '0.9rem'}}>
                          {nextcloudUrl}
                        </p>
                      </div>
                      <div className="button-group" style={{marginTop: '0.75rem'}}>
                        <button className="btn secondary" onClick={handleNextcloudDisconnect}>
                          Nextcloud trennen
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="input-group">
                        <label>Nextcloud URL</label>
                        <input 
                          type="text" 
                          value={nextcloudUrl}
                          onChange={(e) => setNextcloudUrl(e.target.value)}
                          placeholder="https://cloud.example.com"
                        />
                        <small style={{color: 'var(--muted)', display: 'block', marginTop: '0.25rem'}}>
                          Enter your Nextcloud URL. You'll be redirected to your Nextcloud instance to log in with your normal credentials.
                        </small>
                      </div>
                      <div className="button-group">
                        <button className="btn primary" onClick={handleNextcloudLogin} disabled={nextcloudLoggingIn || !nextcloudUrl.trim()}>
                          <i className="fas fa-sign-in-alt" style={{marginRight: '0.5rem'}}></i>
                          {nextcloudLoggingIn ? 'Waiting for confirmation...' : 'Login with Nextcloud'}
                        </button>
                      </div>
                      {nextcloudStatus && <div className="status-text">{nextcloudStatus}</div>}
                    </>
                  )}
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
