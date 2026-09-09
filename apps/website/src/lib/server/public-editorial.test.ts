import { mkdir, mkdtemp, rm, symlink, writeFile } from "node:fs/promises";
import path from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  decodePublicArticle,
  loadPublicArticle,
  loadPublicArticleResult,
  loadPublicJournalFeed,
} from "./public-editorial";

const article = (slug = "published-story", category = "business") => ({
  slug,
  category,
  status: "published",
  noIndex: false,
  title: "An owned published article",
  publishedAt: "2026-01-02T00:00:00Z",
  content: "## Context\n\nPublished article body.",
  excerpt: "A clear summary.",
  coverImage: "/static/news/story.jpg",
  author: { privateValue: "not projected" },
  mdxSource: { compiledSource: "never executed" },
});
const response = (value: unknown) =>
  new Response(JSON.stringify(value), {
    headers: { "content-type": "application/json" },
  });
const websiteRoot = process.cwd();
const temporaryArchives: string[] = [];

const authoredArticle = (slug: string, extra = "") => `---
title: "Local ${slug}"
slug: "${slug}"
category: "property"
publishedAt: "2026-01-02"
${extra}---
## Local context

Published article body.
`;

async function useTemporaryArchive(): Promise<{
  archive: string;
  sandbox: string;
}> {
  const sandbox = await mkdtemp(path.join(websiteRoot, ".mdx-loader-test-"));
  const archive = path.join(sandbox, "mouth", "src", "content", "articles");
  await mkdir(path.join(archive, "property"), { recursive: true });
  await mkdir(path.join(sandbox, "website"));
  temporaryArchives.push(sandbox);
  vi.spyOn(process, "cwd").mockReturnValue(path.join(sandbox, "website"));
  return { archive, sandbox };
}

afterEach(async () => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  await Promise.all(
    temporaryArchives
      .splice(0)
      .map((directory) => rm(directory, { recursive: true, force: true })),
  );
});

describe("current public editorial boundary", () => {
  it("allows only published documents and preserves the original category/slug URL", () => {
    const result = decodePublicArticle(
      article(),
      "business",
      "published-story",
    )!;
    expect(result.metadata.localHref).toBe("/business/published-story");
    expect(result.metadata.date?.label).toBe("2 January 2026");
    expect(result.markdown).toContain("Published article body");
    expect(JSON.stringify(result)).not.toMatch(/privateValue|compiledSource/);
  });
  it("rejects drafts, hidden/future documents, category mismatches and legacy demos", () => {
    for (const patch of [
      { status: "draft" },
      { noIndex: true },
      { publishedAt: null },
      { publishedAt: "2040-01-02T00:00:00Z" },
      { category: "taxes" },
    ]) {
      expect(
        decodePublicArticle(
          { ...article(), ...patch },
          "business",
          "published-story",
        ),
      ).toBeNull();
    }
    expect(
      decodePublicArticle(
        article("golden-visa-revolution", "visas"),
        "visas",
        "golden-visa-revolution",
      ),
    ).toBeNull();
    expect(
      decodePublicArticle(
        article("test-article", "business"),
        "business",
        "test-article",
      ),
    ).toBeNull();
  });
  it("does not fetch traversal/unknown routes and excludes foreign cover origins", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    expect(await loadPublicArticle("business", "../secret")).toBeNull();
    expect(await loadPublicArticle("internal", "published-story")).toBeNull();
    expect(fetcher).not.toHaveBeenCalled();
    expect(
      decodePublicArticle(
        { ...article(), coverImage: "https://other.invalid/image.jpg" },
        "business",
        "published-story",
      )?.metadata.image,
    ).toBeNull();
  });
  it("serves a published English MDX edition without calling fetch", async () => {
    const fetcher = vi.fn(() => {
      throw new Error("network access is forbidden");
    });
    vi.stubGlobal("fetch", fetcher);

    const result = await loadPublicArticleResult(
      "property",
      "leasehold-vs-freehold",
    );

    expect(result).toMatchObject({
      status: "ready",
      article: {
        metadata: {
          title:
            "Leasehold vs Freehold in Indonesia 2026: What Foreigners Need to Know",
        },
      },
    });
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("falls back to the legacy API only when no MDX file exists", async () => {
    const { archive } = await useTemporaryArchive();
    await writeFile(
      path.join(archive, "property", "local-story.mdx"),
      authoredArticle("local-story"),
      "utf8",
    );
    const fetcher = vi.fn(async (input: string) => {
      const slug = input.split("/").at(-1)!;
      return response({ ...article(slug, "property"), title: `API ${slug}` });
    });
    vi.stubGlobal("fetch", fetcher);

    expect(
      await loadPublicArticleResult("property", "local-story"),
    ).toMatchObject({
      status: "ready",
      article: { metadata: { title: "Local local-story" } },
    });
    expect(
      await loadPublicArticleResult("property", "api-only-story"),
    ).toMatchObject({
      status: "ready",
      article: { metadata: { title: "API api-only-story" } },
    });
    expect(fetcher).toHaveBeenCalledTimes(1);

    fetcher.mockResolvedValueOnce(new Response(null, { status: 404 }));
    expect(
      await loadPublicArticleResult("property", "missing-api-story"),
    ).toEqual({ status: "missing" });
  });
  it("rejects an MDX edition the publication gate refuses and does not consult the API", async () => {
    const { archive } = await useTemporaryArchive();
    await writeFile(
      path.join(archive, "property", "draft-story.mdx"),
      authoredArticle("draft-story", "status: draft\n"),
      "utf8",
    );
    await writeFile(
      path.join(archive, "property", "future-story.mdx"),
      authoredArticle("future-story").replace("2026-01-02", "2040-01-02"),
      "utf8",
    );
    const fetcher = vi.fn(async (input: string) => {
      const slug = input.split("/").at(-1)!;
      return response(article(slug, "property"));
    });
    vi.stubGlobal("fetch", fetcher);

    expect(await loadPublicArticleResult("property", "draft-story")).toEqual({
      status: "missing",
    });
    expect(await loadPublicArticleResult("property", "future-story")).toEqual({
      status: "missing",
    });
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("refuses traversal outside the archive root", async () => {
    const { archive, sandbox } = await useTemporaryArchive();
    const outside = path.join(sandbox, "outside.mdx");
    await writeFile(outside, authoredArticle("linked-story"), "utf8");
    await symlink(outside, path.join(archive, "property", "linked-story.mdx"));
    await symlink(
      path.join(sandbox, "missing.mdx"),
      path.join(archive, "property", "broken-story.mdx"),
    );
    const fetcher = vi.fn(async () =>
      response(article("linked-story", "property")),
    );
    vi.stubGlobal("fetch", fetcher);

    expect(await loadPublicArticleResult("property", "../outside")).toEqual({
      status: "missing",
    });
    expect(await loadPublicArticleResult("property", "linked-story")).toEqual({
      status: "missing",
    });
    expect(await loadPublicArticleResult("property", "broken-story")).toEqual({
      status: "missing",
    });
    expect(fetcher).not.toHaveBeenCalled();
  });
});
