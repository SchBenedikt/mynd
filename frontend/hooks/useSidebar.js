'use client';

import { useState, useEffect } from 'react';

const SIDEBAR_COLLAPSED_KEY = 'mynd_sidebar_collapsed_v1';

export function useSidebar() {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    if (typeof window !== 'undefined') {
      const raw = localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
      if (raw === 'true' || raw === 'false') return raw === 'true';
    }
    return false;
  });

  const [canAnimate, setCanAnimate] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(isSidebarCollapsed));
    } catch (err) {
      console.error('Error saving sidebar state:', err);
    }
  }, [isSidebarCollapsed]);

  useEffect(() => {
    const id = requestAnimationFrame(() => setCanAnimate(true));
    return () => cancelAnimationFrame(id);
  }, []);

  const toggleSidebar = () => setIsSidebarCollapsed((prev) => !prev);

  return { isSidebarCollapsed, toggleSidebar, canAnimate };
}
