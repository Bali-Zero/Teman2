import type { Metadata, Viewport } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
};

export const metadata: Metadata = {
  metadataBase: new URL('http://localhost:3000'), // Replace with actual production URL when deploying
  title: {
    default: 'Zantara | Bali Zero Team',
    template: '%s | Zantara',
  },
  description: 'AI-powered team assistant for Bali Zero. Intelligent business operating system.',
  keywords: ['AI', 'Assistant', 'Bali Zero', 'Productivity', 'RAG', 'Business OS'],
  authors: [{ name: 'Bali Zero Team' }],
  creator: 'Bali Zero',
  publisher: 'Bali Zero',
  icons: {
    icon: '/images/logo_zan.png',
    apple: '/images/logo_zan.png',
  },
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: 'https://nuzantara-rag.fly.dev',
    title: 'Zantara | Bali Zero Team',
    description: 'AI-powered team assistant for Bali Zero',
    siteName: 'Zantara',
    images: [
      {
        url: '/images/logo_zan.png',
        width: 800,
        height: 600,
        alt: 'Zantara Logo',
      },
    ],
  },
  robots: {
    index: false,
    follow: false,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-[var(--background)] text-[var(--foreground)]`}
      >
        {children}
      </body>
    </html>
  );
}
