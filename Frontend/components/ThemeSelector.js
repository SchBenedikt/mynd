'use client';

export function ThemeSelector({ currentTheme, onThemeChange, currentDarkMode, onDarkModeChange, contrastColor, onContrastColorChange, showContrastColor = false }) {
  const themes = [
    { id: 'classic', name: 'Classic' },
    { id: 'ocean', name: 'Ocean' },
    { id: 'graphite', name: 'Graphite' },
    { id: 'lavender', name: 'Lavender' },
    { id: 'rose', name: 'Rose' },
    { id: 'gold', name: 'Gold' }
  ];

  const darkModes = [
    { id: 'light', name: 'Light', icon: '☀️' },
    { id: 'dark', name: 'Dark', icon: '🌙' },
    { id: 'auto', name: 'Auto', icon: '🔄' }
  ];

  return (
    <>
      {/* Theme Selector */}
      <div className="input-group">
        <label>Theme</label>
        <div className="theme-selector">
          {themes.map((theme) => (
            <button
              key={theme.id}
              className={`theme-btn ${theme.id} ${currentTheme === theme.id ? 'active' : ''}`}
              onClick={() => onThemeChange(theme.id)}
              title={theme.name}
            />
          ))}
        </div>
      </div>

      {/* Dark Mode Selector */}
      <div className="input-group">
        <label>Dark Mode</label>
        <div className="dark-mode-selector">
          {darkModes.map((mode) => (
            <button
              key={mode.id}
              className={`mode-btn ${currentDarkMode === mode.id ? 'active' : ''}`}
              onClick={() => onDarkModeChange(mode.id)}
            >
              <span>{mode.icon}</span>
              <span>{mode.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Contrast Color Picker (optional) */}
      {showContrastColor && (
        <div className="input-group">
          <label>Contrast Color (optional)</label>
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
                onClick={() => onContrastColorChange('')}
                style={{ padding: '0.5rem 0.75rem' }}
              >
                Reset
              </button>
            )}
          </div>
        </div>
      )}
    </>
  );
}
