import type { Metadata } from "next";
import { NavShell, BZLogo } from "@balizero/core";
import { SessionInit } from "@/components/funnel/SessionInit";
import { HeaderWhatsAppCTA } from "@/components/funnel/HeaderWhatsAppCTA";
import { MobileNav } from "@/app/v2/_components/MobileNav";
import { getFunnelNavItems } from "@/components/funnel/funnel-nav";
import { R19Presentation } from "@/components/r19/R19Presentation";

export const metadata: Metadata = {
  title: "Tax Compliance Calendar",
  description: "Deadlines, reminders and compliance for businesses in Bali.",
};

export default function TaxCalendarLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const navItems = getFunnelNavItems("tax");

  return (
    <R19Presentation force>
      <div className="min-h-screen flex flex-col">
        <NavShell
          variant="paper"
          logo={<BZLogo variant="full" />}
          items={navItems}
          slotAfter={<MobileNav items={navItems} funnel="tax" />}
          actions={<HeaderWhatsAppCTA funnel="tax" />}
        />
        <SessionInit funnel="tax" />
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
