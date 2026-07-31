'use client';

import { useState, useEffect } from 'react';

function readStored() {
  let theme = 'gold';
  let darkMode = 'light';
  let contrastColor = '';
  try {
    theme = localStorage.getItem('theme') || 'gold';
    darkMode = localStorage.getItem('darkMode') || 'light';
    contrastColor = localStorage.getItem('contrastColor') || '';
  } catch {}
  return { theme, darkMode, contrastColor };
}

function resolveMode(mode) {
  if (mode === 'auto') {
    if (typeof window === 'undefined') return 'light';
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  return mode;
}

function applyTheme({ theme, darkMode, contrastColor }) {
  if (typeof document === 'undefined') return;
  document.documentElement.setAttribute('data-theme', theme);
  document.documentElement.setAttribute('data-mode', resolveMode(darkMode));
  if (contrastColor) {
    document.documentElement.style.setProperty('--brand', contrastColor);
  } else {
    document.documentElement.style.removeProperty('--brand');
  }
}

export function useTheme() {
  const [state, setState] = useState(readStored);
  const { theme, darkMode, contrastColor } = state;

  useEffect(() => {
    applyTheme({ theme, darkMode, contrastColor });
    if (darkMode !== 'auto') return undefined;
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = () => {
      document.documentElement.setAttribute('data-mode', mediaQuery.matches ? 'dark' : 'light');
    };
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [theme, darkMode, contrastColor]);

  const setTheme = (newTheme) => {
    const next = { ...state, theme: newTheme };
    setState(next);
    try { localStorage.setItem('theme', newTheme); } catch {}
    applyTheme(next);
  };

  const setDarkMode = (mode) => {
    const next = { ...state, darkMode: mode };
    setState(next);
    try { localStorage.setItem('darkMode', mode); } catch {}
    applyTheme(next);
  };

  const setContrastColor = (color) => {
    const next = { ...state, contrastColor: color };
    setState(next);
    if (color) {
      try { localStorage.setItem('contrastColor', color); } catch {}
      document.documentElement.style.setProperty('--brand', color);
    } else {
      try { localStorage.removeItem('contrastColor'); } catch {}
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
