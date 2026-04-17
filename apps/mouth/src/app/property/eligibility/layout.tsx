import type { Metadata } from "next";
import { NavShell, BZLogo } from "@balizero/core";
import { SessionInit } from "@/components/funnel/SessionInit";

export const metadata: Metadata = {
  title: "Property Eligibility · Bali Zero",
  description:
    "Zoning, struttura legale, tassazione e risk score per immobili in Bali.",
};

export default function PropertyLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex flex-col">
      <NavShell
        logo={<BZLogo variant="full" />}
        items={[
          { label: "Home", href: "https://balizero.com/" },
          { label: "Visa", href: "https://visa.balizero.com/" },
          { label: "KBLI", href: "/kbli" },
          { label: "Tax", href: "https://tax.balizero.com/" },
        ]}
        actions={
          <a
            href="https://wa.me/628213107363"
            className="inline-flex items-center px-3 py-1.5 rounded-md text-xs font-semibold"
            style={{ background: "var(--accent-funnel)", color: "#fff" }}
          >
            WhatsApp
          </a>
        }
      />
      <SessionInit funnel="property" />
      <div className="mx-auto max-w-6xl w-full px-4 pt-14 pb-8 sm:px-6 lg:px-8 flex-1">
        {children}
      </div>
    </div>
  );
}
