import type { Metadata } from "next";
import { NavShell, BZLogo } from "@balizero/core";
import { SessionInit } from "@/components/funnel/SessionInit";
import { HeaderWhatsAppCTA } from "@/components/funnel/HeaderWhatsAppCTA";
import { MobileNav } from "@/app/v2/_components/MobileNav";
import { getFunnelNavItems } from "@/components/funnel/funnel-nav";

export const metadata: Metadata = {
  title: "Idoneità Immobile · Bali Zero",
  description:
    "Zoning, struttura legale, tassazione e punteggio di rischio per immobili a Bali.",
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
