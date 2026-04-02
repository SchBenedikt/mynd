'use client';

export function ThemeSelector({ currentTheme, onThemeChange, currentDarkMode, onDarkModeChange, contrastColor, onContrastColorChange, showContrastColor = false, labels = {} }) {
  const l = {
    theme: labels.theme || 'Theme',
    darkMode: labels.darkMode || 'Dark Mode',
    contrastColor: labels.contrastColor || 'Contrast Color (optional)',
    reset: labels.reset || 'Reset',
    themes: labels.themes || {
      classic: 'Classic',
      ocean: 'Ocean',
      graphite: 'Graphite',
      lavender: 'Lavender',
      rose: 'Rose',
      gold: 'Gold'
    },
    modes: labels.modes || {
      light: 'Light',
      dark: 'Dark',
      auto: 'Auto'
    }
  };

  const themes = [
    { id: 'classic', name: l.themes.classic },
    { id: 'ocean', name: l.themes.ocean },
    { id: 'graphite', name: l.themes.graphite },
    { id: 'lavender', name: l.themes.lavender },
    { id: 'rose', name: l.themes.rose },
    { id: 'gold', name: l.themes.gold }
  ];

  const darkModes = [
    { id: 'light', name: l.modes.light, icon: '☀️' },
    { id: 'dark', name: l.modes.dark, icon: '🌙' },
    { id: 'auto', name: l.modes.auto, icon: '🔄' }
  ];

  return (
    <>
      <div className="input-group">
        <label>{l.theme}</label>
        <div className="theme-selector">
          {themes.map((theme) => (
            <button
              key={theme.id}
              type="button"
              className={`theme-choice ${theme.id} ${currentTheme === theme.id ? 'active' : ''}`}
              onClick={() => onThemeChange(theme.id)}
              title={theme.name}
              aria-label={theme.name}
            >
              <span className="theme-choice-preview" aria-hidden="true" />
              <span className="theme-choice-name">{theme.name}</span>
              {currentTheme === theme.id && (
                <span className="theme-choice-check" aria-hidden="true">✓</span>
              )}
            </button>
          ))}
        </div>
      </div>

      <div className="input-group">
        <label>{l.darkMode}</label>
        <div className="dark-mode-selector">
          {darkModes.map((mode) => (
            <button
              key={mode.id}
              type="button"
              className={`mode-btn ${currentDarkMode === mode.id ? 'active' : ''}`}
              onClick={() => onDarkModeChange(mode.id)}
            >
              <span className="mode-icon">{mode.icon}</span>
              <span>{mode.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Contrast Color Picker (optional) */}
      {showContrastColor && (
        <div className="input-group">
          <label>{l.contrastColor}</label>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <input
              type="color"
              value={contrastColor || '#16a34a'}
              onChange={(e) => onContrastColorChange(e.target.value)}
              style={{ 
                width: '50px', 
                height: '36px', 
                border: '1px solid var(--line)',
                borderRadius: '8px',
                cursor: 'pointer'
              }}
            />
            <input
              type="text"
              value={contrastColor || ''}
              onChange={(e) => onContrastColorChange(e.target.value)}
              placeholder="#16a34a"
              style={{ flex: 1 }}
            />
            {contrastColor && (
              <button
                className="btn"
                type="button"
                onClick={() => onContrastColorChange('')}
                style={{ padding: '0.5rem 0.75rem' }}
              >
                {l.reset}
              </button>
            )}
          </div>
        </div>
      )}
    </>
  );
}
