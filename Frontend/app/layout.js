import { Space_Grotesk, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

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
  title: "NextMind",
  description: "Next.js UI fuer deine lokale AI-Anwendung"
};

export default function RootLayout({ children }) {
  return (
    <html lang="de">
      <body className={`${spaceGrotesk.variable} ${ibmPlexMono.variable}`} data-theme="classic">
        {children}
      </body>
    </html>
  );
}
