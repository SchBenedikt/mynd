"use client";

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import './setup/SetupWizard.css';
import { apiFetch } from '../lib/api';

const SETUP_FLOW_KEY = 'mynd_setup_flow_v1';

const stepLabels = ['Start', 'Benutzer', 'KI', 'Überprüfen'];

export default function SetupWizard() {
  const router = useRouter();
  const [setupStatus, setSetupStatus] = useState(null);
  const [setupMode, setSetupMode] = useState('choose');
  const [setupPath, setSetupPath] = useState('');
  const [setupSubmitting, setSetupSubmitting] = useState(false);
  const [setupMessage, setSetupMessage] = useState('');
  const [setupError, setSetupError] = useState('');
  const [setupStatusLoading, setSetupStatusLoading] = useState(true);
  const [setupStatusError, setSetupStatusError] = useState('');
  const [setupComplete, setSetupComplete] = useState(false);
  const [setupFlowStarted, setSetupFlowStarted] = useState(false);
  const [animDir, setAnimDir] = useState('next');

  const [setupForm, setSetupForm] = useState({
    adminName: '', adminPassword: ''
  });
  const [nextcloudForm, setNextcloudForm] = useState({
    nextcloudUrl: ''
  });
  const [aiForm, setAiForm] = useState({
    provider: 'ollama', baseUrl: 'http://127.0.0.1:11434', model: '', embeddingModel: '', apiKey: ''
  });
  const [aiModels, setAiModels] = useState([]);
  const [authConfigForm, setAuthConfigForm] = useState({
    allowRegistration: false, requireLogin: true
  });

  const isEmbed = (m) => ['embed','embedding','all-minilm','bge','mxbai','snowflake-arctic-embed','nomic-embed','gte','e5','jina-embeddings','paraphrase-multilingual'].some((h) => String(m||'').toLowerCase().includes(h));

  const loadSetupStatus = useCallback(async () => {
    setSetupStatusLoading(true);
    setSetupStatusError('');
    try {
      const response = await apiFetch('/api/setup/status');
      const data = await response.json();
      if (!response.ok || !data?.success) throw new Error(data?.error || 'Status konnte nicht geladen werden');
      setSetupStatus(data);
      if (data.needs_setup) {
        setSetupComplete(false);
        setSetupFlowStarted(true);
        try { setSetupPath(sessionStorage.getItem(SETUP_FLOW_KEY) || ''); } catch (e) {}
        setSetupForm((cur) => ({ ...cur, adminName: cur.adminName || data.admin_user || 'admin' }));
        setNextcloudForm((cur) => ({ ...cur, nextcloudUrl: cur.nextcloudUrl || data.nextcloud_url || '' }));
      } else {
        setSetupFlowStarted(false);
        setSetupComplete(true);
        try { sessionStorage.removeItem(SETUP_FLOW_KEY); } catch (e) {}
      }
    } catch (error) {
      console.warn('Setup status:', error?.message);
      setSetupStatus(null);
      setSetupComplete(false);
      setSetupStatusError('Der Einrichtungsstatus ist nicht erreichbar. Prüfe, ob das MYND-Backend läuft, und versuche es erneut.');
    } finally {
      setSetupStatusLoading(false);
    }
  }, []);

  useEffect(() => { loadSetupStatus(); }, [loadSetupStatus]);

  useEffect(() => {
    if (setupMode === 'ai' && aiForm.provider === 'ollama' && aiModels.length === 0) {
      apiFetch('/api/ollama/models')
        .then(r => r.json())
        .then(data => setAiModels(Array.isArray(data?.models) ? data.models : []))
        .catch((e) => console.warn('Ollama models:', e?.message));
      apiFetch('/api/ui/system-config')
        .then(r => r.json())
        .then(data => {
          if (data?.success && data.config) {
            setAiForm(cur => ({ ...cur, baseUrl: data.config.base_url || cur.baseUrl, model: data.config.model || cur.model, embeddingModel: data.config.embedding_model || cur.embeddingModel }));
          }
        })
        .catch((e) => console.warn('System config:', e?.message));
    }
  }, [setupMode, aiModels, aiForm.provider]);

  const setupAlreadyFinished = Boolean(setupStatus && !setupStatus.needs_setup && !setupFlowStarted);
  useEffect(() => { if (setupAlreadyFinished) router.replace('/'); }, [setupAlreadyFinished, router]);

  const postSetup = async (payload) => {
    const resp = await apiFetch('/api/setup/bootstrap', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
    });
    const data = await resp.json();
    if (!resp.ok || !data.success) throw new Error(data?.error || 'Setup fehlgeschlagen');
    return data;
  };

  const refreshSetupStatus = async () => {
    try { const r = await apiFetch('/api/setup/status'); const d = await r.json(); if (d?.success) { setSetupStatus(d); return d; } } catch (e) {}
    return null;
  };

  const finishSetupFlow = async (msg) => {
    if (msg) setSetupMessage(msg);
    setSetupComplete(true);
    setSetupMode('choose');
    setSetupPath('');
    try { sessionStorage.removeItem(SETUP_FLOW_KEY); } catch (e) {}
    await refreshSetupStatus();
  };

  const setMode = (mode) => {
    setAnimDir('next');
    setSetupError('');
    setSetupMessage('');
    setSetupMode(mode);
  };

  const goBack = () => {
    setAnimDir('prev');
    setSetupError('');
    setSetupMessage('');
    if (setupMode === 'review') {
      setSetupMode('ai');
    } else if (setupMode === 'ai') {
      setSetupMode('admin');
    } else if (setupMode === 'admin' && setupPath === 'nextcloud') {
      setSetupMode('nextcloud');
    } else {
      setSetupMode('choose');
    }
  };

  const submitAdmin = async (ev) => {
    ev.preventDefault();
    if (setupForm.adminPassword.trim().length < 12) {
      setSetupError('Das Passwort muss mindestens 12 Zeichen enthalten.');
      return;
    }
    setSetupSubmitting(true);
    setSetupError('');
    setSetupMessage('');
    try {
      await postSetup({ mode: 'admin', admin_name: setupForm.adminName, admin_password: setupForm.adminPassword });
      setSetupPath('local');
      setMode('ai');
    } catch (err) {
      setSetupError(err.message || 'Fehler beim Speichern');
    } finally { setSetupSubmitting(false); }
  };

  const submitNextcloud = async (ev) => {
    ev.preventDefault();
    setSetupSubmitting(true);
    setSetupError('');
    setSetupMessage('');
    try {
      const startResponse = await apiFetch('/api/nextcloud/loginflow/start', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nextcloud_url: nextcloudForm.nextcloudUrl })
      });
      const start = await startResponse.json();
      if (!startResponse.ok || !start.success) throw new Error(start?.error || 'Nextcloud-Anmeldung konnte nicht gestartet werden.');
      const loginWindow = window.open(start.login_url, '_blank', 'noopener,noreferrer');
      if (!loginWindow) setSetupMessage('Bitte öffne das Nextcloud-Anmeldefenster über den erlaubten Browser-Popup.');
      let connected = false;
      for (let attempt = 0; attempt < 120; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        const pollResponse = await apiFetch(`/api/nextcloud/loginflow/poll?flow_id=${encodeURIComponent(start.flow_id)}`);
        const poll = await pollResponse.json();
        if (pollResponse.ok && poll.status === 'connected') { connected = true; break; }
        if (poll.status && poll.status !== 'pending') throw new Error(poll?.error || 'Nextcloud-Anmeldung fehlgeschlagen.');
      }
      if (!connected) throw new Error('Die Nextcloud-Anmeldung ist abgelaufen. Bitte erneut versuchen.');
      setSetupMessage('Nextcloud ist verbunden. Lege jetzt den lokalen Administrator an.');
      setMode('admin');
    } catch (err) {
      setSetupError(err.message || 'Fehler beim Speichern');
    } finally { setSetupSubmitting(false); }
  };

  const confirmSetup = async () => {
    setSetupSubmitting(true);
    setSetupError('');
    setSetupMessage('');
    try {
      if (aiForm.model) {
        await postSetup({ mode: 'ai', provider: aiForm.provider, base_url: aiForm.baseUrl, model: aiForm.model, embedding_model: aiForm.embeddingModel, api_key: aiForm.apiKey });
      }
      await postSetup({ mode: 'auth_config', allowRegistration: authConfigForm.allowRegistration, requireLogin: authConfigForm.requireLogin });
      await postSetup({ mode: 'system', enable_ollama: false, enable_immich: false });
      await finishSetupFlow('MYND wurde erfolgreich eingerichtet.');
    } catch (err) {
      setSetupError(err.message || 'Fehler beim Abschließen');
    } finally { setSetupSubmitting(false); }
  };

  const startLocalFlow = () => {
    setSetupError('');
    setSetupMessage('');
    setSetupPath('local');
    try { sessionStorage.setItem(SETUP_FLOW_KEY, 'local'); } catch (e) {}
    setMode('admin');
  };

  const startNextcloudFlow = () => {
    setSetupError('');
    setSetupMessage('');
    setSetupPath('nextcloud');
    try { sessionStorage.setItem(SETUP_FLOW_KEY, 'nextcloud'); } catch (e) {}
    setMode('nextcloud');
  };

  const nextcloudHint = [
    'MYND öffnet die offizielle Nextcloud-Anmeldeseite in einem neuen Fenster.',
    'Bestätige dort den Zugriff; Nextcloud erstellt ein widerrufbares App-Passwort.',
    'Das Passwort wird ausschließlich im lokalen verschlüsselten MYND-Tresor gespeichert.'
  ];

  const stepTitles = {
    choose: 'Start wählen', admin: 'Benutzer anlegen',
    nextcloud: 'Nextcloud verbinden', ai: 'KI konfigurieren', review: 'Einstellungen überprüfen'
  };

  const desc = {
    choose: 'Du kannst mit einem lokalen Administrator starten oder zuerst deine Nextcloud als Datenquelle verbinden.',
    admin: 'Lege den Admin-Benutzer an.',
    nextcloud: 'Verbinde MYND über den offiziellen Nextcloud Login Flow. Es ist keine manuell angelegte OAuth-App nötig.',
    ai: 'Wähle ein KI-Modell für die Chat-Funktion aus. Dies kann später in den Einstellungen geändert werden.',
    review: 'Überprüfe deine Einstellungen bevor du die Einrichtung abschließt.',
  };

  const setupPanelVisible = !setupStatusLoading && !setupStatusError && !setupAlreadyFinished && !setupComplete && Boolean(setupMode);

  const stepIndex = { choose: 0, admin: 1, nextcloud: 1, ai: 2, review: 3 }[setupMode] || 0;
  const isPrevStep = (idx) => idx < stepIndex;

  return (
    <div className="setup-page">
      <div className="setup-page-shell">
        <div className="setup-card">
          <div className="setup-card-body">
            <div className="setup-header">
              <div className="setup-badge">MYND</div>
            </div>

            <div className="setup-stepline">
              {stepLabels.map((label, idx) => (
                <span key={label} style={{display:'flex', alignItems:'center'}}>
                  <span className="setup-step-wrapper">
                    <span className={`setup-stepchip ${stepIndex === idx ? 'active' : ''} ${isPrevStep(idx) ? 'done' : ''}`}>
                      {isPrevStep(idx) ? '✓' : idx + 1}
                    </span>
                    <span className="setup-step-label">{label}</span>
                  </span>
                  {idx < stepLabels.length - 1 && <span className="setup-step-arrow">→</span>}
                </span>
              ))}
            </div>

            <div className={`setup-anim-wrap ${animDir}`} key={setupMode}>
              {setupStatusLoading ? (
                <div style={{textAlign:'center',padding:'36px 0'}} role="status" aria-live="polite">
                  <div className="setup-complete-badge setup-status-loading">Prüfe Systemstatus</div>
                  <h2 className="setup-title" style={{marginBottom:'8px'}}>MYND wird vorbereitet</h2>
                  <p className="setup-subtitle">Die vorhandene Konfiguration wird geladen.</p>
                </div>
              ) : setupStatusError ? (
                <div style={{textAlign:'center',padding:'36px 0'}} role="alert">
                  <h2 className="setup-title" style={{marginBottom:'8px'}}>Backend nicht erreichbar</h2>
                  <div className="setup-message error">{setupStatusError}</div>
                  <div className="setup-complete-actions">
                    <button type="button" className="btn btn-primary" onClick={loadSetupStatus}>Erneut prüfen</button>
                  </div>
                </div>
              ) : setupComplete ? (
                <div style={{textAlign:'center',padding:'24px 0'}}>
                  <div className="setup-complete-badge">Abgeschlossen</div>
                  <h2 className="setup-title" style={{marginBottom:'8px'}}>MYND ist jetzt eingerichtet</h2>
                  <p className="setup-subtitle" style={{marginBottom:'8px'}}>Deine Einstellungen wurden gespeichert.</p>
                  {setupMessage && <div className="setup-message success">{setupMessage}</div>}
                  <div className="setup-note" style={{marginTop:'20px',textAlign:'left'}}>
                    Konfiguriere jetzt optionale Dienste:
                  </div>
                  <div style={{marginTop:'16px'}}>
                    <p style={{fontSize:'0.85rem',color:'var(--muted)'}}>
                      Weitere Einstellungen wie KI-Modell, Integrationen und Design findest du in den Einstellungen.
                    </p>
                  </div>
                  <div className="setup-complete-actions" style={{marginTop:'24px'}}>
                    <button type="button" className="btn btn-primary" onClick={() => router.replace('/')}>Startseite öffnen</button>
                  </div>
                </div>
              ) : setupPanelVisible ? (
                <>
                  <h2 className="setup-title">{stepTitles[setupMode]}</h2>
                  <p className="setup-subtitle">{desc[setupMode]}</p>

                  {setupMode === 'choose' && (
                    <div className="setup-choice-grid" style={{marginTop:'24px'}}>
                      <button type="button" className="setup-choice-card" onClick={startLocalFlow}>
                        <div className="setup-choice-icon"><i className="fas fa-user-plus"></i></div>
                        <div className="setup-choice-title">Lokalen Benutzer anlegen</div>
                        <p>Geeignet, wenn du MYND ohne Nextcloud-Login starten willst.</p>
                      </button>
                      <button type="button" className="setup-choice-card" onClick={startNextcloudFlow}>
                        <div className="setup-choice-icon"><i className="fas fa-cloud"></i></div>
                        <div className="setup-choice-title">Nextcloud verbinden</div>
                        <p>Verbindet Kalender, Aufgaben und Dokumente; der MYND-Login bleibt ein lokales Administratorkonto.</p>
                      </button>
                    </div>
                  )}

                  {setupMode === 'admin' && (
                    <form onSubmit={submitAdmin} className="setup-form" style={{marginTop:'24px'}}>
                      <div className="setup-grid">
                        <label className="setup-field">
                          <span>Admin-Benutzer</span>
                          <input value={setupStatus?.admin_user || 'admin'} disabled />
                        </label>
                        <label className="setup-field">
                          <span>Admin-Passwort</span>
                          <input type="password" value={setupForm.adminPassword} onChange={(e) => setSetupForm((cur) => ({ ...cur, adminPassword: e.target.value }))} placeholder="Neues Admin-Passwort" autoFocus />
                        </label>
                        <label className="setup-field setup-wide">
                          <span>Anzeigename</span>
                          <input value={setupForm.adminName} onChange={(e) => setSetupForm((cur) => ({ ...cur, adminName: e.target.value }))} placeholder="z. B. Systemadmin" />
                        </label>
                      </div>
                      <div className="setup-note">Dieses Konto wird als erster lokaler Administrator angelegt.</div>
                      <div className="setup-footer">
                        <button type="button" className="btn" onClick={() => setMode('choose')}>Zurück</button>
                        <button type="submit" className="btn btn-success" disabled={setupSubmitting}>Weiter</button>
                      </div>
                    </form>
                  )}

                  {setupMode === 'nextcloud' && (
                    <form onSubmit={submitNextcloud} className="setup-form" style={{marginTop:'24px'}}>
                      <div className="setup-grid">
                        <label className="setup-field setup-wide">
                          <span>Nextcloud URL</span>
                          <input value={nextcloudForm.nextcloudUrl} onChange={(e) => setNextcloudForm((cur) => ({ ...cur, nextcloudUrl: e.target.value }))} placeholder="https://cloud.example.org" autoFocus />
                        </label>
                      </div>
                      <div className="setup-hints">
                        {nextcloudHint.map((item) => <div key={item} className="setup-hint-item">{item}</div>)}
                      </div>
                      <div className="setup-note">Beim Klick auf „Verbinden“ öffnet sich Nextcloud. Dieses Fenster wartet anschließend auf deine Bestätigung.</div>
                      <div className="setup-footer">
                        <button type="button" className="btn" onClick={() => setMode('choose')}>Zurück</button>
                        <button type="submit" className="btn btn-nc" disabled={setupSubmitting || !nextcloudForm.nextcloudUrl}>{setupSubmitting ? 'Warte auf Nextcloud…' : 'Verbinden'}</button>
                      </div>
                    </form>
                  )}

                  {setupMode === 'ai' && (
                    <div className="setup-form" style={{marginTop:'24px'}}>
                      <div className="setup-grid">
                        <label className="setup-field setup-wide">
                          <span>KI-Anbieter</span>
                          <select value={aiForm.provider} onChange={(e) => {
                            const provider = e.target.value;
                            setAiForm(cur => ({ ...cur, provider, baseUrl: provider === 'openai' ? 'https://api.openai.com/v1' : 'http://127.0.0.1:11434', model: '', embeddingModel: '', apiKey: '' }));
                          }}>
                            <option value="ollama">Ollama (lokal)</option>
                            <option value="openai">OpenAI-kompatibel</option>
                          </select>
                        </label>
                        <label className="setup-field setup-wide">
                          <span>{aiForm.provider === 'ollama' ? 'Ollama Base URL' : 'API Base URL'}</span>
                          <input type="url" value={aiForm.baseUrl} onChange={(e) => setAiForm(cur => ({ ...cur, baseUrl: e.target.value }))} placeholder="http://127.0.0.1:11434" autoFocus />
                        </label>
                        {aiForm.provider === 'openai' && (
                          <label className="setup-field setup-wide">
                            <span>API-Key</span>
                            <input type="password" autoComplete="off" value={aiForm.apiKey} onChange={(e) => setAiForm(cur => ({ ...cur, apiKey: e.target.value }))} placeholder="Wird verschlüsselt im lokalen Tresor gespeichert" />
                          </label>
                        )}
                        <label className="setup-field setup-wide">
                          <span>Chat-Modell</span>
                          {aiForm.provider === 'ollama' ? <select value={aiForm.model} onChange={(e) => setAiForm(cur => ({ ...cur, model: e.target.value }))}>
                            <option value="">— Auswählen —</option>
                            <option value="" disabled>── Modelle ──</option>
                            {aiModels.filter(m => !isEmbed(m?.name || m)).map((m) => { const name = typeof m === 'string' ? m : m.name; return <option key={name} value={name}>{name}</option>; })}
                          </select> : <input value={aiForm.model} onChange={(e) => setAiForm(cur => ({ ...cur, model: e.target.value }))} placeholder="z. B. gpt-5.4" />}
                        </label>
                        {aiForm.provider === 'ollama' && <label className="setup-field setup-wide">
                          <span>Embedding-Modell</span>
                          <select value={aiForm.embeddingModel} onChange={(e) => setAiForm(cur => ({ ...cur, embeddingModel: e.target.value }))}>
                            <option value="">— Keins (optional) —</option>
                            <option value="" disabled>── Modelle ──</option>
                            {aiModels.filter(m => isEmbed(m?.name || m)).map((m) => { const name = typeof m === 'string' ? m : m.name; return <option key={name} value={name}>{name}</option>; })}
                          </select>
                        </label>}
                      </div>
                      {aiForm.provider === 'ollama' && aiModels.length === 0 && (
                        <div className="setup-note">
                          Keine Ollama-Modelle gefunden. Stelle sicher, dass Ollama unter <strong>{aiForm.baseUrl}</strong> läuft.
                        </div>
                      )}
                      <div className="setup-footer">
                        <button type="button" className="btn" onClick={goBack}>Zurück</button>
                        <button type="button" className="btn btn-success" onClick={() => setMode('review')}>Weiter</button>
                      </div>
                    </div>
                  )}

                  {setupMode === 'review' && (
                    <div style={{marginTop:'24px'}}>
                      <div className="setup-review-list">
                        <div className="setup-review-item">
                          <span className="setup-review-label">Admin-Benutzer</span>
                          <span className="setup-review-value">{setupForm.adminName || 'admin'}</span>
                        </div>
                        {setupPath === 'nextcloud' && nextcloudForm.nextcloudUrl && (
                          <div className="setup-review-item">
                            <span className="setup-review-label">Nextcloud</span>
                            <span className="setup-review-value">{nextcloudForm.nextcloudUrl}</span>
                          </div>
                        )}
                        <div className="setup-review-item">
                          <span className="setup-review-label">KI-Modell</span>
                          <span className="setup-review-value">{aiForm.model ? `${aiForm.provider}: ${aiForm.model}` : 'Nicht konfiguriert'}</span>
                        </div>
                        {aiForm.embeddingModel && (
                          <div className="setup-review-item">
                            <span className="setup-review-label">Embedding</span>
                            <span className="setup-review-value">{aiForm.embeddingModel}</span>
                          </div>
                        )}
                      </div>
                      <div className="setup-auth-config" style={{marginTop:'1rem',display:'flex',flexDirection:'column',gap:'0.5rem'}}>
                        <div style={{fontWeight:600,fontSize:'0.85rem',marginBottom:'0.25rem'}}>Authentifizierungseinstellungen</div>
                        <label style={{display:'flex',alignItems:'center',gap:'0.5rem',cursor:'pointer',fontSize:'0.9rem'}}>
                          <input type="checkbox" checked={authConfigForm.allowRegistration}
                            onChange={(e) => setAuthConfigForm(f=>({...f,allowRegistration:e.target.checked}))} />
                          Registrierung erlauben
                        </label>
                        <label style={{display:'flex',alignItems:'center',gap:'0.5rem',cursor:'pointer',fontSize:'0.9rem'}}>
                          <input type="checkbox" checked={authConfigForm.requireLogin}
                            onChange={(e) => setAuthConfigForm(f=>({...f,requireLogin:e.target.checked}))} />
                          Anmeldung erforderlich
                        </label>
                      </div>
                      {setupMessage && <div className="setup-message success" style={{marginTop:'12px'}}>{setupMessage}</div>}
                      {setupError && <div className="setup-message error" style={{marginTop:'12px'}}>{setupError}</div>}
                      <div className="setup-footer" style={{marginTop:'20px'}}>
                        <button type="button" className="btn" onClick={goBack}>Zurück</button>
                        <button type="button" className="btn btn-success" onClick={confirmSetup} disabled={setupSubmitting}>
                          {setupSubmitting ? 'Wird gespeichert…' : 'Einrichtung abschließen'}
                        </button>
                      </div>
                    </div>
                  )}
                </>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
