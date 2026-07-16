"use client";

import { useEffect, useState, useRef } from "react";
import { usePathname, useRouter } from 'next/navigation';
import './AuthGate.css';
import { apiFetch } from '../lib/api';

const LANGUAGE_KEY = 'mynd_language';
const TOKEN_KEY = 'mynd_token_v1';

export default function AuthGate({ children }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [setupRequired, setSetupRequired] = useState(false);
  const [user, setUser] = useState(null);
  const [forceOpen, setForceOpen] = useState(false);
  const lastReplaceRef = useRef(0);

  const guardedReplace = (url) => {
    const now = Date.now();
    if (now - lastReplaceRef.current < 2000) return;
    lastReplaceRef.current = now;
    router.replace(url);
  };

  useEffect(() => {
    let cancelled = false;
    const storedToken = (() => { try { return localStorage.getItem(TOKEN_KEY); } catch(e) { return null; } })();
    Promise.allSettled([
      storedToken
        ? apiFetch('/api/auth/me', { headers: { 'Authorization': `Bearer ${storedToken}` } })
            .then((r) => r.json())
            .then((data) => {
              if (!cancelled && data?.authenticated && data.user) {
                setUser({ ...data.user, token: storedToken });
              }
            })
        : Promise.resolve(),
      apiFetch('/api/setup/status')
        .then((r) => r.json())
        .then((data) => {
          if (cancelled) return;
          const needsSetup = Boolean(data?.success && data.needs_setup);
          setSetupRequired(needsSetup);
          if (needsSetup && pathname !== '/setup') guardedReplace('/setup');
        })
    ]).finally(() => { if (!cancelled) setReady(true); });

    return () => { cancelled = true; };
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
        apiFetch('/api/auth/me', { headers: { 'Authorization': `Bearer ${storedToken}` } })
          .then(r => r.json())
          .then(data => {
            if (data?.authenticated && data.user) {
              setUser({ ...data.user, token: storedToken });
              setForceOpen(false);
            }
          })
          .catch(() => setUser(null));
      } catch (e) {}
    };
    window.addEventListener('auth-login', handleLogin);
    return () => window.removeEventListener('auth-login', handleLogin);
  }, []);

  useEffect(() => {
    const handleExpired = () => {
      setUser(null);
      setForceOpen(true);
      if (pathname !== '/login') router.replace('/login');
    };
    window.addEventListener('auth-expired', handleExpired);
    return () => window.removeEventListener('auth-expired', handleExpired);
  }, [pathname, router]);

  useEffect(() => {
    if (!ready) return;
    if (pathname === '/language' || pathname?.startsWith('/setup') || pathname === '/login') return;
    if (user && !forceOpen) return;
    guardedReplace('/login');
  }, [ready, pathname, user, forceOpen]);

  if (!ready) return (
    <div className="authgate-skeleton">
      <div className="authgate-skeleton-sidebar">
        <div className="skeleton-brand" />
        <div className="skeleton-nav">
          <div className="skeleton-nav-item" />
          <div className="skeleton-nav-item" />
          <div className="skeleton-nav-item" />
          <div className="skeleton-nav-item" />
        </div>
        <div className="skeleton-chats">
          <div className="skeleton-chat-item" />
          <div className="skeleton-chat-item" />
          <div className="skeleton-chat-item" />
        </div>
      </div>
      <div className="authgate-skeleton-main">
        <div className="skeleton-landing">
          <div className="skeleton-logo" />
          <div className="skeleton-title" />
          <div className="skeleton-subtitle" />
          <div className="skeleton-composer" />
        </div>
      </div>
    </div>
  );
  if (pathname === '/language') return children;
  if (pathname?.startsWith('/setup')) return children;
  if (pathname === '/login') return children;
  if (user && !forceOpen) return children;
  return null;
}
