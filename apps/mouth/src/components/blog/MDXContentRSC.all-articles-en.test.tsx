import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  ARTICLES_ROOT,
  compileArticlesInChunks,
  formatFailureAssertionMessage,
  walkMdxFiles,
} from "./mdx-article-guard";

const englishFiles = walkMdxFiles(ARTICLES_ROOT).filter(
  (file) => !/\.(id|it|fr|ru)\.mdx$/.test(path.basename(file)),
);

describe("MDXContentRSC English article compilation guard", () => {
  it("every English article compiles", async () => {
    expect(englishFiles.length).toBeGreaterThan(800);
    const failures = await compileArticlesInChunks(englishFiles, 8);
    expect(
      failures,
      formatFailureAssertionMessage("English", failures),
    ).toEqual([]);
  }, 180000);
});
