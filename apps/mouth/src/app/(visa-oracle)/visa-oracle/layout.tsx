import type { Metadata } from "next";
import { NavShell, BZLogo } from "@balizero/core";
import { SessionInit } from "@/components/funnel/SessionInit";
import { HeaderWhatsAppCTA } from "@/components/funnel/HeaderWhatsAppCTA";
import { getFunnelNavItems } from "@/components/funnel/funnel-nav";
import { ConsentBanner } from "@/components/visa/ConsentBanner";

export const metadata: Metadata = {
  title: "Visa Oracle — What visa do you need for Indonesia?",
  description:
    "AI-powered visa guidance for Indonesia. Get instant, accurate answers about Indonesian visas built on 68,000+ legal documents.",
};

export default function VisaOracleLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div
      className="min-h-screen flex flex-col"
      style={{
        backgroundColor: "var(--bz-base)",
        color: "var(--tx-primary)",
      }}
    >
      <NavShell
        logo={<BZLogo variant="full" />}
        items={getFunnelNavItems("visa")}
        actions={<HeaderWhatsAppCTA funnel="visa" />}
      />
      <SessionInit funnel="visa" />
      {/* NavShell is fixed top (h-14) — push content down */}
      <div className="flex-1 max-w-5xl mx-auto w-full px-6 py-8 pt-14">
        {children}
      </div>
      <ConsentBanner />
    </div>
  );
}
