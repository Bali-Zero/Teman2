import React from "react";
import type { Metadata } from "next";
import "@/styles/kbli-r19-wrapper.css";

const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || "https://balizero.com";

export const metadata: Metadata = {
  title: "Zantara AI | KBLI Business Code Guide",
  description:
    "Search and explore Indonesian business classification codes (KBLI 2025). Check foreign ownership rules, required licenses, and PMA eligibility for any business activity.",
  openGraph: {
    title: "Zantara AI | KBLI Business Code Guide",
    description:
      "Describe your business idea in any language — we find the right Indonesian codes, licenses and requirements.",
    url: `${baseUrl}/kbli-explorer`,
  },
  alternates: {
    canonical: `${baseUrl}/kbli-explorer`,
  },
};

function KBLIExplorerJsonLd() {
  const schema = {
    "@context": "https://schema.org",
    "@type": "WebApplication",
    name: "KBLI 2025 Explorer",
    description:
      "Search and explore Indonesian business classification codes (KBLI 2025). Check foreign ownership rules, required licenses, and PMA eligibility for any business activity.",
    url: `${baseUrl}/kbli-explorer`,
    applicationCategory: "BusinessApplication",
    operatingSystem: "Any",
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "IDR",
    },
    provider: {
      "@type": "Organization",
      name: "Bali Zero",
      url: baseUrl,
    },
    featureList: [
      "KBLI 2025 code search",
      "Foreign ownership eligibility check",
      "License requirement lookup",
      "PMA investment rules",
    ],
    inLanguage: ["en", "id"],
  };

  return (
    <script
      id="kbli-explorer-jsonld"
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

export default function KBLIExplorerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div
      data-presentation="r19"
      className="kbli-r19 h-screen w-full bg-[var(--background)] text-[var(--foreground)] overflow-hidden overflow-x-hidden font-sans selection:bg-accent-sand/30 selection:text-accent-sand"
    >
      <KBLIExplorerJsonLd />
      {/* Main Content Layer */}
      <div className="relative z-10 h-full flex flex-col">{children}</div>
    </div>
  );
}
