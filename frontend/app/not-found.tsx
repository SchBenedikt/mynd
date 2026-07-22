import Link from 'next/link';

export const metadata = {
  title: '404 - Seite nicht gefunden',
  description: 'Die angeforderte Seite existiert nicht.',
  robots: { index: false },
};

export default function NotFound() {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      minHeight: '100vh', background: '#090a0e', color: '#e0e0e0', fontFamily: 'system-ui, sans-serif',
      padding: '2rem', textAlign: 'center', position: 'relative', overflow: 'hidden',
    }}>
      <div style={{
        position: 'absolute', top: '-20%', left: '50%', transform: 'translateX(-50%)',
        width: '500px', height: '500px', background: 'radial-gradient(circle, #91a0ff 0%, transparent 70%)',
        opacity: '0.05', pointerEvents: 'none',
      }} />
      <div style={{
        width: '64px', height: '64px', display: 'grid', placeItems: 'center',
        border: '2px solid #91a0ff', transform: 'rotate(45deg)', marginBottom: '2rem',
      }}>
        <div style={{ width: '16px', height: '16px', background: '#91a0ff' }} />
      </div>
      <h1 style={{
        fontSize: '5rem', fontWeight: 800, margin: 0,
        background: 'linear-gradient(135deg, #91a0ff, #b8c2ff)',
        WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
        lineHeight: 1.1,
      }}>404</h1>
      <p style={{ fontSize: '1.1rem', color: '#9298a8', margin: '0.75rem 0 2rem', maxWidth: '360px' }}>
        Diese Seite existiert nicht.
      </p>
      <Link href="/" style={{
        display: 'inline-flex', alignItems: 'center', gap: '0.5rem',
        padding: '0.75rem 2rem', border: '1px solid #7185ff',
        background: '#7185ff', color: '#fff', textDecoration: 'none',
        fontWeight: 600, fontSize: '0.9rem',
        transition: 'background 0.2s, box-shadow 0.2s',
      }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <line x1="19" y1="12" x2="5" y2="12" />
          <polyline points="12 19 5 12 12 5" />
        </svg>
        Zurück zur Startseite
      </Link>
    </div>
  );
}
