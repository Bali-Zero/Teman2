import path from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  loadPublicJournalFeed,
  loadPublicArticleResult,
} from "./public-editorial";
import { isJournalCategory } from "../../content/journal-categories";
import { isArticleSlug } from "../article-slug";
import { loadPublicCatalog, selectCatalog } from "./public-catalog";
const json = (value: unknown) =>
  new Response(JSON.stringify(value), {
    headers: { "content-type": "application/json" },
  });
const websiteRoot = process.cwd();
const entry = (index: number, category = "business") => ({
  slug: `story-${String(index).padStart(4, "0")}`,
  title: `Archive story ${index}`,
  category,
  excerpt: "Published context",
  publishedAt: "2026-01-02T00:00:00Z",
  tags: [] as string[],
});
function mockCatalog(
  rows: ReturnType<typeof entry>[],
  states: Record<string, string> = {},
) {
  let active = 0,
    peak = 0;
  const fetcher = vi.fn(async (input: string) => {
    const url = new URL(input);
    if (url.pathname === "/api/blog/articles") {
      expect(url.searchParams.has("q")).toBe(false);
      const offset = Number(url.searchParams.get("offset"));
      return json({
        articles: rows.slice(offset, offset + 200),
        total: rows.length,
        hasMore: offset + 200 < rows.length,
      });
    }
    active++;
    peak = Math.max(peak, active);
    await new Promise((resolve) => setTimeout(resolve, 1));
    active--;
    const row = rows.find((v) =>
      url.pathname.endsWith(`/${v.category}/${v.slug}`),
    )!;
    if (states[row.slug] === "unavailable")
      return new Response(null, { status: 503 });
    return json({
      ...row,
      status: states[row.slug] ?? "published",
      content: "## Context\n\nOwned body.",
    });
  });
  vi.stubGlobal("fetch", fetcher);
  return { fetcher, peak: () => peak };
}
beforeEach(() =>
  vi
    .spyOn(process, "cwd")
    .mockReturnValue(path.join(websiteRoot, "__missing_archive__", "website")),
);
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
describe("whole public archive search", () => {
  it("lists the archive from disk when the legacy origin is unavailable", async () => {
    vi.mocked(process.cwd).mockReturnValue(websiteRoot);
    const fetcher = vi.fn(() => {
      throw new Error("legacy origin unavailable");
    });
    vi.stubGlobal("fetch", fetcher);

    const catalog = await loadPublicCatalog();
    expect(catalog.length).toBeGreaterThanOrEqual(808);
    expect(
      catalog.every(
        (row) => isJournalCategory(row.category) && isArticleSlug(row.slug),
      ),
    ).toBe(true);
    expect(catalog.some((row) => /\.(?:id|it|fr|ru)$/.test(row.slug))).toBe(
      false,
    );
    expect(
      new Set(catalog.map((row) => `${row.category}/${row.slug}`)).size,
    ).toBe(catalog.length);
  });
  it("preserves all six published legacy slugs with repeated or trailing hyphens", async () => {
    const legacy = [
      [
        "taxes",
        "jamaicas-digital-nomad-opportunity-more-than-tourism-top-7-industries-to-benefit-silicon-caribe-caribbean-tech-news-and-",
      ],
      [
        "trends",
        "indonesias-data-law-now-covers-us-transfers-what-expats-and-",
      ],
      [
        "trends",
        "indonesian-minister-warns-unguided-ai-risks-dehumanization---tempoco-english-3bcb77",
      ],
      [
        "visas",
        "beware-of-deportation-dont-dare-before-understanding-the-rules-of-foreign-nationals-opening-a-business-in-bali-terbaru---voiid-73a1f5",
      ],
      [
        "trends",
        "indonesias-digital-economy-generates-27-billion-usb-in-tax-revenue---vietnam-vietnamplus-01c364",
      ],
      [
        "trends",
        "indonesia-collects-idr-1224-trillion-in-digital-economy-taxes---rricoid-7d2216",
      ],
    ] as const;
    const rows = legacy.map(([category, slug], index) => ({
      ...entry(index, category),
      slug,
    }));
    const { fetcher } = mockCatalog(rows);
    const feed = await loadPublicJournalFeed({ limit: 12 });
    expect(feed).toMatchObject({
      status: "ready",
      catalogSize: 6,
      total: 6,
      hasMore: false,
      rejected: 0,
    });
    expect(feed.articles.map((article) => article.localHref).sort()).toEqual(
      legacy.map(([category, slug]) => `/${category}/${slug}`).sort(),
    );
    expect(fetcher.mock.calls).toHaveLength(7);
  });
  it("rejects unsafe or unbounded slug syntax before fetching article details", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    for (const slug of [
      "../secret",
      "a/b",
      "a%2fb",
      "a?draft=1",
      "a#x",
      "a\\b",
      "-",
      "_",
      "_leading",
      "a_../secret",
      "a_%2e%2e",
      "a_\n",
      "",
      "a".repeat(201),
    ]) {
      expect(await loadPublicArticleResult("property", slug), slug).toEqual({
        status: "missing",
      });
    }
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("keeps the complete archive searchable when published news identifiers use underscores", async () => {
    const slugs = [
      "news_20260906_175707_90470bc5",
      "news_20260906_175715_4f4d2a35",
      "news_20260907_173053_1e7fa0d1",
    ];
    const rows = Array.from({ length: 818 }, (_, i) => entry(i));
    slugs.forEach((slug, index) => {
      rows[index] = { ...entry(index), slug };
    });
    rows[751] = {
      ...entry(751, "property"),
      slug: "leasehold-vs-freehold",
      title: "Leasehold vs Freehold: Bali Property Ownership",
    };
    mockCatalog(rows);
    const feed = await loadPublicJournalFeed({
      q: "leasehold freehold",
      category: "property",
    });
    expect(feed).toMatchObject({ status: "ready", catalogSize: 818, total: 1 });
    expect(feed.articles[0].localHref).toBe("/property/leasehold-vs-freehold");
    for (const slug of slugs) {
      expect(await loadPublicArticleResult("business", slug)).toMatchObject({
        status: "ready",
        article: { metadata: { slug, localHref: `/business/${slug}` } },
      });
    }
  });
  it("finds the known title beyond the old 200 slice and preserves category scope", async () => {
    const rows = Array.from({ length: 815 }, (_, i) => entry(i));
    rows[751] = {
      ...entry(751, "property"),
      slug: "leasehold-vs-freehold",
      title: "Leasehold vs Freehold: Bali Property Ownership",
    };
    const { fetcher } = mockCatalog(rows);
    const feed = await loadPublicJournalFeed({
      q: "leasehold freehold",
      category: "property",
      limit: 12,
    });
    expect(feed).toMatchObject({
      status: "ready",
      catalogSize: 815,
      total: 1,
      hasMore: false,
    });
    expect(feed.articles[0].localHref).toBe("/property/leasehold-vs-freehold");
    expect(
      fetcher.mock.calls.filter(([url]) => url.includes("offset=")),
    ).toHaveLength(5);
    expect(fetcher.mock.calls).toHaveLength(6);
    expect(
      await loadPublicJournalFeed({
        q: "leasehold freehold",
        category: "taxes",
      }),
    ).toMatchObject({ status: "empty", total: 0 });
  });
  it("continues past 1000 records instead of substituting a larger fixed cutoff", async () => {
    const rows = Array.from({ length: 1201 }, (_, i) => entry(i));
    rows[1200].title = "Last archive needle";
    mockCatalog(rows);
    expect(
      (await loadPublicJournalFeed({ q: "archive needle" })).articles[0].slug,
    ).toBe(rows[1200].slug);
  });
  it("refills withdrawn rows, pages confirmed publication and proves Next with one extra result", async () => {
    const rows = Array.from({ length: 40 }, (_, i) => entry(i));
    const { peak } = mockCatalog(rows, {
      "story-0000": "archived",
      "story-0001": "draft",
    });
    const first = await loadPublicJournalFeed({ page: 1, limit: 12 });
    const second = await loadPublicJournalFeed({ page: 2, limit: 12 });
    expect(first.articles).toHaveLength(12);
    expect(second.articles).toHaveLength(12);
    expect(first.articles[0].slug).toBe("story-0002");
    expect(second.articles[0].slug).toBe("story-0014");
    expect(first.hasMore).toBe(true);
    expect(first.total).toBeUndefined();
    expect(peak()).toBeLessThanOrEqual(4);
    const end = await loadPublicJournalFeed({ page: 4, limit: 12 });
    expect(end).toMatchObject({ hasMore: false, total: 38 });
    expect(end.articles).toHaveLength(2);
    expect(await loadPublicJournalFeed({ page: 5, limit: 12 })).toMatchObject({
      status: "empty",
      hasMore: false,
      total: 38,
    });
  });
  it("ranks title phrases, normalizes case and accents and requires every query term", () => {
    const base = entry(1);
    expect(
      selectCatalog(
        [
          { ...base, slug: "one", title: "Other", excerpt: "cafe bali" },
          { ...base, slug: "two", title: "Café Bali" },
        ],
        { q: "CAFE bali" },
      ).map((v) => v.slug),
    ).toEqual(["two", "one"]);
    expect(selectCatalog([base], { q: "no such thing" })).toEqual([]);
  });
  it("never labels partial/outage data as no results", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json({ articles: [entry(1)], total: 815, hasMore: true }),
      ),
    );
    expect(await loadPublicJournalFeed({ q: "missing" })).toMatchObject({
      status: "unavailable",
      articles: [],
    });
    mockCatalog([entry(1)], { "story-0001": "unavailable" });
    expect(await loadPublicJournalFeed()).toMatchObject({
      status: "unavailable",
      articles: [],
    });
  });
  it("checks fresh publication and distinguishes withdrawal from authority outage", async () => {
    const fetcher = vi.fn(async () => new Response(null, { status: 410 }));
    vi.stubGlobal("fetch", fetcher);
    expect(await loadPublicArticleResult("property", "old-story")).toEqual({
      status: "missing",
    });
    expect(fetcher).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ cache: "no-store" }),
    );
    fetcher.mockImplementation(async () => new Response(null, { status: 503 }));
    expect(await loadPublicArticleResult("property", "old-story")).toEqual({
      status: "unavailable",
    });
  });
});
