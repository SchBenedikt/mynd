export const CHAT_STORAGE_KEY = 'mynd_chat_history_v1';
export const ACTIVE_CHAT_STORAGE_KEY = 'mynd_active_chat_v1';
export const SIDEBAR_COLLAPSED_KEY = 'mynd_sidebar_collapsed_v1';
export const DISPLAY_NAME_STORAGE_KEY = 'mynd_display_name';
export const LOCATION_AUTO_RESOLVE_KEY = 'mynd_location_auto_resolve_v1';
export const BRIEFING_SEEN_KEY = 'mynd_seen_briefings_v1';
export const TTS_PROVIDER_STORAGE_KEY = 'mynd_tts_provider_v1';

export const SPEECH_LANG_MAP = {
  de: 'de-DE', en: 'en-US', fr: 'fr-FR', es: 'es-ES',
  it: 'it-IT', pt: 'pt-PT', nl: 'nl-NL', pl: 'pl-PL',
  tr: 'tr-TR', ru: 'ru-RU', ja: 'ja-JP', zh: 'zh-CN'
};

export const LANGUAGE_COMMANDS = {
  de: ['deutsch', 'german'],
  en: ['englisch', 'english'],
  fr: ['franzoesisch', 'franzosisch', 'french', 'francais'],
  es: ['spanisch', 'spanish', 'espanol'],
  it: ['italienisch', 'italian', 'italiano'],
  pt: ['portugiesisch', 'portuguese', 'portugues'],
  nl: ['niederlaendisch', 'niederlandisch', 'dutch', 'nederlands'],
  pl: ['polnisch', 'polish', 'polski'],
  tr: ['tuerkisch', 'turkisch', 'turkish', 'turkce'],
  ru: ['russisch', 'russian'],
  ja: ['japanisch', 'japanese'],
  zh: ['chinesisch', 'chinese']
};

export const THEME_COMMANDS = {
  ocean: ['blau', 'blue', 'ocean', 'meer'],
  classic: ['gruen', 'grun', 'green', 'nature', 'natuerlich'],
  graphite: ['grau', 'grey', 'gray', 'graphite'],
  lavender: ['lila', 'violett', 'purple', 'lavender'],
  rose: ['rosa', 'pink', 'rose', 'rot'],
  gold: ['gold', 'gelb', 'orange', 'warm']
};

export const MODE_COMMANDS = {
  dark: ['dark mode', 'dark-mode', 'dunkelmodus', 'dunkel', 'nachtmodus'],
  light: ['light mode', 'light-mode', 'hellmodus', 'hell'],
  auto: ['auto mode', 'auto-mode', 'automatisch', 'systemmodus']
};

export const NAMED_COLOR_COMMANDS = {
  '#e11d48': ['rot', 'red'],
  '#2f63ff': ['blau', 'blue'],
  '#16a34a': ['gruen', 'grun', 'green'],
  '#7c3aed': ['lila', 'violett', 'purple'],
  '#b45309': ['gold', 'orange', 'gelb', 'yellow'],
  '#424242': ['grau', 'gray', 'grey', 'graphite']
};

export const THEME_LABEL_KEY = {
  classic: 'Classic', ocean: 'Ocean', graphite: 'Graphite',
  lavender: 'Lavender', rose: 'Rose', gold: 'Gold'
};

export const DESIGN_COLOR_PRESETS = [
  { id: 'brand-red', label: 'Red', value: '#e11d48' },
  { id: 'brand-blue', label: 'Blue', value: '#2f63ff' },
  { id: 'brand-green', label: 'Green', value: '#16a34a' },
  { id: 'brand-violet', label: 'Violet', value: '#7c3aed' },
  { id: 'brand-gold', label: 'Gold', value: '#b45309' }
];

export const createChatId = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now()}-${Math.floor(Math.random() * 100000)}`;
};

export const createMessageId = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now()}-${Math.floor(Math.random() * 100000)}`;
};

export const normalizeTtsProvider = (value) => {
  return String(value || '').trim().toLowerCase() === 'gemini' ? 'gemini' : 'browser';
};

export const createEmptyChat = (project = null) => {
  const now = Date.now();
  return { id: createChatId(), title: 'Neuer Chat', messages: [], createdAt: now, updatedAt: now, project };
};

export const buildChatTitleFromText = (text) => {
  const cleaned = String(text || '').trim().replace(/\s+/g, ' ');
  if (!cleaned) return 'Neuer Chat';
  return cleaned.length > 38 ? `${cleaned.slice(0, 38)}...` : cleaned;
};

export const safeReadJson = async (response) => {
  const text = await response.text();
  if (!text) return {};
  try { return JSON.parse(text); } catch { return { success: false, error: text }; }
};

