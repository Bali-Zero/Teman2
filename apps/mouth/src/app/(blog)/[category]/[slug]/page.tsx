import type { Metadata } from "next";
import type { ReactNode } from "react";
import { notFound, permanentRedirect } from "next/navigation";
import {
  getArticleBySlug,
  getArticleByLocale,
  resolveCategoryAlias,
} from "@/lib/blog/articles";
import { generateArticleMetadata } from "@/lib/blog/metadata";
import { renderMDXBody } from "@/components/blog/MDXContentRSC";
import {
  ArticleClient,
  type SerializedArticleForClient,
} from "./ArticleClient";
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

      return {
        ...baseMetadata,
      };
    }
  } catch (err) {
    logger.error(
      "Error generating metadata:",
      {},
      err instanceof Error ? err : new Error(String(err)),
    );

    // Genuine lookup error (distinct from "article missing"): keep the page
    // renderable but never indexable under invented metadata.
    return {
      title: "Bali Zero",
      robots: { index: false, follow: false },
    };
  }

  // Article does not exist: render the 404 boundary. Title-casing the slug
  // here used to fabricate a phantom 200 page for ANY url (soft-404, D12).
  notFound();
}

// Category labels for breadcrumbs
const CATEGORY_LABELS: Record<string, string> = {
  visas: "Immigration",
  business: "Business",
  taxes: "Tax & Legal",
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

  // No article in backend NOR local MDX: hard 404 (D12 soft-404 fix).
  // getArticleBySlug/getArticleByLocale return null both for "not found";
  // backend outages degrade to the MDX-on-disk fallback before reaching here.
  if (!article) {
    notFound();
  }

  // Category-alias canonicalization: the same article is reachable under
  // alias categories (e.g. /immigration/X and /visas/X). When the requested
  // category is a KNOWN alias of the article's canonical category, issue a
  // 308 permanent redirect to the canonical URL instead of serving duplicate
  // content that relies on the canonical <meta> alone. Unknown categories
  // keep current behavior (notFound per D12 above).
  // NOTE: permanentRedirect throws NEXT_REDIRECT — must stay outside try/catch.
  const canonical = resolveCategoryAlias(category);
  if (canonical && canonical !== category && article.category === canonical) {
    const langSuffix = lang ? `?lang=${encodeURIComponent(lang)}` : "";
    permanentRedirect(`/${canonical}/${slug}${langSuffix}`);
  }

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

  // Render the MDX body SERVER-SIDE for SSR (Google + the e2e see the full
  // article in the initial HTML). React-19 fix: we render via the RSC MDXRemote
  // (a server component) instead of serializing for the client <MDXRemote>,
  // which is hook-based and throws `Cannot read properties of null (reading
  // 'useState')` during SSR under React 19 — that uncaught throw used to unwind
  // the whole article subtree, dropping even the .rumah-putih page chrome from
  // the SSR HTML. See MDXContentRSC for the full rationale.
  let initialArticle: SerializedArticleForClient | null = null;
  let mdxBody: ReactNode = null;
  if (article) {
    const cleanContent = stripImports(article.content);
    try {
      // Awaited (NOT bare JSX) so a compile failure is actually caught here and
      // degrades to the client-fetch fallback instead of crashing the page.
      mdxBody = await renderMDXBody(cleanContent);
      // Serialize dates to strings for the client component. mdxSource is no
      // longer needed for SSR (the body is server-rendered and passed as a
      // prop); ArticleClient keeps its own client-side fallback path for
      // articles it fetches in the browser.
      initialArticle = {
        ...article,
        createdAt: article.createdAt.toISOString(),
        updatedAt: article.updatedAt.toISOString(),
        publishedAt: article.publishedAt
          ? article.publishedAt.toISOString()
          : null,
      };
    } catch (err) {
      logger.error(
        "MDX server render failed in SSR, falling back to client fetch",
        {},
        err instanceof Error ? err : new Error(String(err)),
      );
      // initialArticle/mdxBody stay null — ArticleClient will fetch via API
      // and render the body client-side (in a real browser, React-19-safe).
      initialArticle = null;
      mdxBody = null;
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
        mdxBody={mdxBody}
      />
    </>
  );
}
