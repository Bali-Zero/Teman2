import type { Metadata } from 'next';
import { League_Spartan, Montserrat } from 'next/font/google';
import '@/styles/globals.css';

const leagueSpartan = League_Spartan({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-spartan',
  weight: ['400', '600', '700', '800', '900'],
});

const montserrat = Montserrat({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-montserrat',
  weight: ['400', '500', '600'],
});

export const metadata: Metadata = {
  title: {
    template: '%s — Bali Zero',
    default: 'Bali Zero — Il libro',
  },
  description:
    "Da CV Bayu Santero (2006) a Bali Zero (2020). 5.000+ clienti. L'unica agenzia AI-first in Indonesia.",
  openGraph: {
    type: 'website',
    siteName: 'Bali Zero',
  },
};

export default function BookLayout({ children }: { children: React.ReactNode }) {
  return (
    <div
      className={`${leagueSpartan.variable} ${montserrat.variable} min-h-screen bg-[#0c0c0e] text-[#edeae4]`}
    >
      {children}
    </div>
  );
}
