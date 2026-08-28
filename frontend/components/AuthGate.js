"use client";

import { useCallback, useEffect, useState, useRef } from "react";
import { usePathname, useRouter } from 'next/navigation';
import './AuthGate.css';
import { apiFetch } from '../lib/api';
import LandingPage from './LandingPage';

export default function AuthGate({ children }) {
  const pathname = usePathname();
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [setupRequired, setSetupRequired] = useState(false);
  const [user, setUser] = useState(null);
  const [forceOpen, setForceOpen] = useState(false);
  const [requireLogin, setRequireLogin] = useState(true);
  const lastReplaceRef = useRef(0);

  const guardedReplace = useCallback((url) => {
    const now = Date.now();
    if (now - lastReplaceRef.current < 2000) return;
    lastReplaceRef.current = now;
    router.replace(url);
  }, [router]);

  useEffect(() => {
    let cancelled = false;
    const timeout = setTimeout(() => {
      if (!cancelled) setReady(true);
    }, 4000);
    Promise.allSettled([
      apiFetch('/api/auth/me')
        .then((r) => r.json())
        .then((data) => {
          if (!cancelled && data?.authenticated && data.user) {
            setUser(data.user);
            try { localStorage.setItem('mynd_user_v1', JSON.stringify(data.user)); } catch {}
          }
        }),
      apiFetch('/api/setup/status')
        .then((r) => r.json())
        .then((data) => {
          if (cancelled) return;
          const needsSetup = Boolean(data?.success && data.needs_setup);
          setSetupRequired(needsSetup);
          if (needsSetup && pathname !== '/setup') guardedReplace('/setup');
        }),
      apiFetch('/api/auth/config')
        .then((r) => r.json())
        .then((data) => {
          if (!cancelled && data?.success) setRequireLogin(data.requireLogin !== false);
        })
    ]).finally(() => {
      clearTimeout(timeout);
      if (!cancelled) setReady(true);
    });
    return () => { cancelled = true; clearTimeout(timeout); };
  }, [guardedReplace, pathname]);

  useEffect(() => {
    if (!ready) return;
    if (setupRequired && pathname !== '/setup') {
      guardedReplace('/setup');
    }
  }, [ready, pathname, setupRequired, guardedReplace]);

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
        apiFetch('/api/auth/me')
          .then(r => r.json())
          .then(data => {
            if (data?.authenticated && data.user) {
              setUser(data.user);
              try { localStorage.setItem('mynd_user_v1', JSON.stringify(data.user)); } catch {}
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
    if (pathname === '/' || pathname?.startsWith('/setup') || pathname === '/login' || pathname === '/developers' || pathname === '/guide') return;
    if ((user && !forceOpen) || !requireLogin) return;
    guardedReplace('/login');
  }, [ready, pathname, user, forceOpen, requireLogin, guardedReplace]);

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
  if (pathname?.startsWith('/setup')) return children;
  if (pathname === '/login') return children;
  if (pathname === '/developers') return children;
  if (pathname === '/guide') return children;
  if ((user && !forceOpen) || !requireLogin) return children;
  if (pathname === '/') return <LandingPage />;
  return null;
}
