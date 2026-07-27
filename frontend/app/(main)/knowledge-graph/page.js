'use client';

import { usePageTitle } from '../../../hooks/usePageTitle';
import { useLanguage } from '../../../hooks/useLanguage';
import KnowledgeGraphComponent from '../../../components/KnowledgeGraph';

export default function KnowledgeGraphPage() {
  usePageTitle('Wissensgraph');
  const { language } = useLanguage();
  const tr = (de, en) => language === 'de' ? de : en;

  return (
    <div className="page-layout" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <div style={{
        padding: 'var(--spacing-lg) var(--spacing-xl) var(--spacing)',
        borderBottom: '1px solid var(--border)',
        background: 'var(--bg-1)',
      }}>
        <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 700 }}>
          🧠 {tr('Wissensgraph', 'Knowledge Graph')}
        </h1>
        <p style={{ margin: '4px 0 0', fontSize: '0.85rem', color: 'var(--muted)' }}>
          {tr('Visualisierung aller Entitäten, Speicher und ihre Beziehungen', 'Visualization of all entities, memories, and their relationships')}
        </p>
      </div>
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', background: 'var(--bg-2)' }}>
        <KnowledgeGraphComponent embedded={true} />
      </div>
    </div>
  );
}