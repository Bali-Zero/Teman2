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
    excerpt: item.summary || item.ai_summary || "",
    coverImage:
      item.image_url || `/static/blog/${item.category}/${item.slug}.jpg`,
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
    excerpt: item.summary || item.ai_summary || "",
    content: item.content || "",
    coverImage:
      item.image_url || `/static/blog/${item.category}/${item.slug}.jpg`,
    coverImageAlt: item.title,
    category: normalizeCategory(item.category),
    tags: item.ai_tags || [],
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
  living: ["lifestyle", "living"],
  trends: ["trends"],
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

  const categories = fs.readdirSync(ARTICLES_PATH).filter((item) => {
    const itemPath = path.join(ARTICLES_PATH, item);
    return fs.statSync(itemPath).isDirectory() && !item.startsWith(".");
  });

  for (const folderCategory of categories) {
    const categoryPath = path.join(ARTICLES_PATH, folderCategory);
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
    const tryPath = path.join(ARTICLES_PATH, folder, `${slug}.mdx`);
    if (fs.existsSync(tryPath)) {
      filePath = tryPath;
      actualFolderCategory = folder;
      break;
    }
  }

  if (!filePath) {
    const directPath = path.join(ARTICLES_PATH, category, `${slug}.mdx`);
    if (fs.existsSync(directPath)) {
      filePath = directPath;
      actualFolderCategory = category;
    }
  }

  if (!filePath) return null;

  const fileContents = fs.readFileSync(filePath, "utf8");
  const { data: frontmatter, content } = matter(fileContents);

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
    excerpt: frontmatter.excerpt || "",
    content: content,
    coverImage:
      frontmatter.coverImage ||
      frontmatter.image?.src ||
      `/static/blog/${actualFolderCategory}/${slug}.jpg`,
    coverImageAlt:
      frontmatter.coverImageAlt || frontmatter.image?.alt || frontmatter.title,
    category: normalizeCategory(frontmatter.category || category),
    tags: frontmatter.tags || [],
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
    const localePath = path.join(
      ARTICLES_PATH,
      folder,
      `${slug}.${locale}.mdx`,
    );
    if (fs.existsSync(localePath)) {
      const fileContents = fs.readFileSync(localePath, "utf8");
      const { data: frontmatter, content } = matter(fileContents);

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
        excerpt: frontmatter.excerpt || "",
        content,
        coverImage:
          frontmatter.coverImage ||
          frontmatter.image?.src ||
          `/static/blog/${folder}/${slug}.jpg`,
        coverImageAlt:
          frontmatter.coverImageAlt ||
          frontmatter.image?.alt ||
          frontmatter.title,
        category: normalizeCategory(frontmatter.category || category),
        tags: frontmatter.tags || [],
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
      const localePath = path.join(
        ARTICLES_PATH,
        folder,
        `${slug}.${locale}.mdx`,
      );
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
      const filePath = path.join(ARTICLES_PATH, folderCategory, `${slug}.mdx`);
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
