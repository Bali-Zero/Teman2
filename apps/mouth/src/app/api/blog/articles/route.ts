import { NextRequest, NextResponse } from 'next/server';
import type { ArticleCategory, ArticleSearchParams } from '@/lib/blog/types';
import { getAllArticles, searchArticles, getCategoryCounts } from '@/lib/blog/articles';

/**
 * GET /api/blog/articles
 * List articles with optional filtering from local MDX files
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);

    // Build query params
    const query = searchParams.get('q') || undefined;
    const category = searchParams.get('category') || undefined;
    const featured = searchParams.get('featured') === 'true' ? true : undefined;
    const limit = parseInt(searchParams.get('limit') || '12');
    const offset = parseInt(searchParams.get('offset') || '0');

    // If search query, use search function
    if (query) {
      const articles = await searchArticles(query, limit);
      return NextResponse.json({
        articles,
        total: articles.length,
        hasMore: false,
      });
    }

    // Otherwise, get all articles with filters
    const { articles, total } = await getAllArticles({
      category,
      featured,
      limit,
      offset,
    });

    return NextResponse.json({
      articles,
      total,
      hasMore: offset + articles.length < total,
    });
  } catch (error) {
    console.error('Failed to fetch articles:', error);

    // Return mock data as fallback
    return NextResponse.json({
      articles: MOCK_ARTICLES,
      total: MOCK_ARTICLES.length,
      hasMore: false,
    });
  }
}

/**
 * POST /api/blog/articles
 * Create a new article - Not implemented for static MDX files
 */
export async function POST(_request: NextRequest) {
  return NextResponse.json(
    { error: 'Article creation not supported via API. Create MDX file directly in src/content/articles/[category]/' },
    { status: 501 }
  );
}

// Mock data for development/fallback
const MOCK_ARTICLES = [
  {
    id: '1',
    slug: 'golden-visa-revolution',
    title: "The Golden Visa Revolution: Indonesia's $350K Bet on Global Talent",
    excerpt: 'Indonesia launches its Golden Visa program, offering 5-10 year stays for investors.',
    coverImage: '/static/blog/golden-visa.jpg',
    category: 'immigration',
    author: {
      id: 'zantara-ai',
      name: 'Zantara AI',
      avatar: '/static/zantara-avatar.png',
      role: 'AI Research Assistant',
      isAI: true,
    },
    publishedAt: new Date().toISOString(),
    readingTime: 12,
    viewCount: 15420,
    featured: true,
    trending: true,
    aiGenerated: true,
  },
  {
    id: '2',
    slug: 'oss-2-complete-guide',
    title: 'OSS 2.0: The Complete Guide to Indonesia Business Licensing',
    excerpt: 'Everything about the Online Single Submission system for company registration.',
    coverImage: '/static/blog/oss-guide.jpg',
    category: 'business',
    author: {
      id: '1',
      name: 'Legal Team',
      avatar: '/static/team/legal.jpg',
      role: 'Legal Advisor',
      isAI: false,
    },
    publishedAt: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    readingTime: 15,
    viewCount: 8932,
    featured: false,
    trending: true,
    aiGenerated: false,
  },
  {
    id: '3',
    slug: 'tax-deadlines-2026',
    title: 'Tax Deadlines 2026: What Every Expat Needs to Know',
    excerpt: 'Key dates for personal and corporate tax filings. New Coretax system fully operational.',
    coverImage: '/static/blog/tax-calendar.jpg',
    category: 'tax-legal',
    author: {
      id: 'zantara-ai',
      name: 'Zantara AI',
      avatar: '/static/zantara-avatar.png',
      role: 'AI Research Assistant',
      isAI: true,
    },
    publishedAt: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
    readingTime: 8,
    viewCount: 6234,
    featured: false,
    trending: false,
    aiGenerated: true,
  },
];
