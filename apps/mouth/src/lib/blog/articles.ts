/**
 * Blog Article Reader - Hybrid: Backend API + Local MDX fallback
 * For Nuzantara/Bali Zero Insights Blog
 *
 * Priority: Backend API (news_items table) > Local MDX files
 * Backend articles come from the intel pipeline (scraper → staging → approval → publish)
 * MDX articles are legacy static content
 */

import fs from "fs";
import path from "path";
import matter from "gray-matter";
import { unstable_cache } from "next/cache";
import type { Article, ArticleListItem, ArticleCategory } from "./types";

const ARTICLES_PATH = path.join(process.cwd(), "src/content/articles");
const ARTICLE_FOLDER_NAMES = Object.freeze([
  "immigration",
  "business",
  "business_regulations",
  "news",
  "tax-legal",
  "tax",
  "property",
  "lifestyle",
  "digital-nomad",
  "bali_news",
  "emerging_trends",
  "tech",
  "social_media",
] as const);
type ArticleFolderName = (typeof ARTICLE_FOLDER_NAMES)[number];
const ARTICLE_FOLDER_SET = new Set<string>(ARTICLE_FOLDER_NAMES);

const BACKEND_URL =
  process.env.BACKEND_RAG_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  "https://nuzantara-rag.fly.dev";

/**
 * Map folder/frontmatter categories to valid ArticleCategory
 * This handles legacy naming and folder structure differences
 */
const CATEGORY_MAP: Record<string, ArticleCategory> = {
  // Canonical categories
  visas: "visas",
  business: "business",
  taxes: "taxes",
  property: "property",
  living: "living",
  trends: "trends",
  // Backward compat (old category names)
  immigration: "visas",
  lifestyle: "living",
  tech: "trends",
  bali_news: "living",
  // Folder mappings (14 folders → 7 categories)
  tax: "taxes",
  "tax-legal": "taxes",
  "digital-nomad": "living",
  "bali-news": "living",
  business_regulations: "business",
  emerging_trends: "trends",
  social_media: "trends",
  news: "business",
  // Backend compatibility
  general: "business",
  legal: "taxes",
};

function normalizeCategory(rawCategory: string): ArticleCategory {
  return CATEGORY_MAP[rawCategory] || "living";
}

/**
 * Coerce a raw `tags` value (from MDX frontmatter or the backend `ai_tags`
 * field) into a guaranteed `string[]`. Both sources are untrusted at runtime:
 *  - MDX frontmatter `tags:` can be mis-indented so gray-matter parses it as an
 *    object (real bug: bali-ota-purge-2026.mdx had every later field nested
 *    under `tags`, making it a non-iterable object).
 *  - The backend `ai_tags` is typed `string[] | null` but can arrive as a JSON
 *    string, a single string, or null.
 * Anything that is not an array of strings becomes `[]` (a single string is
 * wrapped). This is the single boundary where tags become iterable — every
 * downstream consumer (`.map`, `.length`, `[...tags]`) is then safe.
 */
export function normalizeTags(raw: unknown): string[] {
  if (Array.isArray(raw)) {
    return raw.filter((t): t is string => typeof t === "string");
  }
  if (typeof raw === "string" && raw.trim().length > 0) {
    return [raw.trim()];
  }
  return [];
}

/**
 * Resolve a requested category param to its canonical category, if known.
 * Returns null for unknown categories (caller keeps current behavior).
 * Used by the article page to issue a permanent redirect from alias
 * categories (e.g. /immigration/X) to the canonical URL (/visas/X).
 */
export function resolveCategoryAlias(
  rawCategory: string,
): ArticleCategory | null {
  return CATEGORY_MAP[rawCategory] ?? null;
}

