/**
 * Enhanced JSON-LD Components for AI Search Optimization (SOTA Feb 2026)
 *
 * Implements:
 * - @graph composite schemas (Article + FAQ + Breadcrumb + Organization)
 * - Entity linking with sameAs/Wikidata QIDs
 * - SpeakableSpecification for voice search
 * - Passage-level optimization hints
 * - Citation-worthy structured data for GEO/AEO/LLMO
 * - TopLevelArticleJsonLd: standalone top-level @type: Article (2026-06-04)
 *
 * Sources: schema.org, Google Search Central, llmstxt.org
 */

import type { FAQItem, EntityMention } from "@/lib/blog/types";

const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || "https://balizero.com";

// Bali Zero Organization schema (singleton, reused across all pages)
const BALI_ZERO_ORG = {
  "@type": "Organization",
  "@id": `${baseUrl}/#organization`,
  name: "Bali Zero",
  url: baseUrl,
  logo: {
    "@type": "ImageObject",
    url: `${baseUrl}/static/balizero-logo-clean.png`,
    width: 512,
    height: 512,
  },
  description:
    "Visa, immigration, and business consulting firm in Bali, Indonesia. Expert guidance on visas, PT PMA company setup, tax compliance, and property services.",
  foundingDate: "2023",
  areaServed: {
    "@type": "Country",
    name: "Indonesia",
    sameAs: "https://www.wikidata.org/wiki/Q252",
  },
  knowsAbout: [
    "Indonesian immigration law",
    "PT PMA company formation",
    "KBLI 2025 business classification",
    "Indonesian tax compliance",
    "Property ownership for foreigners in Indonesia",
  ],
  sameAs: ["https://www.instagram.com/balizero0"],
};

// WebSite schema for sitelinks search
const WEBSITE_SCHEMA = {
  "@type": "WebSite",
  "@id": `${baseUrl}/#website`,
  url: baseUrl,
  name: "Bali Zero",
  publisher: { "@id": `${baseUrl}/#organization` },
  inLanguage: "en-US",
};

/**
 * Map entity mentions to JSON-LD with sameAs linking
 */
function mapEntityToJsonLd(entity: EntityMention) {
  const mapped: Record<string, unknown> = {
    "@type": entity.type,
    name: entity.name,
  };
  if (entity.sameAs) {
    mapped.sameAs = entity.sameAs;
  }
  return mapped;
}

// ============================================================================
// Article + FAQ Composite (most common - articles with FAQ sections)
// ============================================================================

interface ArticleWithFAQJsonLdProps {
  title: string;
  description: string;
  slug: string;
  category: string;
  publishedAt: string;
  updatedAt?: string;
  author?: { name: string; role?: string };
  image?: string;
  tags?: string[];
  readingTime?: number;
  faq: FAQItem[];
  answerSnippet?: string;
  entityMentions?: EntityMention[];
}

