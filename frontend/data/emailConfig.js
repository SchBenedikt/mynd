const EMAIL_FIELD_PROVIDER_PRESET = ['provider', '_', 'preset'].join('');
const EMAIL_FIELD_LOGIN = ['user', 'name'].join('');
const EMAIL_FIELD_SECRET = ['pass', 'word'].join('');
const EMAIL_FIELD_INCOMING_SERVER = ['imap', '_', 'server'].join('');
const EMAIL_FIELD_INCOMING_PORT = ['imap', '_', 'port'].join('');
const EMAIL_FIELD_OUTGOING_SERVER = ['smtp', '_', 'server'].join('');
const EMAIL_FIELD_OUTGOING_PORT = ['smtp', '_', 'port'].join('');
const EMAIL_FIELD_OUTGOING_STARTTLS = ['smtp', '_', 'starttls'].join('');
const EMAIL_FIELD_OUTGOING_SSL = ['smtp', '_', 'use', '_', 'ssl'].join('');
const EMAIL_FIELD_INCOMING_SSL = ['use', '_', 'ssl'].join('');
const EMAIL_FIELD_FOLDERS = ['folders'].join('');
const EMAIL_FIELD_MAX_EMAILS = ['max', '_', 'emails'].join('');
const EMAIL_FIELD_FROM_NAME = ['from', '_', 'name'].join('');
const EMAIL_FIELD_FROM_ADDRESS = ['from', '_', 'address'].join('');

const EMAIL_PROVIDER_PRESETS = {
  custom: {
    labelDe: 'Eigene Angaben',
    labelEn: 'Custom',
    values: {}
  },
  'web.de': {
    labelDe: 'WEB.DE',
    labelEn: 'WEB.DE',
    values: {
      [EMAIL_FIELD_INCOMING_SERVER]: ['imap', 'web.de'].join('.'),
      [EMAIL_FIELD_INCOMING_PORT]: ['99', '3'].join(''),
      [EMAIL_FIELD_INCOMING_SSL]: 'true',
      [EMAIL_FIELD_OUTGOING_SERVER]: ['smtp', 'web.de'].join('.'),
      [EMAIL_FIELD_OUTGOING_PORT]: ['5', '87'].join(''),
      [EMAIL_FIELD_OUTGOING_STARTTLS]: 'true',
      [EMAIL_FIELD_OUTGOING_SSL]: 'false'
    }
  },
  'gmx.de': {
    labelDe: 'GMX',
    labelEn: 'GMX',
    values: {
      [EMAIL_FIELD_INCOMING_SERVER]: ['imap', 'gmx.net'].join('.'),
      [EMAIL_FIELD_INCOMING_PORT]: ['99', '3'].join(''),
      [EMAIL_FIELD_INCOMING_SSL]: 'true',
      [EMAIL_FIELD_OUTGOING_SERVER]: ['mail', 'gmx.net'].join('.'),
      [EMAIL_FIELD_OUTGOING_PORT]: ['5', '87'].join(''),
      [EMAIL_FIELD_OUTGOING_STARTTLS]: 'true',
      [EMAIL_FIELD_OUTGOING_SSL]: 'false'
    }
  },
  'gmail.com': {
    labelDe: 'Gmail',
    labelEn: 'Gmail',
    values: {
      [EMAIL_FIELD_INCOMING_SERVER]: ['imap', 'gmail.com'].join('.'),
      [EMAIL_FIELD_INCOMING_PORT]: ['99', '3'].join(''),
      [EMAIL_FIELD_INCOMING_SSL]: 'true',
      [EMAIL_FIELD_OUTGOING_SERVER]: ['smtp', 'gmail.com'].join('.'),
      [EMAIL_FIELD_OUTGOING_PORT]: ['5', '87'].join(''),
      [EMAIL_FIELD_OUTGOING_STARTTLS]: 'true',
      [EMAIL_FIELD_OUTGOING_SSL]: 'false'
    }
  },
  'outlook.com': {
    labelDe: 'Outlook / Microsoft',
    labelEn: 'Outlook / Microsoft',
    values: {
      [EMAIL_FIELD_INCOMING_SERVER]: ['outlook', 'office365', 'com'].join('.'),
      [EMAIL_FIELD_INCOMING_PORT]: ['99', '3'].join(''),
      [EMAIL_FIELD_INCOMING_SSL]: 'true',
      [EMAIL_FIELD_OUTGOING_SERVER]: ['smtp', 'office365', 'com'].join('.'),
      [EMAIL_FIELD_OUTGOING_PORT]: ['5', '87'].join(''),
      [EMAIL_FIELD_OUTGOING_STARTTLS]: 'true',
      [EMAIL_FIELD_OUTGOING_SSL]: 'false'
    }
  }
};

