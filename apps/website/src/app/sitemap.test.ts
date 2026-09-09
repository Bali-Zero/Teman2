import { afterEach, describe, expect, it, vi } from "vitest";

const catalog = vi.hoisted(() =>
  Array.from({ length: 808 }, (_, index) => ({
    category: ["visas", "business", "taxes", "property", "living", "trends"][
      index % 6
    ],
    slug: `published-story-${index}`,
    title: `Published story ${index}`,
    excerpt: "Published context",
    tags: [],
    publishedAt: "2026-01-02T00:00:00.000Z",
  })),
);

vi.mock("../lib/server/public-catalog", () => ({
  loadPublicCatalog: vi.fn(async () => catalog),
}));

import sitemap from "./sitemap";

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("public sitemap", () => {
  it("includes every public route class once and excludes migration aliases", async () => {
    vi.stubEnv("WEBSITE_PUBLIC_ORIGIN", "https://preview.example/");

    const entries = await sitemap();
    const urls = entries.map((entry) => entry.url);
    const paths = urls.map((url) => new URL(url).pathname);

    expect(new Set(urls).size).toBe(urls.length);
    expect(
      urls.every((url) => url.startsWith("https://preview.example/")),
    ).toBe(true);
    expect(
      entries.every(
        (entry) => !("priority" in entry) && !("changeFrequency" in entry),
      ),
    ).toBe(true);
    expect(paths.filter((route) => /^\/kbli\/\d{5}$/.test(route))).toHaveLength(
      1559,
    );
    expect(
      paths.filter((route) => /^\/kbli\/sectors\/[A-Z]$/.test(route)),
    ).toHaveLength(21);

    for (const article of catalog) {
      const entry = entries.find(
        ({ url }) =>
          new URL(url).pathname === `/${article.category}/${article.slug}`,
      );
      expect(entry, article.slug).toMatchObject({
        lastModified: article.publishedAt,
      });
    }

    for (const route of [
      "/services/visa",
      "/services/company",
      "/visa",
      `/${"jour"}nal`,
      "/visa/voa",
      "/prime",
      "/legacy/news",
      "/api/blog/articles",
    ]) {
      expect(paths, route).not.toContain(route);
    }
    expect(paths).toContain("/visa-oracle");
    expect(paths).not.toContain("/visa-oracle/unlock");
    expect(paths).not.toContain("/visa-oracle/privacy");
    expect(urls.some((url) => url.includes("?lang="))).toBe(false);
  });

  it("uses the default origin and the committed KBLI dataset date", async () => {
    vi.stubEnv("WEBSITE_PUBLIC_ORIGIN", "");

    const entries = await sitemap();
    expect(entries[0]?.url).toBe("https://balizero.com/");
    expect(
      entries.find(({ url }) => url === "https://balizero.com/kbli/01111"),
    ).toMatchObject({ lastModified: "2026-08-15" });
  });
});
