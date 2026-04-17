import type { Metadata } from "next";
import { NavShell } from "@balizero/core/components/NavShell";
import { BZLogo } from "@balizero/core/components/BZLogo";
import { MobileNav } from "../v2/_components/MobileNav";
import { HeroBlueprint } from "../v2/_components/HeroBlueprint";
import { SocialProof } from "../v2/_components/SocialProof";
import { FunnelFeature } from "../v2/_components/FunnelFeature";
import { NewsHero } from "../v2/_components/NewsHero";
import { TopicPills } from "../v2/_components/TopicPills";
import { LatestNews } from "../v2/_components/LatestNews";
import { Footer } from "../v2/_components/Footer";
import { ZantaraFAB } from "../v2/_components/ZantaraFAB";

export const metadata: Metadata = {
  title: {
    absolute: "Bali Zero | #1 Visa & PT PMA Experts in Bali, Indonesia",
  },
  description:
    "Indonesia's AI-powered visa agency. KITAS, KITAP, Golden Visa, PT PMA company setup, tax compliance. 24/7 AI assistant. Trusted by 5000+ clients since 2020.",
  alternates: {
    canonical: "https://balizero.com",
  },
  openGraph: {
    title: "Bali Zero | #1 Visa & PT PMA Experts in Bali, Indonesia",
    description:
      "Indonesia's AI-powered visa agency. KITAS, KITAP, Golden Visa, PT PMA company setup, tax compliance. 24/7 AI assistant. Trusted by 5000+ clients.",
    url: "https://balizero.com",
  },
};

const NAV_ITEMS = [
  { label: "Home", href: "#top" },
  { label: "Visa", href: "#visa" },
  { label: "Business", href: "#kbli" },
  { label: "Tax", href: "#tax" },
  { label: "Property", href: "#property" },
  { label: "News", href: "#news" },
];

export default function HomePage() {
  return (
    <div
      id="top"
      style={{
        background: "var(--surface-base)",
        color: "var(--text-primary)",
        minHeight: "100vh",
      }}
    >
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
        <LatestNews />
      </main>
      <Footer />
      <ZantaraFAB />
    </div>
  );
}
