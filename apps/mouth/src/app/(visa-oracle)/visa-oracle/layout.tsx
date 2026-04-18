import type { Metadata } from "next";
import { NavShell, BZLogo } from "@balizero/core";
import { SessionInit } from "@/components/funnel/SessionInit";
import { ConsentBanner } from "@/components/visa-oracle/ConsentBanner";
import { VisaHeaderWhatsApp } from "@/components/visa-oracle/VisaHeaderWhatsApp";
import { ServiceJsonLd, BreadcrumbJsonLd } from "@/components/seo";

const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || "https://balizero.com";

export const metadata: Metadata = {
  title: "Visa Oracle — What visa do you need for Indonesia?",
  description:
    "AI-powered visa guidance for Indonesia. Free instant answers built on 68,000+ legal documents. KITAS, KITAP, Golden Visa, tourist, business — find your match in 60 seconds.",
  keywords: [
    "indonesia visa",
    "bali visa",
    "kitas indonesia",
    "kitap",
    "golden visa indonesia",
    "visa oracle",
    "indonesia immigration",
    "visa quiz indonesia",
  ],
  openGraph: {
    type: "website",
    locale: "en_US",
    url: `${baseUrl}/visa-oracle`,
    title: "Visa Oracle — AI visa guidance for Indonesia",
    description:
      "Free instant visa recommendations for Indonesia. 60-second quiz, 68,000+ legal documents, expert-verified. Start free, no account required.",
    siteName: "Bali Zero",
    images: [
      {
        url: `${baseUrl}/static/og-image.jpg`,
        width: 1200,
        height: 630,
        alt: "Visa Oracle by Bali Zero",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Visa Oracle — AI visa guidance for Indonesia",
    description:
      "Free instant visa recommendations. 60-second quiz, 68,000+ legal documents.",
    creator: "@balizero",
  },
  alternates: {
    canonical: `${baseUrl}/visa-oracle`,
  },
  robots: {
    index: true,
    follow: true,
  },
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
        actions={<VisaHeaderWhatsApp />}
      />
      <SessionInit funnel="visa" />
      <ServiceJsonLd
        name="Visa Oracle — AI visa guidance for Indonesia"
        description="Free AI-powered visa recommendations for Indonesia built on 68,000+ legal documents. Personalized matches in 60 seconds."
        url="/visa-oracle"
      />
      <BreadcrumbJsonLd
        items={[
          { name: "Home", url: "/" },
          { name: "Visa Oracle", url: "/visa-oracle" },
        ]}
      />
      {/* NavShell is fixed top (h-14) — push content down */}
      <div className="flex-1 max-w-5xl mx-auto w-full px-6 py-8 pt-14">
        {children}
      </div>
      <ConsentBanner />
    </div>
  );
}
