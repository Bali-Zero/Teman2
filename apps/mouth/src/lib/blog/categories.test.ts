import { describe, it, expect } from "vitest";
import fs from "fs";
import path from "path";
import {
  CATEGORY_MAP,
  LOCALE_SUFFIXES,
  articleUrl,
  normalizeCategory,
  publicSlug,
} from "./categories";

const ARTICLES_PATH = path.join(process.cwd(), "src/content/articles");

/**
 * The categories the live site actually routes, read off the published sitemap
 * on 2026-08-11. Anything a URL builder emits outside this set renders
 * "Article not found" — which is precisely the bug this module exists to close,
 * so the set is pinned here rather than derived from the same code under test.
 */
const SERVED_CATEGORIES = new Set([
  "visas",
  "business",
  "taxes",
  "property",
  "living",
  "trends",
]);

describe("normalizeCategory", () => {
  it("maps every content folder on disk to a category the site serves", () => {
    const folders = fs
      .readdirSync(ARTICLES_PATH)
      .filter(
        (f) =>
          fs.statSync(path.join(ARTICLES_PATH, f)).isDirectory() &&
          !f.startsWith("."),
      );

    expect(folders.length).toBeGreaterThan(0);
    for (const folder of folders) {
      expect(
        CATEGORY_MAP,
        `folder "${folder}" has no entry in CATEGORY_MAP — its URLs would fall through to the "living" default`,
      ).toHaveProperty(folder);
      expect(SERVED_CATEGORIES).toContain(normalizeCategory(folder));
    }
  });

  it("collapses the folders that share a public category", () => {
    expect(normalizeCategory("business_regulations")).toBe("business");
    expect(normalizeCategory("immigration")).toBe("visas");
    expect(normalizeCategory("tax-legal")).toBe("taxes");
    expect(normalizeCategory("tax")).toBe("taxes");
    expect(normalizeCategory("lifestyle")).toBe("living");
    expect(normalizeCategory("emerging_trends")).toBe("trends");
  });

  it("falls back to living for an unknown folder", () => {
    expect(normalizeCategory("no-such-folder")).toBe("living");
  });
});

describe("publicSlug", () => {
  it("returns the base slug for every language variant", () => {
    for (const locale of LOCALE_SUFFIXES) {
      expect(publicSlug(`the-honest-map-blocked-bali-codes.${locale}.mdx`)).toBe(
        "the-honest-map-blocked-bali-codes",
      );
    }
    expect(publicSlug("the-honest-map-blocked-bali-codes.mdx")).toBe(
      "the-honest-map-blocked-bali-codes",
    );
  });

  it("strips only KNOWN locales, never any trailing two-letter segment", () => {
    // `de` is not a variant we publish; truncating here would silently point at
    // a different article.
    expect(publicSlug("some-article.de.mdx")).toBe("some-article.de");
    expect(publicSlug("v1.2.mdx")).toBe("v1.2");
  });

  /**
   * Translated variants whose base `.mdx` does not exist. `getAllArticleSlugs`
   * enumerates base files only, so such an article has no page and no sitemap
   * entry — it exists on disk in one language and is invisible on the site.
   * That is a content gap, not a slug bug, so it is pinned rather than papered
   * over: a SECOND one must fail this test, not join a silent tolerance.
   */
  const KNOWN_ORPHAN_VARIANTS = new Set([
    "immigration/driving-license-bali-foreigners-2026.id.mdx",
  ]);

  it("never produces a slug that no .mdx file backs", () => {
    const folders = fs
      .readdirSync(ARTICLES_PATH)
      .filter((f) =>
        fs.statSync(path.join(ARTICLES_PATH, f)).isDirectory(),
      );
    for (const folder of folders) {
      const files = fs
        .readdirSync(path.join(ARTICLES_PATH, folder))
        .filter((f) => f.endsWith(".mdx"));
      const baseSlugs = new Set(
        files
          .filter((f) => !LOCALE_SUFFIXES.some((l) => f.endsWith(`.${l}.mdx`)))
          .map((f) => f.replace(/\.mdx$/, "")),
      );
      for (const file of files) {
        if (KNOWN_ORPHAN_VARIANTS.has(`${folder}/${file}`)) continue;
        const slug = publicSlug(file);
        expect(
          baseSlugs.has(slug),
          `${folder}/${file} → "${slug}", which has no base .mdx — either add the base article or pin it in KNOWN_ORPHAN_VARIANTS`,
        ).toBe(true);
      }
    }
  });
});

describe("articleUrl", () => {
  it("builds the URL the site actually serves", () => {
    expect(
      articleUrl(
        "business_regulations",
        "the-honest-map-blocked-bali-codes.it.mdx",
      ),
    ).toBe("https://balizero.com/business/the-honest-map-blocked-bali-codes");
  });

  it("gives every language variant of an article the same URL", () => {
    const urls = ["mdx", "it.mdx", "id.mdx", "fr.mdx", "ru.mdx"].map((suffix) =>
      articleUrl("immigration", `kitas-guide.${suffix}`),
    );
    expect(new Set(urls).size).toBe(1);
    expect(urls[0]).toBe("https://balizero.com/visas/kitas-guide");
  });
});
