'use client';

import React, { useEffect, useRef, useState } from 'react';
import * as d3 from 'd3';
import styles from './KnowledgeGraph.module.css';

const NodeTypeColors = {
  person: '#4F46E5',
  event: '#8B5CF6',
  task: '#F59E0B',
  organization: '#10B981',
  document: '#EF4444',
  project: '#06B6D4',
  meeting: '#EC4899',
};

const NodeTypeLabels = {
  person: '👤 Person',
  event: '📅 Event',
  task: '✓ Task',
  organization: '🏢 Organisation',
  document: '📄 Dokument',
  project: '📌 Projekt',
  meeting: '🤝 Meeting',
};

export default function KnowledgeGraphComponent() {
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedTypes, setSelectedTypes] = useState(new Set(Object.keys(NodeTypeColors)));
  const [selectedNode, setSelectedNode] = useState(null);
  const [relatedData, setRelatedData] = useState(null);
  const [stats, setStats] = useState(null);

  // Fetch graph data on mount
  useEffect(() => {
    const fetchGraph = async () => {
      try {
        const response = await fetch('/api/knowledge/graph?refresh=true');
        const result = await response.json();
        
        if (result.success) {
          setGraphData(result.data);
          setStats(result.data.stats);
          setLoading(false);
        }
      } catch (error) {
        console.error('Error fetching knowledge graph:', error);
        setLoading(false);
      }
    };

    fetchGraph();
  }, []);

  // Fetch related node data
  const fetchRelatedNode = async (nodeId) => {
    try {
      const response = await fetch(`/api/knowledge/graph/node/${nodeId}`);
      const result = await response.json();
      
      if (result.success) {
        setRelatedData(result.data);
      }
    } catch (error) {
      console.error('Error fetching related nodes:', error);
    }
  };

  // Handle node clicks
  const handleNodeClick = (node) => {
    setSelectedNode(node);
    fetchRelatedNode(node.id);
  };

  // Toggle node type filter
  const toggleNodeType = (type) => {
    const newSelected = new Set(selectedTypes);
    if (newSelected.has(type)) {
      newSelected.delete(type);
    } else {
      newSelected.add(type);
    }
    setSelectedTypes(newSelected);
  };

  // Filter graph data based on selected types
  const getFilteredData = () => {
    if (!graphData) return { nodes: [], links: [] };

    const filteredNodes = graphData.nodes.filter(node =>
      selectedTypes.has(node.type)
    );
    const nodeIds = new Set(filteredNodes.map(n => n.id));

    const filteredLinks = graphData.edges.filter(edge =>
      nodeIds.has(edge.from) && nodeIds.has(edge.to)
    );

    return {
      nodes: filteredNodes,
      links: filteredLinks.map(edge => ({
        source: edge.from,
        target: edge.to,
        type: edge.type,
      })),
    };
  };

  // Render D3 graph
  useEffect(() => {
    if (!graphData || !svgRef.current) return;

    const filteredData = getFilteredData();
    if (filteredData.nodes.length === 0) return;

    const width = containerRef.current?.offsetWidth || 1200;
    const height = containerRef.current?.offsetHeight || 600;

    // Clear previous content
    d3.select(svgRef.current).selectAll('*').remove();

    // Create SVG
    const svg = d3.select(svgRef.current)
      .attr('width', width)
      .attr('height', height);

    // Add zoom behavior
    const g = svg.append('g');
    const zoom = d3.zoom().on('zoom', (event) => {
      g.attr('transform', event.transform);
    });
    svg.call(zoom);

    // Create simulation
    const simulation = d3.forceSimulation(filteredData.nodes)
      .force('link', d3.forceLink(filteredData.links)
        .id(d => d.id)
        .distance(60))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(40));

    // Create links
    const link = g.append('g')
      .selectAll('line')
      .data(filteredData.links)
      .enter()
      .append('line')
      .attr('stroke', '#999')
      .attr('stroke-opacity', 0.6)
      .attr('stroke-width', 1.5);

    // Create nodes
    const node = g.append('g')
      .selectAll('circle')
      .data(filteredData.nodes)
      .enter()
      .append('circle')
      .attr('r', 8)
      .attr('fill', d => NodeTypeColors[d.type] || '#999')
      .attr('opacity', 0.8)
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .style('cursor', 'pointer')
      .on('click', (event, d) => {
        event.stopPropagation();
        handleNodeClick(d);
      })
      .call(
        d3.drag()
          .on('start', dragstarted)
          .on('drag', dragged)
          .on('end', dragended)
      );

    // Create labels
    const labels = g.append('g')
      .selectAll('text')
      .data(filteredData.nodes)
      .enter()
      .append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '0.3em')
      .attr('font-size', '10px')
      .attr('fill', '#000')
      .attr('pointer-events', 'none')
      .text(d => d.label.substring(0, 15));

    // Drag functions
    function dragstarted(event, d) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }

    function dragged(event, d) {
      d.fx = event.x;
      d.fy = event.y;
    }

    function dragended(event, d) {
      if (!event.active) simulation.alphaTarget(0);
      d.fx = null;
      d.fy = null;
    }

    // Update positions on simulation tick
    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);

      node
        .attr('cx', d => d.x)
        .attr('cy', d => d.y);

      labels
        .attr('x', d => d.x)
        .attr('y', d => d.y);
    });

  }, [graphData, selectedTypes]);

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loadingMessage}>Wissensgraph wird geladen...</div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1>🧠 Wissensgraph</h1>
        <p>Visualisierung aller Entitäten und ihre Beziehungen</p>
      </div>

      {stats && (
        <div className={styles.stats}>
          <div className={styles.statItem}>
            <span className={styles.statLabel}>Entitäten:</span>
            <span className={styles.statValue}>{stats.node_count}</span>
          </div>
          <div className={styles.statItem}>
            <span className={styles.statLabel}>Beziehungen:</span>
            <span className={styles.statValue}>{stats.edge_count}</span>
          </div>
          <div className={styles.statItem}>
            <span className={styles.statLabel}>Aktualisiert:</span>
            <span className={styles.statValue}>{new Date(stats.last_update).toLocaleTimeString('de-DE')}</span>
          </div>
        </div>
      )}

      <div className={styles.filterPanel}>
        <h3>Entitätstypen:</h3>
        <div className={styles.filterButtons}>
          {Object.entries(NodeTypeColors).map(([type, color]) => (
            <button
              key={type}
              className={`${styles.filterButton} ${selectedTypes.has(type) ? styles.active : ''}`}
              style={{
                borderColor: color,
                backgroundColor: selectedTypes.has(type) ? color : 'transparent',
              }}
              onClick={() => toggleNodeType(type)}
            >
              {NodeTypeLabels[type]}
            </button>
          ))}
        </div>
      </div>

      <div className={styles.graphContainer} ref={containerRef}>
        <svg ref={svgRef}></svg>
      </div>

      {selectedNode && (
        <div className={styles.sidebar}>
          <div className={styles.close} onClick={() => setSelectedNode(null)}>×</div>
          <h2>{selectedNode.label}</h2>
          <p className={styles.nodeType}>{NodeTypeLabels[selectedNode.type]}</p>
          
          <div className={styles.properties}>
            <h3>Eigenschaften:</h3>
            {Object.entries(selectedNode.properties || {}).map(([key, value]) => (
              <div key={key} className={styles.property}>
                <strong>{key}:</strong>
                <span>{String(value).substring(0, 50)}</span>
              </div>
            ))}
          </div>

          {relatedData && (
            <div className={styles.related}>
              <h3>Verbundene Entitäten ({relatedData.nodes ? Object.keys(relatedData.nodes).length : 0}):</h3>
              <div className={styles.relatedList}>
                {relatedData.nodes && Object.values(relatedData.nodes).map(node => (
                  <div key={node.id} className={styles.relatedItem}>
                    <div 
                      className={styles.relatedColor}
                      style={{ backgroundColor: NodeTypeColors[node.type] || '#999' }}
                    ></div>
                    <span>{node.label.substring(0, 30)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
