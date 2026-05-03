import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { serialize } from "next-mdx-remote/serialize";
import remarkGfm from "remark-gfm";
import {
  getArticleBySlug,
  getArticleByLocale,
  getAvailableLocales,
} from "@/lib/blog/articles";
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
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
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
  "visas",
  "business",
  "taxes",
  "property",
  "living",
  "digital-nomad",
  "trends",
  "living",
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
  searchParams,
}: PageProps): Promise<Metadata> {
  const { category, slug } = await params;
  const sp = await searchParams;
  const lang = typeof sp.lang === "string" ? sp.lang : undefined;

  // Reject static file paths - let Next.js serve them from /public
  if (isStaticFilePath(category, slug)) {
    return { title: "Not Found" };
  }

  try {
    const article = lang
      ? await getArticleByLocale(category, slug, lang)
      : await getArticleBySlug(category, slug);

    if (article) {
      const baseMetadata = generateArticleMetadata(article);

      // Build hreflang alternates for available translations
      const availableLocales = getAvailableLocales(category, slug);
      const baseUrl = "https://balizero.com";
      const languages: Record<string, string> = {
        en: `${baseUrl}/${category}/${slug}`,
        "x-default": `${baseUrl}/${category}/${slug}`,
      };
      for (const loc of availableLocales) {
        if (loc === "en") continue;
        languages[loc] = `${baseUrl}/${category}/${slug}?lang=${loc}`;
      }

      return {
        ...baseMetadata,
        alternates: {
          ...baseMetadata.alternates,
          languages,
        },
      };
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
  visas: "Immigration",
  business: "Business",
  "taxes": "Tax & Legal",
  property: "Property",
  living: "Lifestyle",
  "digital-nomad": "Digital Nomad",
  trends: "Tech",
};

/**
 * Strip import statements from MDX content
 */
function stripImports(content: string): string {
  return content
    .replace(/^import\s+[\s\S]*?from\s+['"][^'"]+['"];?\s*$/gm, "")
    .replace(/^import\s*{[\s\S]*?}\s*from\s*['"][^'"]+['"];?\s*$/gm, "")
    .trim();
}

/**
 * Article page - Server component that renders the client component
 * Serializes MDX server-side and passes it as a prop for SSR (Google sees full content)
 */
export default async function ArticlePage({ params, searchParams }: PageProps) {
  const { category, slug } = await params;
  const sp = await searchParams;
  const lang = typeof sp.lang === "string" ? sp.lang : undefined;

  // Reject static file paths - return 404 so Next.js can serve from /public
  if (isStaticFilePath(category, slug)) {
    notFound();
  }

  // Fetch article (locale-aware) for JSON-LD injection AND SSR content
  const article = lang
    ? await getArticleByLocale(category, slug, lang)
    : await getArticleBySlug(category, slug);

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

  // Serialize MDX server-side so content is in the initial HTML (SSR)
  let initialArticle = null;
  if (article) {
    const cleanContent = stripImports(article.content);
    try {
      const mdxSource = await serialize(cleanContent, {
        mdxOptions: {
          remarkPlugins: [remarkGfm],
          development: false,
        },
      });
      // Serialize dates to strings for client component
      initialArticle = {
        ...article,
        mdxSource,
        createdAt: article.createdAt.toISOString(),
        updatedAt: article.updatedAt.toISOString(),
        publishedAt: article.publishedAt
          ? article.publishedAt.toISOString()
          : null,
      };
    } catch (err) {
      logger.error(
        "MDX serialization failed in SSR, falling back to client fetch",
        {},
        err instanceof Error ? err : new Error(String(err)),
      );
      // initialArticle stays null — ArticleClient will fetch via API
    }
  }

  return (
    <>
      <BreadcrumbJsonLd items={breadcrumbItems} />
      {articleProps && article?.faq?.length ? (
        <ArticleWithFAQJsonLd {...articleProps} faq={article.faq} />
      ) : articleProps ? (
        <EnhancedArticleJsonLd {...articleProps} />
      ) : null}
      <ArticleClient
        category={category}
        slug={slug}
        initialArticle={initialArticle}
      />
    </>
  );
}
