"use client";

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import './AuthGate.css';

const SETUP_FLOW_KEY = 'mynd_setup_flow_v1';

const EMBEDDING_MODEL_HINTS = [
  'embed',
  'embedding',
  'all-minilm',
  'bge',
  'mxbai',
  'snowflake-arctic-embed',
  'nomic-embed',
  'gte',
  'e5',
  'jina-embeddings',
  'paraphrase-multilingual'
];

const normalizeModelName = (model) => String(model || '').trim();

const isEmbeddingModel = (model) => {
  const normalized = normalizeModelName(model).toLowerCase();
  return EMBEDDING_MODEL_HINTS.some((hint) => normalized.includes(hint));
};

const uniqueSortedModels = (models) => {
  return Array.from(new Set((models || []).map(normalizeModelName).filter(Boolean)))
    .sort((left, right) => left.localeCompare(right, undefined, { sensitivity: 'base' }));
};

const splitModelOptions = (models) => {
  const uniqueModels = uniqueSortedModels(models);
  return {
    chatModels: uniqueModels.filter((model) => !isEmbeddingModel(model)),
    embeddingModels: uniqueModels.filter((model) => isEmbeddingModel(model))
  };
};

const resolveModelOption = (models, preferredModel) => {
  const uniqueModels = uniqueSortedModels(models);
  const preferredName = normalizeModelName(preferredModel);
  if (!preferredName) return '';

  const exactMatch = uniqueModels.find((model) => model === preferredName);
  if (exactMatch) return exactMatch;

  const preferredBase = preferredName.toLowerCase().split(':')[0];
  const baseMatch = uniqueModels.find((model) => model.toLowerCase().split(':')[0] === preferredBase);
  return baseMatch || preferredName;
};

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
  const [systemConfigLoaded, setSystemConfigLoaded] = useState(false);
  const [nextcloudConfigLoaded, setNextcloudConfigLoaded] = useState(false);
  const [aiModels, setAiModels] = useState([]);
  const [aiModelsLoaded, setAiModelsLoaded] = useState(false);
  const [setupForm, setSetupForm] = useState({
    adminName: '',
    adminPassword: '',
    clientId: '',
    clientSecret: '',
    nextcloudUrl: ''
  });
  const [systemForm, setSystemForm] = useState({
    baseUrl: 'http://127.0.0.1',
    model: 'gemma3:latest',
    embeddingModel: 'nomic-embed-text',
    immichUrlDefault: '',
    immichApiKeyDefault: ''
  });
  const [configureOllama, setConfigureOllama] = useState(true);
  const [configureImmich, setConfigureImmich] = useState(false);
  const [nextcloudForm, setNextcloudForm] = useState({
    clientId: '',
    clientSecret: '',
    nextcloudUrl: ''
  });

  useEffect(() => {
    fetch('/api/setup/status')
      .then((r) => r.json())
      .then((data) => {
        if (data && data.success) {
          setSetupStatus(data);
          if (data.needs_setup) {
            setSetupFlowStarted(true);
            try {
              setSetupPath(sessionStorage.getItem(SETUP_FLOW_KEY) || '');
            } catch (err) {}
            setSetupForm((current) => ({
              ...current,
              adminName: current.adminName || data.admin_user || 'admin'
            }));
            setNextcloudForm((current) => ({
              ...current,
              nextcloudUrl: current.nextcloudUrl || data.nextcloud_url || ''
            }));
          } else {
            setSetupComplete(true);
          }
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (setupMode === 'system' && !systemConfigLoaded) {
      fetch('/api/ui/system-config')
        .then((r) => r.json())
        .then((data) => {
          if (data && data.success && data.config) {
            setSystemForm((current) => ({
              ...current,
              baseUrl: data.config.base_url || current.baseUrl,
              model: data.config.model || current.model,
              embeddingModel: data.config.embedding_model || current.embeddingModel,
              immichUrlDefault: data.config.immich_url_default || '',
              immichApiKeyDefault: data.config.immich_api_key_default || ''
            }));
          }
        })
        .catch(() => {})
        .finally(() => setSystemConfigLoaded(true));
    }

    if (setupMode === 'system' && !aiModelsLoaded) {
      fetch('/api/ollama/models')
        .then((r) => r.json())
        .then((data) => {
          setAiModels(Array.isArray(data?.models) ? data.models : []);
        })
        .catch(() => {})
        .finally(() => setAiModelsLoaded(true));
    }

    if (setupMode === 'nextcloud' && !nextcloudConfigLoaded) {
      fetch('/api/nextcloud/oauth/config')
        .then((r) => r.json())
        .then((data) => {
          if (data && data.configured) {
            setNextcloudForm((current) => ({
              ...current,
              clientId: data.client_id || current.clientId,
              nextcloudUrl: data.nextcloud_url || current.nextcloudUrl
            }));
          }
        })
        .catch(() => {})
        .finally(() => setNextcloudConfigLoaded(true));
    }
  }, [setupMode, systemConfigLoaded, nextcloudConfigLoaded, aiModelsLoaded]);

  const setupAlreadyFinished = Boolean(setupStatus && !setupStatus.needs_setup && !setupFlowStarted);

  useEffect(() => {
    if (setupAlreadyFinished) {
      router.replace('/');
    }
  }, [setupAlreadyFinished, router]);

  const postSetup = async (payload) => {
    const resp = await fetch('/api/setup/bootstrap', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await resp.json();
    if (!resp.ok || !data.success) {
      throw new Error((data && data.error) ? String(data.error) : 'Setup fehlgeschlagen');
    }
    return data;
  };

  const refreshSetupStatus = async () => {
    try {
      const statusResp = await fetch('/api/setup/status');
      const statusData = await statusResp.json();
      if (statusData && statusData.success) {
        setSetupStatus(statusData);
        return statusData;
      }
    } catch (err) {}
    return null;
  };

  const finishSetupFlow = async (message) => {
    if (message) {
      setSetupMessage(message);
    }
    setSetupComplete(true);
    setSetupMode('choose');
    setSetupPath('');
    try {
      sessionStorage.removeItem(SETUP_FLOW_KEY);
    } catch (err) {}
    await refreshSetupStatus();
  };

  const submitAdmin = async (ev) => {
    ev.preventDefault();
    setSetupError('');
    setSetupMessage('');
    setSetupSubmitting(true);
    try {
      await postSetup({
        mode: 'admin',
        admin_name: setupForm.adminName,
        admin_password: setupForm.adminPassword
      });
      setSetupMessage('Benutzer wurde angelegt. Als Nächstes kommen die optionalen globalen Werte.');
      setSetupMode('system');
      setSetupPath('local');
      setSystemConfigLoaded(false);
      await refreshSetupStatus();
    } catch (err) {
      setSetupError(err.message || 'Das Setup konnte gerade nicht gespeichert werden. Bitte prüfe die Verbindung oder versuche es noch einmal.');
    } finally {
      setSetupSubmitting(false);
    }
  };

  const submitSystem = async (ev) => {
    ev.preventDefault();
    setSetupError('');
    setSetupMessage('');
    setSetupSubmitting(true);
    try {
      if (!configureOllama && !configureImmich) {
        await finishSetupFlow('Keine globale Konfiguration ausgewählt. Setup ist abgeschlossen.');
        return;
      }

      await postSetup({
        mode: 'system',
        enable_ollama: configureOllama,
        ...(configureOllama ? {
          base_url: systemForm.baseUrl,
          model: systemForm.model,
          embedding_model: systemForm.embeddingModel
        } : {}),
        enable_immich: configureImmich,
        ...(configureImmich ? {
          immich_url_default: systemForm.immichUrlDefault,
          immich_api_key_default: systemForm.immichApiKeyDefault
        } : {})
      });
      await finishSetupFlow('Globale KI- und Immich-Werte wurden gespeichert. Setup ist abgeschlossen.');
      await refreshSetupStatus();
    } catch (err) {
      setSetupError(err.message || 'Das Setup konnte gerade nicht gespeichert werden. Bitte prüfe die Verbindung oder versuche es noch einmal.');
    } finally {
      setSetupSubmitting(false);
    }
  };

  const submitNextcloud = async (ev) => {
    ev.preventDefault();
    setSetupError('');
    setSetupMessage('');
    setSetupSubmitting(true);
    try {
      await postSetup({
        mode: 'nextcloud',
        client_id: nextcloudForm.clientId,
        client_secret: nextcloudForm.clientSecret,
        nextcloud_url: nextcloudForm.nextcloudUrl
      });
      setSetupMessage('Nextcloud OAuth wurde gespeichert. Als Nächstes kannst du die globalen KI- und Immich-Werte konfigurieren.');
      setSetupMode('system');
      setSetupPath('nextcloud');
      setSystemConfigLoaded(false);
      await refreshSetupStatus();
    } catch (err) {
      setSetupError(err.message || 'Das Setup konnte gerade nicht gespeichert werden. Bitte prüfe die Verbindung oder versuche es noch einmal.');
    } finally {
      setSetupSubmitting(false);
    }
  };

  const skipSystemStep = async () => {
    setSetupError('');
    setSetupSubmitting(true);
    try {
      await finishSetupFlow('Globale KI- und Immich-Werte werden später konfiguriert.');
    } finally {
      setSetupSubmitting(false);
    }
  };

  const startLocalFlow = () => {
    setSetupError('');
    setSetupMessage('');
    setSetupPath('local');
    try { sessionStorage.setItem(SETUP_FLOW_KEY, 'local'); } catch (err) {}
    setSetupMode('admin');
  };

  const startNextcloudFlow = () => {
    setSetupError('');
    setSetupMessage('');
    setSetupPath('nextcloud');
    try { sessionStorage.setItem(SETUP_FLOW_KEY, 'nextcloud'); } catch (err) {}
    setSetupMode('nextcloud');
  };

  const { chatModels: aiModelOptions, embeddingModels: embeddingModelOptions } = splitModelOptions(aiModels);
  const selectedChatModel = resolveModelOption(aiModelOptions, systemForm.model);
  const selectedEmbeddingModel = resolveModelOption(embeddingModelOptions, systemForm.embeddingModel);
  const chatModelChoices = systemForm.model && !aiModelOptions.includes(systemForm.model)
    ? [systemForm.model, ...aiModelOptions]
    : aiModelOptions;
  const embeddingModelChoices = systemForm.embeddingModel && !embeddingModelOptions.includes(systemForm.embeddingModel)
    ? [systemForm.embeddingModel, ...embeddingModelOptions]
    : embeddingModelOptions;

  const redirectUri = typeof window !== 'undefined'
    ? `${window.location.origin}/api/auth/nextcloud/callback`
    : '/api/auth/nextcloud/callback';

  const [copyOk, setCopyOk] = useState(false);

  const copyRedirectUri = () => {
    navigator.clipboard.writeText(redirectUri).then(() => {
      setCopyOk(true);
      setTimeout(() => setCopyOk(false), 2000);
    }).catch(() => {});
  };

  const nextcloudHint = [
    'In Nextcloud als Admin eine OAuth2-App anlegen oder die vorhandene OAuth2-Funktion nutzen.',
    'Die Callback-URL in der Nextcloud-App muss exakt auf die unten angezeigte Redirect-URI zeigen.',
    'Danach Client ID und Client Secret hier eintragen und speichern.'
  ];

  const stepLabels = {
    choose: 'Start',
    admin: 'Schritt 1 von 3',
    system: 'Schritt 2 von 3',
    nextcloud: 'Schritt 3 von 3'
  };

  const stepTitles = {
    choose: 'Start wählen',
    admin: 'Benutzer anlegen',
    system: 'Globale KI / Immich',
    nextcloud: 'Nextcloud OAuth'
  };

  const setupPanelVisible = !setupAlreadyFinished && !setupComplete && Boolean(setupMode);

  return (
    <div className="setup-page">
      <div className="setup-page-shell">
        <div className="setup-page-hero">
          <div>
            <div className="setup-page-kicker">Einrichtung</div>
            <h1>MYND konfigurieren</h1>
            <p>{setupPath === 'local' ? 'Du hast den lokalen Startweg gewählt. Danach kommen die globalen KI- und Fotoeinstellungen.' : setupPath === 'nextcloud' ? 'Du hast Nextcloud als Startweg gewählt. Danach kommen die globalen KI- und Fotoeinstellungen.' : 'Die Einrichtung läuft in zwei Wegen. Du kannst entweder mit einem lokalen Benutzer starten oder direkt Nextcloud als Login einrichten. In beiden Fällen kannst du danach noch die globalen KI- und Fotoeinstellungen konfigurieren.'}</p>
            <div className="setup-stepline" aria-label="Einrichtungsstatus">
              <span className={`setup-stepchip ${setupMode === 'choose' ? 'active' : ''}`}>Start</span>
              <span className={`setup-stepchip ${setupMode === 'admin' ? 'active' : ''}`}>Benutzer</span>
              <span className={`setup-stepchip ${setupMode === 'system' ? 'active' : ''}`}>Global</span>
              <span className={`setup-stepchip ${setupMode === 'nextcloud' ? 'active' : ''}`}>Nextcloud</span>
            </div>
          </div>
        </div>

        {setupComplete ? (
          <div className="setup-panel setup-panel-standalone setup-complete-panel">
            <div className="setup-complete-badge">Abgeschlossen</div>
            <h2 className="setup-title">MYND ist jetzt eingerichtet</h2>
            <p className="setup-subtitle">Öffne jetzt die Startseite. Dort solltest du entweder die Login-Ansicht oder die normale Oberfläche sehen, je nachdem ob du bereits angemeldet bist.</p>
            <div className="setup-complete-actions">
              <button type="button" className="btn btn-primary" onClick={() => window.location.href = '/'}>Startseite öffnen</button>
            </div>
            {setupMessage ? <div className="setup-message success">{setupMessage}</div> : null}
            {setupError ? <div className="setup-message error">{setupError}</div> : null}
          </div>
        ) : setupPanelVisible ? (
          <div className="setup-panel setup-panel-standalone">
            <div className="setup-panel-head">
              <div>
                <h2 className="setup-title">{stepTitles[setupMode] || 'Einrichtung'}</h2>
                <p className="setup-subtitle">{stepLabels[setupMode] || 'Schritt'} · {setupMode === 'choose' ? 'Wähle den gewünschten Startweg' : setupMode === 'admin' ? 'Benutzername ist bereits vorbereitet' : setupMode === 'system' ? 'Globale KI- und Fotoeinstellungen' : 'Client-ID, Secret und URL eintragen'}</p>
              </div>
            </div>

            {setupMode === 'choose' ? (
              <div className="setup-choice-grid">
                <button type="button" className="setup-choice-card" onClick={startLocalFlow}>
                  <div className="setup-choice-title">Lokalen Benutzer anlegen</div>
                  <p>Geeignet, wenn du MYND ohne Nextcloud-Login starten willst oder zusätzlich einen Admin behalten möchtest.</p>
                </button>
                <button type="button" className="setup-choice-card" onClick={startNextcloudFlow}>
                  <div className="setup-choice-title">Direkt mit Nextcloud starten</div>
                  <p>Geeignet, wenn du keine lokalen Benutzer verwenden willst und den Login vollständig über Nextcloud machen möchtest.</p>
                </button>
              </div>
            ) : null}

            {setupMode === 'admin' ? (
              <form onSubmit={submitAdmin} className="setup-form">
                <div className="setup-grid">
                  <label className="setup-field">
                    <span>Admin-Benutzer</span>
                    <input value={setupStatus?.admin_user || 'admin'} disabled />
                  </label>
                  <label className="setup-field">
                    <span>Admin-Passwort</span>
                    <input type="password" value={setupForm.adminPassword} onChange={(e) => setSetupForm((current) => ({ ...current, adminPassword: e.target.value }))} placeholder="Neues Admin-Passwort" />
                  </label>
                  <label className="setup-field setup-wide">
                    <span>Anzeigename</span>
                    <input value={setupForm.adminName} onChange={(e) => setSetupForm((current) => ({ ...current, adminName: e.target.value }))} placeholder="z. B. Systemadmin" />
                  </label>
                </div>
                <div className="setup-note">Dieses Konto wird als erster lokaler Administrator angelegt. Danach kannst du dich normal im Login anmelden.</div>
                <div className="setup-footer">
                  <button type="submit" className="btn btn-success" disabled={setupSubmitting}>Admin anlegen</button>
                </div>
              </form>
            ) : null}

            {setupMode === 'system' ? (
              <form onSubmit={submitSystem} className="setup-form">
                <div className="setup-global-stack">
                  <div className="setup-global-summary">
                    <div className="setup-section-eyebrow">Schritt 2 von 3</div>
                    <h3>Globale Dienste</h3>
                    <p>Hier richtest du die globale KI und die Fotointegration nacheinander ein. Alles bleibt optional und kann später im Einstellungsbereich geändert werden.</p>
                    <div className="setup-summary-tip">
                      Wenn du heute nichts global konfigurieren willst, kannst du den Schritt einfach überspringen.
                    </div>
                  </div>

                  <section className={`setup-config-card ${configureOllama ? 'active' : ''}`}>
                    <label className="setup-card-toggle">
                      <input type="checkbox" checked={configureOllama} onChange={(e) => setConfigureOllama(e.target.checked)} />
                      <span>
                        <strong>KI konfigurieren</strong>
                        <small>Ollama, Chat-Modell und Embedding-Modell</small>
                      </span>
                    </label>

                    {configureOllama ? (
                      <div className="setup-card-body">
                        <div className="setup-grid">
                          <label className="setup-field setup-wide">
                            <span>Ollama Base URL</span>
                            <input value={systemForm.baseUrl} onChange={(e) => setSystemForm((current) => ({ ...current, baseUrl: e.target.value }))} placeholder="http://127.0.0.1" />
                          </label>
                          <label className="setup-field">
                            <span>KI-Modell</span>
                            <select value={selectedChatModel || ''} onChange={(e) => setSystemForm((current) => ({ ...current, model: e.target.value }))}>
                              <option value="">Bitte auswählen…</option>
                              {chatModelChoices.map((model) => <option key={model} value={model}>{model}</option>)}
                            </select>
                          </label>
                          <label className="setup-field">
                            <span>Embedding-Modell</span>
                            <select value={selectedEmbeddingModel || ''} onChange={(e) => setSystemForm((current) => ({ ...current, embeddingModel: e.target.value }))}>
                              <option value="">Bitte auswählen…</option>
                              {embeddingModelChoices.map((model) => <option key={model} value={model}>{model}</option>)}
                            </select>
                          </label>
                        </div>
                        <div className="setup-mini-help">
                          <div><strong>KI-Modell:</strong> beantwortet Fragen und schreibt Text.</div>
                          <div><strong>Embedding-Modell:</strong> erstellt Vektoren für semantische Suche.</div>
                        </div>
                      </div>
                    ) : null}
                  </section>

                  <section className={`setup-config-card ${configureImmich ? 'active' : ''}`}>
                    <label className="setup-card-toggle">
                      <input type="checkbox" checked={configureImmich} onChange={(e) => setConfigureImmich(e.target.checked)} />
                      <span>
                        <strong>Immich konfigurieren</strong>
                        <small>Globale Fotoanbindung und API-Key</small>
                      </span>
                    </label>

                    {configureImmich ? (
                      <div className="setup-card-body">
                        <div className="setup-grid">
                          <label className="setup-field setup-wide">
                            <span>Immich URL</span>
                            <input value={systemForm.immichUrlDefault} onChange={(e) => setSystemForm((current) => ({ ...current, immichUrlDefault: e.target.value }))} placeholder="https://immich.example.org" />
                          </label>
                          <label className="setup-field setup-wide">
                            <span>Immich API-Key</span>
                            <input type="password" value={systemForm.immichApiKeyDefault} onChange={(e) => setSystemForm((current) => ({ ...current, immichApiKeyDefault: e.target.value }))} placeholder="Immich API-Key" />
                          </label>
                        </div>
                        <div className="setup-mini-help setup-mini-help-muted">
                          Den API-Key findest du in Immich unter deinem Benutzerprofil oder im API-Keys-Bereich.
                        </div>
                      </div>
                    ) : null}
                  </section>
                </div>

                <div className="setup-footer">
                  <button type="button" className="btn" onClick={skipSystemStep} disabled={setupSubmitting}>Überspringen</button>
                  <button type="submit" className="btn btn-primary" disabled={setupSubmitting}>Speichern und weiter</button>
                </div>
              </form>
            ) : null}

            {setupMode === 'nextcloud' ? (
              <form onSubmit={submitNextcloud} className="setup-form">
                <div className="setup-grid">
                  <label className="setup-field setup-wide">
                    <span>Nextcloud URL</span>
                    <input value={nextcloudForm.nextcloudUrl} onChange={(e) => setNextcloudForm((current) => ({ ...current, nextcloudUrl: e.target.value }))} placeholder="https://cloud.example.org" />
                  </label>
                  <label className="setup-field">
                    <span>Client ID</span>
                    <input value={nextcloudForm.clientId} onChange={(e) => setNextcloudForm((current) => ({ ...current, clientId: e.target.value }))} placeholder="Client ID" />
                  </label>
                  <label className="setup-field">
                    <span>Client Secret</span>
                    <input value={nextcloudForm.clientSecret} onChange={(e) => setNextcloudForm((current) => ({ ...current, clientSecret: e.target.value }))} placeholder="Client Secret" />
                  </label>
                </div>

                <div className="setup-hints">
                  {nextcloudHint.map((item) => <div key={item} className="setup-hint-item">{item}</div>)}
                </div>

                <div className="setup-redirect">
                  <span className="setup-redirect-label">Redirect-URI</span>
                  <code className="setup-redirect-code">{redirectUri}</code>
                  <button type="button" className="btn btn-sm" onClick={copyRedirectUri} style={{marginLeft: '0.5rem'}}>
                    {copyOk ? '✓ Kopiert' : 'Kopieren'}
                  </button>
                </div>

                <div className="setup-note">Speichern aktiviert die Nextcloud-Anmeldung direkt im Webinterface. Das ist die globale Login-Verbindung, nicht die persönliche Benutzer-Verbindung.</div>

                <div className="setup-footer">
                  <button type="button" className="btn" onClick={startLocalFlow} disabled={setupSubmitting}>Ohne Nextcloud fortfahren</button>
                  <button type="submit" className="btn btn-nc" disabled={setupSubmitting}>Nextcloud speichern</button>
                </div>
              </form>
            ) : null}

            {setupMessage ? <div className="setup-message success">{setupMessage}</div> : null}
            {setupError ? <div className="setup-message error">{setupError}</div> : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}