import type { Metadata } from "next";
import { NavShell, BZLogo } from "@balizero/core";
import { SessionInit } from "@/components/funnel/SessionInit";
import { HeaderWhatsAppCTA } from "@/components/funnel/HeaderWhatsAppCTA";
import { getFunnelNavItems } from "@/components/funnel/funnel-nav";

export const metadata: Metadata = {
  title: "Tax Compliance Calendar · Bali Zero",
  description: "Deadlines, reminders and compliance for businesses in Bali.",
};

export default function TaxCalendarLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex flex-col">
      <NavShell
        logo={<BZLogo variant="full" />}
        items={getFunnelNavItems("tax")}
        actions={<HeaderWhatsAppCTA funnel="tax" />}
      />
      <SessionInit funnel="tax" />
      <div className="mx-auto max-w-6xl w-full px-4 pt-14 pb-8 sm:px-6 lg:px-8 flex-1">
        {children}
      </div>
    </div>
  );
}
