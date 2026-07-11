'use client';

import { useEffect, useState, useCallback } from 'react';
import { apiFetch, getApiBase } from '../../lib/api';

const API_BASE = () => getApiBase();

export default function AutomationsTab({ tr, language }) {
  const [automations, setAutomations] = useState([]);
  const [history, setHistory] = useState([]);
  const [toolSchema, setToolSchema] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [showHistory, setShowHistory] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [loading, setLoading] = useState(true);

  const L = (de, en) => language === 'de' ? de : en;

  const load = useCallback(async () => {
    try {
      const [aRes, sRes] = await Promise.all([
        fetch(`${getApiBase()}/api/automations`),
        fetch(`${getApiBase()}/api/automations/schema`)
      ]);
      const aData = await aRes.json();
      const sData = await sRes.json();
      if (aData.success) setAutomations(aData.automations);
      if (sData.success) setToolSchema(sData);
    } catch (e) {
      console.error('Failed to load automations:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadHistory = useCallback(async () => {
    try {
      const res = await fetch(`${getApiBase()}/api/automations/history?limit=50`);
      const data = await res.json();
      if (data.success) setHistory(data.history);
    } catch (e) {
      console.error('Failed to load history:', e);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = async (auto) => {
    const method = automations.find(a => a.id === auto.id) ? 'PUT' : 'POST';
    const url = method === 'PUT' ? `${getApiBase()}/api/automations/${auto.id}` : `${getApiBase()}/api/automations`;
    try {
      const res = await fetch(url, {
        method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(auto)
      });
      if ((await res.json()).success) { await load(); setEditingId(null); }
    } catch (e) { console.error('Save failed:', e); }
  };

  const remove = async (id) => {
    if (!window.confirm(L('Wirklich löschen?', 'Really delete?'))) return;
    try {
      await fetch(`${getApiBase()}/api/automations/${id}`, { method: 'DELETE' });
      await load();
    } catch (e) { console.error('Delete failed:', e); }
  };

  const toggle = async (auto) => {
    await save({ ...auto, enabled: !auto.enabled });
  };

  const test = async (auto) => {
    setTestResult({ running: true, name: auto.name });
    try {
      const res = await fetch(`${getApiBase()}/api/automations/${auto.id}/test`, { method: 'POST' });
      const data = await res.json();
      setTestResult({ ...data, name: auto.name, ts: new Date().toLocaleTimeString() });
    } catch (e) { setTestResult({ success: false, error: String(e), name: auto.name }); }
  };

  const renderTrigger = (t) => {
    if (!t) return '–';
    if (t.type === 'interval') {
      const p = []; if (t.hours) p.push(`${t.hours}h`); if (t.minutes) p.push(`${t.minutes}m`);
      return `Alle ${p.join(' ') || '?'}`;
    }
    const p = [];
    if (t.hour !== undefined && t.hour !== '') p.push(`${String(t.hour).padStart(2,'0')}:${String(t.minute||'0').padStart(2,'0')}`);
    if (t.day_of_week) p.push(`(${t.day_of_week})`);
    if (t.day) p.push(`Tag ${t.day}`);
    return p.join(' ') || 'Cron';
  };

  if (loading) return <div className="settings-panel"><p>Lade...</p></div>;

  return (
    <div className="settings-panel">
      <div className="panel-section">
        <div className="section-title">
          <i className="fas fa-clock"></i> {L('Automatisierungen', 'Automations')}
        </div>
        <div style={{display: 'flex', gap: 8, marginBottom: 16}}>
          <button className="btn secondary" onClick={() => { loadHistory(); setShowHistory(!showHistory); }}>
            <i className="fas fa-history"></i> {L('Verlauf', 'History')}
          </button>
          <button className="btn primary" onClick={() => setEditingId('__new__')}>
            <i className="fas fa-plus"></i> {L('Neue Automation', 'New Automation')}
          </button>
        </div>

        {testResult && (
          <div style={{border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: 12, marginBottom: 12, background: 'var(--card-bg)'}}>
            <strong>{testResult.name}</strong> – {testResult.running ? 'Läuft...' : testResult.success ? '✅ Erfolg' : `❌ ${testResult.error}`}
            {testResult.results?.map((r,i) => (
              <div key={i} style={{fontSize:'0.85em', padding: '4px 0', borderBottom: '1px solid var(--border)', color: r.status === 'error' ? '#d9534f' : r.status === 'skipped' ? 'var(--muted)' : 'inherit'}}>
                <strong>{r.step}:</strong> {r.status === 'success' ? '✅' : r.status === 'skipped' ? '⏭️' : '❌'} {(r.result||'').slice(0,200)}
              </div>
            ))}
            <button className="btn secondary" style={{marginTop:8}} onClick={() => setTestResult(null)}>{L('Schließen', 'Close')}</button>
          </div>
        )}

        {showHistory && (
          <div style={{border:'1px solid var(--border)', borderRadius:'var(--radius)', padding:12, marginBottom:12, maxHeight:300, overflowY:'auto', background:'var(--card-bg)'}}>
            <div style={{fontWeight:600, marginBottom:8, fontSize:'0.9em'}}>{L('Ausführungsverlauf', 'Execution History')}</div>
            {history.length === 0 ? <p style={{color:'var(--muted)', fontSize:'0.85em'}}>{L('Noch keine Ausführungen.', 'No executions yet.')}</p> : history.map((h,i) => (
              <div key={i} style={{padding:'6px 0', borderBottom:'1px solid var(--border)', fontSize:'0.85em'}}>
                <div style={{display:'flex', alignItems:'center', gap:8, flexWrap:'wrap'}}>
                  <strong>{h.name}</strong>
                  <span style={{color:'var(--muted)', fontSize:'0.8em'}}>{new Date(h.timestamp).toLocaleString()}</span>
                  <span style={{fontSize:'0.75em', padding:'1px 6px', borderRadius:'var(--radius-sm)', fontWeight:600, background: h.success ? '#5cb85c33' : '#d9534f33', color: h.success ? '#5cb85c' : '#d9534f'}}>{h.success ? 'OK' : 'FEHLER'}</span>
                  <span style={{fontSize:'0.8em', color:'var(--muted)'}}>{h.trigger === 'manual' ? '🧪 Manuell' : '⏰ Geplant'}</span>
                </div>
                {h.steps && <div style={{display:'flex', flexWrap:'wrap', gap:4, marginTop:4}}>{h.steps.map((s,j) => (
                  <span key={j} style={{fontSize:'0.8em', padding:'1px 6px', borderRadius:'var(--radius-sm)', background: s.status === 'error' ? '#d9534f22' : s.status === 'skipped' ? '#f0ad4e22' : 'var(--chip-bg)'}}>{s.step}: {s.status === 'success' ? '✅' : s.status === 'skipped' ? '⏭️' : '❌'}</span>
                ))}</div>}
              </div>
            ))}
          </div>
        )}

        {editingId === '__new__' && (
          <AutoForm auto={{id:Date.now().toString(), name:'', description:'', enabled:true, trigger:{type:'cron', hour:'6', minute:'0'}, steps:[{tool:'', params:{}}]}} schema={toolSchema} onSave={save} onCancel={() => setEditingId(null)} L={L} language={language} />
        )}

        {automations.length === 0 && editingId !== '__new__' ? (
          <div style={{textAlign:'center', padding:32, color:'var(--muted)'}}>
            <i className="fas fa-clock" style={{fontSize:40, opacity:0.3}}></i>
            <p>{L('Noch keine Automatisierungen.', 'No automations yet.')}</p>
            <p style={{fontSize:'0.85em'}}>{L('Erstelle eine, um wiederkehrende Aufgaben zu automatisieren.', 'Create one to automate recurring tasks.')}</p>
          </div>
        ) : (
          <div style={{display:'flex', flexDirection:'column', gap:8}}>
            {automations.map(auto => (
              <div key={auto.id} style={{border:'1px solid var(--border)', borderRadius:'var(--radius)', padding:'10px 14px', background:'var(--card-bg)', opacity: auto.enabled ? 1 : 0.45}}>
                <div style={{display:'flex', alignItems:'center', gap:12}}>
                  <label style={{position:'relative', display:'inline-block', width:36, height:20, flexShrink:0}}>
                    <input type="checkbox" checked={auto.enabled} onChange={() => toggle(auto)} style={{opacity:0, width:0, height:0}} />
                    <span style={{position:'absolute', cursor:'pointer', inset:0, background: auto.enabled ? 'var(--brand)' : 'var(--border)', borderRadius:20, transition:'0.3s'}}>
                      <span style={{position:'absolute', content:'', height:14, width:14, left: auto.enabled ? 19 : 3, bottom:3, background:'#fff', borderRadius:'50%', transition:'0.3s'}}></span>
                    </span>
                  </label>
                  <div style={{flex:1, minWidth:0}}>
                    <strong style={{fontSize:'0.95em'}}>{auto.name || '(unbenannt)'}</strong>
                    {auto.description && <div style={{fontSize:'0.8em', color:'var(--muted)'}}>{auto.description}</div>}
                    <span style={{fontSize:'0.75em', color:'var(--brand)', fontFamily:'monospace', background:'color-mix(in srgb, var(--brand) 10%, transparent)', padding:'1px 7px', borderRadius:'var(--radius-sm)', display:'inline-block', marginTop:2}}>{renderTrigger(auto.trigger)}</span>
                  </div>
                  <div style={{display:'flex', gap:4, flexShrink:0}}>
                    <button className="btn secondary" style={{padding:'4px 8px', fontSize:'0.8em'}} onClick={() => test(auto)} title={L('Testen','Test')}><i className="fas fa-play"></i></button>
                    <button className="btn secondary" style={{padding:'4px 8px', fontSize:'0.8em'}} onClick={() => setEditingId(auto.id)} title={L('Bearbeiten','Edit')}><i className="fas fa-pen"></i></button>
                    <button className="btn secondary" style={{padding:'4px 8px', fontSize:'0.8em'}} onClick={() => remove(auto.id)} title={L('Löschen','Delete')}><i className="fas fa-trash"></i></button>
                  </div>
                </div>
                {auto.steps?.length > 0 && (
                  <div style={{display:'flex', flexWrap:'wrap', gap:4, marginTop:8, paddingTop:8, borderTop:'1px solid var(--border)'}}>
                    {auto.steps.map((s,i) => (
                      <span key={i} style={{fontSize:'0.75em', background:'var(--chip-bg)', padding:'2px 8px', borderRadius:'var(--radius-sm)', color:'var(--muted)', display:'inline-flex', alignItems:'center', gap:3}}>
                        <i className="fas fa-arrow-right" style={{fontSize:'0.6em', color:'var(--brand)'}}></i> {s.tool || '?'}
                      </span>
                    ))}
                  </div>
                )}
                {editingId === auto.id && (
                  <div style={{marginTop:12, paddingTop:12, borderTop:'1px solid var(--border)'}}>
                    <AutoForm auto={auto} schema={toolSchema} onSave={save} onCancel={() => setEditingId(null)} L={L} language={language} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function AutoForm({ auto, schema, onSave, onCancel, L, language }) {
  const [draft, setDraft] = useState(auto);
  const set = (k,v) => setDraft({...draft, [k]:v});
  const setTrigger = (k,v) => set('trigger', {...(draft.trigger||{}), [k]:v});
  const setStep = (i,k,v) => {
    const s = [...(draft.steps||[])]; s[i] = {...s[i], [k]:v}; set('steps', s);
  };
  const addStep = () => set('steps', [...(draft.steps||[]), {tool:'', params:{}}]);
  const removeStep = (i) => set('steps', (draft.steps||[]).filter((_,j)=>j!==i));

  return (
    <div style={{display:'flex', flexDirection:'column', gap:10, fontSize:'0.9em'}}>
      <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:8}}>
        <div>
          <label style={{fontSize:'0.8em', color:'var(--muted)', display:'block', marginBottom:2}}>{L('Name','Name')}</label>
          <input type="text" value={draft.name||''} onChange={e=>set('name',e.target.value)} placeholder={L('z.B. Morgen-News','e.g. Morning News')} style={{width:'100%', background:'var(--bg)', border:'1px solid var(--border)', borderRadius:'var(--radius-sm)', padding:'6px 8px', color:'var(--ink)'}} />
        </div>
        <div>
          <label style={{fontSize:'0.8em', color:'var(--muted)', display:'block', marginBottom:2}}>{L('Beschreibung','Description')}</label>
          <input type="text" value={draft.description||''} onChange={e=>set('description',e.target.value)} placeholder={L('Optional','Optional')} style={{width:'100%', background:'var(--bg)', border:'1px solid var(--border)', borderRadius:'var(--radius-sm)', padding:'6px 8px', color:'var(--ink)'}} />
        </div>
      </div>

      <div style={{borderTop:'1px solid var(--border)', paddingTop:8}}>
        <div style={{fontWeight:600, fontSize:'0.85em', marginBottom:6}}><i className="fas fa-bolt" style={{color:'var(--brand)', marginRight:4}}></i>{L('Auslöser (Trigger)','Trigger')}</div>
        <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:8}}>
          <div>
            <label style={{fontSize:'0.8em',color:'var(--muted)',display:'block',marginBottom:2}}>{L('Typ','Type')}</label>
            <select value={draft.trigger?.type||'cron'} onChange={e=>setTrigger('type',e.target.value)} style={{width:'100%',background:'var(--bg)',border:'1px solid var(--border)',borderRadius:'var(--radius-sm)',padding:'6px 8px',color:'var(--ink)'}}>
              <option value="cron">{L('Cron (zeitgesteuert)','Cron (scheduled)')}</option>
              <option value="interval">{L('Intervall','Interval')}</option>
            </select>
          </div>
          {draft.trigger?.type === 'cron' ? (
            <>
              <div>
                <label style={{fontSize:'0.8em',color:'var(--muted)',display:'block',marginBottom:2}}>{L('Stunde','Hour')}</label>
                <input type="text" value={draft.trigger?.hour??''} onChange={e=>setTrigger('hour',e.target.value)} placeholder="6" style={{width:'100%',background:'var(--bg)',border:'1px solid var(--border)',borderRadius:'var(--radius-sm)',padding:'6px 8px',color:'var(--ink)'}} />
              </div>
              <div>
                <label style={{fontSize:'0.8em',color:'var(--muted)',display:'block',marginBottom:2}}>{L('Minute','Minute')}</label>
                <input type="text" value={draft.trigger?.minute??''} onChange={e=>setTrigger('minute',e.target.value)} placeholder="0" style={{width:'100%',background:'var(--bg)',border:'1px solid var(--border)',borderRadius:'var(--radius-sm)',padding:'6px 8px',color:'var(--ink)'}} />
              </div>
              <div>
                <label style={{fontSize:'0.8em',color:'var(--muted)',display:'block',marginBottom:2}}>{L('Wochentag','Day of Week')}</label>
                <input type="text" value={draft.trigger?.day_of_week??''} onChange={e=>setTrigger('day_of_week',e.target.value)} placeholder="mon-fri" style={{width:'100%',background:'var(--bg)',border:'1px solid var(--border)',borderRadius:'var(--radius-sm)',padding:'6px 8px',color:'var(--ink)'}} />
              </div>
              <div>
                <label style={{fontSize:'0.8em',color:'var(--muted)',display:'block',marginBottom:2}}>{L('Tag (Monat)','Day (Month)')}</label>
                <input type="text" value={draft.trigger?.day??''} onChange={e=>setTrigger('day',e.target.value)} placeholder={L('leer = täglich','empty = daily')} style={{width:'100%',background:'var(--bg)',border:'1px solid var(--border)',borderRadius:'var(--radius-sm)',padding:'6px 8px',color:'var(--ink)'}} />
              </div>
            </>
          ) : (
            <>
              <div>
                <label style={{fontSize:'0.8em',color:'var(--muted)',display:'block',marginBottom:2}}>Stunden</label>
                <input type="number" min="0" value={draft.trigger?.hours??0} onChange={e=>setTrigger('hours',parseInt(e.target.value)||0)} style={{width:'100%',background:'var(--bg)',border:'1px solid var(--border)',borderRadius:'var(--radius-sm)',padding:'6px 8px',color:'var(--ink)'}} />
              </div>
              <div>
                <label style={{fontSize:'0.8em',color:'var(--muted)',display:'block',marginBottom:2}}>Minuten</label>
                <input type="number" min="0" value={draft.trigger?.minutes??0} onChange={e=>setTrigger('minutes',parseInt(e.target.value)||0)} style={{width:'100%',background:'var(--bg)',border:'1px solid var(--border)',borderRadius:'var(--radius-sm)',padding:'6px 8px',color:'var(--ink)'}} />
              </div>
            </>
          )}
        </div>
        {schema?.trigger_examples && draft.trigger?.type === 'cron' && (
          <div style={{marginTop:6}}>
            <label style={{fontSize:'0.8em',color:'var(--muted)',display:'block',marginBottom:3}}>{L('Schnellauswahl:','Quick select:')}</label>
            <div style={{display:'flex',flexWrap:'wrap',gap:4}}>
              {schema.trigger_examples.map((ex,i) => (
                <button key={i} className="btn secondary" style={{padding:'2px 8px',fontSize:'0.75em'}} onClick={() => {setTrigger('type','cron'); Object.entries(ex.value).forEach(([k,v])=>setTrigger(k,v));}}>{ex.label}</button>
              ))}
            </div>
          </div>
        )}
      </div>

      <div style={{borderTop:'1px solid var(--border)', paddingTop:8}}>
        <div style={{fontWeight:600, fontSize:'0.85em', marginBottom:6}}><i className="fas fa-list" style={{color:'var(--brand)', marginRight:4}}></i>{L('Schritte (Aktionen)','Steps (Actions)')}</div>
        <div style={{fontSize:'0.78em',color:'var(--muted)',marginBottom:8}}>
          {L('Jeder Schritt führt ein Tool aus. {{ step_0 }} = Ergebnis von Schritt 0. {{ date }} = heutiges Datum.','Each step runs a tool. {{ step_0 }} = result of step 0. {{ date }} = today.')}
        </div>
        {(draft.steps||[]).map((step,i) => (
          <div key={i} style={{border:'1px solid var(--border)',borderRadius:'var(--radius)',padding:'10px 12px',marginBottom:8,background:'var(--card-bg)'}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:6}}>
              <strong style={{fontSize:'0.85em'}}>{L('Schritt','Step')} {i+1}</strong>
              {(draft.steps||[]).length > 1 && <button className="btn secondary" style={{padding:'2px 6px',fontSize:'0.75em'}} onClick={()=>removeStep(i)}><i className="fas fa-times"></i></button>}
            </div>
            <div>
              <label style={{fontSize:'0.8em',color:'var(--muted)',display:'block',marginBottom:2}}>{L('Tool','Tool')}</label>
              <select value={step.tool} onChange={e=>setStep(i,'tool',e.target.value)} style={{width:'100%',background:'var(--bg)',border:'1px solid var(--border)',borderRadius:'var(--radius-sm)',padding:'6px 8px',color:'var(--ink)',marginBottom:6}}>
                <option value="">– {L('Bitte wählen','Select')} –</option>
                {(() => {
                  const groups = {};
                  (schema?.tools || []).forEach(t => {
                    const name = t.function?.name;
                    if (!name) return;
                    const g = (schema?.tool_groups || {})[name] || 'Sonstige';
                    if (!groups[g]) groups[g] = [];
                    groups[g].push(name);
                  });
                  return Object.entries(groups).map(([g, tools]) => (
                    <optgroup key={g} label={g}>
                      {tools.map(tn => <option key={tn} value={tn}>{tn}</option>)}
                    </optgroup>
                  ));
                })()}
              </select>
            </div>
            {step.tool && (
              <div>
                <label style={{fontSize:'0.8em',color:'var(--muted)',display:'block',marginBottom:2}}>{L('Parameter (JSON)','Parameters (JSON)')}</label>
                <textarea rows={2} value={JSON.stringify(step.params||{},null,2)} onChange={e=>{try{setStep(i,'params',JSON.parse(e.target.value))}catch{}}} placeholder='{"to": "mail@de", "body": "{{ step_0 }}"}' style={{width:'100%',background:'var(--bg)',border:'1px solid var(--border)',borderRadius:'var(--radius-sm)',padding:'6px 8px',color:'var(--ink)',fontFamily:'monospace',fontSize:'0.82em'}} />
              </div>
            )}
          </div>
        ))}
        <button className="btn secondary" style={{padding:'4px 10px',fontSize:'0.85em'}} onClick={addStep}><i className="fas fa-plus"></i> {L('Schritt hinzufügen','Add Step')}</button>
      </div>

      <div style={{display:'flex',justifyContent:'flex-end',gap:8,marginTop:4,paddingTop:10,borderTop:'1px solid var(--border)'}}>
        <button className="btn secondary" onClick={onCancel} style={{padding:'6px 14px'}}>{L('Abbrechen','Cancel')}</button>
        <button className="btn primary" onClick={()=>onSave(draft)} disabled={!draft.name||!(draft.steps||[]).length} style={{padding:'6px 14px'}}>
          <i className="fas fa-save"></i> {L('Speichern','Save')}
        </button>
      </div>
    </div>
  );
}
