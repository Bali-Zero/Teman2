import type { ReactNode } from "react";

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
