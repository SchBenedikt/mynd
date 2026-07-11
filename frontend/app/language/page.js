'use client';

import { useRouter } from 'next/navigation';
import './language.css';

const LANGUAGES = [
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

export default function LanguagePage() {
  const router = useRouter();

  const selectLanguage = (code) => {
    try {
      localStorage.setItem('mynd_language', code);
    } catch (e) {}
    document.documentElement.setAttribute('lang', code);
    router.replace('/');
  };

  return (
    <div className="lang-page">
      <div className="lang-card">
        <div className="lang-badge">MYND</div>
        <h1 className="lang-title">Willkommen</h1>
        <p className="lang-sub">Bitte wähle deine Sprache / Please select your language</p>
        <div className="lang-grid">
          {LANGUAGES.map((lang) => (
            <button
              key={lang.code}
              className="lang-chip"
              onClick={() => selectLanguage(lang.code)}
            >
              {lang.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
