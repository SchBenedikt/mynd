const DEFAULT_BACKEND = 'http://127.0.0.1:5001';
const TOKEN_KEY = 'mynd_token_v1';
const BACKEND_KEY = 'backendUrl';

function cleanUrl(url) {
  return url.replace(/\/+$/, '');
}

function guessBackendFromPage() {
  if (typeof window === 'undefined') return null;
  try {
    const u = new URL(window.location.href);
    const saved = localStorage.getItem(BACKEND_KEY);
    if (saved) return saved;
    if (u.hostname !== 'localhost' && u.hostname !== '127.0.0.1') {
      return `${u.protocol}//${u.hostname}:5001`;
    }
  } catch {}
  return null;
}

export function getApiBase() {
  if (typeof window !== 'undefined') {
    return cleanUrl(guessBackendFromPage() || localStorage.getItem(BACKEND_KEY) || DEFAULT_BACKEND);
  }
  return DEFAULT_BACKEND;
}

export async function apiFetch(path, options = {}) {
  const url = path.startsWith('http') ? path : `${getApiBase()}${path}`;
  const headers = new Headers(options.headers || {});
  if (typeof window !== 'undefined' && !headers.has('Authorization')) {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) headers.set('Authorization', `Bearer ${token}`);
  }
  const response = await fetch(url, { ...options, headers });
  if (response.status === 401 && typeof window !== 'undefined') {
    localStorage.removeItem(TOKEN_KEY);
    window.dispatchEvent(new CustomEvent('auth-expired'));
  }
  return response;
}
