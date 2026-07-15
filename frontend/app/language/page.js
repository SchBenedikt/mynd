'use client';

import { useRouter } from 'next/navigation';
import { useLanguage } from '../../hooks/useLanguage';
import './language.css';

export default function LanguagePage() {
  const router = useRouter();
  const { setLanguage, languages } = useLanguage();

  const selectLanguage = (code) => {
    setLanguage(code);
    router.replace('/');
  };

  return (
    <div className="lang-page">
      <div className="lang-card">
        <div className="lang-badge">MYND</div>
        <h1 className="lang-title">Welcome</h1>
        <p className="lang-sub">Please select your language</p>
        <div className="lang-grid">
          {languages.map((lang) => (
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
