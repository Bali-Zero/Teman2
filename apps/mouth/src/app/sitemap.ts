import { MetadataRoute } from 'next';
import { getAllArticles } from '@/lib/blog/articles';

// Public website base URL
const baseUrl = process.env.NEXT_PUBLIC_PUBLIC_URL || 'https://balizero.com';

// Categories for article pages
const CATEGORIES = [
  'immigration',
  'business',
  'tax-legal',
  'property',
  'lifestyle',
  'digital-nomad',
];

// Services pages
const SERVICES = [
  'visa',
  'company',
  'tax',
  'property',
];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  // Get all articles dynamically
  const { articles } = await getAllArticles();

  // Static pages
  const staticPages: MetadataRoute.Sitemap = [
    {
      url: baseUrl,
      lastModified: new Date(),
      changeFrequency: 'daily',
      priority: 1.0,
    },
    {
      url: `${baseUrl}/services`,
      lastModified: new Date(),
      changeFrequency: 'weekly',
      priority: 0.9,
    },
    {
      url: `${baseUrl}/team`,
      lastModified: new Date(),
      changeFrequency: 'monthly',
      priority: 0.7,
    },
    {
      url: `${baseUrl}/contact`,
      lastModified: new Date(),
      changeFrequency: 'monthly',
      priority: 0.8,
    },
  ];

  // Category pages (now at root level: /immigration, /business, etc.)
  const categoryPages: MetadataRoute.Sitemap = CATEGORIES.map((category) => ({
    url: `${baseUrl}/${category}`,
    lastModified: new Date(),
    changeFrequency: 'daily' as const,
    priority: 0.8,
  }));

  // Service pages
  const servicePages: MetadataRoute.Sitemap = SERVICES.map((service) => ({
    url: `${baseUrl}/services/${service}`,
    lastModified: new Date(),
    changeFrequency: 'weekly' as const,
    priority: 0.8,
  }));

  // Article pages - highest priority for long-tail SEO
  const articlePages: MetadataRoute.Sitemap = articles.map((article) => ({
    url: `${baseUrl}/${article.category}/${article.slug}`,
    lastModified: new Date(article.publishedAt),
    changeFrequency: 'weekly' as const,
    priority: 0.7,
  }));

  return [
    ...staticPages,
    ...categoryPages,
    ...servicePages,
    ...articlePages,
  ];
}
