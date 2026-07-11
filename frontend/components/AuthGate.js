"use client";

import { useEffect, useState, useRef } from "react";
import { usePathname, useRouter } from 'next/navigation';
import './AuthGate.css';
import { apiFetch, getApiBase } from '../lib/api';

const LANGUAGE_KEY = 'mynd_language';
const TOKEN_KEY = 'mynd_token_v1';
const SETUP_FLOW_KEY = 'mynd_setup_flow_v1';

export default function AuthGate({ children }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [setupRequired, setSetupRequired] = useState(false);
  const [user, setUser] = useState(null);
  const [hasToken, setHasToken] = useState(false);
  const [forceOpen, setForceOpen] = useState(false);
  const [requireLoginSetting, setRequireLoginSetting] = useState(true);
  const lastReplaceRef = useRef(0);

  const guardedReplace = (url) => {
    const now = Date.now();
    if (now - lastReplaceRef.current < 2000) return;
    lastReplaceRef.current = now;
    router.replace(url);
  };

  useEffect(() => {
    let cancelled = false;

    try {
      const storedToken = (() => { try { return localStorage.getItem(TOKEN_KEY); } catch(e) { return null; } })();
      setHasToken(!!storedToken);

      if (storedToken) {
        apiFetch('/api/auth/me', { headers: { 'Authorization': `Bearer ${storedToken}` } })
          .then((r) => r.json())
          .then((data) => {
            if (!cancelled && data && data.authenticated && data.user) {
              setUser({ name: data.user.name, username: data.user.username, token: storedToken });
            }
          })
          .catch(() => {});
      }
    } catch (e) {}

    apiFetch('/api/setup/status')
      .then((r) => r.json())
      .then((data) => {
        if (cancelled) return;
        const needsSetup = Boolean(data && data.success && data.needs_setup);
        setSetupRequired(needsSetup);
        if (needsSetup && pathname !== '/setup') {
          guardedReplace('/setup');
        }
      })
      .catch(() => {});
    apiFetch('/api/auth/config')
      .then((r) => r.json())
      .then((data) => {
        if (cancelled) return;
        if (data?.success) {
          setRequireLoginSetting(data.requireLogin !== false);
        }
      })
      .catch(() => {});

    setReady(true);

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (setupRequired && pathname !== '/setup') {
      guardedReplace('/setup');
    }
  }, [ready, pathname, setupRequired]);

  useEffect(() => {
    const langSet = (() => { try { return !!localStorage.getItem(LANGUAGE_KEY); } catch(e) { return true; } })();
    if (!langSet && pathname !== '/language') {
      guardedReplace('/language');
    }
  }, [pathname]);

  useEffect(() => {
    const openHandler = () => {
      try {
        setForceOpen(true);
        router.push('/login');
      } catch (e) {}
    };
    window.addEventListener('open-auth', openHandler);
    return () => window.removeEventListener('open-auth', openHandler);
  }, [router]);

  useEffect(() => {
    const handleLogin = () => {
      try {
        const storedToken = localStorage.getItem(TOKEN_KEY);
        if (!storedToken) return;
        setHasToken(true);
        apiFetch('/api/auth/me', { headers: { 'Authorization': `Bearer ${storedToken}` } })
          .then(r => r.json())
          .then(data => {
            if (data?.authenticated && data.user) {
              setUser({ name: data.user.name, username: data.user.username, token: storedToken });
              setForceOpen(false);
            }
          })
          .catch(() => {});
      } catch (e) {}
    };
    window.addEventListener('auth-login', handleLogin);
    return () => window.removeEventListener('auth-login', handleLogin);
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (pathname === '/language' || pathname?.startsWith('/setup') || pathname === '/login') return;
    if (user && !forceOpen) return;
    if (hasToken && !forceOpen) return;
    if (!requireLoginSetting && !forceOpen) return;
    guardedReplace('/login');
  }, [ready, pathname, user, forceOpen, hasToken, requireLoginSetting]);

  if (!ready) return null;
  if (pathname === '/language') return children;
  if (pathname?.startsWith('/setup')) return children;
  if (pathname === '/login') return children;
  if (user && !forceOpen) return children;
  if (hasToken && !forceOpen) return children;
  if (!requireLoginSetting && !forceOpen) return children;

  return null;
}
