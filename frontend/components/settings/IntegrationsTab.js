'use client';

import { useEffect, useState } from 'react';
import { apiFetch } from '../../lib/api';

const INTEGRATIONS = [
  { id: 'email',         icon: 'fas fa-envelope',      labelDe: 'E-Mail (IMAP/SMTP)', labelEn: 'Email (IMAP/SMTP)' },
  { id: 'immich',        icon: 'fas fa-camera',         labelDe: 'Immich',             labelEn: 'Immich' },
  { id: 'nextcloud',     icon: 'fas fa-cloud',          labelDe: 'Nextcloud',           labelEn: 'Nextcloud' },
  { id: 'homeassistant', icon: 'fas fa-home',           labelDe: 'Home Assistant',      labelEn: 'Home Assistant' },
  { id: 'truenas',       icon: 'fas fa-server',         labelDe: 'TrueNAS',             labelEn: 'TrueNAS' },
  { id: 'server',        icon: 'fas fa-terminal',       labelDe: 'Server (SSH)',        labelEn: 'Server (SSH)' },
  { id: 'spotify',       icon: 'fab fa-spotify',        labelDe: 'Spotify',             labelEn: 'Spotify' },
  { id: 'discord',       icon: 'fab fa-discord',        labelDe: 'Discord',             labelEn: 'Discord' },
  { id: 'plugins',       icon: 'fas fa-puzzle-piece',   labelDe: 'Plugin Manager',      labelEn: 'Plugin Manager' },
];

const FIELD_DEFS = {
  email: [
    { key: 'email/imap_host',     labelDe: 'IMAP Host',         labelEn: 'IMAP Host',         type: 'text' },
    { key: 'email/imap_port',     labelDe: 'IMAP Port',         labelEn: 'IMAP Port',         type: 'text', default: '993' },
    { key: 'email/imap_user',     labelDe: 'IMAP Benutzer',     labelEn: 'IMAP User',         type: 'text' },
    { key: 'email/imap_password', labelDe: 'IMAP Passwort',     labelEn: 'IMAP Password',     type: 'password' },
    { key: 'email/smtp_host',     labelDe: 'SMTP Host',         labelEn: 'SMTP Host',         type: 'text' },
    { key: 'email/smtp_port',     labelDe: 'SMTP Port',         labelEn: 'SMTP Port',         type: 'text', default: '587' },
    { key: 'email/smtp_user',     labelDe: 'SMTP Benutzer',     labelEn: 'SMTP User',         type: 'text' },
    { key: 'email/smtp_password', labelDe: 'SMTP Passwort',     labelEn: 'SMTP Password',     type: 'password' },
  ],
  immich: [
    { key: 'immich/url',    labelDe: 'Immich URL',     labelEn: 'Immich URL',    type: 'text', placeholder: 'https://immich.example.org' },
    { key: 'immich/api_key', labelDe: 'API-Key',        labelEn: 'API Key',       type: 'password' },
  ],
  nextcloud: [
    { key: 'nextcloud/url',      labelDe: 'Nextcloud URL',      labelEn: 'Nextcloud URL',      type: 'text', placeholder: 'https://nc.example.org' },
    { key: 'nextcloud/user',     labelDe: 'Nextcloud Benutzer',  labelEn: 'Nextcloud User',     type: 'text' },
    { key: 'nextcloud/password', labelDe: 'Nextcloud Passwort',  labelEn: 'Nextcloud Password', type: 'password' },
  ],
  homeassistant: [
    { key: 'homeassistant/url',   labelDe: 'Home Assistant URL', labelEn: 'Home Assistant URL', type: 'text', placeholder: 'http://192.168.178.44:8123' },
    { key: 'homeassistant/token', labelDe: 'Langzeit-Zugriffstoken', labelEn: 'Long-Lived Access Token', type: 'password' },
  ],
  truenas: [
    { key: 'truenas/ip',       labelDe: 'TrueNAS IP',       labelEn: 'TrueNAS IP',       type: 'text', placeholder: '192.168.178.44' },
    { key: 'truenas/user',     labelDe: 'TrueNAS Benutzer',  labelEn: 'TrueNAS User',     type: 'text', placeholder: 'admin' },
    { key: 'truenas/password', labelDe: 'TrueNAS Passwort',  labelEn: 'TrueNAS Password',  type: 'password' },
  ],
  server: [
    { key: 'server/ip', labelDe: 'Server IP', labelEn: 'Server IP', type: 'text', placeholder: '192.168.178.44' },
    { key: 'server/user', labelDe: 'Server Benutzer', labelEn: 'Server User', type: 'text', placeholder: 'root' },
    { key: 'server/password', labelDe: 'Server Passwort', labelEn: 'Server Password', type: 'password' },
    { key: 'server/port', labelDe: 'Server Port', labelEn: 'Server Port', type: 'text', default: '22' },
  ],
  spotify: [
    { key: 'spotify/client_id',     labelDe: 'Client-ID',          labelEn: 'Client ID',          type: 'text' },
    { key: 'spotify/client_secret', labelDe: 'Client-Secret',      labelEn: 'Client Secret',      type: 'password' },
    { key: 'spotify/refresh_token', labelDe: 'Refresh-Token',       labelEn: 'Refresh Token',      type: 'password' },
  ],
  discord: [
    { key: 'discord/bot_token', labelDe: 'Bot-Token',            labelEn: 'Bot Token',           type: 'password' },
    { key: 'discord/guild_id',  labelDe: 'Server-ID (optional)', labelEn: 'Guild ID (optional)', type: 'text' },
  ],
};

