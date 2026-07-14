'use client';

import { useState, useEffect } from 'react';
import { apiFetch } from '../../lib/api';
import { useLanguage } from '../../hooks/useLanguage';
import './login.css';

const TOKEN_KEY = 'mynd_token_v1';

const COPY = {
  en: { signIn:'Sign in', register:'Register', create:'Create account', subtitle:'Sign in to continue', newAccount:'Create a new account', username:'Username', displayName:'Display name (optional)', password:'Password', confirm:'Confirm password', repeat:'Repeat password', min:'At least 4 characters', signingIn:'Signing in…', creating:'Creating account…', server:'Server connection', serverHint:'Address of the local backend server', required:'Username and password are required', shortUser:'Username must contain at least 2 characters', shortPass:'Password must contain at least 4 characters', mismatch:'Passwords do not match', created:'Account created! Redirecting…', failed:'Sign-in failed', registerFailed:'Registration failed', network:'Network error — backend is unreachable' },
  de: { signIn:'Anmelden', register:'Registrieren', create:'Account erstellen', subtitle:'Melde dich an', newAccount:'Neuen Account erstellen', username:'Benutzername', displayName:'Anzeigename (optional)', password:'Passwort', confirm:'Passwort bestätigen', repeat:'Passwort wiederholen', min:'Mindestens 4 Zeichen', signingIn:'Anmeldung läuft…', creating:'Account wird erstellt…', server:'Server-Verbindung', serverHint:'Adresse des lokalen Backend-Servers', required:'Benutzername und Passwort erforderlich', shortUser:'Benutzername zu kurz (mind. 2 Zeichen)', shortPass:'Passwort zu kurz (mind. 4 Zeichen)', mismatch:'Passwörter stimmen nicht überein', created:'Account erstellt! Weiterleitung…', failed:'Anmeldung fehlgeschlagen', registerFailed:'Registrierung fehlgeschlagen', network:'Netzwerkfehler — Backend nicht erreichbar' },
  fr: { signIn:'Se connecter', register:"S’inscrire", create:'Créer un compte', subtitle:'Connectez-vous pour continuer', username:"Nom d’utilisateur", password:'Mot de passe', confirm:'Confirmer le mot de passe', signingIn:'Connexion…', creating:'Création…', server:'Connexion au serveur', network:'Erreur réseau — serveur inaccessible' },
  es: { signIn:'Iniciar sesión', register:'Registrarse', create:'Crear cuenta', subtitle:'Inicia sesión para continuar', username:'Usuario', password:'Contraseña', confirm:'Confirmar contraseña', signingIn:'Iniciando sesión…', creating:'Creando cuenta…', server:'Conexión del servidor', network:'Error de red — servidor no disponible' },
  it: { signIn:'Accedi', register:'Registrati', create:'Crea account', subtitle:'Accedi per continuare', username:'Nome utente', password:'Password', confirm:'Conferma password', signingIn:'Accesso…', creating:'Creazione…', server:'Connessione server', network:'Errore di rete — server non raggiungibile' },
  pt: { signIn:'Entrar', register:'Registrar', create:'Criar conta', subtitle:'Entre para continuar', username:'Usuário', password:'Senha', confirm:'Confirmar senha', signingIn:'Entrando…', creating:'Criando conta…', server:'Conexão do servidor', network:'Erro de rede — servidor indisponível' },
  nl: { signIn:'Inloggen', register:'Registreren', create:'Account maken', subtitle:'Log in om door te gaan', username:'Gebruikersnaam', password:'Wachtwoord', confirm:'Wachtwoord bevestigen', signingIn:'Inloggen…', creating:'Account maken…', server:'Serververbinding' },
  pl: { signIn:'Zaloguj się', register:'Zarejestruj się', create:'Utwórz konto', subtitle:'Zaloguj się, aby kontynuować', username:'Nazwa użytkownika', password:'Hasło', confirm:'Potwierdź hasło', signingIn:'Logowanie…', creating:'Tworzenie konta…', server:'Połączenie z serwerem' },
  tr: { signIn:'Giriş yap', register:'Kayıt ol', create:'Hesap oluştur', subtitle:'Devam etmek için giriş yapın', username:'Kullanıcı adı', password:'Parola', confirm:'Parolayı doğrula', signingIn:'Giriş yapılıyor…', creating:'Hesap oluşturuluyor…', server:'Sunucu bağlantısı' },
  ru: { signIn:'Войти', register:'Регистрация', create:'Создать аккаунт', subtitle:'Войдите, чтобы продолжить', username:'Имя пользователя', password:'Пароль', confirm:'Подтвердите пароль', signingIn:'Вход…', creating:'Создание аккаунта…', server:'Подключение к серверу' },
  ja: { signIn:'ログイン', register:'登録', create:'アカウントを作成', subtitle:'続行するにはログインしてください', username:'ユーザー名', password:'パスワード', confirm:'パスワードを確認', signingIn:'ログイン中…', creating:'作成中…', server:'サーバー接続' },
  zh: { signIn:'登录', register:'注册', create:'创建账户', subtitle:'登录以继续', username:'用户名', password:'密码', confirm:'确认密码', signingIn:'正在登录…', creating:'正在创建…', server:'服务器连接' }
};

function Spinner() {
  return <span className="login-btn-spinner" />;
}

