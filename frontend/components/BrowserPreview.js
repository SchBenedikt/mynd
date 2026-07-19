'use client';

import { useState } from 'react';

function backendBase() {
  if (typeof window === 'undefined') return 'http://127.0.0.1:5001';
  try {
    const raw = localStorage.getItem('backendUrl');
    if (raw && raw.trim()) return raw.replace(/\/+$/, '');
  } catch {}
  return 'http://127.0.0.1:5001';
}

function safeScreenshotSrc(screenshot) {
  if (!screenshot) return '';
  const lower = screenshot.toLowerCase().trim();
  if (lower.startsWith('javascript:')) return '';
  if (lower.startsWith('data:')) return '';
  if (lower.startsWith('vbscript:')) return '';
  if (screenshot.startsWith('http://') || screenshot.startsWith('https://')) return screenshot;
  return `${backendBase()}/${screenshot}`;
}

export default function BrowserPreview({ screenshot, title, url, textPreview, compact = false }) {
  const [expanded, setExpanded] = useState(false);
  const [imgError, setImgError] = useState(false);

  if (!screenshot && !title && !textPreview) return null;

  const domain = url ? (() => { try { return new URL(url).hostname; } catch { return url; } })() : '';

  if (compact) {
    return (
      <div className="browser-preview browser-preview--compact">
        {screenshot && !imgError && (
          <img
            src={safeScreenshotSrc(screenshot)}
            alt={title || 'Browser screenshot'}
            className="browser-preview__img browser-preview__img--small"
            onError={() => setImgError(true)}
            onClick={() => setExpanded(true)}
          />
        )}
        <div className="browser-preview__meta">
          {title && <span className="browser-preview__title">{title}</span>}
          {domain && <span className="browser-preview__domain">{domain}</span>}
        </div>

        {expanded && screenshot && !imgError && (
          <div className="browser-preview__overlay" onClick={() => setExpanded(false)}>
            <img
              src={safeScreenshotSrc(screenshot)}
              alt={title || 'Browser screenshot'}
              className="browser-preview__img browser-preview__img--full"
              onError={() => setImgError(true)}
            />
            <button className="browser-preview__close" onClick={() => setExpanded(false)}>×</button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="browser-preview">
      <div className="browser-preview__header">
        <span className="browser-preview__icon">🌐</span>
        {title && <span className="browser-preview__title">{title}</span>}
        {domain && <span className="browser-preview__domain">{domain}</span>}
        {url && (
          <a href={url} target="_blank" rel="noopener noreferrer" className="browser-preview__link">
            ↗
          </a>
        )}
      </div>

      {screenshot && !imgError && (
        <img
          src={safeScreenshotSrc(screenshot)}
          alt={title || 'Browser screenshot'}
          className="browser-preview__img"
          onError={() => setImgError(true)}
          onClick={() => setExpanded(true)}
        />
      )}

      {textPreview && (
        <div className="browser-preview__text">
          {textPreview.slice(0, expanded ? 3000 : 500)}
          {textPreview.length > (expanded ? 3000 : 500) && '...'}
        </div>
      )}

      {expanded && screenshot && !imgError && (
        <div className="browser-preview__overlay" onClick={() => setExpanded(false)}>
          <img
            src={safeScreenshotSrc(screenshot)}
            alt={title || 'Browser screenshot'}
            className="browser-preview__img browser-preview__img--full"
            onError={() => setImgError(true)}
          />
          <button className="browser-preview__close" onClick={() => setExpanded(false)}>×</button>
        </div>
      )}
    </div>
  );
}
