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
      minHeight: '100vh', background: '#0f0f12', color: '#e0e0e0', fontFamily: 'sans-serif',
      padding: '2rem', textAlign: 'center',
    }}>
      <h1 style={{ fontSize: '4rem', fontWeight: 800, margin: 0, background: 'linear-gradient(135deg, #6c5ce7, #a29bfe)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>404</h1>
      <p style={{ fontSize: '1.2rem', color: '#888', margin: '1rem 0 2rem' }}>Diese Seite existiert nicht.</p>
      <Link href="/" style={{
        padding: '0.75rem 2rem', borderRadius: '8px', background: '#6c5ce7', color: '#fff',
        textDecoration: 'none', fontWeight: 600,
      }}>Zurück zur Startseite</Link>
    </div>
  );
}
