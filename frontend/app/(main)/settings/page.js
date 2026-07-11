'use client';

import { useState } from 'react';
import { useLanguage } from '../../../hooks/useLanguage';
import { useApp } from '../../../lib/AppContext';
import IntegrationsTab from '../../../components/settings/IntegrationsTab';
import ConfigTab from '../../../components/settings/ConfigTab';
import ApiRefsTab from '../../../components/settings/ApiRefsTab';
import VaultTab from '../../../components/settings/VaultTab';
import IndexingTab from '../../../components/settings/IndexingTab';
import DesignTab from '../../../components/settings/DesignTab';
import MemoryTab from '../../../components/settings/MemoryTab';
import AutomationsTab from '../../../components/settings/AutomationsTab';
import AdminTab from '../../../components/settings/AdminTab';
import ProfileTab from '../../../components/settings/ProfileTab';

const NAV_GROUPS = [
  { labelDe: 'Allgemein', labelEn: 'General', items: [{ key: 'profile', icon: 'fa-user', label: 'Profil', labelEn: 'Profile' }] },
  { labelDe: 'System', labelEn: 'System', items: [{ key: 'config', icon: 'fa-cog', labelKey: 'tabConfig' }, { key: 'automations', icon: 'fa-clock', label: 'Automatisierungen', labelEn: 'Automations' }] },
  { labelDe: 'Daten', labelEn: 'Data', items: [{ key: 'vault', icon: 'fa-lock', label: 'Tresor', labelEn: 'Vault' }, { key: 'memory', icon: 'fa-brain', label: 'Memory', labelEn: 'Memory' }, { key: 'api-refs', icon: 'fa-book', label: 'API-Referenzen', labelEn: 'API Refs' }] },
  { labelDe: 'Verbindungen', labelEn: 'Connections', items: [{ key: 'integrations', icon: 'fa-puzzle-piece', label: 'Integrationen', labelEn: 'Integrations' }] },
  { labelDe: 'Inhalt', labelEn: 'Content', items: [{ key: 'indexing', icon: 'fa-search', labelKey: 'tabIndexing' }] },
  { labelDe: 'Darstellung', labelEn: 'Appearance', items: [{ key: 'design', icon: 'fa-palette', labelKey: 'tabDesign' }] },
  { labelDe: 'Administration', labelEn: 'Administration', items: [{ key: 'admin', icon: 'fa-shield', label: 'Admin', labelEn: 'Admin' }] }
];

const tr = (de, en, lang) => lang === 'de' ? de : en;

export default function SettingsPage() {
  const { language, t } = useLanguage();
  const [activeTab, setActiveTab] = useState('profile');

  return (
    <div className="center-area">
      <div className="settings-page-layout">
        <div className="settings-page-header">
          <div className="settings-page-header-left">
            <h2><i className="fas fa-cog"></i> {t('settings')}</h2>
          </div>
        </div>
        <div className="settings-body">
          <div className="settings-nav">
            {NAV_GROUPS.map(group => (
              <div key={group.labelDe} className="settings-nav-group">
                <div className="settings-nav-group-label">{language === 'de' ? group.labelDe : group.labelEn}</div>
                {group.items.map(item => {
                  const label = item.labelKey ? t(item.labelKey) : (language === 'de' ? item.label : item.labelEn);
                  return (
                    <button key={item.key}
                      className={`settings-nav-item ${activeTab === item.key ? 'active' : ''}`}
                      onClick={() => setActiveTab(item.key)}>
                      <i className={`fas ${item.icon}`}></i>
                      <span>{label}</span>
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
          <div className="settings-content">
            {activeTab === 'profile' && <ProfileTab tr={(d, e) => tr(d, e, language)} language={language} />}
            {activeTab === 'config' && <ConfigTab tr={(d, e) => tr(d, e, language)} language={language} />}
            {activeTab === 'automations' && <AutomationsTab tr={(d, e) => tr(d, e, language)} language={language} />}
            {activeTab === 'api-refs' && <ApiRefsTab tr={(d, e) => tr(d, e, language)} language={language} />}
            {activeTab === 'vault' && <VaultTab tr={(d, e) => tr(d, e, language)} language={language} />}
            {activeTab === 'integrations' && <IntegrationsTab tr={(d, e) => tr(d, e, language)} language={language} />}
            {activeTab === 'indexing' && <IndexingTab tr={(d, e) => tr(d, e, language)} language={language} />}
            {activeTab === 'memory' && <MemoryTab tr={(d, e) => tr(d, e, language)} language={language} />}
            {activeTab === 'design' && <DesignTab tr={(d, e) => tr(d, e, language)} />}
            {activeTab === 'admin' && <AdminTab tr={(d, e) => tr(d, e, language)} language={language} />}
          </div>
        </div>
      </div>
    </div>
  );
}
