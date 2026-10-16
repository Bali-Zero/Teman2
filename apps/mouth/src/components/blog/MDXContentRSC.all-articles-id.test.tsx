import { describe, expect, it } from "vitest";
import {
  ARTICLES_ROOT,
  compileArticlesInChunks,
  formatFailureAssertionMessage,
  walkMdxFiles,
} from "./mdx-article-guard";

const indonesianFiles = walkMdxFiles(ARTICLES_ROOT).filter((file) =>
  file.endsWith(".id.mdx"),
);

describe("MDXContentRSC Indonesian article compilation guard", () => {
  it("every Indonesian article compiles", async () => {
    expect(indonesianFiles.length).toBeGreaterThan(800);
    const failures = await compileArticlesInChunks(indonesianFiles, 8);
    expect(
      failures,
      formatFailureAssertionMessage("Indonesian", failures),
    ).toEqual([]);
  }, 180000);
});
