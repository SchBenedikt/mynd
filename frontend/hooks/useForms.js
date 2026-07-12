'use client';

import { useState, useCallback } from 'react';
import { createMessageId, safeReadJson, parseBackendDateTimeToInput, formatDateTimeForBackend } from '../lib/pageUtils';
import { apiFetch } from '../lib/api';

const defaultCalendarForm = {
  visible: false, missingInfo: [], title: '', startTime: '', endTime: '',
  calendarName: '', location: '', description: '', availableCalendars: [],
  submitting: false, error: ''
};

const defaultTaskForm = {
  visible: false, missingInfo: [], title: '', dueDate: '', priority: 0,
  listName: '', location: '', description: '', availableTaskLists: [],
  submitting: false, error: ''
};

const defaultIntegrationForm = {
  visible: false, provider: '', feature: '', title: '', description: '',
  fields: [], values: {}, quickActions: [], submitEndpoint: '',
  originalPrompt: '', submitting: false, loginFlowRunning: false, error: ''
};

export function useForms({ activeChatId, appendMessageToChat, sendMessage }) {
  const [calendarForm, setCalendarForm] = useState(defaultCalendarForm);
  const [taskForm, setTaskForm] = useState(defaultTaskForm);
  const [integrationForm, setIntegrationForm] = useState(defaultIntegrationForm);

  const resetCalendarForm = useCallback(() => setCalendarForm(defaultCalendarForm), []);
  const resetTaskForm = useCallback(() => setTaskForm(defaultTaskForm), []);
  const resetIntegrationForm = useCallback(() => setIntegrationForm(defaultIntegrationForm), []);

  const submitCalendarForm = useCallback(async (e) => {
    e.preventDefault();
    if (!calendarForm.title.trim() || !calendarForm.startTime) {
      setCalendarForm(prev => ({ ...prev, error: 'Bitte mindestens Titel und Startzeit ausfuellen.' }));
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
      const res = await apiFetch('/api/calendar/create-with-details', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!res.ok || !data?.success) {
        setCalendarForm(prev => ({ ...prev, submitting: false, error: data?.error || 'Termin konnte nicht erstellt werden.' }));
        return;
      }
      if (activeChatId) {
        appendMessageToChat(activeChatId, { role: 'assistant', content: data.message || 'Termin wurde erstellt.', id: createMessageId() });
      }
      setCalendarForm(defaultCalendarForm);
    } catch (err) {
      setCalendarForm(prev => ({ ...prev, submitting: false, error: `Fehler beim Erstellen: ${err.message}` }));
    }
  }, [calendarForm, activeChatId, appendMessageToChat]);

  const closeCalendarForm = useCallback(() => {
    setCalendarForm(prev => ({ ...prev, visible: false, error: '' }));
  }, []);

  const submitTaskForm = useCallback(async (e) => {
    e.preventDefault();
    if (!taskForm.title.trim()) {
      setTaskForm(prev => ({ ...prev, error: 'Please provide at least a title.' }));
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
      const res = await apiFetch('/api/tasks/create-with-details', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
      });
      const data = await safeReadJson(res);
      if (!res.ok || !data?.success) {
        setTaskForm(prev => ({ ...prev, submitting: false, error: data?.error || 'Task could not be created.' }));
        return;
      }
      if (activeChatId) {
        appendMessageToChat(activeChatId, { role: 'assistant', content: data.message || 'Task created.', id: createMessageId() });
      }
      setTaskForm(defaultTaskForm);
    } catch (err) {
      setTaskForm(prev => ({ ...prev, submitting: false, error: `Error while creating task: ${err.message}` }));
    }
  }, [taskForm, activeChatId, appendMessageToChat]);

  const closeTaskForm = useCallback(() => {
    setTaskForm(prev => ({ ...prev, visible: false, error: '' }));
  }, []);

  const closeIntegrationForm = useCallback(() => {
    setIntegrationForm(prev => ({ ...prev, visible: false, submitting: false, loginFlowRunning: false, error: '' }));
  }, []);

  const runNextcloudLoginFlow = useCallback(async () => {
    const nextcloudUrl = String(integrationForm.values?.nextcloud_url || '').trim();
    if (!nextcloudUrl) {
      setIntegrationForm(prev => ({ ...prev, error: 'Please enter your Nextcloud URL first.' }));
      return;
    }
    setIntegrationForm(prev => ({ ...prev, loginFlowRunning: true, error: '' }));
    try {
      const startRes = await apiFetch('/api/nextcloud/loginflow/start', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nextcloud_url: nextcloudUrl })
      });
      const startData = await safeReadJson(startRes);
      if (!startRes.ok) {
        setIntegrationForm(prev => ({ ...prev, loginFlowRunning: false, error: startData?.error || 'Could not start Nextcloud login flow.' }));
        return;
      }
      if (startData?.login_url) window.open(startData.login_url, '_blank', 'noopener,noreferrer');
      const result = await new Promise((resolve) => {
        let attempts = 0;
        const maxAttempts = 120;
        const pollInterval = setInterval(async () => {
          attempts += 1;
          try {
            const pollRes = await apiFetch('/api/nextcloud/loginflow/poll');
            const pollData = await safeReadJson(pollRes);
            if (!pollRes.ok) { clearInterval(pollInterval); resolve({ success: false, error: pollData?.error || 'Nextcloud login failed.' }); return; }
            if (pollData?.status === 'connected') { clearInterval(pollInterval); resolve({ success: true, data: pollData }); return; }
            if (attempts >= maxAttempts) { clearInterval(pollInterval); resolve({ success: false, error: 'Login timed out. Please try again.' }); }
          } catch (err) { clearInterval(pollInterval); resolve({ success: false, error: err.message || 'Login polling failed.' }); }
        }, 2000);
      });
      if (!result.success) {
        setIntegrationForm(prev => ({ ...prev, loginFlowRunning: false, error: result.error || 'Nextcloud login failed.' }));
        return;
      }
      setIntegrationForm(prev => ({ ...prev, visible: false, submitting: false, loginFlowRunning: false, error: '' }));
      if (activeChatId) {
        appendMessageToChat(activeChatId, {
          role: 'assistant',
          content: `Connected to Nextcloud as ${result.data?.display_name || result.data?.username || 'user'}.`,
          id: createMessageId()
        });
      }
      if (integrationForm.originalPrompt) sendMessage(integrationForm.originalPrompt);
    } catch (err) {
      setIntegrationForm(prev => ({ ...prev, loginFlowRunning: false, error: `Error: ${err.message}` }));
    }
  }, [integrationForm, activeChatId, appendMessageToChat, sendMessage]);

  const submitIntegrationForm = useCallback(async (e) => {
    e.preventDefault();
    const requiredFields = integrationForm.fields.filter((field) => field?.required);
    const missingField = requiredFields.find((field) => {
      const val = integrationForm.values?.[field.name];
      return !String(val || '').trim();
    });
    if (missingField) {
      setIntegrationForm(prev => ({ ...prev, error: `Please provide ${missingField.label || missingField.name}.` }));
      return;
    }
    setIntegrationForm(prev => ({ ...prev, submitting: true, error: '' }));
    try {
      let endpoint = integrationForm.submitEndpoint || '';
      let payload = { ...integrationForm.values };
      if (integrationForm.provider === 'nextcloud') endpoint = '/api/nextcloud/login';
      if (integrationForm.provider === 'immich') endpoint = '/api/ui/system-config';
      if (!endpoint) {
        setIntegrationForm(prev => ({ ...prev, submitting: false, error: 'No setup endpoint provided for this integration.' }));
        return;
      }
      const res = await apiFetch(endpoint, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
      });
      const data = await safeReadJson(res);
      if (!res.ok || data?.success === false || data?.status === 'error') {
        setIntegrationForm(prev => ({ ...prev, submitting: false, error: data?.error || data?.message || 'Could not save integration settings.' }));
        return;
      }
      setIntegrationForm(prev => ({ ...prev, visible: false, submitting: false, loginFlowRunning: false, error: '' }));
      if (activeChatId) {
        appendMessageToChat(activeChatId, {
          role: 'assistant', content: 'Integration connected successfully. I am retrying your request now.', id: createMessageId()
        });
      }
      if (integrationForm.originalPrompt) sendMessage(integrationForm.originalPrompt);
    } catch (err) {
      setIntegrationForm(prev => ({ ...prev, submitting: false, error: `Error while saving configuration: ${err.message}` }));
    }
  }, [integrationForm, activeChatId, appendMessageToChat, sendMessage]);

  return {
    calendarForm, setCalendarForm, submitCalendarForm, closeCalendarForm, resetCalendarForm,
    taskForm, setTaskForm, submitTaskForm, closeTaskForm, resetTaskForm,
    integrationForm, setIntegrationForm, submitIntegrationForm, closeIntegrationForm, resetIntegrationForm,
    runNextcloudLoginFlow
  };
}
