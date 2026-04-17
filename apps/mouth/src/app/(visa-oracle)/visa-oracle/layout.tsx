import type { Metadata } from "next";
import { NavShell, BZLogo } from "@balizero/core";
import { SessionInit } from "@/components/funnel/SessionInit";
import { ConsentBanner } from "@/components/visa-oracle/ConsentBanner";

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
        items={[
          { label: "Home", href: "https://balizero.com/" },
          { label: "KBLI", href: "/kbli" },
          { label: "Tax", href: "https://tax.balizero.com/" },
        ]}
        actions={
          <a
            href="https://wa.me/628213107363"
            className="inline-flex items-center px-3 py-1.5 rounded-md text-xs font-semibold"
            style={{ background: "var(--bz-accent)", color: "#fff" }}
          >
            WhatsApp
          </a>
        }
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
