'use client';

import { useState, useEffect, useRef } from 'react';

export default function SearchPopup({ open, onClose, chats, projects, onOpenChat, language, tr }) {
  const [query, setQuery] = useState('');
  const inputRef = useRef(null);
  const popupRef = useRef(null);

  useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus();
      setQuery('');
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (popupRef.current && !popupRef.current.contains(e.target)) onClose();
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

  if (!open) return null;

  const filtered = query.trim()
    ? chats.filter(c => c.title.toLowerCase().includes(query.toLowerCase()))
    : chats;

  return (
    <div className="search-popup" ref={popupRef}>
      <div className="search-popup-header">
        <i className="fas fa-search"></i>
        <input
          ref={inputRef}
          type="text"
          placeholder={tr('Chat-Titel eingeben...', 'Type a chat title...')}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      <div className="search-popup-body">
        {filtered.length > 0 ? filtered.map(c => {
          const lastMsg = c.messages && c.messages.length > 0 ? c.messages[c.messages.length - 1].content : '';
          const lastDate = c.updatedAt ? new Date(c.updatedAt).toLocaleDateString(language === 'de' ? 'de-DE' : 'en-US', { month: 'short', day: 'numeric' }) : '';
          const proj = c.project ? projects.find(p => p.id === c.project) : null;
          return (
            <div key={c.id} className="search-popup-row" onClick={() => { onOpenChat(c.id); onClose(); }}>
              <div className="search-popup-row-icon"><i className="fas fa-comment"></i></div>
              <div className="search-popup-row-body">
                <div className="search-popup-row-top">
                  <span className="search-popup-row-title">{c.title}</span>
                  <span className="search-popup-row-date">{lastDate}</span>
                </div>
                <div className="search-popup-row-sub">
                  {proj && <span className="search-popup-row-tag">{proj.name}</span>}
                  <span className="search-popup-row-preview">{lastMsg ? lastMsg.slice(0, 60) : ''}</span>
                </div>
              </div>
            </div>
          );
        }) : (
          <div className="search-popup-empty">
            <p>{tr('Keine Chats gefunden', 'No chats found')}</p>
          </div>
        )}
      </div>
    </div>
  );
}
