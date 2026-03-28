'use client';

import { useEffect, useState, useRef } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:5001';

export default function HomePage() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [theme, setThemeState] = useState('classic');
  const [messages, setMessages] = useState([]);
  const [isThinking, setIsThinking] = useState(false);
  const [conversationActive, setConversationActive] = useState(false);
  const [source, setSource] = useState('auto');
  const [health, setHealth] = useState({ ollama: 'unknown', kb: 'unknown' });
  const [activeTab, setActiveTab] = useState('config');
  
  // AI Config
  const [aiProtocol, setAiProtocol] = useState('http');
  const [aiHost, setAiHost] = useState('127.0.0.1');
  const [aiPort, setAiPort] = useState('11434');
  const [aiModel, setAiModel] = useState('');
  const [aiModels, setAiModels] = useState([]);
  const [aiStatus, setAiStatus] = useState('');
  
  // Indexing
  const [indexingProgress, setIndexingProgress] = useState(0);
  const [indexingStatus, setIndexingStatus] = useState('idle');
  const [indexingStats, setIndexingStats] = useState('');
  const progressIntervalRef = useRef(null);
  
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  // Initialize
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'classic';
    setThemeState(savedTheme);
    document.documentElement.setAttribute('data-theme', savedTheme);
    
    loadAIConfig();
    loadOllamaModels();
    updateStatus();
    
    const statusInterval = setInterval(updateStatus, 8000);
    return () => clearInterval(statusInterval);
  }, []);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const setTheme = (newTheme) => {
    setThemeState(newTheme);
    localStorage.setItem('theme', newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
  };

  const updateAIPreview = () => {
    const baseUrl = `${aiProtocol}://${aiHost}:${aiPort}`;
    return baseUrl;
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
      setAiStatus('✓ Config loaded');
    } catch (err) {
      console.error('Error loading config:', err);
      setAiStatus('✗ Error loading config');
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
      const baseUrl = updateAIPreview();
      const res = await fetch(`${API_BASE}/api/ai/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ base_url: baseUrl, model: aiModel })
      });
      if (res.ok) {
        setAiStatus('✓ Saved successfully');
        updateStatus();
      } else {
        setAiStatus('✗ Error saving');
      }
    } catch (err) {
      setAiStatus('✗ Error: ' + err.message);
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
        startProgressUpdates();
      } else {
        const data = await res.json();
        setIndexingStatus('error: ' + data.error);
      }
    } catch (err) {
      setIndexingStatus('error: ' + err.message);
    }
  };

  const startProgressUpdates = () => {
    if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
    progressIntervalRef.current = setInterval(updateProgress, 500);
  };

  const updateProgress = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/indexing/progress`);
      if (res.ok) {
        const data = await res.json();
        const pct = Math.round(data.progress_percentage);
        setIndexingProgress(pct);
        setIndexingStats(`${data.processed_files}/${data.total_files} files | ${Math.round(data.elapsed_time)}s`);
        
        if (data.status === 'completed' || data.status === 'error') {
          setIndexingStatus(data.status);
          if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
        }
      }
    } catch (err) {
      console.error('Update progress error:', err);
    }
  };

  const addMessage = (role, content) => {
    setMessages(prev => [...prev, { role, content, id: Date.now() }]);
  };

  const switchToChat = () => {
    setConversationActive(true);
  };

  const sendMessage = async (text) => {
    if (!text.trim() || isThinking) return;
    
    text = text.trim();
    
    if (!conversationActive) {
      switchToChat();
    }
    
    addMessage('user', text);
    setIsThinking(true);
    
    // Clear input
    if (inputRef.current) {
      inputRef.current.value = '';
    }

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, source })
      });
      const data = await res.json();
      addMessage('assistant', data.response);
    } catch (err) {
      addMessage('assistant', `Error: ${err.message}`);
    } finally {
      setIsThinking(false);
    }
  };

  return (
    <div className="container">
      {/* TOPBAR */}
      <div className="topbar">
        <div className="topbar-left">
          <button className="icon-btn" onClick={() => setSidebarOpen(!sidebarOpen)}>
            <i className="fas fa-bars"></i>
          </button>
          <div className="brand">
            <div className="brand-icon">M</div>
            <span>MYND</span>
          </div>
        </div>

        <div className="topbar-right">
          <div className="status-badge">
            <div className={`status-dot ${health.ollama === 'ok' ? 'ok' : 'error'}`}></div>
            <span> Ollama</span>
          </div>
          <div className="status-badge">
            <div className={`status-dot ${health.kb === 'ok' ? 'ok' : 'error'}`}></div>
            <span> KB</span>
          </div>
        </div>
      </div>

      {/* MAIN */}
      <div className="main">
        {/* SIDEBAR */}
        <div className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
          <div className="sidebar-content">
            <div className="tabs">
              <button 
                className={`tab-btn ${activeTab === 'config' ? 'active' : ''}`}
                onClick={() => setActiveTab('config')}
              >
                ⚙️ Config
              </button>
              <button 
                className={`tab-btn ${activeTab === 'indexing' ? 'active' : ''}`}
                onClick={() => setActiveTab('indexing')}
              >
                📝 Indexing
              </button>
              <button 
                className={`tab-btn ${activeTab === 'sources' ? 'active' : ''}`}
                onClick={() => setActiveTab('sources')}
              >
                📂 Sources
              </button>
            </div>

            {/* CONFIG TAB */}
            {activeTab === 'config' && (
              <div>
                <div className="sidebar-section">
                  <div className="section-title">🤖 AI Model</div>
                  <div className="input-group">
                    <label>Protocol</label>
                    <select 
                      value={aiProtocol}
                      onChange={(e) => setAiProtocol(e.target.value)}
                    >
                      <option>http</option>
                      <option>https</option>
                    </select>
                  </div>
                  <div className="input-group">
                    <label>Host</label>
                    <input 
                      type="text" 
                      value={aiHost}
                      onChange={(e) => setAiHost(e.target.value)}
                    />
                  </div>
                  <div className="input-group">
                    <label>Port</label>
                    <input 
                      type="text" 
                      value={aiPort}
                      onChange={(e) => setAiPort(e.target.value)}
                    />
                  </div>
                  <div className="input-group">
                    <label>Model</label>
                    <select 
                      value={aiModel}
                      onChange={(e) => setAiModel(e.target.value)}
                    >
                      <option value="">Select model...</option>
                      {aiModels.map(model => (
                        <option key={model} value={model}>{model}</option>
                      ))}
                    </select>
                  </div>
                  <div className="button-group">
                    <button className="btn primary" onClick={saveAIConfig}>Save</button>
                  </div>
                  {aiStatus && <div className="status-text">{aiStatus}</div>}
                </div>
              </div>
            )}

            {/* INDEXING TAB */}
            {activeTab === 'indexing' && (
              <div>
                <div className="sidebar-section">
                  <div className="section-title">📚 Document Indexing</div>
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

            {/* SOURCES TAB */}
            {activeTab === 'sources' && (
              <div>
                <div className="sidebar-section">
                  <div className="section-title">📂 Message Sources</div>
                  <div className="input-group" style={{ gap: '0.5rem' }}>
                    <label>
                      <input 
                        type="radio" 
                        name="source" 
                        value="auto" 
                        checked={source === 'auto'}
                        onChange={(e) => setSource(e.target.value)}
                      /> Auto
                    </label>
                    <label>
                      <input 
                        type="radio" 
                        name="source" 
                        value="files" 
                        checked={source === 'files'}
                        onChange={(e) => setSource(e.target.value)}
                      /> Files
                    </label>
                    <label>
                      <input 
                        type="radio" 
                        name="source" 
                        value="photos" 
                        checked={source === 'photos'}
                        onChange={(e) => setSource(e.target.value)}
                      /> Photos
                    </label>
                  </div>
                </div>

                <div className="sidebar-section">
                  <div className="section-title">🎨 Theme</div>
                  <div className="theme-selector">
                    <button 
                      className={`theme-btn classic ${theme === 'classic' ? 'active' : ''}`}
                      onClick={() => setTheme('classic')}
                    ></button>
                    <button 
                      className={`theme-btn ocean ${theme === 'ocean' ? 'active' : ''}`}
                      onClick={() => setTheme('ocean')}
                    ></button>
                    <button 
                      className={`theme-btn graphite ${theme === 'graphite' ? 'active' : ''}`}
                      onClick={() => setTheme('graphite')}
                    ></button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* CHAT AREA */}
        <div className="chat-area">
          {!conversationActive ? (
            // LANDING VIEW
            <div className="landing">
              <div className="landing-header">
                <h2>What's on your mind?</h2>
                <p>Ask anything about your knowledge base or get creative answers powered by AI.</p>
              </div>
              <div className="input-wrapper">
                <input 
                  type="text" 
                  ref={inputRef}
                  placeholder="Ask a question..." 
                  onKeyPress={(e) => {
                    if (e.key === 'Enter') {
                      sendMessage(e.target.value);
                    }
                  }}
                />
                <button onClick={() => sendMessage(inputRef.current?.value || '')}>
                  <i className="fas fa-arrow-right"></i>
                </button>
              </div>
            </div>
          ) : (
            <>
              {/* CONVERSATION VIEW */}
              <div className="conversation">
                <div className="messages">
                  {messages.map((msg) => (
                    <div key={msg.id} className={`message ${msg.role}`}>
                      <div className="bubble">{msg.content}</div>
                    </div>
                  ))}
                  {isThinking && (
                    <div className="message assistant">
                      <div className="thinking-indicator">
                        <div className="dot"></div>
                        <div className="dot"></div>
                        <div className="dot"></div>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>
              </div>

              {/* COMPOSER */}
              <div className="composer">
                <input 
                  type="text" 
                  ref={inputRef}
                  placeholder="Your message here..." 
                  onKeyPress={(e) => {
                    if (e.key === 'Enter' && !e.ctrlKey) {
                      sendMessage(e.target.value);
                    }
                  }}
                />
                <button onClick={() => sendMessage(inputRef.current?.value || '')} disabled={isThinking}>
                  <i className="fas fa-arrow-right"></i>
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
