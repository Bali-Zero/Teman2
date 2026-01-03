import type { Metadata } from 'next';
import { getArticleBySlug } from '@/lib/blog/articles';
import { generateArticleMetadata } from '@/lib/blog/metadata';
import { ArticleClient } from './ArticleClient';

interface PageProps {
  params: Promise<{
    category: string;
    slug: string;
  }>;
}

/**
 * Generate dynamic metadata for SEO
 * This runs on the server and provides metadata to Google, social media, and AI crawlers
 */
export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { category, slug } = await params;

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

  return <ArticleClient category={category} slug={slug} />;
}
