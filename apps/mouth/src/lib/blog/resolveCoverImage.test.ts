/**
 * Covers that point at nothing.
 *
 * The live sweep of balizero.com on 2026-08-27 found three `_next/image` 400s
 * on `/news`. Walking the corpus found 57 articles in the same state across
 * six folders: 30 fell through to a per-slug guess, `/static/blog/<folder>/
 * <slug>.jpg`, whose images had actually been generated into a different tree
 * (`static/insights/`), and 27 named a cover explicitly that is not in the
 * repo under any path.
 *
 * WHY THERE IS NO `fs.existsSync` HERE, and why re-adding one is a regression:
 * the first version of this cure stat'd the candidates at request time and
 * kept the one that existed. `next.config.ts` excludes `./public/static/**`
 * from serverless tracing (public/ is 537MB against a 300MB function limit)
 * while explicitly including `src/content/articles/**`. In the Vercel function
 * the articles are present and the images are not, so that check would answer
 * false for every cover and silently collapse all ~3,300 articles onto their
 * category default. Production cannot answer the question at runtime.
 *
 * So the runtime rule is trivial — frontmatter, else the category cover — and
 * the real check lives HERE, in CI, where public/ is present. That is what the
 * corpus block below is: a build-time proof that every path frontmatter states
 * has a file behind it. It is the half that fails if someone re-introduces a
 * guess or lets an asset go missing.
 */
import fs from "fs";
import path from "path";
import matter from "gray-matter";
import { describe, expect, it } from "vitest";

import { resolveCoverImage } from "./articles";

const PUBLIC = path.join(process.cwd(), "public");
const ARTICLES = path.join(process.cwd(), "src/content/articles");

describe("resolveCoverImage — the rule", () => {
  it("returns what frontmatter states, untouched", () => {
    const explicit = "/static/insights/tax/tax-residency-indonesia.jpg";
    expect(resolveCoverImage(explicit, "taxes")).toBe(explicit);
  });

  it("passes a remote cover through", () => {
    expect(resolveCoverImage("https://cdn.example.com/a.jpg", "trends")).toBe(
      "https://cdn.example.com/a.jpg",
    );
  });

  it("falls back to the category cover when frontmatter is silent", () => {
    expect(resolveCoverImage(undefined, "taxes")).toBe(
      "/static/blog/tax-calendar.jpg",
    );
    expect(resolveCoverImage(null, "property")).toBe(
      "/static/blog/golden-visa.jpg",
    );
    expect(resolveCoverImage("", "living")).toBe("/static/blog/north-bali.jpg");
  });

  it("never invents a path when frontmatter is silent", () => {
    // The defect was a fabricated per-slug path. Whatever the fallback is, it
    // must come from the fixed set of category covers — never be derived from
    // an article's own slug or folder. This is what goes red if someone
    // re-adds a guess.
    const KNOWN = new Set([
      "/static/blog/kitas-guide.jpg",
      "/static/blog/oss-guide.jpg",
      "/static/blog/tax-calendar.jpg",
      "/static/blog/golden-visa.jpg",
      "/static/blog/north-bali.jpg",
      "/static/blog/nomad-comparison.jpg",
    ]);
    for (const category of [
      "visas",
      "business",
      "taxes",
      "property",
      "living",
      "trends",
    ] as const) {
      expect(KNOWN.has(resolveCoverImage(undefined, category))).toBe(true);
    }
  });

  it("gives every category — known or not — a default that ships", () => {
    const categories = [
      "visas",
      "business",
      "taxes",
      "property",
      "living",
      "trends",
      "not-a-category",
    ] as const;
    for (const category of categories) {
      const got = resolveCoverImage(undefined, category as never);
      expect(fs.existsSync(path.join(PUBLIC, got))).toBe(true);
    }
  });
});

describe("resolveCoverImage — the corpus: every cover has a file behind it", () => {
  const articles = fs.existsSync(ARTICLES)
    ? fs
        .readdirSync(ARTICLES, { withFileTypes: true })
        .filter((d) => d.isDirectory())
        .flatMap((dir) =>
          fs
            .readdirSync(path.join(ARTICLES, dir.name))
            .filter((f) => f.endsWith(".mdx"))
            .map((f) => ({ folder: dir.name, file: f })),
        )
    : [];

  it("has a corpus to check at all", () => {
    // An empty read would make the sweep below vacuously green — the exact
    // shape of proof this repo does not accept.
    expect(articles.length).toBeGreaterThan(100);
  });

  it("reads real frontmatter — at least one article states its own cover", () => {
    // Guards the other direction: if the parse silently returned {} for every
    // file, the sweep would be checking only category defaults and would pass
    // while telling us nothing about the 27 explicit covers it exists to hold.
    const stated = articles.filter(({ folder, file }) => {
      const { data } = matter(
        fs.readFileSync(path.join(ARTICLES, folder, file), "utf8"),
      );
      return Boolean(data.coverImage || data.image?.src);
    });
    expect(stated.length).toBeGreaterThan(1000);
  });

  it("resolves every article to a file that exists (or a remote URL)", () => {
    const broken: string[] = [];

    for (const { folder, file } of articles) {
      const { data } = matter(
        fs.readFileSync(path.join(ARTICLES, folder, file), "utf8"),
      );
      const resolved = resolveCoverImage(
        data.coverImage || data.image?.src,
        data.category,
      );
      if (/^(https?:)?\/\//.test(resolved)) continue; // remote, not ours to check
      if (!fs.existsSync(path.join(PUBLIC, resolved))) {
        broken.push(`${folder}/${file.replace(/\.mdx$/, "")} -> ${resolved}`);
      }
    }

    expect(broken).toEqual([]);
  });
});
