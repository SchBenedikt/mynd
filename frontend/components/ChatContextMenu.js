'use client';

import { useRef, useEffect } from 'react';

export default function ChatContextMenu({
  chat, projects, onClose,
  onProjectPicker, onRename, onDelete, tr
}) {
  const proj = chat.project ? projects.find(p => p.id === chat.project) : null;
  const ref = useRef(null);

  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) onClose();
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  return (
    <div className="chat-context-menu" ref={ref} onClick={e => e.stopPropagation()}>
      <div className="chat-context-menu-header">
        <i className="fas fa-comment"></i>
        <span className="chat-context-menu-header-title">{chat.title}</span>
      </div>
      <div className="chat-context-menu-body">
        <button className="chat-context-menu-row" onClick={onProjectPicker}>
          <div className="chat-context-menu-row-icon"><i className="fas fa-folder"></i></div>
          <div className="chat-context-menu-row-body">
            <span className="chat-context-menu-row-title">{tr('Projekt', 'Project')}</span>
            <span className="chat-context-menu-row-sub">{proj ? proj.name : tr('Kein Projekt', 'No project')}</span>
          </div>
        </button>
        <button className="chat-context-menu-row" onClick={onRename}>
          <div className="chat-context-menu-row-icon"><i className="fas fa-pen"></i></div>
          <div className="chat-context-menu-row-body">
            <span className="chat-context-menu-row-title">{tr('Umbenennen', 'Rename')}</span>
            <span className="chat-context-menu-row-sub">{tr('Neuen Titel vergeben', 'Set a new title')}</span>
          </div>
        </button>
        <button className="chat-context-menu-row danger" onClick={onDelete}>
          <div className="chat-context-menu-row-icon"><i className="fas fa-trash"></i></div>
          <div className="chat-context-menu-row-body">
            <span className="chat-context-menu-row-title">{tr('Löschen', 'Delete')}</span>
            <span className="chat-context-menu-row-sub">{tr('Chat dauerhaft entfernen', 'Permanently remove chat')}</span>
          </div>
        </button>
      </div>
    </div>
  );
}
