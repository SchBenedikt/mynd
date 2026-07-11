'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { useTheme } from '../../hooks/useTheme';
import { useLanguage } from '../../hooks/useLanguage';
import { useApp } from '../../lib/AppContext';
import LandingScreen from '../../components/LandingScreen';
import MessageList from '../../components/MessageList';
import Composer from '../../components/Composer';
import PhotoPreviewModal from '../../components/PhotoPreviewModal';
import ChatSummaryModal from '../../components/ChatSummaryModal';
import { apiFetch, getApiBase } from '../../lib/api';

const CHAT_STORAGE_KEY = 'mynd_chat_history_v1';
const ACTIVE_CHAT_STORAGE_KEY = 'mynd_active_chat_v1';
const SIDEBAR_COLLAPSED_KEY = 'mynd_sidebar_collapsed_v1';
const DISPLAY_NAME_STORAGE_KEY = 'mynd_display_name';
const LOCATION_AUTO_RESOLVE_KEY = 'mynd_location_auto_resolve_v1';
const BRIEFING_SEEN_KEY = 'mynd_seen_briefings_v1';
const TTS_PROVIDER_STORAGE_KEY = 'mynd_tts_provider_v1';

const SPEECH_LANG_MAP = {
  de: 'de-DE',
  en: 'en-US',
  fr: 'fr-FR',
  es: 'es-ES',
  it: 'it-IT',
  pt: 'pt-PT',
  nl: 'nl-NL',
  pl: 'pl-PL',
  tr: 'tr-TR',
  ru: 'ru-RU',
  ja: 'ja-JP',
  zh: 'zh-CN'
};

const LANGUAGE_COMMANDS = {
  de: ['deutsch', 'german'],
  en: ['englisch', 'english'],
  fr: ['franzoesisch', 'franzosisch', 'french', 'francais'],
  es: ['spanisch', 'spanish', 'espanol'],
  it: ['italienisch', 'italian', 'italiano'],
  pt: ['portugiesisch', 'portuguese', 'portugues'],
  nl: ['niederlaendisch', 'niederlandisch', 'dutch', 'nederlands'],
  pl: ['polnisch', 'polish', 'polski'],
  tr: ['tuerkisch', 'turkisch', 'turkish', 'turkce'],
  ru: ['russisch', 'russian'],
  ja: ['japanisch', 'japanese'],
  zh: ['chinesisch', 'chinese']
};

const THEME_COMMANDS = {
  ocean: ['blau', 'blue', 'ocean', 'meer'],
  classic: ['gruen', 'grun', 'green', 'nature', 'natuerlich'],
  graphite: ['grau', 'grey', 'gray', 'graphite'],
  lavender: ['lila', 'violett', 'purple', 'lavender'],
  rose: ['rosa', 'pink', 'rose', 'rot'],
  gold: ['gold', 'gelb', 'orange', 'warm']
};

const MODE_COMMANDS = {
  dark: ['dark mode', 'dark-mode', 'dunkelmodus', 'dunkel', 'nachtmodus'],
  light: ['light mode', 'light-mode', 'hellmodus', 'hell'],
  auto: ['auto mode', 'auto-mode', 'automatisch', 'systemmodus']
};



const NAMED_COLOR_COMMANDS = {
  '#e11d48': ['rot', 'red'],
  '#2f63ff': ['blau', 'blue'],
  '#16a34a': ['gruen', 'grun', 'green'],
  '#7c3aed': ['lila', 'violett', 'purple'],
  '#b45309': ['gold', 'orange', 'gelb', 'yellow'],
  '#424242': ['grau', 'gray', 'grey', 'graphite']
};

const THEME_LABEL_KEY = {
  classic: 'Classic',
  ocean: 'Ocean',
  graphite: 'Graphite',
  lavender: 'Lavender',
  rose: 'Rose',
  gold: 'Gold'
};

const DESIGN_COLOR_PRESETS = [
  { id: 'brand-red', label: 'Red', value: '#e11d48' },
  { id: 'brand-blue', label: 'Blue', value: '#2f63ff' },
  { id: 'brand-green', label: 'Green', value: '#16a34a' },
  { id: 'brand-violet', label: 'Violet', value: '#7c3aed' },
  { id: 'brand-gold', label: 'Gold', value: '#b45309' }
];

const createChatId = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.floor(Math.random() * 100000)}`;
};

const createMessageId = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.floor(Math.random() * 100000)}`;
};

const normalizeTtsProvider = (value) => {
  return String(value || '').trim().toLowerCase() === 'gemini' ? 'gemini' : 'browser';
};

const createEmptyChat = (project = null) => {
  const now = Date.now();
  return {
    id: createChatId(),
    title: 'Neuer Chat',
    messages: [],
    createdAt: now,
    updatedAt: now,
    project
  };
};

const buildChatTitleFromText = (text) => {
  const cleaned = String(text || '').trim().replace(/\s+/g, ' ');
  if (!cleaned) return 'Neuer Chat';
  return cleaned.length > 38 ? `${cleaned.slice(0, 38)}...` : cleaned;
};

const safeReadJson = async (response) => {
  const text = await response.text();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return { success: false, error: text };
  }
};

const buildFriendlyChatErrorMessage = (response, data, fallbackMessage = '') => {
  const status = response?.status || 0;
  const backendError = String(data?.error || data?.message || fallbackMessage || '').trim();

  if (status === 0 || status >= 500) {
    return '⚠️ Der Server hat nicht rechtzeitig geantwortet. Das passiert oft bei komplexen Anfragen. Bitte versuche es mit einer kürzeren oder einfacheren Formulierung erneut.';
  }

  if (status === 429) {
    return '⚠️ Zu viele Anfragen in kurzer Zeit. Bitte warte kurz und versuche es dann erneut.';
  }

  if (status >= 400 && backendError) {
    return `⚠️ Fehler: ${backendError}`;
  }

  return '⚠️ Die Anfrage konnte nicht verarbeitet werden. Bitte versuche es erneut.';
};

const analyzeBackendError = (response, data) => {
  const status = response?.status || 0;
  const body = JSON.stringify(data || {});
  const parts = [];
  parts.push(`Fehleranalyse:`);
  parts.push(`- Endpoint antwortete mit Status ${status}.`);
  if (body) parts.push(`- Antwort vom Server: ${body}`);

  if (status >= 500) {
    parts.push('- Mögliche Ursachen: interner Serverfehler, Ausnahme im Backend, fehlende Abhängigkeiten oder defekte Datenbankverbindung.');
    parts.push('- Nächste Schritte: prüfe die Backend-Logs (run_app.py stdout), suche nach Tracebacks oder Exceptions, prüfe Datenbank- und Index-Verbindungen und API-Keys.');
  } else if (status === 401 || status === 403) {
    parts.push('- Mögliche Ursachen: nicht authentifiziert oder unzureichende Berechtigungen. Überprüfe Login/Token/Session.');
    parts.push('- Nächste Schritte: melde dich ab und wieder an, überprüfe OAuth-Credentials oder Admin-Benutzer-Konfiguration.');
  } else if (status === 429) {
    parts.push('- Mögliche Ursachen: Rate-Limiting vom Backend oder externen APIs.');
    parts.push('- Nächste Schritte: warte kurz oder prüfe Backend-Rate-Limits und API-Quoten.');
  } else {
    parts.push('- Mögliche Ursachen: fehlerhafte Anfrage oder Validierungsfehler.');
    parts.push('- Nächste Schritte: überprüfe die Anfrageparameter in den Einstellungen oder die Backend-Validierungen.');
  }

  parts.push('Wenn du möchtest, kann ich versuchen, die Backend-Fehlermeldung detaillierter zu interpretieren.');
  return parts.join('\n');
};

const getTodayDateTimeForInputs = () => {
  const today = new Date();
  const year = String(today.getFullYear());
  const month = String(today.getMonth() + 1).padStart(2, '0');
  const day = String(today.getDate()).padStart(2, '0');
  return {
    dateOnly: `${year}-${month}-${day}`,
    dateTime: `${year}-${month}-${day}T09:00`
  };
};

const resolveSpeechLocale = (langCode) => SPEECH_LANG_MAP[langCode] || 'de-DE';

