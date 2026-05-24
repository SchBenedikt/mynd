"use client";

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import './AuthGate.css';

export default function SetupWizard() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [setupStatus, setSetupStatus] = useState(null);
  const [setupMode, setSetupMode] = useState('');
  const [setupSubmitting, setSetupSubmitting] = useState(false);
  const [setupMessage, setSetupMessage] = useState('');
  const [setupError, setSetupError] = useState('');
  const [setupComplete, setSetupComplete] = useState(false);
  const [setupForm, setSetupForm] = useState({
    adminName: '',
    adminPassword: '',
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
            setSetupMode((current) => current || 'admin');
            setSetupForm((current) => ({
              ...current,
              adminName: current.adminName || data.admin_user || 'admin'
            }));
          } else {
            setSetupComplete(true);
          }
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const mode = searchParams.get('mode');
    if (mode === 'admin' || mode === 'nextcloud') {
      setSetupMode(mode);
    }
  }, [searchParams]);

  useEffect(() => {
    if (setupComplete || setupAlreadyFinished) {
      router.replace('/');
    }
  }, [setupComplete, setupAlreadyFinished, router]);

  const submitBootstrap = async (ev) => {
    ev.preventDefault();
    setSetupError('');
    setSetupMessage('');
    setSetupComplete(false);
    setSetupSubmitting(true);
    try {
      const payload = {
        mode: setupMode,
        admin_name: setupForm.adminName,
        admin_password: setupForm.adminPassword,
        client_id: setupForm.clientId,
        client_secret: setupForm.clientSecret,
        nextcloud_url: setupForm.nextcloudUrl
      };
      const resp = await fetch('/api/setup/bootstrap', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await resp.json();
      if (!resp.ok || !data.success) {
        setSetupError((data && data.error) ? String(data.error) : 'Setup fehlgeschlagen');
        return;
      }

      if (data.admin_created) {
        setSetupMessage('Admin wurde angelegt. Jetzt kannst du dich mit dem lokalen Login anmelden.');
        setSetupMode('');
        setSetupComplete(true);
      } else if (data.oauth_configured) {
        setSetupMessage('Nextcloud OAuth wurde gespeichert. Du kannst jetzt die Nextcloud-Anmeldung nutzen.');
        setSetupMode('');
        setSetupComplete(true);
      }

      try {
        const statusResp = await fetch('/api/setup/status');
        const statusData = await statusResp.json();
        if (statusData && statusData.success) setSetupStatus(statusData);
      } catch (err) {}
    } catch (err) {
      setSetupError('Das Setup konnte gerade nicht gespeichert werden. Bitte prüfe die Verbindung oder versuche es noch einmal.');
    } finally {
      setSetupSubmitting(false);
    }
  };

  const redirectUri = typeof window !== 'undefined'
    ? `${window.location.origin}/api/auth/nextcloud/callback`
    : '/api/auth/nextcloud/callback';

  const nextcloudHint = [
    'In Nextcloud als Admin eine OAuth2-App anlegen oder die vorhandene OAuth2-Funktion nutzen.',
    'Die Callback-URL in der Nextcloud-App muss exakt auf die unten angezeigte Redirect-URI zeigen.',
    'Danach Client ID und Client Secret hier eintragen und speichern.'
  ];

  const setupAlreadyFinished = Boolean(setupStatus && !setupStatus.needs_setup);
  const setupPanelVisible = !setupAlreadyFinished && (Boolean(setupStatus?.needs_setup) || setupMode === 'admin' || setupMode === 'nextcloud');
  const currentStepLabel = setupMode === 'nextcloud' ? 'Schritt 2 von 2' : 'Schritt 1 von 2';

  return (
    <div className="setup-page">
      <div className="setup-page-shell">
        <div className="setup-page-hero">
          <div>
            <div className="setup-page-kicker">Einrichtung</div>
            <h1>MYND konfigurieren</h1>
            <p>Wähle einen Weg. Erst richtest du MYND ein, danach erscheint die normale Anmeldung als nächste Station.</p>
            <div className="setup-stepline" aria-label="Einrichtungsstatus">
              <span className={`setup-stepchip ${setupMode !== 'nextcloud' ? 'active' : ''}`}>1 Einrichtung</span>
              <span className={`setup-stepchip ${setupMode === 'nextcloud' ? 'active' : ''}`}>2 Anmeldung</span>
            </div>
          </div>
        </div>

        {!setupAlreadyFinished ? (
          <div className="setup-choice-grid">
            <button type="button" className={`setup-choice-card ${setupMode === 'admin' ? 'selected' : ''}`} onClick={() => setSetupMode('admin')} disabled={!setupStatus?.needs_setup}>
              <div className="setup-choice-title">1. Lokales Admin-Konto</div>
              <p>Für den ersten Start: einmal einen lokalen Administrator anlegen und direkt danach normal anmelden.</p>
            </button>
            <button type="button" className={`setup-choice-card ${setupMode === 'nextcloud' ? 'selected' : ''}`} onClick={() => setSetupMode('nextcloud')}>
              <div className="setup-choice-title">2. Nextcloud OAuth</div>
              <p>Wenn Nextcloud dein Einstieg sein soll: verbinden, speichern und dann mit derselben Anmeldefläche weiterarbeiten.</p>
            </button>
          </div>
        ) : null}

        {setupPanelVisible ? (
          <div className="setup-panel setup-panel-standalone">
            <div className="setup-panel-head">
              <div>
                <h2 className="setup-title">{setupMode === 'nextcloud' ? 'Nextcloud verbinden' : 'Lokales Admin-Konto anlegen'}</h2>
                <p className="setup-subtitle">{currentStepLabel} · {setupMode === 'nextcloud' ? 'Client-ID, Secret und URL eintragen' : 'Benutzername ist bereits vorbereitet'}</p>
              </div>
            </div>

            {setupMode === 'admin' ? (
              <form onSubmit={submitBootstrap} className="setup-form">
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

            {setupMode === 'nextcloud' ? (
              <form onSubmit={submitBootstrap} className="setup-form">
                <div className="setup-grid">
                  <label className="setup-field setup-wide">
                    <span>Nextcloud URL</span>
                    <input value={setupForm.nextcloudUrl} onChange={(e) => setSetupForm((current) => ({ ...current, nextcloudUrl: e.target.value }))} placeholder="https://cloud.example.org" />
                  </label>
                  <label className="setup-field">
                    <span>Client ID</span>
                    <input value={setupForm.clientId} onChange={(e) => setSetupForm((current) => ({ ...current, clientId: e.target.value }))} placeholder="Client ID" />
                  </label>
                  <label className="setup-field">
                    <span>Client Secret</span>
                    <input value={setupForm.clientSecret} onChange={(e) => setSetupForm((current) => ({ ...current, clientSecret: e.target.value }))} placeholder="Client Secret" />
                  </label>
                </div>

                <div className="setup-hints">
                  {nextcloudHint.map((item) => <div key={item} className="setup-hint-item">{item}</div>)}
                </div>

                <div className="setup-redirect">
                  <span className="setup-redirect-label">Redirect-URI</span>
                  <code className="setup-redirect-code">{redirectUri}</code>
                </div>

                <div className="setup-note">Speichern aktiviert die Nextcloud-Anmeldung direkt im Webinterface.</div>

                <div className="setup-footer">
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