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
 * - News categories
 * - Blog articles (all published articles)
 * - KBLI 2025 codes (1,559 pages)
 * - KBLI sectors index + individual sector pages (~22)
 *
 * Signal discipline (GSC clean-window investigation 2026-07-03):
 * - `priority` and `changeFrequency` are omitted — Google ignores both, and
 *   inaccurate hints erode sitemap trust.
 * - `lastModified` is emitted ONLY where we know the real modification event
 *   (article updatedAt/publishedAt, KBLI data-file mtime). Pages whose real
 *   lastmod we don't track carry no lastModified at all — a fabricated
 *   deploy-time date teaches Google to ignore our lastmod entirely.
 */

const baseUrl = "https://balizero.com";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const routes: MetadataRoute.Sitemap = [];

  // 1. Static pages
  const staticPaths = [
    "",
    "/kbli",
    "/services",
    "/news",
    "/team",
    "/contact",
    "/kbli-explorer",
    "/llms.txt",
    "/llms-full.txt",
    "/llms-id.txt",
  ];
  routes.push(...staticPaths.map((p) => ({ url: `${baseUrl}${p}` })));

  // 2. Service pages (4 main services)
  const servicePaths = [
    "/services/visa",
    "/services/company",
    "/services/tax",
    "/services/property",
  ];
  routes.push(...servicePaths.map((p) => ({ url: `${baseUrl}${p}` })));

  // 3. Category pages (match actual routes: /{category})
  const categories = [
    "visas",
    "business",
    "taxes",
    "property",
    "living",
    "trends",
  ];
  routes.push(...categories.map((c) => ({ url: `${baseUrl}/${c}` })));

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
        const entry: MetadataRoute.Sitemap[number] = {
          url: `${baseUrl}/${article.category}/${article.slug}`,
          ...(article.publishedAt
            ? { lastModified: new Date(article.publishedAt) }
            : {}),
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

  // 5. KBLI Codes (1,559 pages) — lastmod comes from the committed dataset
  // version sidecar (data/kbli-dataset-version.json), NOT the file mtime:
  // git/Vercel checkouts stamp clone time on every file, so mtime would
  // claim all 1,559 pages "modified today" on every deploy — exactly the
  // fabricated freshness signal this sitemap must not send.
  try {
    const codes = getAllCodes();
    let kbliLastModified: Date;
    try {
      const version = JSON.parse(
        fs.readFileSync(
          path.join(process.cwd(), "data", "kbli-dataset-version.json"),
          "utf-8",
        ),
      ) as { lastModified: string };
      kbliLastModified = new Date(version.lastModified);
    } catch {
      kbliLastModified = new Date("2026-06-19");
    }
    const kbliPages = codes.map((c) => ({
      url: `${baseUrl}/kbli/${c.code}`,
      lastModified: kbliLastModified,
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
  const visaPaths = [
    "/visa",
    "/visa/match",
    "/visa/clock",
    "/visa/privacy",
    "/visa/terms",
  ];
  routes.push(...visaPaths.map((p) => ({ url: `${baseUrl}${p}` })));

  // 7. KBLI Sector pages (/kbli/sectors + /kbli/sectors/[id])
  try {
    routes.push({ url: `${baseUrl}/kbli/sectors` });

    const sections = getSections().filter(
      // Exclude sections with no codes AND exclude the sentinel "?" ID that
      // transformCode() emits when sektor_id is null — avoids /kbli/sectors/?
      (s) => s.codeCount > 0 && /^[A-Z]$/.test(s.id),
    );
    routes.push(
      ...sections.map((s) => ({ url: `${baseUrl}/kbli/sectors/${s.id}` })),
    );
  } catch (error) {
    logger.error(
      "[SITEMAP] Failed to load KBLI sectors",
      {},
      error instanceof Error ? error : new Error(String(error)),
    );
  }

  return routes;
}
