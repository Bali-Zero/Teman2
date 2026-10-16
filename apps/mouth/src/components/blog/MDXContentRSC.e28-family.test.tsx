import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  ARTICLES_ROOT,
  compileArticlesInChunks,
  formatFailureAssertionMessage,
} from "./mdx-article-guard";

// The E28 family is served in five locales (the twin is picked by ?lang=), but
// the corpus guards above cover en and id only. These three guides carry the
// corrected E28 facts in every locale, so all fifteen files must compile with
// the production options.
const SLUGS = [
  "e28a-investor-kitas-guide",
  "golden-visa-indonesia-complete-guide",
  "investor-kitas-guide",
];
const SUFFIXES = ["", ".id", ".it", ".fr", ".ru"];
const files = SLUGS.flatMap((slug) =>
  SUFFIXES.map((s) =>
    path.join(ARTICLES_ROOT, "immigration", `${slug}${s}.mdx`),
  ),
);

describe("MDXContentRSC E28 family compilation guard (en, id, it, fr, ru)", () => {
  it("covers fifteen files", () => {
    expect(files).toHaveLength(15);
  });
  it("every E28 family article compiles in every locale", async () => {
    const failures = await compileArticlesInChunks(files, 5);
    expect(
      failures,
      formatFailureAssertionMessage("E28 family", failures),
    ).toEqual([]);
  }, 120000);
});
