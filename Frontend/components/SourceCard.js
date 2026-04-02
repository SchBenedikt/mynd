'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * SourceCard component for displaying source references
 * Shows where the AI retrieved information from (files, calendar events, todos, etc.)
 */
export default function SourceCard({ source }) {
  const [isOpen, setIsOpen] = useState(false);
  const closeButtonRef = useRef(null);
  const openButtonRef = useRef(null);

  const {
    source: sourceName,
    source_type,
    document,
    path,
    chunk_id,
    matched_sentence,
    content_preview,
    similarity_score,
  } = source;

  // Determine icon based on source type
  const getIcon = () => {
    switch (source_type) {
      case 'calendar':
        return '📅';
      case 'todo':
        return '✓';
      case 'photo':
      case 'image':
        return '🖼️';
      case 'chunk':
        return '🧩';
      case 'file':
      default:
        return '📄';
    }
  };

  const icon = getIcon();
  const showScore = typeof similarity_score === 'number' && similarity_score > 0 && similarity_score < 1;

  const decodeSafe = (value) => {
    if (!value || typeof value !== 'string') return '';
    try {
      return decodeURIComponent(value);
    } catch {
      return value;
    }
  };

  const normalizeText = (value) => {
    const text = String(value || '').replace(/\s+/g, ' ').trim();
    // Fix common OCR/parse issue where a sentence end is glued to next token.
    return text.replace(/([0-9A-Za-zÄÖÜäöüß])([A-ZÄÖÜ])/g, '$1 $2');
  };

  const prettifyType = (value) => {
    const v = String(value || 'chunk').toLowerCase();
    if (v === 'chunk') return 'Indexed Chunk';
    if (v === 'file') return 'Datei';
    if (v === 'photo' || v === 'image') return 'Bild';
    if (v === 'calendar') return 'Kalender';
    if (v === 'todo') return 'Aufgabe';
    return v;
  };

  const displayName = decodeSafe(document || sourceName || 'Knowledge Base');
  const displayPath = decodeSafe(path || '');
  const displaySource = decodeSafe(sourceName || displayName);
  const displayQuote = normalizeText(matched_sentence);
  const displayPreview = normalizeText(content_preview);

  const handleOpen = () => setIsOpen(true);
  const handleClose = useCallback(() => {
    setIsOpen(false);
    // Restore focus to the button that opened the modal
    openButtonRef.current?.focus();
  }, []);

  // Move focus into the modal when it opens, and handle ESC to close
  useEffect(() => {
    if (isOpen) {
      closeButtonRef.current?.focus();

      const handleKeyDown = (e) => {
        if (e.key === 'Escape') {
          handleClose();
        }
      };
      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [isOpen, handleClose]);

  // Prevent background scroll while modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      return () => { document.body.style.overflow = ''; };
    }
  }, [isOpen]);

  return (
    <div className="source-card">
      <button type="button" className="source-file-btn" onClick={handleOpen} ref={openButtonRef}>
        <div className="source-file-main">
          <span className="source-icon">{icon}</span>
          <span className="source-title" title={displayName}>{displayName}</span>
        </div>
        <div className="source-file-hint">Details</div>
        {showScore && Math.round(similarity_score * 100) >= 10 && (
          <span className="source-score">
            {Math.round(similarity_score * 100)}%
          </span>
        )}
      </button>

      {isOpen && (
        <div
          className="source-detail-overlay"
          onClick={handleClose}
          role="presentation"
        >
          <div
            className="source-detail-modal"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-labelledby="source-detail-title"
          >
            <div className="source-detail-head">
              <h4 className="source-detail-title" id="source-detail-title">{displayName}</h4>
              <button
                type="button"
                className="source-detail-close"
                onClick={handleClose}
                aria-label="Close source details"
                ref={closeButtonRef}
              >
                ×
              </button>
            </div>

            <div className="source-detail-grid">
              <span className="source-detail-label">Typ</span>
              <span className="source-detail-value">{prettifyType(source_type)}</span>

              <span className="source-detail-label">Chunk</span>
              <span className="source-detail-value">{chunk_id ? `#${chunk_id}` : 'n/a'}</span>

              <span className="source-detail-label">Path</span>
              <span className="source-detail-value">{displayPath || 'n/a'}</span>

              <span className="source-detail-label">Source</span>
              <span className="source-detail-value">{displaySource}</span>

              {showScore && Math.round(similarity_score * 100) >= 10 && (
                <>
                  <span className="source-detail-label">Relevanz</span>
                  <span className="source-detail-value">{Math.round(similarity_score * 100)}%</span>
                </>
              )}
            </div>

            {displayQuote && (
              <>
                <div className="source-detail-section-label">Treffer-Satz</div>
                <div className="source-detail-quote">"{displayQuote}"</div>
              </>
            )}

            {displayPreview && (
              <>
                <div className="source-detail-section-label">Kontext im Chunk</div>
                <div className="source-detail-preview">{displayPreview}</div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
