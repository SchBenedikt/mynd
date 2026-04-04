'use client';

import KnowledgeGraphComponent from '../../components/KnowledgeGraph';
import Link from 'next/link';
import styles from './page.module.css';

export default function KnowledgeGraphPage() {
  return (
    <div className={styles.pageWrapper}>
      <Link href="/" className={styles.backLink}>
        ← Zurück zum Chat
      </Link>
      <KnowledgeGraphComponent />
    </div>
  );
}
