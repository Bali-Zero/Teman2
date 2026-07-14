import type { Metadata } from "next";
import { NavShell } from "@balizero/core/components/NavShell";
import { BZLogo } from "@balizero/core/components/BZLogo";
import { SessionInit } from "@/components/funnel/SessionInit";
import { MobileNav } from "../v2/_components/MobileNav";
import { HeroBlueprint } from "../v2/_components/HeroBlueprint";
import { PersonaDoors } from "../v2/_components/PersonaDoors";
import { NavWhatsAppCTA } from "../v2/_components/NavWhatsAppCTA";
import { SocialProof } from "../v2/_components/SocialProof";
import { TopicPills } from "../v2/_components/TopicPills";
import { NewsHero } from "../v2/_components/NewsHero";
import { LatestNews } from "../v2/_components/LatestNews";
import { Footer } from "../v2/_components/Footer";
import { ZantaraFAB } from "../v2/_components/ZantaraFAB";
import { getAllArticles } from "@/lib/blog/articles";
import homepageLayout from "@/content/homepage-layout.json";
import { RUMAH_VARS, MASTHEAD_VARS } from "@/lib/theme/rumahVars";

export const dynamic = "force-dynamic";

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

const LATEST_NEWS_COUNT = 5;

// In-page anchors preserved: #visa/#kbli/#tax/#property now resolve to the
// persona-door cards (B2R2 — the chips strip is gone, tool identities live
// inside the doors); #news to NewsHero.
const NAV_ITEMS = [
  { label: "Visa", href: "/services/visa" },
  { label: "Business", href: "/services/company" },
  { label: "Tax", href: "/services/tax" },
  { label: "Property", href: "/services/property" },
  { label: "News", href: "/news" },
];

export default async function HomePage() {
  const { articles } = await getAllArticles({});
  const layout = homepageLayout as Record<string, string>;
  const heroSlugs = new Set(
    ["hero_main", "hero_2", "hero_3", "hero_4", "hero_5"]
      .map((k) => layout[k])
      .filter(Boolean),
  );
  const heroArticles = ["hero_main", "hero_2", "hero_3", "hero_4", "hero_5"]
    .map((k) => articles.find((a) => a.slug === layout[k]))
    .filter(Boolean) as typeof articles;
  const preferred = ["latest_1", "latest_2", "latest_3", "latest_4", "latest_5"]
    .map((k) => articles.find((a) => a.slug === layout[k]))
    .filter(Boolean) as typeof articles;
  const fallback = articles.filter((a) => !heroSlugs.has(a.slug));
  const latest = (
    preferred.length >= LATEST_NEWS_COUNT ? preferred : fallback
  ).slice(0, LATEST_NEWS_COUNT);

  return (
    <div
      id="top"
      style={{
        // Page canvas is Rumah Putih paper — sections paint their own
        // backgrounds; this guards against dark flashes between them.
        background: "#f7f6f2",
        color: "var(--text-primary)",
        minHeight: "100vh",
        ...MASTHEAD_VARS,
      }}
    >
      <SessionInit funnel="home" />
      <NavShell
        logo={<BZLogo variant="full" size={36} priority />}
        items={NAV_ITEMS}
        slotAfter={<MobileNav items={NAV_ITEMS} />}
        accentBar
        actions={
          <>
            <a
              href="https://kita.balizero.com/"
              className="px-4 py-1.5 rounded-md text-[11px] font-semibold uppercase tracking-wide"
              style={{
                background: "transparent",
                color: "var(--text-secondary)",
                textDecoration: "none",
              }}
            >
              Login
            </a>
            {/* Subhi's WhatsApp CTA — #1216 tracking island
                (home_whatsapp_cta, trigger: nav). The previous inline copy
                of this anchor had no onClick (server component); routing it
                through the island restores the #1216 instrumentation.
                P2: WhatsApp-green channel accent — red stays reserved for
                the hero primary. */}
            <NavWhatsAppCTA variant="whatsapp" />
          </>
        }
      />
      <main id="main-content" style={RUMAH_VARS}>
        <HeroBlueprint />
        {/* MYTHOS B2R2: four persona doors (IA-1) are the navigation layer;
            each door carries its tool identity (ex-FunnelChips, strip
            removed per Antonello 2026-06-11). */}
        <PersonaDoors />
        <SocialProof />
        <NewsHero articles={heroArticles} />
        <TopicPills />
        <LatestNews articles={latest} />
      </main>
      <Footer />
      <ZantaraFAB />
    </div>
  );
}
