import React from "react";
import type { Metadata } from "next";

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
    <div className="h-screen w-full bg-[#050507] text-silver overflow-hidden overflow-x-hidden font-sans selection:bg-accent-sand/30 selection:text-accent-sand">
      <KBLIExplorerJsonLd />
      {/* Texture Layer: Noise/Grain for tactile feel */}
      <div
        className="fixed inset-0 z-0 opacity-[0.03] pointer-events-none mix-blend-overlay"
        style={{
          backgroundImage:
            'url("https://grainy-gradients.vercel.app/noise.svg")',
        }}
      />

      {/* Ambient Lighting: Subtle, deep, atmospheric */}
      <div className="fixed top-0 left-0 w-full h-full pointer-events-none z-0">
        <div className="absolute top-[-10%] left-[20%] w-[40%] h-[40%] bg-accent-sand/5 rounded-full blur-[150px]" />
        <div className="absolute bottom-[-10%] right-[10%] w-[30%] h-[40%] bg-[#2A3241]/10 rounded-full blur-[120px]" />
      </div>

      {/* Main Content Layer */}
      <div className="relative z-10 h-full flex flex-col">{children}</div>
    </div>
  );
}
