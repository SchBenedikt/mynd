'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useTheme } from '../../hooks/useTheme';
import { useLanguage } from '../../hooks/useLanguage';
import { ThemeSelector } from '../../components/ThemeSelector';
import { EMAIL_PROVIDER_PRESETS, normalizeEmailConfig } from '../../data/emailConfig';

const API_BASE = '';
const SIDEBAR_COLLAPSED_KEY = 'mynd_sidebar_collapsed_v1';
const DISPLAY_NAME_STORAGE_KEY = 'mynd_display_name';
const TTS_PROVIDER_STORAGE_KEY = 'mynd_tts_provider_v1';
const API_DISPLAY_NAMES = {
  gemini_tts: 'Gemini TTS',
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

const normalizeTtsProvider = (value) => {
  return String(value || '').trim().toLowerCase() === 'gemini' ? 'gemini' : 'browser';
};

const formatVoiceLabel = (voice) => {
  const name = String(voice?.name || '').trim();
  const lang = String(voice?.lang || '').trim();
  if (name && lang) return `${name} (${lang})`;
  return name || lang || 'System Voice';
};

const bytesToHex = (bytes) => Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');

const shellQuote = (value, fallback = '') => {
  const resolved = String(value || fallback);
  return `"${resolved.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
};

const shellArg = (value, fallback = '') => {
  const resolved = String(value || fallback).trim();
  return resolved || fallback;
};

const buildTalkWebhookRequest = async ({ roomId, botId, secret, language }) => {
  const normalizedRoomId = String(roomId || 'mychannel').trim() || 'mychannel';
  const normalizedBotId = String(botId || 'Mynd Bot').trim() || 'Mynd Bot';
  const payload = {
    room_id: normalizedRoomId,
    message: 'Testnachricht von Mynd',
    username: normalizedBotId,
    language: String(language || 'de').trim() || 'de'
  };
  const body = JSON.stringify(payload);
  const endpoint = '/api/nextcloud/talk/webhook';
  const terminalEndpoint = 'http://127.0.0.1:5001/api/nextcloud/talk/webhook';
  const headers = { 'Content-Type': 'application/json' };
  const commandLines = [
    "curl -sS -X POST '" + terminalEndpoint + "' \\",
    "  -H 'Content-Type: application/json'"
  ];

  if (secret) {
    const randomHeader = Array.from(window.crypto.getRandomValues(new Uint8Array(8)), (byte) => byte.toString(16).padStart(2, '0')).join('');
    const encoder = new TextEncoder();
    const key = await window.crypto.subtle.importKey('raw', encoder.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
    const signature = await window.crypto.subtle.sign('HMAC', key, encoder.encode(randomHeader + body));
    const signatureHex = bytesToHex(new Uint8Array(signature));

    headers['X-Nextcloud-Talk-Random'] = randomHeader;
    headers['X-Nextcloud-Talk-Signature'] = `sha256=${signatureHex}`;
    commandLines.push("  -H 'X-Nextcloud-Talk-Random: " + randomHeader + "' \\");
    commandLines.push(`  -H 'X-Nextcloud-Talk-Signature: sha256=${signatureHex}'`);
  }

  commandLines.push(`  --data-binary @- <<'JSON'`);
  commandLines.push(body);
  commandLines.push('JSON');

  return {
    payload,
    body,
    endpoint,
    headers,
    command: commandLines.join('\n'),
    hasSecret: Boolean(secret)
  };
};

const buildTalkBotSetupInstructions = ({ webhookUrl, botName, botSecret, roomToken, ncUrl }) => {
  const normUrl = String(webhookUrl || 'https://mynd.example.com/api/nextcloud/talk/webhook').trim().replace(/\/$/, '');
  const botN = String(botName || 'Mynd Bot').trim() || 'Mynd Bot';
  const botSec = String(botSecret || 'openssl_random_secret').trim();
  const roomT = String(roomToken || 'mychannel').trim() || 'mychannel';
  
  return {
    steps: [
      {
        step: 1,
        title: 'Webhook-URL von Mynd',
        desc: 'Die URL muss externe Requests von Nextcloud akzeptieren:',
        value: normUrl,
        action: 'copy'
      },
      {
        step: 2,
        title: 'Bot-Secret generieren (oder verwenden)',
        desc: 'Mind. 32 Zeichen, z.B. mit: openssl rand -hex 24',
        value: botSec,
        action: 'copy'
      },
      {
        step: 3,
        title: 'Bot auf Nextcloud-Server installieren (ssh)',
        desc: 'Admin-Rechte erforderlich. Ersetze <URL>, <SECRET>, <ROOM_TOKEN>:',
        command: `sudo -u www-data php /var/www/nextcloud/occ talk:bot:install --feature webhook,response --no-setup "${botN}" "${botSec}" "${normUrl}"`,
        note: 'Kopiere die Bot-ID (SHA1) aus der Ausgabe'
      },
      {
        step: 4,
        title: 'Bot-Liste abrufen',
        command: `sudo -u www-data php /var/www/nextcloud/occ talk:bot:list`,
        desc: 'Suche nach "Mynd Bot" — die erste Spalte ist die BOT_ID'
      },
      {
        step: 5,
        title: 'Bot zum Raum hinzufügen',
        desc: 'Ersetze <BOT_ID> mit dem Wert aus Schritt 4 und <ROOM_TOKEN> mit dem Raum-Token:',
        command: `sudo -u www-data php /var/www/nextcloud/occ talk:bot:setup <BOT_ID> ${roomT}`,
        example: `sudo -u www-data php /var/www/nextcloud/occ talk:bot:setup bot-abc123def456 ${roomT}`
      },
      {
        step: 6,
        title: 'Webhook testen',
        desc: 'In Mynd Settings: Klick "Talk Webhook testen"',
        action: 'test'
      }
    ]
  };
};

const buildTalkBotCommands = ({ webhookUrl, botName, botSecret, botId, roomToken }) => {
  const instructions = buildTalkBotSetupInstructions({ webhookUrl, botName, botSecret, roomToken });
  const normalizedBotId = String(botId || '').trim() || '<BOT_ID>';

  return instructions.steps
    .map((step) => {
      const header = `# ${step.step}. ${step.title}`;

      if (step.command) {
        return `${header}\n${step.command.replace('<BOT_ID>', normalizedBotId)}`;
      }

      if (step.example) {
        return `${header}\n${step.desc}\nBeispiel: ${step.example.replace('<BOT_ID>', normalizedBotId)}`;
      }

      return `${header}\n${step.desc}${step.value ? `\n${step.value}` : ''}`;
    })
    .join('\n\n');
};

