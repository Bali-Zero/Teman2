import type { Metadata } from "next";
import { NavShell, BZLogo } from "@balizero/core";
import { SessionInit } from "@/components/funnel/SessionInit";
import { HeaderWhatsAppCTA } from "@/components/funnel/HeaderWhatsAppCTA";
import { MobileNav } from "@/app/v2/_components/MobileNav";
import { getFunnelNavItems } from "@/components/funnel/funnel-nav";
import { R19Presentation } from "@/components/r19/R19Presentation";

// C1 (gate-7596-report.md v2, REWORK-BUILD): the previous description
// promised legal structure, tax implications and a risk score — none of
// which this report delivers (PR-3, owner decision). Scope stays zoning +
// what may be built + what a buyer can do, same as the on-page lede.
const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || "https://balizero.com";

const DESCRIPTION =
  "Check a Bali plot's zoning, what may be built there and what a buyer like you can do with it — then talk it through with Bali Zero.";

export const metadata: Metadata = {
  description: DESCRIPTION,
  alternates: {
    canonical: "https://balizero.com/property/eligibility",
  },
  // Next.js merges `openGraph` shallowly: this object replaces the root one,
  // so it restates type/url/siteName/images like (blog)/contact/layout.tsx.
  openGraph: {
    type: "website",
    locale: "en_US",
    url: `${baseUrl}/property/eligibility`,
    title: "Property Eligibility Check — Bali Zoning & Buyer Eligibility",
    description: DESCRIPTION,
    siteName: "Bali Zero",
    images: [
      {
        url: `${baseUrl}/static/og-image.jpg`,
        width: 1200,
        height: 630,
        alt: "Bali Zero Property Check",
      },
    ],
  },
};

export default function PropertyLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const navItems = getFunnelNavItems("property");

  // Rebuilt on R19 2026-09-28 (owner decision): this is one of the 4 L1
  // funnel tools, so it keeps its own cross-funnel NavShell (not BlogNav) —
  // `R19Presentation` supplies the paper/copper CSS vars, `variant="paper"`
  // matches BlogNav's own R19 nav styling (app/(blog)/_components/BlogNav.tsx).
  return (
    <R19Presentation>
      <div className="min-h-screen flex flex-col">
        <NavShell
          variant="paper"
          logo={<BZLogo variant="full" />}
          items={navItems}
          slotAfter={<MobileNav items={navItems} funnel="property" />}
          actions={<HeaderWhatsAppCTA funnel="property" />}
        />
        <SessionInit funnel="property" />
        <div
          className="mx-auto max-w-6xl w-full px-4 pb-8 sm:px-6 lg:px-8 flex-1"
          style={{ paddingTop: "var(--public-header-height, 56px)" }}
        >
          {children}
        </div>
      </div>
    </R19Presentation>
  );
}
