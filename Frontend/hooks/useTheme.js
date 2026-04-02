'use client';

import { useState, useEffect } from 'react';

export function useTheme() {
  const [theme, setThemeState] = useState('gold');
  const [darkMode, setDarkModeState] = useState('auto');
  const [motionStyle, setMotionStyleState] = useState('dynamic');
  const [contrastColor, setContrastColorState] = useState('');

  // Apply theme immediately on mount
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'gold';
    const savedDarkMode = localStorage.getItem('darkMode') || 'auto';
    const savedMotionStyle = localStorage.getItem('motionStyle') || 'dynamic';
    const savedContrast = localStorage.getItem('contrastColor');
    
    // Apply theme immediately to prevent flash
    document.documentElement.setAttribute('data-theme', savedTheme);
    document.documentElement.setAttribute('data-mode', savedDarkMode);
    document.documentElement.setAttribute('data-motion-style', savedMotionStyle);
    
    setThemeState(savedTheme);
    setDarkModeState(savedDarkMode);
    setMotionStyleState(savedMotionStyle);
    setContrastColorState(savedContrast || '');
    
    applyDarkMode(savedDarkMode);
    
    // Only apply custom contrast color if it exists, otherwise use theme default
    if (savedContrast) {
      document.documentElement.style.setProperty('--brand', savedContrast);
    } else {
      // Remove any custom brand color to use theme default
      document.documentElement.style.removeProperty('--brand');
    }

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const handleChange = () => {
      if (savedDarkMode === 'auto') {
        applyDarkMode('auto');
      }
    };
    mediaQuery.addEventListener('change', handleChange);

    return () => {
      mediaQuery.removeEventListener('change', handleChange);
    };
  }, []);

  // Initialize theme on first mount if no localStorage exists
  useEffect(() => {
    if (!localStorage.getItem('theme')) {
      localStorage.setItem('theme', 'gold');
      localStorage.setItem('darkMode', 'auto');
      localStorage.setItem('motionStyle', 'dynamic');
      localStorage.removeItem('contrastColor');
      document.documentElement.setAttribute('data-theme', 'gold');
      document.documentElement.setAttribute('data-motion-style', 'dynamic');
      document.documentElement.style.removeProperty('--brand');
    }
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
    
    // Apply custom contrast color if it exists, otherwise use theme default
    if (contrastColor) {
      document.documentElement.style.setProperty('--brand', contrastColor);
    } else {
      // Remove any custom brand color to use theme default
      document.documentElement.style.removeProperty('--brand');
    }
  };

  const setDarkMode = (mode) => {
    setDarkModeState(mode);
    localStorage.setItem('darkMode', mode);
    applyDarkMode(mode);
  };

  const setMotionStyle = (style) => {
    const allowed = ['calm', 'dynamic', 'aurora'];
    const safeStyle = allowed.includes(style) ? style : 'dynamic';
    setMotionStyleState(safeStyle);
    localStorage.setItem('motionStyle', safeStyle);
    document.documentElement.setAttribute('data-motion-style', safeStyle);
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
    motionStyle,
    contrastColor,
    setTheme,
    setDarkMode,
    setMotionStyle,
    setContrastColor
  };
}
