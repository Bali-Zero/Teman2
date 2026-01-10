/**
 * Blog Metadata Generation
 * SEO-optimized metadata for articles and category pages
 */

import type { Metadata } from 'next';
import type { Article } from './types';

const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || 'https://balizero.com';

// Category metadata
const CATEGORY_META: Record<string, { title: string; description: string; keywords: string[] }> = {
  immigration: {
    title: 'Indonesia Visa & Immigration Guides',
    description: 'Expert guides on Indonesia visas: KITAS, KITAP, Golden Visa, work permits, retirement visa, digital nomad visa. Updated 2026 requirements and processes.',
    keywords: ['indonesia visa', 'kitas', 'kitap', 'work permit indonesia', 'golden visa indonesia', 'retirement visa bali'],
  },
  business: {
    title: 'Starting a Business in Indonesia',
    description: 'Complete guides to PT PMA company setup, business licenses, OSS registration, capital requirements. Expert advice for foreign entrepreneurs.',
    keywords: ['pt pma', 'company setup indonesia', 'business license bali', 'oss registration', 'foreign investment indonesia'],
  },
  'tax-legal': {
    title: 'Indonesia Tax & Legal Guides',
    description: 'Tax compliance guides for expats and businesses in Indonesia. Personal tax, corporate tax, Coretax system, tax deadlines, legal requirements.',
    keywords: ['indonesia tax', 'expat tax indonesia', 'corporate tax indonesia', 'coretax', 'tax deadline indonesia'],
  },
  property: {
    title: 'Property Investment in Bali & Indonesia',
    description: 'Property guides for foreigners: Hak Pakai, leasehold, villa investment, Airbnb regulations, buying property in Bali. Expert real estate advice.',
    keywords: ['property bali', 'villa investment bali', 'foreigner property indonesia', 'hak pakai', 'airbnb bali'],
  },
  lifestyle: {
    title: 'Living in Bali - Expat Lifestyle Guides',
    description: 'Guides for living in Bali: cost of living, healthcare, banking, culture, digital nomad life, expat community. Everything you need to know.',
    keywords: ['living in bali', 'expat bali', 'cost of living bali', 'digital nomad bali', 'bali lifestyle'],
  },
  'digital-nomad': {
    title: 'Digital Nomad Life in Bali',
    description: 'Complete guide for digital nomads in Bali: visa options, coworking spaces, internet, banking, community. Work remotely from paradise.',
    keywords: ['digital nomad bali', 'remote work indonesia', 'coworking bali', 'digital nomad visa'],
  },
};

/**
 * Generate metadata for an article
 */
export function generateArticleMetadata(article: Article): Metadata {
  const articleUrl = `${baseUrl}/${article.category}/${article.slug}`;
  const imageUrl = article.coverImage?.startsWith('http')
    ? article.coverImage
    : `${baseUrl}${article.coverImage || '/static/og-image.jpg'}`;

  // Build keywords from tags and category
  const keywords = [
    ...article.tags,
    article.category,
    'bali',
    'indonesia',
    'bali zero',
  ];

  return {
    title: article.title,
    description: article.excerpt || article.subtitle || article.title,
    keywords: keywords,
    authors: [{ name: article.author.name }],
    openGraph: {
      type: 'article',
      locale: 'en_US',
      url: articleUrl,
      title: article.title,
      description: article.excerpt || article.subtitle || article.title,
      siteName: 'Bali Zero',
      images: [
        {
          url: imageUrl,
          width: 1200,
          height: 630,
          alt: article.coverImageAlt || article.title,
        },
      ],
      publishedTime: article.publishedAt?.toString(),
      modifiedTime: article.updatedAt?.toString(),
      authors: [article.author.name],
      section: article.category,
      tags: article.tags,
    },
    twitter: {
      card: 'summary_large_image',
      title: article.title,
      description: article.excerpt || article.subtitle || article.title,
      images: [imageUrl],
      creator: '@balizero',
    },
    alternates: {
      canonical: articleUrl,
    },
    robots: {
      index: true,
      follow: true,
      googleBot: {
        index: true,
        follow: true,
        'max-video-preview': -1,
        'max-image-preview': 'large',
        'max-snippet': -1,
      },
    },
  };
}

/**
 * Generate metadata for a category page
 */
export function generateCategoryMetadata(category: string): Metadata {
  const meta = CATEGORY_META[category] || {
    title: `${category.charAt(0).toUpperCase() + category.slice(1)} Insights`,
    description: `Expert guides and insights about ${category} in Indonesia and Bali.`,
    keywords: [category, 'indonesia', 'bali', 'guide'],
  };

  const categoryUrl = `${baseUrl}/${category}`;

  return {
    title: meta.title,
    description: meta.description,
    keywords: meta.keywords,
    openGraph: {
      type: 'website',
      locale: 'en_US',
      url: categoryUrl,
      title: `${meta.title} | Bali Zero`,
      description: meta.description,
      siteName: 'Bali Zero',
      images: [
        {
          url: `${baseUrl}/static/og-image.jpg`,
          width: 1200,
          height: 630,
          alt: meta.title,
        },
      ],
    },
    twitter: {
      card: 'summary_large_image',
      title: meta.title,
      description: meta.description,
      creator: '@balizero',
    },
    alternates: {
      canonical: categoryUrl,
    },
  };
}

/**
 * Generate metadata for insights home
 */
export function generateInsightsMetadata(): Metadata {
  return {
    title: 'Bali Zero | Visa, Business & Immigration Experts in Bali, Indonesia',
    description: 'Expert guides on Indonesia visas, company setup, tax compliance, property investment, and expat life in Bali. Updated 2026 information from Bali Zero.',
    keywords: [
      'indonesia visa guide',
      'bali business',
      'pt pma setup',
      'expat indonesia',
      'living in bali',
      'indonesia immigration',
      'bali zero',
    ],
    openGraph: {
      type: 'website',
      locale: 'en_US',
      url: baseUrl,
      title: 'Bali Zero | Visa & Business Experts in Bali',
      description: 'Expert guides on Indonesia visas, business, tax, and life in Bali.',
      siteName: 'Bali Zero',
      images: [
        {
          url: `${baseUrl}/static/og-image.jpg`,
          width: 1200,
          height: 630,
          alt: 'Bali Zero - Visa & Business Experts',
        },
      ],
    },
    twitter: {
      card: 'summary_large_image',
      title: 'Bali Zero | Visa & Business Experts in Bali',
      description: 'Expert guides on Indonesia visas, business, tax, and life in Bali.',
      creator: '@balizero',
    },
    alternates: {
      canonical: baseUrl,
    },
  };
}
