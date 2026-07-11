'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function ChatSummaryModal({ summaryPanel, onClose, onRegenerate, markdownComponents, handleMarkdownContentClick, tr }) {
  if (!summaryPanel.open) return null;
  return (
    <div className="chat-summary-overlay" onClick={() => onClose()}>
      <div className="chat-summary-modal" onClick={(event) => event.stopPropagation()}>
        <div className="chat-summary-glow" aria-hidden="true"></div>
        <button type="button" className="chat-summary-close" onClick={() => onClose()} aria-label="Zusammenfassung schliessen">×</button>
        <div className="chat-summary-header">
          <div className="chat-summary-badge"><i className="fas fa-sparkles"></i>KI Übersicht</div>
          <h3>{summaryPanel.title || 'Chat-Zusammenfassung'}</h3>
          <div className="chat-summary-meta-row">
            <span>{summaryPanel.stats.total} Nachrichten</span>
            <span>{summaryPanel.stats.user} Nutzer</span>
            <span>{summaryPanel.stats.assistant} Assistent</span>
            {summaryPanel.generatedAt > 0 && (
              <span>{new Date(summaryPanel.generatedAt).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}</span>
            )}
          </div>
        </div>
        <div className="chat-summary-body">
          {summaryPanel.loading && (
            <div className="chat-summary-loading">
              <div className="thinking-indicator"><div className="dot"></div><div className="dot"></div><div className="dot"></div></div>
              <p>Erstelle eine strukturierte Uebersicht...</p>
            </div>
          )}
          {!summaryPanel.loading && summaryPanel.error && <div className="chat-summary-error">{summaryPanel.error}</div>}
          {!summaryPanel.loading && !summaryPanel.error && summaryPanel.summary && (
            <div className="chat-summary-content markdown-content" onClickCapture={handleMarkdownContentClick}>
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{summaryPanel.summary}</ReactMarkdown>
            </div>
          )}
        </div>
        <div className="chat-summary-actions">
          <button type="button" className="btn" onClick={onRegenerate} disabled={summaryPanel.loading}>Neu generieren</button>
          <button type="button" className="btn primary" onClick={() => onClose()}>Schliessen</button>
        </div>
      </div>
    </div>
  );
}
