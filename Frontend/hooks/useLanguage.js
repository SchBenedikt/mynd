'use client';

import { useMemo, useState, useEffect } from 'react';

const LANGUAGE_STORAGE_KEY = 'mynd_language';

export const SUPPORTED_LANGUAGES = [
  { code: 'de', label: 'Deutsch' },
  { code: 'en', label: 'English' },
  { code: 'fr', label: 'Français' },
  { code: 'es', label: 'Español' },
  { code: 'it', label: 'Italiano' },
  { code: 'pt', label: 'Português' },
  { code: 'nl', label: 'Nederlands' },
  { code: 'pl', label: 'Polski' },
  { code: 'tr', label: 'Türkçe' },
  { code: 'ru', label: 'Русский' },
  { code: 'ja', label: '日本語' },
  { code: 'zh', label: '中文' }
];

const TRANSLATIONS = {
  de: {
    newChat: 'Neuer Chat',
    settings: 'Einstellungen',
    currentChat: 'Aktueller Chat',
    askHeading: 'Was liegt dir auf dem Herzen?',
    askSubheading: 'Frag mich alles zu deiner Wissensbasis.',
    askPlaceholder: 'Stelle eine Frage...',
    composerPlaceholder: 'Deine Nachricht hier...',
    documentIndexing: 'Dokumenten-Indexierung',
    current: 'Aktuell',
    files: 'Dateien',
    speed: 'Geschwindigkeit',
    elapsed: 'Verstrichen',
    chunks: 'Chunks',
    errors: 'Fehler',
    save: 'Speichern',
    cancel: 'Abbrechen',
    createEvent: 'Termin erstellen',
    saveEvent: 'Speichere...',
    sources: 'Quellen',
    language: 'Sprache',
    theme: 'Theme',
    darkMode: 'Dunkelmodus',
    cmdLanguageChanged: 'Sprache wurde auf {value} umgestellt.',
    cmdThemeChanged: 'Theme wurde auf {value} umgestellt.',
    cmdModeChanged: 'Darstellung wurde auf {value} gesetzt.',
    modeDark: 'Dunkel',
    modeLight: 'Hell',
    modeAuto: 'Automatisch',
    tabConfig: 'Konfiguration',
    tabIndexing: 'Indexierung',
    tabSources: 'Quellen',
    tabDesign: 'Design',
    aiModel: 'KI-Modell',
    protocol: 'Protokoll',
    host: 'Host',
    port: 'Port',
    model: 'Modell',
    selectModel: 'Modell auswählen...',
    suggestions: 'Vorschläge',
    personalizedSuggestions: 'Personalisierte Vorschläge basierend auf deinem Nutzungsverhalten'
  },
  en: {
    newChat: 'New Chat',
    settings: 'Settings',
    currentChat: 'Current Chat',
    askHeading: 'What is on your mind?',
    askSubheading: 'Ask anything about your knowledge base.',
    askPlaceholder: 'Ask a question...',
    composerPlaceholder: 'Your message here...',
    documentIndexing: 'Document Indexing',
    current: 'Current',
    files: 'Files',
    speed: 'Speed',
    elapsed: 'Elapsed',
    chunks: 'Chunks',
    errors: 'Errors',
    save: 'Save',
    cancel: 'Cancel',
    createEvent: 'Create event',
    saveEvent: 'Saving...',
    sources: 'Sources',
    language: 'Language',
    theme: 'Theme',
    darkMode: 'Dark Mode',
    cmdLanguageChanged: 'Language was switched to {value}.',
    cmdThemeChanged: 'Theme was switched to {value}.',
    cmdModeChanged: 'Appearance was switched to {value}.',
    modeDark: 'Dark',
    modeLight: 'Light',
    modeAuto: 'Auto',
    tabConfig: 'Config',
    tabIndexing: 'Indexing',
    tabSources: 'Sources',
    tabDesign: 'Design',
    aiModel: 'AI Model',
    protocol: 'Protocol',
    host: 'Host',
    port: 'Port',
    model: 'Model',
    selectModel: 'Select model...',
    suggestions: 'Suggestions',
    personalizedSuggestions: 'Personalized suggestions based on your usage patterns'
  }
};

function interpolate(template, vars) {
  return String(template).replace(/\{(\w+)\}/g, (_, key) => vars?.[key] ?? `{${key}}`);
}

export function useLanguage() {
  const [language, setLanguageState] = useState('de');

  useEffect(() => {
    const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    const valid = SUPPORTED_LANGUAGES.some((l) => l.code === stored);
    const next = valid ? stored : 'de';
    setLanguageState(next);
    document.documentElement.setAttribute('lang', next);
  }, []);

  const setLanguage = (nextLanguage) => {
    const valid = SUPPORTED_LANGUAGES.some((l) => l.code === nextLanguage);
    const safe = valid ? nextLanguage : 'de';
    setLanguageState(safe);
    localStorage.setItem(LANGUAGE_STORAGE_KEY, safe);
    document.documentElement.setAttribute('lang', safe);
  };

  const t = useMemo(() => {
    return (key, vars) => {
      const table = TRANSLATIONS[language] || TRANSLATIONS.en;
      const value = table?.[key] ?? TRANSLATIONS.de[key] ?? key;
      return interpolate(value, vars);
    };
  }, [language]);

  return {
    language,
    setLanguage,
    t,
    languages: SUPPORTED_LANGUAGES
  };
}
