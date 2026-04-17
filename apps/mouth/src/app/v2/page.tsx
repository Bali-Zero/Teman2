import type { Metadata } from "next";
import { NavShell } from "@balizero/core/components/NavShell";
import { BZLogo } from "@balizero/core/components/BZLogo";
import { SessionInit } from "@/components/funnel/SessionInit";
import { MobileNav } from "./_components/MobileNav";
import { HeroBlueprint } from "./_components/HeroBlueprint";
import { SocialProof } from "./_components/SocialProof";
import { TopicPills } from "./_components/TopicPills";
import { FunnelFeature } from "./_components/FunnelFeature";
import { NewsHero } from "./_components/NewsHero";
import { LatestNews } from "./_components/LatestNews";
import { Footer } from "./_components/Footer";
import { ZantaraFAB } from "./_components/ZantaraFAB";

// Phase 1 reference homepage — "safe" palette variant (#0B0B10 night).
// Compare with /v2-aubergine which uses the contrarian #1A1520.
export const metadata: Metadata = {
  title: "Bali Zero v2 · Design System Preview",
  robots: { index: false, follow: false },
};

const NAV_ITEMS = [
  { label: "Home", href: "#top" },
  { label: "Visa", href: "#visa" },
  { label: "Business", href: "#kbli" },
  { label: "Tax", href: "#tax" },
  { label: "Property", href: "#property" },
  { label: "News", href: "#news" },
];

export default function HomeV2() {
  return (
    <div
      id="top"
      style={{
        background: "var(--surface-base)",
        color: "var(--text-primary)",
        minHeight: "100vh",
      }}
    >
      <SessionInit funnel="home" />
      <NavShell
        logo={<BZLogo variant="full" size={36} priority />}
        items={NAV_ITEMS}
        slotAfter={<MobileNav items={NAV_ITEMS} />}
        actions={
          <>
            <button
              className="px-4 py-1.5 rounded-md text-[11px] font-semibold uppercase tracking-wide"
              style={{
                background: "transparent",
                color: "var(--text-secondary)",
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
      <main id="main-content">
        <HeroBlueprint />
        <SocialProof />
        <FunnelFeature funnel="visa" layout="full" />
        <FunnelFeature funnel="kbli" layout="full" />
        <FunnelFeature funnel="tax" layout="full" />
        <FunnelFeature funnel="property" layout="full" />
        <NewsHero />
        <TopicPills />
        <LatestNews articles={[]} />
      </main>
      <Footer />
      <ZantaraFAB />
    </div>
  );
}
