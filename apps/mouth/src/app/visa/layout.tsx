import type { Metadata } from "next";
import { montserrat } from "@balizero/core/fonts/montserrat";
import { NavShell, BZLogo } from "@balizero/core";
import { SessionInit } from "@/components/funnel/SessionInit";
import { HeaderWhatsAppCTA } from "@/components/funnel/HeaderWhatsAppCTA";
import { MobileNav } from "@/app/v2/_components/MobileNav";
import { getFunnelNavItems } from "@/components/funnel/funnel-nav";

export const metadata: Metadata = {
  title: "Bali Visa Eligibility & Selection",
  description:
    "Find the right Indonesia & Bali visa for your stay. Compare C1, D12, E33G, KITAS, and long-term residency options.",
  alternates: {
    canonical: "https://balizero.com/visa",
  },
};

export default function VisaLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const navItems = getFunnelNavItems("visa");

  return (
    <div
      className={`${montserrat.variable} relative z-1`}
      style={{
        fontFamily: "var(--font-montserrat), system-ui, sans-serif",
      }}
    >
      <NavShell
        logo={<BZLogo variant="full" />}
        items={navItems}
        slotAfter={<MobileNav items={navItems} />}
        actions={<HeaderWhatsAppCTA funnel="visa" />}
      />
      <SessionInit funnel="visa" />
      <div className="mx-auto max-w-6xl px-4 pt-14 pb-8 sm:px-6 lg:px-8">
        {children}
      </div>
    </div>
  );
}
