/**
 * Blog Article Reader - Reads MDX articles from filesystem
 * For Nuzantara/Bali Zero Insights Blog
 */

import fs from 'fs';
import path from 'path';
import matter from 'gray-matter';
import type { Article, ArticleListItem, ArticleCategory } from './types';

const ARTICLES_PATH = path.join(process.cwd(), 'src/content/articles');

/**
 * Map folder/frontmatter categories to valid ArticleCategory
 * This handles legacy naming and folder structure differences
 */
const CATEGORY_MAP: Record<string, ArticleCategory> = {
  'immigration': 'immigration',
  'business': 'business',
  'tax': 'tax-legal',
  'tax-legal': 'tax-legal',
  'property': 'property',
  'lifestyle': 'lifestyle',
  'digital-nomad': 'lifestyle', // Map digital-nomad to lifestyle
  'tech': 'tech',
};

function normalizeCategory(rawCategory: string): ArticleCategory {
  return CATEGORY_MAP[rawCategory] || 'lifestyle';
}

/**
 * Get all article slugs grouped by category
 * Returns both the folder category (for file path) and normalized category (for filtering)
 */
export async function getAllArticleSlugs(): Promise<{ folderCategory: string; category: ArticleCategory; slug: string }[]> {
  const slugs: { folderCategory: string; category: ArticleCategory; slug: string }[] = [];

  const categories = fs.readdirSync(ARTICLES_PATH).filter(item => {
    const itemPath = path.join(ARTICLES_PATH, item);
    return fs.statSync(itemPath).isDirectory() && !item.startsWith('.');
  });

  for (const folderCategory of categories) {
    const categoryPath = path.join(ARTICLES_PATH, folderCategory);
    const files = fs.readdirSync(categoryPath).filter(file => file.endsWith('.mdx'));

    for (const file of files) {
      slugs.push({
        folderCategory,
        category: normalizeCategory(folderCategory),
        slug: file.replace('.mdx', ''),
      });
    }
  }

  return slugs;
}

/**
 * Reverse mapping: normalized category to possible folder names
 * Some articles might be stored in legacy folder names
 */
const CATEGORY_FOLDERS: Record<ArticleCategory, string[]> = {
  'immigration': ['immigration'],
  'business': ['business'],
  'tax-legal': ['tax-legal', 'tax'], // Try tax-legal first, then tax
  'property': ['property'],
  'lifestyle': ['lifestyle', 'digital-nomad'], // Try lifestyle first, then digital-nomad
  'tech': ['tech'],
};

/**
 * Get a single article by category and slug
 * Handles both normalized categories (from URLs) and folder categories (for file lookup)
 */
export async function getArticleBySlug(
  category: string,
  slug: string
): Promise<Article | null> {
  // Get possible folder paths for this category
  const normalizedCategory = normalizeCategory(category);
  const possibleFolders = CATEGORY_FOLDERS[normalizedCategory] || [category];

  let filePath = '';
  let actualFolderCategory = category;

  // Try each possible folder
  for (const folder of possibleFolders) {
    const tryPath = path.join(ARTICLES_PATH, folder, `${slug}.mdx`);
    if (fs.existsSync(tryPath)) {
      filePath = tryPath;
      actualFolderCategory = folder;
      break;
    }
  }

  // Also try the exact category path (for direct folder access)
  if (!filePath) {
    const directPath = path.join(ARTICLES_PATH, category, `${slug}.mdx`);
    if (fs.existsSync(directPath)) {
      filePath = directPath;
      actualFolderCategory = category;
    }
  }

  if (!filePath) {
    return null;
  }

  const fileContents = fs.readFileSync(filePath, 'utf8');
  const { data: frontmatter, content } = matter(fileContents);

  // Parse author from frontmatter
  const author = typeof frontmatter.author === 'object' ? frontmatter.author : {
    id: 'zantara-ai',
    name: 'Zantara AI',
    avatar: '/images/zantara-avatar.png',
    role: 'AI Research Assistant',
    isAI: true,
  };

  const article: Article = {
    id: frontmatter.id || slug,
    slug: frontmatter.slug || slug,
    title: frontmatter.title || 'Untitled',
    subtitle: frontmatter.subtitle,
    excerpt: frontmatter.excerpt || '',
    content: content,
    coverImage: frontmatter.coverImage || frontmatter.image?.src || `/images/blog/${actualFolderCategory}/${slug}.jpg`,
    coverImageAlt: frontmatter.coverImageAlt || frontmatter.image?.alt || frontmatter.title,
    category: normalizeCategory(frontmatter.category || category),
    tags: frontmatter.tags || [],
    author,
    createdAt: new Date(frontmatter.publishedAt || Date.now()),
    updatedAt: new Date(frontmatter.updatedAt || frontmatter.publishedAt || Date.now()),
    publishedAt: frontmatter.publishedAt ? new Date(frontmatter.publishedAt) : undefined,
    status: frontmatter.status || 'published',
    featured: frontmatter.featured || false,
    trending: frontmatter.trending || false,
    seoTitle: frontmatter.seoTitle,
    seoDescription: frontmatter.seoDescription,
    readingTime: frontmatter.readingTime || Math.ceil(content.split(/\s+/).length / 200),
    viewCount: frontmatter.viewCount || 0,
    shareCount: frontmatter.shareCount || 0,
    aiGenerated: frontmatter.aiGenerated || false,
    aiConfidenceScore: frontmatter.aiConfidenceScore,
    relatedArticleIds: frontmatter.relatedArticles || [],
    locale: frontmatter.locale || 'en',
  };

  return article;
}