export const buildFriendlyChatErrorMessage = (response, data, fallbackMessage = '') => {
  const status = response?.status || 0;
  const backendError = String(data?.error || data?.message || fallbackMessage || '').trim();
  if (status === 0 || status >= 500) return '⚠️ Der Server hat nicht rechtzeitig geantwortet. Das passiert oft bei komplexen Anfragen. Bitte versuche es mit einer kürzeren oder einfacheren Formulierung erneut.';
  if (status === 429) return '⚠️ Zu viele Anfragen in kurzer Zeit. Bitte warte kurz und versuche es dann erneut.';
  if (status >= 400 && backendError) return `⚠️ Fehler: ${backendError}`;
  return '⚠️ Die Anfrage konnte nicht verarbeitet werden. Bitte versuche es erneut.';
};

export const analyzeBackendError = (response, data) => {
  const status = response?.status || 0;
  const body = JSON.stringify(data || {});
  const parts = [];
  parts.push('Fehleranalyse:');
  parts.push(`- Endpoint antwortete mit Status ${status}.`);
  if (body) parts.push(`- Antwort vom Server: ${body}`);
  if (status >= 500) {
    parts.push('- Mögliche Ursachen: interner Serverfehler, Ausnahme im Backend, fehlende Abhängigkeiten oder defekte Datenbankverbindung.');
    parts.push('- Nächste Schritte: prüfe die Backend-Logs (run_app.py stdout), suche nach Tracebacks oder Exceptions, prüfe Datenbank- und Index-Verbindungen und API-Keys.');
  } else if (status === 401 || status === 403) {
    parts.push('- Mögliche Ursachen: nicht authentifiziert oder unzureichende Berechtigungen. Überprüfe Login/Token/Session.');
    parts.push('- Nächste Schritte: melde dich ab und wieder an, überprüfe OAuth-Credentials oder Admin-Benutzer-Konfiguration.');
  } else if (status === 429) {
    parts.push('- Mögliche Ursachen: Rate-Limiting vom Backend oder externen APIs.');
    parts.push('- Nächste Schritte: warte kurz oder prüfe Backend-Rate-Limits und API-Quoten.');
  } else {
    parts.push('- Mögliche Ursachen: fehlerhafte Anfrage oder Validierungsfehler.');
    parts.push('- Nächste Schritte: überprüfe die Anfrageparameter in den Einstellungen oder die Backend-Validierungen.');
  }
  parts.push('Wenn du möchtest, kann ich versuchen, die Backend-Fehlermeldung detaillierter zu interpretieren.');
  return parts.join('\n');
};

export const getTodayDateTimeForInputs = () => {
  const today = new Date();
  const year = String(today.getFullYear());
  const month = String(today.getMonth() + 1).padStart(2, '0');
  const day = String(today.getDate()).padStart(2, '0');
  return { dateOnly: `${year}-${month}-${day}`, dateTime: `${year}-${month}-${day}T09:00` };
};

export const resolveSpeechLocale = (langCode) => SPEECH_LANG_MAP[langCode] || 'de-DE';

export const cleanTextForSpeech = (value) => String(value || '')
  .replace(/(^|\n)\s*(?:\*\*|__)?\s*(assistant|assistent)\s*(?:\*\*|__)?\s*[:：-]\s*/gim, '$1')
  .replace(/\b(?:assistant|assistent)\b\s*[:：-]\s*/gi, '')
  .replace(/```[\s\S]*?```/g, ' ')
  .replace(/`([^`]+)`/g, '$1')
  .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
  .replace(/\[[^\]]+\]\([^)]*\)/g, '$1')
  .replace(/[#>*_~\-]+/g, ' ')
  .replace(/\s+/g, ' ')
  .trim();

export const splitTextForGeminiTts = (text, maxChars = 280) => {
  const normalized = String(text || '').trim();
  if (!normalized) return [];
  const sentenceParts = normalized.match(/[^.!?]+[.!?]?/g) || [normalized];
  const chunks = [];
  let current = '';
  for (const sentence of sentenceParts) {
    const part = sentence.trim();
    if (!part) continue;
    if (!current) { current = part; continue; }
    if ((`${current} ${part}`).length <= maxChars) { current = `${current} ${part}`; }
    else { chunks.push(current); current = part; }
  }
  if (current) chunks.push(current);
  return chunks;
};

export const parseBackendDateTimeToInput = (value) => {
  if (!value || typeof value !== 'string') return '';
  const trimmed = value.trim();
  const fullDateTimeMatch = trimmed.match(/^(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}:\d{2})$/);
  if (fullDateTimeMatch) {
    const [, day, month, year, hm] = fullDateTimeMatch;
    return `${year}-${month}-${day}T${hm}`;
  }
  const timeOnlyMatch = trimmed.match(/^(\d{2}:\d{2})$/);
  if (timeOnlyMatch) {
    const today = new Date();
    const year = String(today.getFullYear());
    const month = String(today.getMonth() + 1).padStart(2, '0');
    const day = String(today.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}T${timeOnlyMatch[1]}`;
  }
  return '';
};

export const formatDateTimeForBackend = (datetimeLocalValue) => {
  if (!datetimeLocalValue) return '';
  const [datePart, timePart] = datetimeLocalValue.split('T');
  if (!datePart || !timePart) return datetimeLocalValue;
  const [year, month, day] = datePart.split('-');
  return `${day}.${month}.${year} ${timePart}`;
};
