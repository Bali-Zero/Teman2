/**
 * `(blog)/[category]` is top-level `/:something` — a route group contributes
 * nothing to the URL — so it matches every unmatched single-segment path on
 * every domain this project serves. It used to render the category page with an
 * empty article list and return HTTP 200, and `generateMetadata` title-cased
 * whatever was in the URL ("Zzz-nonsense Insights"). That is an unbounded set of
 * indexable soft-404s.
 *
 * Guilt: junk 404s. Innocence: all six real categories still render.
 */
import { describe, expect, it } from "vitest";

import CategoryLayout, { generateMetadata } from "./layout";
import type { ArticleCategory } from "@/lib/blog/types";
import { CATEGORY_MAP } from "@/lib/blog/categories";

const REAL_CATEGORIES: ArticleCategory[] = [
  "visas",
  "business",
  "taxes",
  "property",
  "living",
  "trends",
];

// Measured live on 2026-07-30, all returning 200 with an invented title.
const JUNK = [
  "zzz-nonsense",
  "slhs",
  "cases",
  "id",
  "it",
  "this-path-does-not-exist-4711",
];

// `hasOwnProperty` rather than `in`: with `in`, every Object.prototype member
// passes the allow-list and /constructor would render as a category.
const PROTOTYPE_KEYS = [
  "constructor",
  "toString",
  "hasOwnProperty",
  "valueOf",
  "__proto__",
];

const call = (category: string) =>
  CategoryLayout({
    children: "children" as unknown as React.ReactNode,
    params: Promise.resolve({ category }),
  });

describe("(blog)/[category] layout: unknown categories must 404, not 200", () => {
  it.each([
    ...PROTOTYPE_KEYS,
    ...Object.entries(CATEGORY_MAP)
      .filter(([alias, target]) => alias !== target)
      .map(([alias]) => alias),
  ])("rejects /%s in both layout and metadata", async (category) => {
    await expect(call(category)).rejects.toThrow();
    expect(
      await generateMetadata({ params: Promise.resolve({ category }) }),
    ).toEqual({
      title: "Page not found",
      robots: { index: false, follow: false },
    });
  });

  for (const category of JUNK) {
    it(`guilt: /${category} calls notFound()`, async () => {
      await expect(call(category)).rejects.toThrow();
    });
  }

  for (const category of PROTOTYPE_KEYS) {
    it(`guilt: /${category} is not a category just because Object has that key`, async () => {
      await expect(call(category)).rejects.toThrow();
    });
  }

  for (const category of REAL_CATEGORIES) {
    it(`innocence: /${category} still renders`, async () => {
      await expect(call(category)).resolves.toBe("children");
    });
  }

  it("guilt: metadata for an unknown category is noindex and invents no title", async () => {
    const meta = await generateMetadata({
      params: Promise.resolve({ category: "zzz-nonsense" }),
    });
    expect(meta.title).toBe("Page not found");
    expect(meta.robots).toEqual({ index: false, follow: false });
    // The old behaviour, pinned so it cannot come back.
    expect(JSON.stringify(meta)).not.toContain("Zzz-nonsense");
    expect(JSON.stringify(meta)).not.toContain("zzz-nonsense");
  });

  it("innocence: metadata for a real category keeps its SEO title and canonical", async () => {
    const meta = await generateMetadata({
      params: Promise.resolve({ category: "visas" }),
    });
    expect(meta.title).toBe("Immigration & Visa Guides Bali 2026");
    expect(meta.alternates?.canonical).toContain("/visas");
    expect(meta.robots).toBeUndefined();
  });
});
