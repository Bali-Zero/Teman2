import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'OSINT NEXUS',
  description: 'Sismografo del Potere',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#1d273b] text-[#ececec] min-h-screen overflow-hidden">
        {children}
      </body>
    </html>
  );
}
