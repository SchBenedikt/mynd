"use client";

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import './AuthGate.css';

export default function SetupWizard() {
  const router = useRouter();
  const [setupStatus, setSetupStatus] = useState(null);
  const [setupMode, setSetupMode] = useState('choose');
  const [setupSubmitting, setSetupSubmitting] = useState(false);
  const [setupMessage, setSetupMessage] = useState('');
  const [setupError, setSetupError] = useState('');
  const [setupComplete, setSetupComplete] = useState(false);
  const [setupFlowStarted, setSetupFlowStarted] = useState(false);
  const [systemConfigLoaded, setSystemConfigLoaded] = useState(false);
  const [nextcloudConfigLoaded, setNextcloudConfigLoaded] = useState(false);
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
    immichUrlDefault: '',
    immichApiKeyDefault: ''
  });
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
              immichUrlDefault: data.config.immich_url_default || '',
              immichApiKeyDefault: data.config.immich_api_key_default || ''
            }));
          }
        })
        .catch(() => {})
        .finally(() => setSystemConfigLoaded(true));
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
  }, [setupMode, systemConfigLoaded, nextcloudConfigLoaded]);

  const setupAlreadyFinished = Boolean(setupStatus && !setupStatus.needs_setup && !setupFlowStarted);

  useEffect(() => {
    if (setupComplete || setupAlreadyFinished) {
      router.replace('/');
    }
  }, [setupComplete, setupAlreadyFinished, router]);

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
      if (statusData && statusData.success) setSetupStatus(statusData);
    } catch (err) {}
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
      await postSetup({
        mode: 'system',
        base_url: systemForm.baseUrl,
        model: systemForm.model,
        immich_url_default: systemForm.immichUrlDefault,
        immich_api_key_default: systemForm.immichApiKeyDefault
      });
      setSetupMessage('Globale KI- und Immich-Werte wurden gespeichert. Weiter geht es mit Nextcloud.');
      setSetupMode('nextcloud');
      setNextcloudConfigLoaded(false);
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
      setSetupMessage('Nextcloud OAuth wurde gespeichert. Die Einrichtung ist damit abgeschlossen.');
      setSetupComplete(true);
      await refreshSetupStatus();
    } catch (err) {
      setSetupError(err.message || 'Das Setup konnte gerade nicht gespeichert werden. Bitte prüfe die Verbindung oder versuche es noch einmal.');
    } finally {
      setSetupSubmitting(false);
    }
  };

  const skipSystemStep = async () => {
    setSetupError('');
    setSetupMessage('Globale KI- und Immich-Werte werden später konfiguriert.');
    setSetupMode('nextcloud');
    setNextcloudConfigLoaded(false);
    await refreshSetupStatus();
  };

  const startLocalFlow = () => {
    setSetupError('');
    setSetupMessage('');
    setSetupMode('admin');
  };

  const startNextcloudFlow = () => {
    setSetupError('');
    setSetupMessage('');
    setSetupMode('nextcloud');
  };

  const skipNextcloudStep = () => {
    setSetupError('');
    setSetupMessage('Nextcloud OAuth wird später eingerichtet.');
    setSetupComplete(true);
  };

  const redirectUri = typeof window !== 'undefined'
    ? `${window.location.origin}/api/auth/nextcloud/callback`
    : '/api/auth/nextcloud/callback';

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

  const setupPanelVisible = !setupAlreadyFinished && Boolean(setupMode);

  return (
    <div className="setup-page">
      <div className="setup-page-shell">
        <div className="setup-page-hero">
          <div>
            <div className="setup-page-kicker">Einrichtung</div>
            <h1>MYND konfigurieren</h1>
            <p>Die Einrichtung läuft in einer festen Reihenfolge. Du kannst aber beim Start wählen, ob du zuerst einen lokalen Benutzer anlegst oder direkt Nextcloud als Login verwendest.</p>
            <div className="setup-stepline" aria-label="Einrichtungsstatus">
              <span className={`setup-stepchip ${setupMode === 'choose' ? 'active' : ''}`}>Start</span>
              <span className={`setup-stepchip ${setupMode === 'admin' ? 'active' : ''}`}>Benutzer</span>
              <span className={`setup-stepchip ${setupMode === 'system' ? 'active' : ''}`}>Global</span>
              <span className={`setup-stepchip ${setupMode === 'nextcloud' ? 'active' : ''}`}>Nextcloud</span>
            </div>
          </div>
        </div>

        {setupPanelVisible ? (
          <div className="setup-panel setup-panel-standalone">
            <div className="setup-panel-head">
              <div>
                <h2 className="setup-title">{stepTitles[setupMode] || 'Einrichtung'}</h2>
                <p className="setup-subtitle">{stepLabels[setupMode] || 'Schritt'} · {setupMode === 'choose' ? 'Wähle den gewünschten Startweg' : setupMode === 'admin' ? 'Benutzername ist bereits vorbereitet' : setupMode === 'system' ? 'Optionale globale Werte' : 'Client-ID, Secret und URL eintragen'}</p>
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
                <div className="setup-grid">
                  <label className="setup-field setup-wide">
                    <span>Ollama Base URL</span>
                    <input value={systemForm.baseUrl} onChange={(e) => setSystemForm((current) => ({ ...current, baseUrl: e.target.value }))} placeholder="http://127.0.0.1" />
                  </label>
                  <label className="setup-field">
                    <span>Ollama Modell</span>
                    <input value={systemForm.model} onChange={(e) => setSystemForm((current) => ({ ...current, model: e.target.value }))} placeholder="gemma3:latest" />
                  </label>
                  <label className="setup-field">
                    <span>Immich URL</span>
                    <input value={systemForm.immichUrlDefault} onChange={(e) => setSystemForm((current) => ({ ...current, immichUrlDefault: e.target.value }))} placeholder="https://immich.example.org" />
                  </label>
                  <label className="setup-field setup-wide">
                    <span>Immich API-Key</span>
                    <input value={systemForm.immichApiKeyDefault} onChange={(e) => setSystemForm((current) => ({ ...current, immichApiKeyDefault: e.target.value }))} placeholder="Immich API-Key" />
                  </label>
                </div>
                <div className="setup-note">Das ist optional. Wenn du jetzt nichts einträgst, kannst du alles später im normalen Einstellungsbereich setzen.</div>
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
                </div>

                <div className="setup-note">Speichern aktiviert die Nextcloud-Anmeldung direkt im Webinterface. Das ist die globale Login-Verbindung, nicht die persönliche Benutzer-Verbindung.</div>

                <div className="setup-footer">
                  <button type="button" className="btn" onClick={skipNextcloudStep} disabled={setupSubmitting}>Ohne Nextcloud fortfahren</button>
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