import type { Metadata } from 'next';
import { JetBrains_Mono, Inter_Tight } from 'next/font/google';
import './globals.css';

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
});

const interTight = Inter_Tight({
  subsets: ['latin'],
  variable: '--font-display',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'OSINT NEXUS',
  description: 'Sismografo del Potere',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`dark ${jetbrainsMono.variable} ${interTight.variable}`}>
      <body className="bg-[var(--sg-base)] text-[var(--sg-text-primary)] min-h-screen overflow-hidden font-[family-name:var(--font-display)]">
        {children}
      </body>
    </html>
  );
}
