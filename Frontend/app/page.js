'use client';

import { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

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
              setIndexingProgress(Math.round(data.progress_percentage));
              setIndexingStats(`${data.processed_files}/${data.total_files} files | ${Math.round(data.elapsed_time)}s`);
              if (data.status === 'completed' || data.status === 'error') {
                setIndexingStatus(data.status);
                clearInterval(progressIntervalRef.current);
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
      setMessages(prev => [...prev, { role: 'assistant', content: data.response, id: Date.now() }]);
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
