import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getAllArticles, getArticleBySlug, getNoIndexSlugs } from "./articles";

// Hermetic: strip the ISR cache wrapper (Next server-only) and force the
// backend fetch to fail fast so getAllArticles falls back to the real
// on-disk MDX corpus (same "real, offline" convention as
// homepage-layout-guard.test.ts — no network, no backend).
vi.mock("next/cache", () => ({
  unstable_cache: (fn: unknown) => fn,
}));

// Real on-disk articles carrying `noIndex: true` (editorial rewrite queue —
// files stay on disk, they only leave listing/feed surfaces).
const NOINDEX_SLUGS = ["perfect-storm-bali-2026", "kerobokan-traffic-trial"];
// A stable indexable article that must keep listing.
const INDEXABLE_SLUG = "vat-ppn-guide";

describe("noIndex listing filter", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("offline in test")),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("fixture sanity: the noIndex slugs are still flagged on disk", async () => {
    const noIndexSlugs = await getNoIndexSlugs();
    for (const slug of NOINDEX_SLUGS) {
      expect(noIndexSlugs.has(slug)).toBe(true);
    }
    expect(noIndexSlugs.has(INDEXABLE_SLUG)).toBe(false);
  });

  it("excludes noIndex articles from getAllArticles (listing + feed source)", async () => {
    const { articles, total } = await getAllArticles({ limit: 500 });
    const slugs = articles.map((a) => a.slug);

    for (const slug of NOINDEX_SLUGS) {
      expect(slugs).not.toContain(slug);
    }
    // `total` reflects the filtered set before pagination.
    expect(total).toBeGreaterThanOrEqual(articles.length);
  });

  it("keeps indexable articles listed", async () => {
    const { articles } = await getAllArticles({
      category: "taxes",
      limit: 500,
    });
    expect(articles.map((a) => a.slug)).toContain(INDEXABLE_SLUG);
  });

  it("excludes noIndex articles under a category filter too", async () => {
    const { articles } = await getAllArticles({
      category: "living",
      limit: 500,
    });
    const slugs = articles.map((a) => a.slug);
    for (const slug of NOINDEX_SLUGS) {
      expect(slugs).not.toContain(slug);
    }
  });

  it("keeps the direct article page working (getArticleBySlug by slug)", async () => {
    // The renderer resolves single articles via getArticleBySlug, NOT
    // getAllArticles — a noIndex article must remain reachable at its URL.
    const article = await getArticleBySlug(
      "lifestyle",
      "perfect-storm-bali-2026",
    );
    expect(article).not.toBeNull();
    expect(article?.noIndex).toBe(true);
  });
});
