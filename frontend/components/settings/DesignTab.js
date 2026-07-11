'use client';

import { useTheme } from '../../hooks/useTheme';
import { useLanguage } from '../../hooks/useLanguage';
import { ThemeSelector } from '../../components/ThemeSelector';

export default function DesignTab({ tr }) {
  const { theme, darkMode, contrastColor, setTheme, setDarkMode, setContrastColor } = useTheme();
  const { language, setLanguage, t, languages } = useLanguage();

  return (
    <div className="settings-panel">
      <div className="input-group" style={{ marginBottom: '1rem' }}>
        <label>{t('language')}</label>
        <select value={language} onChange={(e) => setLanguage(e.target.value)}>
          {languages.map((entry) => (
            <option key={entry.code} value={entry.code}>{entry.label}</option>
          ))}
        </select>
      </div>
      <ThemeSelector
        currentTheme={theme}
        onThemeChange={setTheme}
        currentDarkMode={darkMode}
        onDarkModeChange={setDarkMode}
        showContrastColor={true}
        contrastColor={contrastColor}
        onContrastColorChange={setContrastColor}
        labels={{
          theme: t('theme'),
          darkMode: t('darkMode'),
          contrastColor: tr('Kontrastfarbe (optional)', 'Contrast Color (optional)'),
          reset: tr('Zurücksetzen', 'Reset'),
          themes: { classic: 'Classic', ocean: 'Ocean', graphite: 'Graphite', lavender: 'Lavender', rose: 'Rose', gold: 'Gold', pure: 'Pure' },
          modes: { light: t('modeLight'), dark: t('modeDark'), auto: t('modeAuto') }
        }}
      />
    </div>
  );
}
