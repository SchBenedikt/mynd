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

export const metadata = {
  title: "MYND - Local-first AI Workspace",
  description: "A local-first AI workspace for chat, knowledge, automation, and integrations",
  icons: { icon: '/favicon.svg' }
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
        <meta httpEquiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; img-src 'self' data: https: http:; connect-src 'self' http://127.0.0.1:* http://localhost:* ws:; font-src 'self' https://cdnjs.cloudflare.com data:;" />
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
