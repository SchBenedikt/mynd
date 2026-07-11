'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useTheme } from '../../hooks/useTheme';
import { useLanguage } from '../../hooks/useLanguage';
import { useSidebar } from '../../hooks/useSidebar';

const SIDEBAR_COLLAPSED_KEY = 'mynd_sidebar_collapsed_v1';
const PROJECTS_STORAGE_KEY = 'mynd_projects_v1';
const CHAT_STORAGE_KEY = 'mynd_chat_history_v1';
const ACTIVE_CHAT_STORAGE_KEY = 'mynd_active_chat_v1';

function loadChats() {
  try {
    const raw = localStorage.getItem(CHAT_STORAGE_KEY);
    if (raw) { const parsed = JSON.parse(raw); return Array.isArray(parsed) ? parsed : []; }
  } catch(e) {}
  return [];
}

export default function ProjectsPage() {
  const router = useRouter();
  const { theme, darkMode, setTheme, setDarkMode } = useTheme();
  const { language, setLanguage, t, languages } = useLanguage();
  const tr = (deText, enText) => (language === 'de' ? deText : enText);

  const { isSidebarCollapsed, toggleSidebar, canAnimate } = useSidebar();
  const [projects, setProjects] = useState([]);
  const [chats, setChats] = useState(loadChats);
  const [activeProject, setActiveProject] = useState(null);
  const [newProjectName, setNewProjectName] = useState('');
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [menuChat, setMenuChat] = useState(null);

  function getChatGroups(chats) {
    const dayMs = 86400000;
    const groups = { today: [], yesterday: [], week: [], month: [], older: [] };
    const today = new Date(); today.setHours(0,0,0,0);
    const todayStart = today.getTime();
    const yesterdayStart = todayStart - dayMs;
    const weekStart = todayStart - 7 * dayMs;
    const monthStart = todayStart - 30 * dayMs;
    [...chats].sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0)).forEach(c => {
      const t = c.updatedAt || 0;
      if (t >= todayStart) groups.today.push(c);
      else if (t >= yesterdayStart) groups.yesterday.push(c);
      else if (t >= weekStart) groups.week.push(c);
      else if (t >= monthStart) groups.month.push(c);
      else groups.older.push(c);
    });
    return groups;
  }

  const groupLabels = {
    today: language === 'de' ? 'Heute' : 'Today',
    yesterday: language === 'de' ? 'Gestern' : 'Yesterday',
    week: language === 'de' ? 'Letzte 7 Tage' : 'Last 7 days',
    month: language === 'de' ? 'Letzte 30 Tage' : 'Last 30 days',
    older: language === 'de' ? 'Älter' : 'Older'
  };

  useEffect(() => {
    const close = () => setMenuChat(null);
    document.addEventListener('click', close);
    return () => document.removeEventListener('click', close);
  }, []);

  useEffect(() => {
    const pRaw = localStorage.getItem(PROJECTS_STORAGE_KEY);
    if (pRaw) try { setProjects(JSON.parse(pRaw)); } catch(e) {}
  }, []);

  const createProject = () => {
    const name = newProjectName.trim();
    if (!name) return;
    setProjects(prev => [...prev, { id: Date.now().toString(), name }]);
    setNewProjectName('');
  };

  const renameProject = (id) => {
    const p = projects.find(pp => pp.id === id);
    const name = window.prompt(tr('Neuer Name:', 'New name:'), p?.name || '');
    if (name && name.trim()) {
      setProjects(prev => prev.map(pp => pp.id === id ? { ...pp, name: name.trim() } : pp));
    }
  };

  const deleteProject = (id) => {
    const p = projects.find(pp => pp.id === id);
    if (!window.confirm(tr(`Projekt "${p?.name}" löschen?`, `Delete project "${p?.name}"?`))) return;
    setProjects(prev => prev.filter(pp => pp.id !== id));
    setChats(prev => prev.map(c => c.project === id ? { ...c, project: null } : c));
    if (activeProject === id) setActiveProject(null);
  };

  const filteredChats = activeProject ? chats.filter(c => c.project === activeProject) : [];

  useEffect(() => {
    try { localStorage.setItem(PROJECTS_STORAGE_KEY, JSON.stringify(projects)); } catch(e) {}
  }, [projects]);

  return (
    <div className={`container ${isSidebarCollapsed ? 'sidebar-collapsed' : ''}${!canAnimate ? ' no-animate' : ''}`}>
      <div className={`left-sidebar ${isSidebarCollapsed ? 'collapsed' : ''}`}>
        <div className="sidebar-header">
          <button type="button" className="brand" onClick={toggleSidebar}>
            {isSidebarCollapsed ? <span style={{fontSize:'1.4rem',lineHeight:1}}>🧠</span> : 'MYND'}
          </button>
        </div>

        <div className="primary-nav">
          <button className="nav-item" onClick={() => router.push('/')} title={t('newChat')}>
            <i className="fas fa-pen"></i>
            <span>{t('newChat')}</span>
          </button>
          <button className="nav-item" onClick={() => router.push('/')} title={tr('Chats durchsuchen', 'Search chats')}>
            <i className="fas fa-search"></i>
            <span>{tr('Chats durchsuchen', 'Search chats')}</span>
          </button>
          <button className="nav-item active" onClick={() => router.push('/projects')} title={tr('Projekte', 'Projects')}>
            <i className="fas fa-folder"></i>
            <span>{tr('Projekte', 'Projects')}</span>
          </button>
        </div>

        <div className="chat-history">
          {isSidebarCollapsed ? (
            <button type="button" className="history-item active" onClick={() => router.push('/')} title={t('currentChat')}>
              <i className="fas fa-comment"></i>
            </button>
          ) : chats.length === 0 ? (
            <div className="history-item" onClick={() => router.push('/')}>
              <i className="fas fa-comment"></i>
              <span className="history-title">{t('currentChat')}</span>
            </div>
          ) : (() => {
            const groups = getChatGroups(chats);
            return Object.entries(groups).map(([key, items]) =>
              items.length > 0 ? (
                <div key={key} className="history-group">
                  <div className="section-label">{groupLabels[key]}</div>
                  {items.map(c => (
                    <div key={c.id} className="history-item"
                      onClick={() => { try { localStorage.setItem(ACTIVE_CHAT_STORAGE_KEY, c.id); } catch(e) {} router.push('/'); }}
                      role="button" tabIndex={0} title={c.title}>
                      <i className="fas fa-comment"></i>
                      <span className="history-title">{c.title}</span>
                      <div className="history-actions" onClick={e => e.stopPropagation()}>
                        <button type="button" className="history-action dots" onClick={e => { e.stopPropagation(); setMenuChat(menuChat === c.id ? null : c.id); }}>
                          <i className="fas fa-ellipsis-v"></i>
                        </button>
                        {menuChat === c.id && (
                          <div className="chat-context-menu" onClick={e => e.stopPropagation()}>
                            <button onClick={e => { e.stopPropagation(); try { localStorage.setItem(ACTIVE_CHAT_STORAGE_KEY, c.id); } catch(ex) {} setMenuChat(null); router.push('/'); }}>
                              <i className="fas fa-external-link-alt"></i> {tr('Öffnen', 'Open')}
                            </button>
                            <button className="danger" onClick={e => { e.stopPropagation(); setMenuChat(null); setChats(prev => { const next = prev.filter(x => x.id !== c.id); try { localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(next)); } catch(ex) {} return next; }); }}>
                              <i className="fas fa-trash"></i> {tr('Löschen', 'Delete')}
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : null
            );
          })()}
        </div>

        <div className="sidebar-footer">
          <div className="user-row">
            <div className="user-avatar" onClick={() => isSidebarCollapsed && setUserMenuOpen(!userMenuOpen)} style={isSidebarCollapsed ? {cursor: 'pointer'} : {}}>
              M
              <div className="user-badge">12</div>
            </div>
            {!isSidebarCollapsed && <>
              <div className="user-info">
                <div className="user-name">{tr('Projekte', 'Projects')}</div>
                <div className="user-plan">Free</div>
              </div>
              <div className="user-actions">
                <button className="user-action-btn" onClick={() => router.push('/settings')} title={t('settings')}>
                  <i className="fas fa-cog"></i>
                </button>
              </div>
            </>}
          </div>
          {userMenuOpen && isSidebarCollapsed && (
            <div className="user-context-menu" onClick={() => setUserMenuOpen(false)}>
              <button onClick={() => router.push('/')}><i className="fas fa-comment"></i> {tr('Chats', 'Chats')}</button>
              <button onClick={() => router.push('/settings')}><i className="fas fa-cog"></i> {t('settings')}</button>
            </div>
          )}
          {!isSidebarCollapsed && (
            <div className="status-dots">
              <div className="status-dot-group">
                <div className="status-dot unknown" />
                <span>Ollama</span>
              </div>
              <div className="status-dot-group">
                <div className="status-dot unknown" />
                <span>KB</span>
              </div>
              <div className="status-dot-group">
                <div className="status-dot unknown" />
                <span>Embed</span>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="center-area" style={{padding: '2rem', overflowY: 'auto'}}>
        <div className="page-header">
          <h1>{tr('Projekte', 'Projects')}</h1>
          <p className="page-sub">{tr('Organisiere deine Chats in Projekten.', 'Organize your chats into projects.')}</p>
        </div>

        <div className="project-create-card">
          <input
            type="text"
            placeholder={tr('Neues Projekt anlegen...', 'Create new project...')}
            value={newProjectName}
            onChange={(e) => setNewProjectName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && createProject()}
          />
          <button className="btn primary" onClick={createProject} disabled={!newProjectName.trim()}>
            {tr('Anlegen', 'Create')}
          </button>
        </div>

        {projects.length === 0 ? (
          <div className="projects-empty">
            <i className="fas fa-folder-open"></i>
            <p>{tr('Noch keine Projekte. Lege ein neues Projekt an.', 'No projects yet. Create a new project.')}</p>
          </div>
        ) : (
          <div className="projects-grid">
            {projects.map(p => (
              <div key={p.id} className={`project-card ${activeProject === p.id ? 'active' : ''}`}>
                <div className="project-card-head" onClick={() => setActiveProject(activeProject === p.id ? null : p.id)}>
                  <i className="fas fa-folder"></i>
                  <span className="project-card-name">{p.name}</span>
                  <span className="project-card-count">{chats.filter(c => c.project === p.id).length}</span>
                </div>
                <div className="project-card-acts">
                  <button className="project-card-btn" onClick={() => renameProject(p.id)} title={tr('Umbenennen', 'Rename')}>
                    <i className="fas fa-pen"></i>
                  </button>
                  <button className="project-card-btn del" onClick={() => deleteProject(p.id)} title={tr('Löschen', 'Delete')}>
                    <i className="fas fa-trash"></i>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {activeProject && (
          <div className="project-chats-section">
            <div className="project-chats-header">
              <h3>
                <i className="fas fa-folder-open"></i>
                {projects.find(p => p.id === activeProject)?.name}
              </h3>
              <button className="btn outline" onClick={() => setActiveProject(null)}>
                {tr('Filter aufheben', 'Clear filter')}
              </button>
            </div>
            {filteredChats.length === 0 ? (
              <div className="projects-empty" style={{padding: '1.5rem'}}>
                <p>{tr('Keine Chats in diesem Projekt.', 'No chats in this project.')}</p>
              </div>
            ) : (
              <div className="project-chat-list">
                {filteredChats.map(c => (
                  <div key={c.id} className="project-chat-row" onClick={() => router.push('/')}>
                    <i className="fas fa-comment"></i>
                    <span className="project-chat-title">{c.title}</span>
                    <span className="project-chat-date">
                      {c.updatedAt ? new Date(c.updatedAt).toLocaleDateString(language === 'de' ? 'de-DE' : 'en-US') : ''}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
