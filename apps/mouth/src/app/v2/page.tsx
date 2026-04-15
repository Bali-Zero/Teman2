import type { Metadata } from "next";
import { NavShell } from "@balizero/core/components/NavShell";
import { BZLogo } from "@balizero/core/components/BZLogo";
import { BrandEntrance } from "./_components/BrandEntrance";
import { HeroCarousel } from "./_components/HeroCarousel";
import { FunnelBoxes } from "./_components/FunnelBoxes";
import { ServicesPricing } from "./_components/ServicesPricing";
import { ZantaraFAB } from "./_components/ZantaraFAB";

// Phase 1 reference homepage. Not the production '/' route — that stays on the
// legacy design until cutover. This page validates the DS end-to-end on a real
// (non-public) URL so we can stress-test the system before swapping main route.
export const metadata: Metadata = {
  title: "Bali Zero v2 · Design System Preview",
  robots: { index: false, follow: false },
};

const NAV_ITEMS = [
  { label: "Services", href: "#services" },
  { label: "Visa Oracle", href: "#visa" },
  { label: "KBLI", href: "#kbli" },
  { label: "Tax", href: "#tax" },
  { label: "Property", href: "#property" },
];

export default function HomeV2() {
  return (
    <div style={{ background: "var(--surface-base)", color: "var(--text-primary)", minHeight: "100vh" }}>
      <NavShell
        logo={<BZLogo variant="mark" size={22} />}
        items={NAV_ITEMS}
        actions={
          <>
            <button
              className="px-4 py-1.5 rounded-md text-[11px] font-semibold uppercase tracking-wide"
              style={{
                background: "var(--surface-raised)",
                color: "var(--text-secondary)",
                border: "1px solid var(--border-default)",
              }}
            >
              Login
            </button>
            <button
              className="px-4 py-1.5 rounded-md text-[11px] font-semibold uppercase tracking-wide"
              style={{
                background: "var(--accent-funnel)",
                color: "var(--text-on-accent)",
              }}
            >
              Get Started
            </button>
          </>
        }
      />
      <BrandEntrance />
      <HeroCarousel />
      <FunnelBoxes />
      <ServicesPricing />
      <ZantaraFAB />
    </div>
  );
}
