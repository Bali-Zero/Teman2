import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getArticleBySlug } from "@/lib/blog/articles";
import { generateArticleMetadata } from "@/lib/blog/metadata";
import { ArticleClient } from "./ArticleClient";
import {
  ArticleWithFAQJsonLd,
  EnhancedArticleJsonLd,
  BreadcrumbJsonLd,
} from "@/components/seo";
import { logger } from "@/lib/logger";

interface PageProps {
  params: Promise<{
    category: string;
    slug: string;
  }>;
}

// Static file paths that should NOT be handled by this route
// 'images' included for backward compatibility (old URLs should 404, not render broken page)
const STATIC_PATHS = [
  "static",
  "assets",
  "fonts",
  "_next",
  "api",
  "images",
  "avatars",
  "blueprints",
  "videos",
  "admin",
  "dashboard",
  "login",
  "chat",
  "clients",
  "settings",
];

// Valid blog categories
const VALID_CATEGORIES = [
  "immigration",
  "business",
  "tax-legal",
  "property",
  "lifestyle",
  "digital-nomad",
  "tech",
];

/**
 * Check if this request is for a static file (should return 404 to let Next.js serve static)
 */
function isStaticFilePath(category: string, slug: string): boolean {
  // If category is a known static path, reject
  if (STATIC_PATHS.includes(category)) return true;
  // If slug has a file extension, reject
  if (slug.includes(".")) return true;
  return false;
}

/**
 * Generate dynamic metadata for SEO
 * This runs on the server and provides metadata to Google, social media, and AI crawlers
 */
export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { category, slug } = await params;

  // Reject static file paths - let Next.js serve them from /public
  if (isStaticFilePath(category, slug)) {
    return { title: "Not Found" };
  }

  try {
    const article = await getArticleBySlug(category, slug);

    if (article) {
      return generateArticleMetadata(article);
    }
  } catch (err) {
    logger.error(
      "Error generating metadata:",
      {},
      err instanceof Error ? err : new Error(String(err)),
    );
  }

  // Fallback metadata
  return {
    title: `${slug.replace(/-/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())} | Bali Zero`,
    description: `Learn about ${slug.replace(/-/g, " ")} in Indonesia. Expert guides from Bali Zero.`,
  };
}

// Category labels for breadcrumbs
const CATEGORY_LABELS: Record<string, string> = {
  immigration: "Immigration",
  business: "Business",
  "tax-legal": "Tax & Legal",
  property: "Property",
  lifestyle: "Lifestyle",
  "digital-nomad": "Digital Nomad",
  tech: "Tech",
};

/**
 * Article page - Server component that renders the client component
 * Injects JSON-LD structured data for AI crawlers (server-side rendered)
 */
export default async function ArticlePage({ params }: PageProps) {
  const { category, slug } = await params;

  // Reject static file paths - return 404 so Next.js can serve from /public
  if (isStaticFilePath(category, slug)) {
    notFound();
  }

  // Fetch article for JSON-LD injection (server-side)
  const article = await getArticleBySlug(category, slug);

  const breadcrumbItems = [
    { name: "Home", url: "/" },
    { name: CATEGORY_LABELS[category] || category, url: `/${category}` },
    ...(article ? [{ name: article.title, url: `/${category}/${slug}` }] : []),
  ];

  const articleProps = article
    ? {
        title: article.title,
        description: article.seoDescription || article.excerpt,
        slug: article.slug,
        category: article.category,
        publishedAt: (article.publishedAt || article.createdAt).toISOString(),
        updatedAt: article.updatedAt.toISOString(),
        author: article.author,
        image: article.coverImage,
        tags: article.tags,
        readingTime: article.readingTime,
        answerSnippet: article.aiOptimization?.answerSnippet,
        entityMentions: article.aiOptimization?.entityMentions,
      }
    : null;

  return (
    <>
      <BreadcrumbJsonLd items={breadcrumbItems} />
      {articleProps && article?.faq?.length ? (
        <ArticleWithFAQJsonLd {...articleProps} faq={article.faq} />
      ) : articleProps ? (
        <EnhancedArticleJsonLd {...articleProps} />
      ) : null}
      <ArticleClient category={category} slug={slug} />
    </>
  );
}
