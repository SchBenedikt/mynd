'use client';

import { useEffect, useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import SourceCard from '../components/SourceCard';
import SuggestionsPanel from '../components/SuggestionsPanel';
import { useTheme } from '../hooks/useTheme';
import { useLanguage } from '../hooks/useLanguage';

const API_BASE = '';
const CHAT_STORAGE_KEY = 'mynd_chat_history_v1';
const ACTIVE_CHAT_STORAGE_KEY = 'mynd_active_chat_v1';
const SIDEBAR_COLLAPSED_KEY = 'mynd_sidebar_collapsed_v1';
const DISPLAY_NAME_STORAGE_KEY = 'mynd_display_name';
const LOCATION_AUTO_RESOLVE_KEY = 'mynd_location_auto_resolve_v1';

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

const THEME_LABEL_KEY = {
  classic: 'Classic',
  ocean: 'Ocean',
  graphite: 'Graphite',
  lavender: 'Lavender',
  rose: 'Rose',
  gold: 'Gold'
};

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

const createEmptyChat = () => {
  const now = Date.now();
  return {
    id: createChatId(),
    title: 'Neuer Chat',
    messages: [],
    createdAt: now,
    updatedAt: now
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

export default function HomePage() {
  const router = useRouter();
  const { theme, setTheme, setDarkMode } = useTheme();
  const { language, setLanguage, t, languages } = useLanguage();
  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(true);
  const [isThinking, setIsThinking] = useState(false);
  const [pendingQueue, setPendingQueue] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [source, setSource] = useState('auto');
  const [health, setHealth] = useState({ ollama: 'unknown', kb: 'unknown' });
  const [securityStatus, setSecurityStatus] = useState(null);
  const [securityLoading, setSecurityLoading] = useState(false);
  const [displayName, setDisplayName] = useState('');
  const [, setGreetingTick] = useState(0);
  
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
  const [photoPreview, setPhotoPreview] = useState({
    open: false,
    title: '',
    thumbnailUrl: '',
    immichUrl: '',
    downloadUrl: ''
  });
  const progressIntervalRef = useRef(null);
  const requestAbortRef = useRef(null);
  
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const activeChat = chats.find((chat) => chat.id === activeChatId) || null;
  const messages = activeChat?.messages || [];
  const conversationActive = messages.length > 0;
  const weatherInfo = securityStatus?.weather || null;

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

  const pickGreeting = (segment, name) => {
    const suffix = name ? `, ${name}` : '';
    const greetings = {
      de: {
        morning: [
          'Guten Morgen',
          'Guten Morgen! Bereit fuer den Tag',
          'Was liegt dir am Morgen auf dem Herzen'
        ],
        afternoon: [
          'Guten Tag',
          'Wie laeuft dein Tag',
          'Was kann ich fuer dich tun'
        ],
        evening: [
          'Guten Abend',
          'Wie war dein Tag',
          'Was liegt dir auf dem Herzen'
        ],
        night: [
          'Noch wach',
          'Was brauchst du noch heute',
          'Wie kann ich dir helfen'
        ]
      },
      en: {
        morning: ['Good morning', 'Morning! Ready for the day', "What's on your mind this morning"],
        afternoon: ['Good afternoon', 'How is your day going', 'What can I do for you'],
        evening: ['Good evening', 'How was your day', "What's on your mind"],
        night: ['Still up', 'What do you need today', 'How can I help']
      }
    };

    const list = (greetings[language] || greetings.en)[segment] || greetings.en.morning;
    const seed = Math.floor(Date.now() / (1000 * 60 * 15));
    const base = list[seed % list.length];
    const full = `${base}${suffix}`;
    const needsQuestion = /\b(was|wie|noch wach|what|how|still up)\b/i.test(base);
    if (needsQuestion && !/[?!]$/.test(full)) {
      return `${full}?`;
    }
    return full;
  };

  const getTimeSegment = () => {
    const hour = new Date().getHours();
    if (hour >= 5 && hour < 12) return 'morning';
    if (hour >= 12 && hour < 17) return 'afternoon';
    if (hour >= 17 && hour < 22) return 'evening';
    return 'night';
  };

  const personalGreeting = pickGreeting(getTimeSegment(), displayName);

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

  const handleUiControlCommand = (text, targetChatId) => {
    const normalized = normalizeText(text);
    const languageTarget = detectLanguageTarget(normalized);
    const themeTarget = detectMappedValue(normalized, THEME_COMMANDS);
    const modeTarget = detectMappedValue(normalized, MODE_COMMANDS);

    const hasControlIntent = /sprache|language|theme|farbe|color|modus|mode|design|blau|blue|deutsch|englisch/.test(normalized);
    if (!hasControlIntent && !languageTarget && !themeTarget && !modeTarget) {
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

    if (!confirmations.length) {
      return false;
    }

    appendMessageToChat(targetChatId, {
      role: 'assistant',
      content: confirmations.join('\n'),
      id: createMessageId()
    });

    return true;
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (!isThinking && pendingQueue.length > 0) {
      processNextQueued();
    }
  }, [isThinking, pendingQueue]);

  useEffect(() => {
    loadAIConfig();
    loadOllamaModels();
    updateStatus();
    loadSecurityStatus();
    autoResolveLocationOnOpen();
    
    const statusInterval = setInterval(updateStatus, 8000);
    const securityInterval = setInterval(loadSecurityStatus, 60000);
    return () => {
      clearInterval(statusInterval);
      clearInterval(securityInterval);
    };
  }, []);

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
          await fetch(`${API_BASE}/api/location/resolve`, {
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
      if (rawDisplayName) {
        setDisplayName(rawDisplayName);
      }

      const rawChats = localStorage.getItem(CHAT_STORAGE_KEY);
      const rawActiveChatId = localStorage.getItem(ACTIVE_CHAT_STORAGE_KEY);
      const rawSidebarCollapsed = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);

      if (rawSidebarCollapsed === 'true' || rawSidebarCollapsed === 'false') {
        setIsSidebarCollapsed(rawSidebarCollapsed === 'true');
      }

      if (rawChats) {
        const parsedChats = JSON.parse(rawChats);
        if (Array.isArray(parsedChats) && parsedChats.length > 0) {
          setChats(parsedChats);
          const activeExists = parsedChats.some((chat) => chat.id === rawActiveChatId);
          setActiveChatId(activeExists ? rawActiveChatId : parsedChats[0].id);
          return;
        }
      }
    } catch (err) {
      console.error('Error loading chat history:', err);
    }

    const initialChat = createEmptyChat();
    setChats([initialChat]);
    setActiveChatId(initialChat.id);
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      setGreetingTick(Date.now());
    }, 15 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!chats.length || !activeChatId) return;
    try {
      localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(chats));
      localStorage.setItem(ACTIVE_CHAT_STORAGE_KEY, activeChatId);
    } catch (err) {
      console.error('Error saving chat history:', err);
    }
  }, [chats, activeChatId]);

  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(isSidebarCollapsed));
    } catch (err) {
      console.error('Error saving sidebar state:', err);
    }
  }, [isSidebarCollapsed]);

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
      const res = await fetch(`${API_BASE}/api/ai/config`);
      const config = await safeReadJson(res);
      if (!res.ok || !config?.base_url) {
        throw new Error(config?.error || `Request failed with status ${res.status}`);
      }
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
      const data = await safeReadJson(res);
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
      const ollama = await safeReadJson(ollamaRes);
      const kb = await safeReadJson(kbRes);
      setHealth({
        ollama: ollama.connected ? 'ok' : 'error',
        kb: kb.chunks_loaded > 0 ? 'ok' : 'error'
      });
    } catch (err) {
      setHealth({ ollama: 'error', kb: 'error' });
    }
  };

  const loadSecurityStatus = async () => {
    try {
      setSecurityLoading(true);
      const res = await fetch(`${API_BASE}/api/security/status`);
      const data = await safeReadJson(res);
      if (!res.ok || data?.success === false) {
        setSecurityStatus({
          headline: 'Sicherheitslage aktuell nicht verfuegbar',
          nina_warning_count: 0,
          nina_warnings: []
        });
        return;
      }
      setSecurityStatus(data);
    } catch (err) {
      setSecurityStatus({
        headline: 'Sicherheitslage aktuell nicht verfuegbar',
        nina_warning_count: 0,
        nina_warnings: []
      });
    } finally {
      setSecurityLoading(false);
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

  const queueMessage = (text, chatId) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    const messageId = createMessageId();
    appendMessageToChat(chatId, { role: 'user', content: trimmed, id: messageId, queued: true }, trimmed);
    setPendingQueue((prev) => [...prev, { chatId, text: trimmed, messageId }]);
    setInputValue('');
    if (inputRef.current) inputRef.current.value = '';
  };

  const processNextQueued = () => {
    if (pendingQueue.length === 0) return;
    const [next, ...rest] = pendingQueue;
    setPendingQueue(rest);
    sendMessage(next.text, { fromQueue: true, chatId: next.chatId, messageId: next.messageId });
  };

  const sendMessage = async (text, options = {}) => {
    if (!text.trim()) return;
    if (isThinking && !options.fromQueue) {
      const targetId = activeChatId || createEmptyChat().id;
      if (!activeChatId) {
        const newChat = createEmptyChat();
        setChats([newChat]);
        setActiveChatId(newChat.id);
        queueMessage(text, newChat.id);
        return;
      }
      queueMessage(text, targetId);
      return;
    }
    text = text.trim();
    setIsSidebarCollapsed(false);

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

      const res = await fetch(`${API_BASE}/api/agent/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: abortController.signal,
        body: JSON.stringify({
          prompt: text,
          language,
          preferred_source: source,
          context: conversationContext
        })
      });
      const data = await safeReadJson(res);
      if (!res.ok || data?.success === false) {
        const errorMessage = data?.error || `Request failed with status ${res.status}`;
        insertMessageAfter(targetChatId, userMessageId, {
          role: 'assistant',
          content: `Error: ${errorMessage}`,
          id: createMessageId()
        });
        return;
      }

      insertMessageAfter(targetChatId, userMessageId, {
        role: 'assistant',
        content: data.response,
        sources: data.sources || [],
        id: createMessageId()
      });

      if (data?.requires_input && data?.action === 'calendar_missing_input') {
        const extracted = data?.extracted_info || {};
        let calendars = data?.available_calendars || [];

        if (!calendars.length) {
          try {
            const calendarsRes = await fetch(`${API_BASE}/api/calendar/calendars`);
            const calendarsData = await safeReadJson(calendarsRes);
            calendars = calendarsData?.calendars || [];
          } catch (err) {
            console.error('Error loading calendars for form:', err);
          }
        }

        const prefilledCalendarName = extracted.calendar_name
          || calendars.find((c) => (c?.name || '').toLowerCase().includes((extracted.calendar_name || '').toLowerCase()))?.name
          || calendars[0]?.name
          || '';

        setCalendarForm({
          visible: true,
          missingInfo: data?.missing_info || [],
          title: extracted.title || '',
          startTime: parseBackendDateTimeToInput(extracted.start_time),
          endTime: parseBackendDateTimeToInput(extracted.end_time),
          calendarName: prefilledCalendarName,
          location: extracted.location || '',
          description: text,
          availableCalendars: calendars,
          submitting: false,
          error: ''
        });
      }
    } catch (err) {
      if (err?.name === 'AbortError') {
        return;
      }
      insertMessageAfter(targetChatId, userMessageId, {
        role: 'assistant',
        content: `Error: ${err.message}`,
        id: createMessageId()
      });
    } finally {
      setIsThinking(false);
      requestAbortRef.current = null;
    }
  };

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

  const getImageDownloadUrl = (thumbnailUrl, fallbackUrl = '') => {
    if (!thumbnailUrl) return fallbackUrl;

    try {
      const parsedUrl = new URL(thumbnailUrl, window.location.origin);
      const assetMatch = parsedUrl.pathname.match(/\/api\/immich\/thumbnail\/([^/?#]+)/);
      const assetId = assetMatch?.[1];

      if (!assetId) return fallbackUrl;

      const params = new URLSearchParams();
      const username = parsedUrl.searchParams.get('username');
      if (username) {
        params.set('username', username);
      }

      const query = params.toString();
      return `${API_BASE}/api/immich/download/${assetId}${query ? `?${query}` : ''}`;
    } catch (_) {
      return fallbackUrl;
    }
  };

  const openPhotoPreview = ({ title = 'Vorschau', thumbnailUrl = '', immichUrl = '' }) => {
    setPhotoPreview({
      open: true,
      title,
      thumbnailUrl,
      immichUrl,
      downloadUrl: getImageDownloadUrl(thumbnailUrl, immichUrl)
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
    const immichUrl = anchorElement?.getAttribute('href') || '';

    event.preventDefault();
    event.stopPropagation();

    openPhotoPreview({ title, thumbnailUrl, immichUrl });
  };

  const markdownComponents = {
    p: ({ node, children, ...props }) => {
      const hasOnlyImageLink =
        node?.children?.length === 1
        && node.children[0]?.type === 'link'
        && node.children[0]?.children?.length === 1
        && node.children[0].children[0]?.type === 'image';

      const hasOnlyImage =
        node?.children?.length === 1
        && node.children[0]?.type === 'image';

      const className = hasOnlyImageLink || hasOnlyImage
        ? 'markdown-image-paragraph'
        : undefined;

      return (
        <p className={className} {...props}>
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
    )
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

      const res = await fetch(`${API_BASE}/api/calendar/create-with-details`, {
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

  const startNewChat = () => {
    const newChat = createEmptyChat();
    setChats((prev) => [newChat, ...prev]);
    setActiveChatId(newChat.id);
    resetCalendarForm();
  };

  const openChat = (chatId) => {
    setActiveChatId(chatId);
    resetCalendarForm();
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

  const sortedChats = [...chats].sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));

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

  const groupedChats = sortedChats.reduce((groups, chat) => {
    const label = getChatGroupLabel(chat);
    const lastGroup = groups[groups.length - 1];
    if (!lastGroup || lastGroup.label !== label) {
      groups.push({ label, items: [chat] });
    } else {
      lastGroup.items.push(chat);
    }
    return groups;
  }, []);

  const goToSettings = () => {
    router.push('/settings');
  };

  const canSend = inputValue.trim().length > 0;
  const queueReady = isThinking && canSend;

  return (
    <div className={`container ${isSidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
      {/* LEFT SIDEBAR */}
      <div className={`left-sidebar ${isSidebarCollapsed ? 'collapsed' : ''}`}>
        <div className="sidebar-header">
          <button
            type="button"
            className="brand brand-button"
            onClick={startNewChat}
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
          <button className="new-chat-btn" onClick={startNewChat} title={t('newChat')}>
            <i className="fas fa-plus"></i>
            {t('newChat')}
          </button>
        )}
        <div className="chat-history">
          {isSidebarCollapsed ? (
            <button
              type="button"
              className="history-item active"
              onClick={() => setIsSidebarCollapsed(false)}
              title={t('currentChat')}
            >
              <i className="fas fa-message"></i>
            </button>
          ) : (
            groupedChats.map((group, groupIndex) => (
              <div key={`${group.label}-${groupIndex}`} className="history-group">
                <div className="history-group-label">{group.label}</div>
                {group.items.map((chat) => (
                  <div
                    key={chat.id}
                    className={`history-item ${chat.id === activeChatId ? 'active' : ''}`}
                    onClick={() => openChat(chat.id)}
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault();
                        openChat(chat.id);
                      }
                    }}
                    role="button"
                    tabIndex={0}
                    title={chat.title}
                  >
                    <i className="fas fa-message"></i>
                    <span className="history-title">{chat.title}</span>
                    <div className="history-actions">
                      <button
                        type="button"
                        className="history-action"
                        onClick={(event) => {
                          event.stopPropagation();
                          renameChat(chat.id);
                        }}
                        title="Umbenennen"
                      >
                        <i className="fas fa-pen"></i>
                      </button>
                      <button
                        type="button"
                        className="history-action danger"
                        onClick={(event) => {
                          event.stopPropagation();
                          deleteChat(chat.id);
                        }}
                        title="Loeschen"
                      >
                        <i className="fas fa-trash"></i>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            ))
          )}
        </div>
        <div className="sidebar-footer">
          <button
            className="new-chat-btn settings-btn"
            onClick={goToSettings}
            title={t('settings')}
          >
            <i className="fas fa-cog"></i>
            {!isSidebarCollapsed && t('settings')}
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

      {/* CENTER - Chat */}
      <div className="center-area">
        {(securityStatus?.nina_warning_count || 0) > 0 && (
          <div className="security-banner alert">
            <div className="security-banner-header">
              <div className="security-banner-title">
                <i className="fas fa-triangle-exclamation"></i>
                <span>{securityStatus?.headline || 'Aktive Warnungen erkannt'}</span>
              </div>
              <button
                type="button"
                className="security-refresh"
                onClick={loadSecurityStatus}
                disabled={securityLoading}
                title="Sicherheitslage aktualisieren"
              >
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

        {!conversationActive ? (
          <div className="landing">
            <div className="landing-header">
              <h2>{personalGreeting}</h2>
              <p>{t('askSubheading')}</p>
            </div>
            <div className="input-wrapper">
              <input
                type="text" 
                ref={inputRef}
                value={inputValue}
                placeholder={t('askPlaceholder')}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && sendMessage(e.target.value)}
              />
              <button
                onClick={() => sendMessage(inputRef.current?.value || '')}
                disabled={!canSend}
                className={queueReady ? 'queue-ready' : ''}
                title={queueReady ? 'In die Warteschlange' : undefined}
              >
                <i className={`fas ${queueReady ? 'fa-arrow-up' : 'fa-arrow-right'}`}></i>
                {queueReady && <span className="queue-tooltip">In die Warteschlange</span>}
              </button>
            </div>

            {/* Query Suggestions Panel */}
            <SuggestionsPanel
              language={language}
              username="default"
              chatHistory={chats}
              onSuggestionClick={(suggestion) => {
                if (inputRef.current) {
                  inputRef.current.value = suggestion;
                  setInputValue(suggestion);
                  sendMessage(suggestion);
                }
              }}
              t={t}
            />

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
                    {t('documentIndexing')}
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
                      <strong>{t('current')}:</strong> {indexingDetails.currentFile}
                    </div>
                  )}
                  
                  <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.75rem'}}>
                    <div><strong>{t('files')}:</strong> {indexingDetails.processedFiles}/{indexingDetails.totalFiles}</div>
                    <div><strong>{t('speed')}:</strong> {indexingDetails.processingSpeed} files/s</div>
                    <div><strong>{t('elapsed')}:</strong> {indexingDetails.elapsedTime}s</div>
                    <div><strong>{t('chunks')}:</strong> ~{indexingDetails.chunksCreated}</div>
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
                      <strong>{t('errors')}:</strong> {indexingDetails.errors.length}
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
                  <div key={msg.id} className={`message ${msg.role} ${msg.queued ? 'queued' : ''}`}>
                    <div className="bubble">
                      {msg.role === 'assistant' ? (
                        <div onClickCapture={handleMarkdownContentClick}>
                          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                            {msg.content}
                          </ReactMarkdown>
                        </div>
                      ) : (
                        msg.content
                      )}
                    </div>
                    {msg.role === 'user' && msg.queued && (
                      <div className="queued-tag">In der Warteschlange</div>
                    )}
                    {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
                      <div className="sources-container">
                        <div className="sources-header">
                          <i className="fas fa-link"></i>
                          <span>{t('sources')} ({msg.sources.length})</span>
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

                {calendarForm.visible && (
                  <div className="message assistant">
                    <div className="bubble calendar-form-bubble">
                      <h4>Termin erstellen</h4>
                      {calendarForm.missingInfo.length > 0 && (
                        <p className="calendar-form-hint">
                          Bitte ergaenze: {calendarForm.missingInfo.join(', ')}
                        </p>
                      )}
                      <form className="calendar-form" onSubmit={submitCalendarForm}>
                        <label>
                          Titel
                          <input
                            type="text"
                            value={calendarForm.title}
                            onChange={(e) => setCalendarForm(prev => ({ ...prev, title: e.target.value }))}
                            placeholder="z.B. Team Meeting"
                            required
                          />
                        </label>

                        <label>
                          Startzeit
                          <input
                            type="datetime-local"
                            value={calendarForm.startTime}
                            onChange={(e) => setCalendarForm(prev => ({ ...prev, startTime: e.target.value }))}
                            required
                          />
                        </label>

                        <label>
                          Endzeit (optional)
                          <input
                            type="datetime-local"
                            value={calendarForm.endTime}
                            onChange={(e) => setCalendarForm(prev => ({ ...prev, endTime: e.target.value }))}
                          />
                        </label>

                        {calendarForm.availableCalendars.length > 0 && (
                          <label>
                            Kalender
                            <select
                              value={calendarForm.calendarName}
                              onChange={(e) => setCalendarForm(prev => ({ ...prev, calendarName: e.target.value }))}
                            >
                              {calendarForm.availableCalendars.map((cal) => (
                                <option key={cal.name} value={cal.name}>{cal.name}</option>
                              ))}
                            </select>
                          </label>
                        )}

                        <label>
                          Ort (optional)
                          <input
                            type="text"
                            value={calendarForm.location}
                            onChange={(e) => setCalendarForm(prev => ({ ...prev, location: e.target.value }))}
                            placeholder="z.B. Berlin oder Zoom"
                          />
                        </label>

                        {calendarForm.error && <p className="calendar-form-error">{calendarForm.error}</p>}

                        <div className="calendar-form-actions">
                          <button type="button" className="btn" onClick={closeCalendarForm} disabled={calendarForm.submitting}>
                            Abbrechen
                          </button>
                          <button type="submit" className="btn primary" disabled={calendarForm.submitting}>
                            {calendarForm.submitting ? t('saveEvent') : t('createEvent')}
                          </button>
                        </div>
                      </form>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            </div>
            <div className="composer-shell">
              {isThinking && (
                <div className="composer-hint">Anfrage läuft · Strg+C zum Abbrechen</div>
              )}
              <div className={`composer ${isThinking ? 'is-thinking' : ''}`}>
                <input 
                  type="text" 
                  ref={inputRef}
                  value={inputValue}
                  placeholder={t('composerPlaceholder')}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && !e.ctrlKey && sendMessage(e.target.value)}
                />
                <button
                  onClick={() => sendMessage(inputRef.current?.value || '')}
                  disabled={!canSend}
                  className={queueReady ? 'queue-ready' : ''}
                  title={queueReady ? 'In die Warteschlange' : undefined}
                >
                  <i className={`fas ${queueReady ? 'fa-arrow-up' : 'fa-arrow-right'}`}></i>
                  {queueReady && <span className="queue-tooltip">In die Warteschlange</span>}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
      {weatherInfo?.success && weatherInfo?.temperature_display && (
        <div className="weather-mini-widget" title={weatherInfo.description || 'Lokales Wetter'}>
          {renderWeatherMiniIcon(weatherInfo.icon)}
          <span className="weather-mini-temp">{weatherInfo.temperature_display}</span>
        </div>
      )}
      {photoPreview.open && (
        <div className="image-modal-overlay" onClick={closePhotoPreview}>
          <div className="image-modal" onClick={(e) => e.stopPropagation()}>
            <button
              type="button"
              className="image-modal-close"
              onClick={closePhotoPreview}
              aria-label="Vorschau schliessen"
            >
              ×
            </button>
            <div className="image-modal-title">{photoPreview.title || 'Vorschau'}</div>
            <img
              src={photoPreview.thumbnailUrl}
              alt={photoPreview.title || 'Vorschau'}
              className="image-modal-preview"
              loading="lazy"
            />
            <div className="image-modal-actions">
              {photoPreview.downloadUrl && (
                <a className="btn primary" href={photoPreview.downloadUrl}>
                  Original herunterladen
                </a>
              )}
              {photoPreview.immichUrl && (
                <a className="btn" href={photoPreview.immichUrl} target="_blank" rel="noopener noreferrer">
                  In Immich oeffnen
                </a>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
