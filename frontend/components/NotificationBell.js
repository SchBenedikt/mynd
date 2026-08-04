'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { apiFetch } from '../lib/api';
import { useLanguage } from '../hooks/useLanguage';

const POLL_MS = 10000;
const TOAST_DURATION = 9000;
const SEEN_KEY = 'mynd_notif_seen_v1';

function timeAgo(iso, language) {
  if (!iso) return '';
  try {
    const diff = Date.now() - new Date(iso).getTime();
    const min = Math.floor(diff / 60000);
    if (min < 1) return language === 'de' ? 'gerade eben' : 'just now';
    if (min < 60) return language === 'de' ? `vor ${min} Min.` : `${min} min ago`;
    const hr = Math.floor(min / 60);
    if (hr < 24) return language === 'de' ? `vor ${hr} Std.` : `${hr} h ago`;
    const d = Math.floor(hr / 24);
    if (d < 7) return language === 'de' ? `vor ${d} Tagen` : `${d} days ago`;
    const w = Math.floor(d / 7);
    if (w < 5) return language === 'de' ? `vor ${w} Wo.` : `${w} wk ago`;
    return new Date(iso).toLocaleDateString(language === 'de' ? 'de-DE' : 'en-US', {
      day: '2-digit', month: 'short', year: 'numeric',
    });
  } catch (e) {
    return '';
  }
}

function guessType(notification) {
  const haystack = `${notification.title || ''} ${notification.content || ''}`.toLowerCase();
  if (/(foto|immich|kamera|bild|photo|album)/.test(haystack)) return 'photo';
  if (/(e-?mail|betreff|@)/.test(haystack)) return 'email';
  if (/(automation|automation abgeschlossen|schritt|workflow|skript)/.test(haystack)) return 'automation';
  if (/(calendar|termin|kalender|erinnerung|reminder)/.test(haystack)) return 'calendar';
  if (/(briefing|tagesbriefing|morgenbriefing)/.test(haystack)) return 'briefing';
  if (/(fehler|error|failed|gescheitert)/.test(haystack)) return 'error';
  return 'default';
}

function typeIcon(type) {
  switch (type) {
    case 'photo': return 'fa-camera';
    case 'email': return 'fa-envelope';
    case 'automation': return 'fa-diagram-project';
    case 'error': return 'fa-triangle-exclamation';
    case 'briefing': return 'fa-sun';
    case 'calendar': return 'fa-calendar';
    default: return 'fa-bell';
  }
}

function loadSeenIds() {
  try {
    return new Set(JSON.parse(sessionStorage.getItem(SEEN_KEY) || '[]'));
  } catch (e) {
    return new Set();
  }
}

function saveSeenIds(ids) {
  try {
    sessionStorage.setItem(SEEN_KEY, JSON.stringify([...ids]));
  } catch (e) {}
}

