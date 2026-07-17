import type { KBLICode } from "@/lib/kbli-types";
import { buildKbliFaq } from "@/lib/kbli-faq";

export function KBLICodeJsonLd({
  code,
  dateModified,
}: {
  code: KBLICode;
  // Real dataset modification date (file mtime, same source as the sitemap
  // lastmod). Rendering-time `new Date()` claimed "modified today" on every
  // build — a fabricated freshness signal Google learns to distrust.
  dateModified?: Date;
}) {
  // National PMA openness != Bali registrability. When a code is nationally open
  // but l4_bali.blocked, the SEO/JSON-LD must NOT tell Google "100% foreign
  // ownership allowed" unqualified — it would surface in rich results / AI answers
  // as a green light that is false for a Bali setup.
  const baliBlocked = !!code.baliL4?.blocked;
  // GARUDA-FILIERA Fase-1 cure #4 (2026-07-17): a code whose Bali risk tier
  // was carried over from a different activity (code-number collision) is
  // neither blocked nor confirmed open — don't let Google/AI answers read
  // it as an unqualified "100% foreign ownership allowed" green light.
  const baliNonClassifiable = code.baliL4?.status === "NON_CLASSIFICABILE";
  const baliNat = baliBlocked
    ? " nationally — but blocked for a PT PMA in Bali"
    : baliNonClassifiable
      ? " nationally — Bali PMA applicability not yet classifiable, verify with the team"
      : "";
  const pmaLabel =
    code.pma.status === "open"
      ? `100% foreign ownership allowed (TERBUKA)${baliNat}`
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
    ...(dateModified
      ? { dateModified: dateModified.toISOString().split("T")[0] }
      : {}),
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
      // avoid repeating the Indonesian title when no distinct English title exists
      code.titleEn !== code.titleId ? code.titleEn : undefined,
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
  // Questions and answers come from buildKbliFaq — the SAME source that
  // renders the visible Common Questions section, so the FAQPage markup
  // always has matching on-page content (Google requires it).
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: buildKbliFaq(code).map((q) => ({
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
