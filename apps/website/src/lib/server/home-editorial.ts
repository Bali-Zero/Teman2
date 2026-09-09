import homepageLayout from "../../../../mouth/src/content/homepage-layout.json";
import { loadPublicCatalog, selectCatalog, type CatalogEntry } from "./public-catalog";
import { loadPublicArticleResult, type JournalFeed } from "./public-editorial";
import type { JournalArticle } from "../../content/journal";

/** Reuse the existing editorial configuration, not a second hand-maintained
 * copy. Legacy home presents hero_main..5 and latest_1..5; hero_6..7 belong to
 * other placements. Every selected record must still be publicly available. */
export async function loadPublicHomeFeed(): Promise<JournalFeed> {
  try {
    const catalog = await loadPublicCatalog(), recent = selectCatalog(catalog, {});
    const used = new Set<string>();
    const latestSlugs = [homepageLayout.latest_1, homepageLayout.latest_2, homepageLayout.latest_3, homepageLayout.latest_4, homepageLayout.latest_5];
    async function section(slugs: string[], reserved: readonly string[] = []): Promise<JournalArticle[]> {
      const pins = slugs.flatMap((slug) => {
        const matches = catalog.filter((row) => row.slug === slug);
        return matches.length === 1 ? matches : [];
      });
      // A missing hero may not consume an explicitly configured latest slot.
      const ordered = [...pins, ...recent.filter((row) => !reserved.includes(row.slug))], result: JournalArticle[] = [];
      const seen = new Set<string>();
      for (let start = 0; start < ordered.length && result.length < 5;) {
        const batch: CatalogEntry[] = [];
        while (start < ordered.length && batch.length < Math.min(4, 5 - result.length)) {
          const row = ordered[start++], key = `${row.category}/${row.slug}`;
          if (!used.has(key) && !seen.has(key)) { seen.add(key); batch.push(row); }
        }
        const checked = await Promise.all(batch.map((row) => loadPublicArticleResult(row.category, row.slug)));
        for (let i = 0; i < checked.length; i++) {
          const item = checked[i];
          if (item.status === "unavailable") throw new Error("Editorial placement authority unavailable");
          if (item.status === "ready") { used.add(`${batch[i].category}/${batch[i].slug}`); result.push(item.article.metadata); }
        }
      }
      return result;
    }
    const heroes = await section([homepageLayout.hero_main, homepageLayout.hero_2, homepageLayout.hero_3, homepageLayout.hero_4, homepageLayout.hero_5], latestSlugs);
    const latest = await section(latestSlugs);
    const articles = [...heroes, ...latest];
    return { status: articles.length ? "ready" : "empty", articles, rejected: 0, provenance: "publisher", featuredCount: heroes.length };
  } catch { return { status: "unavailable", articles: [], rejected: 0 }; }
}
