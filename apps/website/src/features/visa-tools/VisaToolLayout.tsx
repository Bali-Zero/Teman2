import type { ReactNode } from "react";
import { SiteShell } from "../../components/SiteShell";
import "./visa-tools.css";
export function VisaToolLayout({ children }: { children: ReactNode }) {
  return (
    <SiteShell
      context={{ label: "Visa & immigration", href: "/services/visa" }}
    >
      <main id="main-content" className="visa-tools">
        <nav className="visa-tool-nav" aria-label="Visa tools">
          <a href="/visa-oracle">Visa Oracle</a>
          <a href="/visa/voa">Visa on Arrival</a>
          <a href="/visa/clock">Visa Clock</a>
          <a href="/visa/match">Visa Match</a>
          <a href="/visa/second-home">Second Home</a>
        </nav>
        {children}
      </main>
    </SiteShell>
  );
}