export default function LoginPage() {
  const { language } = useLanguage();
  const c = { ...COPY.en, ...(COPY[language] || {}) };
  const [loginUser, setLoginUser] = useState('');
  const [loginPass, setLoginPass] = useState('');
  const [loginPassConfirm, setLoginPassConfirm] = useState('');
  const [loginName, setLoginName] = useState('');
  const [loginError, setLoginError] = useState('');
  const [loginSuccess, setLoginSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState('login');
  const [registrationAllowed, setRegistrationAllowed] = useState(false);
  const [backendUrl, setBackendUrl] = useState('http://127.0.0.1:5001');
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    try {
      const stored = localStorage.getItem('backendUrl');
      if (stored) setBackendUrl(stored);
    } catch {}
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    apiFetch('/api/auth/config')
      .then(r => r.json())
      .then(data => {
        if (data?.allowRegistration) setRegistrationAllowed(true);
      })
      .catch(() => setRegistrationAllowed(false));
  }, []);

  const validate = () => {
    if (!loginUser || !loginPass) return c.required;
    if (loginUser.length < 2) return c.shortUser;
    if (tab === 'register') {
      if (loginPass.length < 4) return c.shortPass;
      if (loginPass !== loginPassConfirm) return c.mismatch;
    }
    return '';
  };

  const switchTab = (newTab) => {
    if (newTab === tab) return;
    setTab(newTab);
    setLoginError('');
    setLoginSuccess('');
    setLoginPassConfirm('');
  };

  const submitCredentials = async (e) => {
    e.preventDefault();
    const validationError = validate();
    if (validationError) {
      setLoginError(validationError);
      return;
    }
    setLoading(true);
    setLoginError('');
    setLoginSuccess('');
    try {
      const endpoint = tab === 'register' ? '/api/auth/register' : '/api/auth/login';
      const body = tab === 'register'
        ? { username: loginUser, password: loginPass, name: loginName || loginUser }
        : { username: loginUser, password: loginPass };
      const resp = await apiFetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      const data = await resp.json();
      if (resp.ok && data.token) {
        try { localStorage.setItem(TOKEN_KEY, data.token); } catch {}
        if (tab === 'register') {
          setLoginSuccess(c.created);
          await new Promise(r => setTimeout(r, 800));
        }
        window.location.href = '/';
        return;
      }
      setLoginError((data && data.error) ? String(data.error) : (tab === 'register' ? c.registerFailed : c.failed));
    } catch (err) {
      setLoginError(c.network);
    }
    setLoading(false);
  };

  const changeBackendUrl = (url) => {
    setBackendUrl(url);
    try { localStorage.setItem('backendUrl', url); } catch {}
  };

  const isRegister = tab === 'register';
  const canSubmit = !loading && loginUser && loginPass && (!isRegister || loginPassConfirm);

  return (
    <div className="login-page">
      <div className="login-bg" />
      <div className="login-card">
        <div className="login-header">
          <div className="login-logo">◆</div>
          <h1>MYND</h1>
          <p className="login-subtitle">
            {isRegister ? c.newAccount : c.subtitle}
          </p>
        </div>

        {registrationAllowed && (
          <div className="login-tabs">
            <button
              className={'login-tab' + (tab === 'login' ? ' active' : '')}
              onClick={() => switchTab('login')}
              type="button"
            >
              {c.signIn}
            </button>
            <button
              className={'login-tab' + (tab === 'register' ? ' active' : '')}
              onClick={() => switchTab('register')}
              type="button"
            >
              {c.register}
            </button>
          </div>
        )}

        <form onSubmit={submitCredentials} className="login-form">
          <div className="login-field">
            <label htmlFor="login-user">{c.username}</label>
            <input
              id="login-user"
              value={loginUser}
              onChange={(e) => setLoginUser(e.target.value)}
              placeholder={c.username}
              autoFocus
              autoComplete="username"
            />
          </div>
          {isRegister && (
            <div className="login-field">
              <label htmlFor="login-name">{c.displayName}</label>
              <input
                id="login-name"
                value={loginName}
                onChange={(e) => setLoginName(e.target.value)}
                placeholder="Wie möchtest du angezeigt werden?"
              />
            </div>
          )}
          <div className="login-field">
            <label htmlFor="login-pass">{c.password}</label>
            <input
              id="login-pass"
              value={loginPass}
              onChange={(e) => setLoginPass(e.target.value)}
              placeholder={c.password}
              type="password"
              autoComplete={isRegister ? 'new-password' : 'current-password'}
            />
            {isRegister && loginPass.length > 0 && loginPass.length < 4 && (
              <p className="login-hint">{c.min}</p>
            )}
          </div>
          {isRegister && (
            <div className="login-field">
              <label htmlFor="login-pass-confirm">{c.confirm}</label>
              <input
                id="login-pass-confirm"
                value={loginPassConfirm}
                onChange={(e) => setLoginPassConfirm(e.target.value)}
                placeholder={c.repeat}
                type="password"
                autoComplete="new-password"
              />
            </div>
          )}
          <button type="submit" className="login-btn" disabled={!canSubmit}>
            {loading && <Spinner />}
            {loading
              ? (isRegister ? c.creating : c.signingIn)
              : (isRegister ? c.create : c.signIn)}
          </button>
          {loginError && <div className="login-error">{loginError}</div>}
          {loginSuccess && <div className="login-success">{loginSuccess}</div>}
        </form>

        <div className="login-footer">
          <button className="login-details-toggle" onClick={() => setShowDetails(!showDetails)}>
            {c.server}
          </button>
          {showDetails && (
            <div className="login-details">
              <input
                type="text"
                value={backendUrl}
                onChange={(e) => changeBackendUrl(e.target.value)}
                placeholder="http://127.0.0.1:5001"
              />
              <small>{c.serverHint}</small>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
