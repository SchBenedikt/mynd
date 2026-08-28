'use client';

export function currentStorageOwner() {
  if (typeof window === 'undefined') return 'anonymous';
  try {
    const user = JSON.parse(window.localStorage.getItem('mynd_user_v1') || '{}');
    const username = String(user?.username || '').trim();
    return username ? encodeURIComponent(username) : 'anonymous';
  } catch {
    return 'anonymous';
  }
}

export function userStorageKey(baseKey) {
  return `${baseKey}:${currentStorageOwner()}`;
}