export default function IntegrationsTab({ tr, language }) {
  const [activeInt, setActiveInt] = useState('email');
  const [values, setValues] = useState({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  const [err, setErr] = useState('');
  const [plugins, setPlugins] = useState([]);
  const [pluginsLoaded, setPluginsLoaded] = useState(false);

  const t = (de, en) => language === 'de' ? de : en;

  const loadAll = async () => {
    try {
      const r = await apiFetch('/api/vault/entries');
      const d = await r.json();
      if (d?.success === false) return;
      const entries = d.entries || [];
      const map = {};
      for (const e of entries) map[e.key] = e.value;
      setValues(map);
    } catch (e) { /* ignore */ }
  };

  const loadPlugins = async () => {
    try {
      const r = await apiFetch('/api/plugins');
      const d = await r.json();
      if (d.success) {
        setPlugins(d.plugins || []);
        setPluginsLoaded(true);
      }
    } catch (e) { console.error('Plugin load failed:', e); }
  };

  useEffect(() => { loadAll(); }, []);
  useEffect(() => { if (activeInt === 'plugins' && !pluginsLoaded) loadPlugins(); }, [activeInt, pluginsLoaded]);

  const setVal = (key, val) => setValues(p => ({ ...p, [key]: val }));
  const isSet = (key) => values[key] === '__SET__';

  const saveIntegration = async () => {
    setSaving(true); setMsg(''); setErr('');
    const fields = FIELD_DEFS[activeInt];
    let ok = true;
    for (const f of fields) {
      const raw = values[f.key];
      if (raw === '__SET__') continue;
      if (raw !== undefined && raw !== '') {
        try {
          const r = await apiFetch('/api/vault/entries', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ key: f.key, value: raw }),
          });
          const d = await r.json();
          if (!r.ok) { ok = false; setErr(d?.error || 'Fehler'); break; }
          if (f.type === 'password') {
            setVal(f.key, '__SET__');
          }
        } catch (ex) { ok = false; setErr(ex.message); break; }
      }
    }
    if (ok) setMsg(tr('Gespeichert im Tresor.', 'Saved to vault.'));
    setSaving(false);
  };

  const handleToggle = async (name, enabled) => {
    try {
      await apiFetch(`/api/plugins/${name}/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
      });
      setPlugins(plugins.map(p => p.name === name ? { ...p, enabled } : p));
    } catch (e) { console.error('Toggle failed:', e); }
  };

  const handleUninstall = async (name) => {
    if (!window.confirm(t(`Plugin "${name}" wirklich deinstallieren?`, `Really uninstall "${name}"?`))) return;
    try {
      const r = await apiFetch(`/api/plugins/${name}`, { method: 'DELETE' });
      const d = await r.json();
      if (d.success) {
        setPlugins(plugins.filter(p => p.name !== name));
      } else {
        alert(d.error || t('Fehler beim Deinstallieren', 'Uninstall failed'));
      }
    } catch (e) { alert(String(e)); }
  };

  const testConnection = async (integrationId) => {
    setMsg(''); setErr('');
    try {
      const r = await apiFetch(`/api/registry/${integrationId}/test`, { method: 'POST' });
      const d = await r.json();
      if (d.success) setMsg(t('Verbindung erfolgreich!', 'Connection successful!'));
      else setErr(d.error || t('Verbindung fehlgeschlagen', 'Connection failed'));
    } catch (e) { setErr(e.message); }
  };

  const currentFields = FIELD_DEFS[activeInt] || [];
  const intLabel = INTEGRATIONS.find(i => i.id === activeInt);

  if (activeInt === 'plugins') {
    return (
      <div className="settings-panel" style={{ padding: 0, overflow: 'hidden', height: '100%', display: 'flex', flexDirection: 'column' }}>
        <div className="integrations-layout">
          <div className="integrations-nav">
            <div className="integrations-nav-label">{t('Integrationen', 'Integrations')}</div>
            <div className="integrations-nav-items">
              {INTEGRATIONS.map(int => (
                <button key={int.id}
                  className={`integrations-nav-item ${activeInt === int.id ? 'active' : ''}`}
                  onClick={() => setActiveInt(int.id)}>
                  <i className={int.icon}></i>{t(int.labelDe, int.labelEn)}
                </button>
              ))}
            </div>
          </div>
          <div className="integrations-content">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
              <div>
                <div style={{ fontSize: '1.1rem', fontWeight: 700 }}>
                  <i className="fas fa-puzzle-piece" style={{ marginRight: 8 }}></i>
                  {t('Plugin Manager', 'Plugin Manager')}
                </div>
                <p style={{ fontSize: '0.85rem', color: 'var(--muted)', margin: '0.25rem 0 0' }}>
                  {t(`${plugins.length} Plugin(s)`, `${plugins.length} plugin(s)`)}
                  {' · '}
                  {t(`${plugins.filter(p => p.enabled).length} aktiv`, `${plugins.filter(p => p.enabled).length} active`)}
                </p>
              </div>
            </div>

            {!pluginsLoaded ? (
              <p style={{ color: 'var(--muted)' }}>{t('Lade...', 'Loading...')}</p>
            ) : plugins.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '2.5rem 1rem', color: 'var(--muted)' }}>
                <i className="fas fa-puzzle-piece" style={{ fontSize: 40, opacity: 0.2, marginBottom: 12, display: 'block' }}></i>
                <p>{t('Keine Plugins installiert.', 'No plugins installed.')}</p>
                <p style={{ fontSize: '0.85rem' }}>{t('Installiere eines via GitHub-URL oben.', 'Install one via the GitHub URL above.')}</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {plugins.map(p => (
                  <div key={p.name} style={{ border: '1px solid var(--line)', borderRadius: 'var(--radius)', padding: '1rem', background: 'var(--card-bg)', opacity: p.enabled ? 1 : 0.45 }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                      <label style={{ position: 'relative', display: 'inline-block', width: 36, height: 20, flexShrink: 0, marginTop: 2 }}>
                        <input type="checkbox" checked={p.enabled} onChange={e => handleToggle(p.name, e.target.checked)}
                          style={{ opacity: 0, width: 0, height: 0 }} />
                        <span style={{ position: 'absolute', cursor: 'pointer', inset: 0, background: p.enabled ? 'var(--brand)' : 'var(--border)', borderRadius: 20, transition: '0.3s' }}>
                          <span style={{ position: 'absolute', height: 14, width: 14, left: p.enabled ? 19 : 3, bottom: 3, background: '#fff', borderRadius: '50%', transition: '0.3s' }}></span>
                        </span>
                      </label>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                          <strong style={{ fontSize: '0.95rem' }}>{p.name}</strong>
                          <span style={{ fontSize: '0.7rem', color: 'var(--muted)', background: 'var(--bg-2)', padding: '0.05rem 0.5rem', borderRadius: 'var(--radius-sm)', fontFamily: 'monospace' }}>v{p.version}</span>
                          <span style={{ fontSize: '0.7rem', color: p.tool_count > 0 ? 'var(--muted)' : 'var(--danger)', background: p.tool_count > 0 ? 'color-mix(in srgb, var(--brand) 10%, transparent)' : 'color-mix(in srgb, var(--danger) 10%, transparent)', padding: '0.05rem 0.5rem', borderRadius: 'var(--radius-sm)' }}>
                            {p.tool_count} {t('Tools', 'Tools')}
                          </span>
                          {!p.enabled && (
                            <span style={{ fontSize: '0.7rem', color: 'var(--muted)', background: 'var(--chip-bg)', padding: '0.05rem 0.5rem', borderRadius: 'var(--radius-sm)' }}>
                              {t('deaktiviert', 'disabled')}
                            </span>
                          )}
                        </div>
                        {p.description && <p style={{ fontSize: '0.82rem', color: 'var(--muted)', margin: '0.3rem 0 0', lineHeight: 1.4 }}>{p.description}</p>}
                      </div>
                      <button className="btn secondary" style={{ padding: '4px 8px', fontSize: '0.75em', flexShrink: 0, marginTop: 1 }}
                        onClick={() => handleUninstall(p.name)} title={t('Deinstallieren', 'Uninstall')}>
                        <i className="fas fa-trash"></i>
                      </button>
                    </div>
                    {p.tools?.length > 0 && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--line)' }}>
                        {p.tools.map(tn => (
                          <span key={tn} style={{ fontSize: '0.72rem', fontFamily: 'monospace', background: 'color-mix(in srgb, var(--brand) 8%, var(--bg-2))', color: 'var(--muted)', fontWeight: p.enabled ? 400 : 300, padding: '0.15rem 0.55rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--line)' }}>{tn}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  const hasTest = ['immich', 'nextcloud', 'homeassistant', 'truenas', 'spotify', 'discord'].includes(activeInt);

  return (
    <div className="settings-panel" style={{ padding: 0, overflow: 'hidden', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div className="integrations-layout">
        <div className="integrations-nav">
          <div className="integrations-nav-label">{t('Integrationen', 'Integrations')}</div>
          <div className="integrations-nav-items">
            {INTEGRATIONS.map(int => (
              <button key={int.id}
                className={`integrations-nav-item ${activeInt === int.id ? 'active' : ''}`}
                onClick={() => setActiveInt(int.id)}>
                <i className={int.icon}></i>{t(int.labelDe, int.labelEn)}
              </button>
            ))}
          </div>
        </div>

        <div className="integrations-content">
          <div style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '0.25rem' }}>
            <i className={intLabel?.icon} style={{ marginRight: 8 }}></i>
            {t(intLabel?.labelDe, intLabel?.labelEn)}
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--muted)', marginBottom: '1.25rem' }}>
            {activeInt === 'spotify'
              ? t('Benötigt eine Spotify App im Developer Dashboard. Client-ID und -Secret eintragen, dann Authorization Code Grant durchführen.',
                 'Requires a Spotify App in the Developer Dashboard. Enter Client ID and Secret, then perform Authorization Code Grant.')
              : activeInt === 'discord'
              ? t('Erstelle einen Discord Bot im Developer Portal und trage den Token ein. Optionales Guild-ID-Filter für Server-spezifische Befehle.',
                 'Create a Discord Bot in the Developer Portal and enter the token. Optional guild ID filter for server-specific commands.')
              : t('Alle Werte werden lokal im Tresor gespeichert. Bestehende Passwörter bleiben erhalten, wenn du das Feld leer lässt.',
                 'All values are stored locally in the vault. Existing passwords are preserved when left empty.')}
          </p>

          {activeInt === 'email' ? <EmailAccountsSection tr={tr} language={language} values={values} setVal={setVal} isSet={isSet} /> : (
          <>  
          <div className="input-group" style={{ marginBottom: '0.75rem', fontSize: '0.8rem', color: 'var(--muted)', background: 'var(--chip-bg)', borderRadius: 'var(--radius-sm)', padding: '0.5rem 0.75rem' }}>
            <i className="fas fa-shield-alt" style={{ marginRight: 6 }}></i>
            {t('Gespeichert im Tresor', 'Stored in vault')}
          </div>

          {currentFields.map(f => {
            const currentVal = values[f.key];
            const isPasswordSet = f.type === 'password' && isSet(f.key);
            return (
              <label key={f.key} className="input-group" style={{ marginBottom: '1rem' }}>
                <label style={{ fontSize: '0.8rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>{t(f.labelDe, f.labelEn)}</span>
                  <code style={{ fontSize: '0.65rem', color: 'var(--muted)', background: 'var(--chip-bg)', padding: '0.1rem 0.4rem', borderRadius: '4px' }}>{f.key}</code>
                </label>
                <input type={f.type}
                  value={isPasswordSet ? '' : (currentVal ?? f.default ?? '')}
                  onChange={e => setVal(f.key, e.target.value)}
                  placeholder={isPasswordSet ? t('•••••• (ausgefüllt – leer lassen = behalten)', '•••••• (set – leave empty = keep)') : (f.placeholder || t('Eingeben...', 'Enter...'))}
                  style={{ marginTop: '4px' }} />
              </label>
            );
          })}

          {msg && <div className="status-text" style={{ color: 'var(--success)', marginBottom: '0.75rem' }}>{msg}</div>}
          {err && <div className="status-text" style={{ color: '#ef4444', marginBottom: '0.75rem' }}>{err}</div>}

          <div className="button-group" style={{ marginTop: '0.5rem', display: 'flex', gap: 8 }}>
            <button className="btn primary" onClick={saveIntegration} disabled={saving}>
              <i className="fas fa-save" style={{ marginRight: 6 }}></i>
              {saving ? t('Speichere…', 'Saving…') : t('Im Tresor speichern', 'Save to Vault')}
            </button>
            {hasTest && (
              <button className="btn" onClick={() => testConnection(activeInt)}>
                <i className="fas fa-plug" style={{ marginRight: 6 }}></i>
                {t('Verbindung testen', 'Test Connection')}
              </button>
            )}
          </div>
          </>  
          )}
        </div>
      </div>
    </div>
  );
}


/* ── Mehrere E-Mail-Konten ──────────────────────────── */

const EMAIL_FIELDS = [
  { key: 'imap_server', labelDe: 'IMAP Server', labelEn: 'IMAP Server', type: 'text', placeholder: 'imap.example.com' },
  { key: 'imap_port', labelDe: 'IMAP Port', labelEn: 'IMAP Port', type: 'text', default: '993' },
  { key: 'imap_user', labelDe: 'IMAP Benutzer', labelEn: 'IMAP User', type: 'text' },
  { key: 'imap_password', labelDe: 'IMAP Passwort', labelEn: 'IMAP Password', type: 'password' },
  { key: 'smtp_server', labelDe: 'SMTP Server', labelEn: 'SMTP Server', type: 'text', placeholder: 'smtp.example.com' },
  { key: 'smtp_port', labelDe: 'SMTP Port', labelEn: 'SMTP Port', type: 'text', default: '587' },
  { key: 'smtp_user', labelDe: 'SMTP Benutzer', labelEn: 'SMTP User', type: 'text' },
  { key: 'smtp_password', labelDe: 'SMTP Passwort', labelEn: 'SMTP Password', type: 'password' },
];

function EmailAccountsSection({ tr, language, values, setVal, isSet }) {
  const t = (de, en) => language === 'de' ? de : en;
  const [accounts, setAccounts] = useState([]);
  const [editing, setEditing] = useState(null);
  const [newName, setNewName] = useState('');
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');

  const loadAccounts = async () => {
    try {
      const r = await apiFetch('/api/email/accounts');
      const d = await r.json();
      if (d.success) setAccounts(Object.entries(d.accounts || {}).map(([k,v]) => ({ name: k, ...v })));
    } catch(e) { console.error(e); }
  };

  useEffect(() => { loadAccounts(); }, []);

  const saveAccount = async (name) => {
    setSaving(true); setMsg('');
    try {
      const payload = { name, ...form };
      await apiFetch('/api/email/accounts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (name === 'default') {
        for (const f of EMAIL_FIELDS) {
          if (form[f.key]) {
            await apiFetch('/api/vault/entries', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ key: `email/${f.key}`, value: form[f.key] }),
            });
          }
        }
      }
      setMsg(t('Konto gespeichert!', 'Account saved!'));
      await loadAccounts();
      setEditing(null);
    } catch(e) { setMsg('❌ ' + e.message); }
    setSaving(false);
  };

  const deleteAccount = async (name) => {
    if (!window.confirm(t(`Konto "${name}" löschen?`, `Delete account "${name}"?`))) return;
    try {
      await apiFetch(`/api/email/accounts/${name}`, { method: 'DELETE' });
      await loadAccounts();
    } catch(e) { console.error(e); }
  };

  const startEdit = (acct) => {
    setForm({
      imap_server: acct.imap_server || '',
      imap_port: acct.imap_port || '993',
      imap_user: acct.imap_user || '',
      imap_password: '',
      smtp_server: acct.smtp_server || '',
      smtp_port: acct.smtp_port || '587',
      smtp_user: acct.smtp_user || '',
      smtp_password: '',
    });
    setEditing(acct.name);
  };

  return (
    <div>
      <div style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: '0.75rem' }}>
          <input type="text" value={newName} onChange={e => setNewName(e.target.value)}
            placeholder={t('Neues Konto (z.B. work)', 'New account name (e.g. work)')}
            style={{ flex: 1, background: 'var(--input-bg)', border: '1px solid var(--line)', borderRadius: 'var(--radius-sm)', padding: '0.5rem 0.75rem', color: 'var(--ink)', fontSize: '0.85rem' }} />
          <button className="btn primary" onClick={() => { if(newName.trim()) startEdit({ name: newName.trim() }); }}>
            <i className="fas fa-plus"></i>
          </button>
        </div>
      </div>

      {accounts.length === 0 && <p style={{ color: 'var(--muted)', textAlign: 'center', padding: '1rem' }}>{t('Keine E-Mail-Konten konfiguriert.', 'No email accounts configured.')}</p>}

      {accounts.map(acct => (
        <div key={acct.name} style={{ border: '1px solid var(--line)', borderRadius: 'var(--radius)', padding: '0.75rem', marginBottom: '0.75rem', background: 'var(--card-bg)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
            <strong><i className="fas fa-envelope" style={{ marginRight: 6 }}></i>{acct.name}</strong>
            <div style={{ display: 'flex', gap: 6 }}>
              <button className="btn" onClick={() => startEdit(acct)} style={{ padding: '0.25rem 0.6rem', fontSize: '0.8rem' }}>
                <i className="fas fa-edit"></i>
              </button>
              <button className="btn" onClick={() => deleteAccount(acct.name)} style={{ padding: '0.25rem 0.6rem', fontSize: '0.8rem', color: '#ef4444' }}>
                <i className="fas fa-trash"></i>
              </button>
            </div>
          </div>
          <div style={{ fontSize: '0.82rem', color: 'var(--muted)' }}>
            {acct.imap_user ? `${acct.imap_user} @ ` : ''}{acct.imap_server || t('Nicht konfiguriert', 'Not configured')}
          </div>
        </div>
      ))}

      {editing && (
        <div style={{ border: '2px solid var(--brand)', borderRadius: 'var(--radius)', padding: '1rem', marginBottom: '1rem', background: 'var(--chip-bg)' }}>
          <div style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '0.75rem' }}>
            <i className="fas fa-pen"></i> {t('Bearbeite', 'Edit')}: {editing}
          </div>
          {EMAIL_FIELDS.map(f => (
            <label key={f.key} className="input-group" style={{ marginBottom: '0.75rem' }}>
              <label style={{ fontSize: '0.8rem' }}>{t(f.labelDe, f.labelEn)}</label>
              <input type={f.type}
                value={form[f.key] ?? f.default ?? ''}
                onChange={e => setForm(p => ({...p, [f.key]: e.target.value}))}
                placeholder={f.type === 'password' ? t('Neu (optional)', 'New (optional)') : f.placeholder || ''}
                style={{ marginTop: '4px' }} />
            </label>
          ))}
          {msg && <p style={{ fontSize: '0.82rem', color: 'var(--success)', margin: '0.5rem 0' }}>{msg}</p>}
          <div className="button-group" style={{ marginTop: '0.5rem' }}>
            <button className="btn primary" onClick={() => saveAccount(editing)} disabled={saving}>
              {saving ? t('Speichere...', 'Saving...') : t('Speichern', 'Save')}
            </button>
            <button className="btn" onClick={() => { setEditing(null); setMsg(''); }} style={{ marginLeft: 8 }}>
              {t('Abbrechen', 'Cancel')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
