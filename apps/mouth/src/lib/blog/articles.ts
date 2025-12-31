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
 * Get all article slugs grouped by category
 */
export async function getAllArticleSlugs(): Promise<{ category: string; slug: string }[]> {
  const slugs: { category: string; slug: string }[] = [];

  const categories = fs.readdirSync(ARTICLES_PATH).filter(item => {
    const itemPath = path.join(ARTICLES_PATH, item);
    return fs.statSync(itemPath).isDirectory() && !item.startsWith('.');
  });

  for (const category of categories) {
    const categoryPath = path.join(ARTICLES_PATH, category);
    const files = fs.readdirSync(categoryPath).filter(file => file.endsWith('.mdx'));

    for (const file of files) {
      slugs.push({
        category,
        slug: file.replace('.mdx', ''),
      });
    }
  }

  return slugs;
}

/**
 * Get a single article by category and slug
 */
export async function getArticleBySlug(
  category: string,
  slug: string
): Promise<Article | null> {
  const filePath = path.join(ARTICLES_PATH, category, `${slug}.mdx`);

  if (!fs.existsSync(filePath)) {
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
    coverImage: frontmatter.coverImage || `/images/blog/${category}/${slug}.jpg`,
    coverImageAlt: frontmatter.coverImageAlt || frontmatter.title,
    category: (frontmatter.category || category) as ArticleCategory,
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

  // Filter by category if specified
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

  for (const { category, slug } of filteredSlugs) {
    const article = await getArticleBySlug(category, slug);
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
        category: article.category,
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
 * Get category counts
 */
export async function getCategoryCounts(): Promise<Record<string, number>> {
  const allSlugs = await getAllArticleSlugs();
  const counts: Record<string, number> = {};

  for (const { category } of allSlugs) {
    counts[category] = (counts[category] || 0) + 1;
  }

  return counts;
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
