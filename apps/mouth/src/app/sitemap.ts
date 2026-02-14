import type { MetadataRoute } from 'next';
import { logger } from '@/lib/logger';

/**
 * Dynamic Sitemap Generator
 *
 * Generates XML sitemap for SEO with:
 * - Static pages (homepage, services, team, contact, kbli-explorer)
 * - Service pages (4 main services)
 * - News categories (6 categories)
 * - Blog articles (all published articles)
 * - Top KBLI codes (35 most searched codes)
 *
 * Priority scale:
 * - 1.0: Homepage
 * - 0.9: Main service pages
 * - 0.8: Blog articles, KBLI explorer
 * - 0.7: Service detail pages, news categories
 * - 0.6: KBLI code pages
 *
 * Change frequency:
 * - daily: News, blog
 * - weekly: Services, KBLI
 * - monthly: Static pages
 */

const baseUrl = 'https://balizero.com';

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const routes: MetadataRoute.Sitemap = [];

  // 1. Static pages
  const staticPages = [
    {
      url: `${baseUrl}`,
      lastModified: new Date(),
      changeFrequency: 'monthly' as const,
      priority: 1.0,
    },
    {
      url: `${baseUrl}/services`,
      lastModified: new Date(),
      changeFrequency: 'monthly' as const,
      priority: 0.9,
    },
    {
      url: `${baseUrl}/news`,
      lastModified: new Date(),
      changeFrequency: 'daily' as const,
      priority: 0.8,
    },
    {
      url: `${baseUrl}/team`,
      lastModified: new Date(),
      changeFrequency: 'monthly' as const,
      priority: 0.7,
    },
    {
      url: `${baseUrl}/contact`,
      lastModified: new Date(),
      changeFrequency: 'monthly' as const,
      priority: 0.7,
    },
    {
      url: `${baseUrl}/kbli-explorer`,
      lastModified: new Date(),
      changeFrequency: 'weekly' as const,
      priority: 0.8,
    },
  ];

  routes.push(...staticPages);

  // 2. Service pages (4 main services)
  const servicePages = [
    {
      url: `${baseUrl}/services/visa`,
      lastModified: new Date(),
      changeFrequency: 'weekly' as const,
      priority: 0.9,
    },
    {
      url: `${baseUrl}/services/company`,
      lastModified: new Date(),
      changeFrequency: 'weekly' as const,
      priority: 0.9,
    },
    {
      url: `${baseUrl}/services/tax`,
      lastModified: new Date(),
      changeFrequency: 'weekly' as const,
      priority: 0.9,
    },
    {
      url: `${baseUrl}/services/property`,
      lastModified: new Date(),
      changeFrequency: 'weekly' as const,
      priority: 0.9,
    },
  ];

  routes.push(...servicePages);

  // 3. News categories (6 categories)
  const newsCategories = [
    'immigration',
    'business',
    'tax',
    'legal',
    'property',
    'lifestyle',
  ];

  const newsCategoryPages = newsCategories.map((category) => ({
    url: `${baseUrl}/news/${category}`,
    lastModified: new Date(),
    changeFrequency: 'daily' as const,
    priority: 0.7,
  }));

  routes.push(...newsCategoryPages);

  // 4. Blog articles (fetch from API or static content)
  try {
    // Try to fetch articles from backend API
    const articlesResponse = await fetch(
      `https://nuzantara-rag.fly.dev/api/blog/articles?published=true&limit=200`,
      { next: { revalidate: 3600 } } // Cache for 1 hour
    );

    if (articlesResponse.ok) {
      const articlesData = await articlesResponse.json();
      const articles = articlesData.articles || [];

      const articlePages = articles.map((article: any) => ({
        url: `${baseUrl}/news/${article.slug}`,
        lastModified: article.publishedAt ? new Date(article.publishedAt) : new Date(),
        changeFrequency: 'monthly' as const,
        priority: 0.8,
      }));

      routes.push(...articlePages);
    }
  } catch (error) {
    logger.error('[SITEMAP] Failed to fetch articles', { error });
    // Fallback: add mock articles for now
    // In production, this should pull from your content directory
  }

  // 5. Top KBLI codes (35 most searched)
  // These are the most relevant business classification codes for SEO
  const topKBLICodes = [
    '56101', // Restaurant
    '56102', // Cafe
    '47911', // Retail trade
    '68100', // Real estate
    '55101', // Hotel
    '55102', // Villa
    '93110', // Fitness center
    '96022', // Spa
    '85109', // Education
    '62010', // Computer programming
    '62020', // Computer consultancy
    '63111', // Data processing
    '70200', // Management consultancy
    '73200', // Market research
    '74100', // Specialized design
    '74200', // Photography
    '77100', // Motor vehicle rental
    '79110', // Travel agency
    '79120', // Tour operator
    '82990', // Other business support
    '46900', // Wholesale trade
    '47190', // Retail sale
    '47710', // Clothing retail
    '47721', // Pharmacy
    '47730', // Fuel station
    '56210', // Event catering
    '58110', // Book publishing
    '58120', // Software publishing
    '62090', // Other IT services
    '69200', // Accounting
    '71100', // Architecture
    '73100', // Advertising
    '74300', // Translation
    '82110', // Office support
    '96090', // Other personal services
  ];

  const kbliPages = topKBLICodes.map((code) => ({
    url: `${baseUrl}/kbli/${code}`,
    lastModified: new Date(),
    changeFrequency: 'weekly' as const,
    priority: 0.6,
  }));

  routes.push(...kbliPages);

  return routes;
}
