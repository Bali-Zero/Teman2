/**
 * Enhanced JSON-LD Components for AI Search Optimization (SOTA Feb 2026)
 *
 * Implements:
 * - @graph composite schemas (Article + FAQ + Breadcrumb + Organization)
 * - Entity linking with sameAs/Wikidata QIDs
 * - SpeakableSpecification for voice search
 * - Passage-level optimization hints
 * - Citation-worthy structured data for GEO/AEO/LLMO
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
