'use client';

import { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import SourceCard from '../components/SourceCard';

const API_BASE = '';

export default function HomePage() {
  const router = useRouter();
  const [messages, setMessages] = useState([]);
  const [isThinking, setIsThinking] = useState(false);
  const [conversationActive, setConversationActive] = useState(false);
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
    lastIndexingStart: 0,
    lastIndexingEnd: 0,
    lastIndexingDuration: 0
  });
  const progressIntervalRef = useRef(null);
  
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

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
      // First check if there's a configuration
      const configRes = await fetch(`${API_BASE}/api/indexing/config`);
      if (configRes.ok) {
        const config = await configRes.json();
        if (!config.url || !config.username || !config.password) {
          setIndexingStatus('error: Nextcloud configuration required. Please configure in Settings first.');
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
        if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = setInterval(async () => {
          try {
            const res = await fetch(`${API_BASE}/api/indexing/progress`);
            if (res.ok) {
              const data = await res.json();
              setIndexingProgress(Math.round(data.progress_percentage || 0));
              
              // Calculate processing speed (files per second)
              const processingSpeed = data.elapsed_time > 0 ? (data.processed_files / data.elapsed_time).toFixed(1) : 0;
              
              setIndexingDetails({
                currentFile: data.current_file || '',
                processedFiles: data.processed_files || 0,
                totalFiles: data.total_files || 0,
                elapsedTime: Math.round(data.elapsed_time) || 0,
                errors: data.errors || [],
                chunksCreated: 0, // Will be updated when indexing completes
                documentsProcessed: data.processed_files || 0,
                processingSpeed: parseFloat(processingSpeed),
                lastIndexingStart: data.last_indexing_start || 0,
                lastIndexingEnd: data.last_indexing_end || 0,
                lastIndexingDuration: data.last_indexing_duration || 0
              });
              
              // Enhanced stats display
              const timeRemaining = data.progress_percentage > 0 && data.elapsed_time > 0 
                ? Math.round((data.elapsed_time / data.progress_percentage) * (100 - data.progress_percentage))
                : 0;
              
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
                clearInterval(progressIntervalRef.current);
              }
            } else if (res.status === 500) {
              // Handle server errors gracefully
              console.error('Server error during indexing progress check');
              setIndexingStatus('error: Server error');
              clearInterval(progressIntervalRef.current);
            } else {
              console.error('Unexpected response:', res.status, res.statusText);
              const errorText = await res.text();
              console.error('Error response:', errorText);
              setIndexingStatus(`error: ${res.status}`);
            }
          } catch (err) {
            console.error('Update progress error:', err);
            // Don't immediately set error status, might be temporary network issue
            if (err.message.includes('JSON')) {
              setIndexingStatus('error: Invalid response from server');
              clearInterval(progressIntervalRef.current);
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

  const sendMessage = async (text) => {
    if (!text.trim() || isThinking) return;
    text = text.trim();
    if (!conversationActive) setConversationActive(true);
    setMessages(prev => [...prev, { role: 'user', content: text, id: Date.now() }]);
    setIsThinking(true);
    if (inputRef.current) inputRef.current.value = '';

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, source })
      });
      const data = await res.json();
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.response,
        sources: data.sources || [],
        id: Date.now()
      }]);
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: `Error: ${err.message}`, id: Date.now() }]);
    } finally {
      setIsThinking(false);
    }
  };

  const startNewChat = () => {
    setMessages([]);
    setConversationActive(false);
  };

  const goToSettings = () => {
    router.push('/settings');
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
          className="new-chat-btn settings-btn"
          onClick={goToSettings}
        >
          <i className="fas fa-cog"></i> Settings
        </button>
        <div className="chat-history">
          <div className="history-item active">
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

      {/* CENTER - Chat */}
      <div className="center-area">
        {!conversationActive ? (
          <div className="landing">
            <div className="landing-header">
              <h2>What is on your mind?</h2>
              <p>Ask anything about your knowledge base.</p>
            </div>
            <div className="input-wrapper">
              <input 
                type="text" 
                ref={inputRef}
                placeholder="Ask a question..." 
                onKeyPress={(e) => e.key === 'Enter' && sendMessage(e.target.value)}
              />
              <button onClick={() => sendMessage(inputRef.current?.value || '')}>
                <i className="fas fa-arrow-right"></i>
              </button>
            </div>
            
            {/* Indexing Status Panel */}
            {(indexingStatus !== 'idle' || indexingDetails.processedFiles > 0) && (
              <div className="indexing-panel" style={{
                marginTop: '2rem',
                padding: '1rem',
                background: 'var(--surface)',
                borderRadius: '8px',
                border: '1px solid var(--border)'
              }}>
                <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem'}}>
                  <h4 style={{margin: 0, fontSize: '0.9rem', fontWeight: '600'}}>
                    <i className="fas fa-database" style={{marginRight: '0.5rem'}}></i>
                    Document Indexing
                  </h4>
                  <span style={{
                    fontSize: '0.8rem',
                    padding: '0.25rem 0.5rem',
                    borderRadius: '4px',
                    background: indexingStatus === 'running' ? 'var(--primary)' : 
                               indexingStatus === 'completed' ? 'var(--success)' : 
                               indexingStatus === 'error' ? 'var(--error)' : 'var(--muted)',
                    color: 'white'
                  }}>
                    {indexingStatus}
                  </span>
                </div>
                
                {indexingStatus === 'running' && (
                  <div className="progress-bar-wrapper" style={{marginBottom: '0.5rem'}}>
                    <div className="progress-bar" style={{
                      height: '4px',
                      background: 'var(--border)',
                      borderRadius: '2px',
                      overflow: 'hidden'
                    }}>
                      <div className="progress-fill" style={{
                        height: '100%',
                        background: 'var(--primary)',
                        transition: 'width 0.3s ease',
                        width: `${indexingProgress}%`
                      }}></div>
                    </div>
                  </div>
                )}
                
                <div style={{fontSize: '0.8rem', color: 'var(--muted)'}}>
                  {indexingStats && <div style={{marginBottom: '0.5rem'}}>{indexingStats}</div>}
                  
                  {indexingDetails.currentFile && (
                    <div style={{marginBottom: '0.25rem'}}>
                      <strong>Current:</strong> {indexingDetails.currentFile}
                    </div>
                  )}
                  
                  <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.75rem'}}>
                    <div><strong>Files:</strong> {indexingDetails.processedFiles}/{indexingDetails.totalFiles}</div>
                    <div><strong>Speed:</strong> {indexingDetails.processingSpeed} files/s</div>
                    <div><strong>Elapsed:</strong> {indexingDetails.elapsedTime}s</div>
                    <div><strong>Chunks:</strong> ~{indexingDetails.chunksCreated}</div>
                  </div>
                  
                  {/* Last Indexing Times */}
                  {indexingDetails.lastIndexingEnd > 0 && (
                    <div style={{marginTop: '0.5rem', padding: '0.5rem', background: 'var(--background)', borderRadius: '4px', fontSize: '0.7rem'}}>
                      <div style={{fontWeight: '600', marginBottom: '0.25rem', color: 'var(--text)'}}>
                        <i className="fas fa-history" style={{marginRight: '0.25rem'}}></i>
                        Letzte Indexierung:
                      </div>
                      <div style={{color: 'var(--muted)'}}>
                        <div><strong>Start:</strong> {new Date(indexingDetails.lastIndexingStart * 1000).toLocaleString('de-DE')}</div>
                        <div><strong>Ende:</strong> {new Date(indexingDetails.lastIndexingEnd * 1000).toLocaleString('de-DE')}</div>
                        <div><strong>Dauer:</strong> {Math.round(indexingDetails.lastIndexingDuration)}s</div>
                      </div>
                    </div>
                  )}
                  
                  {indexingDetails.errors.length > 0 && (
                    <div style={{marginTop: '0.5rem', color: 'var(--error)'}}>
                      <strong>Errors:</strong> {indexingDetails.errors.length}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        ) : (
          <>
            <div className="conversation">
              <div className="messages">
                {messages.map((msg) => (
                  <div key={msg.id} className={`message ${msg.role}`}>
                    <div className="bubble">
                      {msg.role === 'assistant' ? (
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {msg.content}
                        </ReactMarkdown>
                      ) : (
                        msg.content
                      )}
                    </div>
                    {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
                      <div className="sources-container">
                        <div className="sources-header">
                          <i className="fas fa-link"></i>
                          <span>Quellen ({msg.sources.length})</span>
                        </div>
                        <div className="sources-grid">
                          {msg.sources.map((source, idx) => (
                            <SourceCard key={idx} source={source} />
                          ))}
                        </div>
                      </div>
                    )}
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
            <div className="composer">
              <input 
                type="text" 
                ref={inputRef}
                placeholder="Your message here..." 
                onKeyPress={(e) => e.key === 'Enter' && !e.ctrlKey && sendMessage(e.target.value)}
              />
              <button onClick={() => sendMessage(inputRef.current?.value || '')} disabled={isThinking}>
                <i className="fas fa-arrow-right"></i>
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
