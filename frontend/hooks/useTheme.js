'use client';

import { useState, useEffect } from 'react';

function loadTheme() {
  if (typeof window === 'undefined') return { theme: 'gold', darkMode: 'auto', contrastColor: '' };
  const savedTheme = localStorage.getItem('theme') || 'gold';
  const savedDarkMode = localStorage.getItem('darkMode') || 'auto';
  const savedContrast = localStorage.getItem('contrastColor') || '';
  try {
    document.documentElement.setAttribute('data-theme', savedTheme);
    document.documentElement.setAttribute('data-mode', savedDarkMode);
    if (savedContrast) {
      document.documentElement.style.setProperty('--brand', savedContrast);
    }
  } catch {}
  return { theme: savedTheme, darkMode: savedDarkMode, contrastColor: savedContrast };
}

export function useTheme() {
  const initial = loadTheme();
  const [theme, setThemeState] = useState(initial.theme);
  const [darkMode, setDarkModeState] = useState(initial.darkMode);
  const [contrastColor, setContrastColorState] = useState(initial.contrastColor);

  useEffect(() => {
  const savedDarkMode = localStorage.getItem('darkMode') || 'auto';

    applyDarkMode(savedDarkMode);

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = () => {
      if (savedDarkMode === 'auto') applyDarkMode('auto');
    };
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  const applyDarkMode = (mode) => {
    if (mode === 'auto') {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      document.documentElement.setAttribute('data-mode', prefersDark ? 'dark' : 'light');
    } else {
      document.documentElement.setAttribute('data-mode', mode);
    }
  };

  const setTheme = (newTheme) => {
    setThemeState(newTheme);
    localStorage.setItem('theme', newTheme);
    document.documentElement.setAttribute('data-theme', newTheme);
    
    if (contrastColor) {
      document.documentElement.style.setProperty('--brand', contrastColor);
    } else {
      document.documentElement.style.removeProperty('--brand');
    }
  };

  const setDarkMode = (mode) => {
    setDarkModeState(mode);
    localStorage.setItem('darkMode', mode);
    applyDarkMode(mode);
  };

  const setContrastColor = (color) => {
    setContrastColorState(color);
    if (color) {
      localStorage.setItem('contrastColor', color);
      document.documentElement.style.setProperty('--brand', color);
    } else {
      localStorage.removeItem('contrastColor');
      document.documentElement.style.removeProperty('--brand');
    }
  };

  return {
    theme,
    darkMode,
    contrastColor,
    setTheme,
    setDarkMode,
    setContrastColor
  };
}
