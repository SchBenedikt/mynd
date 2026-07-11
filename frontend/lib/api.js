const DEFAULT_BACKEND = 'http://127.0.0.1:5001';

function cleanUrl(url) {
  return url.replace(/\/+$/, '');
}

export function getApiBase() {
  if (typeof window !== 'undefined') {
    return cleanUrl(localStorage.getItem('backendUrl') || DEFAULT_BACKEND);
  }
  return DEFAULT_BACKEND;
}

export function apiFetch(path, options = {}) {
  const url = path.startsWith('http') ? path : `${getApiBase()}${path}`;
  return fetch(url, options);
}
