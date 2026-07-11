'use client';

import { createContext, useContext, useState, useEffect, useMemo, useCallback } from 'react';
import { apiFetch } from './api';

const CHAT_STORAGE_KEY = 'mynd_chat_history_v1';
const ACTIVE_CHAT_STORAGE_KEY = 'mynd_active_chat_v1';
const PROJECTS_STORAGE_KEY = 'mynd_projects_v1';

const AppContext = createContext(null);

function createChatId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now()}-${Math.floor(Math.random() * 100000)}`;
}

function createEmptyChat(project = null) {
  const now = Date.now();
  return { id: createChatId(), title: 'Neuer Chat', messages: [], createdAt: now, updatedAt: now, project };
}

function loadChats() {
  try {
    const raw = localStorage.getItem(CHAT_STORAGE_KEY);
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch { return []; }
}

function loadActiveChatId() {
  try { return localStorage.getItem(ACTIVE_CHAT_STORAGE_KEY); } catch { return null; }
}

function loadProjects() {
  try {
    const raw = localStorage.getItem(PROJECTS_STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

export function AppProvider({ children }) {
  const [chats, setChats] = useState(loadChats);
  const [activeChatId, setActiveChatId] = useState(loadActiveChatId);
  const [showSettings, setShowSettings] = useState(false);
  const [user, setUser] = useState(null);
  const [health, setHealth] = useState({ ollama: 'unknown', kb: 'unknown', embeddings: 'unknown' });
  const [projects, setProjects] = useState(loadProjects);
  const [activeProject, setActiveProject] = useState(null);

  useEffect(() => {
    const token = (() => { try { return localStorage.getItem('mynd_token_v1'); } catch(e) { return null; } })();
    if (!token) return;
    apiFetch('/api/auth/me', { headers: { 'Authorization': `Bearer ${token}` } })
      .then(r => r.json())
      .then(data => { if (data?.authenticated && data.user) setUser(data.user); })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const nonEmpty = chats.filter(c => (c.messages?.length || 0) > 0 || c.title !== 'Neuer Chat');
    if (nonEmpty.length > 0) {
      try {
        localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(nonEmpty));
        localStorage.setItem(ACTIVE_CHAT_STORAGE_KEY, activeChatId || '');
      } catch {}
    }
  }, [chats, activeChatId]);

  useEffect(() => {
    try {
      localStorage.setItem(PROJECTS_STORAGE_KEY, JSON.stringify(projects));
    } catch {}
  }, [projects]);

  const startNewChat = useCallback((sourceMode) => {
    const newChat = createEmptyChat(activeProject);
    setChats(prev => [newChat, ...prev]);
    setActiveChatId(newChat.id);
  }, [activeProject]);

  const openChat = useCallback((chatId) => {
    setActiveChatId(chatId);
  }, []);

  const deleteChat = useCallback((chatId) => {
    setChats(prev => {
      const remaining = prev.filter(c => c.id !== chatId);
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
  }, [activeChatId]);

  const renameChat = useCallback((chatId, title) => {
    setChats(prev => prev.map(c => c.id === chatId ? { ...c, title, updatedAt: Date.now() } : c));
  }, []);

  const assignProjectToChat = useCallback((chatId, projectId) => {
    setChats(prev => prev.map(c => c.id === chatId ? { ...c, project: projectId } : c));
  }, []);

  const value = useMemo(() => ({
    chats, setChats, activeChatId, setActiveChatId,
    showSettings, setShowSettings,
    user, setUser, health, setHealth,
    projects, setProjects, activeProject, setActiveProject,
    startNewChat, openChat, deleteChat, renameChat, assignProjectToChat
  }), [
    chats, activeChatId, showSettings, user, health, projects, activeProject,
    startNewChat, openChat, deleteChat, renameChat, assignProjectToChat
  ]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used within AppProvider');
  return ctx;
}
