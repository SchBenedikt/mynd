"use client";

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import './SetupWizard.css';

const SETUP_FLOW_KEY = 'mynd_setup_flow_v1';

export default function SetupWizard() {
  const router = useRouter();
  const [setupStatus, setSetupStatus] = useState(null);
  const [setupMode, setSetupMode] = useState('choose');
  const [setupPath, setSetupPath] = useState('');
  const [setupSubmitting, setSetupSubmitting] = useState(false);
  const [setupMessage, setSetupMessage] = useState('');
  const [setupError, setSetupError] = useState('');
  const [setupComplete, setSetupComplete] = useState(false);
  const [setupFlowStarted, setSetupFlowStarted] = useState(false);
  const [nextcloudConfigLoaded, setNextcloudConfigLoaded] = useState(false);
  const [animDir, setAnimDir] = useState('next');
  const [systemConfigLoaded, setSystemConfigLoaded] = useState(false);
  const [aiModels, setAiModels] = useState([]);
  const [aiModelsLoaded, setAiModelsLoaded] = useState(false);

  const [setupForm, setSetupForm] = useState({
    adminName: '', adminPassword: ''
  });
  const [nextcloudForm, setNextcloudForm] = useState({
    clientId: '', clientSecret: '', nextcloudUrl: ''
  });
  const [systemForm, setSystemForm] = useState({
    baseUrl: 'http://127.0.0.1:11434', model: '', embeddingModel: '',
    immichUrl: '', immichApiKey: ''
  });
  const [configureOllama, setConfigureOllama] = useState(true);

  const stepLabels = setupPath === 'nextcloud'
    ? ['Start', 'Nextcloud', 'KI', 'Überprüfen']
    : ['Start', 'Konto', 'KI', 'Überprüfen'];

  const stepIndex = { choose: 0, admin: 0, nextcloud: 0, system: 2, review: 3 }[setupMode] ?? 0;
  const adjustedStepIndex = setupMode === 'admin' || setupMode === 'nextcloud' ? 1 : stepIndex;
  const isPrevStep = (idx) => idx < (setupMode === 'choose' ? 0 : adjustedStepIndex);

  useEffect(() => {
    fetch('/api/setup/status')
      .then((r) => r.json())
      .then((data) => {
        if (data && data.success) {
          setSetupStatus(data);
          if (data.needs_setup) {
            setSetupFlowStarted(true);
            try { setSetupPath(sessionStorage.getItem(SETUP_FLOW_KEY) || ''); } catch (e) {}
            setSetupForm((cur) => ({ ...cur, adminName: cur.adminName || data.admin_user || 'admin' }));
            setNextcloudForm((cur) => ({ ...cur, nextcloudUrl: cur.nextcloudUrl || data.nextcloud_url || '' }));
          } else {
            setSetupComplete(true);
          }
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (setupMode === 'nextcloud' && !nextcloudConfigLoaded) {
      fetch('/api/nextcloud/oauth/config')
        .then((r) => r.json())
        .then((data) => {
          if (data?.configured) {
            setNextcloudForm((cur) => ({ ...cur, clientId: data.client_id || cur.clientId, nextcloudUrl: data.nextcloud_url || cur.nextcloudUrl }));
          }
        })
        .catch(() => {})
        .finally(() => setNextcloudConfigLoaded(true));
    }
    if (setupMode === 'system' && !systemConfigLoaded) {
      fetch('/api/ui/system-config')
        .then((r) => r.json())
        .then((data) => {
          if (data?.success && data.config) {
            setSystemForm((cur) => ({
              ...cur, baseUrl: data.config.base_url || cur.baseUrl,
              model: data.config.model || cur.model,
              embeddingModel: data.config.embedding_model || cur.embeddingModel
            }));
          }
        })
        .catch(() => {})
        .finally(() => setSystemConfigLoaded(true));
    }
    if (setupMode === 'system' && !aiModelsLoaded) {
      fetch('/api/ollama/models')
        .then((r) => r.json())
        .then((data) => setAiModels(Array.isArray(data?.models) ? data.models : []))
        .catch(() => {})
        .finally(() => setAiModelsLoaded(true));
    }
  }, [setupMode, nextcloudConfigLoaded, systemConfigLoaded, aiModelsLoaded]);

  const setupAlreadyFinished = Boolean(setupStatus && !setupStatus.needs_setup && !setupFlowStarted);
  useEffect(() => { if (setupAlreadyFinished) router.replace('/'); }, [setupAlreadyFinished, router]);

  const postSetup = async (payload) => {
    const resp = await fetch('/api/setup/bootstrap', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
    });
    const data = await resp.json();
    if (!resp.ok || !data.success) throw new Error(data?.error || 'Setup fehlgeschlagen');
    return data;
  };

  const refreshSetupStatus = async () => {
    try { const r = await fetch('/api/setup/status'); const d = await r.json(); if (d?.success) { setSetupStatus(d); return d; } } catch (e) {}
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
    if (setupMode === 'admin' || setupMode === 'nextcloud') {
      setSetupMode('choose');
    } else if (setupMode === 'system') {
      if (setupPath === 'nextcloud') setSetupMode('nextcloud');
      else setSetupMode('admin');
    } else if (setupMode === 'review') {
      setSetupMode('system');
    } else {
      setSetupMode('choose');
    }
  };

  const submitAdmin = async (ev) => {
    ev.preventDefault();
    if (!setupForm.adminPassword.trim()) { setSetupError('Passwort eingeben'); return; }
    setSetupSubmitting(true); setSetupError(''); setSetupMessage('');
    try {
      await postSetup({ mode: 'admin', admin_name: setupForm.adminName, admin_password: setupForm.adminPassword });
      setSetupPath('local');
      setSystemConfigLoaded(false); setAiModelsLoaded(false);
      setMode('system');
    } catch (err) { setSetupError(err.message || 'Fehler beim Speichern'); }
    finally { setSetupSubmitting(false); }
  };

  const submitNextcloud = async (ev) => {
    ev.preventDefault();
    setSetupSubmitting(true); setSetupError(''); setSetupMessage('');
    try {
      await postSetup({ mode: 'nextcloud', client_id: nextcloudForm.clientId, client_secret: nextcloudForm.clientSecret, nextcloud_url: nextcloudForm.nextcloudUrl });
      setSetupPath('nextcloud');
      setSystemConfigLoaded(false); setAiModelsLoaded(false);
      setMode('system');
    } catch (err) { setSetupError(err.message || 'Fehler beim Speichern'); }
    finally { setSetupSubmitting(false); }
  };

  const submitSystem = async (ev) => {
    ev.preventDefault();
    setSetupSubmitting(true); setSetupError(''); setSetupMessage('');
    try {
      const payload = { mode: 'system', enable_ollama: configureOllama };
      if (configureOllama) {
        payload.base_url = systemForm.baseUrl;
        payload.model = systemForm.model;
        payload.embedding_model = systemForm.embeddingModel;
      }
      await postSetup(payload);
      setMode('review');
    } catch (err) { setSetupError(err.message || 'Fehler beim Speichern'); }
    finally { setSetupSubmitting(false); }
  };

  const confirmSetup = async () => {
    setSetupSubmitting(true); setSetupError(''); setSetupMessage('');
    try {
      await postSetup({ mode: 'system', enable_ollama: false });
      await finishSetupFlow('MYND wurde erfolgreich eingerichtet.');
    } catch (err) { setSetupError(err.message || 'Fehler beim Abschließen'); }
    finally { setSetupSubmitting(false); }
  };

  const startLocalFlow = () => {
    setSetupError(''); setSetupMessage(''); setSetupPath('local');
    try { sessionStorage.setItem(SETUP_FLOW_KEY, 'local'); } catch (e) {}
    setMode('admin');
  };

  const startNextcloudFlow = () => {
    setSetupError(''); setSetupMessage(''); setSetupPath('nextcloud');
    try { sessionStorage.setItem(SETUP_FLOW_KEY, 'nextcloud'); } catch (e) {}
    setMode('nextcloud');
  };

  const redirectUri = typeof window !== 'undefined' ? `${window.location.origin}/api/auth/nextcloud/callback` : '/api/auth/nextcloud/callback';
  const [copyOk, setCopyOk] = useState(false);

  const copyRedirectUri = () => {
    const input = document.createElement('input');
    input.value = redirectUri;
    document.body.appendChild(input);
    input.select();
    try { document.execCommand('copy'); setCopyOk(true); setTimeout(() => setCopyOk(false), 2000); } catch (e) {}
    document.body.removeChild(input);
  };

  const nextcloudHint = [
    'In Nextcloud als Admin eine OAuth2-App anlegen oder die vorhandene OAuth2-Funktion nutzen.',
    'Die Callback-URL in der Nextcloud-App muss exakt auf die unten angezeigte Redirect-URI zeigen.',
    'Danach Client ID und Client Secret hier eintragen und speichern.'
  ];

  const stepTitles = {
    choose: 'Start wählen', admin: 'Konto anlegen',
    nextcloud: 'Nextcloud OAuth', system: 'KI konfigurieren',
    review: 'Alles überprüfen'
  };

  const desc = {
    choose: 'Du kannst MYND mit einem lokalen Konto oder per Nextcloud-Login einrichten.',
    admin: 'Lege den Admin-Benutzer für die lokale Anmeldung an.',
    nextcloud: 'Trage die Nextcloud-Zugangsdaten für die OAuth-Anmeldung ein.',
    system: 'Verbinde deine KI (Ollama) und wähle Chat- und Embedding-Modell.',
    review: 'Überprüfe deine Einstellungen vor dem Abschluss.',
  };

  const setupPanelVisible = !setupAlreadyFinished && !setupComplete && Boolean(setupMode);

  const modelOpts = [...new Set((aiModels||[]).map(m=>String(m||'').trim()).filter(Boolean))].sort();
  const embedHints = ['embed','embedding','all-minilm','bge','mxbai','nomic-embed','gte','e5','jina-embeddings'];
  const embedOpts = modelOpts.filter(m => embedHints.some(h => m.toLowerCase().includes(h)));
  const chatOpts = modelOpts.filter(m => !embedHints.some(h => m.toLowerCase().includes(h)));

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
                <span key={idx} style={{display:'flex', alignItems:'center'}}>
                  <span className="setup-step-wrapper">
                    <span className={`setup-stepchip ${adjustedStepIndex === idx ? 'active' : ''} ${isPrevStep(idx) ? 'done' : ''}`}>
                      {isPrevStep(idx) ? '✓' : idx + 1}
                    </span>
                    <span className="setup-step-label">{label}</span>
                  </span>
                  {idx < stepLabels.length - 1 && <span className="setup-step-arrow">→</span>}
                </span>
              ))}
            </div>

            <div className={`setup-anim-wrap ${animDir}`} key={setupMode}>
              {setupComplete ? (
                <div style={{textAlign:'center',padding:'24px 0'}}>
                  <div className="setup-complete-badge">Abgeschlossen</div>
                  <h2 className="setup-title" style={{marginBottom:'8px'}}>MYND ist jetzt eingerichtet</h2>
                  <p className="setup-subtitle" style={{marginBottom:'8px'}}>Deine Einstellungen wurden gespeichert.</p>
                  {setupMessage && <div className="setup-message success">{setupMessage}</div>}
                  <div className="setup-note" style={{marginTop:'20px',textAlign:'left'}}>
                    Weitere Einstellungen findest du hier:
                  </div>
                  <div style={{display:'flex',flexDirection:'column',gap:'10px',marginTop:'16px'}}>
                    <div className="setup-post-card" onClick={() => window.location.href = '/setup/ai'}>
                      <div className="setup-post-icon"><i className="fas fa-brain"></i></div>
                      <div className="setup-post-info">
                        <strong>KI detailliert konfigurieren</strong>
                        <small>Ollama, Modell, Embeddings, TTS</small>
                      </div>
                      <span className="setup-post-arrow">→</span>
                    </div>
                    <div className="setup-post-card" onClick={() => window.location.href = '/setup/integrations'}>
                      <div className="setup-post-icon"><i className="fas fa-plug"></i></div>
                      <div className="setup-post-info">
                        <strong>Integrationen einrichten</strong>
                        <small>E-Mail, Immich, TrueNAS</small>
                      </div>
                      <span className="setup-post-arrow">→</span>
                    </div>
                  </div>
                  <div className="setup-complete-actions" style={{marginTop:'24px'}}>
                    <button type="button" className="btn btn-primary" onClick={() => window.location.href = '/'}>Startseite öffnen</button>
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
                        <div className="setup-choice-title">Lokales Konto</div>
                        <p>Du erstellst einen Admin-Benutzer und meldest dich lokal an.</p>
                      </button>
                      <button type="button" className="setup-choice-card" onClick={startNextcloudFlow}>
                        <div className="setup-choice-icon"><i className="fas fa-cloud"></i></div>
                        <div className="setup-choice-title">Nextcloud-Login</div>
                        <p>Du verbindest MYND mit deiner Nextcloud für die Anmeldung.</p>
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
                        <label className="setup-field">
                          <span>Client ID</span>
                          <input value={nextcloudForm.clientId} onChange={(e) => setNextcloudForm((cur) => ({ ...cur, clientId: e.target.value }))} placeholder="Client ID" />
                        </label>
                        <label className="setup-field">
                          <span>Client Secret</span>
                          <input value={nextcloudForm.clientSecret} onChange={(e) => setNextcloudForm((cur) => ({ ...cur, clientSecret: e.target.value }))} placeholder="Client Secret" />
                        </label>
                      </div>
                      <div className="setup-hints">
                        {nextcloudHint.map((item) => <div key={item} className="setup-hint-item">{item}</div>)}
                      </div>
                      <div className="setup-redirect">
                        <span className="setup-redirect-label">Redirect-URI</span>
                        <div style={{display:'flex', alignItems:'center', gap:'6px'}}>
                          <code className="setup-redirect-code" style={{flex:1}}>{redirectUri}</code>
                          <button type="button" onClick={copyRedirectUri} style={{padding:'10px 14px', borderRadius:'10px', border:'1px solid #d7e0eb', background:'#fff', cursor:'pointer', color:'#64748b', fontSize:'14px', lineHeight:1, flexShrink:0}}>
                            {copyOk ? '✓' : '📋'}
                          </button>
                        </div>
                      </div>
                      <div className="setup-note">Speichern aktiviert die Nextcloud-Anmeldung.</div>
                      <div className="setup-footer">
                        <button type="button" className="btn" onClick={() => setMode('choose')}>Zurück</button>
                        <button type="submit" className="btn btn-nc" disabled={setupSubmitting}>Weiter</button>
                      </div>
                    </form>
                  )}

                  {setupMode === 'system' && (
                    <form onSubmit={submitSystem} className="setup-form" style={{marginTop:'24px'}}>
                      <label className="setup-card-toggle" style={{display:'flex',alignItems:'center',gap:'12px',padding:'12px 16px',border:'1px solid #e2e8f0',borderRadius:'14px',cursor:'pointer',background:'#fff'}}>
                        <input type="checkbox" checked={configureOllama} onChange={(e) => setConfigureOllama(e.target.checked)} style={{width:'20px',height:'20px',cursor:'pointer'}} />
                        <span><strong style={{display:'block',fontSize:'15px',color:'#0f172a'}}>KI (Ollama) konfigurieren</strong><small style={{fontSize:'12px',color:'#64748b'}}>Chat-Modell und Embedding-Modell</small></span>
                      </label>
                      {configureOllama && (
                        <div style={{display:'flex',flexDirection:'column',gap:'16px',padding:'0 0 8px'}}>
                          <label className="setup-field">
                            <span>Ollama Base URL</span>
                            <input value={systemForm.baseUrl} onChange={(e) => setSystemForm((cur) => ({ ...cur, baseUrl: e.target.value }))} placeholder="http://127.0.0.1:11434" />
                          </label>
                          <div className="setup-grid">
                            <label className="setup-field">
                              <span>Chat-Modell</span>
                              <select value={systemForm.model} onChange={(e) => setSystemForm((cur) => ({ ...cur, model: e.target.value }))}>
                                <option value="">Bitte auswählen…</option>
                                {[...new Set([...(systemForm.model && !chatOpts.includes(systemForm.model) ? [systemForm.model] : []), ...chatOpts])].map((m) => (
                                  <option key={m} value={m}>{m}</option>
                                ))}
                              </select>
                            </label>
                            <label className="setup-field">
                              <span>Embedding-Modell</span>
                              <select value={systemForm.embeddingModel} onChange={(e) => setSystemForm((cur) => ({ ...cur, embeddingModel: e.target.value }))}>
                                <option value="">Bitte auswählen…</option>
                                {[...new Set([...(systemForm.embeddingModel && !embedOpts.includes(systemForm.embeddingModel) ? [systemForm.embeddingModel] : []), ...embedOpts])].map((m) => (
                                  <option key={m} value={m}>{m}</option>
                                ))}
                              </select>
                            </label>
                          </div>
                        </div>
                      )}
                      {setupMessage && <div className="setup-message success">{setupMessage}</div>}
                      {setupError && <div className="setup-message error">{setupError}</div>}
                      <div className="setup-footer">
                        <button type="button" className="btn" onClick={goBack}>Zurück</button>
                        <button type="button" className="btn" onClick={() => { setConfigureOllama(false); submitSystem({preventDefault:()=>{}}); }}>Überspringen</button>
                        <button type="submit" className="btn btn-primary" disabled={setupSubmitting}>Weiter</button>
                      </div>
                    </form>
                  )}

                  {setupMode === 'review' && (
                    <div style={{marginTop:'24px'}}>
                      <div className="setup-review-list">
                        <div className="setup-review-item">
                          <span className="setup-review-label">Konto</span>
                          <span className="setup-review-value">{setupPath === 'nextcloud' ? 'Nextcloud' : (setupForm.adminName || 'admin')}</span>
                        </div>
                        {setupPath === 'nextcloud' && nextcloudForm.nextcloudUrl && (
                          <div className="setup-review-item">
                            <span className="setup-review-label">Nextcloud URL</span>
                            <span className="setup-review-value">{nextcloudForm.nextcloudUrl}</span>
                          </div>
                        )}
                        <div className="setup-review-item">
                          <span className="setup-review-label">KI konfigurieren</span>
                          <span className="setup-review-value">{configureOllama ? 'Ja' : 'Nein'}</span>
                        </div>
                        {configureOllama && systemForm.model && (
                          <div className="setup-review-item">
                            <span className="setup-review-label">Chat-Modell</span>
                            <span className="setup-review-value">{systemForm.model}</span>
                          </div>
                        )}
                        {configureOllama && systemForm.embeddingModel && (
                          <div className="setup-review-item">
                            <span className="setup-review-label">Embedding-Modell</span>
                            <span className="setup-review-value">{systemForm.embeddingModel}</span>
                          </div>
                        )}
                      </div>
                      <div className="setup-note" style={{marginTop:'16px'}}>
                        Detailierte KI- und Integrationseinstellungen kannst du jederzeit in den Einstellungen anpassen.
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
