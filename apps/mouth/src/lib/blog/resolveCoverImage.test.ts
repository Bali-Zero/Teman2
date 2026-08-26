/**
 * Cover images that do not exist.
 *
 * Until 2026-08-27 an MDX article's cover was a guess nobody checked:
 * `frontmatter.coverImage || frontmatter.image?.src ||
 *  `/static/blog/${folder}/${slug}.jpg``. The live sweep of balizero.com found
 * three `_next/image` 400s on `/news`; walking the corpus found 57 articles in
 * the same state, across six folders — 30 from the per-slug guess (the images
 * live under `static/insights/`, a tree the fallback never looked at) and 27
 * from explicit frontmatter naming a file that is not in the repo at all.
 *
 * The suite is in two halves on purpose:
 *
 *   - the UNIT half pins the ordering with an injected `exists`, so it states
 *     the rule independently of which assets happen to be checked in today;
 *   - the CORPUS half runs the real resolver over every real article with the
 *     real filesystem, and is the one that actually fails if someone points
 *     the fallback at another wrong directory. It reads frontmatter with
 *     gray-matter — the same parser the code under test uses — so the two
 *     cannot disagree about what an explicit cover is.
 */
import fs from "fs";
import path from "path";
import matter from "gray-matter";
import { describe, expect, it } from "vitest";

import { resolveCoverImage } from "./articles";

const PUBLIC = path.join(process.cwd(), "public");
const ARTICLES = path.join(process.cwd(), "src/content/articles");

// A predicate over a set of site-absolute paths, so a case reads as "these
// files exist and nothing else does".
const only =
  (...present: string[]) =>
  (absolute: string) =>
    present.some((rel) => absolute === path.join(PUBLIC, rel));

const NOTHING = () => false;

describe("resolveCoverImage — guilt: never emits a path that is not there", () => {
  it("drops an explicit cover that does not exist, for the category default", () => {
    const got = resolveCoverImage(
      "/static/insights/tax/ppn-12-percent.jpg", // real frontmatter, absent file
      "tax",
      "ppn-12-percent-increase-2026",
      "taxes",
      NOTHING,
    );
    expect(got).toBe("/static/blog/tax-calendar.jpg");
    expect(got).not.toContain("ppn-12-percent");
  });

  it("finds the image in insights/ when the old blog/ guess was empty", () => {
    const got = resolveCoverImage(
      undefined,
      "tax",
      "coretax-npwp-problems-2026",
      "taxes",
      only("/static/insights/tax/coretax-npwp-problems-2026.jpg"),
    );
    expect(got).toBe("/static/insights/tax/coretax-npwp-problems-2026.jpg");
  });

  it("falls back to the category cover when the slug has no image anywhere", () => {
    expect(
      resolveCoverImage(
        undefined,
        "tax",
        "pph-final-umkm-profesi-khusus",
        "taxes",
        NOTHING,
      ),
    ).toBe("/static/blog/tax-calendar.jpg");
  });

  it("refuses a candidate that tries to climb out of public/", () => {
    // The predicate says yes to the traversal target and to nothing else, so
    // if the resolver ever asked about it, it would return it. Reaching the
    // category default is the proof that it never asked.
    expect(
      resolveCoverImage(
        "/static/../../etc/passwd",
        "tax",
        "x",
        "taxes",
        (absolute) => absolute.includes("etc/passwd"),
      ),
    ).toBe("/static/blog/tax-calendar.jpg");
  });
});

describe("resolveCoverImage — innocence: an author's working choice is untouched", () => {
  it("returns an explicit cover verbatim when the file is there", () => {
    const explicit =
      "/static/insights/tax/indonesia-zero-tax-foreign-income-2026.jpg";
    expect(
      resolveCoverImage(
        explicit,
        "tax",
        "whatever-slug",
        "taxes",
        only(explicit),
      ),
    ).toBe(explicit);
  });

  it("prefers the explicit cover over both per-slug guesses when all three exist", () => {
    const explicit = "/static/news/hand-picked.jpg";
    expect(
      resolveCoverImage(explicit, "tax", "slug", "taxes", () => true),
    ).toBe(explicit);
  });

  it("passes a remote URL straight through without touching the filesystem", () => {
    let asked = false;
    const got = resolveCoverImage(
      "https://cdn.example.com/cover.jpg",
      "news",
      "slug",
      "trends",
      () => {
        asked = true;
        return false;
      },
    );
    expect(got).toBe("https://cdn.example.com/cover.jpg");
    expect(asked).toBe(false);
  });

  it("gives every known category a default that ships in the repo", () => {
    for (const category of [
      "visas",
      "business",
      "taxes",
      "property",
      "living",
      "trends",
    ] as const) {
      const got = resolveCoverImage(undefined, "any", "any", category, NOTHING);
      expect(fs.existsSync(path.join(PUBLIC, got))).toBe(true);
    }
  });

  it("gives an unrecognised category a default that ships too", () => {
    const got = resolveCoverImage(
      undefined,
      "weird",
      "slug",
      "not-a-category" as never,
      NOTHING,
    );
    expect(fs.existsSync(path.join(PUBLIC, got))).toBe(true);
  });
});

describe("resolveCoverImage — the corpus: every article resolves to a real file", () => {
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
    // Without this, an empty read would make the sweep below vacuously green —
    // which is exactly the shape of proof this repo does not accept.
    expect(articles.length).toBeGreaterThan(100);
  });

  it("resolves every MDX cover to a file that exists (or a remote URL)", () => {
    const broken: string[] = [];

    for (const { folder, file } of articles) {
      const slug = file.replace(/\.mdx$/, "");
      const { data } = matter(
        fs.readFileSync(path.join(ARTICLES, folder, file), "utf8"),
      );
      const resolved = resolveCoverImage(
        data.coverImage || data.image?.src,
        folder,
        slug,
        data.category,
      );
      if (!resolved.startsWith("/")) continue; // remote, cannot be checked here
      if (!fs.existsSync(path.join(PUBLIC, resolved))) {
        broken.push(`${folder}/${slug} -> ${resolved}`);
      }
    }

    expect(broken).toEqual([]);
  });
});
