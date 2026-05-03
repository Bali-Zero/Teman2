import type { KBLICode } from "@/lib/kbli-types";

export function KBLICodeJsonLd({ code }: { code: KBLICode }) {
  const pmaLabel =
    code.pma.status === "open"
      ? `100% foreign ownership allowed (TERBUKA)`
      : code.pma.status === "restricted"
        ? `Restricted to max ${code.pma.maxForeign}% foreign ownership (TERBATAS)`
        : "Closed to foreign investment (TERTUTUP)";

  const riskLevel: string = code.licensing[0]?.riskCategory ?? "Unknown";
  const licenseType = code.licensing[0]?.licenseType ?? "NIB";

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    name: `KBLI ${code.code} — ${code.titleId}`,
    headline: `KBLI ${code.code}: ${code.titleId} — Indonesian Business Code Guide`,
    description: `${code.description.slice(0, 160)}. ${pmaLabel}. Risk: ${riskLevel}.`,
    inLanguage: "en",
    datePublished: "2025-06-18",
    dateModified: new Date().toISOString().split("T")[0],
    author: {
      "@type": "Organization",
      name: "Bali Zero",
      url: "https://balizero.com",
    },
    publisher: {
      "@type": "Organization",
      name: "Bali Zero",
      url: "https://balizero.com",
      logo: {
        "@type": "ImageObject",
        url: "https://balizero.com/static/balizero-logo-clean.png",
      },
    },
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": `https://balizero.com/kbli/${code.code}`,
    },
    isPartOf: {
      "@type": "WebPage",
      "@id": "https://balizero.com/kbli",
      name: "KBLI 2025 Navigator — Indonesian Business Classification",
    },
    keywords: [
      `KBLI ${code.code}`,
      code.titleId,
      code.titleEn,
      "KBLI 2025",
      "Indonesian business license",
      code.pma.status === "open" ? "PT PMA" : undefined,
      riskLevel !== "Unknown" ? `${riskLevel} risk` : undefined,
      code.section ? `Section ${code.section}` : undefined,
    ]
      .filter(Boolean)
      .join(", "),
    about: {
      "@type": "GovernmentService",
      name: `KBLI ${code.code} — ${code.titleId}`,
      description: `${code.titleEn}. ${pmaLabel}. License: ${licenseType}. Risk level: ${riskLevel}.`,
      serviceType: "Business Classification",
      jurisdiction: {
        "@type": "AdministrativeArea",
        name: "Indonesia",
      },
      provider: {
        "@type": "GovernmentOrganization",
        name: "Badan Pusat Statistik (BPS)",
        url: "https://bps.go.id",
      },
      isRelatedTo: {
        "@type": "GovernmentOrganization",
        name: "BKPM (Investment Coordinating Board)",
        url: "https://bkpm.go.id",
      },
    },
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
    />
  );
}

export function KBLIFaqJsonLd({ code }: { code: KBLICode }) {
  const pmaAnswer =
    code.pma.status === "open"
      ? `Yes. KBLI ${code.code} (${code.titleId}) is TERBUKA — open to 100% foreign ownership via PT PMA. No local Indonesian partner required.`
      : code.pma.status === "restricted"
        ? `Partially. KBLI ${code.code} is TERBATAS — foreign ownership capped at ${code.pma.maxForeign}%.${code.pma.condition ? ` Condition: ${code.pma.condition}` : ""} An Indonesian partner holds the remaining shares.`
        : `No. KBLI ${code.code} (${code.titleId}) is TERTUTUP — closed to foreign investment. Reserved for Indonesian nationals only.`;

  const licenseAnswer =
    code.licensing.length > 0
      ? `KBLI ${code.code} has a ${code.licensing[0].riskCategory} risk classification. Required license: ${code.licensing[0].licenseType ?? "NIB (Nomor Induk Berusaha)"}. ${code.licensing[0].timeframe ? `Processing time: ${code.licensing[0].timeframe}.` : "Processed through OSS (Online Single Submission)."}`
      : `KBLI ${code.code} requires a NIB (Nomor Induk Berusaha) via OSS (Online Single Submission). Contact a licensed consultant for specific requirements.`;

  const questions: { question: string; answer: string }[] = [
    {
      question: `Can foreigners operate a ${code.titleEn.toLowerCase()} business in Indonesia?`,
      answer: pmaAnswer,
    },
    {
      question: `What license is required for KBLI ${code.code}?`,
      answer: licenseAnswer,
    },
    {
      question: `What is KBLI ${code.code}?`,
      answer: `KBLI ${code.code} is the Indonesian business classification code for "${code.titleId}" (${code.titleEn}). It falls under Section ${code.section ?? "N/A"} of KBLI 2025, the Indonesian Standard Industrial Classification updated by BPS (Regulation 7/2025), effective June 18, 2026.`,
    },
  ];

  if (code.transition.previousCodes.length > 0) {
    questions.push({
      question: `How did KBLI ${code.code} change from KBLI 2020 to 2025?`,
      answer: `KBLI ${code.code} was mapped from previous code${code.transition.previousCodes.length > 1 ? "s" : ""} ${code.transition.previousCodes.join(", ")} (KBLI 2020).${code.transition.mappingNote ? ` ${code.transition.mappingNote}` : ""} All businesses must migrate to KBLI 2025 by June 18, 2026 per BPS Regulation 7/2025.`,
    });
  }

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: questions.map((q) => ({
      "@type": "Question",
      name: q.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: q.answer,
      },
    })),
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
    />
  );
}

export function KBLIBreadcrumbJsonLd({
  items,
}: {
  items: { name: string; url: string }[];
}) {
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: items.map((item, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: item.name,
      item: item.url,
    })),
  };

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
    />
  );
}
