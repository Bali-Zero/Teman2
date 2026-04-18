import type { ReactNode } from "react";

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
