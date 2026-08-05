import type { Metadata } from "next";
import { NavShell, BZLogo } from "@balizero/core";
import { SessionInit } from "@/components/funnel/SessionInit";
import { HeaderWhatsAppCTA } from "@/components/funnel/HeaderWhatsAppCTA";
import { MobileNav } from "@/app/v2/_components/MobileNav";
import { getFunnelNavItems } from "@/components/funnel/funnel-nav";

export const metadata: Metadata = {
  title: "Property Eligibility Check — Bali Zoning & Legal Structure",
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

  return (
    <div className="min-h-screen flex flex-col">
      <NavShell
        logo={<BZLogo variant="full" />}
        items={navItems}
        slotAfter={<MobileNav items={navItems} />}
        actions={<HeaderWhatsAppCTA funnel="property" />}
      />
      <SessionInit funnel="property" />
      <div className="mx-auto max-w-6xl w-full px-4 pt-14 pb-8 sm:px-6 lg:px-8 flex-1">
        {children}
      </div>
    </div>
  );
}
