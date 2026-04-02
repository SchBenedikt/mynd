'use client';

import { useEffect, useMemo, useState } from 'react';

const API_BASE = '';

const toIsoDate = (dateObj) => dateObj.toISOString().slice(0, 10);

const shiftDate = (isoDate, deltaDays) => {
  const date = new Date(`${isoDate}T00:00:00`);
  date.setDate(date.getDate() + deltaDays);
  return toIsoDate(date);
};

const shiftByView = (isoDate, view, direction) => {
  if (view === 'week') return shiftDate(isoDate, direction * 7);
  if (view === 'month') {
    const date = new Date(`${isoDate}T00:00:00`);
    date.setMonth(date.getMonth() + direction);
    return toIsoDate(date);
  }
  if (view === 'list') return shiftDate(isoDate, direction * 14);
  return shiftDate(isoDate, direction);
};

const formatDueLabel = (dueDate) => {
  if (!dueDate) return 'No due date';
  const d = new Date(`${dueDate}T00:00:00`);
  if (Number.isNaN(d.getTime())) return dueDate;
  return d.toLocaleDateString('en-GB', { weekday: 'short', day: '2-digit', month: 'short', year: 'numeric' });
};

const formatPhotoDate = (value) => {
  if (!value) return '';
  const dateValue = new Date(value);
  if (Number.isNaN(dateValue.getTime())) return String(value);
  return dateValue.toLocaleDateString('de-DE', { day: '2-digit', month: 'short', year: 'numeric' });
};

