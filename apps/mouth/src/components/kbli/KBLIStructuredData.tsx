import type { KBLICode } from "@/lib/kbli-types";
import { buildKbliFaq } from "@/lib/kbli-faq";
import {
  isLicensingVerificationPending,
  isPmaVerdictVerified,
} from "@/lib/kbli-provenance";
import {
  formatPmaOwnership,
  hasPublishablePmaCap,
} from "@/lib/kbli-pma-disclosure";
import { riskLabelEn } from "@/lib/kbli-derive";
import { pmaCapShape } from "@/lib/kbli-pma-shape";
import { pmaSourceAttributionStructured } from "@/lib/kbli-pma-source";

/**
 * JSON-LD keeps its search-oriented verified wording, but cap availability is
 * decided only by the shared exact gate. Every unavailable shape therefore
 * inherits the same explicit qualifier as visible and metadata surfaces.
 */
function structuredPmaOwnership(code: KBLICode): string {
  const shared = formatPmaOwnership(code.pma, "metadata");
  if (!hasPublishablePmaCap(code.pma)) return shared;

  if (code.pma.status === "open" && code.pma.maxForeign === 100) {
    return "100% foreign ownership allowed";
  }
  if (code.pma.status !== "restricted") return shared;
  if (code.pma.capSpecial && code.pma.maxForeign === "special") {
    return "Restricted by special non-percentage conditions";
  }

  switch (pmaCapShape(code.pma)) {
    case "none":
      return "Closed to foreign ownership in practice — 0% ceiling";
    case "full":
    case "conditional":
      return "Restricted by conditions rather than an ownership ceiling";
    default:
      return `Restricted to max ${code.pma.maxForeign}% foreign ownership`;
  }
}

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
  const baliBlocked = code.baliL4?.blocked === true;
  // GARUDA-FILIERA Fase-1 cure #4 (2026-07-17): a code whose Bali risk tier
  // was carried over from a different activity (code-number collision) is
  // neither blocked nor confirmed open — don't let Google/AI answers read
  // it as an unqualified "100% foreign ownership allowed" green light.
  const baliNonClassifiable = code.baliL4?.status === "NON_CLASSIFICABILE";
  const pmaVerdictVerified = isPmaVerdictVerified(code);
  const baliNat = baliBlocked
    ? " nationally — but blocked for a PT PMA in Bali"
    : baliNonClassifiable
      ? " nationally — Bali PMA applicability not yet classifiable, verify with the team"
      : "";
  // PMA source attribution with vintage (FATAL-2 axis): cite the in-force
  // annexes and their pending KBLI-2025 crosswalk instead of bare fact.
  //
  // The attribution is DERIVED, not fixed. "Crosswalk to KBLI 2025 pending" tells a
  // reader — and Google, and every AI answer built on this JSON-LD — that a basis
  // exists and only the mapping is unfinished. That is true only for codes with
  // an authoritative BPS-recorded KBLI-2020 origin. If a future or defensive
  // input records none, there is nothing to crosswalk from and the same sentence
  // would overstate what we can show. The current canonical has no such gap.
  // Source-aware (kbli-pma-source.ts, shared with kbli-faq.ts's pmaSourceNote
  // — one classifier for one fact, never reinvented per surface): the Perpres
  // crosswalk-pending caveat is only true for codes the Perpres annexes
  // actually govern. The six insurance codes this fix-pack adjudicates under
  // PP 14/2018 Pasal 5(1) jo. PP 3/2020 are NOT among them, and the old
  // hardcoded clause attributed their 80% cap to the wrong instrument in the
  // JSON-LD Google ingests.
  const pmaAttribution = pmaSourceAttributionStructured(
    code.pma.source,
    code.provenance?.pma.status ?? "declared_gap",
  );
  const ownershipLabel = structuredPmaOwnership(code);
  const statusToken =
    code.pma.status === "open"
      ? "TERBUKA"
      : code.pma.status === "restricted"
        ? "TERBATAS"
        : "TERTUTUP";
  const pmaLabel = `${
    !pmaVerdictVerified
      ? "Foreign-ownership status not yet verified for this KBLI 2025 code"
      : `${ownershipLabel} (${statusToken})${
          code.pma.status === "open" ? baliNat : ""
        }`
  }${pmaAttribution}`;

  // The rendered page translates this tier (PR #4776); the JSON-LD did not, so a
  // block that declares `"inLanguage": "en"` was emitting `Risk: Menengah Rendah`
  // into the description, keywords and GovernmentService that search engines read.
  // `riskLabelEn` returns null for a tier it does not recognise, so the raw value is
  // kept as the fallback -- this translates what it knows and never drops information.
  const rawRiskCategory = code.licensing[0]?.riskCategory;
  const riskLevel: string =
    riskLabelEn(rawRiskCategory) ?? rawRiskCategory ?? "Unknown";
  const licenseType = code.licensing[0]?.licenseType ?? "NIB";
  // Rows not verified against a KBLI-2025-native OSS source must not reach
  // Google/AI answers as unqualified fact (Codex gate round 4).
  const pendingSuffix = isLicensingVerificationPending(code)
    ? " (verification pending)"
    : "";

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    name: `KBLI ${code.code} — ${code.titleId}`,
    headline: `KBLI ${code.code}: ${code.titleId} — Indonesian Business Code Guide`,
    description: `${code.description.slice(0, 160)}. ${pmaLabel}. Risk: ${riskLevel}${pendingSuffix}.`,
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
      pmaVerdictVerified &&
      code.pma.status === "open" &&
      hasPublishablePmaCap(code.pma) &&
      !(code.pma.capVerified === true && code.pma.maxForeign === 0)
        ? "PT PMA"
        : undefined,
      riskLevel !== "Unknown" ? `${riskLevel} risk` : undefined,
      code.section ? `Section ${code.section}` : undefined,
    ]
      .filter(Boolean)
      .join(", "),
    about: {
      "@type": "GovernmentService",
      name: `KBLI ${code.code} — ${code.titleId}`,
      description: `${code.titleEn}. ${pmaLabel}. License: ${licenseType}${pendingSuffix}. Risk level: ${riskLevel}${pendingSuffix}.`,
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
