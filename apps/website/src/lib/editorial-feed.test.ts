import { describe, expect, it } from "vitest";
import { readEditorialFeed } from "./editorial-feed";

const article = {
  slug: "editorial-fixture", title: "Editorial fixture", category: "business",
  coverImage: "/static/news/fixture.jpg", publishedAt: "2026-09-06",
  publicationState: "published", noIndex: false,
};
const read = (rows: unknown[]) => readEditorialFeed(async () => ({ version: 1, articles: rows }));

describe("public editorial boundary", () => {
  it("keeps canonical article and asset ownership across application origins", async () => {
    const result = await read([article]);
    expect(result.status).toBe("ready");
    expect(result.articles[0]).toMatchObject({
      sourceUrl: "https://balizero.com/business/editorial-fixture",
      image: { src: "/legacy/static/news/fixture.jpg", sourceSrc: "https://balizero.com/static/news/fixture.jpg" },
      date: { iso: "2026-09-06T00:00:00.000Z" },
      verificationStatus: "pending", finalSourceUrl: null,
    });
  });

  it("rejects drafts, hidden records and legacy records without explicit publication state", async () => {
    const { publicationState: _, ...legacy } = article;
    const result = await read([legacy, { ...article, publicationState: "draft" }, { ...article, noIndex: true }]);
    expect(result).toEqual({ status: "unavailable", articles: [], rejected: 3 });
  });

  it("distinguishes empty, malformed and failed publishing responses without invented stories", async () => {
    expect((await read([])).status).toBe("empty");
    expect((await readEditorialFeed(async () => ({ articles: [article] }))).status).toBe("unavailable");
    expect((await readEditorialFeed(async () => { throw new Error("offline"); })).articles).toEqual([]);
  });

  it("does not turn missing or impossible publication dates into fresh articles", async () => {
    expect((await read([{ ...article, publishedAt: null }])).articles[0].date).toBeNull();
    for (const publishedAt of [undefined, "invalid", "2026-02-30", "2026-09-06T25:00:00Z"]) {
      expect((await read([{ ...article, publishedAt }])).articles).toEqual([]);
    }
  });

  it("rejects injected URLs, foreign assets, invalid route segments and unknown categories", async () => {
    const invalid = [
      { coverImage: "javascript:alert(1)" },
      { coverImage: "//untrusted.invalid/static/cover.jpg" },
      { coverImage: "https://balizero.com@untrusted.invalid/static/cover.jpg" },
      { coverImage: "https://user:password@balizero.com/static/cover.jpg" },
      { coverImage: "/static/../api/private" },
      { slug: "../../portal" }, { category: "portal" }, { title: " " },
    ];
    expect((await read(invalid.map((change) => ({ ...article, ...change })))).rejected).toBe(invalid.length);
  });

  it("deduplicates canonical URLs while preserving publisher order", async () => {
    const result = await read([article, article, { ...article, slug: "second-story" }]);
    expect(result.articles.map((row) => row.slug)).toEqual(["editorial-fixture", "second-story"]);
    expect(result.rejected).toBe(1);
  });
});
