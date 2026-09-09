import { afterEach, describe, expect, it, vi } from "vitest";
import { decodePublicArticle, loadPublicArticle, loadPublicJournalFeed } from "./public-editorial";

const article = (slug = "published-story", category = "business") => ({
  slug, category, status: "published", noIndex: false, title: "An owned published article",
  publishedAt: "2026-01-02T00:00:00Z", content: "## Context\n\nPublished article body.",
  excerpt: "A clear summary.", coverImage: "/static/news/story.jpg",
  author: { privateValue: "not projected" }, mdxSource: { compiledSource: "never executed" },
});
const response = (value: unknown) => new Response(JSON.stringify(value), { headers: { "content-type": "application/json" } });
afterEach(() => vi.unstubAllGlobals());

describe("current public editorial boundary", () => {
  it("allows only published documents and preserves the original category/slug URL", () => {
    const result = decodePublicArticle(article(), "business", "published-story")!;
    expect(result.metadata.localHref).toBe("/business/published-story");
    expect(result.metadata.date?.label).toBe("2 January 2026");
    expect(result.markdown).toContain("Published article body");
    expect(JSON.stringify(result)).not.toMatch(/privateValue|compiledSource/);
  });
  it("rejects drafts, hidden/future documents, category mismatches and legacy demos", () => {
    for (const patch of [{ status: "draft" }, { noIndex: true }, { publishedAt: null }, { publishedAt: "2040-01-02T00:00:00Z" }, { category: "taxes" }]) {
      expect(decodePublicArticle({ ...article(), ...patch }, "business", "published-story")).toBeNull();
    }
    expect(decodePublicArticle(article("golden-visa-revolution", "visas"), "visas", "golden-visa-revolution")).toBeNull();
  });
  it("does not fetch traversal/unknown routes and excludes foreign cover origins", async () => {
    const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
    expect(await loadPublicArticle("business", "../secret")).toBeNull();
    expect(await loadPublicArticle("internal", "published-story")).toBeNull();
    expect(fetcher).not.toHaveBeenCalled();
    expect(decodePublicArticle({ ...article(), coverImage: "https://other.invalid/image.jpg" }, "business", "published-story")?.metadata.image).toBeNull();
  });
});