export default function NotificationBell() {
  const { language } = useLanguage();
  const tr = useCallback((de, en) => (language === 'de' ? de : en), [language]);
  const [notifications, setNotifications] = useState([]);
  const [toasts, setToasts] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const wrapRef = useRef(null);
  const seenRef = useRef(loadSeenIds());
  const toastTimersRef = useRef({});

  const dismissToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    if (toastTimersRef.current[id]) {
      clearTimeout(toastTimersRef.current[id]);
      delete toastTimersRef.current[id];
    }
  }, []);

  const pushToast = useCallback((notification) => {
    setToasts((prev) => {
      if (prev.some((t) => t.id === notification.id)) return prev;
      const next = [...prev, notification].slice(-4);
      return next;
    });
    if (toastTimersRef.current[notification.id]) clearTimeout(toastTimersRef.current[notification.id]);
    toastTimersRef.current[notification.id] = setTimeout(() => dismissToast(notification.id), TOAST_DURATION);
  }, [dismissToast]);

  const load = useCallback(async (opts = {}) => {
    const { announceNew = false } = opts;
    try {
      const res = await apiFetch('/api/notifications/latest?limit=50');
      const data = await res.json();
      if (!res.ok || data?.success === false) throw new Error('bad');
      const items = Array.isArray(data.notifications) ? data.notifications : [];
      const fresh = new Set(seenRef.current);
      const newlySeen = [];
      for (const n of items) {
        if (n.read) continue;
        if (!fresh.has(n.id)) {
          fresh.add(n.id);
          newlySeen.push(n);
        }
      }
      if (announceNew && newlySeen.length > 0) {
        newlySeen.slice(0, 4).forEach(pushToast);
      }
      seenRef.current = fresh;
      saveSeenIds(fresh);
      setNotifications(items);
      setError(false);
    } catch (e) {
      setError(true);
    }
  }, [pushToast]);

  useEffect(() => {
    load({ announceNew: true });
    const iv = setInterval(() => load({ announceNew: true }), POLL_MS);
    const timers = toastTimersRef.current;
    return () => {
      clearInterval(iv);
      Object.values(timers).forEach(clearTimeout);
    };
  }, [load]);

  const markAllRead = useCallback(async () => {
    const unread = notifications.filter((n) => !n.read).map((n) => n.id);
    if (unread.length === 0) return;
    try {
      await apiFetch('/api/notifications/read', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: unread }),
      });
    } catch (e) {}
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, [notifications]);

  const markRead = useCallback(async (id) => {
    try {
      await apiFetch('/api/notifications/read', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: [id] }),
      });
    } catch (e) {}
    setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)));
  }, []);

  const clearAll = useCallback(async () => {
    if (notifications.length === 0) return;
    if (!window.confirm(tr('Alle Benachrichtigungen löschen?', 'Clear all notifications?'))) return;
    try {
      await apiFetch('/api/notifications/clear', { method: 'POST' });
    } catch (e) {}
    setNotifications([]);
    setToasts([]);
  }, [notifications, tr]);

  useEffect(() => {
    if (!open) return;
    const onClick = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    const onKey = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const unreadCount = notifications.filter((n) => !n.read).length;

  const grouped = useCallback(() => {
    const now = Date.now();
    const groups = [];
    const byKey = {};
    for (const n of notifications) {
      const t = n.created_at ? new Date(n.created_at).getTime() : now;
      const dayDiff = Math.floor((now - t) / 86400000);
      let key;
      if (dayDiff < 1) key = tr('Heute', 'Today');
      else if (dayDiff < 2) key = tr('Gestern', 'Yesterday');
      else if (dayDiff < 7) key = tr('Diese Woche', 'This week');
      else key = tr('Älter', 'Older');
      if (!byKey[key]) { byKey[key] = []; groups.push(key); }
      byKey[key].push(n);
    }
    return groups.map((label) => ({ label, items: byKey[label] }));
  }, [notifications, tr]);

  return (
    <>
      <div className="notification-bell-wrap" ref={wrapRef}>
        <button
          type="button"
          className="user-action-btn notification-bell-btn"
          onClick={() => {
            const next = !open;
            setOpen(next);
            if (next) { setLoading(true); load().finally(() => setLoading(false)); }
          }}
          title={tr('Benachrichtigungen', 'Notifications')}
          aria-haspopup="true"
          aria-expanded={open}
        >
          <i className={`fas fa-bell${unreadCount > 0 ? '' : ' fa-regular'}`} />
          {unreadCount > 0 && <span className="notification-badge">{unreadCount > 9 ? '9+' : unreadCount}</span>}
        </button>

        {open && (
          <div className="notification-dropdown" role="menu">
            <div className="notification-dropdown-header">
              <span className="notification-dropdown-title">
                <i className="fas fa-bell" />
                {tr('Benachrichtigungen', 'Notifications')}
                {unreadCount > 0 && <span className="notification-count-chip">{unreadCount}</span>}
              </span>
              <div className="notification-dropdown-actions">
                <button type="button" onClick={markAllRead} disabled={unreadCount === 0}>
                  {tr('Alle gelesen', 'Mark all read')}
                </button>
                <button type="button" onClick={clearAll} disabled={notifications.length === 0}>
                  {tr('Löschen', 'Clear')}
                </button>
              </div>
            </div>
            <div className="notification-dropdown-list">
              {loading && notifications.length === 0 ? (
                <div className="notification-empty">
                  <div className="notification-spinner" />
                  <span>{tr('Lade...', 'Loading...')}</span>
                </div>
              ) : error && notifications.length === 0 ? (
                <div className="notification-empty notification-error">
                  <i className="fas fa-plug-circle-xmark"></i>
                  <span>{tr('Benachrichtigungen nicht verfügbar.', 'Notifications unavailable.')}</span>
                </div>
              ) : notifications.length === 0 ? (
                <div className="notification-empty">
                  <i className="fas fa-bell-slash"></i>
                  <span>{tr('Keine Benachrichtigungen.', 'No notifications.')}</span>
                </div>
              ) : (
                grouped().map((group) => (
                  <div className="notification-group" key={group.label}>
                    <div className="notification-group-label">{group.label}</div>
                    {group.items.map((n) => {
                      const type = guessType(n);
                      return (
                        <div key={n.id} className={`notification-item${n.read ? '' : ' unread'}`}
                          onClick={() => { if (!n.read) markRead(n.id); }}>
                          <div className={`notification-item-icon type-${type}`}>
                            <i className={`fas ${typeIcon(type)}`} />
                          </div>
                          <div className="notification-item-body">
                            <div className="notification-item-title">{n.title || tr('Benachrichtigung', 'Notification')}</div>
                            {n.content && <div className="notification-item-content">{n.content}</div>}
                            <div className="notification-item-time">
                              <i className="fas fa-clock" />
                              {timeAgo(n.created_at, language)}
                            </div>
                          </div>
                          {!n.read && <span className="notification-dot" />}
                        </div>
                      );
                    })}
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>

      {toasts.length > 0 && (
        <div className="notification-toast-layer" aria-live="polite">
          {toasts.map((n) => {
            const type = guessType(n);
            return (
              <div key={n.id} className="notification-toast">
                <div className={`notification-toast-icon type-${type}`}>
                  <i className={`fas ${typeIcon(type)}`} />
                </div>
                <div className="notification-toast-body">
                  <div className="notification-toast-title">{n.title || tr('Neue Benachrichtigung', 'New notification')}</div>
                  {n.content && <div className="notification-toast-content">{n.content}</div>}
                  <div className="notification-toast-time">
                    <i className="fas fa-clock" />
                    {timeAgo(n.created_at, language)}
                  </div>
                </div>
                <button type="button" className="notification-toast-close" onClick={() => dismissToast(n.id)} aria-label="Close">
                  <i className="fas fa-xmark" />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
