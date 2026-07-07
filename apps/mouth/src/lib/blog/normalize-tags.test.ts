import { describe, expect, it } from "vitest";
import { normalizeTags } from "./articles";

// Regression guard for the "TypeError: article.tags is not iterable" /
// "tags.join is not a function" article-page crash. Two real MDX articles
// (bali-ota-purge-2026, bali-real-estate-era-of-order-2026) had mis-indented
// frontmatter so gray-matter parsed `tags` as an OBJECT, not an array — and the
// backend `ai_tags` field (typed string[] | null) can arrive as a non-array at
// runtime. normalizeTags is the single data-layer boundary that guarantees a
// string[] so every downstream `.map` / `.length` / `[...tags]` is safe.

describe("normalizeTags", () => {
  it("passes a clean string[] through unchanged", () => {
    expect(normalizeTags(["bali", "visa", "kitas"])).toEqual([
      "bali",
      "visa",
      "kitas",
    ]);
  });

  it("returns [] for undefined (article has no tags frontmatter)", () => {
    expect(normalizeTags(undefined)).toEqual([]);
  });

  it("returns [] for null (backend ai_tags is null)", () => {
    expect(normalizeTags(null)).toEqual([]);
  });

  it("returns [] for a non-array OBJECT (the mis-indented-frontmatter bug)", () => {
    // This is exactly what gray-matter produced for bali-ota-purge-2026.mdx:
    // every later frontmatter field got nested under `tags:`.
    const malformed = {
      publishedAt: "2026-02-27",
      author: null,
      name: "Zantara AI",
    };
    expect(normalizeTags(malformed)).toEqual([]);
  });

  it("wraps a single string into a one-element array", () => {
    expect(normalizeTags("visa")).toEqual(["visa"]);
  });

  it("trims and wraps a single string, drops an empty/whitespace string", () => {
    expect(normalizeTags("  property  ")).toEqual(["property"]);
    expect(normalizeTags("   ")).toEqual([]);
    expect(normalizeTags("")).toEqual([]);
  });

  it("filters non-string members out of an array", () => {
    // Defensive: a backend array could contain nulls/numbers.
    expect(normalizeTags(["bali", null, 42, "tax", undefined])).toEqual([
      "bali",
      "tax",
    ]);
  });

  it("returns [] for other non-iterables (number, boolean)", () => {
    expect(normalizeTags(42)).toEqual([]);
    expect(normalizeTags(true)).toEqual([]);
  });

  it("the result is always a real array (spread-safe, .join-safe)", () => {
    for (const input of [undefined, null, {}, "x", 7, ["a"]]) {
      const out = normalizeTags(input);
      expect(Array.isArray(out)).toBe(true);
      // [...out] and out.join() must never throw.
      expect(() => [...out]).not.toThrow();
      expect(() => out.join(",")).not.toThrow();
    }
  });
});
