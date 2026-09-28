import type { Metadata } from "next";
import { NavShell, BZLogo } from "@balizero/core";
import { SessionInit } from "@/components/funnel/SessionInit";
import { HeaderWhatsAppCTA } from "@/components/funnel/HeaderWhatsAppCTA";
import { MobileNav } from "@/app/v2/_components/MobileNav";
import { getFunnelNavItems } from "@/components/funnel/funnel-nav";
import { R19Presentation } from "@/components/r19/R19Presentation";

export const metadata: Metadata = {
  description:
    "Check if a Bali property is eligible for foreign ownership. Get zoning analysis, legal structure (Hak Pakai / HGB via PMA), tax implications, and risk score.",
  alternates: {
    canonical: "https://balizero.com/property/eligibility",
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
        <div className="mx-auto max-w-6xl w-full px-4 pt-14 pb-8 sm:px-6 lg:px-8 flex-1">
          {children}
        </div>
      </div>
    </R19Presentation>
  );
}
