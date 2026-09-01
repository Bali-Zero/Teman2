/**
 * The 2026-07-30 cure for the root-namespace soft-404 was applied to
 * `layout.tsx` — both its `generateMetadata` (return "Page not found",
 * noindex) and its default export (`notFound()` for anything outside the
 * allow-list). It is correct, and `layout.test.tsx` covers it.
 *
 * It did not hold in production, and this file is why: `page.tsx` exports its
 * OWN `generateMetadata`, and in the Next App Router a page's metadata
 * OVERRIDES its layout's. So the layout returned "Page not found" and the page
 * put the invented title straight back.
 *
 * Measured live on 2026-08-27, four weeks after that cure landed:
 *   GET https://balizero.com/nope-single-segment
 *   -> HTTP 200, <title>Nope-single-segment Insights | Bali Zero</title>
 * over a body that renders the blog not-found ("Article not found"). Any
 * single-segment path mints a Bali Zero title from attacker-chosen text.
 *
 * Guilt: junk segments get the not-found title and noindex.
 * Innocence: all six real categories keep their own SEO metadata untouched.
 */
import { describe, expect, it } from "vitest";

import { generateMetadata } from "./page";
import { generateMetadata as layoutMetadata } from "./layout";
import type { ArticleCategory } from "@/lib/blog/types";

/**
 * DERIVED from the layout, never transcribed: the whole defect was the two
 * halves disagreeing, so a hand-copied literal here would reproduce exactly
 * the blindness this file exists to close. If someone edits the layout's
 * wording, this suite follows it instead of going green against a stale copy.
 */
const NOT_FOUND_TITLE = String(
  (
    await layoutMetadata({
      params: Promise.resolve({ category: "zzz-derive" }),
    })
  ).title,
);

const REAL_CATEGORIES: ArticleCategory[] = [
  "visas",
  "business",
  "taxes",
  "property",
  "living",
  "trends",
];

// The live probe plus the shapes an SEO-spam crawler actually walks.
const JUNK = [
  "nope-single-segment",
  "zzz-nonsense",
  "buy-cheap-visas",
  "id",
  "it",
  "cases",
  "wp-admin",
];

const meta = (category: string) =>
  generateMetadata({ params: Promise.resolve({ category }) });

/** Every string VALUE reachable in a metadata object, keys excluded. */
function collectStrings(value: unknown, out: string[] = []): string[] {
  if (typeof value === "string") out.push(value);
  else if (Array.isArray(value)) value.forEach((v) => collectStrings(v, out));
  else if (value && typeof value === "object")
    Object.values(value).forEach((v) => collectStrings(v, out));
  return out;
}

describe("(blog)/[category] page metadata — guilt", () => {
  it.each(JUNK)(
    "does not mint a title from the URL segment: /%s",
    async (category) => {
      const m = await meta(category);
      expect(m.title).toBe(NOT_FOUND_TITLE);
      // The root layout sets the title template `%s | Bali Zero`, so this
      // string must NOT carry the suffix itself — the first draft of this
      // guard did, which would have rendered "… | Bali Zero | Bali Zero".
      expect(String(m.title)).not.toContain("Bali Zero");
      // The segment must appear in no metadata VALUE — that is the whole
      // defect: arbitrary caller text reaching a Bali Zero <title>.
      // Deliberately NOT a substring scan of the serialized object: the
      // key names are part of that string, and `"title"` contains `"it"`,
      // so a JSON-wide scan fails on the real locale-root probe `/it` for a
      // reason that has nothing to do with the guard (superscar #3,
      // over-match — this test tripped on it on first run).
      for (const value of collectStrings(m)) {
        expect(value.toLowerCase()).not.toContain(category.toLowerCase());
      }
    },
  );

  it.each(JUNK)("marks junk noindex,nofollow: /%s", async (category) => {
    const m = await meta(category);
    expect(m.robots).toMatchObject({ index: false, follow: false });
  });
});

describe("(blog)/[category] page metadata — innocence", () => {
  it.each(REAL_CATEGORIES)(
    "leaves the real category's own metadata intact: /%s",
    async (category) => {
      const m = await meta(category);
      expect(m.title).not.toBe(NOT_FOUND_TITLE);
      expect(typeof m.title).toBe("string");
      expect(String(m.title).length).toBeGreaterThan(0);
      // A real category must never be marked noindex by this guard.
      expect(m.robots ?? null).not.toMatchObject({ index: false });
    },
  );

  it("keeps the six real categories and the junk set disjoint", () => {
    // Guards against a future edit that quietly narrows VALID_CATEGORIES and
    // makes the guilt suite pass for the wrong reason.
    for (const c of REAL_CATEGORIES) {
      expect(JUNK).not.toContain(c);
    }
  });
});
