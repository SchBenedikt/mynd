'use client';

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import SourceCard from './SourceCard';
import ContextDataCard from './ContextDataCard';
import ResearchStats from './ResearchStats';
import GeneratedFileCard from './GeneratedFileCard';
import BrowserPreview from './BrowserPreview';
import { parseSourceList, embedCitations, stripSourceList, renumberSources } from '../lib/sources';

function _stripToolTags(text) {
  if (!text) return text;
  return text
    .replace(/<tool[^>]*>[\s\S]*?<\/tool>/g, '')
    .replace(/<tool\s+[^>]*\/>/g, '')
    .replace(/<tool_code>[\s\S]*?<\/tool_code>/g, '')
    .replace(/<tool_call>[\s\S]*?<\/tool_call>/g, '')
    .replace(/\[TOOL_CALL\][\s\S]*?\[\/TOOL_CALL\]/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function CollapsibleSources({ sources }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="sources-collapsible">
      <button className="sources-toggle" onClick={() => setOpen(!open)}>
        <i className={`fas ${open ? 'fa-chevron-down' : 'fa-chevron-right'}`}></i>
        Quellen ({sources.length})
      </button>
      {open && (
        <div className="sources-list">
          {sources.map((s, i) => (
            <a key={i} href={s.url} target="_blank" rel="noopener noreferrer" className="source-entry">
              <span className="source-entry-num">({s.number})</span>
              <span className="source-entry-domain">{s.domain}</span>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

function LiveTools({ tools, thinking }) {
  const mergedThinking = (tools || []).filter(t => t.tool === 'think').map(t => t.args?.thought || '').join('').trim() || (thinking || '').trim();
  const actionTools = (tools || []).filter(t => t.tool !== 'think' && t.tool !== 'status');
  if (actionTools.length === 0 && !mergedThinking) return null;

  const rounds = {};
  for (const t of actionTools) {
    const rk = t.round || 1;
    if (!rounds[rk]) rounds[rk] = { round: rk, tools: [] };
    rounds[rk].tools.push(t);
  }

  return (
    <div className="live-stream-container">
      {mergedThinking && (
        <div className="live-round">
          <div className="live-round-header">
            <span>Überlegung</span>
          </div>
          <div className="live-round-tools">
            <div className="live-tool-row done think">
              <span className="live-tool-name"></span>
              <span className="live-tool-args-preview">{mergedThinking.slice(0, 300)}</span>
            </div>
          </div>
        </div>
      )}
      {Object.values(rounds).map((r) => (
        <div key={r.round} className="live-round">
          <div className="live-round-header">
            <span>Runde {r.round}</span>
            <span className="live-round-count">{r.tools.length} Tool(s)</span>
          </div>
          <div className="live-round-tools">
            {r.tools.map((t, i) => {
              const icon = t.status === 'running' ? <span className="live-spinner">⟳</span> : (t.success ? <span>✓</span> : <span>✗</span>);
              let browserData = t.browser;
              if (!browserData?.screenshot && t.tool?.startsWith('browser_') && t.result_preview) {
                try {
                  const p = JSON.parse(t.result_preview);
                  if (p.screenshot) browserData = p;
                } catch {
                  const m = t.result_preview.match(/"screenshot"\s*:\s*"([^"]+)"/);
                  if (m) browserData = { screenshot: m[1] };
                }
              }
              return (
                <div key={i} className={`live-tool-row ${t.status}`}>
                  <span className="live-tool-icon">{icon}</span>
                  <span className="live-tool-name">{t.tool}</span>
                  {t.result_preview && <span className="live-tool-args-preview" title={t.result_preview}>{t.result_preview.slice(0, 240)}</span>}
                  {t.duration_ms > 0 && <span className="live-tool-duration">{(t.duration_ms / 1000).toFixed(1)}s</span>}
                  {t.result_preview?.startsWith('{') && !t.result_preview.includes('❌') && browserData?.screenshot && (
                    <div className="live-tool-screenshot">
                      <BrowserPreview
                        screenshot={browserData.screenshot}
                        title={browserData.title || browserData.new_title}
                        url={browserData.url || browserData.new_url}
                        textPreview={browserData.text_preview || browserData.text}
                        compact={true}
                      />
                    </div>
                  )}
                  {t.result_preview?.startsWith('{') && !t.result_preview.includes('❌') && !browserData?.screenshot && (
                    <span className="live-tool-noimg">⚠️ Kein Screenshot</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function MessageList({
  messages, isThinking, liveTools,
  markdownComponents, handleMarkdownContentClick,
  messagesEndRef, sendMessage,
  calendarForm, setCalendarForm, submitCalendarForm, closeCalendarForm,
  taskForm, setTaskForm, submitTaskForm, closeTaskForm,
  integrationForm, setIntegrationForm, submitIntegrationForm, closeIntegrationForm,
  openPhotoPreview, onEditMessage, onCopyMessage,
  theme, darkMode, contrastColor, setTheme, setDarkMode, setContrastColor,
  DESIGN_COLOR_PRESETS, THEME_LABEL_KEY,
  t, tr, language
}) {
  const [copiedId, setCopiedId] = useState(null);

  const handleCopy = (msgId, text) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedId(msgId);
      setTimeout(() => setCopiedId(null), 2000);
    }).catch(() => { setCopiedId(msgId); setTimeout(() => setCopiedId(null), 2000); });
  };

  return (
    <div className="conversation">
      <div className="messages">
        {messages.map((msg) => {
          const trace = (liveTools?.[msg.id] && liveTools[msg.id].length > 0)
            ? liveTools[msg.id]
            : msg.streamTrace;
          const processed = msg.role === 'assistant' && msg.content
            ? (() => {
                const cleaned = _stripToolTags(msg.content);
                const { sources } = parseSourceList(cleaned);
                const renumbered = renumberSources(sources);
                const mainContent = sources.length > 0
                  ? embedCitations(stripSourceList(cleaned), renumbered)
                  : embedCitations(cleaned, sources);
                return { sources: renumbered, mainContent };
              })()
            : null;
          const displayContent = processed ? processed.mainContent : _stripToolTags(msg.content);

          return (
          <div key={msg.id} className={`message ${msg.role} ${msg.queued ? 'queued' : ''}`}>
            <div className={`bubble${msg.isStreaming ? ' streaming' : ''}`} data-msg-id={msg.id}>
              {msg.role === 'assistant' && <LiveTools tools={trace} thinking={msg.thinking} />}
              {msg.role === 'assistant' && msg.researchStats && msg.researchStats.length > 0 && (
                <ResearchStats stats={msg.researchStats} />
              )}
              {msg.role === 'assistant' ? (
                <div onClickCapture={handleMarkdownContentClick}>
                  {processed ? (
                    <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]} components={markdownComponents}>{processed.mainContent}</ReactMarkdown>
                  ) : (
                    <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[rehypeKatex]} components={markdownComponents}>{_stripToolTags(msg.content)}</ReactMarkdown>
                  )}
                </div>
              ) : msg.content}
              {msg.role === 'assistant' && processed?.sources?.length > 0 && (
                <CollapsibleSources sources={processed.sources} />
              )}
            </div>
            <div className="message-actions">
              {msg.role === 'user' && onEditMessage && (
                <button className="msg-action-btn" onClick={() => onEditMessage(msg)} title="Bearbeiten">
                  <i className="fas fa-pen"></i>
                </button>
              )}
              {msg.role === 'assistant' && msg.content && (
                <button className="msg-action-btn" onClick={() => handleCopy(msg.id, displayContent)} title="Kopieren">
                  {copiedId === msg.id ? <i className="fas fa-check"></i> : <i className="fas fa-copy"></i>}
                </button>
              )}
            </div>
            {msg.role === 'user' && msg.queued && <div className="queued-tag">In der Warteschlange</div>}
            {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
              <div className="sources-container">
                <div className="sources-header"><i className="fas fa-link"></i><span>{t('sources')} ({msg.sources.length})</span></div>
                <div className="sources-grid">{msg.sources.map((source, idx) => (<SourceCard key={idx} source={source} />))}</div>
              </div>
            )}
            {msg.role === 'assistant' && msg.files && msg.files.length > 0 && (
              <div className="generated-files-wrap">
                {msg.files.map((file, idx) => (
                  <GeneratedFileCard key={`${file.name}-${idx}`} file={file} />
                ))}
              </div>
            )}
            {msg.role === 'assistant' && msg.uiCards && msg.uiCards.length > 0 && (
              <div className="context-cards-wrap">
                {msg.uiCards.map((card, idx) => (
                  <ContextDataCard key={`${card.type || 'card'}-${idx}`} card={card} language={language}
                    onQueryAction={(query) => sendMessage(query)} onPhotoPreview={openPhotoPreview} />
                ))}
              </div>
            )}
            {msg.role === 'assistant' && msg.designControls && (
              <div className="chat-design-controls">
                <div className="chat-design-group">
                  <span>{t('theme')}</span>
                  <div className="chat-design-btn-row">
                    {['classic', 'ocean', 'graphite', 'lavender', 'rose', 'gold'].map((themeOption) => (
                      <button key={`chat-theme-${themeOption}`} className={`chat-design-btn ${theme === themeOption ? 'active' : ''}`}
                        type="button" onClick={() => setTheme(themeOption)}>
                        {THEME_LABEL_KEY[themeOption] || themeOption}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="chat-design-group">
                  <span>{t('darkMode')}</span>
                  <div className="chat-design-btn-row">
                    {['light', 'dark', 'auto'].map((modeOption) => (
                      <button key={`chat-mode-${modeOption}`} className={`chat-design-btn ${darkMode === modeOption ? 'active' : ''}`}
                        type="button" onClick={() => setDarkMode(modeOption)}>
                        {t(modeOption === 'dark' ? 'modeDark' : modeOption === 'light' ? 'modeLight' : 'modeAuto')}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="chat-design-group">
                  <span>Accent</span>
                  <div className="chat-color-row">
                    {DESIGN_COLOR_PRESETS.map((preset) => (
                      <button key={preset.id} type="button" className={`chat-color-btn ${(contrastColor || '').toLowerCase() === preset.value.toLowerCase() ? 'active' : ''}`}
                        style={{ '--chat-color': preset.value }} onClick={() => setContrastColor(preset.value)} title={preset.label} aria-label={preset.label} />
                    ))}
                    <button type="button" className="chat-design-btn" onClick={() => setContrastColor('')}>Reset</button>
                  </div>
                </div>
              </div>
            )}
            </div>
          );
        })}

        {isThinking && (
          <div className="message assistant">
            <div className="thinking-indicator"><div className="dot"></div><div className="dot"></div><div className="dot"></div></div>
          </div>
        )}

        {calendarForm.visible && (
          <div className="message assistant">
            <div className="bubble calendar-form-bubble">
              <h4>Termin erstellen</h4>
              {calendarForm.missingInfo.length > 0 && (
                <p className="calendar-form-hint">Bitte ergaenze: {calendarForm.missingInfo.join(', ')}</p>
              )}
              <form className="calendar-form" onSubmit={submitCalendarForm}>
                <label>Titel<input type="text" value={calendarForm.title} onChange={(e) => setCalendarForm(prev => ({ ...prev, title: e.target.value }))} placeholder="z.B. Team Meeting" required /></label>
                <label>Startzeit<input type="datetime-local" value={calendarForm.startTime} onChange={(e) => setCalendarForm(prev => ({ ...prev, startTime: e.target.value }))} required /></label>
                <label>Endzeit (optional)<input type="datetime-local" value={calendarForm.endTime} onChange={(e) => setCalendarForm(prev => ({ ...prev, endTime: e.target.value }))} /></label>
                {calendarForm.availableCalendars.length > 0 && (
                  <label>Kalender<select value={calendarForm.calendarName} onChange={(e) => setCalendarForm(prev => ({ ...prev, calendarName: e.target.value }))}>
                    {calendarForm.availableCalendars.map((cal) => (<option key={cal.name} value={cal.name}>{cal.name}</option>))}
                  </select></label>
                )}
                <label>Ort (optional)<input type="text" value={calendarForm.location} onChange={(e) => setCalendarForm(prev => ({ ...prev, location: e.target.value }))} placeholder="z.B. Berlin oder Zoom" /></label>
                {calendarForm.error && <p className="calendar-form-error">{calendarForm.error}</p>}
                <div className="calendar-form-actions">
                  <button type="button" className="btn" onClick={closeCalendarForm} disabled={calendarForm.submitting}>Abbrechen</button>
                  <button type="submit" className="btn primary" disabled={calendarForm.submitting}>{calendarForm.submitting ? t('saveEvent') : t('createEvent')}</button>
                </div>
              </form>
            </div>
          </div>
        )}

        {taskForm.visible && (
          <div className="message assistant">
            <div className="bubble calendar-form-bubble">
              <h4>Create Task</h4>
              {taskForm.missingInfo.length > 0 && (<p className="calendar-form-hint">Please add: {taskForm.missingInfo.join(', ')}</p>)}
              <form className="calendar-form" onSubmit={submitTaskForm}>
                <label>Title<input type="text" value={taskForm.title} onChange={(e) => setTaskForm(prev => ({ ...prev, title: e.target.value }))} placeholder="e.g. Submit tax documents" required /></label>
                <label>Due Date (optional)<input type="date" value={taskForm.dueDate} onChange={(e) => setTaskForm(prev => ({ ...prev, dueDate: e.target.value }))} /></label>
                <label>Priority<select value={taskForm.priority} onChange={(e) => setTaskForm(prev => ({ ...prev, priority: Number(e.target.value) }))}>
                  <option value={0}>No priority</option><option value={1}>High</option><option value={5}>Medium</option><option value={9}>Low</option>
                </select></label>
                {taskForm.availableTaskLists.length > 0 && (
                  <label>Task List<select value={taskForm.listName} onChange={(e) => setTaskForm(prev => ({ ...prev, listName: e.target.value }))}>
                    {taskForm.availableTaskLists.map((listName) => (<option key={listName} value={listName}>{listName}</option>))}
                  </select></label>
                )}
                <label>Location (optional)<input type="text" value={taskForm.location} onChange={(e) => setTaskForm(prev => ({ ...prev, location: e.target.value }))} placeholder="e.g. Office or Home" /></label>
                <label>Description (optional)<input type="text" value={taskForm.description} onChange={(e) => setTaskForm(prev => ({ ...prev, description: e.target.value }))} placeholder="Optional details" /></label>
                {taskForm.error && <p className="calendar-form-error">{taskForm.error}</p>}
                <div className="calendar-form-actions">
                  <button type="button" className="btn" onClick={closeTaskForm} disabled={taskForm.submitting}>Cancel</button>
                  <button type="submit" className="btn primary" disabled={taskForm.submitting}>{taskForm.submitting ? 'Saving...' : 'Create Task'}</button>
                </div>
              </form>
            </div>
          </div>
        )}

        {integrationForm.visible && (
          <div className="message assistant">
            <div className="bubble calendar-form-bubble">
              <h4>{integrationForm.title || 'Connect API'}</h4>
              {integrationForm.description && <p className="calendar-form-hint">{integrationForm.description}</p>}
              <form className="calendar-form" onSubmit={submitIntegrationForm}>
                {integrationForm.fields.map((field) => (
                  <label key={field.name || field.label}>
                    {field.label || field.name}
                    <input type={field.type || 'text'} value={integrationForm.values?.[field.name] || ''}
                      onChange={(e) => { setIntegrationForm(prev => ({ ...prev, values: { ...prev.values, [field.name]: e.target.value } })); }}
                      placeholder={field.placeholder || ''} required={Boolean(field.required)} />
                  </label>
                ))}
                {integrationForm.error && <p className="calendar-form-error">{integrationForm.error}</p>}
                <div className="calendar-form-actions integration-form-actions">
                  <button type="button" className="btn" onClick={closeIntegrationForm} disabled={integrationForm.submitting || integrationForm.loginFlowRunning}>Cancel</button>
                  <button type="submit" className="btn primary" disabled={integrationForm.submitting || integrationForm.loginFlowRunning}>
                    {integrationForm.submitting ? 'Saving...' : 'Save & Retry'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}