export function ArticleWithFAQJsonLd({
  title,
  description,
  slug,
  category,
  publishedAt,
  updatedAt,
  author,
  image,
  tags,
  readingTime,
  faq,
  answerSnippet,
  entityMentions,
}: Readonly<ArticleWithFAQJsonLdProps>) {
  const articleUrl = `${baseUrl}/${category}/${slug}`;
  const imageUrl = image?.startsWith("http")
    ? image
    : `${baseUrl}${image || "/static/og-image.jpg"}`;

  // Filter entity mentions for about (exclude Bali Zero itself)
  const aboutEntities = entityMentions
    ?.filter((e) => e.type !== "Organization" || e.name !== "Bali Zero")
    .slice(0, 5)
    .map(mapEntityToJsonLd);

  const allEntities = entityMentions?.map(mapEntityToJsonLd);

  const schema = {
    "@context": "https://schema.org",
    "@graph": [
      BALI_ZERO_ORG,
      WEBSITE_SCHEMA,
      {
        "@type": "WebPage",
        "@id": articleUrl,
        url: articleUrl,
        name: title,
        isPartOf: { "@id": `${baseUrl}/#website` },
        datePublished: publishedAt,
        dateModified: updatedAt || publishedAt,
        lastReviewed: updatedAt || publishedAt,
        reviewedBy: { "@id": `${baseUrl}/#organization` },
        inLanguage: "en-US",
        breadcrumb: { "@id": `${baseUrl}/#breadcrumb` },
      },
      {
        "@type": ["Article", "NewsArticle"],
        "@id": `${articleUrl}#article`,
        isPartOf: { "@id": `${baseUrl}/#website` },
        headline: title,
        description: answerSnippet || description,
        url: articleUrl,
        image: {
          "@type": "ImageObject",
          url: imageUrl,
          width: 1200,
          height: 630,
        },
        datePublished: publishedAt,
        dateModified: updatedAt || publishedAt,
        author: { "@id": `${baseUrl}/#organization` },
        publisher: { "@id": `${baseUrl}/#organization` },
        mainEntityOfPage: { "@id": articleUrl },
        keywords: tags?.join(", "),
        wordCount: readingTime ? readingTime * 200 : undefined,
        articleSection: category,
        inLanguage: "en-US",
        isAccessibleForFree: true,
        speakable: {
          "@type": "SpeakableSpecification",
          cssSelector: ["h1", "[data-ai-excerpt]", ".faq-answer"],
        },
        ...(aboutEntities?.length ? { about: aboutEntities } : {}),
        ...(allEntities?.length ? { mentions: allEntities } : {}),
      },
      {
        "@type": "FAQPage",
        "@id": `${articleUrl}#faq`,
        isPartOf: { "@id": `${articleUrl}#article` },
        mainEntity: faq.map((item) => ({
          "@type": "Question",
          name: item.question,
          acceptedAnswer: { "@type": "Answer", text: item.answer },
        })),
      },
    ],
  };

  return (
    <script
      id="article-faq-jsonld"
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// ============================================================================
// Enhanced Article (no FAQ - simpler articles)
// ============================================================================

interface EnhancedArticleJsonLdProps {
  title: string;
  description: string;
  slug: string;
  category: string;
  publishedAt: string;
  updatedAt?: string;
  author?: { name: string; role?: string };
  image?: string;
  tags?: string[];
  readingTime?: number;
  answerSnippet?: string;
  entityMentions?: EntityMention[];
}

export function EnhancedArticleJsonLd({
  title,
  description,
  slug,
  category,
  publishedAt,
  updatedAt,
  image,
  tags,
  readingTime,
  answerSnippet,
  entityMentions,
}: Readonly<EnhancedArticleJsonLdProps>) {
  const articleUrl = `${baseUrl}/${category}/${slug}`;
  const imageUrl = image?.startsWith("http")
    ? image
    : `${baseUrl}${image || "/static/og-image.jpg"}`;

  const aboutEntities = entityMentions
    ?.filter((e) => e.type !== "Organization" || e.name !== "Bali Zero")
    .slice(0, 5)
    .map(mapEntityToJsonLd);

  const allEntities = entityMentions?.map(mapEntityToJsonLd);

  const schema = {
    "@context": "https://schema.org",
    "@graph": [
      BALI_ZERO_ORG,
      WEBSITE_SCHEMA,
      {
        "@type": "WebPage",
        "@id": articleUrl,
        url: articleUrl,
        name: title,
        isPartOf: { "@id": `${baseUrl}/#website` },
        datePublished: publishedAt,
        dateModified: updatedAt || publishedAt,
        lastReviewed: updatedAt || publishedAt,
        reviewedBy: { "@id": `${baseUrl}/#organization` },
        inLanguage: "en-US",
      },
      {
        "@type": ["Article", "NewsArticle"],
        "@id": `${articleUrl}#article`,
        isPartOf: { "@id": `${baseUrl}/#website` },
        headline: title,
        description: answerSnippet || description,
        url: articleUrl,
        image: {
          "@type": "ImageObject",
          url: imageUrl,
          width: 1200,
          height: 630,
        },
        datePublished: publishedAt,
        dateModified: updatedAt || publishedAt,
        author: { "@id": `${baseUrl}/#organization` },
        publisher: { "@id": `${baseUrl}/#organization` },
        mainEntityOfPage: { "@id": articleUrl },
        keywords: tags?.join(", "),
        wordCount: readingTime ? readingTime * 200 : undefined,
        articleSection: category,
        inLanguage: "en-US",
        isAccessibleForFree: true,
        speakable: {
          "@type": "SpeakableSpecification",
          cssSelector: ["h1", "[data-ai-excerpt]"],
        },
        ...(aboutEntities?.length ? { about: aboutEntities } : {}),
        ...(allEntities?.length ? { mentions: allEntities } : {}),
      },
    ],
  };

  return (
    <script
      id="enhanced-article-jsonld"
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// ============================================================================
// HowTo Schema (for step-by-step guides)
// ============================================================================

interface HowToStep {
  name: string;
  text: string;
}

interface HowToJsonLdProps {
  name: string;
  description: string;
  steps: HowToStep[];
  totalTime?: string;
  image?: string;
}

export function HowToJsonLd({
  name,
  description,
  steps,
  totalTime,
  image,
}: Readonly<HowToJsonLdProps>) {
  const imageUrl = image?.startsWith("http")
    ? image
    : `${baseUrl}${image || "/static/og-image.jpg"}`;

  const schema = {
    "@context": "https://schema.org",
    "@type": "HowTo",
    name,
    description,
    image: imageUrl,
    totalTime: totalTime || undefined,
    step: steps.map((step, i) => ({
      "@type": "HowToStep",
      position: i + 1,
      name: step.name,
      text: step.text,
    })),
  };

  return (
    <script
      id="howto-jsonld"
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}

// ============================================================================
// Top-Level Article JSON-LD (standalone, NOT inside @graph)
// Required for Google Rich Results eligibility — audit 2026-06-04
// ============================================================================

interface TopLevelArticleJsonLdProps {
  title: string;
  description?: string;
  slug: string;
  category: string;
  publishedAt: string; // ISO 8601 string
  updatedAt?: string; // ISO 8601 string
  image?: string;
}

/**
 * Emits a standalone top-level @type: Article JSON-LD block.
 *
 * This is the form Google requires for Article rich results eligibility.
 * Must coexist with (not replace) the @graph-based composite schemas.
 *
 * - datetime: ISO 8601 full format with +07:00 (WIB timezone)
 * - image: falls back to og-default.jpg if null/undefined
 * - author + publisher: always Bali Zero Organization
 */
export function TopLevelArticleJsonLd({
  title,
  description,
  slug,
  category,
  publishedAt,
  updatedAt,
}: Readonly<TopLevelArticleJsonLdProps>) {
  const articleUrl = `${baseUrl}/${category}/${slug}`;

  /**
   * Normalize an ISO string to include the WIB timezone (+07:00).
   * If the string already carries a timezone offset or 'Z', we strip the
   * trailing Z/+00:00 and append +07:00 only when no tz is present,
   * so we never double-apply a timezone.
   */
  function toWibIso(isoString: string): string {
    // Already has a named timezone offset → return as-is
    if (/[+-]\d{2}:\d{2}$/.test(isoString)) return isoString;
    // Ends with 'Z' (UTC) → replace with +07:00
    if (isoString.endsWith("Z")) {
      return isoString.slice(0, -1) + "+07:00";
    }
    // No timezone — assume it's a date-only or datetime without tz, append +07:00
    // Ensure it has a time component (YYYY-MM-DD → YYYY-MM-DDT00:00:00)
    const hasTime = /T/.test(isoString);
    return hasTime ? `${isoString}+07:00` : `${isoString}T00:00:00+07:00`;
  }

  const schema = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: title,
    description: description ?? undefined,
    url: articleUrl,
    datePublished: toWibIso(publishedAt),
    dateModified: toWibIso(updatedAt ?? publishedAt),
    image: {
      "@type": "ImageObject",
      url: `${baseUrl}/og-default.jpg`,
      width: 1200,
      height: 630,
    },
    author: {
      "@type": "Organization",
      name: "Bali Zero",
      url: baseUrl,
    },
    publisher: {
      "@type": "Organization",
      name: "Bali Zero",
      url: baseUrl,
      logo: {
        "@type": "ImageObject",
        url: `${baseUrl}/static/balizero-logo-clean.png`,
      },
    },
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": articleUrl,
    },
    inLanguage: "en-US",
    isAccessibleForFree: true,
  };

  return (
    <script
      id="top-level-article-jsonld"
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
    />
  );
}
