'use client';

import { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { useTheme } from '../../hooks/useTheme';
import { useLanguage } from '../../hooks/useLanguage';
import { useApp } from '../../lib/AppContext';
import { useVoice } from '../../hooks/useVoice';
import { useForms } from '../../hooks/useForms';
import LandingScreen from '../../components/LandingScreen';
import MessageList from '../../components/MessageList';
import Composer from '../../components/Composer';
import PhotoPreviewModal from '../../components/PhotoPreviewModal';
import ChatSummaryModal from '../../components/ChatSummaryModal';
import { apiFetch, getApiBase } from '../../lib/api';
import { isChatModel, uniqueSortedModels } from '../../lib/modelUtils';
import {
  CHAT_STORAGE_KEY, ACTIVE_CHAT_STORAGE_KEY, DISPLAY_NAME_STORAGE_KEY,
  BRIEFING_SEEN_KEY, TTS_PROVIDER_STORAGE_KEY, LOCATION_AUTO_RESOLVE_KEY,
  createChatId, createMessageId, createEmptyChat, buildChatTitleFromText,
  safeReadJson, buildFriendlyChatErrorMessage, getTodayDateTimeForInputs,
  normalizeTtsProvider, LANGUAGE_COMMANDS, THEME_COMMANDS, MODE_COMMANDS,
  NAMED_COLOR_COMMANDS, THEME_LABEL_KEY, DESIGN_COLOR_PRESETS
} from '../../lib/pageUtils';

export default function HomePage() {
  const router = useRouter();
  const { theme, darkMode, contrastColor, setTheme, setDarkMode, setContrastColor } = useTheme();
  const { language, setLanguage, t, languages } = useLanguage();
  const tr = useCallback((deText, enText) => (language === 'de' ? deText : enText), [language]);
  const { chats, setChats, activeChatId, setActiveChatId, user, setUser, health, setHealth, projects, setProjects, activeProject, setActiveProject } = useApp();

  const sendMessageRef = useRef(null);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  const progressIntervalRef = useRef(null);
  const requestAbortRef = useRef(null);

  const voice = useVoice({ language, onTranscriptRef: sendMessageRef });

  const [aiProtocol, setAiProtocol] = useState('http');
  const [aiHost, setAiHost] = useState('127.0.0.1');
  const [aiPort, setAiPort] = useState('11434');
  const [aiModel, setAiModel] = useState('');
  const [aiModels, setAiModels] = useState([]);
  const [model, setModel] = useState('');
  const [aiStatus, setAiStatus] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [personalGreeting, setPersonalGreeting] = useState('');

  const [securityStatus, setSecurityStatus] = useState(null);
  const [securityLoading, setSecurityLoading] = useState(false);
  const [proactiveBriefings, setProactiveBriefings] = useState([]);
  const [indexingProgress, setIndexingProgress] = useState(0);
  const [indexingStatus, setIndexingStatus] = useState('idle');
  const [indexingStats, setIndexingStats] = useState('');
  const [indexingDetails, setIndexingDetails] = useState({
    currentFile: '', processedFiles: 0, totalFiles: 0, elapsedTime: 0,
    errors: [], chunksCreated: 0, documentsProcessed: 0, processingSpeed: 0,
    lastIndexingStart: 0, lastIndexingEnd: 0, lastIndexingDuration: 0
  });

  const [searchQuery, setSearchQuery] = useState('');
  const [projectModalOpen, setProjectModalOpen] = useState(false);
  const [, setGreetingTick] = useState(0);
  const [liveTools, setLiveTools] = useState({});
  const [source, setSource] = useState('auto');

  const [inputValue, setInputValue] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [pendingQueue, setPendingQueue] = useState([]);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const fileInputRef = useRef(null);
  const [pendingToolConfirm, setPendingToolConfirm] = useState(null);
  const [pendingUserInput, setPendingUserInput] = useState(null);
  const [pendingUserInputValue, setPendingUserInputValue] = useState('');

  const [photoPreview, setPhotoPreview] = useState({
    open: false, title: '', thumbnailUrl: '', immichUrl: '', sourceUrl: '', downloadUrl: ''
  });
  const [chatSummaryPanel, setChatSummaryPanel] = useState({
    open: false, chatId: '', title: '', summary: '', generatedAt: 0,
    messageCount: 0, stats: { total: 0, user: 0, assistant: 0 }, loading: false, error: ''
  });

  const activeChat = chats.find((chat) => chat.id === activeChatId) || null;
  const messages = activeChat?.messages || [];
  const conversationActive = messages.length > 0;
  const weatherInfo = securityStatus?.weather || null;

  const languageLabel = useCallback((code) => languages.find((l) => l.code === code)?.label || code, [languages]);

  const appendMessageToChat = useCallback((chatId, message, originalUserText = null) => {
    const now = Date.now();
    setChats((prevChats) => prevChats.map((chat) => {
      if (chat.id !== chatId) return chat;
      const nextMessages = [...(chat.messages || []), message];
      const shouldUpdateTitle = chat.title === 'Neuer Chat' && message.role === 'user' && originalUserText;
      return { ...chat, messages: nextMessages, title: shouldUpdateTitle ? buildChatTitleFromText(originalUserText) : chat.title, updatedAt: now };
    }));
  }, [setChats]);

  const updateMessageInChat = useCallback((chatId, messageId, updater) => {
    setChats((prevChats) => prevChats.map((chat) => {
      if (chat.id !== chatId) return chat;
      const nextMessages = (chat.messages || []).map((msg) => (msg.id !== messageId ? msg : updater(msg)));
      return { ...chat, messages: nextMessages };
    }));
  }, [setChats]);

  const insertMessageAfter = useCallback((chatId, afterMessageId, message) => {
    setChats((prevChats) => prevChats.map((chat) => {
      if (chat.id !== chatId) return chat;
      const messagesList = chat.messages || [];
      const index = messagesList.findIndex((msg) => msg.id === afterMessageId);
      if (index === -1) return { ...chat, messages: [...messagesList, message] };
      const nextMessages = [...messagesList];
      nextMessages.splice(index + 1, 0, message);
      return { ...chat, messages: nextMessages };
    }));
  }, [setChats]);

  const fetchUser = useCallback(async () => {
    try {
      const storedToken = localStorage.getItem('mynd_token_v1');
      if (!storedToken) return;
      const res = await apiFetch('/api/auth/me', { headers: { 'Authorization': `Bearer ${storedToken}` } });
      const data = await safeReadJson(res);
      if (res.ok && data && data.authenticated && data.user) setUser(data.user);
    } catch {}
  }, [setUser]);

  const fetchGreeting = useCallback(async () => {
    try {
      const res = await apiFetch('/api/ai/greeting', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language, name: displayName })
      });
      const data = await res.json();
      if (data.success && data.greeting) setPersonalGreeting(data.greeting);
    } catch {}
  }, [language, displayName]);

  const autoResolveLocationOnOpen = useCallback(async () => {
    if (typeof window === 'undefined' || !navigator.geolocation) return;
    try {
      const marker = sessionStorage.getItem(LOCATION_AUTO_RESOLVE_KEY);
      if (marker === 'done') return;
    } catch (err) { console.error('Could not read location auto-resolve marker:', err); }
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        try {
          await apiFetch('/api/location/resolve', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lat: position.coords.latitude, lon: position.coords.longitude, save: true })
          });
        } catch (err) { console.error('Automatic location resolve failed:', err); }
        finally {
          try { sessionStorage.setItem(LOCATION_AUTO_RESOLVE_KEY, 'done'); } catch (storageErr) { console.error('Could not persist location auto-resolve marker:', storageErr); }
          loadSecurityStatus();
        }
      },
      () => {
        try { sessionStorage.setItem(LOCATION_AUTO_RESOLVE_KEY, 'done'); } catch (storageErr) { console.error('Could not persist location auto-resolve marker:', storageErr); }
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
    );
  }, []);

  const normalizeText = useCallback((value) => String(value || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, ''), []);
  const detectMappedValue = useCallback((normalizedText, map) => {
    for (const [, keywords] of Object.entries(map)) {
      for (const keyword of keywords) {
        if (normalizedText.includes(keyword)) return true;
      }
    }
    return false;
  }, []);

  const detectLanguageTarget = useCallback((normalizedText) => {
    let bestMatch = null;
    let lastPos = -1;
    for (const [code, keywords] of Object.entries(LANGUAGE_COMMANDS)) {
      for (const keyword of keywords) {
        const pos = normalizedText.lastIndexOf(keyword);
        if (pos > lastPos) { lastPos = pos; bestMatch = code; }
      }
    }
    return bestMatch;
  }, []);

  const detectColorTarget = useCallback((normalizedText, originalText) => {
    const hexMatch = originalText.match(/#[0-9a-fA-F]{6}\b/);
    if (hexMatch) return hexMatch[0].toLowerCase();
    for (const [hex, keywords] of Object.entries(NAMED_COLOR_COMMANDS)) {
      for (const keyword of keywords) {
        if (normalizedText.includes(keyword)) return hex;
      }
    }
    return null;
  }, []);

  const handleUiControlCommand = useCallback((text, targetChatId) => {
    const normalized = normalizeText(text);
    const languageTarget = detectLanguageTarget(normalized);
    if (languageTarget && languageTarget !== language) {
      setLanguage(languageTarget);
      appendMessageToChat(targetChatId, { role: 'assistant', content: language === 'de' ? `Sprache auf ${languageTarget.toUpperCase()} gewechselt.` : `Switched language to ${languageTarget.toUpperCase()}.`, id: createMessageId() });
      return true;
    }
    if (detectMappedValue(normalized, THEME_COMMANDS)) {
      for (const [themeName, keywords] of Object.entries(THEME_COMMANDS)) {
        if (keywords.some(k => normalized.includes(k))) {
          setTheme(themeName);
          appendMessageToChat(targetChatId, { role: 'assistant', content: language === 'de' ? `Design auf ${THEME_LABEL_KEY[themeName] || themeName} gewechselt.` : `Switched theme to ${THEME_LABEL_KEY[themeName] || themeName}.`, id: createMessageId() });
          return true;
        }
      }
    }
    if (detectMappedValue(normalized, MODE_COMMANDS)) {
      for (const [mode, keywords] of Object.entries(MODE_COMMANDS)) {
        if (keywords.some(k => normalized.includes(k))) {
          setDarkMode(mode);
          appendMessageToChat(targetChatId, { role: 'assistant', content: language === 'de' ? `${mode === 'dark' ? 'Dunkelmodus' : mode === 'light' ? 'Hellmodus' : 'Automatischer Modus'} aktiviert.` : `${mode.charAt(0).toUpperCase() + mode.slice(1)} mode activated.`, id: createMessageId() });
          return true;
        }
      }
    }
    const colorTarget = detectColorTarget(normalized, text);
    if (colorTarget) {
      setContrastColor(colorTarget);
      appendMessageToChat(targetChatId, { role: 'assistant', content: language === 'de' ? `Akzentfarbe geaendert.` : `Accent color changed.`, id: createMessageId() });
      return true;
    }
    return false;
  }, [language, normalizeText, detectLanguageTarget, detectMappedValue, detectColorTarget, setLanguage, setTheme, setDarkMode, setContrastColor, appendMessageToChat]);

  const cancelPendingRequest = useCallback(() => {
    if (!requestAbortRef.current) return;
    requestAbortRef.current.abort();
    requestAbortRef.current = null;
    setIsThinking(false);
    if (activeChatId) {
      appendMessageToChat(activeChatId, { role: 'assistant', content: 'Anfrage abgebrochen.', id: createMessageId() });
    }
  }, [activeChatId, appendMessageToChat]);

  const sendMessage = useCallback(async (text, options = {}) => {
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
    if (handledByUIControl) return;
    setIsThinking(true);
    const abortController = new AbortController();
    requestAbortRef.current = abortController;
    try {
      const currentMessages = chats.find((chat) => chat.id === targetChatId)?.messages || [];
      const contextMessages = options.messageId ? currentMessages : [...currentMessages, { role: 'user', content: text, id: userMessageId }];
      const conversationContext = contextMessages.slice(-8).map((m) => `${m.role === 'user' ? 'User' : 'Assistant'}: ${m.content}`).join('\n');
      let emailConfig = null;
      try {
        const emailConfigRes = await apiFetch('/api/registry/email/config');
        const emailConfigData = await safeReadJson(emailConfigRes);
        if (emailConfigRes.ok && emailConfigData?.success !== false) emailConfig = emailConfigData?.config || null;
      } catch (err) { console.error('Error loading email config for chat:', err); }
      const res = await apiFetch('/api/agent/query/stream', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, signal: abortController.signal,
        body: JSON.stringify({
          prompt: uploadedFiles.length > 0
            ? `${text}\n\n\u{1F4CE} Angeh\u00e4ngte Dateien:\n${uploadedFiles.map((f, i) => `  ${i + 1}. [${f.filename}](${f.url}) (${(f.size / 1024).toFixed(0)} KB)`).join('\n')}\n\nBitte lies diese Dateien ein und verarbeite sie gem\u00e4\u00df meiner Anfrage.`
            : text,
          language, model: model, preferred_source: source,
          context: conversationContext, email_config: emailConfig,
          account_id: emailConfig?.active_account_id || emailConfig?.selected_account_id || emailConfig?.account_id || ''
        })
      });
      if (!res.ok) {
        const text_body = await res.text().catch(() => '');
        let err_data;
        try { err_data = JSON.parse(text_body); } catch { err_data = null; }
        const errorMessage = buildFriendlyChatErrorMessage(res, err_data, `Status ${res.status}`);
        insertMessageAfter(targetChatId, userMessageId, { role: 'assistant', content: errorMessage, id: createMessageId() });
        return;
      }
      const assistantMessageId = createMessageId();
      insertMessageAfter(targetChatId, userMessageId, { role: 'assistant', content: '', id: assistantMessageId });
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      const msgTools = [];
      let activeThinkToolIndex = -1;
      const syncLiveTools = () => { setLiveTools(prev => ({ ...prev, [assistantMessageId]: [...msgTools] })); };
      const clearActiveThinkTool = () => { activeThinkToolIndex = -1; };
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
            document.getElementById('thinking-text') && (document.getElementById('thinking-text').textContent = `\u27f3 ${event.tool}...`);
            syncLiveTools();
          } else if (event.type === 'content') {
            clearActiveThinkTool();
            updateMessageInChat(targetChatId, assistantMessageId, (msg) => ({ ...msg, content: (msg.content || '') + event.content }));
          } else if (event.type === 'think') {
            const thinkChunk = String(event.content || '');
            if (!thinkChunk) continue;
            if (activeThinkToolIndex < 0 || msgTools[activeThinkToolIndex]?.tool !== 'think') {
              msgTools.push({ type: 'think', round: event.round || 1, tool: 'think', args: { thought: '' }, status: 'done', success: true });
              activeThinkToolIndex = msgTools.length - 1;
            }
            const previousThought = String(msgTools[activeThinkToolIndex]?.args?.thought || '');
            msgTools[activeThinkToolIndex] = { ...msgTools[activeThinkToolIndex], args: { ...msgTools[activeThinkToolIndex].args, thought: previousThought + thinkChunk } };
            syncLiveTools();
            updateMessageInChat(targetChatId, assistantMessageId, (msg) => ({ ...msg, thinking: (msg.thinking || '') + thinkChunk }));
          } else if (event.type === 'status') {
            clearActiveThinkTool();
            const statusText = String(event.message || '').trim();
            document.getElementById('thinking-text') && (document.getElementById('thinking-text').textContent = statusText || 'Anfrage l\u00e4uft...');
          } else if (event.type === 'tool_end') {
            clearActiveThinkTool();
            const idx = msgTools.findLastIndex(t => t.tool === event.tool && t.status === 'running');
            if (idx >= 0) msgTools[idx] = { ...msgTools[idx], ...event, status: 'done' };
            else msgTools.push({ ...event, status: 'done' });
            document.getElementById('thinking-text') && (document.getElementById('thinking-text').textContent = `\u2713 ${event.tool} (${(event.duration_ms/1000).toFixed(1)}s)`);
            syncLiveTools();
          } else if (event.type === 'final') {
            clearActiveThinkTool();
            document.getElementById('thinking-text') && (document.getElementById('thinking-text').textContent = '');
            setLiveTools(prev => { const n = {...prev}; delete n[assistantMessageId]; return n; });
            updateMessageInChat(targetChatId, assistantMessageId, (msg) => ({
              ...msg, content: event.response, researchStats: event.research_stats || [], files: event.files || [], streamTrace: [...msgTools]
            }));
            if (options.fromVoice) voice.speakAssistantText(event.response);
          } else if (event.type === 'error') {
            clearActiveThinkTool();
            document.getElementById('thinking-text') && (document.getElementById('thinking-text').textContent = '');
            setLiveTools(prev => { const n = {...prev}; delete n[assistantMessageId]; return n; });
            updateMessageInChat(targetChatId, assistantMessageId, (msg) => ({ ...msg, content: `\u26a0\ufe0f Fehler: ${event.error}`, streamTrace: [...msgTools] }));
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
      if (err?.name === 'AbortError') return;
      const isTimeout = /timeout|timed ?out|econnrefused|econnreset|networkerror/i.test(String(err?.message || ''));
      const friendlyMessage = isTimeout
        ? '\u26a0\ufe0f Die Anfrage hat zu lange gedauert. Bitte versuche es mit einer k\u00fcrzeren oder einfacheren Formulierung erneut.'
        : (err?.message || '\u26a0\ufe0f Die Anfrage konnte nicht verarbeitet werden. Bitte versuche es erneut.');
      updateMessageInChat(targetChatId, assistantMessageId, (msg) => ({ ...msg, content: (msg.content || '') + '\n\n' + friendlyMessage }));
    } finally {
      setIsThinking(false);
      setUploadedFiles([]);
      requestAbortRef.current = null;
    }
  }, [isThinking, activeChatId, chats, language, model, source, uploadedFiles, voice.speakAssistantText]);

  sendMessageRef.current = sendMessage;

  const queueMessage = useCallback((text, chatId, meta = {}) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    const messageId = createMessageId();
    appendMessageToChat(chatId, { role: 'user', content: trimmed, id: messageId, queued: true }, trimmed);
    setPendingQueue((prev) => [...prev, { chatId, text: trimmed, messageId, fromVoice: Boolean(meta.fromVoice) }]);
    setInputValue('');
    if (inputRef.current) inputRef.current.value = '';
  }, [appendMessageToChat]);

  const processNextQueued = useCallback(() => {
    if (pendingQueue.length === 0) return;
    const [next, ...rest] = pendingQueue;
    setPendingQueue(rest);
    sendMessage(next.text, { fromQueue: true, chatId: next.chatId, messageId: next.messageId, fromVoice: Boolean(next.fromVoice) });
  }, [pendingQueue, sendMessage]);

  const handleFileUpload = useCallback(async (files) => {
    const uploaded = [];
    for (const file of files) {
      const formData = new FormData();
      formData.append('file', file);
      try {
        const res = await apiFetch('/api/upload', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.success) uploaded.push(data);
      } catch (e) { console.error('Upload error:', e); }
    }
    setUploadedFiles(prev => [...prev, ...uploaded]);
  }, []);

  const removeUploadedFile = useCallback((idx) => {
    setUploadedFiles(prev => prev.filter((_, i) => i !== idx));
  }, []);

  const forms = useForms({ activeChatId, appendMessageToChat, sendMessage });

  const startNewChat = useCallback((sourceMode) => {
    const newChat = createEmptyChat();
    setChats((prev) => [newChat, ...prev]);
    setActiveChatId(newChat.id);
    if (sourceMode) setSource(sourceMode);
    forms.resetCalendarForm();
    forms.resetTaskForm();
    forms.resetIntegrationForm();
  }, [setChats, setActiveChatId, setSource, forms]);

  const openChat = useCallback((chatId) => {
    setActiveChatId(chatId);
    forms.resetCalendarForm();
    forms.resetTaskForm();
    forms.resetIntegrationForm();
    router.push(`/chat/${chatId}`, { scroll: false });
  }, [setActiveChatId, forms, router]);

  const summarizeChat = useCallback(async (chatId, options = {}) => {
    const chat = chats.find((item) => item.id === chatId);
    if (!chat) return;
    const messagesForSummary = Array.isArray(chat.messages)
      ? chat.messages.filter((message) => { const role = String(message?.role || '').toLowerCase(); return role === 'user' || role === 'assistant'; })
      : [];
    if (!messagesForSummary.length) { window.alert('Dieser Chat hat noch keinen Inhalt zum Zusammenfassen.'); return; }
    const userMessages = messagesForSummary.filter((message) => message.role === 'user').length;
    const assistantMessages = messagesForSummary.filter((message) => message.role === 'assistant').length;
    const reuseCached = !options.force && chat.summary?.messageCount === messagesForSummary.length && chat.summary?.content;
    if (reuseCached) {
      setChatSummaryPanel({ open: true, chatId, title: chat.title, summary: chat.summary.content, generatedAt: chat.summary.generatedAt || Date.now(), messageCount: chat.summary.messageCount || messagesForSummary.length, stats: { total: messagesForSummary.length, user: userMessages, assistant: assistantMessages }, loading: false, error: '' });
      return;
    }
    setChatSummaryPanel({ open: true, chatId, title: chat.title, summary: '', generatedAt: 0, messageCount: messagesForSummary.length, stats: { total: messagesForSummary.length, user: userMessages, assistant: assistantMessages }, loading: true, error: '' });
    try {
      const res = await apiFetch('/api/chat/summarize', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: messagesForSummary, title: chat.title, language: 'de', preferred_source: 'auto' })
      });
      const data = await safeReadJson(res);
      if (!res.ok || data?.success === false) throw new Error(data?.error || `Request failed with status ${res.status}`);
      const summaryText = String(data?.summary || '').trim();
      const generatedAt = Date.now();
      setChats((prevChats) => prevChats.map((item) => (item.id === chatId ? { ...item, summary: { content: summaryText, generatedAt, messageCount: messagesForSummary.length }, updatedAt: item.updatedAt || Date.now() } : item)));
      setChatSummaryPanel((prev) => ({ ...prev, open: true, summary: summaryText, generatedAt, loading: false, error: '' }));
    } catch (err) { setChatSummaryPanel((prev) => ({ ...prev, loading: false, error: `Zusammenfassung fehlgeschlagen: ${err.message}` })); }
  }, [chats, setChats]);

  const renameChat = useCallback((chatId) => {
    const chat = chats.find((item) => item.id === chatId);
    if (!chat) return;
    const nextTitle = window.prompt('Chat umbenennen:', chat.title);
    if (!nextTitle || !nextTitle.trim()) return;
    const trimmed = nextTitle.trim();
    setChats((prevChats) => prevChats.map((item) => (item.id === chatId ? { ...item, title: trimmed, updatedAt: Date.now() } : item)));
  }, [chats, setChats]);

  const deleteChat = useCallback((chatId) => {
    const chat = chats.find((item) => item.id === chatId);
    if (!chat) return;
    const confirmed = window.confirm(`Chat "${chat.title}" wirklich loeschen?`);
    if (!confirmed) return;
    if (chatId === activeChatId) { forms.resetCalendarForm(); forms.resetTaskForm(); forms.resetIntegrationForm(); }
    setChats((prevChats) => {
      const remaining = prevChats.filter((item) => item.id !== chatId);
      if (!remaining.length) { const newChat = createEmptyChat(); setActiveChatId(newChat.id); return [newChat]; }
      if (chatId === activeChatId) setActiveChatId(remaining[0].id);
      return remaining;
    });
  }, [chats, activeChatId, setChats, setActiveChatId, forms]);

  const assignProjectToChat = useCallback((chatId, projectId) => {
    setChats((prev) => prev.map((c) => (c.id === chatId ? { ...c, project: projectId } : c)));
  }, [setChats]);

  const sortedChats = useMemo(() => [...chats]
    .filter(c => !activeProject || c.project === activeProject)
    .sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0)),
  [chats, activeProject]);

  const getWeekStart = useCallback((value) => {
    const date = new Date(value.getFullYear(), value.getMonth(), value.getDate());
    const day = date.getDay();
    const diff = day === 0 ? -6 : 1 - day;
    date.setDate(date.getDate() + diff);
    return date;
  }, []);

  const getChatGroupLabel = useCallback((chat) => {
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
  }, [getWeekStart]);

  const loadAIConfig = useCallback(async () => {
    try {
      const res = await apiFetch('/api/ai/config');
      const config = await safeReadJson(res);
      if (!res.ok || !config?.base_url) throw new Error(config?.error || `Request failed with status ${res.status}`);
      const url = new URL(config.base_url);
      setAiProtocol(url.protocol.replace(':', ''));
      setAiHost(url.hostname);
      setAiPort(url.port || '11434');
      setAiModel(config.model);
      setModel(config.model);
      const hasServerTtsProvider = Object.prototype.hasOwnProperty.call(config, 'tts_provider');
      const storedTtsProvider = typeof window !== 'undefined' ? window.localStorage.getItem(TTS_PROVIDER_STORAGE_KEY) : '';
      const resolvedTtsProvider = hasServerTtsProvider ? normalizeTtsProvider(config.tts_provider) : normalizeTtsProvider(storedTtsProvider);
      voice.setTtsProvider(resolvedTtsProvider);
      if (typeof window !== 'undefined') window.localStorage.setItem(TTS_PROVIDER_STORAGE_KEY, resolvedTtsProvider);
      voice.setSelectedVoiceUri(String(config.browser_tts_voice_uri || ''));
      setAiStatus('Loaded');
    } catch (err) { setAiStatus('Error loading config'); }
  }, [voice]);

  const loadOllamaModels = useCallback(async () => {
    try {
      const res = await apiFetch('/api/ollama/models');
      const data = await safeReadJson(res);
      setAiModels(uniqueSortedModels(data.models).filter(isChatModel));
    } catch (err) { console.error('Error loading models:', err); }
  }, []);

  const saveAIConfig = useCallback(async () => {
    try {
      const baseUrl = `${aiProtocol}://${aiHost}:${aiPort}`;
      const res = await apiFetch('/api/ai/config', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ base_url: baseUrl, model: aiModel })
      });
      if (res.ok) { setAiStatus('Saved successfully'); updateStatus(); }
      else setAiStatus('Error saving');
    } catch (err) { setAiStatus('Error: ' + err.message); }
  }, [aiProtocol, aiHost, aiPort, aiModel]);

  const updateStatus = useCallback(async () => {
    try {
      const [ollamaRes, kbRes] = await Promise.all([apiFetch('/api/ollama/status'), apiFetch('/api/knowledge/status')]);
      const ollama = await safeReadJson(ollamaRes);
      const kb = await safeReadJson(kbRes);
      const totalChunks = Number(kb.chunks_loaded || 0);
      const generatedEmbeddings = Number(kb.generated_embeddings ?? kb.embeddings_count ?? 0);
      const missingEmbeddings = Number(kb.missing_embeddings ?? Math.max(totalChunks - generatedEmbeddings, 0));
      const embeddingsComplete = Boolean(kb.embeddings_complete ?? (totalChunks > 0 && missingEmbeddings === 0));
      setHealth({ ollama: ollama.connected ? 'ok' : 'error', kb: kb.database_path ? 'ok' : 'error', embeddings: kb.semantic_search_available ? (embeddingsComplete ? 'ok' : 'loading') : 'error' });
    } catch (err) { setHealth({ ollama: 'error', kb: 'error', embeddings: 'error' }); }
    try {
      const storedToken = (() => { try { return localStorage.getItem('mynd_token_v1'); } catch(e) { return null; } })();
      const headers = storedToken ? { 'Authorization': `Bearer ${storedToken}` } : {};
      const meRes = await apiFetch('/api/auth/me', { headers });
      const me = await safeReadJson(meRes);
      if (meRes.ok && me && me.authenticated) setUser(me.user);
      else setUser(null);
    } catch (err) { setUser(null); }
  }, [setHealth, setUser]);

  const loadSecurityStatus = useCallback(async () => {
    try {
      setSecurityLoading(true);
      const res = await apiFetch('/api/security/status');
      const data = await safeReadJson(res);
      if (!res.ok || data?.success === false) { setSecurityStatus({ headline: 'Sicherheitslage aktuell nicht verf\u00fcgbar', nina_warning_count: 0, nina_warnings: [] }); return; }
      setSecurityStatus(data);
    } catch (err) { setSecurityStatus({ headline: 'Sicherheitslage aktuell nicht verf\u00fcgbar', nina_warning_count: 0, nina_warnings: [] }); }
    finally { setSecurityLoading(false); }
  }, []);

  const loadProactiveBriefings = useCallback(async (force = false) => {
    try {
      const briefingUrl = force ? `${getApiBase()}/api/assistant/briefing/current?force=true` : `${getApiBase()}/api/assistant/briefing/current`;
      const res = await fetch(briefingUrl);
      const data = await safeReadJson(res);
      if (!res.ok || data?.success === false) return;
      const items = Array.isArray(data?.items) ? data.items : [];
      setProactiveBriefings(items.filter((item) => item?.content));
    } catch (err) { console.error('Could not load proactive briefings:', err); }
  }, []);

  const startIndexing = useCallback(async () => {
    try {
      const configRes = await apiFetch('/api/indexing/config');
      if (configRes.ok) {
        const config = await configRes.json();
        if (!config.url || !config.username) { setIndexingStatus('error: Nextcloud configuration required. Please configure in Settings first.'); return; }
      }
      const res = await apiFetch('/api/indexing/start', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
      if (res.ok) {
        setIndexingStatus('running');
        if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = setInterval(async () => {
          try {
            const pres = await apiFetch('/api/indexing/progress');
            if (pres.ok) {
              const data = await pres.json();
              setIndexingProgress(Math.round(data.progress_percentage || 0));
              const processingSpeed = data.elapsed_time > 0 ? (data.processed_files / data.elapsed_time).toFixed(1) : 0;
              setIndexingDetails({
                currentFile: data.current_file || '', processedFiles: data.processed_files || 0, totalFiles: data.total_files || 0,
                elapsedTime: Math.round(data.elapsed_time) || 0, errors: data.errors || [], chunksCreated: 0,
                documentsProcessed: data.processed_files || 0, processingSpeed: parseFloat(processingSpeed),
                lastIndexingStart: data.last_indexing_start || 0, lastIndexingEnd: data.last_indexing_end || 0, lastIndexingDuration: data.last_indexing_duration || 0
              });
              const timeRemaining = data.progress_percentage > 0 && data.elapsed_time > 0
                ? Math.round((data.elapsed_time / data.progress_percentage) * (100 - data.progress_percentage)) : 0;
              setIndexingStats(`${data.processed_files || 0}/${data.total_files || 0} ${t('files').toLowerCase()} | ${Math.round(data.elapsed_time || 0)}s ${t('elapsed').toLowerCase()} | ${processingSpeed} ${t('files').toLowerCase()}/s | ${timeRemaining > 0 ? `~${timeRemaining}s` : '...'}`);
              if (data.status === 'completed' || data.status === 'error') {
                setIndexingStatus(data.status);
                if (data.status === 'completed') setIndexingDetails(prev => ({ ...prev, chunksCreated: data.processed_files * 10 }));
                clearInterval(progressIntervalRef.current);
              }
            } else if (pres.status === 500) { console.error('Server error during indexing progress check'); setIndexingStatus('error: Server error'); clearInterval(progressIntervalRef.current); }
            else { console.error('Unexpected response:', pres.status, pres.statusText); const errorText = await pres.text(); console.error('Error response:', errorText); setIndexingStatus(`error: ${pres.status}`); }
          } catch (err) {
            console.error('Update progress error:', err);
            if (err.message.includes('JSON')) { setIndexingStatus('error: Invalid response from server'); clearInterval(progressIntervalRef.current); }
          }
        }, 500);
      } else { const data = await res.json(); setIndexingStatus('error: ' + data.error); }
    } catch (err) { setIndexingStatus('error: ' + err.message); }
  }, [t]);

  const getImageDownloadUrl = useCallback((thumbnailUrl) => {
    if (!thumbnailUrl) return '';
    try {
      const parsedUrl = new URL(thumbnailUrl, window.location.origin);
      const assetMatch = parsedUrl.pathname.match(/\/api\/immich\/thumbnail\/([^/?#]+)/);
      const assetId = assetMatch?.[1];
      if (!assetId) return '';
      const params = new URLSearchParams();
      const username = parsedUrl.searchParams.get('username');
      if (username) params.set('username', username);
      const query = params.toString();
      return `${getApiBase()}/api/immich/download/${assetId}${query ? `?${query}` : ''}`;
    } catch (_) { return ''; }
  }, []);

  const openPhotoPreview = useCallback(({ title = 'Vorschau', thumbnailUrl = '', immichUrl = '', sourceUrl = '' }) => {
    const resolvedSourceUrl = sourceUrl || immichUrl;
    setPhotoPreview({ open: true, title, thumbnailUrl, immichUrl, sourceUrl: resolvedSourceUrl, downloadUrl: getImageDownloadUrl(thumbnailUrl) });
  }, [getImageDownloadUrl]);

  const closePhotoPreview = useCallback(() => { setPhotoPreview((prev) => ({ ...prev, open: false })); }, []);

  const handleMarkdownContentClick = useCallback((event) => {
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
  }, [openPhotoPreview]);

  const markdownComponents = useMemo(() => ({
    p: ({ node, children, ...props }) => {
      const isImg = (c) => c.tagName === 'img';
      const isImgLink = (c) => c.tagName === 'a' && c.children?.some(isImg);
      const isWhitespace = (c) => c.type === 'text' && /^\s*$/.test(c.value || '');
      const isImageParagraph = node?.children?.length > 0 && node.children.every((c) => isImg(c) || isImgLink(c) || isWhitespace(c));
      return <p className={isImageParagraph ? 'markdown-image-paragraph' : undefined} {...props}>{children}</p>;
    },
    a: ({ href, children, ...props }) => <a href={href} target="_blank" rel="noopener noreferrer" {...props}>{children}</a>,
    img: ({ src, alt, ...props }) => <img {...props} src={src} alt={alt} className="chat-thumbnail" loading="lazy" />,
    code: ({ className, children, inline, ...props }) => {
      if (inline) return <code className="inline-code" {...props}>{children}</code>;
      const codeString = String(children || '').replace(/\n$/, '');
      return <code className={className}>{codeString}</code>;
    },
    pre: ({ children, ...props }) => {
      let codeString = '';
      let lang = '';
      if (children && typeof children === 'object') {
        codeString = children.props?.children || '';
        const cls = children.props?.className || '';
        const match = /language-(\w+)/.exec(cls);
        lang = match ? match[1] : '';
      }
      return <SyntaxHighlighter style={oneDark} language={lang || undefined} PreTag="div" customStyle={{ margin: '8px 0', borderRadius: '8px', fontSize: '0.82rem' }}>{codeString}</SyntaxHighlighter>;
    }
  }), []);

  const renderWeatherMiniIcon = useCallback((iconType) => {
    if (iconType === 'rain') return <span className="weather-mini-icon rain" aria-hidden="true"><i className="fas fa-cloud"></i><span className="rain-drop drop-1"></span><span className="rain-drop drop-2"></span><span className="rain-drop drop-3"></span></span>;
    if (iconType === 'cloud') return <span className="weather-mini-icon cloud" aria-hidden="true"><i className="fas fa-cloud"></i></span>;
    return <span className="weather-mini-icon sun" aria-hidden="true"><i className="fas fa-sun"></i></span>;
  }, []);

  useEffect(() => {
    if (!messagesEndRef.current) return;
    const el = messagesEndRef.current;
    const parent = el.parentElement;
    if (parent) { const distanceToBottom = parent.scrollHeight - parent.scrollTop - parent.clientHeight; if (distanceToBottom > 150) return; }
    el.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (!isThinking && pendingQueue.length > 0) processNextQueued();
  }, [isThinking, pendingQueue, processNextQueued]);

  useEffect(() => {
    loadAIConfig();
    loadOllamaModels();
    fetchUser();
    updateStatus();
    loadSecurityStatus();
    loadProactiveBriefings();
    autoResolveLocationOnOpen();
    fetchGreeting();
    if (!personalGreeting) setPersonalGreeting('Hallo');
    const onPop = () => { const urlChat = new URL(window.location.href).searchParams.get('chat'); if (urlChat) setActiveChatId(urlChat); };
    window.addEventListener('popstate', onPop);
    const statusInterval = setInterval(updateStatus, 8000);
    const securityInterval = setInterval(loadSecurityStatus, 60000);
    const briefingInterval = setInterval(loadProactiveBriefings, 10 * 60 * 1000);
    return () => { clearInterval(statusInterval); clearInterval(securityInterval); clearInterval(briefingInterval); window.removeEventListener('popstate', onPop); };
  }, []);

  useEffect(() => {
    if (!activeChatId || !proactiveBriefings.length) return;
    let seen = [];
    try { seen = JSON.parse(localStorage.getItem(BRIEFING_SEEN_KEY) || '[]'); if (!Array.isArray(seen)) seen = []; } catch { seen = []; }
    const unseen = proactiveBriefings.filter((item) => item?.key && !seen.includes(item.key));
    if (!unseen.length) return;
    unseen.forEach((item) => { appendMessageToChat(activeChatId, { role: 'assistant', content: `## ${item.title || 'Briefing'}\n\n${item.content || ''}`, id: createMessageId(), sources: [], uiCards: [] }); });
    try { const nextSeen = [...new Set([...seen, ...unseen.map((item) => item.key)])]; localStorage.setItem(BRIEFING_SEEN_KEY, JSON.stringify(nextSeen)); } catch (err) { console.error('Could not persist seen briefings:', err); }
  }, [activeChatId, proactiveBriefings, appendMessageToChat]);

  useEffect(() => {
    try { const rawDisplayName = localStorage.getItem(DISPLAY_NAME_STORAGE_KEY); if (rawDisplayName) setDisplayName(rawDisplayName); }
    catch (err) { console.error('Error loading data:', err); }
  }, []);

  useEffect(() => {
    const cleanChats = chats.filter(c => (c.messages?.length || 0) > 0 || c.title !== 'Neuer Chat');
    if (cleanChats.length !== chats.length) setChats(cleanChats);
  }, [chats, setChats]);

  useEffect(() => {
    if (chats.length === 0) { const initialChat = createEmptyChat(); setChats([initialChat]); setActiveChatId(initialChat.id); return; }
    if (!activeChatId) { setActiveChatId(chats[0].id); return; }
    const urlChat = typeof window !== 'undefined' ? new URL(window.location.href).searchParams.get('chat') : null;
    if (urlChat && chats.some(c => c.id === urlChat) && urlChat !== activeChatId) setActiveChatId(urlChat);
  }, [chats.length, chats, activeChatId, setChats, setActiveChatId]);

  useEffect(() => {
    const interval = setInterval(() => { setGreetingTick(Date.now()); }, 15 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!chats.length || !activeChatId) return;
    const cleanChats = chats.filter(c => (c.messages?.length || 0) > 0 || c.title !== 'Neuer Chat');
    try { localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(cleanChats)); localStorage.setItem(ACTIVE_CHAT_STORAGE_KEY, activeChatId); }
    catch (err) { console.error('Error saving chat history:', err); }
  }, [chats, activeChatId]);

  useEffect(() => {
    if (!photoPreview.open) return undefined;
    const handleEscape = (event) => { if (event.key === 'Escape') setPhotoPreview((prev) => ({ ...prev, open: false })); };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [photoPreview.open]);

  useEffect(() => {
    if (!chatSummaryPanel.open) return undefined;
    const handleEscape = (event) => { if (event.key === 'Escape') setChatSummaryPanel((prev) => ({ ...prev, open: false })); };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [chatSummaryPanel.open]);

  useEffect(() => {
    const handleCancelKey = (event) => {
      if (!isThinking) return;
      if (event.key === 'c' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); cancelPendingRequest(); }
    };
    window.addEventListener('keydown', handleCancelKey);
    return () => window.removeEventListener('keydown', handleCancelKey);
  }, [isThinking, cancelPendingRequest]);

  const canSend = inputValue.trim().length > 0;
  const queueReady = isThinking && canSend;
  const voiceStatusText = (() => {
    if (voice.voiceError) return voice.voiceError;
    if (voice.isListening) return language === 'de' ? 'Voice: Ich hoere zu...' : 'Voice: Listening...';
    if (voice.isSpeaking) return language === 'de' ? 'Voice: Ich antworte gerade...' : 'Voice: Speaking...';
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
              <button type="button" className="security-refresh" onClick={loadSecurityStatus} disabled={securityLoading} title="Sicherheitslage aktualisieren">
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
              <button type="button" className="security-refresh" onClick={() => loadProactiveBriefings(true)} title="Briefing aktualisieren">Aktualisieren</button>
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
            canSend={canSend} isListening={voice.isListening}
            onSend={sendMessage} onStartVoiceInput={voice.startVoiceInput}
            indexingStatus={indexingStatus} indexingProgress={indexingProgress}
            indexingDetails={indexingDetails} indexingStats={indexingStats}
            source={source} setSource={setSource}
            model={model} setModel={setModel} aiModels={aiModels}
          />
        ) : (
          <>
            <MessageList
              messages={messages} isThinking={isThinking} liveTools={liveTools}
              markdownComponents={markdownComponents} handleMarkdownContentClick={handleMarkdownContentClick}
              messagesEndRef={messagesEndRef} sendMessage={sendMessage}
              calendarForm={forms.calendarForm} setCalendarForm={forms.setCalendarForm}
              submitCalendarForm={forms.submitCalendarForm} closeCalendarForm={forms.closeCalendarForm}
              taskForm={forms.taskForm} setTaskForm={forms.setTaskForm}
              submitTaskForm={forms.submitTaskForm} closeTaskForm={forms.closeTaskForm}
              integrationForm={forms.integrationForm} setIntegrationForm={forms.setIntegrationForm}
              submitIntegrationForm={forms.submitIntegrationForm} closeIntegrationForm={forms.closeIntegrationForm}
              runNextcloudLoginFlow={forms.runNextcloudLoginFlow}
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
              isListening={voice.isListening} voiceStatusText={voiceStatusText}
              source={source} setSource={setSource}
              model={model} setModel={setModel} aiModels={aiModels}
              onSend={sendMessage} onStartVoiceInput={voice.startVoiceInput}
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
                        <button className="modal-list-act del" onClick={() => { if (window.confirm(tr(`Projekt "${p.name}" l\u00f6schen?`, `Delete project "${p.name}"?`))) { setProjects(prev => prev.filter(pp => pp.id !== p.id)); setChats(prev => prev.map(c => c.project === p.id ? { ...c, project: null } : c)); if (activeProject === p.id) setActiveProject(null); }}} title={tr('L\u00f6schen', 'Delete')}><i className="fas fa-trash"></i></button>
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
              <p style={{marginBottom: '16px', color: '#ccc', fontSize: '1.05em', lineHeight: 1.5}}>{pendingUserInput.message}</p>
              <textarea value={pendingUserInputValue} onChange={(e) => setPendingUserInputValue(e.target.value)}
                placeholder={tr('Deine Antwort...', 'Your answer...')} rows={3}
                style={{width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #444', background: '#222', color: '#eee', fontSize: '0.95em', resize: 'vertical', marginBottom: '12px', boxSizing: 'border-box'}}
              />
              <div style={{display: 'flex', gap: '10px', justifyContent: 'flex-end'}}>
                <button className="btn btn-secondary" onClick={() => { setPendingUserInput(null); setPendingUserInputValue(''); }}>{tr('Abbrechen', 'Cancel')}</button>
                <button className="btn btn-primary" disabled={!pendingUserInputValue.trim()} onClick={async () => {
                  const input = pendingUserInputValue.trim();
                  setPendingUserInputValue('');
                  setPendingUserInput(null);
                  updateMessageInChat(pendingUserInput.chatId, pendingUserInput.messageId, (msg) => ({ ...msg, content: (msg.content || '') + `\n\n\u26a0\ufe0f **KI fragt:** ${pendingUserInput.message}\n\u{1F464} **Antwort:** ${input}` }));
                  try {
                    const res = await apiFetch('/api/agent/input', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ input }) });
                    const data = await res.json();
                    if (data.success && data.response) { updateMessageInChat(pendingUserInput.chatId, pendingUserInput.messageId, (msg) => ({ ...msg, content: data.response, streamTrace: [...(msg.streamTrace || [])] })); }
                    else { updateMessageInChat(pendingUserInput.chatId, pendingUserInput.messageId, (msg) => ({ ...msg, content: msg.content + `\n\n\u274c Fehler: ${data.error || 'Unbekannter Fehler'}` })); }
                  } catch (e) { updateMessageInChat(pendingUserInput.chatId, pendingUserInput.messageId, (msg) => ({ ...msg, content: msg.content + `\n\n\u274c Fehler: ${e.message}` })); }
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
              <strong>{tr('Tool-Best\u00e4tigung', 'Tool Confirmation')}</strong>
              <button className="modal-x" onClick={() => setPendingToolConfirm(null)}>&times;</button>
            </div>
            <div className="modal-body" style={{padding: '20px'}}>
              <p style={{marginBottom: '12px', color: '#e8a040'}}><i className="fas fa-shield-halved"></i> <strong>{pendingToolConfirm.tool}</strong>: {pendingToolConfirm.description}</p>
              <p style={{fontSize: '0.9em', color: '#999', marginBottom: '20px'}}>{tr('M\u00f6chtest du die Ausf\u00fchrung dieses Tools erlauben?', 'Do you want to allow executing this tool?')}</p>
              <div style={{display: 'flex', gap: '10px', justifyContent: 'flex-end'}}>
                <button className="btn btn-secondary" onClick={() => setPendingToolConfirm(null)}>{tr('Ablehnen', 'Deny')}</button>
                <button className="btn btn-primary" onClick={async () => {
                  const toolInfo = pendingToolConfirm;
                  setPendingToolConfirm(null);
                  try {
                    const res = await apiFetch('/api/tool/run', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ confirmed: true }) });
                    const data = await res.json();
                    if (data.success) { insertMessageAfter(activeChatId, userMessageId, { role: 'assistant', content: `✅ Tool ausgef\u00fchrt:\n\`\`\`\n${data.result}\n\`\`\``, id: createMessageId() }); }
                    else { insertMessageAfter(activeChatId, userMessageId, { role: 'assistant', content: `\u274c Fehler: ${data.error}`, id: createMessageId() }); }
                  } catch (e) { console.error('Tool confirm error:', e); }
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
