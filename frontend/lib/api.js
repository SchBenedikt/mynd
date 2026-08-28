const DEFAULT_BACKEND = 'http://127.0.0.1:5001';
const BACKEND_KEY = 'backendUrl';

function cleanUrl(url) {
  try {
    const parsed = new URL(String(url));
    if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password) return DEFAULT_BACKEND;
    return parsed.origin + parsed.pathname.replace(/\/+$/, '');
  } catch {
    return DEFAULT_BACKEND;
  }
}

function guessBackendFromPage() {
  if (typeof window === 'undefined') return null;
  try {
    const u = new URL(window.location.href);
    const saved = localStorage.getItem(BACKEND_KEY);
    if (saved) return saved;
    if (u.hostname === 'localhost' || u.hostname === '127.0.0.1') {
      return `${u.protocol}//${u.hostname}:5001`;
    }
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
  const base = getApiBase();
  let url;
  if (/^https?:\/\//i.test(path)) {
    const candidate = new URL(path);
    if (candidate.origin !== new URL(base).origin) throw new Error('Cross-origin API URL is not allowed');
    url = candidate.toString();
  } else {
    if (!String(path).startsWith('/')) throw new Error('API path must start with /');
    url = `${base}${path}`;
  }
  const headers = new Headers(options.headers || {});
  const response = await fetch(url, { ...options, headers, credentials: 'include' });
  if (response.status === 401 && typeof window !== 'undefined') {
    localStorage.removeItem('mynd_token_v1');
    window.dispatchEvent(new CustomEvent('auth-expired'));
  }
  return response;
}
