'use client';

import React, { useEffect, useRef, useState, useCallback, useMemo } from 'react';
import * as d3 from 'd3';
import styles from './KnowledgeGraph.module.css';
import { apiFetch } from '../lib/api';
import { useTheme } from '../hooks/useTheme';

const NODE_TYPES = [
  { key: 'memory', color: '#FF6B9D', icon: '🧠', label: 'Erinnerung' },
  { key: 'document', color: '#EF4444', icon: '📄', label: 'Dokument' },
  { key: 'project', color: '#06B6D4', icon: '📌', label: 'Projekt' },
  { key: 'person', color: '#4F46E5', icon: '👤', label: 'Person' },
  { key: 'event', color: '#8B5CF6', icon: '📅', label: 'Event' },
  { key: 'task', color: '#F59E0B', icon: '✓', label: 'Task' },
  { key: 'organization', color: '#10B981', icon: '🏢', label: 'Org' },
  { key: 'meeting', color: '#EC4899', icon: '🤝', label: 'Meeting' },
];
const TYPE_MAP = Object.fromEntries(NODE_TYPES.map(t => [t.key, t]));
const ALL_TYPES = new Set(NODE_TYPES.map(t => t.key));

const GRAPH_ENDPOINT = '/api/knowledge/graph';
const EDGE_COLORS = { contains: '#888', related: '#FF6B9D' };

function readResponse(r) {
  const ct = r.headers.get('content-type') || '';
  if (ct.includes('application/json')) return r.json();
  return r.text().then(t => { try { return JSON.parse(t); } catch { return { success: false, error: t }; } });
}

