'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { useLanguage } from '../hooks/useLanguage';

const LABELS = {
  de: {
    '': 'Start',
    'settings': 'Einstellungen',
    'login': 'Anmelden',
    'language': 'Sprache',
    'projects': 'Projekte',
    'knowledge-graph': 'Wissensgraph',
    'setup': 'Einrichtung',
  },
  en: {
    '': 'Home',
    'settings': 'Settings',
    'login': 'Sign In',
    'language': 'Language',
    'projects': 'Projects',
    'knowledge-graph': 'Knowledge Graph',
    'setup': 'Setup',
  },
};

export default function Breadcrumbs() {
  const pathname = usePathname();
  const { language } = useLanguage();
  const labels = language === 'de' ? LABELS.de : LABELS.en;

  const segments = pathname.split('/').filter(Boolean);

  if (segments.length === 0) return null;

  const items = [{ href: '/', label: labels[''] || 'Home' }];
  let accum = '';
  for (const seg of segments) {
    accum += `/${seg}`;
    items.push({ href: accum, label: labels[seg] || seg });
  }

  return (
    <nav aria-label="Breadcrumb" style={{ padding: '0.5rem 1rem', fontSize: '0.78rem', color: 'var(--muted)' }}>
      <ol style={{ listStyle: 'none', display: 'flex', gap: '0.4rem', margin: 0, padding: 0, alignItems: 'center' }}>
        {items.map((item, i) => (
          <li key={item.href} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            {i > 0 && <span style={{ opacity: 0.4 }}>/</span>}
            {i === items.length - 1 ? (
              <span aria-current="page" style={{ color: 'var(--ink)' }}>{item.label}</span>
            ) : (
              <Link href={item.href} style={{ color: 'var(--muted)', textDecoration: 'none', hover: { color: 'var(--brand)' } }}>
                {item.label}
              </Link>
            )}
          </li>
        ))}
        <script type="application/ld+json" dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            '@context': 'https://schema.org',
            '@type': 'BreadcrumbList',
            itemListElement: items.map((item, i) => ({
              '@type': 'ListItem',
              position: i + 1,
              name: item.label,
              item: `${typeof window !== 'undefined' ? window.location.origin : ''}${item.href}`,
            })),
          }),
        }} />
      </ol>
    </nav>
  );
}