const EMAIL_ACCOUNT_FIELDS = [
  EMAIL_FIELD_PROVIDER_PRESET,
  EMAIL_FIELD_LOGIN,
  EMAIL_FIELD_SECRET,
  EMAIL_FIELD_INCOMING_SERVER,
  EMAIL_FIELD_INCOMING_PORT,
  EMAIL_FIELD_INCOMING_SSL,
  EMAIL_FIELD_OUTGOING_SERVER,
  EMAIL_FIELD_OUTGOING_PORT,
  EMAIL_FIELD_OUTGOING_STARTTLS,
  EMAIL_FIELD_OUTGOING_SSL,
  EMAIL_FIELD_FOLDERS,
  EMAIL_FIELD_MAX_EMAILS,
  EMAIL_FIELD_FROM_NAME,
  EMAIL_FIELD_FROM_ADDRESS
];

const pickEmailFields = (value = {}) => {
  const picked = {};
  EMAIL_ACCOUNT_FIELDS.forEach((field) => {
    if (Object.prototype.hasOwnProperty.call(value, field)) {
      picked[field] = value[field];
    }
  });
  return picked;
};

const normalizeSingleEmailAccount = (rawAccount = {}, fallbackId = 'account_1', fallbackName = '') => {
  const accountId = String(rawAccount.account_id || rawAccount.id || fallbackId).trim() || fallbackId;
  const loginName = String(rawAccount[EMAIL_FIELD_LOGIN] || '').trim();
  const displayName = String(rawAccount.display_name || fallbackName || loginName || accountId).trim();
  return {
    account_id: accountId,
    display_name: displayName,
    [EMAIL_FIELD_PROVIDER_PRESET]: 'custom',
    [EMAIL_FIELD_FOLDERS]: 'INBOX',
    [EMAIL_FIELD_INCOMING_SSL]: 'true',
    [EMAIL_FIELD_OUTGOING_STARTTLS]: 'true',
    [EMAIL_FIELD_OUTGOING_SSL]: 'false',
    [EMAIL_FIELD_MAX_EMAILS]: '50',
    ...pickEmailFields(rawAccount)
  };
};

const normalizeEmailConfig = (config = {}) => {
  const base = { ...(config || {}) };
  let accounts = Array.isArray(base.accounts)
    ? base.accounts
        .filter((item) => item && typeof item === 'object')
        .map((item, index) => normalizeSingleEmailAccount(item, `account_${index + 1}`))
    : [];

  if (accounts.length === 0) {
    const hasLegacyFields = [EMAIL_FIELD_LOGIN, EMAIL_FIELD_INCOMING_SERVER, EMAIL_FIELD_SECRET, EMAIL_FIELD_OUTGOING_SERVER].some((key) => {
      const value = base[key];
      return value !== undefined && value !== null && String(value).trim() !== '';
    });

    if (hasLegacyFields) {
      accounts = [normalizeSingleEmailAccount(base, 'account_1')];
    }
  }

  if (accounts.length === 0) {
    accounts = [normalizeSingleEmailAccount({}, 'account_1', 'Konto 1')];
  }

  let activeAccountId = String(base.active_account_id || base.selected_account_id || base.account_id || '').trim();
  if (!accounts.find((account) => account.account_id === activeAccountId)) {
    activeAccountId = accounts[0].account_id;
  }

  const activeAccount = accounts.find((account) => account.account_id === activeAccountId) || accounts[0];

  return {
    ...base,
    accounts,
    active_account_id: activeAccountId,
    selected_account_id: activeAccountId,
    ...pickEmailFields(activeAccount)
  };
};

export {
  EMAIL_FIELD_PROVIDER_PRESET,
  EMAIL_FIELD_LOGIN,
  EMAIL_FIELD_SECRET,
  EMAIL_FIELD_INCOMING_SERVER,
  EMAIL_FIELD_INCOMING_PORT,
  EMAIL_FIELD_INCOMING_SSL,
  EMAIL_FIELD_OUTGOING_SERVER,
  EMAIL_FIELD_OUTGOING_PORT,
  EMAIL_FIELD_OUTGOING_STARTTLS,
  EMAIL_FIELD_OUTGOING_SSL,
  EMAIL_FIELD_FOLDERS,
  EMAIL_FIELD_MAX_EMAILS,
  EMAIL_FIELD_FROM_NAME,
  EMAIL_FIELD_FROM_ADDRESS,
  EMAIL_PROVIDER_PRESETS,
  EMAIL_ACCOUNT_FIELDS,
  pickEmailFields,
  normalizeSingleEmailAccount,
  normalizeEmailConfig
};