/**
 * Get all articles with optional filtering
 */
export async function getAllArticles(options?: {
  category?: string;
  featured?: boolean;
  limit?: number;
  offset?: number;
}): Promise<{ articles: ArticleListItem[]; total: number }> {
  const allSlugs = await getAllArticleSlugs();

  // Filter by category if specified (uses normalized category)
  let filteredSlugs = options?.category
    ? allSlugs.filter(s => s.category === options.category)
    : allSlugs;

  const total = filteredSlugs.length;

  // Apply pagination
  if (options?.offset) {
    filteredSlugs = filteredSlugs.slice(options.offset);
  }
  if (options?.limit) {
    filteredSlugs = filteredSlugs.slice(0, options.limit);
  }

  const articles: ArticleListItem[] = [];

  for (const { folderCategory, slug } of filteredSlugs) {
    // Use folderCategory for file path lookup
    const article = await getArticleBySlug(folderCategory, slug);
    if (article) {
      // Filter by featured if specified
      if (options?.featured !== undefined && article.featured !== options.featured) {
        continue;
      }

      articles.push({
        id: article.id,
        slug: article.slug,
        title: article.title,
        excerpt: article.excerpt,
        coverImage: article.coverImage,
        category: article.category, // Already normalized in getArticleBySlug
        author: article.author,
        publishedAt: article.publishedAt || article.createdAt,
        readingTime: article.readingTime,
        viewCount: article.viewCount,
        featured: article.featured,
        trending: article.trending,
        aiGenerated: article.aiGenerated,
      });
    }
  }

  // Sort by publishedAt descending
  articles.sort((a, b) => {
    const dateA = new Date(a.publishedAt).getTime();
    const dateB = new Date(b.publishedAt).getTime();
    return dateB - dateA;
  });

  return { articles, total };
}

/**
 * Get featured articles
 */
export async function getFeaturedArticles(limit = 6): Promise<ArticleListItem[]> {
  const { articles } = await getAllArticles({ featured: true, limit });
  return articles;
}

/**
 * Get articles by category
 */
export async function getArticlesByCategory(
  category: string,
  limit = 20,
  offset = 0
): Promise<{ articles: ArticleListItem[]; total: number }> {
  return getAllArticles({ category, limit, offset });
}

/**
 * Get category counts (uses normalized categories)
 */
export async function getCategoryCounts(): Promise<Record<ArticleCategory, number>> {
  const allSlugs = await getAllArticleSlugs();
  const counts: Record<string, number> = {};

  for (const { category } of allSlugs) {
    // category is already normalized in getAllArticleSlugs
    counts[category] = (counts[category] || 0) + 1;
  }

  return counts as Record<ArticleCategory, number>;
}

/**
 * Search articles by query
 */
export async function searchArticles(
  query: string,
  limit = 20
): Promise<ArticleListItem[]> {
  const { articles } = await getAllArticles({ limit: 200 }); // Get more for search
  const lowerQuery = query.toLowerCase();

  const results = articles.filter(article => {
    return (
      article.title.toLowerCase().includes(lowerQuery) ||
      article.excerpt.toLowerCase().includes(lowerQuery)
    );
  });

  return results.slice(0, limit);
}
