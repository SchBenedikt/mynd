'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useTheme } from '../../hooks/useTheme';
import { useLanguage } from '../../hooks/useLanguage';
import { ThemeSelector } from '../../components/ThemeSelector';

const API_BASE = '';
const SIDEBAR_COLLAPSED_KEY = 'mynd_sidebar_collapsed_v1';
const DISPLAY_NAME_STORAGE_KEY = 'mynd_display_name';
const API_DISPLAY_NAMES = {
  immich: 'Immich',
  homeassistant: 'Home Assistant',
  uptimekuma: 'Uptime Kuma',
  openweather: 'OpenWeather',
  nina: 'NINA',
  autobahn: 'Autobahn',
  dashboard_deutschland: 'Dashboard Deutschland',
  deutschland_atlas: 'Deutschland Atlas',
  email: 'E-Mail'
};

const EMAIL_PROVIDER_PRESETS = {
  custom: {
    labelDe: 'Eigene Angaben',
    labelEn: 'Custom',
    values: {}
  },
  'web.de': {
    labelDe: 'WEB.DE',
    labelEn: 'WEB.DE',
    values: {
      imap_host: 'imap.web.de',
      imap_port: '993',
      use_ssl: 'true',
      smtp_host: 'smtp.web.de',
      smtp_port: '587',
      smtp_starttls: 'true',
      smtp_use_ssl: 'false'
    }
  },
  'gmx.de': {
    labelDe: 'GMX',
    labelEn: 'GMX',
    values: {
      imap_host: 'imap.gmx.net',
      imap_port: '993',
      use_ssl: 'true',
      smtp_host: 'mail.gmx.net',
      smtp_port: '587',
      smtp_starttls: 'true',
      smtp_use_ssl: 'false'
    }
  },
  'gmail.com': {
    labelDe: 'Gmail',
    labelEn: 'Gmail',
    values: {
      imap_host: 'imap.gmail.com',
      imap_port: '993',
      use_ssl: 'true',
      smtp_host: 'smtp.gmail.com',
      smtp_port: '587',
      smtp_starttls: 'true',
      smtp_use_ssl: 'false'
    }
  },
  'outlook.com': {
    labelDe: 'Outlook / Microsoft',
    labelEn: 'Outlook / Microsoft',
    values: {
      imap_host: 'outlook.office365.com',
      imap_port: '993',
      use_ssl: 'true',
      smtp_host: 'smtp.office365.com',
      smtp_port: '587',
      smtp_starttls: 'true',
      smtp_use_ssl: 'false'
    }
  }
};

const EMAIL_ACCOUNT_FIELDS = [
  'provider_preset',
  'username',
  'password',
  'imap_host',
  'imap_port',
  'use_ssl',
  'smtp_host',
  'smtp_port',
  'smtp_starttls',
  'smtp_use_ssl',
  'folders',
  'max_emails',
  'from_name',
  'from_address'
];

const _pickEmailFields = (value = {}) => {
  const picked = {};
  EMAIL_ACCOUNT_FIELDS.forEach((field) => {
    if (Object.prototype.hasOwnProperty.call(value, field)) {
      picked[field] = value[field];
    }
  });
  return picked;
};

const _normalizeSingleEmailAccount = (rawAccount = {}, fallbackId = 'account_1', fallbackName = '') => {
  const accountId = String(rawAccount.account_id || rawAccount.id || fallbackId).trim() || fallbackId;
  const username = String(rawAccount.username || '').trim();
  const displayName = String(rawAccount.display_name || fallbackName || username || accountId).trim();
  return {
    account_id: accountId,
    display_name: displayName,
    provider_preset: 'custom',
    folders: 'INBOX',
    use_ssl: 'true',
    smtp_starttls: 'true',
    smtp_use_ssl: 'false',
    max_emails: '50',
    ..._pickEmailFields(rawAccount)
  };
};

const normalizeEmailConfig = (config = {}) => {
  const base = { ...(config || {}) };
  let accounts = Array.isArray(base.accounts)
    ? base.accounts
        .filter((item) => item && typeof item === 'object')
        .map((item, index) => _normalizeSingleEmailAccount(item, `account_${index + 1}`))
    : [];

  if (accounts.length === 0) {
    const hasLegacyFields = ['username', 'imap_host', 'password', 'smtp_host'].some((key) => {
      const value = base[key];
      return value !== undefined && value !== null && String(value).trim() !== '';
    });

    if (hasLegacyFields) {
      accounts = [_normalizeSingleEmailAccount(base, 'account_1')];
    }
  }

  if (accounts.length === 0) {
    accounts = [_normalizeSingleEmailAccount({}, 'account_1', 'Konto 1')];
  }

  let activeAccountId = String(base.active_account_id || base.selected_account_id || base.account_id || '').trim();
  if (!accounts.find((account) => account.account_id === activeAccountId)) {
    activeAccountId = accounts[0].account_id;
  }

  const activeAccount = accounts.find((account) => account.account_id === activeAccountId) || accounts[0];

  return {
    ...base,
    accounts,
    active_account_id: activeAccountId,
    selected_account_id: activeAccountId,
    ..._pickEmailFields(activeAccount)
  };
};