export default function ContextDataCard({ card, onQueryAction, onPhotoPreview }) {
  const type = card?.type || 'calendar';

  const [anchorDate, setAnchorDate] = useState(card?.anchor_date || toIsoDate(new Date()));
  const [calendarView, setCalendarView] = useState(card?.default_view || 'day');
  const [taskScope, setTaskScope] = useState(card?.default_scope || 'all');
  const [photoPerson, setPhotoPerson] = useState(card?.selected_people?.[0] || '');
  const [photoDatePhrase, setPhotoDatePhrase] = useState(card?.date_phrase || '');
  const [photoDate, setPhotoDate] = useState(card?.date_from || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [payload, setPayload] = useState(null);

  const [editingKey, setEditingKey] = useState('');
  const [editForm, setEditForm] = useState({});
  const [saving, setSaving] = useState(false);

  const isCalendar = type === 'calendar';
  const isPhoto = type === 'photos';
  const photoItems = card?.photos || [];
  const photoPersonOptions = card?.people_options || [];
  const photoDateOptions = card?.date_options || [];

  useEffect(() => {
    setAnchorDate(card?.anchor_date || toIsoDate(new Date()));
    setCalendarView(card?.default_view || 'day');
    setTaskScope(card?.default_scope || 'all');
    setPhotoPerson(card?.selected_people?.[0] || '');
    setPhotoDatePhrase(card?.date_phrase || '');
    setPhotoDate(card?.date_from || '');
  }, [card]);

  const fetchUrl = useMemo(() => {
    if (isCalendar) {
      const params = new URLSearchParams({ view: calendarView, date: anchorDate });
      return `${API_BASE}/api/calendar/ui?${params.toString()}`;
    }

    const params = new URLSearchParams({ scope: taskScope, date: anchorDate });
    return `${API_BASE}/api/tasks/ui?${params.toString()}`;
  }, [isCalendar, calendarView, taskScope, anchorDate]);

  useEffect(() => {
    if (isPhoto) {
      return undefined;
    }

    let cancelled = false;

    const loadData = async () => {
      setLoading(true);
      setError('');
      try {
        const res = await fetch(fetchUrl);
        const data = await res.json();
        if (!res.ok || data?.success === false) {
          throw new Error(data?.error || `Request failed with status ${res.status}`);
        }
        if (!cancelled) {
          setPayload(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err.message || 'Could not load data.');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadData();
    return () => {
      cancelled = true;
    };
  }, [fetchUrl, isPhoto]);

  const buildPhotoQuery = ({ person = photoPerson, datePhrase = photoDatePhrase, isoDate = photoDate } = {}) => {
    const parts = ['Zeig mir Fotos'];
    if (datePhrase) {
      parts.push(`von ${datePhrase}`);
    } else if (isoDate) {
      parts.push(`am ${isoDate}`);
    }
    if (person) {
      parts.push(`mit ${person}`);
    }
    return parts.join(' ');
  };

  const triggerPhotoSearch = (overrides = {}) => {
    if (!onQueryAction) return;
    onQueryAction(buildPhotoQuery(overrides));
  };

  const handlePhotoPersonSelect = (personName) => {
    setPhotoPerson(personName);
    triggerPhotoSearch({ person: personName });
  };

  const handlePhotoDatePreset = (dateLabel) => {
    setPhotoDatePhrase(dateLabel);
    setPhotoDate('');
    triggerPhotoSearch({ datePhrase: dateLabel, isoDate: '' });
  };

  const onCalendarEdit = (eventItem) => {
    const key = eventItem.uid || eventItem.nextcloud_path || eventItem.summary;
    setEditingKey(key);
    setEditForm({
      key,
      nextcloud_path: eventItem.nextcloud_path || '',
      title: eventItem.summary || '',
      start_time: eventItem.start || '',
      end_time: eventItem.end || '',
      location: eventItem.location || '',
      description: eventItem.description || ''
    });
  };

  const onTaskEdit = (taskItem) => {
    const key = taskItem.uid || taskItem.title;
    setEditingKey(key);
    setEditForm({
      key,
      uid: taskItem.uid,
      list_name: taskItem.list_name || 'tasks',
      title: taskItem.title || '',
      due_date: taskItem.due_date || '',
      description: taskItem.description || '',
      priority: Number(taskItem.priority || 0)
    });
  };

  const closeEdit = () => {
    setEditingKey('');
    setEditForm({});
  };

  const refreshCurrent = async () => {
    const res = await fetch(fetchUrl);
    const data = await res.json();
    if (!res.ok || data?.success === false) {
      throw new Error(data?.error || `Request failed with status ${res.status}`);
    }
    setPayload(data);
  };

  const submitEdit = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');

    try {
      if (isCalendar) {
        const res = await fetch(`${API_BASE}/api/calendar/update`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            nextcloud_path: editForm.nextcloud_path,
            title: editForm.title,
            start_time: editForm.start_time,
            end_time: editForm.end_time,
            location: editForm.location,
            description: editForm.description
          })
        });
        const data = await res.json();
        if (!res.ok || data?.success === false) {
          throw new Error(data?.error || 'Could not update event.');
        }
      } else {
        const res = await fetch(`${API_BASE}/api/tasks/update/${encodeURIComponent(editForm.uid)}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            list_name: editForm.list_name,
            title: editForm.title,
            due_date: editForm.due_date,
            description: editForm.description,
            priority: Number(editForm.priority || 0)
          })
        });
        const data = await res.json();
        if (!res.ok || data?.success === false) {
          throw new Error(data?.error || 'Could not update task.');
        }
      }

      await refreshCurrent();
      closeEdit();
    } catch (err) {
      setError(err.message || 'Save failed.');
    } finally {
      setSaving(false);
    }
  };

  const completeTask = async (taskItem) => {
    try {
      const res = await fetch(`${API_BASE}/api/tasks/complete/${encodeURIComponent(taskItem.uid)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ list_name: taskItem.list_name || 'tasks' })
      });
      const data = await res.json();
      if (!res.ok || data?.error) {
        throw new Error(data?.error || 'Could not complete task.');
      }
      await refreshCurrent();
    } catch (err) {
      setError(err.message || 'Could not complete task.');
    }
  };

  const calendarItems = payload?.events || [];
  const taskItems = payload?.tasks || [];

  const widthVariant = useMemo(() => {
    if (isPhoto) {
      if (photoItems.length >= 4) return 'wide';
      if (photoItems.length >= 2) return 'medium';
      return 'compact';
    }

    if (isCalendar) {
      if (calendarView === 'day' && calendarItems.length <= 3) return 'compact';
      if (calendarView === 'week' || calendarView === 'month' || calendarItems.length >= 8) return 'wide';
      return 'medium';
    }

    if (taskScope === 'today' && taskItems.length <= 4) return 'compact';
    if (taskScope === 'all' || taskItems.length >= 10) return 'wide';
    return 'medium';
  }, [isPhoto, photoItems.length, isCalendar, calendarView, calendarItems.length, taskScope, taskItems.length]);

  return (
    <div className={`context-data-card context-data-card--${widthVariant}`}>
      <div className="context-data-head">
        <div className="context-data-title-wrap">
          <div className="context-data-title">
            {isPhoto ? (card?.title || 'Fotos') : (isCalendar ? 'Calendar Overview' : 'Task Overview')}
          </div>
          <div className="context-data-subtitle">
            {isPhoto
              ? (card?.subtitle || `${photoItems.length} items`)
              : (isCalendar ? (payload?.period_label || 'Loading period...') : `${payload?.count || 0} items`)}
          </div>
        </div>

        {!isPhoto && (
          <div className="context-data-controls">
            {isCalendar ? (
              <>
                <button type="button" className="chip-btn" onClick={() => setCalendarView('day')} aria-pressed={calendarView === 'day'}>
                  Day
                </button>
                <button type="button" className="chip-btn" onClick={() => setCalendarView('week')} aria-pressed={calendarView === 'week'}>
                  Week
                </button>
                <button type="button" className="chip-btn" onClick={() => setCalendarView('month')} aria-pressed={calendarView === 'month'}>
                  Month
                </button>
                <button type="button" className="chip-btn" onClick={() => setCalendarView('list')} aria-pressed={calendarView === 'list'}>
                  List
                </button>
              </>
            ) : (
              <>
                <button type="button" className="chip-btn" onClick={() => setTaskScope('today')} aria-pressed={taskScope === 'today'}>
                  Today
                </button>
                <button type="button" className="chip-btn" onClick={() => setTaskScope('overdue')} aria-pressed={taskScope === 'overdue'}>
                  Overdue
                </button>
                <button type="button" className="chip-btn" onClick={() => setTaskScope('all')} aria-pressed={taskScope === 'all'}>
                  All
                </button>
              </>
            )}
          </div>
        )}
      </div>

      {!isPhoto && (
        <div className="context-data-nav">
          <button
            type="button"
            className="context-nav-btn"
            onClick={() => setAnchorDate((prev) => shiftByView(prev, isCalendar ? calendarView : 'day', -1))}
            aria-label="Previous"
          >
            <i className="fas fa-chevron-left"></i>
          </button>
          <div className="context-data-anchor">{anchorDate}</div>
          <button
            type="button"
            className="context-nav-btn"
            onClick={() => setAnchorDate((prev) => shiftByView(prev, isCalendar ? calendarView : 'day', 1))}
            aria-label="Next"
          >
            <i className="fas fa-chevron-right"></i>
          </button>
        </div>
      )}

      {loading && <div className="context-data-status">Loading…</div>}
      {error && <div className="context-data-error">{error}</div>}

      {isPhoto && !error && (
        <div className="photo-context-body">
          <div className="photo-context-gallery">
            {photoItems.length === 0 && <div className="context-data-empty">Keine Fotos gefunden.</div>}
            {photoItems.map((photo, idx) => {
              const title = photo.original_file_name || `Foto ${idx + 1}`;
              const subtitle = [formatPhotoDate(photo.created_at), photo.people?.[0], photo.location].filter(Boolean).join(' • ');
              return (
                <button
                  type="button"
                  key={photo.id || `${title}-${idx}`}
                  className="photo-thumb-card"
                  onClick={() => {
                    if (onPhotoPreview) {
                      onPhotoPreview({
                        title,
                        thumbnailUrl: photo.thumbnail_url,
                        immichUrl: photo.asset_url,
                        downloadUrl: photo.asset_url
                      });
                    }
                  }}
                >
                  <img src={photo.thumbnail_url} alt={title} />
                  <span className="photo-thumb-title">{title}</span>
                  {subtitle && <span className="photo-thumb-subtitle">{subtitle}</span>}
                </button>
              );
            })}
          </div>

          <div className="photo-context-controls">
            <div className="photo-context-section">
              <div className="photo-context-section-label">Andere Personen</div>
              <div className="photo-chip-row">
                {photoPersonOptions.length === 0 && <div className="context-data-empty small">Keine alternativen Personen verfügbar.</div>}
                {photoPersonOptions.map((name) => (
                  <button
                    type="button"
                    key={name}
                    className="chip-btn photo-chip"
                    aria-pressed={photoPerson === name}
                    onClick={() => handlePhotoPersonSelect(name)}
                  >
                    {name}
                  </button>
                ))}
              </div>
              <div className="photo-input-row">
                <input
                  type="text"
                  value={photoPerson}
                  onChange={(e) => setPhotoPerson(e.target.value)}
                  placeholder="Andere Person eingeben"
                />
              </div>
            </div>

            <div className="photo-context-section">
              <div className="photo-context-section-label">Anderes Datum</div>
              <div className="photo-chip-row">
                {photoDateOptions.map((option) => (
                  <button
                    type="button"
                    key={option.value}
                    className="chip-btn photo-chip"
                    aria-pressed={photoDatePhrase === option.value}
                    onClick={() => handlePhotoDatePreset(option.value)}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
              <div className="photo-input-row">
                <input
                  type="date"
                  value={photoDate}
                  onChange={(e) => {
                    setPhotoDate(e.target.value);
                    setPhotoDatePhrase('');
                  }}
                />
                <button type="button" className="btn primary" onClick={() => triggerPhotoSearch()}>
                  Neue Suche
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {!isPhoto && !loading && !error && isCalendar && (
        <div className="context-data-list">
          {calendarItems.length === 0 && <div className="context-data-empty">No events in this range.</div>}
          {calendarItems.map((eventItem, idx) => {
            const key = eventItem.uid || eventItem.nextcloud_path || `${eventItem.summary}-${idx}`;
            const editing = editingKey === key;
            return (
              <div key={key} className="context-item calendar-item">
                <div className="context-item-main">
                  <div className="context-item-title">{eventItem.summary || 'Untitled event'}</div>
                  <div className="context-item-meta">
                    {eventItem.start || '-'}
                    {eventItem.end ? ` to ${eventItem.end}` : ''}
                    {eventItem.calendar ? ` • ${eventItem.calendar}` : ''}
                    {eventItem.location ? ` • ${eventItem.location}` : ''}
                  </div>
                </div>
                <button type="button" className="context-item-action" onClick={() => onCalendarEdit(eventItem)}>
                  Edit
                </button>

                {editing && (
                  <form className="context-edit-form" onSubmit={submitEdit}>
                    <input
                      type="text"
                      value={editForm.title || ''}
                      onChange={(e) => setEditForm((prev) => ({ ...prev, title: e.target.value }))}
                      placeholder="Title"
                      required
                    />
                    <input
                      type="text"
                      value={editForm.start_time || ''}
                      onChange={(e) => setEditForm((prev) => ({ ...prev, start_time: e.target.value }))}
                      placeholder="Start (DD.MM.YYYY HH:MM)"
                      required
                    />
                    <input
                      type="text"
                      value={editForm.end_time || ''}
                      onChange={(e) => setEditForm((prev) => ({ ...prev, end_time: e.target.value }))}
                      placeholder="End (optional)"
                    />
                    <input
                      type="text"
                      value={editForm.location || ''}
                      onChange={(e) => setEditForm((prev) => ({ ...prev, location: e.target.value }))}
                      placeholder="Location"
                    />
                    <input
                      type="text"
                      value={editForm.description || ''}
                      onChange={(e) => setEditForm((prev) => ({ ...prev, description: e.target.value }))}
                      placeholder="Description"
                    />
                    <div className="context-edit-actions">
                      <button type="button" className="btn" onClick={closeEdit} disabled={saving}>Cancel</button>
                      <button type="submit" className="btn primary" disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
                    </div>
                  </form>
                )}
              </div>
            );
          })}
        </div>
      )}

      {!isPhoto && !loading && !error && !isCalendar && (
        <div className="context-data-list">
          {taskItems.length === 0 && <div className="context-data-empty">No tasks for this scope.</div>}
          {taskItems.map((taskItem, idx) => {
            const key = taskItem.uid || `${taskItem.title}-${idx}`;
            const editing = editingKey === key;
            return (
              <div key={key} className="context-item task-item">
                <div className="context-item-main">
                  <div className="context-item-title">{taskItem.title || 'Untitled task'}</div>
                  <div className="context-item-meta">
                    {formatDueLabel(taskItem.due_date)}
                    {taskItem.list_name ? ` • ${taskItem.list_name}` : ''}
                    {taskItem.priority ? ` • P${taskItem.priority}` : ''}
                  </div>
                </div>
                <div className="context-item-actions-row">
                  <button type="button" className="context-item-action" onClick={() => onTaskEdit(taskItem)}>
                    Edit
                  </button>
                  <button type="button" className="context-item-action success" onClick={() => completeTask(taskItem)}>
                    Done
                  </button>
                </div>

                {editing && (
                  <form className="context-edit-form" onSubmit={submitEdit}>
                    <input
                      type="text"
                      value={editForm.title || ''}
                      onChange={(e) => setEditForm((prev) => ({ ...prev, title: e.target.value }))}
                      placeholder="Title"
                      required
                    />
                    <input
                      type="date"
                      value={editForm.due_date || ''}
                      onChange={(e) => setEditForm((prev) => ({ ...prev, due_date: e.target.value }))}
                    />
                    <input
                      type="number"
                      min="0"
                      max="9"
                      value={editForm.priority ?? 0}
                      onChange={(e) => setEditForm((prev) => ({ ...prev, priority: Number(e.target.value) }))}
                      placeholder="Priority"
                    />
                    <input
                      type="text"
                      value={editForm.description || ''}
                      onChange={(e) => setEditForm((prev) => ({ ...prev, description: e.target.value }))}
                      placeholder="Description"
                    />
                    <div className="context-edit-actions">
                      <button type="button" className="btn" onClick={closeEdit} disabled={saving}>Cancel</button>
                      <button type="submit" className="btn primary" disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
                    </div>
                  </form>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
