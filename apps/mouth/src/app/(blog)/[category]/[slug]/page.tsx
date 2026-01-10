import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { getArticleBySlug } from '@/lib/blog/articles';
import { generateArticleMetadata } from '@/lib/blog/metadata';
import { ArticleClient } from './ArticleClient';

interface PageProps {
  params: Promise<{
    category: string;
    slug: string;
  }>;
}

// Static file paths that should NOT be handled by this route
// 'images' included for backward compatibility (old URLs should 404, not render broken page)
const STATIC_PATHS = ['static', 'assets', 'fonts', '_next', 'api', 'images', 'avatars', 'blueprints', 'videos'];

// Valid blog categories
const VALID_CATEGORIES = ['immigration', 'business', 'tax-legal', 'property', 'lifestyle', 'digital-nomad', 'tech'];

/**
 * Check if this request is for a static file (should return 404 to let Next.js serve static)
 */
function isStaticFilePath(category: string, slug: string): boolean {
  // If category is a known static path, reject
  if (STATIC_PATHS.includes(category)) return true;
  // If slug has a file extension, reject
  if (slug.includes('.')) return true;
  return false;
}

/**
 * Generate dynamic metadata for SEO
 * This runs on the server and provides metadata to Google, social media, and AI crawlers
 */
export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { category, slug } = await params;

  // Reject static file paths - let Next.js serve them from /public
  if (isStaticFilePath(category, slug)) {
    return { title: 'Not Found' };
  }

  try {
    const article = await getArticleBySlug(category, slug);

    if (article) {
      return generateArticleMetadata(article);
    }
  } catch (error) {
    console.error('Error generating metadata:', error);
  }

  // Fallback metadata
  return {
    title: `${slug.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase())} | Bali Zero`,
    description: `Learn about ${slug.replace(/-/g, ' ')} in Indonesia. Expert guides from Bali Zero.`,
  };
}

/**
 * Article page - Server component that renders the client component
 */
export default async function ArticlePage({ params }: PageProps) {
  const { category, slug } = await params;

  // Reject static file paths - return 404 so Next.js can serve from /public
  if (isStaticFilePath(category, slug)) {
    notFound();
  }

  return <ArticleClient category={category} slug={slug} />;
}
