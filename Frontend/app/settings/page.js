'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useTheme } from '../../hooks/useTheme';
import { useLanguage } from '../../hooks/useLanguage';
import { ThemeSelector } from '../../components/ThemeSelector';

const API_BASE = '';
const SIDEBAR_COLLAPSED_KEY = 'mynd_sidebar_collapsed_v1';
const DISPLAY_NAME_STORAGE_KEY = 'mynd_display_name';

export default function SettingsPage() {
  const router = useRouter();
  const { theme, darkMode, contrastColor, setTheme, setDarkMode, setContrastColor } = useTheme();
  const { language, setLanguage, t, languages } = useLanguage();
  const [activeTab, setActiveTab] = useState('config');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(true);
  const [source, setSource] = useState('auto');
  const [health, setHealth] = useState({ ollama: 'unknown', kb: 'unknown' });
  const [displayName, setDisplayName] = useState('');
  
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
  const [calendarConfig, setCalendarConfig] = useState({
    default_calendar_name: ''
  });
  const [calendarOptions, setCalendarOptions] = useState([]);
  const [calendarConfigStatus, setCalendarConfigStatus] = useState('');
  const [nextcloudConfigured, setNextcloudConfigured] = useState(false);
  const [nextcloudDisplayName, setNextcloudDisplayName] = useState('');
  const [nextcloudLoggingIn, setNextcloudLoggingIn] = useState(false);

  // API Registry State
  const [apis, setApis] = useState([]);
  const [apiHealth, setApiHealth] = useState({});
  const [selectedApi, setSelectedApi] = useState(null);
  const [apiConfig, setApiConfig] = useState({});
  const [apiConfigStatus, setApiConfigStatus] = useState('');

  const tr = (deText, enText) => (language === 'de' ? deText : enText);

  useEffect(() => {
    loadAIConfig();
    loadImmichConfig();
    loadOllamaModels();
    loadNextcloudConfig();
    loadCalendarConfig();
    loadCalendarOptions();
    loadAllApis();
    updateStatus();

    const statusInterval = setInterval(() => {
      updateStatus();
      loadApiHealth();
    }, 8000);
    return () => {
      clearInterval(statusInterval);
    };
  }, []);

  useEffect(() => {
    try {
      const rawSidebarCollapsed = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
      if (rawSidebarCollapsed === 'true' || rawSidebarCollapsed === 'false') {
        setIsSidebarCollapsed(rawSidebarCollapsed === 'true');
      }
    } catch (err) {
      console.error('Error loading sidebar state:', err);
    }
  }, []);

  useEffect(() => {
    try {
      const storedName = localStorage.getItem(DISPLAY_NAME_STORAGE_KEY);
      if (storedName) {
        setDisplayName(storedName);
      }
    } catch (err) {
      console.error('Error loading display name:', err);
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(isSidebarCollapsed));
    } catch (err) {
      console.error('Error saving sidebar state:', err);
    }
  }, [isSidebarCollapsed]);

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
          if (config.display_name || config.username) {
            try {
              const existing = localStorage.getItem(DISPLAY_NAME_STORAGE_KEY);
              if (!existing) {
                localStorage.setItem(DISPLAY_NAME_STORAGE_KEY, config.display_name || config.username);
                setDisplayName(config.display_name || config.username);
              }
            } catch (err) {
              console.error('Error saving display name:', err);
            }
          }
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

  const loadCalendarConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/calendar/config`);
      if (res.ok) {
        const config = await res.json();
        setCalendarConfig({
          default_calendar_name: config.default_calendar_name || ''
        });
      }
    } catch (err) {
      console.error('Error loading calendar config:', err);
    }
  };

  const loadCalendarOptions = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/calendar/calendars`);
      if (res.ok) {
        const data = await res.json();
        setCalendarOptions(data.calendars || []);
      }
    } catch (err) {
      console.error('Error loading calendar options:', err);
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

  const saveCalendarConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/calendar/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(calendarConfig)
      });
      if (res.ok) {
        setCalendarConfigStatus('Standard-Kalender gespeichert');
      } else {
        const data = await res.json();
        setCalendarConfigStatus('Fehler: ' + (data.error || 'Unbekannt'));
      }
    } catch (err) {
      setCalendarConfigStatus('Fehler: ' + err.message);
    }
  };

  const handleNextcloudLogin = async () => {
    if (!nextcloudUrl.trim()) {
      setNextcloudStatus(tr('Bitte gib deine Nextcloud-URL ein', 'Please enter your Nextcloud URL'));
      return;
    }
    try {
      setNextcloudLoggingIn(true);
      setNextcloudStatus(tr('Nextcloud-Login wird geoeffnet...', 'Opening Nextcloud login...'));

      const startRes = await fetch(`${API_BASE}/api/nextcloud/loginflow/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nextcloud_url: nextcloudUrl.trim() })
      });

      const startData = await startRes.json();
      if (!startRes.ok) {
        setNextcloudLoggingIn(false);
        setNextcloudStatus('Error: ' + (startData.error || tr('Nextcloud-Login-Flow konnte nicht gestartet werden', 'Could not start Nextcloud login flow')));
        return;
      }

      window.open(startData.login_url, '_blank', 'noopener,noreferrer');
      setNextcloudStatus(tr('Bitte bestaetige den Login im geoeffneten Nextcloud-Tab...', 'Please confirm login in the opened Nextcloud tab...'));

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
            setNextcloudStatus(tr('Login-Timeout. Bitte versuche es erneut.', 'Login timeout. Please try again.'));
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
      setNextcloudStatus(tr('Verbindung wird getrennt...', 'Disconnecting...'));
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
      setNextcloudStatus(tr('Nextcloud-Verbindung entfernt', 'Nextcloud connection removed'));
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
      setAiStatus(tr('Geladen', 'Loaded'));
    } catch (err) {
      setAiStatus(tr('Fehler beim Laden der Konfiguration', 'Error loading config'));
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
        setImmichStatus(tr('Geladen', 'Loaded'));
      } else {
        setImmichStatus(tr('Fehler beim Laden der Immich-Konfiguration', 'Error loading Immich config'));
      }
    } catch (err) {
      setImmichStatus(tr('Fehler beim Laden der Immich-Konfiguration', 'Error loading Immich config'));
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
        setImmichStatus(tr('Erfolgreich gespeichert', 'Saved successfully'));
      } else {
        setImmichStatus(`Error: ${data?.error || tr('Immich-Konfiguration konnte nicht gespeichert werden', 'Could not save Immich config')}`);
      }
    } catch (err) {
      setImmichStatus('Error: ' + err.message);
    }
  };

  const testImmichConnection = async () => {
    try {
      setImmichStatus(tr('Verbindung wird getestet...', 'Testing connection...'));
      const res = await fetch(`${API_BASE}/api/immich/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });

      const data = await res.json();
      if (res.ok && data?.success) {
        setImmichStatus(tr('Verbindung erfolgreich', 'Connection successful'));
      } else {
        setImmichStatus(`Connection failed: ${data?.error || data?.message || tr('Unbekannter Fehler', 'Unknown error')}`);
      }
    } catch (err) {
      setImmichStatus(tr('Verbindung fehlgeschlagen: ', 'Connection failed: ') + err.message);
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
        setAiStatus(tr('Erfolgreich gespeichert', 'Saved successfully'));
        updateStatus();
      } else {
        setAiStatus(tr('Fehler beim Speichern', 'Error saving'));
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

  // API Registry Functions
  const loadAllApis = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/registry/apis`);
      if (res.ok) {
        const data = await res.json();
        setApis(data.apis || []);
      }
    } catch (err) {
      console.error('Error loading APIs:', err);
    }
  };

  const loadApiHealth = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/registry/health`);
      if (res.ok) {
        const data = await res.json();
        setApiHealth(data.health || {});
      }
    } catch (err) {
      console.error('Error loading API health:', err);
    }
  };

  const loadApiConfig = async (apiName) => {
    try {
      const res = await fetch(`${API_BASE}/api/registry/${apiName}/config`);
      if (res.ok) {
        const data = await res.json();
        setApiConfig(data.config || {});
        setSelectedApi({ ...data, api_name: apiName });
      }
    } catch (err) {
      console.error('Error loading API config:', err);
    }
  };

  const saveApiConfig = async (apiName) => {
    try {
      setApiConfigStatus(tr('Speichern...', 'Saving...'));

      const res = await fetch(`${API_BASE}/api/registry/${apiName}/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: apiConfig })
      });

      if (res.ok) {
        setApiConfigStatus(tr('✓ Gespeichert und Verbindung erfolgreich getestet', '✓ Saved and connection tested successfully'));
        loadAllApis();
        loadApiHealth();
      } else {
        const data = await res.json();
        setApiConfigStatus(tr('Fehler: ', 'Error: ') + (data.error || 'Unknown error'));
      }
    } catch (err) {
      setApiConfigStatus(tr('Fehler: ', 'Error: ') + err.message);
    }
  };

  const testApiConfig = async (apiName) => {
    try {
      setApiConfigStatus(tr('Teste Verbindung...', 'Testing connection...'));

      const res = await fetch(`${API_BASE}/api/registry/${apiName}/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: apiConfig })
      });

      if (res.ok) {
        const data = await res.json();
        if (data.health.status === 'healthy') {
          setApiConfigStatus(tr('✓ Verbindung erfolgreich', '✓ Connection successful'));
        } else {
          setApiConfigStatus(tr('Verbindung fehlgeschlagen: ', 'Connection failed: ') + data.health.error);
        }
      } else {
        const data = await res.json();
        setApiConfigStatus(tr('Fehler: ', 'Error: ') + (data.error || 'Test failed'));
      }
    } catch (err) {
      setApiConfigStatus(tr('Fehler: ', 'Error: ') + err.message);
    }
  };

  const deleteApiConfig = async (apiName) => {
    try {
      const res = await fetch(`${API_BASE}/api/registry/${apiName}/config`, {
        method: 'DELETE'
      });

      if (res.ok) {
        setApiConfigStatus(tr('✓ Konfiguration gelöscht', '✓ Configuration deleted'));
        setSelectedApi(null);
        setApiConfig({});
        loadAllApis();
        loadApiHealth();
      } else {
        const data = await res.json();
        setApiConfigStatus(tr('Fehler: ', 'Error: ') + (data.error || 'Unknown error'));
      }
    } catch (err) {
      setApiConfigStatus(tr('Fehler: ', 'Error: ') + err.message);
    }
  };

  const startNewChat = () => {
    router.push('/');
  };

  return (
    <div className={`container ${isSidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
      {/* LEFT SIDEBAR */}
      <div className={`left-sidebar ${isSidebarCollapsed ? 'collapsed' : ''}`}>
        <div className="sidebar-header">
          <button
            type="button"
            className="brand brand-button"
            onClick={() => router.push('/')}
            aria-label="Zur Startseite"
          >
            <div className="brand-icon">M</div>
            {!isSidebarCollapsed && <span>MYND</span>}
          </button>
          <button
            className="sidebar-toggle"
            type="button"
            onClick={() => setIsSidebarCollapsed((prev) => !prev)}
            aria-label={isSidebarCollapsed ? 'Seitenleiste ausklappen' : 'Seitenleiste einklappen'}
          >
            <i className={`fas ${isSidebarCollapsed ? 'fa-angle-right' : 'fa-angle-left'}`}></i>
          </button>
        </div>
        {isSidebarCollapsed ? (
          <button className="new-chat-btn compact" onClick={startNewChat} title={t('newChat')}>
            <i className="fas fa-plus"></i>
          </button>
        ) : (
          <button className="new-chat-btn" onClick={startNewChat}>
            <i className="fas fa-plus"></i> {t('newChat')}
          </button>
        )}
        <div className="chat-history">
          {isSidebarCollapsed ? (
            <button type="button" className="history-item active" onClick={startNewChat} title={t('currentChat')}>
              <i className="fas fa-message"></i>
            </button>
          ) : (
            <div className="history-item">
              <i className="fas fa-message"></i>
              <span>{t('currentChat')}</span>
            </div>
          )}
        </div>
        <div className="sidebar-footer">
          <button className="new-chat-btn settings-btn active" type="button">
            <i className="fas fa-cog"></i> {!isSidebarCollapsed && t('settings')}
          </button>
          <div className="status-badges">
            <div className={`status-badge ${health.ollama}`}>
              <div className={`status-dot ${health.ollama}`}></div>
              <div className="status-meta">
                <span className="status-label">Ollama</span>
                <span className="status-value">{health.ollama === 'ok' ? 'Online' : 'Offline'}</span>
              </div>
            </div>
            <div className={`status-badge ${health.kb}`}>
              <div className={`status-dot ${health.kb}`}></div>
              <div className="status-meta">
                <span className="status-label">KB</span>
                <span className="status-value">{health.kb === 'ok' ? 'Verbunden' : 'Offline'}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* CENTER - Settings Full Screen */}
      <div className="center-area">
        <div className="settings-full">
          <div className="settings-tabs">
            <button className={`tab-btn ${activeTab === 'config' ? 'active' : ''}`} onClick={() => setActiveTab('config')}>{t('tabConfig')}</button>
            <button className={`tab-btn ${activeTab === 'apis' ? 'active' : ''}`} onClick={() => setActiveTab('apis')}>{tr('APIs', 'APIs')}</button>
            <button className={`tab-btn ${activeTab === 'indexing' ? 'active' : ''}`} onClick={() => setActiveTab('indexing')}>{t('tabIndexing')}</button>
            <button className={`tab-btn ${activeTab === 'sources' ? 'active' : ''}`} onClick={() => setActiveTab('sources')}>{t('tabSources')}</button>
            <button className={`tab-btn ${activeTab === 'design' ? 'active' : ''}`} onClick={() => setActiveTab('design')}>{t('tabDesign')}</button>
          </div>
          <div className="settings-content">
            {activeTab === 'config' && (
              <div className="settings-panel">
                <div className="panel-section">
                  <div className="section-title">{t('aiModel')}</div>
                  <div className="input-group">
                    <label>{t('protocol')}</label>
                    <select value={aiProtocol} onChange={(e) => setAiProtocol(e.target.value)}>
                      <option>http</option>
                      <option>https</option>
                    </select>
                  </div>
                  <div className="input-group">
                    <label>{t('host')}</label>
                    <input type="text" value={aiHost} onChange={(e) => setAiHost(e.target.value)} />
                  </div>
                  <div className="input-group">
                    <label>{t('port')}</label>
                    <input type="text" value={aiPort} onChange={(e) => setAiPort(e.target.value)} />
                  </div>
                  <div className="input-group">
                    <label>{t('model')}</label>
                    <select value={aiModel} onChange={(e) => setAiModel(e.target.value)}>
                      <option value="">{t('selectModel')}</option>
                      {aiModels.map(model => <option key={model} value={model}>{model}</option>)}
                    </select>
                  </div>
                  <div className="button-group">
                    <button className="btn primary" onClick={saveAIConfig}>{t('save')}</button>
                  </div>
                  {aiStatus && <div className="status-text">{aiStatus}</div>}
                </div>

                <div className="panel-section" style={{marginTop: '2rem'}}>
                  <div className="section-title">Personalisierung</div>
                  <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
                    Dieser Name wird fuer die persoenliche Begruessung auf der Startseite genutzt.
                  </p>
                  <div className="input-group">
                    <label>Anzeigename</label>
                    <input
                      type="text"
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      placeholder="z.B. Vinzenz"
                    />
                  </div>
                  <div className="button-group">
                    <button className="btn primary" onClick={saveDisplayName}>Speichern</button>
                  </div>
                </div>

                <div className="panel-section" style={{marginTop: '2rem'}}>
                  <div className="section-title">{tr('Immich-Integration', 'Immich Integration')}</div>
                  <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
                    {tr('Globale Immich-Standards fuer die Fotosuche konfigurieren.', 'Configure global Immich defaults for photo search.')}
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
                    <button className="btn primary" onClick={saveImmichConfig}>{tr('Immich speichern', 'Save Immich')}</button>
                    <button className="btn" onClick={testImmichConnection}>{tr('Verbindung testen', 'Test Connection')}</button>
                  </div>
                  {immichStatus && <div className="status-text">{immichStatus}</div>}
                </div>

                <div className="panel-section" style={{marginTop: '2rem'}}>
                  <div className="section-title">Kalender Standard</div>
                  <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
                    Dieser Kalender wird verwendet, wenn beim Erstellen eines Termins kein Kalender angegeben wird.
                  </p>
                  <div className="input-group">
                    <label>Standard-Kalender</label>
                    <select
                      value={calendarConfig.default_calendar_name}
                      onChange={(e) => setCalendarConfig(prev => ({ ...prev, default_calendar_name: e.target.value }))}
                    >
                      <option value="">(Kein Standard - erster Kalender)</option>
                      {calendarOptions.map((cal, idx) => (
                        <option key={`${cal.name}-${idx}`} value={cal.name}>{cal.name}</option>
                      ))}
                    </select>
                  </div>
                  <div className="button-group">
                    <button className="btn primary" onClick={saveCalendarConfig}>Standard speichern</button>
                    <button className="btn" onClick={loadCalendarOptions}>{tr('Kalender neu laden', 'Reload calendars')}</button>
                  </div>
                  {calendarConfigStatus && <div className="status-text">{calendarConfigStatus}</div>}
                </div>
              </div>
            )}
            {activeTab === 'apis' && (
              <div className="settings-panel">
                <div className="panel-section">
                  <div className="section-title">{tr('API Integrationen', 'API Integrations')}</div>
                  <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0 1.5rem 0'}}>
                    {tr('Konfiguriere externe APIs für erweiterte Funktionen', 'Configure external APIs for extended functionality')}
                  </p>

                  {/* API List */}
                  <div style={{display: 'grid', gap: '1rem', marginBottom: '2rem'}}>
                    {apis.map((api) => {
                      const health = apiHealth[api.api_name] || {};
                      const isHealthy = health.status === 'healthy';
                      const isConfigured = api.configured;

                      return (
                        <div
                          key={api.api_name}
                          style={{
                            padding: '1rem',
                            background: 'var(--panel-bg)',
                            border: '1px solid var(--border)',
                            borderRadius: '8px',
                            cursor: 'pointer',
                            transition: 'all 0.2s'
                          }}
                          onClick={() => {
                            loadApiConfig(api.api_name);
                            setApiConfigStatus('');
                          }}
                        >
                          <div style={{display: 'flex', alignItems: 'center', justifyContent: 'space-between'}}>
                            <div style={{display: 'flex', alignItems: 'center', gap: '1rem'}}>
                              <div style={{
                                width: '12px',
                                height: '12px',
                                borderRadius: '50%',
                                background: isConfigured ? (isHealthy ? 'var(--success)' : 'var(--error)') : 'var(--muted)'
                              }}></div>
                              <div>
                                <div style={{fontWeight: '600', textTransform: 'capitalize'}}>
                                  {api.api_name === 'homeassistant' ? 'Home Assistant' :
                                   api.api_name === 'uptimekuma' ? 'Uptime Kuma' : api.api_name}
                                </div>
                                <div style={{fontSize: '0.85rem', color: 'var(--muted)'}}>
                                  {isConfigured ?
                                    (isHealthy ? tr('✓ Verbunden', '✓ Connected') : tr('✗ Nicht erreichbar', '✗ Not reachable')) :
                                    tr('Nicht konfiguriert', 'Not configured')}
                                </div>
                              </div>
                            </div>
                            {health.response_time && (
                              <div style={{fontSize: '0.85rem', color: 'var(--muted)'}}>
                                {Math.round(health.response_time * 1000)}ms
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* API Configuration Form */}
                  {selectedApi && (
                    <div style={{marginTop: '2rem', padding: '1.5rem', background: 'var(--background)', border: '1px solid var(--border)', borderRadius: '8px'}}>
                      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem'}}>
                        <div className="section-title" style={{textTransform: 'capitalize'}}>
                          {selectedApi.api_name === 'homeassistant' ? 'Home Assistant' :
                           selectedApi.api_name === 'uptimekuma' ? 'Uptime Kuma' : selectedApi.api_name}
                        </div>
                        <button
                          className="btn"
                          onClick={() => {
                            setSelectedApi(null);
                            setApiConfig({});
                            setApiConfigStatus('');
                          }}
                          style={{padding: '0.5rem 1rem'}}
                        >
                          {tr('Schließen', 'Close')}
                        </button>
                      </div>

                      {/* Dynamic config fields based on schema */}
                      {selectedApi.schema && Object.entries(selectedApi.schema).map(([key, fieldSchema]) => (
                        <div key={key} className="input-group">
                          <label>
                            {fieldSchema.description || key}
                            {fieldSchema.required && <span style={{color: 'var(--error)'}}>*</span>}
                          </label>
                          <input
                            type={fieldSchema.secret ? 'password' : fieldSchema.type === 'number' ? 'number' : 'text'}
                            value={apiConfig[key] || ''}
                            onChange={(e) => setApiConfig(prev => ({...prev, [key]: e.target.value}))}
                            placeholder={fieldSchema.example || fieldSchema.default || ''}
                          />
                          {fieldSchema.description && (
                            <small style={{fontSize: '0.8rem', color: 'var(--muted)', display: 'block', marginTop: '0.25rem'}}>
                              {fieldSchema.type === 'string' && fieldSchema.example ? `${tr('Beispiel', 'Example')}: ${fieldSchema.example}` : ''}
                            </small>
                          )}
                        </div>
                      ))}

                      <div className="button-group" style={{marginTop: '1.5rem'}}>
                        <button
                          className="btn primary"
                          onClick={() => saveApiConfig(selectedApi.api_name)}
                        >
                          {tr('Speichern', 'Save')}
                        </button>
                        <button
                          className="btn"
                          onClick={() => testApiConfig(selectedApi.api_name)}
                        >
                          {tr('Verbindung testen', 'Test Connection')}
                        </button>
                        {selectedApi.configured && (
                          <button
                            className="btn"
                            onClick={() => {
                              if (confirm(tr('Möchtest du diese API-Konfiguration wirklich löschen?', 'Do you really want to delete this API configuration?'))) {
                                deleteApiConfig(selectedApi.api_name);
                              }
                            }}
                            style={{background: 'var(--error)', color: 'white'}}
                          >
                            {tr('Löschen', 'Delete')}
                          </button>
                        )}
                      </div>
                      {apiConfigStatus && <div className="status-text" style={{marginTop: '1rem'}}>{apiConfigStatus}</div>}
                    </div>
                  )}
                </div>
              </div>
            )}
            {activeTab === 'indexing' && (
              <div className="settings-panel">
                <div className="panel-section">
                  <div className="section-title">{tr('Nextcloud-Login', 'Nextcloud Login')}</div>
                  <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
                    {tr('Verbinde deine Nextcloud-Instanz fuer die Dokumenten-Indexierung', 'Connect to your Nextcloud instance for document indexing')}
                  </p>

                  {nextcloudConfigured ? (
                    <div style={{padding: '1rem', background: 'var(--background)', borderRadius: '8px', border: '2px solid var(--success)', marginBottom: '1.5rem'}}>
                      <div style={{display: 'flex', alignItems: 'center', marginBottom: '0.5rem'}}>
                        <i className="fas fa-check-circle" style={{color: 'var(--success)', marginRight: '0.5rem', fontSize: '1.4rem'}}></i>
                        <span style={{fontWeight: '600', fontSize: '1.1rem'}}>{tr('Verbunden', 'Connected')}</span>
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
                          {tr('Gib deine Nextcloud-URL ein. Du wirst zur Anmeldung auf deine Nextcloud-Seite weitergeleitet.', "Enter your Nextcloud URL. You'll be redirected to your Nextcloud instance to log in with your normal credentials.")}
                        </small>
                      </div>
                      <div className="button-group">
                        <button className="btn primary" onClick={handleNextcloudLogin} disabled={nextcloudLoggingIn || !nextcloudUrl.trim()}>
                          <i className="fas fa-sign-in-alt" style={{marginRight: '0.5rem'}}></i>
                          {nextcloudLoggingIn ? tr('Warte auf Bestaetigung...', 'Waiting for confirmation...') : tr('Mit Nextcloud anmelden', 'Login with Nextcloud')}
                        </button>
                      </div>
                      {nextcloudStatus && <div className="status-text">{nextcloudStatus}</div>}
                    </>
                  )}
                </div>
                
                <div className="panel-section" style={{marginTop: '2rem'}}>
                  <div className="section-title">{tr('Dokumenten-Indexierung', 'Document Indexing')}</div>
                  <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
                    {tr('Indexiere deine Dokumente fuer die semantische Suche mit detaillierter Fortschrittsanzeige', 'Index your documents for semantic search with detailed progress tracking')}
                  </p>
                  <div className="button-group">
                    <button className="btn primary" onClick={startIndexing} disabled={indexingStatus === 'running'}>
                      {indexingStatus === 'running' ? tr('Indexierung laeuft...', 'Indexing...') : tr('Indexierung starten', 'Start Indexing')}
                    </button>
                    {indexingStatus === 'running' && (
                      <button className="btn secondary" onClick={() => fetch(`${API_BASE}/api/indexing/stop`, {method: 'POST'})}>
                        {tr('Stoppen', 'Stop')}
                      </button>
                    )}
                  </div>
                  
                  {/* Progress Section */}
                  {(indexingStatus !== 'idle' || indexingDetails.processedFiles > 0) && (
                    <div style={{marginTop: '1.5rem', padding: '1rem', background: 'var(--surface)', borderRadius: '8px', border: '1px solid var(--border)'}}>
                      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem'}}>
                        <h4 style={{margin: 0, fontSize: '1rem', fontWeight: '600'}}>
                          <i className="fas fa-chart-line" style={{marginRight: '0.5rem'}}></i>
                          {tr('Indexierungsfortschritt', 'Indexing Progress')}
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
                            <span>{indexingProgress}% {tr('abgeschlossen', 'Complete')}</span>
                            <span>{indexingDetails.processedFiles} / {indexingDetails.totalFiles} {tr('Dateien', 'files')}</span>
                          </div>
                        </div>
                      )}
                      
                      {/* Detailed Statistics Grid */}
                      <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem', marginBottom: '1rem'}}>
                        <div style={{textAlign: 'center', padding: '0.75rem', background: 'var(--background)', borderRadius: '6px'}}>
                          <div style={{fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--primary)'}}>
                            {indexingDetails.processedFiles}
                          </div>
                          <div style={{fontSize: '0.75rem', color: 'var(--muted)'}}>{tr('Dateien verarbeitet', 'Files Processed')}</div>
                        </div>
                        <div style={{textAlign: 'center', padding: '0.75rem', background: 'var(--background)', borderRadius: '6px'}}>
                          <div style={{fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--success)'}}>
                            {indexingDetails.processingSpeed}
                          </div>
                          <div style={{fontSize: '0.75rem', color: 'var(--muted)'}}>{tr('Dateien/Sekunde', 'Files/Second')}</div>
                        </div>
                        <div style={{textAlign: 'center', padding: '0.75rem', background: 'var(--background)', borderRadius: '6px'}}>
                          <div style={{fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--accent)'}}>
                            {Math.floor(indexingDetails.elapsedTime / 60)}:{(indexingDetails.elapsedTime % 60).toString().padStart(2, '0')}
                          </div>
                          <div style={{fontSize: '0.75rem', color: 'var(--muted)'}}>{tr('Verstrichene Zeit', 'Time Elapsed')}</div>
                        </div>
                        <div style={{textAlign: 'center', padding: '0.75rem', background: 'var(--background)', borderRadius: '6px'}}>
                          <div style={{fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--warning)'}}>
                            {indexingDetails.estimatedTimeRemaining > 0 ? `${Math.floor(indexingDetails.estimatedTimeRemaining / 60)}:${(indexingDetails.estimatedTimeRemaining % 60).toString().padStart(2, '0')}` : '--:--'}
                          </div>
                          <div style={{fontSize: '0.75rem', color: 'var(--muted)'}}>{tr('Restzeit', 'Time Remaining')}</div>
                        </div>
                      </div>
                      
                      {/* Current File and Additional Details */}
                      {indexingDetails.currentFile && (
                        <div style={{marginBottom: '1rem', padding: '0.75rem', background: 'var(--background)', borderRadius: '6px', fontSize: '0.85rem'}}>
                          <div style={{fontWeight: '600', marginBottom: '0.25rem', color: 'var(--text)'}}>
                            <i className="fas fa-file-alt" style={{marginRight: '0.5rem'}}></i>
                            {tr('Wird gerade verarbeitet:', 'Currently Processing:')}
                          </div>
                          <div style={{color: 'var(--muted)', wordBreak: 'break-all'}}>{indexingDetails.currentFile}</div>
                        </div>
                      )}
                      
                      {/* Summary Stats */}
                      <div style={{fontSize: '0.8rem', color: 'var(--muted)'}}>
                        {indexingStats && <div style={{marginBottom: '0.5rem', fontWeight: '500'}}>{indexingStats}</div>}
                        
                        <div style={{display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem'}}>
                          <span><strong>{tr('Dokumente', 'Documents')}:</strong> {indexingDetails.documentsProcessed}</span>
                          <span><strong>{tr('Chunks erstellt', 'Chunks Created')}:</strong> ~{indexingDetails.chunksCreated}</span>
                          {indexingDetails.errors.length > 0 && (
                            <span style={{color: 'var(--error)'}}><strong>{tr('Fehler', 'Errors')}:</strong> {indexingDetails.errors.length}</span>
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
                            {tr('Letzte Fehler:', 'Recent Errors:')}
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
                  <div className="section-title">{tr('Nachrichtenquellen', 'Message Sources')}</div>
                  <div className="input-group">
                    <label><input type="radio" name="source" value="auto" checked={source === 'auto'} onChange={(e) => setSource(e.target.value)} /> Auto</label>
                    <label><input type="radio" name="source" value="files" checked={source === 'files'} onChange={(e) => setSource(e.target.value)} /> {tr('Dateien', 'Files')}</label>
                    <label><input type="radio" name="source" value="photos" checked={source === 'photos'} onChange={(e) => setSource(e.target.value)} /> {tr('Fotos', 'Photos')}</label>
                  </div>
                </div>
              </div>
            )}
            {activeTab === 'design' && (
              <div className="settings-panel">
                <div className="input-group" style={{ marginBottom: '1rem' }}>
                  <label>{t('language')}</label>
                  <select value={language} onChange={(e) => setLanguage(e.target.value)}>
                    {languages.map((entry) => (
                      <option key={entry.code} value={entry.code}>{entry.label}</option>
                    ))}
                  </select>
                </div>
                <ThemeSelector
                  currentTheme={theme}
                  onThemeChange={setTheme}
                  currentDarkMode={darkMode}
                  onDarkModeChange={setDarkMode}
                  contrastColor={contrastColor}
                  onContrastColorChange={setContrastColor}
                  showContrastColor={true}
                  labels={{
                    theme: t('theme'),
                    darkMode: t('darkMode'),
                    reset: 'Reset',
                    contrastColor: 'Kontrastfarbe (optional)',
                    themes: {
                      classic: 'Classic',
                      ocean: 'Ocean',
                      graphite: 'Graphite',
                      lavender: 'Lavender',
                      rose: 'Rose',
                      gold: 'Gold'
                    },
                    modes: {
                      light: t('modeLight'),
                      dark: t('modeDark'),
                      auto: t('modeAuto')
                    }
                  }}
                />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