export default function SettingsPage() {
  const router = useRouter();
  const { theme, darkMode, motionStyle, contrastColor, setTheme, setDarkMode, setMotionStyle, setContrastColor } = useTheme();
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
  const [indexingPath, setIndexingPath] = useState('');
  const [indexingPathStatus, setIndexingPathStatus] = useState('');
  
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
  const [emailFolderOptions, setEmailFolderOptions] = useState([]);
  const [emailFolderStatus, setEmailFolderStatus] = useState('');
  const [apiQuery, setApiQuery] = useState('');
  const [ninaRegions, setNinaRegions] = useState([]);
  const [ninaRegionStatus, setNinaRegionStatus] = useState('');
  const [ninaRegionQuery, setNinaRegionQuery] = useState('');
  const [ninaWarnings, setNinaWarnings] = useState([]);
  const [ninaWarningsStatus, setNinaWarningsStatus] = useState('');
  const [ninaWarningsArs, setNinaWarningsArs] = useState('');
  const [locationStatus, setLocationStatus] = useState('');
  const [locationResult, setLocationResult] = useState(null);

  const tr = (deText, enText) => (language === 'de' ? deText : enText);
  const getApiDisplayName = (apiName) => API_DISPLAY_NAMES[apiName] || apiName;
  const immichConfigured = Boolean(immichUrlDefault && immichApiKeyDefault);
  const normalizedEmailConfig = normalizeEmailConfig(apiConfig);
  const emailAccounts = selectedApi?.api_name === 'email' ? normalizedEmailConfig.accounts : [];
  const activeEmailAccountId = selectedApi?.api_name === 'email' ? normalizedEmailConfig.active_account_id : '';
  const activeEmailAccount = selectedApi?.api_name === 'email'
    ? (emailAccounts.find((account) => account.account_id === activeEmailAccountId) || emailAccounts[0] || {})
    : {};
  const emailPresetKey = activeEmailAccount.provider_preset || 'custom';
  const emailFoldersAreAll = String(activeEmailAccount.folders || '').trim().toUpperCase() === 'ALL';
  const emailSelectedFolders = emailFoldersAreAll
    ? emailFolderOptions
    : String(activeEmailAccount.folders || '')
        .split(',')
        .map((folder) => folder.trim())
        .filter(Boolean);
  const catalogApis = [{ api_name: 'immich', configured: immichConfigured, isImmichSpecial: true }, ...apis];
  const normalizedApiQuery = apiQuery.trim().toLowerCase();
  const visibleApis = catalogApis
    .filter((api) => {
      if (!normalizedApiQuery) return true;
      const name = getApiDisplayName(api.api_name).toLowerCase();
      const key = String(api.api_name || '').toLowerCase();
      return name.includes(normalizedApiQuery) || key.includes(normalizedApiQuery);
    })
    .sort((a, b) => {
      if (a.configured !== b.configured) {
        return a.configured ? -1 : 1;
      }
      return getApiDisplayName(a.api_name).localeCompare(getApiDisplayName(b.api_name));
    });
  const configuredApiCount = catalogApis.filter((api) => api.configured).length;
  const healthyApiCount = catalogApis.filter((api) => apiHealth[api.api_name]?.status === 'healthy').length;

  useEffect(() => {
    loadAIConfig();
    loadImmichConfig();
    loadOllamaModels();
    loadNextcloudConfig();
    loadCalendarConfig();
    loadCalendarOptions();
    loadIndexingConfig();
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
          loadCalendarOptions();
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
        const calendars = data.calendars || [];
        setCalendarOptions(calendars);
        if (calendars.length === 0) {
          setCalendarConfigStatus(tr('Keine Kalender gefunden', 'No calendars found'));
        } else {
          setCalendarConfigStatus('');
        }
      } else {
        let message = tr('Kalender konnten nicht geladen werden', 'Could not load calendars');
        try {
          const data = await res.json();
          if (data?.error) {
            message = data.error;
          }
        } catch (_) {
          // Keep generic fallback message if non-JSON response.
        }
        setCalendarOptions([]);
        setCalendarConfigStatus(tr('Fehler: ', 'Error: ') + message);
      }
    } catch (err) {
      console.error('Error loading calendar options:', err);
      setCalendarOptions([]);
      setCalendarConfigStatus(tr('Fehler: ', 'Error: ') + err.message);
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
            loadCalendarOptions();
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
        loadApiHealth();
      } else {
        setImmichStatus(`Error: ${data?.error || tr('Immich-Konfiguration konnte nicht gespeichert werden', 'Could not save Immich config')}`);
        loadApiHealth();
      }
    } catch (err) {
      setImmichStatus('Error: ' + err.message);
      loadApiHealth();
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
        loadApiHealth();
      } else {
        setImmichStatus(`Connection failed: ${data?.error || data?.message || tr('Unbekannter Fehler', 'Unknown error')}`);
        loadApiHealth();
      }
    } catch (err) {
      setImmichStatus(tr('Verbindung fehlgeschlagen: ', 'Connection failed: ') + err.message);
      loadApiHealth();
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

  const loadIndexingConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/indexing/path`);
      if (res.ok) {
        const data = await res.json();
        setIndexingPath(data.path || '');
      }
    } catch (err) {
      console.error('Error loading indexing path:', err);
    }
  };

  const saveIndexingConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/indexing/path`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: indexingPath })
      });
      if (res.ok) {
        setIndexingPathStatus(tr('✓ Pfad gespeichert', '✓ Path saved'));
      } else {
        const data = await res.json();
        setIndexingPathStatus(tr('Fehler: ', 'Error: ') + (data.error || 'Unknown error'));
      }
    } catch (err) {
      setIndexingPathStatus('Error: ' + err.message);
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
        body: JSON.stringify({ path: indexingPath || undefined })
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
      const [registryRes, immichRes] = await Promise.all([
        fetch(`${API_BASE}/api/registry/health`),
        fetch(`${API_BASE}/api/immich/test`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({})
        })
      ]);

      const healthMap = {};

      if (registryRes.ok) {
        const registryData = await registryRes.json();
        Object.assign(healthMap, registryData.health || {});
      }

      const immichStart = performance.now();
      let immichPayload = {};
      try {
        immichPayload = await immichRes.json();
      } catch (_) {
        immichPayload = {};
      }
      const immichElapsedSeconds = (performance.now() - immichStart) / 1000;

      healthMap.immich = {
        status: immichRes.ok && immichPayload?.success ? 'healthy' : 'unhealthy',
        response_time: immichElapsedSeconds,
        error: immichRes.ok && immichPayload?.success ? null : (immichPayload?.error || immichPayload?.message || 'Connection test failed')
      };

      setApiHealth(healthMap);
    } catch (err) {
      console.error('Error loading API health:', err);
    }
  };

  const loadApiConfig = async (apiName) => {
    try {
      const res = await fetch(`${API_BASE}/api/registry/${apiName}/config`);
      if (res.ok) {
        const data = await res.json();
        const loadedConfig = data.config || {};
        setApiConfig(apiName === 'email' ? normalizeEmailConfig(loadedConfig) : loadedConfig);
        setSelectedApi({ ...data, api_name: apiName });
        setNinaRegions([]);
        setNinaRegionStatus('');
        setNinaWarnings([]);
        setNinaWarningsStatus('');
        setNinaWarningsArs('');
        setLocationStatus('');
        setLocationResult(null);

        if (apiName === 'email') {
          loadEmailFolders(normalizeEmailConfig(loadedConfig));
        }
      }
    } catch (err) {
      console.error('Error loading API config:', err);
    }
  };

  const applyEmailPreset = (presetKey) => {
    const preset = EMAIL_PROVIDER_PRESETS[presetKey] || EMAIL_PROVIDER_PRESETS.custom;
    setApiConfig((prev) => {
      const normalized = normalizeEmailConfig(prev);
      const accountId = normalized.active_account_id;
      const accounts = normalized.accounts.map((account) => (
        account.account_id === accountId
          ? { ...account, provider_preset: presetKey, ...preset.values }
          : account
      ));
      return normalizeEmailConfig({ ...normalized, accounts });
    });
  };

  const setActiveEmailAccount = (accountId) => {
    setApiConfig((prev) => {
      const normalized = normalizeEmailConfig(prev);
      return normalizeEmailConfig({ ...normalized, active_account_id: accountId, selected_account_id: accountId });
    });
  };

  const updateActiveEmailAccount = (patch = {}) => {
    setApiConfig((prev) => {
      const normalized = normalizeEmailConfig(prev);
      const accountId = normalized.active_account_id;
      const accounts = normalized.accounts.map((account) => (
        account.account_id === accountId
          ? { ...account, ...patch }
          : account
      ));
      return normalizeEmailConfig({ ...normalized, accounts });
    });
  };

  const addEmailAccount = () => {
    setApiConfig((prev) => {
      const normalized = normalizeEmailConfig(prev);
      const nextIndex = normalized.accounts.length + 1;
      const newAccount = _normalizeSingleEmailAccount({}, `account_${nextIndex}`, `Konto ${nextIndex}`);
      const accounts = [...normalized.accounts, newAccount];
      return normalizeEmailConfig({ ...normalized, accounts, active_account_id: newAccount.account_id });
    });
    setEmailFolderOptions([]);
    setEmailFolderStatus('');
  };

  const removeEmailAccount = () => {
    setApiConfig((prev) => {
      const normalized = normalizeEmailConfig(prev);
      if (normalized.accounts.length <= 1) {
        return normalized;
      }
      const accountId = normalized.active_account_id;
      const remaining = normalized.accounts.filter((account) => account.account_id !== accountId);
      return normalizeEmailConfig({ ...normalized, accounts: remaining, active_account_id: remaining[0].account_id });
    });
    setEmailFolderOptions([]);
    setEmailFolderStatus('');
  };

  const loadEmailFolders = async (configOverride = {}) => {
    try {
      setEmailFolderStatus(tr('Ordner werden geladen...', 'Loading folders...'));
      const mergedConfig = normalizeEmailConfig({ ...apiConfig, ...configOverride });
      const res = await fetch(`${API_BASE}/api/email/folders`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          account_id: mergedConfig.active_account_id,
          config: mergedConfig
        })
      });

      const data = await res.json();
      if (!res.ok || data?.success === false) {
        setEmailFolderOptions([]);
        setEmailFolderStatus(tr('Fehler: ', 'Error: ') + (data?.error || 'Unknown error'));
        return;
      }

      setEmailFolderOptions(data.folders || []);
      setEmailFolderStatus(
        (data.folders || []).length > 0
          ? tr(`✓ ${data.folders.length} Ordner gefunden`, `✓ ${data.folders.length} folders found`)
          : tr('Keine Ordner gefunden', 'No folders found')
      );
    } catch (err) {
      setEmailFolderOptions([]);
      setEmailFolderStatus(tr('Fehler: ', 'Error: ') + err.message);
    }
  };

  const updateEmailFolders = (selectedFolders) => {
    updateActiveEmailAccount({
      folders: selectedFolders.length > 0 ? selectedFolders.join(', ') : 'INBOX'
    });
  };

  const loadNinaRegions = async () => {
    try {
      setNinaRegionStatus(tr('Lade Regionalschluessel...', 'Loading regional keys...'));
      const params = new URLSearchParams();
      if (ninaRegionQuery.trim()) {
        params.set('query', ninaRegionQuery.trim());
      }
      params.set('limit', '200');

      const res = await fetch(`${API_BASE}/api/nina/regions?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        const items = (data.data && data.data.items) ? data.data.items : [];
        setNinaRegions(items);

        // Auto-apply best match so users do not need an extra manual selection step.
        if (items.length > 0 && items[0].ars) {
          setApiConfig(prev => ({ ...prev, ars: items[0].ars }));
        }

        setNinaRegionStatus(
          items.length > 0
            ? tr(
                `✓ ${items.length} Treffer (ARS automatisch gesetzt: ${items[0].ars})`,
                `✓ ${items.length} matches (ARS auto-set: ${items[0].ars})`
              )
            : tr('Keine Treffer', 'No matches')
        );
      } else {
        const data = await res.json();
        setNinaRegionStatus(tr('Fehler: ', 'Error: ') + (data.error || 'Unknown error'));
      }
    } catch (err) {
      setNinaRegionStatus(tr('Fehler: ', 'Error: ') + err.message);
    }
  };

  const extractNinaWarnings = (payload) => {
    if (!payload) {
      return [];
    }

    if (Array.isArray(payload)) {
      return payload;
    }

    if (typeof payload !== 'object') {
      return [];
    }

    const candidates = [
      payload.warnings,
      payload.alerts,
      payload.items,
      payload.data,
      payload.dashboard
    ];

    for (const entry of candidates) {
      if (Array.isArray(entry)) {
        return entry;
      }
    }

    return [];
  };

  const getNinaWarningTitle = (warning) => {
    if (!warning || typeof warning !== 'object') {
      return tr('Unbekannte Warnung', 'Unknown warning');
    }

    return (
      warning.headline ||
      warning.event ||
      warning.title ||
      warning.name ||
      warning.identifier ||
      warning.id ||
      tr('Warnung', 'Warning')
    );
  };

  const getNinaWarningDescription = (warning) => {
    if (!warning || typeof warning !== 'object') {
      return '';
    }

    return warning.description || warning.instruction || warning.content || warning.type || '';
  };

  const loadNinaWarnings = async () => {
    try {
      setNinaWarningsStatus(tr('Lade Warnungen...', 'Loading warnings...'));
      const arsValue = String(apiConfig?.ars || '').trim();
      const params = new URLSearchParams();
      if (arsValue) {
        params.set('ars', arsValue);
      }

      const query = params.toString();
      const res = await fetch(`${API_BASE}/api/nina/dashboard${query ? `?${query}` : ''}`);
      if (res.ok) {
        const data = await res.json();
        const warnings = extractNinaWarnings(data.data);

        setNinaWarnings(warnings);
        setNinaWarningsArs(data.ars || '');
        setNinaWarningsStatus(
          warnings.length > 0
            ? tr(`✓ ${warnings.length} Warnungen`, `✓ ${warnings.length} warnings`)
            : tr('Keine Warnungen', 'No warnings')
        );
      } else {
        const data = await res.json();
        setNinaWarningsStatus(tr('Fehler: ', 'Error: ') + (data.error || 'Unknown error'));
      }
    } catch (err) {
      setNinaWarningsStatus(tr('Fehler: ', 'Error: ') + err.message);
    }
  };

  const resolveLocation = async () => {
    if (!navigator.geolocation) {
      setLocationStatus(tr('Geolocation wird nicht unterstuetzt', 'Geolocation not supported'));
      return;
    }

    setLocationStatus(tr('Standort wird ermittelt...', 'Resolving location...'));
    navigator.geolocation.getCurrentPosition(async (position) => {
      try {
        const res = await fetch(`${API_BASE}/api/location/resolve`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            lat: position.coords.latitude,
            lon: position.coords.longitude,
            save: true
          })
        });

        const data = await res.json();
        if (res.ok && data.success) {
          setLocationResult(data);
          if (data.nina && data.nina.ars) {
            setApiConfig(prev => ({ ...prev, ars: data.nina.ars }));
          }
          if (data.openweather_error) {
            setLocationStatus(
              tr(
                '✓ Standort für NINA übernommen (OpenWeather konnte nicht automatisch gesetzt werden)',
                '✓ Location applied for NINA (OpenWeather could not be auto-configured)'
              )
            );
          } else {
            setLocationStatus(tr('✓ Standort übernommen', '✓ Location applied'));
          }
        } else {
          setLocationStatus(tr('Fehler: ', 'Error: ') + (data.error || 'Unknown error'));
        }
      } catch (err) {
        setLocationStatus(tr('Fehler: ', 'Error: ') + err.message);
      }
    }, (error) => {
      setLocationStatus(tr('Fehler: ', 'Error: ') + error.message);
    }, {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 60000
    });
  };

  const saveApiConfig = async (apiName) => {
    try {
      setApiConfigStatus(tr('Speichern...', 'Saving...'));
      const configToSave = apiName === 'email' ? normalizeEmailConfig(apiConfig) : apiConfig;

      const res = await fetch(`${API_BASE}/api/registry/${apiName}/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: configToSave })
      });

      if (res.ok) {
        setApiConfigStatus(tr('✓ Gespeichert und Verbindung erfolgreich getestet', '✓ Saved and connection tested successfully'));
        if (apiName === 'email') {
          setApiConfig(configToSave);
        }
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
      const configToTest = apiName === 'email' ? normalizeEmailConfig(apiConfig) : apiConfig;

      const res = await fetch(`${API_BASE}/api/registry/${apiName}/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: configToTest })
      });

      if (res.ok) {
        const data = await res.json();
        if (data.health.status === 'healthy') {
          setApiConfigStatus(tr('✓ Verbindung erfolgreich', '✓ Connection successful'));
        } else {
          const errorMessage = data?.health?.error || tr('Unbekannter Fehler', 'Unknown error');
          setApiConfigStatus(tr('Verbindung fehlgeschlagen: ', 'Connection failed: ') + errorMessage);
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
                    Dieser Name wird für die persönliche Begrüßung auf der Startseite genutzt.
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
                  <div className="section-title">{tr('Integrationen', 'Integrations')}</div>
                  <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0 1.25rem 0'}}>
                    {tr('Konfiguriere verbundene Dienste für erweiterte Funktionen', 'Configure connected services for extended functionality')}
                  </p>

                  <div className="api-overview-bar">
                    <div className="api-overview-chip">
                      <span>{tr('Gesamt', 'Total')}</span>
                      <strong>{apis.length}</strong>
                    </div>
                    <div className="api-overview-chip">
                      <span>{tr('Konfiguriert', 'Configured')}</span>
                      <strong>{configuredApiCount}</strong>
                    </div>
                    <div className="api-overview-chip">
                      <span>{tr('Erreichbar', 'Reachable')}</span>
                      <strong>{healthyApiCount}</strong>
                    </div>
                    <div className="api-search-box">
                      <i className="fas fa-search" aria-hidden="true"></i>
                      <input
                        type="text"
                        value={apiQuery}
                        onChange={(e) => setApiQuery(e.target.value)}
                        placeholder={tr('Integration suchen...', 'Search integration...')}
                      />
                    </div>
                  </div>

                  <div className="api-workspace">
                    <div className="api-catalog">
                      {visibleApis.length === 0 && (
                        <div className="api-empty-state">{tr('Keine Integration gefunden', 'No integrations found')}</div>
                      )}

                      {visibleApis.map((api) => {
                        const health = apiHealth[api.api_name] || {};
                        const isHealthy = health.status === 'healthy';
                        const isConfigured = api.configured;
                        const isSelected = selectedApi?.api_name === api.api_name;
                        const statusVariant = !isConfigured ? 'neutral' : (isHealthy ? 'healthy' : 'unhealthy');
                        const statusLabel = !isConfigured
                          ? tr('Nicht konfiguriert', 'Not configured')
                          : (isHealthy
                            ? tr('Verbunden', 'Connected')
                            : tr('Nicht erreichbar', 'Not reachable'));

                        return (
                          <button
                            key={api.api_name}
                            type="button"
                            className={`api-item-card ${isSelected ? 'selected' : ''}`}
                            onClick={() => {
                              if (api.isImmichSpecial) {
                                setSelectedApi({ api_name: 'immich', configured: immichConfigured, isImmichSpecial: true, schema: {} });
                                setApiConfig({});
                              } else {
                                loadApiConfig(api.api_name);
                              }
                              setApiConfigStatus('');
                            }}
                          >
                            <div className="api-item-top">
                              <div className="api-item-title">{getApiDisplayName(api.api_name)}</div>
                              <div className={`api-item-pill ${statusVariant}`}>
                                {statusLabel}
                              </div>
                            </div>
                            <div className="api-item-bottom">
                              <span className="api-key-label">{api.api_name}</span>
                              {health.response_time && (
                                <span className="api-response-time">{Math.round(health.response_time * 1000)}ms</span>
                              )}
                            </div>
                          </button>
                        );
                      })}
                    </div>

                    <div className="api-editor">
                      {!selectedApi && (
                        <div className="api-empty-state large">
                          {tr('Waehle links eine Integration aus, um die Konfiguration zu bearbeiten.', 'Select an integration from the left to edit its configuration.')}
                        </div>
                      )}

                      {selectedApi && (
                        <div className="api-editor-card">
                          <div className="api-editor-header">
                            <div>
                              <div className="section-title" style={{margin: 0}}>
                                {getApiDisplayName(selectedApi.api_name)}
                              </div>
                              <div style={{fontSize: '0.85rem', color: 'var(--muted)', marginTop: '0.25rem'}}>
                                {selectedApi.configured ? tr('✓ Konfiguriert', '✓ Configured') : tr('Nicht konfiguriert', 'Not configured')}
                              </div>
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

                          {(selectedApi.api_name === 'nina' || selectedApi.api_name === 'openweather') && (
                            <div className="api-editor-subsection">
                              <div style={{fontSize: '0.9rem', fontWeight: '600', marginBottom: '1rem'}}>
                                {tr('Standort-Einstellungen', 'Location Settings')}
                              </div>
                              <div style={{marginBottom: '1rem'}}>
                                <div style={{fontWeight: '600', marginBottom: '0.5rem'}}>
                                  {tr('Standort automatisch übernehmen', 'Auto-detect location')}
                                </div>
                                <div className="button-group">
                                  <button className="btn" onClick={resolveLocation}>
                                    {tr('Standort ermitteln', 'Detect location')}
                                  </button>
                                </div>
                                {locationStatus && (
                                  <div className="status-text" style={{marginTop: '0.5rem'}}>{locationStatus}</div>
                                )}
                                {locationResult && (
                                  <div style={{marginTop: '0.5rem', fontSize: '0.85rem', color: 'var(--muted)'}}>
                                    {locationResult.location?.display_name && (
                                      <div>{tr('Standort', 'Location')}: {locationResult.location.display_name}</div>
                                    )}
                                    {locationResult.nina?.ars && (
                                      <div>{tr('NINA ARS', 'NINA ARS')}: {locationResult.nina.ars} {locationResult.nina.name ? `(${locationResult.nina.name})` : ''}</div>
                                    )}
                                    {locationResult.openweather?.lat && locationResult.openweather?.lon && (
                                      <div>
                                        {tr('OpenWeather Koordinaten', 'OpenWeather coordinates')}: {locationResult.openweather.lat}, {locationResult.openweather.lon}
                                        {locationResult.openweather.location_name ? ` (${locationResult.openweather.location_name})` : ''}
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>

                              {selectedApi.api_name === 'nina' && (
                                <>
                                  <div style={{fontWeight: '600', marginBottom: '0.5rem'}}>
                                    {tr('Regionalschlüssel (ARS) suchen', 'Search regional keys (ARS)')}
                                  </div>
                                  <div className="input-group">
                                    <label>{tr('Suche nach Ort oder ARS', 'Search by place or ARS')}</label>
                                    <input
                                      type="text"
                                      value={ninaRegionQuery}
                                      onChange={(e) => setNinaRegionQuery(e.target.value)}
                                      placeholder={tr('z.B. Berlin oder 110000000000', 'e.g. Berlin or 110000000000')}
                                    />
                                  </div>
                                  <div className="button-group" style={{marginTop: '0.5rem'}}>
                                    <button className="btn" onClick={loadNinaRegions}>
                                      {tr('Regionen laden', 'Load regions')}
                                    </button>
                                  </div>
                                  {ninaRegionStatus && (
                                    <div className="status-text" style={{marginTop: '0.5rem'}}>{ninaRegionStatus}</div>
                                  )}
                                  {ninaRegions.length > 0 && (
                                    <div className="input-group" style={{marginTop: '0.75rem'}}>
                                      <label>{tr('Treffer', 'Matches')}</label>
                                      <select
                                        value=""
                                        onChange={(e) => {
                                          const ars = e.target.value;
                                          if (ars) {
                                            setApiConfig(prev => ({ ...prev, ars }));
                                          }
                                        }}
                                      >
                                        <option value="">{tr('Auswählen...', 'Select...')}</option>
                                        {ninaRegions.map((entry) => (
                                          <option key={`${entry.ars}-${entry.name}`} value={entry.ars}>
                                            {entry.ars} - {entry.name}{entry.hint ? ` (${entry.hint})` : ''}
                                          </option>
                                        ))}
                                      </select>
                                    </div>
                                  )}
                                  <div style={{marginTop: '1rem'}}>
                                    <div style={{fontWeight: '600', marginBottom: '0.5rem'}}>
                                      {tr('Warnungen für konfigurierten ARS', 'Warnings for configured ARS')}
                                    </div>
                                    <div className="button-group">
                                      <button className="btn" onClick={loadNinaWarnings}>
                                        {tr('Warnungen laden', 'Load warnings')}
                                      </button>
                                    </div>
                                    {ninaWarningsStatus && (
                                      <div className="status-text" style={{marginTop: '0.5rem'}}>
                                        {ninaWarningsStatus}
                                      </div>
                                    )}
                                    {ninaWarningsArs && (
                                      <div style={{fontSize: '0.85rem', color: 'var(--muted)', marginTop: '0.25rem'}}>
                                        {tr('ARS', 'ARS')}: {ninaWarningsArs}
                                      </div>
                                    )}
                                    {ninaWarnings.length > 0 && (
                                      <div className="api-warning-list">
                                        {ninaWarnings.slice(0, 10).map((warning, index) => (
                                          <div
                                            key={`${warning.identifier || warning.id || index}`}
                                            className="api-warning-item"
                                          >
                                            <div style={{fontWeight: '600'}}>{getNinaWarningTitle(warning)}</div>
                                            {getNinaWarningDescription(warning) && (
                                              <div style={{fontSize: '0.85rem', color: 'var(--muted)', marginTop: '0.35rem'}}>
                                                {getNinaWarningDescription(warning)}
                                              </div>
                                            )}
                                          </div>
                                        ))}
                                      </div>
                                    )}
                                  </div>
                                </>
                              )}
                            </div>
                          )}

                          {selectedApi.api_name === 'immich' && (
                            <div style={{marginBottom: '1.5rem'}}>
                              <div style={{fontSize: '0.9rem', color: 'var(--muted)', marginBottom: '0.9rem'}}>
                                {tr('Globale Immich-Standards für die Fotosuche konfigurieren.', 'Configure global Immich defaults for photo search.')}
                              </div>
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
                            </div>
                          )}

                          {selectedApi.api_name === 'email' && (
                            <div style={{marginBottom: '1.5rem'}}>
                              <div style={{fontSize: '0.9rem', color: 'var(--muted)', marginBottom: '0.9rem'}}>
                                {tr('E-Mail einfacher einrichten: Vorlage wählen, Kontodaten ergänzen und Ordner automatisch laden.', 'Set up email more easily: choose a preset, fill in account details, and load folders automatically.')}
                              </div>

                              <div className="input-group">
                                <label>{tr('E-Mail-Konto', 'Email account')}</label>
                                <div style={{display: 'flex', gap: '0.5rem', alignItems: 'center'}}>
                                  <select
                                    value={activeEmailAccountId}
                                    onChange={(e) => {
                                      const nextId = e.target.value;
                                      setActiveEmailAccount(nextId);
                                      const nextConfig = normalizeEmailConfig({ ...apiConfig, active_account_id: nextId, selected_account_id: nextId });
                                      loadEmailFolders(nextConfig);
                                    }}
                                    style={{flex: 1}}
                                  >
                                    {emailAccounts.map((account) => (
                                      <option key={account.account_id} value={account.account_id}>
                                        {account.display_name || account.username || account.account_id}
                                      </option>
                                    ))}
                                  </select>
                                  <button className="btn" type="button" onClick={addEmailAccount}>
                                    {tr('Konto hinzufügen', 'Add account')}
                                  </button>
                                  <button className="btn" type="button" onClick={removeEmailAccount} disabled={emailAccounts.length <= 1}>
                                    {tr('Konto entfernen', 'Remove account')}
                                  </button>
                                </div>
                              </div>

                              <div className="input-group">
                                <label>{tr('Kontoname', 'Account name')}</label>
                                <input
                                  type="text"
                                  value={activeEmailAccount.display_name || ''}
                                  onChange={(e) => updateActiveEmailAccount({ display_name: e.target.value })}
                                  placeholder={tr('z.B. WEB.DE privat', 'e.g. WEB.DE private')}
                                />
                              </div>

                              <div className="input-group">
                                <label>{tr('Provider-Vorlage', 'Provider preset')}</label>
                                <select
                                  value={emailPresetKey}
                                  onChange={(e) => applyEmailPreset(e.target.value)}
                                >
                                  {Object.entries(EMAIL_PROVIDER_PRESETS).map(([key, preset]) => (
                                    <option key={key} value={key}>
                                      {language === 'de' ? preset.labelDe : preset.labelEn}
                                    </option>
                                  ))}
                                </select>
                              </div>

                              <div className="input-group">
                                <label>{tr('E-Mail-Adresse / Benutzername', 'Email address / username')}</label>
                                <input
                                  type="text"
                                  value={activeEmailAccount.username || ''}
                                  onChange={(e) => updateActiveEmailAccount({ username: e.target.value })}
                                  placeholder={tr('dein.name@anbieter.de', 'your.name@provider.com')}
                                />
                              </div>

                              <div className="input-group">
                                <label>{tr('Passwort / App-Passwort', 'Password / app password')}</label>
                                <input
                                  type="password"
                                  value={activeEmailAccount.password || ''}
                                  onChange={(e) => updateActiveEmailAccount({ password: e.target.value })}
                                  placeholder="••••••••"
                                />
                              </div>

                              <div className="input-group">
                                <label>IMAP Host</label>
                                <input
                                  type="text"
                                  value={activeEmailAccount.imap_host || ''}
                                  onChange={(e) => updateActiveEmailAccount({ imap_host: e.target.value })}
                                  placeholder="imap.web.de"
                                />
                              </div>

                              <div className="input-group">
                                <label>IMAP Port</label>
                                <input
                                  type="number"
                                  value={activeEmailAccount.imap_port || ''}
                                  onChange={(e) => updateActiveEmailAccount({ imap_port: e.target.value })}
                                  placeholder="993"
                                />
                              </div>

                              <div className="input-group">
                                <label>SMTP Host</label>
                                <input
                                  type="text"
                                  value={activeEmailAccount.smtp_host || ''}
                                  onChange={(e) => updateActiveEmailAccount({ smtp_host: e.target.value })}
                                  placeholder="smtp.web.de"
                                />
                              </div>

                              <div className="input-group">
                                <label>SMTP Port</label>
                                <input
                                  type="number"
                                  value={activeEmailAccount.smtp_port || ''}
                                  onChange={(e) => updateActiveEmailAccount({ smtp_port: e.target.value })}
                                  placeholder="587"
                                />
                              </div>

                              <div className="input-group">
                                <label>{tr('SMTP STARTTLS', 'SMTP STARTTLS')}</label>
                                <select
                                  value={activeEmailAccount.smtp_starttls ?? 'true'}
                                  onChange={(e) => updateActiveEmailAccount({ smtp_starttls: e.target.value })}
                                >
                                  <option value="true">{tr('Ja', 'Yes')}</option>
                                  <option value="false">{tr('Nein', 'No')}</option>
                                </select>
                              </div>

                              <div className="input-group">
                                <label>{tr('SMTP SSL', 'SMTP SSL')}</label>
                                <select
                                  value={activeEmailAccount.smtp_use_ssl ?? 'false'}
                                  onChange={(e) => updateActiveEmailAccount({ smtp_use_ssl: e.target.value })}
                                >
                                  <option value="true">{tr('Ja', 'Yes')}</option>
                                  <option value="false">{tr('Nein', 'No')}</option>
                                </select>
                              </div>

                              <div className="input-group">
                                <label>{tr('Ordner synchronisieren', 'Folders to sync')}</label>
                                <div style={{display: 'flex', flexDirection: 'column', gap: '0.6rem'}}>
                                  <label style={{display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.95rem'}}>
                                    <input
                                      type="checkbox"
                                      checked={emailFoldersAreAll}
                                      onChange={(e) => updateActiveEmailAccount({ folders: e.target.checked ? 'ALL' : (emailSelectedFolders[0] || 'INBOX') })}
                                    />
                                    {tr('Alle Ordner automatisch verwenden', 'Use all folders automatically')}
                                  </label>
                                  {!emailFoldersAreAll && emailFolderOptions.length > 0 && (
                                    <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.5rem', maxHeight: '220px', overflowY: 'auto', padding: '0.5rem', border: '1px solid var(--line)', borderRadius: '8px'}}>
                                      {emailFolderOptions.map((folder) => {
                                        const checked = emailSelectedFolders.includes(folder);
                                        return (
                                          <label key={folder} style={{display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9rem'}}>
                                            <input
                                              type="checkbox"
                                              checked={checked}
                                              onChange={(e) => {
                                                const nextFolders = checked
                                                  ? emailSelectedFolders.filter((value) => value !== folder)
                                                  : [...emailSelectedFolders, folder];
                                                updateEmailFolders(nextFolders);
                                              }}
                                            />
                                            <span>{folder}</span>
                                          </label>
                                        );
                                      })}
                                    </div>
                                  )}
                                  {!emailFoldersAreAll && emailFolderOptions.length === 0 && (
                                    <div style={{fontSize: '0.85rem', color: 'var(--muted)'}}>
                                      {tr('Noch keine Ordner geladen. Nutze den Button unten, um die Liste zu laden.', 'No folders loaded yet. Use the button below to fetch the list.')}
                                    </div>
                                  )}
                                </div>
                              </div>

                              <div className="input-group">
                                <label>{tr('Maximale Mails pro Ordner', 'Max emails per folder')}</label>
                                <input
                                  type="number"
                                  value={activeEmailAccount.max_emails || ''}
                                  onChange={(e) => updateActiveEmailAccount({ max_emails: e.target.value })}
                                  placeholder="50"
                                />
                              </div>

                              <div className="input-group">
                                <label>{tr('IMAP SSL', 'IMAP SSL')}</label>
                                <select
                                  value={activeEmailAccount.use_ssl ?? 'true'}
                                  onChange={(e) => updateActiveEmailAccount({ use_ssl: e.target.value })}
                                >
                                  <option value="true">{tr('Ja', 'Yes')}</option>
                                  <option value="false">{tr('Nein', 'No')}</option>
                                </select>
                              </div>

                              <div className="button-group" style={{marginTop: '0.5rem'}}>
                                <button className="btn" onClick={() => loadEmailFolders(normalizeEmailConfig(apiConfig))}>
                                  {tr('Ordner neu laden', 'Reload folders')}
                                </button>
                              </div>

                              {emailFolderStatus && <div className="status-text" style={{marginTop: '0.5rem'}}>{emailFolderStatus}</div>}
                            </div>
                          )}

                          {selectedApi.api_name !== 'immich' && selectedApi.api_name !== 'email' && selectedApi.schema && Object.keys(selectedApi.schema).length > 0 && (
                            <div style={{marginBottom: '1.5rem'}}>
                              <div style={{fontSize: '0.9rem', fontWeight: '600', marginBottom: '1rem'}}>
                                {tr('Authentifizierung & Einstellungen', 'Authentication & Settings')}
                              </div>
                              {Object.entries(selectedApi.schema).map(([key, fieldSchema]) => (
                                <div key={key} className="input-group">
                                  <label>
                                    {fieldSchema.description || key}
                                    {fieldSchema.required && <span style={{color: '#ef4444'}}>*</span>}
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
                            </div>
                          )}

                          {selectedApi.api_name === 'immich' ? (
                            <>
                              <div className="button-group" style={{marginTop: '1.5rem', paddingTop: '1rem', borderTop: '1px solid var(--line)'}}>
                                <button className="btn primary" onClick={saveImmichConfig}>{tr('Speichern', 'Save')}</button>
                                <button className="btn" onClick={testImmichConnection}>{tr('Verbindung testen', 'Test Connection')}</button>
                              </div>
                              {immichStatus && <div className="status-text" style={{marginTop: '1rem'}}>{immichStatus}</div>}
                            </>
                          ) : (
                            <>
                              <div className="button-group" style={{marginTop: '1.5rem', paddingTop: '1rem', borderTop: '1px solid var(--line)'}}>
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
                                {selectedApi.api_name === 'homeassistant' && (
                                  <button
                                    className="btn"
                                    onClick={() => {
                                      const url = apiConfig.url || 'https://my.home-assistant.io/redirect/profile/';
                                      window.open(url, '_blank', 'noopener,noreferrer');
                                    }}
                                  >
                                    {tr('Home Assistant öffnen', 'Open Home Assistant')}
                                  </button>
                                )}
                                {selectedApi.configured && (
                                  <button
                                    className="btn"
                                    onClick={() => {
                                      if (confirm(tr('Möchtest du diese API-Konfiguration wirklich löschen?', 'Do you really want to delete this API configuration?'))) {
                                        deleteApiConfig(selectedApi.api_name);
                                      }
                                    }}
                                    style={{background: '#ef4444', color: 'white'}}
                                  >
                                    {tr('Löschen', 'Delete')}
                                  </button>
                                )}
                              </div>
                              {apiConfigStatus && <div className="status-text" style={{marginTop: '1rem'}}>{apiConfigStatus}</div>}
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}
            {activeTab === 'indexing' && (
              <div className="settings-panel">
                <div className="panel-section">
                  <div className="section-title">{tr('Nextcloud-Login', 'Nextcloud Login')}</div>
                  <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
                    {tr('Verbinde deine Nextcloud-Instanz für die Dokumenten-Indexierung', 'Connect to your Nextcloud instance for document indexing')}
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
                          {nextcloudLoggingIn ? tr('Warte auf Bestätigung...', 'Waiting for confirmation...') : tr('Mit Nextcloud anmelden', 'Login with Nextcloud')}
                        </button>
                      </div>
                      {nextcloudStatus && <div className="status-text">{nextcloudStatus}</div>}
                    </>
                  )}
                </div>
                
                <div className="panel-section" style={{marginTop: '2rem'}}>
                  <div className="section-title">{tr('Dokumenten-Indexierung', 'Document Indexing')}</div>
                  <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
                    {tr('Indexiere deine Dokumente für die semantische Suche mit detaillierter Fortschrittsanzeige', 'Index your documents for semantic search with detailed progress tracking')}
                  </p>
                  
                  <div className="input-group">
                    <label>{tr('Indexierungs-Pfad (optional)', 'Indexing Path (optional)')}</label>
                    <input
                      type="text"
                      value={indexingPath}
                      onChange={(e) => setIndexingPath(e.target.value)}
                      placeholder={tr('z.B. /Documents', 'e.g. /Documents')}
                    />
                    <small style={{color: 'var(--muted)', display: 'block', marginTop: '0.25rem'}}>
                      {tr('Spezifischer Pfad im Nextcloud, der indexiert werden soll. Leer lassen für alle Dateien.', 'Specific path in Nextcloud to index. Leave empty to index all files.')}
                    </small>
                  </div>

                  <div className="button-group">
                    <button className="btn primary" onClick={saveIndexingConfig}>
                      {tr('Pfad speichern', 'Save Path')}
                    </button>
                  </div>
                  {indexingPathStatus && <div className="status-text">{indexingPathStatus}</div>}

                  <div className="button-group" style={{marginTop: '1.5rem'}}>
                    <button className="btn primary" onClick={startIndexing} disabled={indexingStatus === 'running'}>
                      {indexingStatus === 'running' ? tr('Indexierung läuft...', 'Indexing...') : tr('Indexierung starten', 'Start Indexing')}
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
                  currentMotionStyle={motionStyle}
                  onMotionStyleChange={setMotionStyle}
                  showContrastColor={false}
                  labels={{
                    theme: t('theme'),
                    darkMode: t('darkMode'),
                    motionStyle: t('motionStyle'),
                    reset: 'Reset',
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
                    },
                    motion: {
                      calm: t('motionCalm'),
                      dynamic: t('motionDynamic'),
                      aurora: t('motionAurora')
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
