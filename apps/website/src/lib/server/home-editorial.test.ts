import path from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import layout from "../../../../mouth/src/content/homepage-layout.json";
import { loadPublicHomeFeed } from "./home-editorial";
const json = (value: unknown) =>
  new Response(JSON.stringify(value), {
    headers: { "content-type": "application/json" },
  });
const websiteRoot = process.cwd();
beforeEach(() =>
  vi
    .spyOn(process, "cwd")
    .mockReturnValue(path.join(websiteRoot, "__missing_archive__", "website")),
);
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
describe("configured home editorial placements", () => {
  it("resolves all five heroes and five latest pins, independent of recency and old hero API truncation", async () => {
    const slugs = [
      layout.hero_main,
      layout.hero_2,
      layout.hero_3,
      layout.hero_4,
      layout.hero_5,
      layout.latest_1,
      layout.latest_2,
      layout.latest_3,
      layout.latest_4,
      layout.latest_5,
    ];
    const rows = [...slugs].reverse().map((slug) => ({
      slug,
      category: "business",
      title: slug,
      publishedAt: "2026-01-02",
    }));
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string) =>
        input.includes("?")
          ? json({ articles: rows, total: rows.length, hasMore: false })
          : json({
              ...rows.find((v) => input.endsWith(v.slug)),
              status: "published",
              content: "## Owned content",
            }),
      ),
    );
    const feed = await loadPublicHomeFeed();
    expect(feed.featuredCount).toBe(5);
    expect(feed.articles.map((v) => v.slug)).toEqual(slugs);
  });
  it("omits withdrawn pins and never fabricates an unavailable placement", async () => {
    const rows = [
      { slug: layout.hero_main, category: "business", title: "Withdrawn" },
      { slug: "available-fallback", category: "business", title: "Available" },
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string) =>
        input.includes("?")
          ? json({ articles: rows, total: rows.length })
          : json({
              ...rows.find((v) => input.endsWith(v.slug)),
              status: input.endsWith(layout.hero_main)
                ? "archived"
                : "published",
              publishedAt: "2026-01-02",
              content: "## Owned content",
            }),
      ),
    );
    expect((await loadPublicHomeFeed()).articles.map((v) => v.slug)).toEqual([
      "available-fallback",
    ]);
  });
  it("refills a withdrawn hero without taking a configured latest position", async () => {
    const heroes = [
      layout.hero_main,
      layout.hero_2,
      layout.hero_3,
      layout.hero_4,
      layout.hero_5,
    ];
    const latest = [
      layout.latest_1,
      layout.latest_2,
      layout.latest_3,
      layout.latest_4,
      layout.latest_5,
    ];
    const rows = [...latest, ...heroes, "spare-story"].map((slug, i) => ({
      slug,
      category: "business",
      title: slug,
      publishedAt: i < 5 ? "2026-02-01" : "2026-01-01",
    }));
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: string) =>
        input.includes("?")
          ? json({ articles: rows, total: rows.length })
          : json({
              ...rows.find((v) => input.endsWith(v.slug)),
              status: input.endsWith(layout.hero_main)
                ? "archived"
                : "published",
              content: "## Owned content",
            }),
      ),
    );
    const feed = await loadPublicHomeFeed();
    expect(feed.featuredCount).toBe(5);
    expect(feed.articles.slice(0, 5).map((v) => v.slug)).toEqual([
      ...heroes.slice(1),
      "spare-story",
    ]);
    expect(feed.articles.slice(5).map((v) => v.slug)).toEqual(latest);
  });
});
