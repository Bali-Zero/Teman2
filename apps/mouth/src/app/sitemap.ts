import type { MetadataRoute } from "next";
import { getAllArticles, getNoIndexSlugs } from "@/lib/blog/articles";
import { getAllCodes, getSections } from "@/lib/kbli-data.server";
import { logger } from "@/lib/logger";
import fs from "fs";
import path from "path";

/**
 * Dynamic Sitemap Generator
 *
 * Generates XML sitemap for SEO with:
 * - Static pages (homepage, services, team, contact, kbli-explorer)
 * - Service pages (4 main services)
 * - News categories (8 categories)
 * - Blog articles (all published articles)
 * - KBLI 2025 codes (1,559 pages)
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
      getAllArticles({ limit: 10000 }),
      getNoIndexSlugs(),
    ]);

    // Slugs that must never appear in sitemap regardless of source
    // (test content, sentinel values injected by CMS/backend).
    const SITEMAP_BLOCKED_SLUGS = new Set(["test-article"]);

    const articlePages = articles
      .filter((article) => {
        // Exclude slugs that contain query-string characters (e.g. "foo?bar")
        if (article.slug.includes("?")) return false;
        // Exclude explicitly blocked slugs (test content, etc.)
        if (SITEMAP_BLOCKED_SLUGS.has(article.slug)) return false;
        // Exclude slugs marked noIndex in MDX frontmatter
        if (noIndexSlugs.has(article.slug)) return false;
        return true;
      })
      .map((article) => {
        // Priority: featured editorial (0.9) > ai-enriched (0.8) > basic (0.6)
        const priority = article.featured
          ? 0.9
          : article.aiGenerated
            ? 0.8
            : 0.6;
        const entry: MetadataRoute.Sitemap[number] = {
          url: `${baseUrl}/${article.category}/${article.slug}`,
          lastModified: article.publishedAt
            ? new Date(article.publishedAt)
            : new Date(),
          changeFrequency: "weekly" as const,
          priority,
        };

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

  // 5. KBLI Codes (1,559 pages)
  try {
    const codes = getAllCodes();
    const kbliDataPath = path.join(
      process.cwd(),
      "data",
      "KBLI_2025_FINAL_CLEAN.json",
    );
    let kbliLastModified: Date;
    try {
      kbliLastModified = fs.statSync(kbliDataPath).mtime;
    } catch {
      kbliLastModified = new Date("2026-06-19");
    }
    const kbliPages = codes.map((c) => ({
      url: `${baseUrl}/kbli/${c.code}`,
      lastModified: kbliLastModified,
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

  // 6. Visa funnel pages (balizero.com/visa — consolidated 2026-04-21,
  // was previously at visa.balizero.com; the subdomain now 302-redirects
  // to these canonical paths via middleware.ts).
  const visaPages = [
    {
      url: `${baseUrl}/visa`,
      lastModified: new Date(),
      changeFrequency: "weekly" as const,
      priority: 0.9,
    },
    {
      url: `${baseUrl}/visa/match`,
      lastModified: new Date(),
      changeFrequency: "weekly" as const,
      priority: 0.9,
    },
    {
      url: `${baseUrl}/visa/clock`,
      lastModified: new Date(),
      changeFrequency: "weekly" as const,
      priority: 0.9,
    },
    {
      url: `${baseUrl}/visa/privacy`,
      lastModified: new Date(),
      changeFrequency: "monthly" as const,
      priority: 0.5,
    },
    {
      url: `${baseUrl}/visa/terms`,
      lastModified: new Date(),
      changeFrequency: "monthly" as const,
      priority: 0.5,
    },
  ];
  routes.push(...visaPages);

  // 7. KBLI Sector pages (/kbli/sectors + /kbli/sectors/[id])
  try {
    routes.push({
      url: `${baseUrl}/kbli/sectors`,
      lastModified: new Date(),
      changeFrequency: "monthly" as const,
      priority: 0.8,
    });

    const sections = getSections().filter(
      // Exclude sections with no codes AND exclude the sentinel "?" ID that
      // transformCode() emits when sektor_id is null — avoids /kbli/sectors/?
      (s) => s.codeCount > 0 && /^[A-Z]$/.test(s.id),
    );
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
