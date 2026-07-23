'use client';

import { useEffect } from 'react';

export function usePageTitle(title) {
  useEffect(() => {
    const prev = document.title;
    document.title = `${title} | MYND`;
    return () => {
      document.title = prev;
    };
  }, [title]);
}
