import type { MetadataRoute } from "next";
import {
  getAllArticles,
  getNoIndexSlugs,
  getAvailableLocales,
} from "@/lib/blog/articles";
import { getAllCodes, getSections } from "@/lib/kbli-data.server";
import { logger } from "@/lib/logger";

/**
 * Dynamic Sitemap Generator
 *
 * Generates XML sitemap for SEO with:
 * - Static pages (homepage, services, team, contact, kbli-explorer)
 * - Service pages (4 main services)
 * - News categories (8 categories)
 * - Blog articles (all published articles)
 * - KBLI 2025 codes (1,563 pages)
 * - KBLI sectors index + individual sector pages (~22)
 * Priority scale:
 * - 1.0: Homepage
 * - 0.9: Main service pages
 * - 0.8: Blog articles, KBLI explorer, KBLI codes
 * - 0.7: Service detail pages, news categories, KBLI sectors
 *
 * Change frequency:
 * - daily: News, blog
 * - weekly: Services, KBLI
 * - monthly: Static pages
 */

const baseUrl = "https://balizero.com";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const routes: MetadataRoute.Sitemap = [];

  // 1. Static pages
  const staticPages = [
    {
      url: `${baseUrl}`,
      lastModified: new Date(),
      changeFrequency: "monthly" as const,
      priority: 1.0,
    },
    {
      url: `${baseUrl}/kbli`,
      lastModified: new Date(),
      changeFrequency: "weekly" as const,
      priority: 0.9,
    },
    {
      url: `${baseUrl}/services`,
      lastModified: new Date(),
      changeFrequency: "monthly" as const,
      priority: 0.9,
    },
    {
      url: `${baseUrl}/news`,
      lastModified: new Date(),
      changeFrequency: "daily" as const,
      priority: 0.8,
    },
    {
      url: `${baseUrl}/team`,
      lastModified: new Date(),
      changeFrequency: "monthly" as const,
      priority: 0.7,
    },
    {
      url: `${baseUrl}/contact`,
      lastModified: new Date(),
      changeFrequency: "monthly" as const,
      priority: 0.7,
    },
    {
      url: `${baseUrl}/kbli-explorer`,
      lastModified: new Date(),
      changeFrequency: "weekly" as const,
      priority: 0.8,
    },
    {
      url: `${baseUrl}/llms.txt`,
      lastModified: new Date(),
      changeFrequency: "daily" as const,
      priority: 1.0,
    },
    {
      url: `${baseUrl}/llms-full.txt`,
      lastModified: new Date(),
      changeFrequency: "daily" as const,
      priority: 0.9,
    },
    {
      url: `${baseUrl}/llms-id.txt`,
      lastModified: new Date(),
      changeFrequency: "daily" as const,
      priority: 0.9,
    },
  ];

  routes.push(...staticPages);

  // 2. Service pages (4 main services)
  const servicePages = [
    {
      url: `${baseUrl}/services/visa`,
      lastModified: new Date(),
      changeFrequency: "weekly" as const,
      priority: 0.9,
    },
    {
      url: `${baseUrl}/services/company`,
      lastModified: new Date(),
      changeFrequency: "weekly" as const,
      priority: 0.9,
    },
    {
      url: `${baseUrl}/services/tax`,
      lastModified: new Date(),
      changeFrequency: "weekly" as const,
      priority: 0.9,
    },
    {
      url: `${baseUrl}/services/property`,
      lastModified: new Date(),
      changeFrequency: "weekly" as const,
      priority: 0.9,
    },
  ];

  routes.push(...servicePages);

  // 3. Category pages (match actual routes: /{category})
  const categories = [
    "visas",
    "business",
    "taxes",
    "property",
    "living",
    "trends",
  ];

  const newsCategoryPages = categories.map((category) => ({
    url: `${baseUrl}/${category}`,
    lastModified: new Date(),
    changeFrequency: "daily" as const,
    priority: 0.7,
  }));

  routes.push(...newsCategoryPages);

  // 4. Blog articles (from local MDX content, excluding noIndex articles)
  try {
    const [{ articles }, noIndexSlugs] = await Promise.all([
      getAllArticles({ limit: 500 }),
      getNoIndexSlugs(),
    ]);

    const articlePages = articles
      .filter((article) => !noIndexSlugs.has(article.slug))
      .map((article) => {
        const locales = getAvailableLocales(article.category, article.slug);
        const entry: MetadataRoute.Sitemap[number] = {
          url: `${baseUrl}/${article.category}/${article.slug}`,
          lastModified: article.publishedAt
            ? new Date(article.publishedAt)
            : new Date(),
          changeFrequency: "monthly" as const,
          priority: 0.8,
        };

        // Add hreflang alternates if translations exist
        if (locales.length > 1) {
          const languages: Record<string, string> = {};
          for (const loc of locales) {
            languages[loc] =
              loc === "en"
                ? `${baseUrl}/${article.category}/${article.slug}`
                : `${baseUrl}/${article.category}/${article.slug}?lang=${loc}`;
          }
          entry.alternates = { languages };
        }

        return entry;
      });

    routes.push(...articlePages);
  } catch (error) {
    logger.error(
      "[SITEMAP] Failed to load articles",
      {},
      error instanceof Error ? error : new Error(String(error)),
    );
  }

  // 5. KBLI Codes (1,563 pages)
  try {
    const codes = getAllCodes();
    const kbliPages = codes.map((c) => ({
      url: `${baseUrl}/kbli/${c.code}`,
      lastModified: new Date(),
      changeFrequency: "monthly" as const,
      priority: 0.8,
    }));
    routes.push(...kbliPages);
  } catch (error) {
    logger.error(
      "[SITEMAP] Failed to load KBLI codes",
      {},
      error instanceof Error ? error : new Error(String(error)),
    );
  }

  // 6. KBLI Sector pages (/kbli/sectors + /kbli/sectors/[id])
  try {
    routes.push({
      url: `${baseUrl}/kbli/sectors`,
      lastModified: new Date(),
      changeFrequency: "monthly" as const,
      priority: 0.8,
    });

    const sections = getSections().filter((s) => s.codeCount > 0);
    const sectorPages = sections.map((s) => ({
      url: `${baseUrl}/kbli/sectors/${s.id}`,
      lastModified: new Date(),
      changeFrequency: "monthly" as const,
      priority: 0.7,
    }));
    routes.push(...sectorPages);
  } catch (error) {
    logger.error(
      "[SITEMAP] Failed to load KBLI sectors",
      {},
      error instanceof Error ? error : new Error(String(error)),
    );
  }

  return routes;
}