const getEffectiveTalkSecret = (botSecret, webhookSecret) => {
  return String(webhookSecret || '').trim() || String(botSecret || '').trim();
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
  
  const [aiProtocol, setAiProtocol] = useState('http');
  const [aiHost, setAiHost] = useState('127.0.0.1');
  const [aiPort, setAiPort] = useState('11434');
  const [aiModel, setAiModel] = useState('');
  const [aiModels, setAiModels] = useState([]);
  const [aiStatus, setAiStatus] = useState('');
  const [immichUrlDefault, setImmichUrlDefault] = useState('');
  const [immichApiKeyDefault, setImmichApiKeyDefault] = useState('');
  const [immichStatus, setImmichStatus] = useState('');
  const [briefingDailyEnabled, setBriefingDailyEnabled] = useState(true);
  const [briefingWeeklyEnabled, setBriefingWeeklyEnabled] = useState(true);
  const [briefingMorningHour, setBriefingMorningHour] = useState(7);
  const [briefingStatus, setBriefingStatus] = useState('');
  // Email send settings for proactive briefings
  const [briefingSendDaily, setBriefingSendDaily] = useState(false);
  const [briefingSendWeekly, setBriefingSendWeekly] = useState(false);
  const [briefingSendRecipients, setBriefingSendRecipients] = useState('');
  const [briefingSendAccountId, setBriefingSendAccountId] = useState('');
  const [briefingEmailAccounts, setBriefingEmailAccounts] = useState([]);
  const [briefingBotId, setBriefingBotId] = useState('');
  const [briefingTalkWebhookUrl, setBriefingTalkWebhookUrl] = useState('');
  const [briefingTalkServerBotId, setBriefingTalkServerBotId] = useState('');
  const [briefingBotSecretLocal, setBriefingBotSecretLocal] = useState('');
  const [briefingSendTalk, setBriefingSendTalk] = useState(false);
  const [briefingTalkRoomId, setBriefingTalkRoomId] = useState('');
  const [briefingTalkWebhookSecret, setBriefingTalkWebhookSecret] = useState('');
  const [briefingTalkWebhookSecretSet, setBriefingTalkWebhookSecretSet] = useState(false);
  const [briefingTalkBotSetupPreview, setBriefingTalkBotSetupPreview] = useState('');
  const [briefingTalkBotSetupStatus, setBriefingTalkBotSetupStatus] = useState('');
  
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
  const [persistentIndexStats, setPersistentIndexStats] = useState({ db_stats: {}, indexing_runs: [] });
  
  const [nextcloudUrl, setNextcloudUrl] = useState('');
  const [showNcBotPanel, setShowNcBotPanel] = useState(false);
  const [nextcloudStatus, setNextcloudStatus] = useState('');
  const [calendarConfig, setCalendarConfig] = useState({
    default_calendar_name: ''
  });
  const [calendarOptions, setCalendarOptions] = useState([]);
  const [calendarConfigStatus, setCalendarConfigStatus] = useState('');
  const [nextcloudConfigured, setNextcloudConfigured] = useState(false);
  const [nextcloudDisplayName, setNextcloudDisplayName] = useState('');
  const [nextcloudLoggingIn, setNextcloudLoggingIn] = useState(false);

  // Email Indexing State
  const [emailConfig, setEmailConfig] = useState({
    imap_host: '',
    imap_port: 993,
    username: '',
    password: '',
    folders: 'INBOX',
    max_emails: 50,
    use_ssl: true
  });
  const [emailConfigStatus, setEmailConfigStatus] = useState('');
  const [emailTestLoading, setEmailTestLoading] = useState(false);
  const [emailIndexingMode, setEmailIndexingMode] = useState('manual');
  const [emailIndexingAccountId, setEmailIndexingAccountId] = useState('');
  const [emailIndexingStatus, setEmailIndexingStatus] = useState('idle');
  const [emailIndexingProgress, setEmailIndexingProgress] = useState(0);
  const [emailIndexingDetails, setEmailIndexingDetails] = useState({
    processed: 0,
    elapsed: 0,
    current_folder: '',
    message: ''
  });

  useEffect(() => {
    if (typeof window !== 'undefined' && !briefingTalkWebhookUrl.trim()) {
      setBriefingTalkWebhookUrl(`${window.location.origin}/api/nextcloud/talk/webhook`);
    }
  }, [briefingTalkWebhookUrl]);

  useEffect(() => {
    if (briefingEmailAccounts.length > 0) {
      setEmailIndexingMode((current) => current === 'manual' && !emailIndexingAccountId ? 'existing' : current);
      if (!emailIndexingAccountId || !briefingEmailAccounts.some((account) => account.account_id === emailIndexingAccountId)) {
        setEmailIndexingAccountId(briefingEmailAccounts[0].account_id);
      }
    } else if (emailIndexingMode === 'existing') {
      setEmailIndexingMode('manual');
      setEmailIndexingAccountId('');
    }
  }, [briefingEmailAccounts, emailIndexingAccountId, emailIndexingMode]);

  useEffect(() => {
    let cancelled = false;

    const updateSetupPreview = () => {
      try {
        const preview = buildTalkBotCommands({
          webhookUrl: briefingTalkWebhookUrl,
          botName: briefingBotId,
          botSecret: getEffectiveTalkSecret(briefingBotSecretLocal, briefingTalkWebhookSecret),
          botId: briefingTalkServerBotId,
          roomToken: briefingTalkRoomId
        });

        if (!cancelled) {
          setBriefingTalkBotSetupPreview(preview);
          if (briefingBotSecretLocal.trim() && briefingBotSecretLocal.trim().length < 40) {
            setBriefingTalkBotSetupStatus(tr('Bot-Secret ist zu kurz (mindestens 40 Zeichen).', 'Bot secret is too short (minimum 40 characters).'));
          } else if (briefingTalkServerBotId.trim()) {
            setBriefingTalkBotSetupStatus(tr('Setup-Befehle sind vollständig.', 'Setup commands are complete.'));
          } else {
            setBriefingTalkBotSetupStatus(tr('Führe zuerst talk:bot:list aus und trage dann die Bot-ID ein.', 'Run talk:bot:list first and then enter the bot ID.'));
          }
        }
      } catch (err) {
        if (!cancelled) {
          setBriefingTalkBotSetupPreview('');
          setBriefingTalkBotSetupStatus(`Error: ${err.message}`);
        }
      }
    };

    updateSetupPreview();

    return () => {
      cancelled = true;
    };
  }, [briefingTalkWebhookUrl, briefingBotId, briefingBotSecretLocal, briefingTalkServerBotId, briefingTalkRoomId, language]);

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
  const geminiTtsConfigured = ttsProvider === 'gemini' || geminiTtsApiKeySet;
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
  const catalogApis = [
    { api_name: 'gemini_tts', configured: geminiTtsConfigured, isGeminiTtsSpecial: true },
    { api_name: 'immich', configured: immichConfigured, isImmichSpecial: true },
    ...apis
  ];
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
  const visibleVoices = language === 'de'
    ? availableVoices.filter((voice) => String(voice.lang || '').toLowerCase().startsWith('de'))
    : availableVoices;
  const geminiVoices = [
    'Achernar', 'Achird', 'Algenib', 'Algieba', 'Alnilam', 'Aoede', 'Autonoe', 'Callirrhoe', 'Charon', 'Despina',
    'Enceladus', 'Erinome', 'Fenrir', 'Gacrux', 'Iapetus', 'Kore', 'Laomedeia', 'Leda', 'Orus', 'Pulcherrima',
    'Puck', 'Rasalgethi', 'Sadachbia', 'Sadaltager', 'Schedar', 'Sulafat', 'Umbriel', 'Vindemiatrix', 'Zephyr', 'Zubenelgenubi'
  ];

  useEffect(() => {
    loadAIConfig();
    loadImmichConfig();
    loadEmailAccounts();
    loadOllamaModels();
    loadNextcloudConfig();
    loadCalendarConfig();
    loadCalendarOptions();
    loadIndexingConfig();
    loadEmailIndexingConfig();
    loadAllApis();
    updateStatus();
    // initial load of persistent indexing stats
    loadIndexingStats();

    const statusInterval = setInterval(() => {
      updateStatus();
      loadApiHealth();
    }, 8000);
    const statsInterval = setInterval(() => {
      loadIndexingStats();
    }, 10000);
    return () => {
      clearInterval(statusInterval);
      clearInterval(statsInterval);
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

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const supportsSynthesis = 'speechSynthesis' in window && typeof window.SpeechSynthesisUtterance !== 'undefined';
    setSpeechSynthesisSupported(supportsSynthesis);

    if (!supportsSynthesis) return;

    const updateVoices = () => {
      const voices = window.speechSynthesis.getVoices();
      const normalized = voices.map((voice) => ({
        voiceURI: voice.voiceURI,
        name: voice.name,
        lang: voice.lang,
        default: voice.default
      }));
      setAvailableVoices(normalized);
    };

    updateVoices();
    window.speechSynthesis.addEventListener('voiceschanged', updateVoices);
    return () => {
      window.speechSynthesis.removeEventListener('voiceschanged', updateVoices);
    };
  }, []);

  useEffect(() => {
    if (!selectedVoiceUri) return;
    const exists = visibleVoices.some((voice) => voice.voiceURI === selectedVoiceUri);
    if (!exists) {
      setSelectedVoiceUri('');
    }
  }, [selectedVoiceUri, visibleVoices]);

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

      const hasServerTtsProvider = Object.prototype.hasOwnProperty.call(config, 'tts_provider');
      const storedTtsProvider = typeof window !== 'undefined'
        ? window.localStorage.getItem(TTS_PROVIDER_STORAGE_KEY)
        : '';
      const resolvedTtsProvider = hasServerTtsProvider
        ? normalizeTtsProvider(config.tts_provider)
        : normalizeTtsProvider(storedTtsProvider);

      setTtsProvider(resolvedTtsProvider);
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(TTS_PROVIDER_STORAGE_KEY, resolvedTtsProvider);
      }

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
        setBriefingDailyEnabled(Boolean(data.config.briefing_daily_enabled ?? true));
        setBriefingWeeklyEnabled(Boolean(data.config.briefing_weekly_enabled ?? true));
        setBriefingMorningHour(Number.isFinite(Number(data.config.briefing_morning_hour)) ? Number(data.config.briefing_morning_hour) : 7);
        setBriefingSendDaily(Boolean(data.config.briefing_send_daily ?? false));
        setBriefingSendWeekly(Boolean(data.config.briefing_send_weekly ?? false));
        setBriefingSendRecipients(String(data.config.briefing_send_recipients || ''));
        setBriefingSendAccountId(String(data.config.briefing_send_account_id || ''));
        // Nextcloud Talk briefing settings
        setBriefingSendTalk(Boolean(data.config.briefing_send_talk ?? false));
        setBriefingTalkRoomId(String(data.config.briefing_talk_room_id || ''));
        setBriefingTalkWebhookSecretSet(Boolean(data.config.briefing_talk_webhook_secret_set));
        // Do not populate webhook secret from server; only show whether it's set
        if (data.config.briefing_talk_webhook_secret_set) {
          setBriefingTalkWebhookSecret('');
          setShowNcBotPanel(true);
        }
        setImmichStatus(tr('Geladen', 'Loaded'));
      } else {
        setImmichStatus(tr('Fehler beim Laden der Immich-Konfiguration', 'Error loading Immich config'));
      }
    } catch (err) {
      setImmichStatus(tr('Fehler beim Laden der Immich-Konfiguration', 'Error loading Immich config'));
    }
  };

  const loadEmailAccounts = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/email/accounts`);
      const data = await res.json();
      if (res.ok && data?.success) {
          const accounts = Array.isArray(data.accounts) ? data.accounts : (data.config?.accounts || []);
          setBriefingEmailAccounts(accounts.map(a => ({ account_id: a.account_id || a.id, display_name: a.display_name || a.username || a.account_id || a.id })));
        if (!briefingSendAccountId && accounts.length > 0) {
          setBriefingSendAccountId(accounts[0].account_id || accounts[0].id);
        }
      }
    } catch (err) {
      // ignore
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

  const saveBriefingConfig = async () => {
    try {
      const safeHour = Math.max(0, Math.min(23, Number(briefingMorningHour) || 7));
      const effectiveTalkSecret = getEffectiveTalkSecret(briefingBotSecretLocal, briefingTalkWebhookSecret);
      const res = await fetch(`${API_BASE}/api/ui/system-config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          briefing_daily_enabled: briefingDailyEnabled,
          briefing_weekly_enabled: briefingWeeklyEnabled,
          briefing_morning_hour: safeHour,
          briefing_send_daily: briefingSendDaily,
          briefing_send_weekly: briefingSendWeekly,
          briefing_send_recipients: briefingSendRecipients,
          briefing_send_account_id: briefingSendAccountId,
          // Nextcloud Talk settings
          briefing_send_talk: briefingSendTalk,
          briefing_talk_room_id: briefingTalkRoomId,
          ...(effectiveTalkSecret ? { briefing_talk_webhook_secret: effectiveTalkSecret } : {})
        })
      });

      const data = await res.json();
      if (res.ok && data?.success) {
        setBriefingMorningHour(safeHour);
        if (briefingTalkWebhookSecret.trim()) {
          setBriefingTalkWebhookSecretSet(true);
        }
        setBriefingStatus(tr('Briefing-Einstellungen gespeichert', 'Briefing settings saved'));
      } else {
        setBriefingStatus(`Error: ${data?.error || tr('Briefing-Einstellungen konnten nicht gespeichert werden', 'Could not save briefing settings')}`);
      }
    } catch (err) {
      setBriefingStatus('Error: ' + err.message);
    }
  };

    const testTalkWebhook = async () => {
      try {
        setBriefingStatus(tr('Teste Talk Webhook...', 'Testing Talk webhook...'));
        
        // Simple test payload - reply: false to skip AI response generation for quick test
        const payload = {
          room_id: briefingTalkRoomId || 'mychannel',
          message: tr('Testnachricht von Mynd', 'Test message from Mynd'),
          language: language || 'de',
          reply: false
        };

        const res = await fetch('/api/nextcloud/talk/webhook', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        const data = await res.json().catch(() => ({}));
        
        if (res.ok) {
          setBriefingStatus(tr('✅ Talk Webhook erfolgreich getestet! Bot ist aktiv.', '✅ Talk webhook test succeeded! Bot is active.'));
        } else if (res.status === 401) {
          setBriefingStatus(tr('❌ Signatur-Fehler: Bot-Secret ist falsch oder nicht gespeichert.', '❌ Signature error: bot secret is wrong or not saved.'));
        } else if (res.status === 404) {
          setBriefingStatus(tr('❌ Endpoint nicht gefunden. Webhook-URL ist nicht erreichbar.', '❌ Endpoint not found. Webhook URL not reachable.'));
        } else if (res.status === 400) {
          setBriefingStatus(tr('❌ Fehler: Fehlende Parameter (room_id oder message). Überprüfe die Eingabefelder.', '❌ Error: Missing parameters (room_id or message).'));
        } else {
          setBriefingStatus(`❌ Error (${res.status}): ${data?.error || res.statusText || 'Unbekannter Fehler'}`);
        }
      } catch (err) {
        setBriefingStatus(tr('❌ Fehler: ', '❌ Error: ') + err.message);
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
      const payload = {
        base_url: baseUrl,
        model: aiModel,
        tts_provider: ttsProvider,
        browser_tts_voice_uri: selectedVoiceUri,
        gemini_tts_model: geminiTtsModel,
        gemini_tts_voice: geminiTtsVoice,
        gemini_tts_language_code: geminiTtsLanguageCode,
        gemini_tts_style_prompt: geminiTtsStylePrompt,
        gemini_tts_audio_encoding: geminiTtsAudioEncoding
      };

      if (geminiTtsApiKey.trim()) {
        payload.gemini_tts_api_key = geminiTtsApiKey.trim();
      }

      const res = await fetch(`${API_BASE}/api/ai/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (res.ok) {
        setAiStatus(tr('Erfolgreich gespeichert', 'Saved successfully'));
        const persistedTtsProvider = normalizeTtsProvider(data?.tts_provider || ttsProvider);
        if (typeof window !== 'undefined') {
          window.localStorage.setItem(TTS_PROVIDER_STORAGE_KEY, persistedTtsProvider);
        }
        setGeminiTtsApiKey('');
        setGeminiTtsApiKeySet(Boolean(data?.gemini_tts_api_key_set || geminiTtsApiKeySet || geminiTtsApiKey.trim()));
        updateStatus();
      } else {
        setAiStatus(`Error: ${data?.error || tr('Fehler beim Speichern', 'Error saving')}`);
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

  const loadEmailIndexingConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/email-indexing/config`);
      if (res.ok) {
        const config = await res.json();
        // Don't display the password for security
        setEmailConfig(prev => ({
          ...prev,
          imap_host: config.imap_host || '',
          imap_port: config.imap_port || 993,
          username: config.username || '',
          folders: config.folders || 'INBOX',
          max_emails: config.max_emails || 50,
          use_ssl: config.use_ssl !== false
          // password stays as-is (empty after load for security)
        }));
      }
    } catch (err) {
      console.error('Error loading email indexing config:', err);
    }
  };

  const buildEmailIndexingPayload = () => {
    const safeFolders = String(emailConfig.folders || 'INBOX').trim() || 'INBOX';
    const safeMaxEmails = Number.isFinite(Number(emailConfig.max_emails)) ? Number(emailConfig.max_emails) : 50;

    if (emailIndexingMode === 'existing' && emailIndexingAccountId) {
      return {
        account_id: emailIndexingAccountId,
        folders: safeFolders,
        max_emails: safeMaxEmails,
        use_ssl: Boolean(emailConfig.use_ssl)
      };
    }

    return {
      email_config: {
        imap_host: String(emailConfig.imap_host || '').trim(),
        imap_port: Number.isFinite(Number(emailConfig.imap_port)) ? Number(emailConfig.imap_port) : 993,
        username: String(emailConfig.username || '').trim(),
        password: String(emailConfig.password || ''),
        folders: safeFolders,
        max_emails: safeMaxEmails,
        use_ssl: Boolean(emailConfig.use_ssl)
      }
    };
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

    const loadIndexingStats = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/indexing/stats`);
        if (res.ok) {
          const data = await res.json();
          setPersistentIndexStats(data || {});
        }
      } catch (err) {
        // ignore transient errors
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

  // ========== Email Indexing Functions ==========
  
  const testEmailConnection = async () => {
    setEmailTestLoading(true);
    try {
      const payload = emailIndexingMode === 'existing' && emailIndexingAccountId
        ? { account_id: emailIndexingAccountId }
        : { config: buildEmailIndexingPayload().email_config };

      const res = await fetch(`${API_BASE}/api/email/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        const data = await res.json();
        setEmailConfigStatus(data?.message || tr('Verbindung erfolgreich.', 'Connection successful.'));
      } else {
        const data = await res.json();
        setEmailConfigStatus(tr('Fehler: ', 'Error: ') + (data.error || 'Unbekannter Fehler'));
      }
    } catch (err) {
      setEmailConfigStatus(tr('Fehler: ', 'Error: ') + err.message);
    } finally {
      setEmailTestLoading(false);
    }
  };

  const saveEmailConfig = async () => {
    try {
      if (emailIndexingMode === 'existing' && emailIndexingAccountId) {
        setEmailConfigStatus(tr('Für bestehende Konten ist kein separates Speichern nötig.', 'No separate save is needed for existing accounts.'));
        return;
      }

      const res = await fetch(`${API_BASE}/api/email-indexing/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(emailConfig)
      });
      if (res.ok) {
        setEmailConfigStatus(tr('E-Mail-Konfiguration erfolgreich gespeichert!', 'Email configuration saved successfully!'));
      } else {
        const data = await res.json();
        setEmailConfigStatus(tr('Fehler beim Speichern: ', 'Error saving: ') + (data.error || 'Unbekannter Fehler'));
      }
    } catch (err) {
      setEmailConfigStatus(tr('Fehler: ', 'Error: ') + err.message);
    }
  };

  const startEmailIndexing = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/email-indexing/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildEmailIndexingPayload())
      });
      
      if (res.ok) {
        setEmailIndexingStatus('running');
        const progressInterval = setInterval(async () => {
          try {
            const res = await fetch(`${API_BASE}/api/email-indexing/progress`);
            if (res.ok) {
              const data = await res.json();
              setEmailIndexingProgress(Math.round(data.progress_percentage || 0));
              setEmailIndexingDetails({
                processed: data.emails_processed || 0,
                elapsed: Math.round(data.elapsed_time || 0),
                current_folder: data.current_folder || '',
                message: data.status_message || ''
              });
              
              if (data.status === 'completed' || data.status === 'error') {
                setEmailIndexingStatus(data.status);
                clearInterval(progressInterval);
              }
            }
          } catch (err) {
            console.error('Error checking email indexing progress:', err);
          }
        }, 1000);
      } else {
        const data = await res.json();
        setEmailIndexingStatus('error');
        setEmailConfigStatus(tr('Fehler: ', 'Error: ') + (data.error || 'Unbekannter Fehler'));
      }
    } catch (err) {
      setEmailIndexingStatus('error');
      setEmailConfigStatus(tr('Fehler: ', 'Error: ') + err.message);
    }
  };

  const stopEmailIndexing = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/email-indexing/stop`, {
        method: 'POST'
      });
      if (res.ok) {
        setEmailIndexingStatus('stopped');
      }
    } catch (err) {
      console.error('Error stopping email indexing:', err);
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
            <button className={`tab-btn ${activeTab === 'talk-bot' ? 'active' : ''}`} onClick={() => setActiveTab('talk-bot')}>{tr('Talk Bot Setup', 'Talk Bot Setup')}</button>
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

                <div className="panel-section" style={{marginTop: '2rem'}}>
                  <div className="section-title">Proaktives Briefing</div>
                  <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
                    {tr('Automatisches Briefing jeden Morgen sowie optional montags zum Wochenstart.', 'Automatic briefing every morning with optional Monday weekly kickoff.')}
                  </p>

                  <div className="input-group">
                    <label>{tr('Tagesbriefing aktiv', 'Daily briefing enabled')}</label>
                    <select
                      value={briefingDailyEnabled ? 'true' : 'false'}
                      onChange={(e) => setBriefingDailyEnabled(e.target.value === 'true')}
                    >
                      <option value="true">{tr('Ja', 'Yes')}</option>
                      <option value="false">{tr('Nein', 'No')}</option>
                    </select>
                  </div>

                  <div className="input-group">
                    <label>{tr('Wochenstart-Briefing (Montag) aktiv', 'Weekly kickoff briefing (Monday) enabled')}</label>
                    <select
                      value={briefingWeeklyEnabled ? 'true' : 'false'}
                      onChange={(e) => setBriefingWeeklyEnabled(e.target.value === 'true')}
                    >
                      <option value="true">{tr('Ja', 'Yes')}</option>
                      <option value="false">{tr('Nein', 'No')}</option>
                    </select>
                  </div>

                  <div className="input-group">
                    <label>{tr('Uhrzeit für Morgenbriefing (0-23)', 'Morning briefing hour (0-23)')}</label>
                    <input
                      type="number"
                      min="0"
                      max="23"
                      value={briefingMorningHour}
                      onChange={(e) => setBriefingMorningHour(e.target.value)}
                    />
                  </div>

                  <div className="input-group">
                    <label>{tr('Briefing per E-Mail senden (täglich)', 'Send briefing via email (daily)')}</label>
                    <select
                      value={briefingSendDaily ? 'true' : 'false'}
                      onChange={(e) => setBriefingSendDaily(e.target.value === 'true')}
                    >
                      <option value="true">{tr('Ja', 'Yes')}</option>
                      <option value="false">{tr('Nein', 'No')}</option>
                    </select>
                  </div>

                  <div className="input-group">
                    <label>{tr('Briefing per E-Mail senden (Montag)', 'Send briefing via email (Monday)')}</label>
                    <select
                      value={briefingSendWeekly ? 'true' : 'false'}
                      onChange={(e) => setBriefingSendWeekly(e.target.value === 'true')}
                    >
                      <option value="true">{tr('Ja', 'Yes')}</option>
                      <option value="false">{tr('Nein', 'No')}</option>
                    </select>
                  </div>

                  <div className="input-group">
                    <label>{tr('Empfänger (Komma-getrennt)', 'Recipients (comma-separated)')}</label>
                    <input
                      type="text"
                      value={briefingSendRecipients}
                      onChange={(e) => setBriefingSendRecipients(e.target.value)}
                      placeholder={tr('z.B. max@beispiel.de,anna@beispiel.de', 'e.g. max@example.com,anna@example.com')}
                    />
                  </div>

                  <div className="input-group">
                    <label>{tr('E‑Mail Konto zum Senden', 'Email account to send from')}</label>
                    <select value={briefingSendAccountId} onChange={(e) => setBriefingSendAccountId(e.target.value)}>
                      <option value="">{tr('Auswählen...', 'Select...')}</option>
                      {briefingEmailAccounts.map((acc) => (
                        <option key={acc.account_id} value={acc.account_id}>{acc.display_name}</option>
                      ))}
                    </select>
                  </div>

                  <div className="input-group">
                    <label>{tr('Briefing per Nextcloud Talk senden (täglich)', 'Send briefing via Nextcloud Talk (daily)')}</label>
                    <select
                      value={briefingSendTalk ? 'true' : 'false'}
                      onChange={(e) => setBriefingSendTalk(e.target.value === 'true')}
                    >
                      <option value="true">{tr('Ja', 'Yes')}</option>
                      <option value="false">{tr('Nein', 'No')}</option>
                    </select>
                    <small style={{color: 'var(--muted)', display: 'block', marginTop: '0.25rem'}}>
                      {tr('Raum-Token wird unter Talk Bot Setup konfiguriert.', 'Room token is configured under Talk Bot Setup.')}
                    </small>
                  </div>

                  <div className="button-group">
                    <button className="btn primary" onClick={saveBriefingConfig}>{tr('Briefing speichern', 'Save briefing')}</button>
                  </div>
                  {briefingStatus && <div className="status-text">{briefingStatus}</div>}
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
                                if (api.isGeminiTtsSpecial) {
                                  setSelectedApi({ api_name: 'gemini_tts', configured: geminiTtsConfigured, isGeminiTtsSpecial: true, schema: {} });
                                  setApiConfig({});
                                } else if (api.isImmichSpecial) {
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

                          {selectedApi.api_name === 'gemini_tts' && (
                            <div style={{marginBottom: '1.5rem'}}>
                              <div className="api-editor-subsection">
                                <div style={{fontSize: '0.9rem', fontWeight: '600', marginBottom: '0.85rem'}}>
                                  {tr('Ausgabe-Anbieter', 'Output Provider')}
                                </div>
                                <div className="input-group">
                                  <label>{tr('TTS-Anbieter', 'TTS Provider')}</label>
                                  <select value={ttsProvider} onChange={(e) => setTtsProvider(e.target.value)}>
                                    <option value="browser">{tr('Browser (lokal)', 'Browser (local)')}</option>
                                    <option value="gemini">Gemini TTS</option>
                                  </select>
                                </div>

                                <div className="input-group">
                                  <label>{tr('Browser-Stimme', 'Browser Voice')}</label>
                                  {speechSynthesisSupported ? (
                                    <>
                                      <select value={selectedVoiceUri} onChange={(e) => setSelectedVoiceUri(e.target.value)}>
                                        <option value="">{tr('Automatische Stimme', 'Automatic voice')}</option>
                                        {visibleVoices.map((voice) => (
                                          <option key={voice.voiceURI} value={voice.voiceURI}>
                                            {formatVoiceLabel(voice)}
                                          </option>
                                        ))}
                                      </select>
                                      {language === 'de' && (
                                        <div className="status-text">{tr('Bei deutscher Sprache werden nur deutsche Stimmen angeboten.', 'Only German voices are shown for German language.')}</div>
                                      )}
                                    </>
                                  ) : (
                                    <div className="status-text">{tr('Sprachausgabe wird von diesem Browser nicht unterstuetzt.', 'Speech synthesis is not supported in this browser.')}</div>
                                  )}
                                </div>
                              </div>

                              <div className="api-editor-subsection">
                                <div style={{fontSize: '0.9rem', fontWeight: '600', marginBottom: '0.85rem'}}>
                                  {tr('Gemini Zugang', 'Gemini Access')}
                                </div>
                                <div className="input-group">
                                  <label>Gemini API Key</label>
                                  <input
                                    type="password"
                                    value={geminiTtsApiKey}
                                    onChange={(e) => setGeminiTtsApiKey(e.target.value)}
                                    placeholder={geminiTtsApiKeySet ? tr('Bereits gesetzt (neu eingeben zum Ueberschreiben)', 'Already set (enter new key to overwrite)') : 'AIza...'}
                                  />
                                  {geminiTtsApiKeySet && !geminiTtsApiKey.trim() && (
                                    <div className="status-text">{tr('API Key ist gesetzt.', 'API key is set.')}</div>
                                  )}
                                </div>

                                <div className="input-group">
                                  <label>{tr('Gemini Modell', 'Gemini Model')}</label>
                                  <select value={geminiTtsModel} onChange={(e) => setGeminiTtsModel(e.target.value)}>
                                    <option value="gemini-2.5-flash-tts">gemini-2.5-flash-tts</option>
                                    <option value="gemini-2.5-pro-tts">gemini-2.5-pro-tts</option>
                                  </select>
                                </div>

                                <div className="input-group">
                                  <label>{tr('Gemini Stimme', 'Gemini Voice')}</label>
                                  <select value={geminiTtsVoice} onChange={(e) => setGeminiTtsVoice(e.target.value)}>
                                    {geminiVoices.map((voiceName) => (
                                      <option key={voiceName} value={voiceName}>{voiceName}</option>
                                    ))}
                                  </select>
                                </div>
                              </div>

                              <div className="api-editor-subsection" style={{marginBottom: '1rem'}}>
                                <div style={{fontSize: '0.9rem', fontWeight: '600', marginBottom: '0.85rem'}}>
                                  {tr('Audio Einstellungen', 'Audio Settings')}
                                </div>
                                <div className="input-group">
                                  <label>{tr('Gemini Sprache (BCP-47)', 'Gemini Language (BCP-47)')}</label>
                                  <input type="text" value={geminiTtsLanguageCode} onChange={(e) => setGeminiTtsLanguageCode(e.target.value)} placeholder="de-DE" />
                                </div>

                                <div className="input-group">
                                  <label>{tr('Audio-Format', 'Audio Encoding')}</label>
                                  <select value={geminiTtsAudioEncoding} onChange={(e) => setGeminiTtsAudioEncoding(e.target.value)}>
                                    <option value="MP3">MP3</option>
                                    <option value="LINEAR16">LINEAR16</option>
                                    <option value="OGG_OPUS">OGG_OPUS</option>
                                    <option value="MULAW">MULAW</option>
                                    <option value="ALAW">ALAW</option>
                                    <option value="PCM">PCM</option>
                                  </select>
                                </div>

                                <div className="input-group">
                                  <label>{tr('Stil-Prompt (optional)', 'Style Prompt (optional)')}</label>
                                  <input
                                    type="text"
                                    value={geminiTtsStylePrompt}
                                    onChange={(e) => setGeminiTtsStylePrompt(e.target.value)}
                                    placeholder={tr('z.B. Sprich ruhig und freundlich', 'e.g. Speak in a calm and friendly tone')}
                                  />
                                </div>
                              </div>

                              <div className="button-group">
                                <button className="btn primary" onClick={saveAIConfig}>{t('save')}</button>
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
            {activeTab === 'talk-bot' && (
              <div className="settings-panel">
                <div className="panel-section">
                  <div className="section-title" style={{fontSize: '1.4rem', marginBottom: '1rem'}}>
                    🤖 Nextcloud Talk Bot Setup
                  </div>
                  <p style={{fontSize: '1rem', color: 'var(--muted)', lineHeight: '1.6', margin: '0 0 1rem 0'}}>
                    {tr('Diese Anleitung zeigt die Schritte zur Installation und Konfiguration des Mynd Talk Bots auf deinem Nextcloud-Server.', 'This guide shows the steps to install and configure the Mynd Talk Bot on your Nextcloud server.')}
                  </p>
                  
                  <div style={{backgroundColor: 'var(--bg-light)', padding: '1rem', borderRadius: '0.5rem', marginBottom: '1.5rem', border: '1px solid var(--border-color)'}}>
                    <strong>⚠️ {tr('Voraussetzungen', 'Requirements')}:</strong>
                    <ul style={{margin: '0.5rem 0 0 1.5rem'}}>
                      <li>{tr('SSH-Zugriff auf den Nextcloud-Server mit Admin-Rechten', 'SSH access to Nextcloud server with admin privileges')}</li>
                      <li>{tr('Mynd Backend läuft und ist über öffentliche URL erreichbar', 'Mynd backend is running and reachable via public URL')}</li>
                      <li>{tr('Die Webhook-URL muss von außen erreichbar sein (z.B. über ngrok wenn lokal)', 'Webhook URL must be externally reachable (e.g., via ngrok if local)')}</li>
                    </ul>
                  </div>

                  {/* Step-by-step instructions */}
                  <div style={{display: 'grid', gridTemplateColumns: '1fr', gap: '1.5rem'}}>
                    {/* Webhook URL */}
                    <div style={{backgroundColor: 'var(--bg-light)', padding: '1rem', borderRadius: '0.5rem', border: '1px solid var(--border-color)'}}>
                      <div style={{display: 'flex', alignItems: 'center', marginBottom: '0.5rem'}}>
                        <span style={{fontSize: '1.2rem', marginRight: '0.5rem'}}>1️⃣</span>
                        <strong>{tr('Webhook-URL von Mynd', 'Mynd Webhook URL')}</strong>
                      </div>
                      <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0 0 0.5rem 0'}}>
                        {tr('Diese URL kopierst du in den OCC-Befehl weiter unten:', 'Copy this URL to the OCC command below:')}
                      </p>
                      <div style={{display: 'flex', gap: '0.5rem'}}>
                        <input 
                          type="text" 
                          value={briefingTalkWebhookUrl || 'https://mynd.example.com/api/nextcloud/talk/webhook'} 
                          onChange={(e) => setBriefingTalkWebhookUrl(e.target.value)}
                          style={{flex: 1}}
                          placeholder="https://mynd.example.com/api/nextcloud/talk/webhook"
                        />
                        <button className="btn" onClick={() => {
                          navigator.clipboard.writeText(briefingTalkWebhookUrl || 'https://mynd.example.com/api/nextcloud/talk/webhook');
                          alert('Kopiert!');
                        }}>📋</button>
                      </div>
                    </div>

                    {/* Secret */}
                    <div style={{backgroundColor: 'var(--bg-light)', padding: '1rem', borderRadius: '0.5rem', border: '1px solid var(--border-color)'}}>
                      <div style={{display: 'flex', alignItems: 'center', marginBottom: '0.5rem'}}>
                        <span style={{fontSize: '1.2rem', marginRight: '0.5rem'}}>2️⃣</span>
                        <strong>{tr('Bot-Secret generieren', 'Generate Bot Secret')}</strong>
                      </div>
                      <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0 0 0.5rem 0'}}>
                        {tr('Auf dem Nextcloud-Server (SSH):', 'On Nextcloud server (SSH):')}
                      </p>
                      <code style={{display: 'block', backgroundColor: 'var(--bg-dark)', padding: '0.5rem', borderRadius: '0.25rem', fontSize: '0.9rem', color: 'var(--success)', marginBottom: '0.5rem', wordBreak: 'break-all'}}>
                        openssl rand -hex 24
                      </code>
                      <p style={{fontSize: '0.85rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
                        {tr('Kopiere die 48-Zeichen-Ausgabe:', 'Copy the 48-character output:')}
                      </p>
                      <div style={{display: 'flex', gap: '0.5rem'}}>
                        <input 
                          type="text" 
                          value={briefingBotSecretLocal} 
                          onChange={(e) => setBriefingBotSecretLocal(e.target.value)}
                          style={{flex: 1}}
                          placeholder="(z.B. a1b2c3d4e5f6...)"
                        />
                        <button className="btn" onClick={() => {
                          navigator.clipboard.writeText(briefingBotSecretLocal);
                          alert('Kopiert!');
                        }} disabled={!briefingBotSecretLocal}>📋</button>
                        <button className="btn" onClick={async () => {
                          // generate 24 random bytes -> 48 hex chars
                          const bytes = new Uint8Array(24);
                          crypto.getRandomValues(bytes);
                          const hex = Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
                          setBriefingBotSecretLocal(hex);
                          // Persist immediately
                          try {
                            setBriefingStatus(tr('Generiere und speichere Secret...', 'Generating and saving secret...'));
                            const res = await fetch(`${API_BASE}/api/ui/system-config`, {
                              method: 'POST',
                              headers: { 'Content-Type': 'application/json' },
                              body: JSON.stringify({ briefing_talk_webhook_secret: hex })
                            });
                            const data = await res.json().catch(() => ({}));
                            if (res.ok && data?.success) {
                              setBriefingTalkWebhookSecretSet(true);
                              setBriefingStatus(tr('Secret generiert und gespeichert', 'Secret generated and saved'));
                            } else {
                              setBriefingStatus(tr('Fehler beim Speichern des Secrets', 'Error saving secret'));
                            }
                          } catch (e) {
                            setBriefingStatus(tr('Fehler beim Speichern des Secrets', 'Error saving secret'));
                          }
                        }}>🔐 {tr('Generieren & Speichern', 'Generate & Save')}</button>
                      </div>
                    </div>

                    {/* Bot Installation Command */}
                    <div style={{backgroundColor: 'var(--bg-light)', padding: '1rem', borderRadius: '0.5rem', border: '1px solid var(--border-color)'}}>
                      <div style={{display: 'flex', alignItems: 'center', marginBottom: '0.5rem'}}>
                        <span style={{fontSize: '1.2rem', marginRight: '0.5rem'}}>3️⃣</span>
                        <strong>{tr('Bot auf Nextcloud installieren', 'Install Bot on Nextcloud')}</strong>
                      </div>
                      <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0 0 0.5rem 0'}}>
                        {tr('Führe diesen Befehl auf dem Nextcloud-Server aus (SSH mit sudo):', 'Run this command on Nextcloud server (SSH with sudo):')}
                      </p>
                      <div style={{backgroundColor: 'var(--bg-dark)', padding: '0.75rem', borderRadius: '0.25rem', fontSize: '0.85rem', color: 'var(--success)', fontFamily: 'monospace', marginBottom: '0.5rem', wordBreak: 'break-all', whiteSpace: 'pre-wrap', maxHeight: '200px', overflow: 'auto'}}>
                        {'sudo -u www-data php /var/www/nextcloud/occ talk:bot:install \\\n  --feature webhook,response --no-setup \\\n  "Mynd Bot" \\\n  "' + (briefingBotSecretLocal || '<SECRET>') + '" \\\n  "' + (briefingTalkWebhookUrl || 'https://mynd.example.com/api/nextcloud/talk/webhook') + '"'}
                      </div>
                      <button className="btn" onClick={() => {
                        const cmd = `sudo -u www-data php /var/www/nextcloud/occ talk:bot:install --feature webhook,response --no-setup "Mynd Bot" "${briefingBotSecretLocal || '<SECRET>'}" "${briefingTalkWebhookUrl || 'https://mynd.example.com/api/nextcloud/talk/webhook'}"`;
                        navigator.clipboard.writeText(cmd);
                        alert('Befehl kopiert! Einfügen im SSH-Terminal.');
                      }}>📋 {tr('Befehl kopieren', 'Copy command')}</button>
                      <p style={{fontSize: '0.85rem', color: 'var(--warning)', margin: '0.5rem 0', fontStyle: 'italic'}}>
                        ℹ️ {tr('Speichere die Bot-ID (SHA1 Hash) aus der Ausgabe auf!', 'Save the Bot ID (SHA1 hash) from the output!')}
                      </p>
                    </div>

                    {/* Bot ID */}
                    <div style={{backgroundColor: 'var(--bg-light)', padding: '1rem', borderRadius: '0.5rem', border: '1px solid var(--border-color)'}}>
                      <div style={{display: 'flex', alignItems: 'center', marginBottom: '0.5rem'}}>
                        <span style={{fontSize: '1.2rem', marginRight: '0.5rem'}}>4️⃣</span>
                        <strong>{tr('Bot-ID abrufen', 'Get Bot ID')}</strong>
                      </div>
                      <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0 0 0.5rem 0'}}>
                        {tr('Hinweis: `talk:bot:install` gibt die Bot‑ID direkt in der Ausgabe an (z.B. "ID: 40"). Du brauchst `talk:bot:list` nicht zusätzlich auszuführen.', 'Note: `talk:bot:install` prints the Bot ID directly in its output (e.g. "ID: 40"). You do not need to run `talk:bot:list` additionally.')}
                      </p>
                      <p style={{fontSize: '0.85rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
                        {tr('Kopiere die dort angezeigte Bot‑ID (z.B. 40) in das Feld, oder trage sie hier manuell ein.', 'Copy the Bot ID shown there (e.g. 40) into the field, or enter it here manually.')}
                      </p>
                      <input 
                        type="text" 
                        value={briefingTalkServerBotId} 
                        onChange={(e) => setBriefingTalkServerBotId(e.target.value)}
                        placeholder="z.B. bot1a2b3c4d5e6f7g8h9i0j..."
                        style={{width: '100%'}}
                      />
                    </div>

                    {/* Room Setup */}
                    <div style={{backgroundColor: 'var(--bg-light)', padding: '1rem', borderRadius: '0.5rem', border: '1px solid var(--border-color)'}}>
                      <div style={{display: 'flex', alignItems: 'center', marginBottom: '0.5rem'}}>
                        <span style={{fontSize: '1.2rem', marginRight: '0.5rem'}}>5️⃣</span>
                        <strong>{tr('Bot zum Raum hinzufügen', 'Add Bot to Room')}</strong>
                      </div>
                      <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0 0 0.5rem 0'}}>
                        {tr('Room-Token (Raum-ID) eingeben:', 'Enter Room Token (Room ID):')}
                      </p>
                      <input 
                        type="text" 
                        value={briefingTalkRoomId} 
                        onChange={(e) => setBriefingTalkRoomId(e.target.value)}
                        placeholder="z.B. mychannel"
                        style={{width: '100%', marginBottom: '0.5rem'}}
                      />
                      <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
                        {tr('Danach diesen Befehl ausführen:', 'Then run this command:')}
                      </p>
                      <div style={{backgroundColor: 'var(--bg-dark)', padding: '0.75rem', borderRadius: '0.25rem', fontSize: '0.85rem', color: 'var(--success)', fontFamily: 'monospace', marginBottom: '0.5rem', wordBreak: 'break-all'}}>
                        {'sudo -u www-data php /var/www/nextcloud/occ talk:bot:setup \\\n  ' + (briefingTalkServerBotId || '<BOT_ID>') + ' \\\n  ' + (briefingTalkRoomId || '<ROOM_TOKEN>')}
                      </div>
                      <button className="btn" onClick={() => {
                        const cmd = `sudo -u www-data php /var/www/nextcloud/occ talk:bot:setup "${briefingTalkServerBotId || '<BOT_ID>'}" "${briefingTalkRoomId || 'mychannel'}"`;
                        navigator.clipboard.writeText(cmd);
                        alert('Befehl kopiert!');
                      }}>📋 {tr('Befehl kopieren', 'Copy command')}</button>
                    </div>

                    {/* Test */}
                    <div style={{backgroundColor: 'var(--bg-light)', padding: '1rem', borderRadius: '0.5rem', border: '1px solid var(--border-color)'}}>
                      <div style={{display: 'flex', alignItems: 'center', marginBottom: '0.5rem'}}>
                        <span style={{fontSize: '1.2rem', marginRight: '0.5rem'}}>6️⃣</span>
                        <strong>{tr('Webhook testen', 'Test Webhook')}</strong>
                      </div>
                      <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0 0 0.5rem 0'}}>
                        {tr('Klick unten um eine Test-Nachricht zu senden:', 'Click below to send a test message:')}
                      </p>
                      <button className="btn primary" onClick={testTalkWebhook} style={{width: '100%'}}>
                        🧪 {tr('Talk Webhook testen', 'Test Talk webhook')}
                      </button>
                      {briefingStatus && (
                        <div style={{
                          marginTop: '0.5rem',
                          padding: '0.5rem',
                          borderRadius: '0.25rem',
                          backgroundColor: briefingStatus.includes('✅') ? 'var(--success-bg)' : briefingStatus.includes('❌') ? 'var(--error-bg)' : 'var(--info-bg)',
                          color: briefingStatus.includes('✅') ? 'var(--success)' : briefingStatus.includes('❌') ? 'var(--error)' : 'var(--info)',
                          fontSize: '0.9rem'
                        }}>
                          {briefingStatus}
                        </div>
                      )}
                    </div>
                  </div>

                  <div style={{marginTop: '2rem', padding: '1rem', backgroundColor: 'var(--bg-light)', borderRadius: '0.5rem', border: '1px solid var(--border-color)'}}>
                    <strong>{tr('Troubleshooting', 'Troubleshooting')}:</strong>
                    <ul style={{margin: '0.5rem 0 0 1.5rem', fontSize: '0.9rem'}}>
                      <li><strong>❌ Signatur-Fehler:</strong> {tr('Das Secret im Mynd Settings muss EXAKT mit dem OCC-Setup übereinstimmen', 'The secret in Mynd settings must EXACTLY match the OCC setup')}</li>
                      <li><strong>❌ Bot nicht gefunden:</strong> {tr('Stelle sicher dass der OCC install Befehl erfolgreich war', 'Make sure the OCC install command succeeded')}</li>
                      <li><strong>❌ Webhook erreicht Backend nicht:</strong> {tr('Prüfe dass die Webhook-URL von Nextcloud aus erreichbar ist (nicht localhost!)', 'Check that the webhook URL is reachable from Nextcloud (not localhost!)')}</li>
                      <li><strong>❌ Messages erscheinen als User:</strong> {tr('Bot ist wahrscheinlich nicht korrekt installiert', 'Bot probably is not correctly installed')}</li>
                    </ul>
                  </div>

                  <div style={{marginTop: '1rem', padding: '1rem', backgroundColor: 'var(--info-bg)', borderRadius: '0.5rem', border: '1px solid var(--info)'}}>
                    <strong style={{color: 'var(--info)'}}>🔍 {tr('Bot antwortet nicht automatisch?', 'Bot doesn\'t reply automatically?')}</strong>
                    <p style={{margin: '0.5rem 0 0 0', fontSize: '0.9rem', color: 'var(--muted)'}}>
                      {tr('Häufige Gründe:', 'Common reasons:')}
                    </p>
                    <ol style={{margin: '0.5rem 0 0 1.5rem', fontSize: '0.9rem', color: 'var(--muted)'}}>
                      <li>{tr('Der Bot wurde NICHT mit dem Flag --feature response installiert (Schritt 3)', 'Bot was NOT installed with --feature response flag (Step 3)')}</li>
                      <li>{tr('Die Webhook-URL ist nicht erreichbar von Nextcloud (z.B. localhost ohne Tunnel)', 'Webhook URL is not reachable from Nextcloud (e.g. localhost without tunnel)')}</li>
                      <li>{tr('Der Bot wurde nicht mit talk:bot:setup zu dem Raum hinzugefügt (Schritt 5)', 'Bot was not added to room with talk:bot:setup (Step 5)')}</li>
                      <li>{tr('Das Secret wurde nicht in Mynd Settings gespeichert (Schritt 6)', 'Secret was not saved in Mynd settings (Step 6)')}</li>
                    </ol>
                    <p style={{margin: '0.75rem 0 0 0', fontSize: '0.85rem', color: 'var(--muted)'}}>
                      <strong>{tr('Lösung:', 'Solution:')}</strong> {tr('Überprüfe alle 7 Setup-Schritte oben nochmal - besonders Schritt 3 und 5!', 'Check all 7 setup steps above again - especially steps 3 and 5!')}
                    </p>
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
                  {/* Persistent Index Stats */}
                  <div style={{display: 'flex', gap: '0.75rem', marginBottom: '1rem', flexWrap: 'wrap'}}>
                    <div style={{padding: '0.6rem 0.8rem', background: 'var(--background)', borderRadius: '8px', border: '1px solid var(--line)'}}>
                      <div style={{fontSize: '0.95rem', fontWeight: '700'}}>{persistentIndexStats?.db_stats?.documents || 0}</div>
                      <div style={{fontSize: '0.75rem', color: 'var(--muted)'}}>{tr('Dokumente indexiert', 'Documents indexed')}</div>
                    </div>
                    <div style={{padding: '0.6rem 0.8rem', background: 'var(--background)', borderRadius: '8px', border: '1px solid var(--line)'}}>
                      <div style={{fontSize: '0.95rem', fontWeight: '700'}}>{persistentIndexStats?.db_stats?.chunks || 0}</div>
                      <div style={{fontSize: '0.75rem', color: 'var(--muted)'}}>{tr('Chunks insgesamt', 'Total chunks')}</div>
                    </div>
                    <div style={{padding: '0.6rem 0.8rem', background: 'var(--background)', borderRadius: '8px', border: '1px solid var(--line)'}}>
                      <div style={{fontSize: '0.95rem', fontWeight: '700'}}>{persistentIndexStats?.db_stats?.embeddings || 0}</div>
                      <div style={{fontSize: '0.75rem', color: 'var(--muted)'}}>{tr('Embeddings', 'Embeddings')}</div>
                    </div>
                    {persistentIndexStats?.indexing_runs?.length > 0 && (
                      <div style={{padding: '0.6rem 0.8rem', background: 'var(--background)', borderRadius: '8px', border: '1px solid var(--line)'}}>
                        <div style={{fontSize: '0.75rem', color: 'var(--muted)'}}>Letzte Indexierung</div>
                        <div style={{fontSize: '0.8rem'}}>{new Date((persistentIndexStats.indexing_runs[0].ended_at || 0) * 1000).toLocaleString('de-DE')}</div>
                      </div>
                    )}
                  </div>
                  
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

                <div className="panel-section" style={{marginTop: '2rem'}}>
                  <div className="section-title">{tr('E-Mail-Indexierung', 'Email Indexing')}</div>
                  <p style={{fontSize: '0.9rem', color: 'var(--muted)', margin: '0.5rem 0'}}>
                    {tr('Indexiere deine E-Mails für die semantische Suche', 'Index your emails for semantic search')}
                  </p>

                  <div className="input-group">
                    <label>{tr('Quelle für die E-Mail-Indexierung', 'Email indexing source')}</label>
                    <select
                      value={emailIndexingMode}
                      onChange={(e) => setEmailIndexingMode(e.target.value)}
                    >
                      <option value="existing">{tr('Gespeichertes Konto verwenden', 'Use saved account')}</option>
                      <option value="manual">{tr('Eigenes Konto manuell angeben', 'Enter custom account')}</option>
                    </select>
                  </div>

                  {emailIndexingMode === 'existing' ? (
                    <>
                      <div className="input-group">
                        <label>{tr('Gespeichertes E-Mail-Konto', 'Saved email account')}</label>
                        <select
                          value={emailIndexingAccountId}
                          onChange={(e) => setEmailIndexingAccountId(e.target.value)}
                        >
                          {briefingEmailAccounts.length === 0 ? (
                            <option value="">{tr('Keine Konten verfügbar', 'No accounts available')}</option>
                          ) : (
                            briefingEmailAccounts.map((account) => (
                              <option key={account.account_id} value={account.account_id}>
                                {account.display_name}
                              </option>
                            ))
                          )}
                        </select>
                        <small style={{color: 'var(--muted)', display: 'block', marginTop: '0.25rem'}}>
                          {tr('Es wird die unter APIs bereits gespeicherte Konfiguration verwendet. Manuelle IMAP-Daten sind dann nicht nötig.', 'The already saved API configuration is used. Manual IMAP details are not needed.')} 
                        </small>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="input-group">
                        <label>IMAP Host</label>
                        <input 
                          type="text" 
                          value={emailConfig.imap_host}
                          onChange={(e) => setEmailConfig({...emailConfig, imap_host: e.target.value})}
                          placeholder="imap.gmail.com"
                        />
                      </div>

                      <div className="input-group">
                        <label>IMAP Port</label>
                        <input 
                          type="number" 
                          value={emailConfig.imap_port}
                          onChange={(e) => setEmailConfig({...emailConfig, imap_port: parseInt(e.target.value)})}
                          placeholder="993"
                        />
                      </div>

                      <div className="input-group">
                        <label>{tr('E-Mail-Adresse', 'Email Address')}</label>
                        <input 
                          type="email" 
                          value={emailConfig.username}
                          onChange={(e) => setEmailConfig({...emailConfig, username: e.target.value})}
                          placeholder="your-email@example.com"
                        />
                      </div>

                      <div className="input-group">
                        <label>{tr('Passwort', 'Password')}</label>
                        <input 
                          type="password" 
                          value={emailConfig.password}
                          onChange={(e) => setEmailConfig({...emailConfig, password: e.target.value})}
                          placeholder="••••••••"
                        />
                        <small style={{color: 'var(--muted)', display: 'block', marginTop: '0.25rem'}}>
                          {tr('Für Gmail: Verwende App-Passwort (nicht dein normales Passwort)', 'For Gmail: Use App Password (not your regular password)')}
                        </small>
                      </div>
                    </>
                  )}

                  <div className="input-group">
                    <label>{tr('Ordner (kommasepariert)', 'Folders (comma-separated)')}</label>
                    <input 
                      type="text" 
                      value={emailConfig.folders}
                      onChange={(e) => setEmailConfig({...emailConfig, folders: e.target.value})}
                      placeholder="INBOX, Sent, Drafts"
                    />
                    <small style={{color: 'var(--muted)', display: 'block', marginTop: '0.25rem'}}>
                      {tr('Welche E-Mail-Ordner sollen indexiert werden?', 'Which email folders should be indexed?')}
                    </small>
                  </div>

                  <div className="input-group">
                    <label>{tr('Max E-Mails pro Ordner', 'Max Emails per Folder')}</label>
                    <input 
                      type="number" 
                      value={emailConfig.max_emails}
                      onChange={(e) => setEmailConfig({...emailConfig, max_emails: parseInt(e.target.value)})}
                      placeholder="50"
                    />
                  </div>

                  <div className="input-group" style={{display: 'flex', alignItems: 'center'}}>
                    <label style={{display: 'flex', alignItems: 'center', cursor: 'pointer', marginBottom: 0}}>
                      <input 
                        type="checkbox" 
                        checked={emailConfig.use_ssl}
                        onChange={(e) => setEmailConfig({...emailConfig, use_ssl: e.target.checked})}
                        style={{marginRight: '0.5rem'}}
                      />
                      {tr('SSL/TLS verwenden', 'Use SSL/TLS')}
                    </label>
                  </div>

                  <div className="button-group" style={{marginTop: '1.5rem'}}>
                    <button className="btn secondary" onClick={testEmailConnection} disabled={emailTestLoading}>
                      <i className="fas fa-flask" style={{marginRight: '0.5rem'}}></i>
                      {emailTestLoading ? tr('Teste Verbindung...', 'Testing Connection...') : tr('Verbindung testen', 'Test Connection')}
                    </button>
                    {emailIndexingMode === 'manual' && (
                      <button className="btn primary" onClick={saveEmailConfig} disabled={!emailConfig.imap_host || !emailConfig.username || !emailConfig.password}>
                        <i className="fas fa-save" style={{marginRight: '0.5rem'}}></i>
                        {tr('Manuelle Konfiguration speichern', 'Save manual config')}
                      </button>
                    )}
                  </div>

                  {emailConfigStatus && <div className={`status-text ${emailConfigStatus.includes('Fehler') ? 'error' : 'success'}`}>{emailConfigStatus}</div>}

                  <div className="button-group" style={{marginTop: '1.5rem'}}>
                    <button className="btn primary" onClick={startEmailIndexing} disabled={emailIndexingStatus === 'running'}>
                      <i className="fas fa-envelope" style={{marginRight: '0.5rem'}}></i>
                      {emailIndexingStatus === 'running' ? tr('E-Mail-Indexierung läuft...', 'Email Indexing...') : tr('E-Mail-Indexierung starten', 'Start Email Indexing')}
                    </button>
                    {emailIndexingStatus === 'running' && (
                      <button className="btn secondary" onClick={stopEmailIndexing}>
                        {tr('Stoppen', 'Stop')}
                      </button>
                    )}
                  </div>

                  {/* Email Indexing Progress */}
                  {(emailIndexingStatus !== 'idle' || emailIndexingDetails.processed > 0) && (
                    <div style={{marginTop: '1.5rem', padding: '1rem', background: 'var(--surface)', borderRadius: '8px', border: '1px solid var(--border)'}}>
                      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem'}}>
                        <h4 style={{margin: 0, fontSize: '1rem', fontWeight: '600'}}>
                          <i className="fas fa-chart-line" style={{marginRight: '0.5rem'}}></i>
                          {tr('E-Mail-Indexierungsfortschritt', 'Email Indexing Progress')}
                        </h4>
                        <span style={{
                          fontSize: '0.8rem',
                          padding: '0.25rem 0.75rem',
                          borderRadius: '12px',
                          background: emailIndexingStatus === 'running' ? 'var(--primary)' : 
                                     emailIndexingStatus === 'completed' ? 'var(--success)' : 
                                     emailIndexingStatus === 'error' ? 'var(--error)' : 'var(--muted)',
                          color: 'white',
                          fontWeight: '500'
                        }}>
                          {emailIndexingStatus.toUpperCase()}
                        </span>
                      </div>

                      {emailIndexingStatus === 'running' && (
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
                              width: `${emailIndexingProgress}%`,
                              borderRadius: '4px'
                            }}></div>
                          </div>
                          <div style={{display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--muted)', marginTop: '0.5rem'}}>
                            <span>{emailIndexingProgress}% {tr('abgeschlossen', 'Complete')}</span>
                            <span>{emailIndexingDetails.processed} {tr('E-Mails verarbeitet', 'Emails Processed')}</span>
                          </div>
                        </div>
                      )}

                      <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '1rem', marginBottom: '1rem'}}>
                        <div style={{textAlign: 'center', padding: '0.75rem', background: 'var(--background)', borderRadius: '6px'}}>
                          <div style={{fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--primary)'}}>
                            {emailIndexingDetails.processed}
                          </div>
                          <div style={{fontSize: '0.75rem', color: 'var(--muted)'}}>{tr('E-Mails verarbeitet', 'Emails Processed')}</div>
                        </div>
                        <div style={{textAlign: 'center', padding: '0.75rem', background: 'var(--background)', borderRadius: '6px'}}>
                          <div style={{fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--accent)'}}>
                            {Math.floor((emailIndexingDetails.elapsed || 0) / 60)}:{((emailIndexingDetails.elapsed || 0) % 60).toString().padStart(2, '0')}
                          </div>
                          <div style={{fontSize: '0.75rem', color: 'var(--muted)'}}>{tr('Verstrichene Zeit', 'Time Elapsed')}</div>
                        </div>
                        <div style={{textAlign: 'center', padding: '0.75rem', background: 'var(--background)', borderRadius: '6px'}}>
                          <div style={{fontSize: '1.5rem', fontWeight: 'bold', color: 'var(--success)'}}>
                            {emailIndexingDetails.current_folder || '--'}
                          </div>
                          <div style={{fontSize: '0.75rem', color: 'var(--muted)'}}>{tr('Aktueller Ordner', 'Current Folder')}</div>
                        </div>
                      </div>

                      {emailIndexingDetails.message && (
                        <div style={{marginBottom: '1rem', padding: '0.75rem', background: 'var(--background)', borderRadius: '6px', fontSize: '0.85rem', color: 'var(--muted)'}}>
                          {emailIndexingDetails.message}
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
