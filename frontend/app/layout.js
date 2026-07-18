import { Space_Grotesk, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import "katex/dist/katex.min.css";
import AuthGate from '../components/AuthGate';
import ErrorBoundary from '../components/ErrorBoundary';
import { AppProvider } from '../lib/AppContext';
import { LanguageProvider } from '../hooks/useLanguage';

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space-grotesk"
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-ibm-plex-mono"
});

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'http://localhost:3000';

export const metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "MYND - Local-first AI Workspace",
    template: "%s | MYND"
  },
  description: "A local-first AI workspace for chat, knowledge, automation, and integrations. Your private AI assistant that understands your documents, emails, and smart home.",
  keywords: ["AI", "workspace", "local-first", "privacy", "chat", "knowledge management", "home automation", "Nextcloud", "Immich", "TrueNAS"],
  authors: [{ name: "MYND" }],
  creator: "MYND",
  publisher: "MYND",
  icons: {
    icon: '/favicon.svg',
    apple: '/favicon.svg',
  },
  openGraph: {
    type: 'website',
    locale: 'de_DE',
    alternateLocale: ['en_US', 'fr_FR', 'es_ES', 'it_IT', 'nl_NL', 'pl_PL', 'pt_BR', 'tr_TR', 'ru_RU', 'ja_JP', 'zh_CN'],
    siteName: 'MYND',
    title: 'MYND - Local-first AI Workspace',
    description: 'A local-first AI workspace for chat, knowledge, automation, and integrations. Your private AI assistant.',
    url: siteUrl,
    images: [{ url: '/og-image.png', width: 1200, height: 630, alt: 'MYND Workspace' }],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'MYND - Local-first AI Workspace',
    description: 'A local-first AI workspace for chat, knowledge, automation, and integrations.',
    images: ['/og-image.png'],
    creator: '@mynd_ai',
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, 'max-video-preview': -1, 'max-image-preview': 'large', 'max-snippet': -1 },
  },
  alternates: {
    canonical: siteUrl,
    languages: {
      'de': `${siteUrl}/language`,
      'en': `${siteUrl}/language`,
    },
  },
  category: 'technology',
};

export default function RootLayout({ children }) {
  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: 'MYND',
    applicationCategory: 'ProductivityApplication',
    operatingSystem: 'macOS, Linux, Windows, Docker',
    description: 'A local-first AI workspace for chat, knowledge, automation, and integrations. Your private AI assistant.',
    url: siteUrl,
    author: { '@type': 'Organization', name: 'MYND' },
    offers: { '@type': 'Offer', price: '0', priceCurrency: 'EUR' },
    featureList: [
      'AI-powered chat with context awareness',
      'Semantic search across documents and photos',
      'Smart home control (Home Assistant)',
      'Nextcloud integration (Calendar, Tasks, Contacts, Files)',
      'Immich photo management',
      'TrueNAS server monitoring',
      'Email management (IMAP/SMTP)',
      'Local-first, privacy focused',
    ],
  };

  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
        <meta httpEquiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; img-src 'self' data: https: http:; connect-src 'self' http: https: ws: wss:; font-src 'self' https://cdnjs.cloudflare.com data:;" />
        <meta name="theme-color" content="#0f0f12" />
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        <link rel="manifest" href="/manifest.json" />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body className={`${spaceGrotesk.variable} ${ibmPlexMono.variable}`}>
        <ErrorBoundary>
          <AuthGate>
            <LanguageProvider>
              <AppProvider>
                {children}
              </AppProvider>
            </LanguageProvider>
          </AuthGate>
        </ErrorBoundary>
      </body>
    </html>
  );
}