/** Strip markdown headings and formatting from excerpt text (used for frontmatter/backend strings) */
function cleanExcerpt(text: string | null): string {
  if (!text) return "";
  return text
    .replace(/^#{1,6}\s+.*$/gm, "") // remove ## heading lines entirely
    .replace(/\*\*(.*?)\*\*/g, "$1") // **bold**
    .replace(/\*(.*?)\*/g, "$1") // *italic*
    .replace(/\[(.*?)\]\(.*?\)/g, "$1") // [link](url)
    .replace(/`(.*?)`/g, "$1") // `code`
    .replace(/\n{2,}/g, " ") // collapse blank lines
    .trim();
}

/**
 * Extract the first meaningful paragraph from MDX body content.
 * Skips all heading lines (## ...) and their immediate content blocks,
 * picks the first paragraph longer than 60 characters.
 */
function extractBodyExcerpt(body: string): string {
  if (!body) return "";

  // Split into lines and process
  const lines = body.split("\n");
  let inHeadingBlock = false;
  const paragraphLines: string[] = [];

  for (const line of lines) {
    const trimmed = line.trim();

    // New heading encountered — reset block accumulator and skip
    if (/^#{1,6}\s/.test(trimmed)) {
      // If we already have paragraph lines, stop here (we're past first para)
      if (paragraphLines.length > 0) break;
      inHeadingBlock = true;
      continue;
    }

    // Blank line after a heading block — heading block ends, but skip blank
    if (inHeadingBlock && trimmed === "") {
      inHeadingBlock = false;
      continue;
    }

    // Skip JSX/import lines and HTML-ish tags
    if (/^import\s|^export\s|^<[A-Z]|^<\//.test(trimmed)) continue;

    // Skip lines that are only markdown decorators (hr, list bullets, blockquote markers)
    if (/^[-*_]{3,}$|^>\s/.test(trimmed)) continue;

    if (trimmed !== "") {
      paragraphLines.push(trimmed);
    } else if (paragraphLines.length > 0) {
      // Blank line = paragraph break; check if accumulated text is long enough
      const candidate = paragraphLines
        .join(" ")
        .replace(/\*\*(.*?)\*\*/g, "$1")
        .replace(/\*(.*?)\*/g, "$1")
        .replace(/\[(.*?)\]\(.*?\)/g, "$1")
        .replace(/`(.*?)`/g, "$1")
        .trim();
      if (candidate.length > 60) return candidate;
      // Too short — reset and keep looking
      paragraphLines.length = 0;
    }
  }

  // End of file — check whatever is accumulated
  if (paragraphLines.length > 0) {
    const candidate = paragraphLines
      .join(" ")
      .replace(/\*\*(.*?)\*\*/g, "$1")
      .replace(/\*(.*?)\*/g, "$1")
      .replace(/\[(.*?)\]\(.*?\)/g, "$1")
      .replace(/`(.*?)`/g, "$1")
      .trim();
    if (candidate.length > 60) return candidate;
  }

  return "";
}

/** Default cover images per normalized category (files that actually exist in public/static/blog/) */
const CATEGORY_COVER_DEFAULTS: Record<string, string> = {
  visas: "/static/blog/kitas-guide.jpg",
  business: "/static/blog/oss-guide.jpg",
  taxes: "/static/blog/tax-calendar.jpg",
  property: "/static/blog/golden-visa.jpg",
  living: "/static/blog/north-bali.jpg",
  trends: "/static/blog/nomad-comparison.jpg",
};

function defaultCoverImage(category: ArticleCategory): string {
  return CATEGORY_COVER_DEFAULTS[category] || "/static/blog/golden-visa.jpg";
}

/**
 * Derive the homepage-card (16:10) variant path from a news cover image.
 * The poller writes `/static/news/{slug}.jpg` (hero) + `/static/news/{slug}_card.jpg`
 * (card). When an explicit cardImage isn't in frontmatter, derive it only for the
 * news-cover pattern; otherwise return undefined so consumers fall back to coverImage.
 */
function deriveCardImage(coverImage?: string | null): string | undefined {
  if (!coverImage) return undefined;
  const m = coverImage.match(/^(\/static\/news\/.+)\.(jpg|jpeg|png)$/i);
  return m ? `${m[1]}_card.${m[2]}` : undefined;
}

function isArticleFolderName(value: string): value is ArticleFolderName {
  return ARTICLE_FOLDER_SET.has(value);
}

function articleFolderPath(folder: ArticleFolderName): string {
  return path.join(/*turbopackIgnore: true*/ ARTICLES_PATH, folder);
}

function articleMdxPath(folder: ArticleFolderName, slug: string): string {
  return path.join(
    /*turbopackIgnore: true*/ articleFolderPath(folder),
    `${slug}.mdx`,
  );
}

function articleLocaleMdxPath(
  folder: ArticleFolderName,
  slug: string,
  locale: string,
): string {
  return path.join(
    /*turbopackIgnore: true*/ articleFolderPath(folder),
    `${slug}.${locale}.mdx`,
  );
}

// ============================================================================
// Backend API Functions
// ============================================================================

interface BackendNewsItem {
  id: string;
  title: string;
  slug: string;
  summary: string | null;
  content: string | null;
  source: string;
  source_url: string | null;
  category: string;
  priority: string;
  status: string;
  image_url: string | null;
  view_count: number;
  published_at: string | null;
  created_at: string;
  ai_summary: string | null;
  ai_tags: string[] | null;
}

function backendToArticleListItem(item: BackendNewsItem): ArticleListItem {
  return {
    id: item.id,
    slug: item.slug,
    title: item.title,
    excerpt: cleanExcerpt(item.summary || item.ai_summary),
    coverImage:
      item.image_url || defaultCoverImage(normalizeCategory(item.category)),
    cardImage: deriveCardImage(item.image_url),
    category: normalizeCategory(item.category),
    author: {
      id: "zantara-ai",
      name: "Zantara AI",
      avatar: "/static/zantara-avatar.png",
      role: "AI Research Assistant",
      isAI: true,
    },
    publishedAt: item.published_at
      ? new Date(item.published_at)
      : new Date(item.created_at),
    readingTime: item.content
      ? Math.ceil(item.content.split(/\s+/).length / 200)
      : 5,
    viewCount: item.view_count || 0,
    featured: item.priority === "high",
    trending: false,
    aiGenerated: true,
  };
}

function backendToArticle(item: BackendNewsItem): Article {
  return {
    id: item.id,
    slug: item.slug,
    title: item.title,
    excerpt: cleanExcerpt(item.summary || item.ai_summary),
    content: item.content || "",
    coverImage:
      item.image_url || defaultCoverImage(normalizeCategory(item.category)),
    cardImage: deriveCardImage(item.image_url),
    coverImageAlt: item.title,
    category: normalizeCategory(item.category),
    tags: normalizeTags(item.ai_tags),
    author: {
      id: "zantara-ai",
      name: "Zantara AI",
      avatar: "/static/zantara-avatar.png",
      role: "AI Research Assistant",
      isAI: true,
    },
    createdAt: new Date(item.created_at),
    updatedAt: new Date(item.created_at),
    publishedAt: item.published_at ? new Date(item.published_at) : undefined,
    status: "published",
    featured: item.priority === "high",
    trending: false,
    readingTime: item.content
      ? Math.ceil(item.content.split(/\s+/).length / 200)
      : 5,
    viewCount: item.view_count || 0,
    shareCount: 0,
    likeCount: 0,
    commentCount: 0,
    aiGenerated: true,
    relatedArticleIds: [],
    locale: "en",
  };
}

async function fetchBackendArticles(options?: {
  category?: string;
  limit?: number;
  page?: number;
  search?: string;
}): Promise<{ items: BackendNewsItem[]; total: number } | null> {
  try {
    const params = new URLSearchParams();
    if (options?.category) params.set("category", options.category);
    if (options?.limit) params.set("limit", String(options.limit));
    if (options?.page) params.set("page", String(options.page));
    if (options?.search) params.set("search", options.search);
    params.set("status", "approved");

    const url = `${BACKEND_URL}/api/news?${params.toString()}`;
    const res = await fetch(url, {
      next: { revalidate: 60 },
      signal: AbortSignal.timeout(5000),
    });

    if (!res.ok) return null;

    const data = await res.json();
    if (!data.success) return null;

    return { items: data.data || [], total: data.total || 0 };
  } catch {
    // Backend unavailable — silent fallback to MDX
    return null;
  }
}

async function fetchBackendArticleBySlug(
  slug: string,
): Promise<BackendNewsItem | null> {
  try {
    const url = `${BACKEND_URL}/api/news/${slug}`;
    const res = await fetch(url, {
      next: { revalidate: 60 },
      signal: AbortSignal.timeout(5000),
    });

    if (!res.ok) return null;

    const data = await res.json();
    if (!data.success) return null;

    return data.data || null;
  } catch {
    return null;
  }
}

// ============================================================================
// Local MDX Functions (fallback)
// ============================================================================

/**
 * Reverse mapping: normalized category to possible folder names
 */
const CATEGORY_FOLDERS: Record<ArticleCategory, string[]> = {
  visas: ["immigration"],
  business: ["business", "business_regulations", "news"],
  taxes: ["tax-legal", "tax"],
  property: ["property"],
  living: ["lifestyle", "digital-nomad", "bali_news"],
  trends: ["emerging_trends", "tech", "social_media"],
};

async function getAllMdxSlugs(): Promise<
  { folderCategory: string; category: ArticleCategory; slug: string }[]
> {
  const slugs: {
    folderCategory: string;
    category: ArticleCategory;
    slug: string;
  }[] = [];

  if (!fs.existsSync(ARTICLES_PATH)) return slugs;

  const categories = ARTICLE_FOLDER_NAMES.filter((item) => {
    const itemPath = articleFolderPath(item);
    return fs.existsSync(itemPath) && fs.statSync(itemPath).isDirectory();
  });

  for (const folderCategory of categories) {
    const categoryPath = articleFolderPath(folderCategory);
    const files = fs
      .readdirSync(categoryPath)
      .filter(
        (file) =>
          file.endsWith(".mdx") &&
          !file.endsWith(".id.mdx") &&
          !file.endsWith(".it.mdx") &&
          !file.endsWith(".ru.mdx") &&
          !file.endsWith(".fr.mdx") &&
          !file.includes(".sync-conflict-"),
      );

    for (const file of files) {
      slugs.push({
        folderCategory,
        category: normalizeCategory(folderCategory),
        slug: file.replace(".mdx", ""),
      });
    }
  }

  return slugs;
}

async function getMdxArticleBySlug(
  category: string,
  slug: string,
): Promise<Article | null> {
  const normalizedCategory = normalizeCategory(category);
  const possibleFolders = CATEGORY_FOLDERS[normalizedCategory] || [category];

  let filePath = "";
  let actualFolderCategory = category;

  for (const folder of possibleFolders) {
    if (!isArticleFolderName(folder)) continue;
    const tryPath = articleMdxPath(folder, slug);
    if (fs.existsSync(tryPath)) {
      filePath = tryPath;
      actualFolderCategory = folder;
      break;
    }
  }

  if (!filePath && isArticleFolderName(category)) {
    const directPath = articleMdxPath(category, slug);
    if (fs.existsSync(directPath)) {
      filePath = directPath;
      actualFolderCategory = category;
    }
  }

  if (!filePath) return null;

  let fileContents: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let frontmatter: Record<string, any>;
  let content: string;
  try {
    fileContents = fs.readFileSync(filePath, "utf8");
    const parsed = matter(fileContents);
    frontmatter = parsed.data;
    content = parsed.content;
  } catch {
    // Skip articles with corrupted frontmatter (bad YAML)
    return null;
  }

  const author =
    typeof frontmatter.author === "object"
      ? frontmatter.author
      : {
          id: "zantara-ai",
          name: "Zantara AI",
          avatar: "/static/zantara-avatar.png",
          role: "AI Research Assistant",
          isAI: true,
        };

  return {
    id: frontmatter.id || slug,
    slug: frontmatter.slug || slug,
    title: frontmatter.title || "Untitled",
    subtitle: frontmatter.subtitle,
    excerpt: frontmatter.excerpt
      ? cleanExcerpt(frontmatter.excerpt)
      : extractBodyExcerpt(content),
    content: content,
    coverImage:
      frontmatter.coverImage ||
      frontmatter.image?.src ||
      `/static/blog/${actualFolderCategory}/${slug}.jpg`,
    cardImage:
      frontmatter.cardImage ||
      deriveCardImage(frontmatter.coverImage || frontmatter.image?.src),
    coverImageAlt:
      frontmatter.coverImageAlt || frontmatter.image?.alt || frontmatter.title,
    category: normalizeCategory(frontmatter.category || category),
    tags: normalizeTags(frontmatter.tags),
    author,
    createdAt: new Date(frontmatter.publishedAt || Date.now()),
    updatedAt: new Date(
      frontmatter.updatedAt || frontmatter.publishedAt || Date.now(),
    ),
    publishedAt: frontmatter.publishedAt
      ? new Date(frontmatter.publishedAt)
      : undefined,
    status: frontmatter.status || "published",
    featured: frontmatter.featured || false,
    trending: frontmatter.trending || false,
    seoTitle: frontmatter.seoTitle,
    seoDescription: frontmatter.seoDescription,
    readingTime:
      frontmatter.readingTime || Math.ceil(content.split(/\s+/).length / 200),
    viewCount: frontmatter.viewCount || 0,
    shareCount: frontmatter.shareCount || 0,
    likeCount: frontmatter.likeCount || 0,
    commentCount: frontmatter.commentCount || 0,
    aiGenerated: frontmatter.aiGenerated || false,
    aiConfidenceScore: frontmatter.aiConfidenceScore,
    aiOptimization: frontmatter.aiOptimization || undefined,
    faq: frontmatter.faq || undefined,
    contentStructure: frontmatter.contentStructure || undefined,
    relatedArticleIds: frontmatter.relatedArticles || [],
    locale: frontmatter.locale || "en",
    noIndex: frontmatter.noIndex || false,
  };
}

// ============================================================================
// Public API (Hybrid: Backend + MDX)
// ============================================================================

/**
 * Get all article slugs grouped by category (MDX only, for sitemap/feed)
 */
export async function getAllArticleSlugs(): Promise<
  { folderCategory: string; category: ArticleCategory; slug: string }[]
> {
  return getAllMdxSlugs();
}

/**
 * Get a single article by category and slug
 * Tries backend first, then MDX fallback
 */
export async function getArticleBySlug(
  category: string,
  slug: string,
): Promise<Article | null> {
  // Try backend API first
  const backendItem = await fetchBackendArticleBySlug(slug);
  if (backendItem) {
    return backendToArticle(backendItem);
  }

  // Fallback to local MDX
  return getMdxArticleBySlug(category, slug);
}

/**
 * Get an article in a specific locale.
 * Looks for {slug}.{locale}.mdx, falls back to {slug}.mdx (English).
 */
export async function getArticleByLocale(
  category: string,
  slug: string,
  locale: string,
): Promise<Article | null> {
  if (!locale || locale === "en") {
    return getArticleBySlug(category, slug);
  }

  // Try locale-specific MDX file
  const normalizedCategory = normalizeCategory(category);
  const possibleFolders = CATEGORY_FOLDERS[normalizedCategory] || [category];

  for (const folder of possibleFolders) {
    if (!isArticleFolderName(folder)) continue;
    const localePath = articleLocaleMdxPath(folder, slug, locale);
    if (fs.existsSync(localePath)) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      let frontmatter: Record<string, any>;
      let content: string;
      try {
        const fileContents = fs.readFileSync(localePath, "utf8");
        const parsed = matter(fileContents);
        frontmatter = parsed.data;
        content = parsed.content;
      } catch {
        // Skip locale files with corrupted frontmatter
        continue;
      }

      const author =
        typeof frontmatter.author === "object"
          ? frontmatter.author
          : {
              id: "zantara-ai",
              name: "Zantara AI",
              avatar: "/static/zantara-avatar.png",
              role: "AI Research Assistant",
              isAI: true,
            };

      return {
        id: frontmatter.id || slug,
        slug: frontmatter.slug || slug,
        title: frontmatter.title || "Untitled",
        subtitle: frontmatter.subtitle,
        excerpt: frontmatter.excerpt
          ? cleanExcerpt(frontmatter.excerpt)
          : extractBodyExcerpt(content),
        content,
        coverImage:
          frontmatter.coverImage ||
          frontmatter.image?.src ||
          `/static/blog/${folder}/${slug}.jpg`,
        cardImage:
          frontmatter.cardImage ||
          deriveCardImage(frontmatter.coverImage || frontmatter.image?.src),
        coverImageAlt:
          frontmatter.coverImageAlt ||
          frontmatter.image?.alt ||
          frontmatter.title,
        category: normalizeCategory(frontmatter.category || category),
        tags: normalizeTags(frontmatter.tags),
        author,
        createdAt: new Date(frontmatter.publishedAt || Date.now()),
        updatedAt: new Date(
          frontmatter.updatedAt || frontmatter.publishedAt || Date.now(),
        ),
        publishedAt: frontmatter.publishedAt
          ? new Date(frontmatter.publishedAt)
          : undefined,
        status: frontmatter.status || "published",
        featured: frontmatter.featured || false,
        trending: frontmatter.trending || false,
        seoTitle: frontmatter.seoTitle,
        seoDescription: frontmatter.seoDescription,
        readingTime:
          frontmatter.readingTime ||
          Math.ceil(content.split(/\s+/).length / 200),
        viewCount: frontmatter.viewCount || 0,
        shareCount: frontmatter.shareCount || 0,
        likeCount: frontmatter.likeCount || 0,
        commentCount: frontmatter.commentCount || 0,
        aiGenerated: frontmatter.aiGenerated || false,
        aiConfidenceScore: frontmatter.aiConfidenceScore,
        aiOptimization: frontmatter.aiOptimization || undefined,
        faq: frontmatter.faq || undefined,
        contentStructure: frontmatter.contentStructure || undefined,
        relatedArticleIds: frontmatter.relatedArticles || [],
        locale:
          (frontmatter.locale as "en" | "id" | "it" | "ru" | "fr") ||
          (locale as "en" | "id" | "it" | "ru" | "fr"),
        noIndex: frontmatter.noIndex || false,
      };
    }
  }

  // Fallback to English
  return getArticleBySlug(category, slug);
}

/**
 * Check which locales are available for a given article slug.
 * Returns an array of available locale codes.
 */
export function getAvailableLocales(category: string, slug: string): string[] {
  const locales = ["en"]; // English always available
  const normalizedCategory = normalizeCategory(category);
  const possibleFolders = CATEGORY_FOLDERS[normalizedCategory] || [category];

  for (const locale of ["id", "it", "ru", "fr"] as const) {
    for (const folder of possibleFolders) {
      if (!isArticleFolderName(folder)) continue;
      const localePath = articleLocaleMdxPath(folder, slug, locale);
      if (fs.existsSync(localePath)) {
        locales.push(locale);
        break;
      }
    }
  }

  return locales;
}

/**
 * Get all articles with optional filtering
 * Merges backend API articles + local MDX articles, deduped by slug
 * Cached with ISR - revalidates every 60 seconds
 */
export const getAllArticles = unstable_cache(
  async (options?: {
    category?: string;
    featured?: boolean;
    limit?: number;
    offset?: number;
  }): Promise<{ articles: ArticleListItem[]; total: number }> => {
    const allArticles: ArticleListItem[] = [];
    const seenSlugs = new Set<string>();

    // 1. Fetch from backend API (priority)
    const backendResult = await fetchBackendArticles({
      category: options?.category,
      limit: 100, // fetch more, we'll merge with MDX
    });

    if (backendResult) {
      for (const item of backendResult.items) {
        const listItem = backendToArticleListItem(item);
        if (
          options?.featured !== undefined &&
          listItem.featured !== options.featured
        ) {
          continue;
        }
        allArticles.push(listItem);
        seenSlugs.add(item.slug);
      }
    }

    // 2. Add MDX articles not already in backend (dedup by slug)
    const allSlugs = await getAllMdxSlugs();
    let filteredSlugs = options?.category
      ? allSlugs.filter((s) => s.category === options.category)
      : allSlugs;

    for (const { folderCategory, slug } of filteredSlugs) {
      if (seenSlugs.has(slug)) continue;

      const article = await getMdxArticleBySlug(folderCategory, slug);
      if (!article) continue;

      if (
        options?.featured !== undefined &&
        article.featured !== options.featured
      ) {
        continue;
      }

      allArticles.push({
        id: article.id,
        slug: article.slug,
        title: article.title,
        excerpt: article.excerpt,
        coverImage: article.coverImage,
        category: article.category,
        author: article.author,
        publishedAt: article.publishedAt || article.createdAt,
        readingTime: article.readingTime,
        viewCount: article.viewCount,
        featured: article.featured,
        trending: article.trending,
        aiGenerated: article.aiGenerated,
      });
      seenSlugs.add(slug);
    }

    // Sort by publishedAt descending
    allArticles.sort((a, b) => {
      const dateA = new Date(a.publishedAt).getTime();
      const dateB = new Date(b.publishedAt).getTime();
      return dateB - dateA;
    });

    const total = allArticles.length;

    // Apply pagination
    let result = allArticles;
    if (options?.offset) {
      result = result.slice(options.offset);
    }
    if (options?.limit) {
      result = result.slice(0, options.limit);
    }

    return { articles: result, total };
  },
  ["articles"],
  {
    tags: ["articles"],
    revalidate: 60,
  },
);

/**
 * Get featured articles
 */
export async function getFeaturedArticles(
  limit = 6,
): Promise<ArticleListItem[]> {
  const { articles } = await getAllArticles({ featured: true, limit });
  return articles;
}

/**
 * Get articles by category
 */
export async function getArticlesByCategory(
  category: string,
  limit = 20,
  offset = 0,
): Promise<{ articles: ArticleListItem[]; total: number }> {
  return getAllArticles({ category, limit, offset });
}

/**
 * Get category counts (uses normalized categories)
 */
export async function getCategoryCounts(): Promise<
  Record<ArticleCategory, number>
> {
  const { articles } = await getAllArticles({ limit: 500 });
  const counts: Record<string, number> = {};

  for (const article of articles) {
    counts[article.category] = (counts[article.category] || 0) + 1;
  }

  return counts as Record<ArticleCategory, number>;
}

/**
 * Get set of slugs marked as noIndex (for sitemap exclusion)
 * Only checks MDX articles since backend articles don't have noIndex
 */
export async function getNoIndexSlugs(): Promise<Set<string>> {
  const noIndexSlugs = new Set<string>();
  const allSlugs = await getAllMdxSlugs();

  for (const { folderCategory, slug } of allSlugs) {
    try {
      if (!isArticleFolderName(folderCategory)) continue;
      const filePath = articleMdxPath(folderCategory, slug);
      if (!fs.existsSync(filePath)) continue;
      const fileContents = fs.readFileSync(filePath, "utf8");
      const { data: frontmatter } = matter(fileContents);
      if (frontmatter.noIndex) {
        noIndexSlugs.add(slug);
      }
    } catch {
      // Skip articles that can't be read
    }
  }

  return noIndexSlugs;
}

/**
 * Search articles by query
 * Tries backend search first, then falls back to in-memory filtering
 */
export async function searchArticles(
  query: string,
  limit = 20,
): Promise<ArticleListItem[]> {
  // Try backend search
  const backendResult = await fetchBackendArticles({
    search: query,
    limit,
  });

  if (backendResult && backendResult.items.length > 0) {
    return backendResult.items.map(backendToArticleListItem);
  }

  // Fallback to in-memory MDX search
  const { articles } = await getAllArticles({ limit: 200 });
  const lowerQuery = query.toLowerCase();

  const results = articles.filter((article) => {
    return (
      article.title.toLowerCase().includes(lowerQuery) ||
      article.excerpt.toLowerCase().includes(lowerQuery)
    );
  });

  return results.slice(0, limit);
}

// ─── Homepage layout slug-drift guard ───────────────────────────────────────
// The homepage curates hero_main..hero_N + latest_1..N (+ insight_*) slugs in
// content/homepage-layout.json, resolved against getAllArticles() in
// (marketing)/page.tsx with a silent `.filter(Boolean)`. A deleted/renamed
// slug therefore silently drops with NO signal — and Next.js notFound() returns
// HTTP 200, so status-only monitoring also misses it. This guard makes the
// drift LOUD at build/test time. (Antonello flagged 2026-06-11.)

/** Keys in homepage-layout.json that hold a curated article slug. Non-slug
 *  metadata keys (anything starting with `_`, e.g. `_comment`) are ignored. */
function isCuratedSlugKey(key: string): boolean {
  return !key.startsWith("_");
}

export interface HomepageLayoutValidation {
  ok: boolean;
  /** [layoutKey, slug] pairs whose slug does not resolve to a real article. */
  missing: { key: string; slug: string }[];
  checked: number;
}

/**
 * Pure validator: assert every curated slug in `layout` resolves to a real
 * article slug in `knownSlugs`. No I/O — feed it a fixture in tests or the
 * real MDX slug index (via {@link validateHomepageLayoutFromDisk}) in CI.
 */
export function validateHomepageLayout(
  layout: Record<string, unknown>,
  knownSlugs: Iterable<string>,
): HomepageLayoutValidation {
  const slugSet = new Set(knownSlugs);
  const missing: { key: string; slug: string }[] = [];
  let checked = 0;

  for (const [key, value] of Object.entries(layout)) {
    if (!isCuratedSlugKey(key)) continue;
    if (typeof value !== "string" || value.length === 0) continue;
    checked += 1;
    if (!slugSet.has(value)) {
      missing.push({ key, slug: value });
    }
  }

  return { ok: missing.length === 0, missing, checked };
}

/**
 * Offline/deterministic CI helper: validate `layout` against the canonical
 * MDX slug index on disk (no network, no backend). Throws with a readable
 * message listing every drifted slug so a build/test fails loudly.
 */
export async function validateHomepageLayoutFromDisk(
  layout: Record<string, unknown>,
): Promise<HomepageLayoutValidation> {
  const slugs = await getAllMdxSlugs();
  const result = validateHomepageLayout(
    layout,
    slugs.map((s) => s.slug),
  );
  if (!result.ok) {
    const detail = result.missing
      .map((m) => `  - ${m.key}: "${m.slug}"`)
      .join("\n");
    throw new Error(
      `homepage-layout.json references ${result.missing.length} ` +
        `slug(s) that no longer resolve to a real article:\n${detail}\n` +
        `Fix the slug(s) in apps/mouth/src/content/homepage-layout.json.`,
    );
  }
  return result;
}
