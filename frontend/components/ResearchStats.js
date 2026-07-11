'use client';
import { useState } from 'react';

function formatMs(ms) {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function ToolDetail({ tool }) {
  const [showDetails, setShowDetails] = useState(false);
  const args = tool.args || {};
  const argsEntries = Object.entries(args);
  const isVaultCall = tool.name === 'vault_get' || tool.name === 'vault_set' || tool.name === 'vault_list';
  const isThink = tool.name === 'think';

  const actionLabel = (() => {
    if (isThink) return '';
    if (tool.name === 'web_search') return args.query || '';
    if (tool.name === 'execute_bash' || tool.name === 'execute_ssh') return args.command || '';
    if (tool.name === 'http_request') return `${args.method || 'GET'} ${args.url || ''}`;
    if (tool.name === 'fetch_news') return args.category ? `Kategorie: ${args.category}` : '';
    if (tool.name === 'search_documents') return args.query || '';
    if (tool.name === 'prompt_user') return args.message || '';
    if (tool.name === 'nextcloud_read_file' || tool.name === 'nextcloud_write_file') return args.path || '';
    if (tool.name === 'memory_get' || tool.name === 'memory_set') return args.key || '';
    if (tool.name === 'read_local_file' || tool.name === 'write_local_file') return args.path || '';
    if (args.url) return args.url;
    if (args.query) return args.query;
    if (args.command) return args.command;
    if (args.path) return args.path;
    if (args.key) return args.key;
    return '';
  })();

  return (
    <div className="research-tool-detail">
      <div className="research-tool-row" onClick={() => setShowDetails(!showDetails)}>
        {isThink ? (
          <span className="research-tool-status think">💭</span>
        ) : (
          <span className={`research-tool-status ${tool.success ? 'success' : 'fail'}`}>
            {tool.success ? '✓' : '✗'}
          </span>
        )}
        <span className="research-tool-name">{isThink ? 'Überlegung' : tool.name}</span>
        {isThink ? (
          <span className="research-tool-thought">{args.thought || ''}</span>
        ) : (
          <span className="research-tool-action">{actionLabel}</span>
        )}
        <span className="research-tool-duration">{formatMs(tool.duration_ms)}</span>
        <i className={`fas fa-chevron-down ${showDetails ? 'open' : ''}`} style={{fontSize: '0.6rem', opacity: 0.4, marginLeft: '0.3rem', flexShrink: 0}}></i>
      </div>
      {showDetails && (
        <div className="research-tool-detail-body">
          {tool.result && (
            <div className="research-result">
              <div className="research-detail-label">Ergebnis:</div>
              <pre className="research-result-pre">
                {(typeof tool.result === 'string' ? tool.result : JSON.stringify(tool.result, null, 2)).slice(0, 1000)}
                {(typeof tool.result === 'string' ? tool.result.length : JSON.stringify(tool.result).length) > 1000 ? '...' : ''}
              </pre>
            </div>
          )}
          {!isThink && argsEntries.length > 0 && (
            <div className="research-args">
              <div className="research-detail-label">Parameter:</div>
              {argsEntries.map(([key, value]) => (
                <div key={key} className="research-arg-row">
                  <span className="research-arg-key">{key}:</span>
                  <span className="research-arg-value" style={isVaultCall ? { filter: 'blur(4px)', cursor: 'pointer', transition: 'filter 0.2s' } : {}} onClick={isVaultCall ? (e) => e.target.style.filter = 'none' : undefined}>
                    {typeof value === 'string' ? value : JSON.stringify(value, null, 2)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function ResearchStats({ stats }) {
  const [expanded, setExpanded] = useState(false);
  if (!stats || stats.length === 0) return null;

  const allTools = stats.flatMap(r => r.tools || []);
  const totalToolCalls = allTools.length;
  const totalDuration = stats.reduce((s, r) => s + r.duration_ms, 0);
  const failedCalls = allTools.filter(t => !t.success).length;
  const thinkCalls = allTools.filter(t => t.name === 'think').length;

  return (
    <div className="research-stats-container">
      <div className="research-stats-header" onClick={() => setExpanded(!expanded)}>
        <i className={`fas ${expanded ? 'fa-chevron-down' : 'fa-chevron-right'}`} style={{fontSize:'0.65rem', opacity:0.5}}></i>
        <span>{totalToolCalls} Schritte · {formatMs(totalDuration)}{thinkCalls > 0 ? ` · ${thinkCalls} Überlegungen` : ''}{failedCalls > 0 ? ` · ${failedCalls} fehlgeschlagen` : ''}</span>
      </div>
      {expanded && (
        <div className="research-stats-body">
          {allTools.map((tool, i) => (
            <ToolDetail key={i} tool={tool} />
          ))}
        </div>
      )}
    </div>
  );
}