export default function KnowledgeGraphComponent({ embedded = false }) {
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const simRef = useRef(null);
  const { darkMode } = useTheme();

  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const [activeTypes, setActiveTypes] = useState(new Set(ALL_TYPES));
  const [selectedNode, setSelectedNode] = useState(null);
  const [relatedData, setRelatedData] = useState(null);
  const [search, setSearch] = useState('');
  const [hoveredNode, setHoveredNode] = useState(null);

  const load = useCallback(async (opts = {}) => {
    const refresh = opts.refresh || false;
    try {
      setError(null);
      if (!graphData) setLoading(true); else setRefreshing(true);
      const url = refresh ? `${GRAPH_ENDPOINT}?refresh=true` : GRAPH_ENDPOINT;
      const r = await apiFetch(url, { cache: 'no-store' });
      const result = await readResponse(r);
      if (!r.ok || !result?.success) throw new Error(result?.error || `Fehler (${r.status})`);
      setGraphData(result.data);
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    } finally { setLoading(false); setRefreshing(false); }
  }, [graphData]);

  useEffect(() => { load(); }, []); // eslint-disable-line

  const fetchRelated = async (id) => {
    try {
      const r = await apiFetch(`/api/knowledge/graph/node/${id}`);
      const d = await readResponse(r);
      if (r.ok && d.success) setRelatedData(d.data);
    } catch (e) { console.error(e); }
  };

  const stats = useMemo(() => {
    if (!graphData) return null;
    return {
      nodes: graphData.nodes.length,
      edges: graphData.edges.length,
      byType: Object.fromEntries(
        NODE_TYPES.map(t => [t.key, graphData.nodes.filter(n => n.type === t.key).length])
      ),
    };
  }, [graphData]);

  const filtered = useMemo(() => {
    if (!graphData) return { nodes: [], links: [] };
    let nodes = graphData.nodes.filter(n => activeTypes.has(n.type));
    if (search.trim()) {
      const q = search.toLowerCase();
      nodes = nodes.filter(n =>
        (n.label || '').toLowerCase().includes(q) ||
        (n.properties?.key || '').toLowerCase().includes(q) ||
        (n.properties?.value || '').toLowerCase().includes(q) ||
        n.type.includes(q) ||
        (n.properties?.source || '').toLowerCase().includes(q)
      );
    }
    const ids = new Set(nodes.map(n => n.id));
    const links = graphData.edges.filter(e => ids.has(e.from) && ids.has(e.to));
    return { nodes, links: links.map(e => ({ source: e.from, target: e.to, type: e.type })) };
  }, [graphData, activeTypes, search]);

  // ── D3 Rendering (warmup-then-stop approach for stability) ──
  useEffect(() => {
    const el = svgRef.current;
    const container = containerRef.current;
    if (!el || !container) return;
    const { nodes, links } = filtered;
    if (!graphData || nodes.length === 0) return;

    const w = container.offsetWidth || 1200;
    const h = container.offsetHeight || 600;
    const isRerender = !!el.__dataInitialized;

    const svg = d3.select(el).attr('width', w).attr('height', h);
    if (!isRerender) svg.selectAll('*').remove();

    // ── Defs ──
    const defs = !isRerender ? svg.append('defs') : svg.select('defs');
    defs.selectAll('radialGradient').remove();
    const nid = d => d.id.replace(/[^a-zA-Z0-9]/g, '_');
    nodes.forEach(d => {
      const c = TYPE_MAP[d.type]?.color || '#999';
      defs.append('radialGradient').attr('id', `g_${nid(d)}`)
        .append('stop').attr('offset', '0%').attr('stop-color', c).attr('stop-opacity', 0.95)
        .append('stop').attr('offset', '100%').attr('stop-color', c).attr('stop-opacity', 0.3);
    });

    // ── Container g + Zoom ──
    let g = svg.select('g.graph-root').size() ? svg.select('g.graph-root') : svg.append('g').attr('class', 'graph-root');
    if (!isRerender) svg.call(d3.zoom().scaleExtent([0.2, 6]).on('zoom', e => g.attr('transform', e.transform)));

    // ── Degree-based sizing ──
    const linkCounts = {};
    links.forEach(l => { linkCounts[l.source.id || l.source] = (linkCounts[l.source.id || l.source] || 0) + 1; linkCounts[l.target.id || l.target] = (linkCounts[l.target.id || l.target] || 0) + 1; });
    const maxDeg = Math.max(...Object.values(linkCounts), 1);
    const rScale = d3.scaleSqrt().domain([0, maxDeg]).range([5, 16]);
    const fontSizeScale = d3.scaleLinear().domain([0, maxDeg]).range([9, 13]);

    // ── Links ──
    const linkG = g.select('g.links').size() ? g.select('g.links') : g.append('g').attr('class', 'links');
    const linkSel = linkG.selectAll('line').data(links, d => `${d.source.id || d.source}-${d.target.id || d.target}`);
    linkSel.join(
      enter => enter.append('line')
        .attr('stroke', d => EDGE_COLORS[d.type] || '#888')
        .attr('stroke-opacity', 0.35)
        .attr('stroke-width', d => d.type === 'related' ? 0.8 : 1.2)
        .attr('stroke-dasharray', d => d.type === 'related' ? '4,3' : null),
      update => update,
      exit => exit.remove()
    );

    // ── Nodes ──
    const nodeG = g.select('g.nodes').size() ? g.select('g.nodes') : g.append('g').attr('class', 'nodes');
    const nodeSel = nodeG.selectAll('circle').data(nodes, d => d.id);
    const circles = nodeSel.join(
      enter => enter.append('circle')
        .attr('fill', d => `url(#g_${nid(d)})`)
        .attr('stroke', d => TYPE_MAP[d.type]?.color || '#999')
        .attr('stroke-width', 2)
        .style('cursor', 'pointer')
        .style('filter', d => d.type === 'memory' ? 'drop-shadow(0 0 5px rgba(255,107,157,0.5))' : 'none')
        .on('mouseenter', function () {
          d3.select(this).attr('opacity', 1).attr('stroke', '#fff').attr('stroke-width', 3);
        })
        .on('mouseleave', function (e, d) {
          d3.select(this).attr('opacity', 0.85).attr('stroke', TYPE_MAP[d.type]?.color || '#999').attr('stroke-width', 2);
        })
        .on('click', (e, d) => { e.stopPropagation(); setSelectedNode(d); fetchRelated(d.id); })
        .call(d3.drag()
          .on('start', function (e, d) {
            if (!e.active) { sim.alpha(0.15).restart(); setTimeout(() => { if (sim) sim.stop(); }, 300); }
            d.fx = d.x; d.fy = d.y;
          })
          .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
          .on('end', function (e, d) {
            if (!e.active) sim.stop();
            d.fx = null; d.fy = null;
          })),
      update => update,
      exit => exit.remove()
    );
    circles.transition().duration(400)
      .attr('r', d => Math.max(rScale(linkCounts[d.id] || 0), 5))
      .attr('fill', d => `url(#g_${nid(d)})`)
      .attr('stroke', d => TYPE_MAP[d.type]?.color || '#999');

    // ── Labels ──
    const lblG = g.select('g.labels').size() ? g.select('g.labels') : g.append('g').attr('class', 'labels');
    const lblSel = lblG.selectAll('g').data(nodes, d => d.id);
    lblSel.join(
      enter => {
        const grp = enter.append('g').style('pointer-events', 'none');
        grp.append('rect').attr('rx', 4).attr('ry', 4).attr('fill', 'var(--bg-1, #fff)').attr('opacity', 0.85);
        grp.append('text').attr('text-anchor', 'middle').attr('dy', '0.35em')
          .attr('fill', 'var(--text, #333)').attr('font-weight', d => d.type === 'memory' ? '600' : '500');
        return grp;
      },
      update => update,
      exit => exit.remove()
    );
    lblSel.select('text').text(d => {
      const maxLen = d.type === 'memory' ? 18 : 14;
      let l = String(d.label || '').substring(0, maxLen);
      if (d.type === 'memory' && d.properties?.value) l += '…' + String(d.properties.value).substring(0, 10);
      return l;
    }).attr('font-size', d => `${Math.max(fontSizeScale(linkCounts[d.id] || 0), 9)}px`);
    lblSel.select('rect').each(function () {
      const text = d3.select(this.parentNode).select('text');
      const b = text.node()?.getBBox();
      if (b) d3.select(this).attr('x', b.x - 4).attr('y', b.y - 2).attr('width', b.width + 8).attr('height', b.height + 4);
    });

    // ── Hover tooltip ──
    g.selectAll('g.hover-tip').remove();
    if (hoveredNode && hoveredNode.x != null) {
      const tip = g.append('g').attr('class', 'hover-tip').style('pointer-events', 'none');
      const r = Math.max(rScale(linkCounts[hoveredNode.id] || 0), 5);
      tip.append('rect').attr('rx', 6).attr('ry', 6).attr('fill', 'rgba(0,0,0,0.75)').attr('opacity', 0.9);
      tip.append('text').attr('text-anchor', 'middle').attr('dy', '0.35em').attr('fill', '#fff').attr('font-size', '11px').attr('font-weight', '600')
        .text(`${hoveredNode.label} · ${TYPE_MAP[hoveredNode.type]?.label || hoveredNode.type}`);
      tip.attr('transform', `translate(${hoveredNode.x}, ${hoveredNode.y - r - 18})`);
      const b = tip.select('text').node()?.getBBox();
      if (b) tip.select('rect').attr('x', b.x - 6).attr('y', b.y - 4).attr('width', b.width + 12).attr('height', b.height + 8);
    }

    // ── Simulation: warmup + stop ──
    if (simRef.current) simRef.current.stop();

    const sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id(d => d.id).distance(d => d.type === 'contains' ? 35 : 70))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(w / 2, h / 2))
      .force('collision', d3.forceCollide().radius(d => Math.max(rScale(linkCounts[d.id] || 0) + 20, 35)))
      .velocityDecay(0.6).alphaDecay(0.15);

    for (let i = 0; i < 300; i++) sim.tick();
    sim.stop();
    simRef.current = sim;

    // Animate from current (or random) positions to settled positions
    const duration = isRerender ? 500 : 1;
    linkSel.transition().duration(duration)
      .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
    circles.transition().duration(duration)
      .attr('cx', d => d.x).attr('cy', d => d.y);
    lblSel.transition().duration(duration)
      .attr('transform', d => `translate(${d.x}, ${(d.y || 0) + Math.max(rScale(linkCounts[d.id] || 0), 5) + 12})`);

    el.__dataInitialized = true;
    return () => { if (simRef.current) { simRef.current.stop(); simRef.current = null; } };
  }, [filtered, graphData, hoveredNode]); // eslint-disable-line

  // ── Controls ──
  const resetZoom = () => {
    const svg = d3.select(svgRef.current);
    svg.transition().duration(500).call(d3.zoom().transform, d3.zoomIdentity);
  };

  const toggleType = (k) => {
    const next = new Set(activeTypes);
    if (next.has(k)) next.delete(k); else next.add(k);
    setActiveTypes(next);
  };

  // ── Render ──
  if (loading) return <div className={styles.container}><div className={styles.loadingMessage}><div className={styles.spinner}></div><span>Wissensgraph wird geladen…</span></div></div>;

  return (
    <div className={styles.container}>
      {/* Toolbar */}
      <div className={styles.toolbar}>
        <div className={styles.toolbarLeft}>
          {!embedded && <span style={{ fontWeight: 700, fontSize: 15 }}>🧠 Wissensgraph</span>}
          <div className={styles.typeFilter}>
            {NODE_TYPES.map(t => {
              const count = stats?.byType[t.key] || 0;
              const active = activeTypes.has(t.key);
              return (
                <button key={t.key} className={`${styles.typeBtn} ${active ? styles.typeBtnActive : ''}`}
                  style={{ '--type-color': t.color }}
                  onClick={() => toggleType(t.key)} title={`${t.label} (${count})`}>
                  {t.icon} {count}
                </button>
              );
            })}
          </div>
        </div>
        <div className={styles.toolbarRight}>
          {stats && <span className={styles.statPill}>{stats.nodes} Knoten · {stats.edges} Kanten</span>}
          <div className={styles.searchWrap}>
            <i className="fas fa-search" style={{ fontSize: 11, opacity: 0.5 }}></i>
            <input className={styles.searchInput} type="text" placeholder="Suchen…" value={search}
              onChange={e => setSearch(e.target.value)} />
            {search && <button className={styles.clearBtn} onClick={() => setSearch('')}><i className="fas fa-times"></i></button>}
          </div>
          <button className={styles.toolBtn} onClick={resetZoom} title="Zoom zurücksetzen"><i className="fas fa-expand"></i></button>
          <button className={styles.toolBtn} onClick={() => load({ refresh: true })} disabled={refreshing} title="Neu laden">
            <i className={`fas fa-sync-alt ${refreshing ? styles.spin : ''}`}></i>
          </button>
        </div>
      </div>

      {error && <div className={styles.error}><strong>Fehler:</strong> {error} <button onClick={() => load()}>Wiederholen</button></div>}

      {/* Graph */}
      <div className={styles.graphContainer} ref={containerRef}>
        <svg ref={svgRef}></svg>
        {filtered.nodes.length === 0 && <div className={styles.emptyHint}>
          {activeTypes.size === 0 ? 'Alle Typen ausgeblendet.' : search ? `Keine Treffer für „${search}“` : 'Keine Daten'}
        </div>}
        {refreshing && <div className={styles.loadingOverlay}><div className={styles.spinner}></div></div>}
      </div>

      {/* Sidebar */}
      {selectedNode && (
        <div className={styles.sidebar} onClick={e => e.target === e.currentTarget && setSelectedNode(null)}>
          <div className={styles.sidebarClose} onClick={() => setSelectedNode(null)}>×</div>
          <div className={styles.sidebarHead}>
            <div className={styles.sidebarAvatar} style={{ background: TYPE_MAP[selectedNode.type]?.color || '#999' }}>
              {TYPE_MAP[selectedNode.type]?.icon || '📄'}
            </div>
            <div>
              <div className={styles.sidebarTitle}>{selectedNode.label}</div>
              <div className={styles.sidebarType}>{TYPE_MAP[selectedNode.type]?.label || selectedNode.type}</div>
            </div>
          </div>

          {selectedNode.properties && Object.keys(selectedNode.properties).length > 0 && (
            <div className={styles.sidebarSection}>
              <div className={styles.sidebarSectionTitle}>Eigenschaften</div>
              {Object.entries(selectedNode.properties).map(([k, v]) => (
                <div key={k} className={styles.sidebarProp}>
                  <div className={styles.sidebarPropKey}>{k}</div>
                  <div className={styles.sidebarPropVal}>{String(v).substring(0, 500)}</div>
                </div>
              ))}
            </div>
          )}

          {relatedData?.nodes && Object.keys(relatedData.nodes).length > 0 && (
            <div className={styles.sidebarSection}>
              <div className={styles.sidebarSectionTitle}>Verbundene ({Object.keys(relatedData.nodes).length})</div>
              {Object.values(relatedData.nodes).map(n => (
                <div key={n.id} className={styles.relatedRow} onClick={() => { setSelectedNode(n); fetchRelated(n.id); }}>
                  <span className={styles.relatedDot} style={{ background: TYPE_MAP[n.type]?.color || '#999' }}></span>
                  <span>{n.label.substring(0, 40)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}