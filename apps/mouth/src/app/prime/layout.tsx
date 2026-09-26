import type { Metadata } from "next";
import type { ReactNode } from "react";

// Every route under /prime is a prospect-facing tool, not a public landing
// page. On balizero.com (a public host) /prime/* is neither redirected by
// proxy.ts nor disallowed in robots.ts, so /prime/proposal/[token] — which
// renders the investor's name client-side — needs its own noindex. /prime
// itself already had one (page.tsx); the proposal route did not.
// On prime.balizero.com robots.ts disallows the whole host, so crawlers never
// fetch this tag there; it is not a second layer on that host.
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

// PF3a: scoped preconnect to Google Maps origins (prime route only)
export default function PrimeLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <link
        rel="preconnect"
        href="https://maps.googleapis.com"
        crossOrigin="anonymous"
      />
      <link rel="dns-prefetch" href="https://maps.gstatic.com" />
      {children}
    </>
  );
}