const cleanTextForSpeech = (value) => String(value || '')
  .replace(/(^|\n)\s*(?:\*\*|__)?\s*(assistant|assistent)\s*(?:\*\*|__)?\s*[:：-]\s*/gim, '$1')
  .replace(/\b(?:assistant|assistent)\b\s*[:：-]\s*/gi, '')
  .replace(/```[\s\S]*?```/g, ' ')
  .replace(/`([^`]+)`/g, '$1')
  .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
  .replace(/\[[^\]]+\]\([^)]*\)/g, '$1')
  .replace(/[#>*_~\-]+/g, ' ')
  .replace(/\s+/g, ' ')
  .trim();

const splitTextForGeminiTts = (text, maxChars = 280) => {
  const normalized = String(text || '').trim();
  if (!normalized) return [];

  const sentenceParts = normalized.match(/[^.!?]+[.!?]?/g) || [normalized];
  const chunks = [];
  let current = '';

  for (const sentence of sentenceParts) {
    const part = sentence.trim();
    if (!part) continue;

    if (!current) {
      current = part;
      continue;
    }

    if ((`${current} ${part}`).length <= maxChars) {
      current = `${current} ${part}`;
    } else {
      chunks.push(current);
      current = part;
    }
  }

  if (current) chunks.push(current);
  return chunks;
};

export default function HomePage() {
  const router = useRouter();
  const {
    theme,
    darkMode,
    contrastColor,
    setTheme,
    setDarkMode,
    setContrastColor
  } = useTheme();
  const { language, setLanguage, t, languages } = useLanguage();
  const tr = (deText, enText) => (language === 'de' ? deText : enText);
  const { chats, setChats, activeChatId, setActiveChatId, user, setUser, health, setHealth, projects, setProjects, activeProject, setActiveProject } = useApp();
  const [isThinking, setIsThinking] = useState(false);
  const [pendingQueue, setPendingQueue] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [source, setSource] = useState('auto');
  const [pendingToolConfirm, setPendingToolConfirm] = useState(null);
  const [pendingUserInput, setPendingUserInput] = useState(null);
  const [pendingUserInputValue, setPendingUserInputValue] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const fileInputRef = useRef(null);
  const [securityStatus, setSecurityStatus] = useState(null);
  const [securityLoading, setSecurityLoading] = useState(false);
  const [proactiveBriefings, setProactiveBriefings] = useState([]);
  const [displayName, setDisplayName] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [projectModalOpen, setProjectModalOpen] = useState(false);
  const [, setGreetingTick] = useState(0);
  const [isListening, setIsListening] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [voiceError, setVoiceError] = useState('');
  const [speechCapabilities, setSpeechCapabilities] = useState({ input: false, output: false });
  const [selectedVoiceUri, setSelectedVoiceUri] = useState('');
  const [ttsProvider, setTtsProvider] = useState('browser');
  
  const [aiProtocol, setAiProtocol] = useState('http');
  const [aiHost, setAiHost] = useState('127.0.0.1');
  const [aiPort, setAiPort] = useState('11434');
  const [aiModel, setAiModel] = useState('');
  const [aiModels, setAiModels] = useState([]);
  const [model, setModel] = useState('');
  const [aiStatus, setAiStatus] = useState('');
  const [personalGreeting, setPersonalGreeting] = useState('');
  const [liveTools, setLiveTools] = useState({});
  
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
  const logout = async () => {
    try { await apiFetch('/api/auth/logout', { method: 'POST' }); } catch (e) {}
    try { localStorage.removeItem('mynd_user_v1'); localStorage.removeItem('mynd_token_v1'); } catch (e) {}
    window.location.reload();
  };
  const [calendarForm, setCalendarForm] = useState({
    visible: false,
    missingInfo: [],
    title: '',
    startTime: '',
    endTime: '',
    calendarName: '',
    location: '',
    description: '',
    availableCalendars: [],
    submitting: false,
    error: ''
  });
  const [taskForm, setTaskForm] = useState({
    visible: false,
    missingInfo: [],
    title: '',
    dueDate: '',
    priority: 0,
    listName: '',
    location: '',
    description: '',
    availableTaskLists: [],
    submitting: false,
    error: ''
  });
  const [integrationForm, setIntegrationForm] = useState({
    visible: false,
    provider: '',
    feature: '',
    title: '',
    description: '',
    fields: [],
    values: {},
    quickActions: [],
    submitEndpoint: '',
    originalPrompt: '',
    submitting: false,
    loginFlowRunning: false,
    error: ''
  });
  const [photoPreview, setPhotoPreview] = useState({
    open: false,
    title: '',
    thumbnailUrl: '',
    immichUrl: '',
    sourceUrl: '',
    downloadUrl: ''
  });
  const [chatSummaryPanel, setChatSummaryPanel] = useState({
    open: false,
    chatId: '',
    title: '',
    summary: '',
    generatedAt: 0,
    messageCount: 0,
    stats: {
      total: 0,
      user: 0,
      assistant: 0
    },
    loading: false,
    error: ''
  });
  const progressIntervalRef = useRef(null);
  const requestAbortRef = useRef(null);
  const speechRecognitionRef = useRef(null);
  const activeAudioRef = useRef(null);
  const audioContextRef = useRef(null);
  const activeAudioSourceRef = useRef(null);
  const ttsPlaybackTokenRef = useRef(0);
  
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const activeChat = chats.find((chat) => chat.id === activeChatId) || null;
  const messages = activeChat?.messages || [];
  const conversationActive = messages.length > 0;
  const weatherInfo = securityStatus?.weather || null;
  const speechRecognitionSupported = speechCapabilities.input;
  const speechSynthesisSupported = speechCapabilities.output;

  const languageLabel = (code) => languages.find((l) => l.code === code)?.label || code;

  const renderWeatherMiniIcon = (iconType) => {
    if (iconType === 'rain') {
      return (
        <span className="weather-mini-icon rain" aria-hidden="true">
          <i className="fas fa-cloud"></i>
          <span className="rain-drop drop-1"></span>
          <span className="rain-drop drop-2"></span>
          <span className="rain-drop drop-3"></span>
        </span>
      );
    }

    if (iconType === 'cloud') {
      return (
        <span className="weather-mini-icon cloud" aria-hidden="true">
          <i className="fas fa-cloud"></i>
        </span>
      );
    }

    return (
      <span className="weather-mini-icon sun" aria-hidden="true">
        <i className="fas fa-sun"></i>
      </span>
    );
  };

  const fetchGreeting = async () => {
    try {
      const res = await fetch(`${getApiBase()}/api/ai/greeting`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language, name: displayName })
      });
      const data = await res.json();
      if (data.success && data.greeting) {
        setPersonalGreeting(data.greeting);
      }
    } catch {
      /* keep fallback */
    }
  };

  const normalizeText = (value) => String(value || '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');

  const detectMappedValue = (normalizedText, map) => {
    const entries = Object.entries(map);
    for (const [value, keywords] of entries) {
      if (keywords.some((keyword) => normalizedText.includes(keyword))) {
        return value;
      }
    }
    return null;
  };

  const detectLanguageTarget = (normalizedText) => {
    let bestMatch = null;
    let bestIndex = -1;

    for (const [value, keywords] of Object.entries(LANGUAGE_COMMANDS)) {
      for (const keyword of keywords) {
        const idx = normalizedText.lastIndexOf(keyword);
        if (idx > bestIndex) {
          bestIndex = idx;
          bestMatch = value;
        }
      }
    }

    return bestMatch;
  };

  const detectColorTarget = (normalizedText, originalText) => {
    const hexMatch = String(originalText || '').match(/#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b/);
    if (hexMatch?.[0]) {
      return hexMatch[0];
    }

    for (const [hex, keywords] of Object.entries(NAMED_COLOR_COMMANDS)) {
      if (keywords.some((keyword) => normalizedText.includes(keyword))) {
        return hex;
      }
    }

    return null;
  };

  const handleUiControlCommand = (text, targetChatId) => {
    const normalized = normalizeText(text);
    const languageTarget = detectLanguageTarget(normalized);
    const themeTarget = detectMappedValue(normalized, THEME_COMMANDS);
    const modeTarget = detectMappedValue(normalized, MODE_COMMANDS);
    const colorTarget = detectColorTarget(normalized, text);

    // Don't interpret HA/smart-home commands as design intent
    const isHomeAssistantCmd = /schalte|licht|lampe|einschalten|ausschalten|nanoleaf|hue|philips|wohnzimmer|schlafzimmer|küche|terrasse|garage|helligkeit|dimmer|temperatur|farbe|rgb|heizung|rollladen|steckdose|szene/i.test(normalized);
    if (isHomeAssistantCmd && !languageTarget) {
      return false;
    }

    const wantsDesignPanel = /theme|design|farbe|color|look|stil|style/.test(normalized);

    const hasControlIntent = /sprache|language|theme|farbe|color|modus|mode|design|blau|blue|deutsch|englisch/.test(normalized);
    if (!hasControlIntent && !languageTarget && !themeTarget && !modeTarget && !colorTarget) {
      return false;
    }

    const confirmations = [];

    if (languageTarget && languageTarget !== language) {
      setLanguage(languageTarget);
      confirmations.push(t('cmdLanguageChanged', { value: languageLabel(languageTarget) }));
    }

    if (themeTarget && themeTarget !== theme) {
      setTheme(themeTarget);
      confirmations.push(t('cmdThemeChanged', { value: THEME_LABEL_KEY[themeTarget] || themeTarget }));
    }

    if (modeTarget) {
      setDarkMode(modeTarget);
      const modeKey = modeTarget === 'dark' ? 'modeDark' : modeTarget === 'light' ? 'modeLight' : 'modeAuto';
      confirmations.push(t('cmdModeChanged', { value: t(modeKey) }));
    }

    if (colorTarget) {
      setContrastColor(colorTarget);
      const colorConfirm = language === 'de'
        ? `Akzentfarbe wurde auf ${colorTarget} gesetzt.`
        : `Accent color was set to ${colorTarget}.`;
      confirmations.push(colorConfirm);
    }

    if (!confirmations.length && !wantsDesignPanel) {
      return false;
    }

    appendMessageToChat(targetChatId, {
      role: 'assistant',
      content: confirmations.length ? `${confirmations.join('\n')}\n\n${t('designControlHint')}` : t('designControlHint'),
      designControls: wantsDesignPanel || confirmations.length > 0,
      id: createMessageId()
    });

    return true;
  };

  useEffect(() => {
    if (!messagesEndRef.current) return;
    const el = messagesEndRef.current;
    const parent = el.parentElement;
    if (parent) {
      const distanceToBottom = parent.scrollHeight - parent.scrollTop - parent.clientHeight;
      if (distanceToBottom > 150) return;
    }
    el.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (!isThinking && pendingQueue.length > 0) {
      processNextQueued();
    }
  }, [isThinking, pendingQueue]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    setSpeechCapabilities({
      input: 'SpeechRecognition' in window || 'webkitSpeechRecognition' in window,
      output: 'speechSynthesis' in window && typeof window.SpeechSynthesisUtterance !== 'undefined'
    });
  }, []);

  useEffect(() => {
    loadAIConfig();
    loadOllamaModels();
    updateStatus();
    loadSecurityStatus();
    loadProactiveBriefings();
    autoResolveLocationOnOpen();
    fetchGreeting();
    if (!personalGreeting) {
      setPersonalGreeting('Hallo');
    }
    
    const onPop = () => {
      const urlChat = new URL(window.location.href).searchParams.get('chat');
      if (urlChat) {
        setActiveChatId(urlChat);
      }
    };
    window.addEventListener('popstate', onPop);

    const statusInterval = setInterval(updateStatus, 8000);
    const securityInterval = setInterval(loadSecurityStatus, 60000);
    const briefingInterval = setInterval(loadProactiveBriefings, 10 * 60 * 1000);
    return () => {
      clearInterval(statusInterval);
      clearInterval(securityInterval);
      clearInterval(briefingInterval);
      window.removeEventListener('popstate', onPop);
    };
  }, []);

  useEffect(() => {
    if (!activeChatId || !proactiveBriefings.length) return;

    let seen = [];
    try {
      seen = JSON.parse(localStorage.getItem(BRIEFING_SEEN_KEY) || '[]');
      if (!Array.isArray(seen)) seen = [];
    } catch {
      seen = [];
    }

    const unseen = proactiveBriefings.filter((item) => item?.key && !seen.includes(item.key));
    if (!unseen.length) return;

    unseen.forEach((item) => {
      appendMessageToChat(activeChatId, {
        role: 'assistant',
        content: `## ${item.title || 'Briefing'}\n\n${item.content || ''}`,
        id: createMessageId(),
        sources: [],
        uiCards: []
      });
    });

    try {
      const nextSeen = [...new Set([...seen, ...unseen.map((item) => item.key)])];
      localStorage.setItem(BRIEFING_SEEN_KEY, JSON.stringify(nextSeen));
    } catch (err) {
      console.error('Could not persist seen briefings:', err);
    }
  }, [activeChatId, proactiveBriefings]);

  const autoResolveLocationOnOpen = async () => {
    if (typeof window === 'undefined' || !navigator.geolocation) {
      return;
    }

    // Avoid repeated permission prompts during the same browser session.
    try {
      const marker = sessionStorage.getItem(LOCATION_AUTO_RESOLVE_KEY);
      if (marker === 'done') {
        return;
      }
    } catch (err) {
      console.error('Could not read location auto-resolve marker:', err);
    }

    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          await fetch(`${getApiBase()}/api/location/resolve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              lat: position.coords.latitude,
              lon: position.coords.longitude,
              save: true
            })
          });
        } catch (err) {
          console.error('Automatic location resolve failed:', err);
        } finally {
          try {
            sessionStorage.setItem(LOCATION_AUTO_RESOLVE_KEY, 'done');
          } catch (storageErr) {
            console.error('Could not persist location auto-resolve marker:', storageErr);
          }
          loadSecurityStatus();
        }
      },
      () => {
        try {
          sessionStorage.setItem(LOCATION_AUTO_RESOLVE_KEY, 'done');
        } catch (storageErr) {
          console.error('Could not persist location auto-resolve marker:', storageErr);
        }
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 60000
      }
    );
  };

  useEffect(() => {
    try {
      const rawDisplayName = localStorage.getItem(DISPLAY_NAME_STORAGE_KEY);
      if (rawDisplayName) setDisplayName(rawDisplayName);
    } catch (err) { console.error('Error loading data:', err); }
  }, []);

  useEffect(() => {
    const cleanChats = chats.filter(c => (c.messages?.length || 0) > 0 || c.title !== 'Neuer Chat');
    if (cleanChats.length !== chats.length) {
      setChats(cleanChats);
    }
  }, []);

  useEffect(() => {
    if (chats.length === 0) {
      const initialChat = createEmptyChat();
      setChats([initialChat]);
      setActiveChatId(initialChat.id);
      return;
    }
    if (!activeChatId) {
      setActiveChatId(chats[0].id);
      return;
    }
    const urlChat = typeof window !== 'undefined' ? new URL(window.location.href).searchParams.get('chat') : null;
    if (urlChat && chats.some(c => c.id === urlChat) && urlChat !== activeChatId) {
      setActiveChatId(urlChat);
    }
  }, [chats.length]);

  useEffect(() => {
    const interval = setInterval(() => {
      setGreetingTick(Date.now());
    }, 15 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!chats.length || !activeChatId) return;
    const cleanChats = chats.filter(c => (c.messages?.length || 0) > 0 || c.title !== 'Neuer Chat');
    try {
      localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(cleanChats));
      localStorage.setItem(ACTIVE_CHAT_STORAGE_KEY, activeChatId);
    } catch (err) {
      console.error('Error saving chat history:', err);
    }
  }, [chats, activeChatId]);

  useEffect(() => {
    if (!photoPreview.open) return undefined;

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setPhotoPreview((prev) => ({ ...prev, open: false }));
      }
    };

    window.addEventListener('keydown', handleEscape);
    return () => {
      window.removeEventListener('keydown', handleEscape);
    };
  }, [photoPreview.open]);

  useEffect(() => {
    if (!chatSummaryPanel.open) return undefined;

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setChatSummaryPanel((prev) => ({ ...prev, open: false }));
      }
    };

    window.addEventListener('keydown', handleEscape);
    return () => {
      window.removeEventListener('keydown', handleEscape);
    };
  }, [chatSummaryPanel.open]);

  useEffect(() => {
    const handleCancelKey = (event) => {
      if (!isThinking) return;
      if (event.key === 'c' && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        cancelPendingRequest();
      }
    };

    window.addEventListener('keydown', handleCancelKey);
    return () => {
      window.removeEventListener('keydown', handleCancelKey);
    };
  }, [isThinking]);

  const cancelPendingRequest = () => {
    if (!requestAbortRef.current) return;
    requestAbortRef.current.abort();
    requestAbortRef.current = null;
    setIsThinking(false);

    if (activeChatId) {
      appendMessageToChat(activeChatId, {
        role: 'assistant',
        content: 'Anfrage abgebrochen.',
        id: createMessageId()
      });
    }
  };

  const appendMessageToChat = (chatId, message, originalUserText = null) => {
    const now = Date.now();
    setChats((prevChats) => prevChats.map((chat) => {
      if (chat.id !== chatId) return chat;
      const nextMessages = [...(chat.messages || []), message];
      const shouldUpdateTitle = chat.title === 'Neuer Chat' && message.role === 'user' && originalUserText;
      return {
        ...chat,
        messages: nextMessages,
        title: shouldUpdateTitle ? buildChatTitleFromText(originalUserText) : chat.title,
        updatedAt: now
      };
    }));
  };

  const updateMessageInChat = (chatId, messageId, updater) => {
    setChats((prevChats) => prevChats.map((chat) => {
      if (chat.id !== chatId) return chat;
      const nextMessages = (chat.messages || []).map((msg) => {
        if (msg.id !== messageId) return msg;
        return updater(msg);
      });
      return { ...chat, messages: nextMessages };
    }));
  };

  const insertMessageAfter = (chatId, afterMessageId, message) => {
    setChats((prevChats) => prevChats.map((chat) => {
      if (chat.id !== chatId) return chat;
      const messagesList = chat.messages || [];
      const index = messagesList.findIndex((msg) => msg.id === afterMessageId);
      if (index === -1) {
        return { ...chat, messages: [...messagesList, message] };
      }
      const nextMessages = [...messagesList];
      nextMessages.splice(index + 1, 0, message);
      return { ...chat, messages: nextMessages };
    }));
  };

  const loadAIConfig = async () => {
    try {
      const res = await fetch(`${getApiBase()}/api/ai/config`);
      const config = await safeReadJson(res);
      if (!res.ok || !config?.base_url) {
        throw new Error(config?.error || `Request failed with status ${res.status}`);
      }
      const url = new URL(config.base_url);
      setAiProtocol(url.protocol.replace(':', ''));
      setAiHost(url.hostname);
      setAiPort(url.port || '11434');
      setAiModel(config.model);
      setModel(config.model);

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
      setAiStatus('Loaded');
    } catch (err) {
      setAiStatus('Error loading config');
    }
  };

  const loadOllamaModels = async () => {
    try {
      const res = await fetch(`${getApiBase()}/api/ollama/models`);
      const data = await safeReadJson(res);
      setAiModels(data.models || []);
    } catch (err) {
      console.error('Error loading models:', err);
    }
  };

  const saveAIConfig = async () => {
    try {
      const baseUrl = `${aiProtocol}://${aiHost}:${aiPort}`;
      const res = await fetch(`${getApiBase()}/api/ai/config`, {
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
        fetch(`${getApiBase()}/api/ollama/status`),
        fetch(`${getApiBase()}/api/knowledge/status`)
      ]);
      const ollama = await safeReadJson(ollamaRes);
      const kb = await safeReadJson(kbRes);
      const totalChunks = Number(kb.chunks_loaded || 0);
      const generatedEmbeddings = Number(kb.generated_embeddings ?? kb.embeddings_count ?? 0);
      const missingEmbeddings = Number(kb.missing_embeddings ?? Math.max(totalChunks - generatedEmbeddings, 0));
      const embeddingsComplete = Boolean(kb.embeddings_complete ?? (totalChunks > 0 && missingEmbeddings === 0));
      setHealth({
        ollama: ollama.connected ? 'ok' : 'error',
        kb: kb.database_path ? 'ok' : 'error',
        embeddings: kb.semantic_search_available ? (embeddingsComplete ? 'ok' : 'loading') : 'error'
      });
      // also fetch current user (if any) to display in sidebar
      try {
        const storedToken = (() => { try { return localStorage.getItem('mynd_token_v1'); } catch(e) { return null; } })();
        const headers = storedToken ? { 'Authorization': `Bearer ${storedToken}` } : {};
        const meRes = await fetch(`${getApiBase()}/api/auth/me`, { headers });
        const me = await safeReadJson(meRes);
        if (meRes.ok && me && me.authenticated) setUser(me.user);
        else setUser(null);
      } catch (err) {
        setUser(null);
      }
    } catch (err) {
      setHealth({ ollama: 'error', kb: 'error', embeddings: 'error' });
    }
  };

  const loadSecurityStatus = async () => {
    try {
      setSecurityLoading(true);
      const res = await fetch(`${getApiBase()}/api/security/status`);
      const data = await safeReadJson(res);
      if (!res.ok || data?.success === false) {
        setSecurityStatus({
          headline: 'Sicherheitslage aktuell nicht verfügbar',
          nina_warning_count: 0,
          nina_warnings: []
        });
        return;
      }
      setSecurityStatus(data);
    } catch (err) {
      setSecurityStatus({
        headline: 'Sicherheitslage aktuell nicht verfügbar',
        nina_warning_count: 0,
        nina_warnings: []
      });
    } finally {
      setSecurityLoading(false);
    }
  };

  const loadProactiveBriefings = async (force = false) => {
    try {
      const briefingUrl = force
        ? `${getApiBase()}/api/assistant/briefing/current?force=true`
        : `${getApiBase()}/api/assistant/briefing/current`;
      const res = await fetch(briefingUrl);
      const data = await safeReadJson(res);
      if (!res.ok || data?.success === false) {
        return;
      }
      const items = Array.isArray(data?.items) ? data.items : [];
      setProactiveBriefings(items.filter((item) => item?.content));
    } catch (err) {
      console.error('Could not load proactive briefings:', err);
    }
  };

  const startIndexing = async () => {
    try {
      // First check if there's a configuration
      const configRes = await fetch(`${getApiBase()}/api/indexing/config`);
      if (configRes.ok) {
        const config = await configRes.json();
        if (!config.url || !config.username) {
          setIndexingStatus('error: Nextcloud configuration required. Please configure in Settings first.');
          return;
        }
      }
      
      const res = await fetch(`${getApiBase()}/api/indexing/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      if (res.ok) {
        setIndexingStatus('running');
        if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = setInterval(async () => {
          try {
            const res = await fetch(`${getApiBase()}/api/indexing/progress`);
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
                `${data.processed_files || 0}/${data.total_files || 0} ${t('files').toLowerCase()} | ` +
                `${Math.round(data.elapsed_time || 0)}s ${t('elapsed').toLowerCase()} | ` +
                `${processingSpeed} ${t('files').toLowerCase()}/s | ` +
                (timeRemaining > 0 ? `~${timeRemaining}s` : '...')
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

  const queueMessage = (text, chatId, meta = {}) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    const messageId = createMessageId();
    appendMessageToChat(chatId, { role: 'user', content: trimmed, id: messageId, queued: true }, trimmed);
    setPendingQueue((prev) => [...prev, { chatId, text: trimmed, messageId, fromVoice: Boolean(meta.fromVoice) }]);
    setInputValue('');
    if (inputRef.current) inputRef.current.value = '';
  };

  const processNextQueued = () => {
    if (pendingQueue.length === 0) return;
    const [next, ...rest] = pendingQueue;
    setPendingQueue(rest);
    sendMessage(next.text, {
      fromQueue: true,
      chatId: next.chatId,
      messageId: next.messageId,
      fromVoice: Boolean(next.fromVoice)
    });
  };

  const handleFileUpload = async (files) => {
    const uploaded = [];
    for (const file of files) {
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res = await apiFetch('/api/upload', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.success) {
          uploaded.push(data);
        }
      } catch (e) {
        console.error('Upload error:', e);
      }
    }
    setUploadedFiles(prev => [...prev, ...uploaded]);
  };

  const removeUploadedFile = (idx) => {
    setUploadedFiles(prev => prev.filter((_, i) => i !== idx));
  };

  const sendMessage = async (text, options = {}) => {
    if (!text.trim()) return;
    if (isThinking && !options.fromQueue) {
      const targetId = activeChatId || createEmptyChat().id;
      if (!activeChatId) {
        const newChat = createEmptyChat();
        setChats([newChat]);
        setActiveChatId(newChat.id);
        queueMessage(text, newChat.id, { fromVoice: options.fromVoice });
        return;
      }
      queueMessage(text, targetId, { fromVoice: options.fromVoice });
      return;
    }
    text = text.trim();

    let targetChatId = options.chatId || activeChatId;
    if (!targetChatId) {
      const newChat = createEmptyChat();
      setChats([newChat]);
      setActiveChatId(newChat.id);
      targetChatId = newChat.id;
    }

    const userMessageId = options.messageId || createMessageId();
    if (options.messageId) {
      updateMessageInChat(targetChatId, options.messageId, (msg) => ({ ...msg, queued: false }));
    } else {
      appendMessageToChat(targetChatId, { role: 'user', content: text, id: userMessageId }, text);
    }
    setInputValue('');
    if (inputRef.current) inputRef.current.value = '';

    const handledByUIControl = handleUiControlCommand(text, targetChatId);
    if (handledByUIControl) {
      return;
    }

    setIsThinking(true);
    const abortController = new AbortController();
    requestAbortRef.current = abortController;

    try {
      const currentMessages = chats.find((chat) => chat.id === targetChatId)?.messages || [];
      const contextMessages = options.messageId ? currentMessages : [...currentMessages, { role: 'user', content: text, id: userMessageId }];
      const conversationContext = contextMessages
        .slice(-8)
        .map((m) => `${m.role === 'user' ? 'User' : 'Assistant'}: ${m.content}`)
        .join('\n');

      let emailConfig = null;
      try {
        const emailConfigRes = await fetch(`${getApiBase()}/api/registry/email/config`);
        const emailConfigData = await safeReadJson(emailConfigRes);
        if (emailConfigRes.ok && emailConfigData?.success !== false) {
          emailConfig = emailConfigData?.config || null;
        }
      } catch (err) {
        console.error('Error loading email config for chat:', err);
      }

      const res = await fetch(`${getApiBase()}/api/agent/query/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: abortController.signal,
          body: JSON.stringify({
            prompt: uploadedFiles.length > 0
              ? `${text}\n\n📎 Angehängte Dateien:\n${uploadedFiles.map((f, i) => `  ${i + 1}. [${f.filename}](${f.url}) (${(f.size / 1024).toFixed(0)} KB)`).join('\n')}\n\nBitte lies diese Dateien ein und verarbeite sie gemäß meiner Anfrage.`
              : text,
            language,
            model: model,
            preferred_source: source,
            context: conversationContext,
            email_config: emailConfig,
            account_id: emailConfig?.active_account_id || emailConfig?.selected_account_id || emailConfig?.account_id || ''
          })
      });
      if (!res.ok) {
        const text_body = await res.text().catch(() => '');
        let err_data;
        try { err_data = JSON.parse(text_body); } catch { err_data = null; }
        const errorMessage = buildFriendlyChatErrorMessage(res, err_data, `Status ${res.status}`);
        insertMessageAfter(targetChatId, userMessageId, {
          role: 'assistant',
          content: errorMessage,
          id: createMessageId()
        });
        return;
      }

      const assistantMessageId = createMessageId();
      insertMessageAfter(targetChatId, userMessageId, {
        role: 'assistant',
        content: '',
        id: assistantMessageId
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      const msgTools = [];
      let activeThinkToolIndex = -1;

      const syncLiveTools = () => {
        setLiveTools(prev => ({ ...prev, [assistantMessageId]: [...msgTools] }));
      };

      const clearActiveThinkTool = () => {
        activeThinkToolIndex = -1;
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          let event;
          try { event = JSON.parse(line.slice(6)); } catch { continue; }

          if (event.type === 'tool_start') {
            clearActiveThinkTool();
            msgTools.push({ ...event, status: 'running' });
            document.getElementById('thinking-text') && (document.getElementById('thinking-text').textContent = `⟳ ${event.tool}...`);
            syncLiveTools();
          } else if (event.type === 'content') {
            clearActiveThinkTool();
            updateMessageInChat(targetChatId, assistantMessageId, (msg) => ({
              ...msg,
              content: (msg.content || '') + event.content
            }));
          } else if (event.type === 'think') {
            const thinkChunk = String(event.content || '');
            if (!thinkChunk) continue;

            if (activeThinkToolIndex < 0 || msgTools[activeThinkToolIndex]?.tool !== 'think') {
              msgTools.push({
                type: 'think',
                round: event.round || 1,
                tool: 'think',
                args: { thought: '' },
                status: 'done',
                success: true
              });
              activeThinkToolIndex = msgTools.length - 1;
            }

            const previousThought = String(msgTools[activeThinkToolIndex]?.args?.thought || '');
            msgTools[activeThinkToolIndex] = {
              ...msgTools[activeThinkToolIndex],
              args: {
                ...msgTools[activeThinkToolIndex].args,
                thought: previousThought + thinkChunk
              }
            };
            syncLiveTools();

            updateMessageInChat(targetChatId, assistantMessageId, (msg) => ({
              ...msg,
              thinking: (msg.thinking || '') + thinkChunk
            }));
          } else if (event.type === 'status') {
            clearActiveThinkTool();
            const statusText = String(event.message || '').trim();
            document.getElementById('thinking-text') && (document.getElementById('thinking-text').textContent = statusText || 'Anfrage läuft...');
          } else if (event.type === 'tool_end') {
            clearActiveThinkTool();
            const idx = msgTools.findLastIndex(t => t.tool === event.tool && t.status === 'running');
            if (idx >= 0) msgTools[idx] = { ...msgTools[idx], ...event, status: 'done' };
            else msgTools.push({ ...event, status: 'done' });
            document.getElementById('thinking-text') && (document.getElementById('thinking-text').textContent = `✓ ${event.tool} (${(event.duration_ms/1000).toFixed(1)}s)`);
            syncLiveTools();
          } else if (event.type === 'final') {
            clearActiveThinkTool();
            document.getElementById('thinking-text') && (document.getElementById('thinking-text').textContent = '');
            setLiveTools(prev => { const n = {...prev}; delete n[assistantMessageId]; return n; });
            updateMessageInChat(targetChatId, assistantMessageId, (msg) => ({
              ...msg,
              content: event.response,
              researchStats: event.research_stats || [],
              files: event.files || [],
              streamTrace: [...msgTools]
            }));
            if (options.fromVoice) {
              speakAssistantText(event.response);
            }
          } else if (event.type === 'error') {
            clearActiveThinkTool();
            document.getElementById('thinking-text') && (document.getElementById('thinking-text').textContent = '');
            setLiveTools(prev => { const n = {...prev}; delete n[assistantMessageId]; return n; });
            updateMessageInChat(targetChatId, assistantMessageId, (msg) => ({
              ...msg,
              content: `⚠️ Fehler: ${event.error}`,
              streamTrace: [...msgTools]
            }));
          } else if (event.type === 'needs_input') {
            clearActiveThinkTool();
            document.getElementById('thinking-text') && (document.getElementById('thinking-text').textContent = '');
            setLiveTools(prev => { const n = {...prev}; delete n[assistantMessageId]; return n; });
            setPendingUserInput({ message: event.message, chatId: targetChatId, messageId: assistantMessageId });
          } else if (event.type === 'confirm_tool') {
            clearActiveThinkTool();
            document.getElementById('thinking-text') && (document.getElementById('thinking-text').textContent = '');
            setLiveTools(prev => { const n = {...prev}; delete n[assistantMessageId]; return n; });
            setPendingToolConfirm({ tool: event.tool, description: event.description });
          }
        }
      }
    } catch (err) {
      if (err?.name === 'AbortError') {
        return;
      }
      const isTimeout = /timeout|timed ?out|econnrefused|econnreset|networkerror/i.test(String(err?.message || ''));
      const friendlyMessage = isTimeout
        ? '⚠️ Die Anfrage hat zu lange gedauert. Bitte versuche es mit einer kürzeren oder einfacheren Formulierung erneut.'
        : (err?.message || '⚠️ Die Anfrage konnte nicht verarbeitet werden. Bitte versuche es erneut.');
      updateMessageInChat(targetChatId, assistantMessageId, (msg) => ({
        ...msg,
        content: (msg.content || '') + '\n\n' + friendlyMessage
      }));
    } finally {
      setIsThinking(false);
      setUploadedFiles([]);
      requestAbortRef.current = null;
    }
  };

  const stopVoiceInput = () => {
    const recognition = speechRecognitionRef.current;
    if (!recognition) return;
    recognition.stop();
  };

  const ensureUnlockedAudioContext = async () => {
    if (typeof window === 'undefined') return null;
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return null;

    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContextClass();
    }

    if (audioContextRef.current.state === 'suspended') {
      try {
        await audioContextRef.current.resume();
      } catch (_) {
        return audioContextRef.current;
      }
    }

    return audioContextRef.current;
  };

  const base64ToArrayBuffer = (base64) => {
    const binaryString = window.atob(String(base64 || ''));
    const len = binaryString.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i += 1) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
  };

  const playGeminiAudioWithWebAudio = async (audioBase64) => {
    const context = await ensureUnlockedAudioContext();
    if (!context) return false;

    const encodedBuffer = base64ToArrayBuffer(audioBase64);
    const decodedBuffer = await context.decodeAudioData(encodedBuffer.slice(0));

    if (activeAudioSourceRef.current) {
      try {
        activeAudioSourceRef.current.stop();
      } catch (_) {
        // ignore stop errors from stale sources
      }
      activeAudioSourceRef.current = null;
    }

    const source = context.createBufferSource();
    source.buffer = decodedBuffer;
    source.connect(context.destination);
    activeAudioSourceRef.current = source;

    return new Promise((resolve, reject) => {
      source.onended = () => {
        if (activeAudioSourceRef.current === source) {
          activeAudioSourceRef.current = null;
        }
        resolve(true);
      };

      try {
        source.start(0);
      } catch (err) {
        if (activeAudioSourceRef.current === source) {
          activeAudioSourceRef.current = null;
        }
        reject(err);
      }
    });
  };

  const playGeminiAudioWithHtmlAudio = async (audioBase64, mimeType = 'audio/mpeg') => {
    const audio = new Audio(`data:${mimeType};base64,${audioBase64}`);
    activeAudioRef.current = audio;

    return new Promise((resolve, reject) => {
      audio.onended = () => {
        if (activeAudioRef.current === audio) {
          activeAudioRef.current = null;
        }
        resolve(true);
      };

      audio.onerror = () => {
        if (activeAudioRef.current === audio) {
          activeAudioRef.current = null;
        }
        reject(new Error(language === 'de' ? 'Gemini-Audio konnte nicht abgespielt werden.' : 'Gemini audio playback failed.'));
      };

      audio.play().catch(reject);
    });
  };

  const speakAssistantText = (text) => {
    const prepared = cleanTextForSpeech(text).slice(0, 1100);
    if (!prepared) return;

    const stopAudioPlayback = () => {
      ttsPlaybackTokenRef.current += 1;

      const activeAudio = activeAudioRef.current;
      if (activeAudio) {
        try {
          activeAudio.pause();
        } catch (_) {
          // ignore pause errors from stale audio instances
        }
        activeAudioRef.current = null;
      }

      if (activeAudioSourceRef.current) {
        try {
          activeAudioSourceRef.current.stop();
        } catch (_) {
          // ignore stop errors from stale sources
        }
        activeAudioSourceRef.current = null;
      }

      setIsSpeaking(false);
    };

    const speakWithBrowser = () => {
      if (!speechSynthesisSupported) return;

      try {
        stopAudioPlayback();
        window.speechSynthesis.cancel();
        const utterance = new window.SpeechSynthesisUtterance(prepared);
        const locale = resolveSpeechLocale(language);
        utterance.lang = locale;
        utterance.rate = 1;
        utterance.pitch = 1;

        const browserVoices = window.speechSynthesis.getVoices();
        const selectedVoice = selectedVoiceUri
          ? browserVoices.find((voice) => voice.voiceURI === selectedVoiceUri)
          : null;
        const matchingVoice = selectedVoice
          || browserVoices.find((voice) => voice.lang?.toLowerCase().startsWith(language.toLowerCase()))
          || browserVoices.find((voice) => voice.lang?.toLowerCase().startsWith(locale.slice(0, 2).toLowerCase()));

        if (matchingVoice) {
          utterance.voice = matchingVoice;
        }

        utterance.onstart = () => {
          setIsSpeaking(true);
        };

        utterance.onend = () => {
          setIsSpeaking(false);
        };

        utterance.onerror = () => {
          setIsSpeaking(false);
          setVoiceError(language === 'de' ? 'Sprachausgabe fehlgeschlagen.' : 'Text-to-speech failed.');
        };

        window.speechSynthesis.speak(utterance);
      } catch (err) {
        setIsSpeaking(false);
        setVoiceError(language === 'de' ? 'Sprachausgabe nicht verfuegbar.' : 'Text-to-speech is unavailable.');
      }
    };

    const speakWithGeminiFallback = async (playbackToken) => {
      const chunks = splitTextForGeminiTts(prepared, 260);
      if (!chunks.length) {
        return;
      }

      for (const chunk of chunks) {
        if (playbackToken !== ttsPlaybackTokenRef.current) {
          return;
        }

        const response = await fetch(getApiBase() + '/api/tts/synthesize', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: chunk,
            language_code: resolveSpeechLocale(language)
          })
        });
        const data = await safeReadJson(response);

        if (!response.ok || data?.success === false || !data?.audio_base64) {
          throw new Error(data?.error || `Gemini TTS request failed (${response.status})`);
        }

        if (playbackToken !== ttsPlaybackTokenRef.current) {
          return;
        }

        try {
          await playGeminiAudioWithWebAudio(data.audio_base64);
        } catch (_) {
          await playGeminiAudioWithHtmlAudio(data.audio_base64, data?.mime_type || 'audio/mpeg');
        }
      }
    };

    const speakWithGemini = async () => {
      let currentPlaybackToken = 0;

      try {
        stopAudioPlayback();
        ttsPlaybackTokenRef.current += 1;
        currentPlaybackToken = ttsPlaybackTokenRef.current;

        if (speechSynthesisSupported) {
          window.speechSynthesis.cancel();
        }

        setIsSpeaking(true);
        setVoiceError('');

        const response = await fetch(getApiBase() + '/api/tts/live', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: prepared,
            language_code: resolveSpeechLocale(language)
          })
        });

        if (!response.ok || !response.body) {
          await speakWithGeminiFallback(currentPlaybackToken);
          return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let gotAudio = false;
        let streamError = '';
        let playbackChain = Promise.resolve();

        const enqueueAudioChunk = (audioBase64, mimeType) => {
          playbackChain = playbackChain.then(async () => {
            if (currentPlaybackToken !== ttsPlaybackTokenRef.current) return;
            try {
              const playedWithWebAudio = await playGeminiAudioWithWebAudio(audioBase64);
              if (!playedWithWebAudio) {
                await playGeminiAudioWithHtmlAudio(audioBase64, mimeType || 'audio/wav');
              }
            } catch (_) {
              await playGeminiAudioWithHtmlAudio(audioBase64, mimeType || 'audio/wav');
            }
          });
        };

        let streamDone = false;
        while (!streamDone) {
          const { value, done } = await reader.read();
          if (done) {
            streamDone = true;
          } else {
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
              const trimmed = line.trim();
              if (!trimmed) continue;

              let event = null;
              try {
                event = JSON.parse(trimmed);
              } catch {
                continue;
              }

              if (event?.type === 'audio' && event?.audio_base64) {
                gotAudio = true;
                enqueueAudioChunk(event.audio_base64, event.mime_type);
              }

              if (event?.type === 'error') {
                streamError = String(event.error || 'Live stream failed');
              }

              if (event?.type === 'done') {
                streamDone = true;
              }
            }
          }

          if (currentPlaybackToken !== ttsPlaybackTokenRef.current) {
            try {
              await reader.cancel();
            } catch (_) {
              // ignore reader cancel errors from closed streams
            }
            return;
          }
        }

        if (streamError) {
          throw new Error(streamError);
        }

        if (buffer.trim()) {
          try {
            const lastEvent = JSON.parse(buffer.trim());
            if (lastEvent?.type === 'audio' && lastEvent?.audio_base64) {
              gotAudio = true;
              enqueueAudioChunk(lastEvent.audio_base64, lastEvent.mime_type);
            }
            if (lastEvent?.type === 'error') {
              throw new Error(String(lastEvent.error || 'Live stream failed'));
            }
          } catch (err) {
            if (err instanceof Error) {
              throw err;
            }
          }
        }

        await playbackChain;

        if (!gotAudio) {
          await speakWithGeminiFallback(currentPlaybackToken);
        }
      } catch (err) {
        if (currentPlaybackToken && currentPlaybackToken !== ttsPlaybackTokenRef.current) {
          return;
        }

        try {
          await speakWithGeminiFallback(currentPlaybackToken);
          return;
        } catch (fallbackErr) {
          const fallbackMessage = fallbackErr?.message || err?.message || 'Unknown error';
          setVoiceError(language === 'de'
            ? `Gemini-TTS Fehler: ${fallbackMessage}. Fallback auf Browser-Stimme.`
            : `Gemini TTS error: ${fallbackMessage}. Falling back to browser voice.`);
          speakWithBrowser();
        }
      } finally {
        if (currentPlaybackToken && currentPlaybackToken === ttsPlaybackTokenRef.current) {
          setIsSpeaking(false);
        }
      }
    };

    if (ttsProvider === 'gemini') {
      speakWithGemini();
      return;
    }

    speakWithBrowser();
  };

  const startVoiceInput = () => {
    if (!speechRecognitionSupported) {
      setVoiceError(language === 'de' ? 'Spracheingabe wird von diesem Browser nicht unterstuetzt.' : 'Speech recognition is not supported in this browser.');
      return;
    }

    if (isListening) {
      stopVoiceInput();
      return;
    }

    const RecognitionClass = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!RecognitionClass) {
      setVoiceError(language === 'de' ? 'Spracheingabe ist nicht verfuegbar.' : 'Speech recognition is unavailable.');
      return;
    }

    let finalTranscript = '';
    const recognition = new RecognitionClass();
    speechRecognitionRef.current = recognition;
    recognition.lang = resolveSpeechLocale(language);
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setVoiceError('');
      setIsListening(true);
    };

    recognition.onresult = (event) => {
      let interimTranscript = '';
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const text = event.results[i][0]?.transcript || '';
        if (event.results[i].isFinal) {
          finalTranscript += ` ${text}`;
        } else {
          interimTranscript += ` ${text}`;
        }
      }
      const previewText = (finalTranscript + interimTranscript).trim();
      setInputValue(previewText);
      if (inputRef.current) {
        inputRef.current.value = previewText;
      }
    };

    recognition.onerror = (event) => {
      const code = String(event.error || '');
      if (code === 'not-allowed' || code === 'service-not-allowed') {
        setVoiceError(language === 'de' ? 'Mikrofonzugriff wurde verweigert.' : 'Microphone permission was denied.');
      } else if (code !== 'aborted') {
        setVoiceError(language === 'de' ? `Spracheingabe-Fehler: ${code}` : `Speech input error: ${code}`);
      }
    };

    recognition.onend = () => {
      setIsListening(false);
      speechRecognitionRef.current = null;
      const transcript = finalTranscript.trim();
      if (transcript) {
        sendMessage(transcript, { fromVoice: true });
      }
    };

    recognition.start();
  };

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;

    const unlockAudio = () => {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) return;

      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContextClass();
      }

      if (audioContextRef.current.state === 'suspended') {
        audioContextRef.current.resume().catch(() => {
          // ignore resume errors on restrictive browsers
        });
      }
    };

    window.addEventListener('pointerdown', unlockAudio, { passive: true });
    window.addEventListener('keydown', unlockAudio);
    return () => {
      window.removeEventListener('pointerdown', unlockAudio);
      window.removeEventListener('keydown', unlockAudio);
    };
  }, []);

  useEffect(() => {
    return () => {
      if (speechRecognitionRef.current) {
        speechRecognitionRef.current.stop();
        speechRecognitionRef.current = null;
      }
      if (activeAudioRef.current) {
        try {
          activeAudioRef.current.pause();
        } catch (_) {
          // ignore pause errors from stale audio instances
        }
        activeAudioRef.current = null;
      }
      if (activeAudioSourceRef.current) {
        try {
          activeAudioSourceRef.current.stop();
        } catch (_) {
          // ignore stop errors from stale sources
        }
        activeAudioSourceRef.current = null;
      }
      if (audioContextRef.current) {
        audioContextRef.current.close().catch(() => {
          // ignore close errors on torn-down contexts
        });
        audioContextRef.current = null;
      }
      if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, [speechSynthesisSupported]);

  const parseBackendDateTimeToInput = (value) => {
    if (!value || typeof value !== 'string') return '';
    const trimmed = value.trim();

    // DD.MM.YYYY HH:MM
    const fullDateTimeMatch = trimmed.match(/^(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}:\d{2})$/);
    if (fullDateTimeMatch) {
      const [, day, month, year, hm] = fullDateTimeMatch;
      return `${year}-${month}-${day}T${hm}`;
    }

    // HH:MM -> heute
    const timeOnlyMatch = trimmed.match(/^(\d{2}:\d{2})$/);
    if (timeOnlyMatch) {
      const today = new Date();
      const year = String(today.getFullYear());
      const month = String(today.getMonth() + 1).padStart(2, '0');
      const day = String(today.getDate()).padStart(2, '0');
      return `${year}-${month}-${day}T${timeOnlyMatch[1]}`;
    }

    return '';
  };

  const formatDateTimeForBackend = (datetimeLocalValue) => {
    if (!datetimeLocalValue) return '';
    // Input format: YYYY-MM-DDTHH:MM -> backend format: DD.MM.YYYY HH:MM
    const [datePart, timePart] = datetimeLocalValue.split('T');
    if (!datePart || !timePart) return datetimeLocalValue;
    const [year, month, day] = datePart.split('-');
    return `${day}.${month}.${year} ${timePart}`;
  };

  const getImageDownloadUrl = (thumbnailUrl) => {
    if (!thumbnailUrl) return '';

    try {
      const parsedUrl = new URL(thumbnailUrl, window.location.origin);
      const assetMatch = parsedUrl.pathname.match(/\/api\/immich\/thumbnail\/([^/?#]+)/);
      const assetId = assetMatch?.[1];

      if (!assetId) return '';

      const params = new URLSearchParams();
      const username = parsedUrl.searchParams.get('username');
      if (username) {
        params.set('username', username);
      }

      const query = params.toString();
      return `${getApiBase()}/api/immich/download/${assetId}${query ? `?${query}` : ''}`;
    } catch (_) {
      return '';
    }
  };

  const openPhotoPreview = ({ title = 'Vorschau', thumbnailUrl = '', immichUrl = '', sourceUrl = '' }) => {
    const resolvedSourceUrl = sourceUrl || immichUrl;
    setPhotoPreview({
      open: true,
      title,
      thumbnailUrl,
      immichUrl,
      sourceUrl: resolvedSourceUrl,
      downloadUrl: getImageDownloadUrl(thumbnailUrl)
    });
  };

  const closePhotoPreview = () => {
    setPhotoPreview((prev) => ({ ...prev, open: false }));
  };

  const handleMarkdownContentClick = (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;

    const imageElement = target.closest('img.chat-thumbnail');
    if (!imageElement) return;

    const anchorElement = imageElement.closest('a');
    const thumbnailUrl = imageElement.getAttribute('src') || '';
    const title = imageElement.getAttribute('alt') || 'Vorschau';
    const sourceUrl = anchorElement?.getAttribute('href') || '';

    event.preventDefault();
    event.stopPropagation();

    openPhotoPreview({ title, thumbnailUrl, sourceUrl });
  };

  const markdownComponents = {
    p: ({ node, children, ...props }) => {
      const isImg = (c) => c.tagName === 'img';
      const isImgLink = (c) => c.tagName === 'a' && c.children?.some(isImg);
      const isWhitespace = (c) => c.type === 'text' && /^\s*$/.test(c.value || '');

      const isImageParagraph = node?.children?.length > 0
        && node.children.every((c) => isImg(c) || isImgLink(c) || isWhitespace(c));

      return (
        <p className={isImageParagraph ? 'markdown-image-paragraph' : undefined} {...props}>
          {children}
        </p>
      );
    },
    a: ({ href, children, ...props }) => {
      return (
        <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
          {children}
        </a>
      );
    },
    img: ({ src, alt, ...props }) => (
      <img
        {...props}
        src={src}
        alt={alt}
        className="chat-thumbnail"
        loading="lazy"
      />
    ),
    code: ({ className, children, inline, ...props }) => {
      if (inline) {
        return <code className="inline-code" {...props}>{children}</code>;
      }
      const codeString = String(children || '').replace(/\n$/, '');
      return <code className={className}>{codeString}</code>;
    },
    pre: ({ children, ...props }) => {
      let codeString = '';
      let language = '';
      if (children && typeof children === 'object') {
        codeString = children.props?.children || '';
        const cls = children.props?.className || '';
        const match = /language-(\w+)/.exec(cls);
        language = match ? match[1] : '';
      }
      return (
        <SyntaxHighlighter
          style={oneDark}
          language={language || undefined}
          PreTag="div"
          customStyle={{ margin: '8px 0', borderRadius: '8px', fontSize: '0.82rem' }}
        >
          {codeString}
        </SyntaxHighlighter>
      );
    }
  };

  const submitCalendarForm = async (e) => {
    e.preventDefault();

    if (!calendarForm.title.trim() || !calendarForm.startTime) {
      setCalendarForm(prev => ({
        ...prev,
        error: 'Bitte mindestens Titel und Startzeit ausfuellen.'
      }));
      return;
    }

    setCalendarForm(prev => ({ ...prev, submitting: true, error: '' }));

    try {
      const payload = {
        title: calendarForm.title.trim(),
        start_time: formatDateTimeForBackend(calendarForm.startTime),
        end_time: calendarForm.endTime ? formatDateTimeForBackend(calendarForm.endTime) : null,
        calendar_name: calendarForm.calendarName || null,
        location: calendarForm.location.trim() || null,
        description: calendarForm.description.trim() || null
      };

      const res = await fetch(`${getApiBase()}/api/calendar/create-with-details`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await res.json();

      if (!res.ok || !data?.success) {
        setCalendarForm(prev => ({
          ...prev,
          submitting: false,
          error: data?.error || 'Termin konnte nicht erstellt werden.'
        }));
        return;
      }

      if (activeChatId) {
        appendMessageToChat(activeChatId, {
          role: 'assistant',
          content: data.message || 'Termin wurde erstellt.',
          id: createMessageId()
        });
      }

      setCalendarForm({
        visible: false,
        missingInfo: [],
        title: '',
        startTime: '',
        endTime: '',
        calendarName: '',
        location: '',
        description: '',
        availableCalendars: [],
        submitting: false,
        error: ''
      });
    } catch (err) {
      setCalendarForm(prev => ({
        ...prev,
        submitting: false,
        error: `Fehler beim Erstellen: ${err.message}`
      }));
    }
  };

  const closeCalendarForm = () => {
    setCalendarForm(prev => ({ ...prev, visible: false, error: '' }));
  };

  const submitTaskForm = async (e) => {
    e.preventDefault();

    if (!taskForm.title.trim()) {
      setTaskForm(prev => ({
        ...prev,
        error: 'Please provide at least a title.'
      }));
      return;
    }

    setTaskForm(prev => ({ ...prev, submitting: true, error: '' }));

    try {
      const payload = {
        title: taskForm.title.trim(),
        due_date: taskForm.dueDate || null,
        priority: Number(taskForm.priority || 0),
        list_name: taskForm.listName || null,
        location: taskForm.location?.trim() || null,
        description: taskForm.description?.trim() || null
      };

      const res = await fetch(`${getApiBase()}/api/tasks/create-with-details`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const data = await safeReadJson(res);

      if (!res.ok || !data?.success) {
        setTaskForm(prev => ({
          ...prev,
          submitting: false,
          error: data?.error || 'Task could not be created.'
        }));
        return;
      }

      if (activeChatId) {
        appendMessageToChat(activeChatId, {
          role: 'assistant',
          content: data.message || 'Task created.',
          id: createMessageId()
        });
      }

      setTaskForm({
        visible: false,
        missingInfo: [],
        title: '',
        dueDate: '',
        priority: 0,
        listName: '',
        location: '',
        description: '',
        availableTaskLists: [],
        submitting: false,
        error: ''
      });
    } catch (err) {
      setTaskForm(prev => ({
        ...prev,
        submitting: false,
        error: `Error while creating task: ${err.message}`
      }));
    }
  };

  const closeTaskForm = () => {
    setTaskForm(prev => ({ ...prev, visible: false, error: '' }));
  };

  const closeIntegrationForm = () => {
    setIntegrationForm(prev => ({
      ...prev,
      visible: false,
      submitting: false,
      loginFlowRunning: false,
      error: ''
    }));
  };

  const runNextcloudLoginFlow = async () => {
    const nextcloudUrl = String(integrationForm.values?.nextcloud_url || '').trim();
    if (!nextcloudUrl) {
      setIntegrationForm(prev => ({ ...prev, error: 'Please enter your Nextcloud URL first.' }));
      return;
    }

    setIntegrationForm(prev => ({
      ...prev,
      loginFlowRunning: true,
      error: ''
    }));

    try {
      const startRes = await fetch(`${getApiBase()}/api/nextcloud/loginflow/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nextcloud_url: nextcloudUrl })
      });
      const startData = await safeReadJson(startRes);

      if (!startRes.ok) {
        setIntegrationForm(prev => ({
          ...prev,
          loginFlowRunning: false,
          error: startData?.error || 'Could not start Nextcloud login flow.'
        }));
        return;
      }

      if (startData?.login_url) {
        window.open(startData.login_url, '_blank', 'noopener,noreferrer');
      }

      const result = await new Promise((resolve) => {
        let attempts = 0;
        const maxAttempts = 120;
        const pollInterval = setInterval(async () => {
          attempts += 1;
          try {
            const pollRes = await fetch(`${getApiBase()}/api/nextcloud/loginflow/poll`);
            const pollData = await safeReadJson(pollRes);

            if (!pollRes.ok) {
              clearInterval(pollInterval);
              resolve({ success: false, error: pollData?.error || 'Nextcloud login failed.' });
              return;
            }

            if (pollData?.status === 'connected') {
              clearInterval(pollInterval);
              resolve({ success: true, data: pollData });
              return;
            }

            if (attempts >= maxAttempts) {
              clearInterval(pollInterval);
              resolve({ success: false, error: 'Login timed out. Please try again.' });
            }
          } catch (err) {
            clearInterval(pollInterval);
            resolve({ success: false, error: err.message || 'Login polling failed.' });
          }
        }, 2000);
      });

      if (!result.success) {
        setIntegrationForm(prev => ({
          ...prev,
          loginFlowRunning: false,
          error: result.error || 'Nextcloud login failed.'
        }));
        return;
      }

      setIntegrationForm(prev => ({
        ...prev,
        visible: false,
        submitting: false,
        loginFlowRunning: false,
        error: ''
      }));

      if (activeChatId) {
        appendMessageToChat(activeChatId, {
          role: 'assistant',
          content: `Connected to Nextcloud as ${result.data?.display_name || result.data?.username || 'user'}.`,
          id: createMessageId()
        });
      }

      if (integrationForm.originalPrompt) {
        sendMessage(integrationForm.originalPrompt);
      }
    } catch (err) {
      setIntegrationForm(prev => ({
        ...prev,
        loginFlowRunning: false,
        error: `Error: ${err.message}`
      }));
    }
  };

  const submitIntegrationForm = async (e) => {
    e.preventDefault();

    const requiredFields = integrationForm.fields.filter((field) => field?.required);
    const missingField = requiredFields.find((field) => {
      const val = integrationForm.values?.[field.name];
      return !String(val || '').trim();
    });

    if (missingField) {
      setIntegrationForm(prev => ({
        ...prev,
        error: `Please provide ${missingField.label || missingField.name}.`
      }));
      return;
    }

    setIntegrationForm(prev => ({ ...prev, submitting: true, error: '' }));

    try {
      let endpoint = integrationForm.submitEndpoint || '';
      let payload = { ...integrationForm.values };

      if (integrationForm.provider === 'nextcloud') {
        endpoint = '/api/nextcloud/login';
      }

      if (integrationForm.provider === 'immich') {
        endpoint = '/api/ui/system-config';
      }

      if (!endpoint) {
        setIntegrationForm(prev => ({
          ...prev,
          submitting: false,
          error: 'No setup endpoint provided for this integration.'
        }));
        return;
      }

      const res = await fetch(`${getApiBase()}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await safeReadJson(res);

      if (!res.ok || data?.success === false || data?.status === 'error') {
        setIntegrationForm(prev => ({
          ...prev,
          submitting: false,
          error: data?.error || data?.message || 'Could not save integration settings.'
        }));
        return;
      }

      setIntegrationForm(prev => ({
        ...prev,
        visible: false,
        submitting: false,
        loginFlowRunning: false,
        error: ''
      }));

      if (activeChatId) {
        appendMessageToChat(activeChatId, {
          role: 'assistant',
          content: 'Integration connected successfully. I am retrying your request now.',
          id: createMessageId()
        });
      }

      if (integrationForm.originalPrompt) {
        sendMessage(integrationForm.originalPrompt);
      }
    } catch (err) {
      setIntegrationForm(prev => ({
        ...prev,
        submitting: false,
        error: `Error while saving configuration: ${err.message}`
      }));
    }
  };

  const resetCalendarForm = () => {
    setCalendarForm({
      visible: false,
      missingInfo: [],
      title: '',
      startTime: '',
      endTime: '',
      calendarName: '',
      location: '',
      description: '',
      availableCalendars: [],
      submitting: false,
      error: ''
    });
  };

  const resetTaskForm = () => {
    setTaskForm({
      visible: false,
      missingInfo: [],
      title: '',
      dueDate: '',
      priority: 0,
      listName: '',
      location: '',
      description: '',
      availableTaskLists: [],
      submitting: false,
      error: ''
    });
  };

  const resetIntegrationForm = () => {
    setIntegrationForm({
      visible: false,
      provider: '',
      feature: '',
      title: '',
      description: '',
      fields: [],
      values: {},
      quickActions: [],
      submitEndpoint: '',
      originalPrompt: '',
      submitting: false,
      loginFlowRunning: false,
      error: ''
    });
  };

  const startNewChat = (sourceMode) => {
    const newChat = createEmptyChat();
    setChats((prev) => [newChat, ...prev]);
    setActiveChatId(newChat.id);
    if (sourceMode) setSource(sourceMode);
    resetCalendarForm();
    resetTaskForm();
    resetIntegrationForm();
  };

  const openChat = (chatId) => {
    setActiveChatId(chatId);
    resetCalendarForm();
    resetTaskForm();
    resetIntegrationForm();
    router.push(`/chat/${chatId}`, { scroll: false });
  };

  const summarizeChat = async (chatId, options = {}) => {
    const chat = chats.find((item) => item.id === chatId);
    if (!chat) return;

    const messagesForSummary = Array.isArray(chat.messages)
      ? chat.messages.filter((message) => {
          const role = String(message?.role || '').toLowerCase();
          return role === 'user' || role === 'assistant';
        })
      : [];

    if (!messagesForSummary.length) {
      window.alert('Dieser Chat hat noch keinen Inhalt zum Zusammenfassen.');
      return;
    }

    const userMessages = messagesForSummary.filter((message) => message.role === 'user').length;
    const assistantMessages = messagesForSummary.filter((message) => message.role === 'assistant').length;
    const reuseCached = !options.force && chat.summary?.messageCount === messagesForSummary.length && chat.summary?.content;

    if (reuseCached) {
      setChatSummaryPanel({
        open: true,
        chatId,
        title: chat.title,
        summary: chat.summary.content,
        generatedAt: chat.summary.generatedAt || Date.now(),
        messageCount: chat.summary.messageCount || messagesForSummary.length,
        stats: {
          total: messagesForSummary.length,
          user: userMessages,
          assistant: assistantMessages
        },
        loading: false,
        error: ''
      });
      return;
    }

    setChatSummaryPanel({
      open: true,
      chatId,
      title: chat.title,
      summary: '',
      generatedAt: 0,
      messageCount: messagesForSummary.length,
      stats: {
        total: messagesForSummary.length,
        user: userMessages,
        assistant: assistantMessages
      },
      loading: true,
      error: ''
    });

    try {
      const res = await fetch(`${getApiBase()}/api/chat/summarize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: messagesForSummary,
          title: chat.title,
          language: 'de',
          preferred_source: 'auto'
        })
      });

      const data = await safeReadJson(res);
      if (!res.ok || data?.success === false) {
        throw new Error(data?.error || `Request failed with status ${res.status}`);
      }

      const summaryText = String(data?.summary || '').trim();
      const generatedAt = Date.now();

      setChats((prevChats) => prevChats.map((item) => (
        item.id === chatId
          ? {
              ...item,
              summary: {
                content: summaryText,
                generatedAt,
                messageCount: messagesForSummary.length
              },
              updatedAt: item.updatedAt || Date.now()
            }
          : item
      )));

      setChatSummaryPanel((prev) => ({
        ...prev,
        open: true,
        summary: summaryText,
        generatedAt,
        loading: false,
        error: ''
      }));
    } catch (err) {
      setChatSummaryPanel((prev) => ({
        ...prev,
        loading: false,
        error: `Zusammenfassung fehlgeschlagen: ${err.message}`
      }));
    }
  };

  const renameChat = (chatId) => {
    const chat = chats.find((item) => item.id === chatId);
    if (!chat) return;
    const nextTitle = window.prompt('Chat umbenennen:', chat.title);
    if (!nextTitle || !nextTitle.trim()) return;
    const trimmed = nextTitle.trim();

    setChats((prevChats) => prevChats.map((item) => (
      item.id === chatId ? { ...item, title: trimmed, updatedAt: Date.now() } : item
    )));
  };

  const deleteChat = (chatId) => {
    const chat = chats.find((item) => item.id === chatId);
    if (!chat) return;
    const confirmed = window.confirm(`Chat "${chat.title}" wirklich loeschen?`);
    if (!confirmed) return;

    if (chatId === activeChatId) {
      resetCalendarForm();
      resetTaskForm();
      resetIntegrationForm();
    }

    setChats((prevChats) => {
      const remaining = prevChats.filter((item) => item.id !== chatId);
      if (!remaining.length) {
        const newChat = createEmptyChat();
        setActiveChatId(newChat.id);
        return [newChat];
      }
      if (chatId === activeChatId) {
        setActiveChatId(remaining[0].id);
      }
      return remaining;
    });
  };

  const assignProjectToChat = (chatId, projectId) => {
    setChats((prev) => prev.map((c) => (c.id === chatId ? { ...c, project: projectId } : c)));
  };

  const sortedChats = [...chats]
    .filter(c => !activeProject || c.project === activeProject)
    .sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));

  const getWeekStart = (value) => {
    const date = new Date(value.getFullYear(), value.getMonth(), value.getDate());
    const day = date.getDay();
    const diff = day === 0 ? -6 : 1 - day;
    date.setDate(date.getDate() + diff);
    return date;
  };

  const getChatGroupLabel = (chat) => {
    const ts = chat.updatedAt || chat.createdAt || 0;
    if (!ts) return 'Aelter';

    const now = new Date();
    const lastUpdated = new Date(ts);
    const hourAgo = new Date(now.getTime() - 60 * 60 * 1000);
    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const startOfYesterday = new Date(startOfToday.getTime() - 24 * 60 * 60 * 1000);
    const startOfWeek = getWeekStart(now);
    const startOfLastWeek = new Date(startOfWeek.getTime() - 7 * 24 * 60 * 60 * 1000);

    if (lastUpdated >= hourAgo) return 'Letzte Stunde';
    if (lastUpdated >= startOfToday) return 'Heute';
    if (lastUpdated >= startOfYesterday) return 'Gestern';
    if (lastUpdated >= startOfWeek) return 'Diese Woche';
    if (lastUpdated >= startOfLastWeek) return 'Letzte Woche';
    return 'Aelter';
  };

  const canSend = inputValue.trim().length > 0;
  const queueReady = isThinking && canSend;
  const voiceStatusText = (() => {
    if (voiceError) return voiceError;
    if (isListening) return language === 'de' ? 'Voice: Ich hoere zu...' : 'Voice: Listening...';
    if (isSpeaking) return language === 'de' ? 'Voice: Ich antworte gerade...' : 'Voice: Speaking...';
    return '';
  })();

  return (
    <>
      <div className="center-area">
        {(securityStatus?.nina_warning_count || 0) > 0 && (
          <div className="security-banner alert">
            <div className="security-banner-header">
              <div className="security-banner-title">
                <i className="fas fa-triangle-exclamation"></i>
                <span>{securityStatus?.headline || 'Aktive Warnungen erkannt'}</span>
              </div>
              <button type="button" className="security-refresh" onClick={loadSecurityStatus}
                disabled={securityLoading} title="Sicherheitslage aktualisieren">
                {securityLoading ? '...' : 'Aktualisieren'}
              </button>
            </div>
            {(securityStatus?.nina_warnings || []).length > 0 && (
              <ul className="security-warning-list">
                {securityStatus.nina_warnings.slice(0, 3).map((warning, idx) => (
                  <li key={`${warning.id || warning.headline || 'warning'}-${idx}`}>
                    <strong>{warning.headline || `Warnung ${idx + 1}`}</strong>
                    {warning.severity ? ` (${warning.severity})` : ''}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {proactiveBriefings.length > 0 && (
          <div className="security-banner" style={{marginTop: '0.5rem'}}>
            <div className="security-banner-header">
              <div className="security-banner-title">
                <i className="fas fa-sun"></i>
                <span>{proactiveBriefings[0]?.title || 'Tagesbriefing'}</span>
              </div>
              <button type="button" className="security-refresh"
                onClick={() => loadProactiveBriefings(true)} title="Briefing aktualisieren">Aktualisieren</button>
            </div>
            <div style={{whiteSpace: 'pre-line', color: 'var(--text-secondary)', fontSize: '0.92rem'}}>
              {(proactiveBriefings[0]?.content || '').slice(0, 360)}
              {(proactiveBriefings[0]?.content || '').length > 360 ? '...' : ''}
            </div>
          </div>
        )}

        {!conversationActive ? (
          <LandingScreen
            personalGreeting={personalGreeting} t={t} language={language} chats={chats}
            inputValue={inputValue} setInputValue={setInputValue} inputRef={inputRef}
            canSend={canSend} isListening={isListening}
            onSend={sendMessage} onStartVoiceInput={startVoiceInput}
            indexingStatus={indexingStatus} indexingProgress={indexingProgress}
            indexingDetails={indexingDetails} indexingStats={indexingStats}
            source={source} setSource={setSource}
            model={model} setModel={setModel} aiModels={aiModels}
          />
        ) : (
          <>
            <MessageList
              messages={messages} isThinking={isThinking}
              liveTools={liveTools}
              markdownComponents={markdownComponents} handleMarkdownContentClick={handleMarkdownContentClick}
              messagesEndRef={messagesEndRef} sendMessage={sendMessage}
              calendarForm={calendarForm} setCalendarForm={setCalendarForm}
              submitCalendarForm={submitCalendarForm} closeCalendarForm={closeCalendarForm}
              taskForm={taskForm} setTaskForm={setTaskForm}
              submitTaskForm={submitTaskForm} closeTaskForm={closeTaskForm}
              integrationForm={integrationForm} setIntegrationForm={setIntegrationForm}
              submitIntegrationForm={submitIntegrationForm} closeIntegrationForm={closeIntegrationForm}
              runNextcloudLoginFlow={runNextcloudLoginFlow}
              openPhotoPreview={openPhotoPreview}
              onEditMessage={(msg) => { setInputValue(msg.content || ''); inputRef.current?.focus(); }}
              onCopyMessage={(text) => navigator.clipboard.writeText(text)}
              theme={theme} darkMode={darkMode} contrastColor={contrastColor}
              setTheme={setTheme} setDarkMode={setDarkMode} setContrastColor={setContrastColor}
              DESIGN_COLOR_PRESETS={DESIGN_COLOR_PRESETS} THEME_LABEL_KEY={THEME_LABEL_KEY}
              t={t} tr={tr} language={language}
            />
            <Composer
              inputValue={inputValue} setInputValue={setInputValue} inputRef={inputRef}
              canSend={canSend} queueReady={queueReady} isThinking={isThinking}
              isListening={isListening} voiceStatusText={voiceStatusText}
              source={source} setSource={setSource}
              model={model} setModel={setModel} aiModels={aiModels}
              onSend={sendMessage} onStartVoiceInput={startVoiceInput}
              tr={tr}
              fileInputRef={fileInputRef}
              onFileUpload={handleFileUpload}
              uploadedFiles={uploadedFiles}
              setUploadedFiles={setUploadedFiles}
              onRemoveUploadedFile={removeUploadedFile}
            />
          </>
        )}
      </div>

      {!conversationActive && weatherInfo?.temperature_display && (
        <div className="weather-mini-widget weather-mini-widget--landing"
          title={weatherInfo.summary || weatherInfo.description || 'Lokales Wetter'}>
          {renderWeatherMiniIcon(weatherInfo.icon)}
          <span className="weather-mini-temp">{weatherInfo.temperature_display}</span>
        </div>
      )}

      <PhotoPreviewModal photoPreview={photoPreview} onClose={closePhotoPreview} />

      <ChatSummaryModal
        summaryPanel={chatSummaryPanel}
        onClose={() => setChatSummaryPanel((prev) => ({ ...prev, open: false }))}
        onRegenerate={() => summarizeChat(chatSummaryPanel.chatId, { force: true })}
        markdownComponents={markdownComponents}
        handleMarkdownContentClick={handleMarkdownContentClick}
        tr={tr}
      />

      {projectModalOpen && (
        <div className="overlay" onClick={() => { setProjectModalOpen(false); }}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{maxWidth: '440px'}}>
            <div className="modal-head">
              <h2>{tr('Projekte', 'Projects')}</h2>
              <button className="modal-x" onClick={() => { setProjectModalOpen(false); }}>&times;</button>
            </div>
            <div className="modal-body">
              <div className="modal-inline-form">
                <input type="text" placeholder={tr('Neues Projekt...', 'New project...')}
                  onKeyDown={(e) => { if (e.key === 'Enter' && e.target.value.trim()) { setProjects(prev => [...prev, { id: Date.now().toString(), name: e.target.value.trim() }]); e.target.value = ''; }}} />
                <button className="modal-inline-btn" onClick={(e) => { const inp = e.target.parentElement.querySelector('input'); if (inp.value.trim()) { setProjects(prev => [...prev, { id: Date.now().toString(), name: inp.value.trim() }]); inp.value = ''; }}}>{tr('Anlegen', 'Create')}</button>
              </div>
              {projects.length === 0 ? (
                <div className="modal-empty"><i className="fas fa-folder-open"></i><p>{tr('Noch keine Projekte.', 'No projects yet.')}</p></div>
              ) : (
                <div className="modal-list">
                  {projects.map(p => (
                    <div key={p.id} className={`modal-list-item ${activeProject === p.id ? 'active' : ''}`}>
                      <div className="modal-list-item-main" onClick={() => { setActiveProject(activeProject === p.id ? null : p.id); setProjectModalOpen(false); }}>
                        <i className="fas fa-folder"></i>
                        <span className="modal-list-item-label">{p.name}</span>
                        <span className="modal-list-item-count">{chats.filter(c => c.project === p.id).length}</span>
                      </div>
                      <div className="modal-list-item-acts">
                        <button className="modal-list-act" onClick={() => { const name = window.prompt(tr('Neuer Name:', 'New name:'), p.name); if (name && name.trim()) { setProjects(prev => prev.map(pp => pp.id === p.id ? { ...pp, name: name.trim() } : pp)); }}} title={tr('Umbenennen', 'Rename')}><i className="fas fa-pen"></i></button>
                        <button className="modal-list-act del" onClick={() => { if (window.confirm(tr(`Projekt "${p.name}" löschen?`, `Delete project "${p.name}"?`))) { setProjects(prev => prev.filter(pp => pp.id !== p.id)); setChats(prev => prev.map(c => c.project === p.id ? { ...c, project: null } : c)); if (activeProject === p.id) setActiveProject(null); }}} title={tr('Löschen', 'Delete')}><i className="fas fa-trash"></i></button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {activeProject && (
                <div className="modal-clear-filter" onClick={() => { setActiveProject(null); setProjectModalOpen(false); }}>
                  <i className="fas fa-times-circle"></i> {tr('Filter aufheben', 'Clear filter')}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
      {pendingUserInput && (
        <div className="modal-overlay" onClick={() => setPendingUserInput(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{maxWidth: '520px'}}>
            <div className="modal-head">
              <strong>{tr('Frage der KI', 'AI Question')}</strong>
              <button className="modal-x" onClick={() => { setPendingUserInput(null); setPendingUserInputValue(''); }}>&times;</button>
            </div>
            <div className="modal-body" style={{padding: '20px'}}>
              <p style={{marginBottom: '16px', color: '#ccc', fontSize: '1.05em', lineHeight: 1.5}}>
                {pendingUserInput.message}
              </p>
              <textarea
                value={pendingUserInputValue}
                onChange={(e) => setPendingUserInputValue(e.target.value)}
                placeholder={tr('Deine Antwort...', 'Your answer...')}
                rows={3}
                style={{width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #444', background: '#222', color: '#eee', fontSize: '0.95em', resize: 'vertical', marginBottom: '12px', boxSizing: 'border-box'}}
              />
              <div style={{display: 'flex', gap: '10px', justifyContent: 'flex-end'}}>
                <button className="btn btn-secondary" onClick={() => { setPendingUserInput(null); setPendingUserInputValue(''); }}>
                  {tr('Abbrechen', 'Cancel')}
                </button>
                <button className="btn btn-primary" disabled={!pendingUserInputValue.trim()} onClick={async () => {
                  const input = pendingUserInputValue.trim();
                  setPendingUserInputValue('');
                  setPendingUserInput(null);
                  updateMessageInChat(pendingUserInput.chatId, pendingUserInput.messageId, (msg) => ({
                    ...msg,
                    content: (msg.content || '') + `\n\n⚠️ **KI fragt:** ${pendingUserInput.message}\n👤 **Antwort:** ${input}`,
                  }));
                  try {
                    const res = await apiFetch('/api/agent/input', {
                      method: 'POST',
                      headers: {'Content-Type': 'application/json'},
                      body: JSON.stringify({ input })
                    });
                    const data = await res.json();
                    if (data.success && data.response) {
                      let r = data.response;
                      const imgs = (r.match(/!\[.*?\]\(.*?\)/g) || []).length;
                      updateMessageInChat(pendingUserInput.chatId, pendingUserInput.messageId, (msg) => ({
                        ...msg,
                        content: r,
                        streamTrace: [...(msg.streamTrace || [])]
                      }));
                    } else {
                      updateMessageInChat(pendingUserInput.chatId, pendingUserInput.messageId, (msg) => ({
                        ...msg,
                        content: msg.content + `\n\n❌ Fehler: ${data.error || 'Unbekannter Fehler'}`
                      }));
                    }
                  } catch (e) {
                    updateMessageInChat(pendingUserInput.chatId, pendingUserInput.messageId, (msg) => ({
                      ...msg,
                      content: msg.content + `\n\n❌ Fehler: ${e.message}`
                    }));
                  }
                }}>
                  <i className="fas fa-paper-plane"></i> {tr('Antworten', 'Respond')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
      {pendingToolConfirm && (
        <div className="modal-overlay" onClick={() => setPendingToolConfirm(null)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{maxWidth: '480px'}}>
            <div className="modal-head">
              <strong>{tr('Tool-Bestätigung', 'Tool Confirmation')}</strong>
              <button className="modal-x" onClick={() => setPendingToolConfirm(null)}>&times;</button>
            </div>
            <div className="modal-body" style={{padding: '20px'}}>
              <p style={{marginBottom: '12px', color: '#e8a040'}}>
                <i className="fas fa-shield-halved"></i>{' '}
                <strong>{pendingToolConfirm.tool}</strong>: {pendingToolConfirm.description}
              </p>
              <p style={{fontSize: '0.9em', color: '#999', marginBottom: '20px'}}>
                {tr('Möchtest du die Ausführung dieses Tools erlauben?', 'Do you want to allow executing this tool?')}
              </p>
              <div style={{display: 'flex', gap: '10px', justifyContent: 'flex-end'}}>
                <button className="btn btn-secondary" onClick={() => setPendingToolConfirm(null)}>
                  {tr('Ablehnen', 'Deny')}
                </button>
                <button className="btn btn-primary" onClick={async () => {
                  const toolInfo = pendingToolConfirm;
                  setPendingToolConfirm(null);
                  try {
                    const res = await apiFetch('/api/tool/run', {
                      method: 'POST',
                      headers: {'Content-Type': 'application/json'},
                      body: JSON.stringify({ confirmed: true })
                    });
                    const data = await res.json();
                    if (data.success) {
                      insertMessageAfter(targetChatId, userMessageId, {
                        role: 'assistant',
                        content: `✅ Tool ausgeführt:\n\`\`\`\n${data.result}\n\`\`\``,
                        id: createMessageId()
                      });
                    } else {
                      insertMessageAfter(targetChatId, userMessageId, {
                        role: 'assistant',
                        content: `❌ Fehler: ${data.error}`,
                        id: createMessageId()
                      });
                    }
                  } catch (e) {
                    console.error('Tool confirm error:', e);
                  }
                }}>
                  <i className="fas fa-check"></i> {tr('Erlauben', 'Allow')}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
