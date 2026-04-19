import type { Metadata } from "next";
import { NavShell } from "@balizero/core/components/NavShell";
import { BZLogo } from "@balizero/core/components/BZLogo";
import { SessionInit } from "@/components/funnel/SessionInit";
import { buildWhatsAppLink } from "@/lib/whatsapp-utm";
import { MobileNav } from "./_components/MobileNav";
import { HeroBlueprint } from "./_components/HeroBlueprint";
import { SocialProof } from "./_components/SocialProof";
import { TopicPills } from "./_components/TopicPills";
import { FunnelFeature } from "./_components/FunnelFeature";
import { NewsHero } from "./_components/NewsHero";
import { LatestNews } from "./_components/LatestNews";
import { Footer } from "./_components/Footer";
import { ZantaraFAB } from "./_components/ZantaraFAB";
import { getAllArticles } from "@/lib/blog/articles";
import homepageLayout from "@/content/homepage-layout.json";

export const dynamic = "force-dynamic";

// Phase 1 reference homepage — "safe" palette variant (#0B0B10 night).
// Compare with /v2-aubergine which uses the contrarian #1A1520.
export const metadata: Metadata = {
  title: "Bali Zero v2 · Design System Preview",
  robots: { index: false, follow: false },
};

const LATEST_NEWS_COUNT = 5;

const NAV_ITEMS = [
  { label: "Home", href: "#top" },
  { label: "Visa", href: "#visa" },
  { label: "Business", href: "#kbli" },
  { label: "Tax", href: "#tax" },
  { label: "Property", href: "#property" },
  { label: "News", href: "#news" },
];

export default async function HomeV2() {
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
            <a
              href={buildWhatsAppLink("home")}
              target="_blank"
              rel="noopener noreferrer"
              className="px-4 py-1.5 rounded-md text-[11px] font-semibold uppercase tracking-wide"
              style={{
                background: "var(--accent-funnel)",
                color: "var(--text-on-accent)",
                textDecoration: "none",
              }}
            >
              Get Started
            </a>
          </>
        }
      />
      <main id="main-content">
        <HeroBlueprint />
        <FunnelFeature funnel="visa" layout="full" />
        <FunnelFeature funnel="kbli" layout="full" />
        <FunnelFeature funnel="tax" layout="full" />
        <FunnelFeature funnel="property" layout="full" />
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
