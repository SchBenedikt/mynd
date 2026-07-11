'use client';

import { useState, useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { useApp } from '../lib/AppContext';
import { useSidebar } from '../hooks/useSidebar';
import { useLanguage } from '../hooks/useLanguage';
import SearchPopup from './SearchModal';
import ChatContextMenu from './ChatContextMenu';

const DAY_MS = 86400000;
const WEEK_MS = 7 * DAY_MS;
const MONTH_MS = 30 * DAY_MS;

export default function Sidebar() {
  const {
    chats, activeChatId, projects,
    openChat, startNewChat, deleteChat, renameChat,
    assignProjectToChat, user, health,
    setShowSettings
  } = useApp();
  const { isSidebarCollapsed, toggleSidebar, canAnimate } = useSidebar();
  const { language, t } = useLanguage();
  const tr = (deText, enText) => (language === 'de' ? deText : enText);
  const router = useRouter();
  const [searchOpen, setSearchOpen] = useState(false);
  const [menuChat, setMenuChat] = useState(null);
  const [menuPos, setMenuPos] = useState(null);
  const [projectPickerChat, setProjectPickerChat] = useState(null);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  const chatForMenu = menuChat ? chats.find(c => c.id === menuChat) : null;

  const sortedChats = useMemo(() => {
    return [...chats].sort((a, b) => (b.updatedAt || b.createdAt) - (a.updatedAt || a.createdAt));
  }, [chats]);

  const groupedChats = useMemo(() => {
    const groups = [];
    const now = Date.now();

    const pinned = sortedChats.filter(c => c.pinned);
    if (pinned.length > 0) groups.push({ label: 'Pinned', items: pinned });

    const today = sortedChats.filter(c => !c.pinned && (now - (c.updatedAt || c.createdAt)) < DAY_MS);
    if (today.length > 0) groups.push({ label: language === 'de' ? 'Heute' : 'Today', items: today });

    const thisWeek = sortedChats.filter(c => !c.pinned && (now - (c.updatedAt || c.createdAt)) < WEEK_MS && (now - (c.updatedAt || c.createdAt)) >= DAY_MS);
    if (thisWeek.length > 0) groups.push({ label: language === 'de' ? 'Diese Woche' : 'This Week', items: thisWeek });

    const thisMonth = sortedChats.filter(c => !c.pinned && (now - (c.updatedAt || c.createdAt)) < MONTH_MS && (now - (c.updatedAt || c.createdAt)) >= WEEK_MS);
    if (thisMonth.length > 0) groups.push({ label: language === 'de' ? 'Dieser Monat' : 'This Month', items: thisMonth });

    const older = sortedChats.filter(c => !c.pinned && (now - (c.updatedAt || c.createdAt)) >= MONTH_MS);
    if (older.length > 0) groups.push({ label: language === 'de' ? 'Älter' : 'Older', items: older });

    return groups;
  }, [sortedChats, language]);

  const openMenu = useCallback((e, chatId) => {
    e.stopPropagation();
    const sidebarEl = document.querySelector('.left-sidebar');
    const sidebarRect = sidebarEl?.getBoundingClientRect();
    const rect = e.currentTarget.getBoundingClientRect();
    setMenuPos({ x: (sidebarRect?.right || rect.right) + 4, y: rect.top });
    setMenuChat(menuChat === chatId ? null : chatId);
    setProjectPickerChat(null);
  }, [menuChat]);

  const closeMenu = useCallback(() => {
    setMenuChat(null);
    setMenuPos(null);
  }, []);

  const handleRename = useCallback((chatId) => {
    const chat = chats.find(item => item.id === chatId);
    if (!chat) return;
    const nextTitle = window.prompt(
      language === 'de' ? 'Chat umbenennen:' : 'Rename chat:',
      chat.title
    );
    if (!nextTitle || !nextTitle.trim()) return;
    renameChat(chatId, nextTitle.trim());
  }, [chats, language, renameChat]);

  const handleDelete = useCallback((chatId) => {
    const chat = chats.find(item => item.id === chatId);
    if (!chat) return;
    const msg = language === 'de'
      ? `Chat "${chat.title}" wirklich löschen?`
      : `Delete chat "${chat.title}"?`;
    if (!window.confirm(msg)) return;
    deleteChat(chatId);
  }, [chats, language, deleteChat]);

  const logout = async () => {
    try { await fetch('/api/auth/logout', { method: 'POST' }); } catch (e) {}
    try { localStorage.removeItem('mynd_user_v1'); localStorage.removeItem('mynd_token_v1'); } catch (e) {}
    window.location.reload();
  };

  return (
    <div className={`left-sidebar ${isSidebarCollapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-header">
        <button type="button" className="brand" onClick={toggleSidebar}>
          {isSidebarCollapsed ? <span style={{fontSize:'1.4rem',lineHeight:1}}>🧠</span> : 'MYND'}
        </button>
      </div>

      <div className="primary-nav">
        <button className="nav-item" onClick={startNewChat} title={t('newChat')}>
          <i className="fas fa-pen"></i><span>{t('newChat')}</span>
        </button>
        <div className="search-btn-wrap">
          <button className="nav-item" onClick={() => setSearchOpen(true)} title={tr('Chats durchsuchen', 'Search chats')}>
            <i className="fas fa-search"></i><span>{tr('Chats durchsuchen', 'Search chats')}</span>
          </button>
          <SearchPopup open={searchOpen} onClose={() => setSearchOpen(false)} chats={chats} projects={projects} onOpenChat={openChat} language={language} tr={tr} />
        </div>
        <button className="nav-item" onClick={() => router.push('/projects')} title={tr('Projekte', 'Projects')}>
          <i className="fas fa-folder"></i><span>{tr('Projekte', 'Projects')}</span>
        </button>
      </div>

      <div className="chat-history">
        {groupedChats.filter(g => g.label && g.items.length > 0).length > 0 ? (
          <>
            {groupedChats.filter(g => g.label === 'Pinned' || g.label === 'Angeheftet').map((group, gi) => (
              <div key={`pinned-${gi}`} className="history-group">
                {!isSidebarCollapsed && <div className="section-label">{tr('Angeheftet', 'Pinned')}</div>}
                {group.items.map((chat) => (
                  <div key={chat.id} className={`history-item ${chat.id === activeChatId ? 'active' : ''}`}
                    onClick={() => openChat(chat.id)} role="button" tabIndex={0} title={chat.title}>
                    <i className="fas fa-comment"></i><span className="history-title">{chat.title}</span>
                    <div className="history-actions">
                      <button type="button" className="history-action dots" onClick={(e) => openMenu(e, chat.id)} title={tr('Mehr', 'More')}><i className="fas fa-ellipsis-h"></i></button>
                    </div>
                  </div>
                ))}
              </div>
            ))}
            {groupedChats.filter(g => g.label !== 'Pinned' && g.label !== 'Angeheftet').map((group, gi) => (
              <div key={`recent-${gi}`} className="history-group">
                {!isSidebarCollapsed && <div className="section-label">{group.label}</div>}
                {group.items.map((chat) => (
                  <div key={chat.id} className={`history-item ${chat.id === activeChatId ? 'active' : ''}`}
                    onClick={() => openChat(chat.id)} role="button" tabIndex={0} title={chat.title}>
                    {!isSidebarCollapsed && <i className="fas fa-comment"></i>}
                    <span className="history-title">{chat.title}</span>
                    {!isSidebarCollapsed && chat.project && <span className="project-badge">{projects.find(p => p.id === chat.project)?.name || '?'}</span>}
                    <div className="history-actions">
                      <button type="button" className="history-action dots" onClick={(e) => openMenu(e, chat.id)} title={tr('Mehr', 'More')}><i className="fas fa-ellipsis-h"></i></button>
                    </div>
                    {projectPickerChat === chat.id && !isSidebarCollapsed && (
                      <div className="project-picker-dropdown" onClick={e => e.stopPropagation()}>
                        <div className="project-picker-option" onClick={() => { assignProjectToChat(chat.id, null); setProjectPickerChat(null); }}>
                          <i className="fas fa-times-circle"></i> Kein Projekt
                        </div>
                        {projects.map(p => (
                          <div key={p.id} className={`project-picker-option ${chat.project === p.id ? 'active' : ''}`} onClick={() => { assignProjectToChat(chat.id, p.id); setProjectPickerChat(null); }}>
                            <i className="fas fa-folder"></i> {p.name}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ))}
          </>
        ) : isSidebarCollapsed ? (
          <button type="button" className="history-item active" title={t('currentChat')}><i className="fas fa-comment"></i></button>
        ) : null}
      </div>

      {chatForMenu && menuPos && (
        <div className="chat-context-menu-fixed" style={{ left: menuPos.x, top: menuPos.y }}>
          <ChatContextMenu
            chat={chatForMenu} projects={projects} tr={tr}
            onClose={closeMenu}
            onProjectPicker={() => { setProjectPickerChat(chatForMenu.id); closeMenu(); }}
            onRename={() => { handleRename(chatForMenu.id); closeMenu(); }}
            onDelete={() => { handleDelete(chatForMenu.id); closeMenu(); }}
          />
        </div>
      )}

      <div className="sidebar-footer">
        <div className="user-row">
          <div className="user-avatar" onClick={() => isSidebarCollapsed && setUserMenuOpen(!userMenuOpen)} style={isSidebarCollapsed ? {cursor: 'pointer'} : {}}>
            {user ? (user.name || user.username || '?')[0].toUpperCase() : '?'}
            <div className="user-badge">12</div>
          </div>
          {!isSidebarCollapsed && <>
            <div className="user-info">
              <div className="user-name">{user ? (user.name || user.username || tr('Gast', 'Guest')) : tr('Nicht angemeldet', 'Not signed in')}</div>
              <div className="user-plan">Free</div>
            </div>
            <div className="user-actions">
              <button className="user-action-btn" onClick={() => router.push('/settings')} title={t('settings')}><i className="fas fa-cog"></i></button>
              {user ? (<button className="user-action-btn" onClick={logout} title={tr('Abmelden', 'Logout')}><i className="fas fa-right-from-bracket"></i></button>) : null}
            </div>
          </>}
        </div>
        {userMenuOpen && isSidebarCollapsed && (
          <div className="user-context-menu" onClick={() => setUserMenuOpen(false)}>
            <button onClick={() => router.push('/settings')}><i className="fas fa-cog"></i> {t('settings')}</button>
            {user && <button onClick={logout}><i className="fas fa-right-from-bracket"></i> {tr('Abmelden', 'Logout')}</button>}
          </div>
        )}
        {!isSidebarCollapsed && (
          <div className="status-dots">
            <div className="status-dot-group"><div className={`status-dot ${health.ollama}`} /><span>Ollama</span></div>
            <div className="status-dot-group"><div className={`status-dot ${health.kb}`} /><span>KB</span></div>
            <div className="status-dot-group"><div className={`status-dot ${health.embeddings}`} /><span>Embed</span></div>
          </div>
        )}
      </div>
    </div>
  );
}
