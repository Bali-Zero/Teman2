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
