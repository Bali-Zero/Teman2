import { describe, expect, it } from "vitest";
import { readFile } from "node:fs/promises";
import { articleFolders, decodeAuthoredTranslation, isArticleLocale, loadAuthoredTranslations } from "./article-translations";

const fixture = `---
title: "Una storia pubblicata"
slug: "published-story"
category: "business"
locale: "it"
publishedAt: "2026-01-02"
---
## Il contesto

Testo integrale della traduzione pubblicata.
`;

describe("authored article translations", () => {
  it("retains the authored body and only the selected locale in public URLs", () => {
    const result = decodeAuthoredTranslation(fixture, "business", "published-story", "it");
    expect(result?.metadata.title).toBe("Una storia pubblicata");
    expect(result?.metadata.localHref).toBe("/business/published-story?lang=it");
    expect(result?.markdown).toContain("Testo integrale della traduzione pubblicata.");
  });
  it("rejects drafts, identity/language mismatches, future dates and executable frontmatter", () => {
    for (const source of [fixture.replace('locale: "it"', 'locale: "fr"'), fixture.replace('category: "business"', 'category: "property"'), fixture.replace('2026-01-02', '2040-01-02'), fixture.replace('locale: "it"', 'locale: "it"\nstatus: draft'), fixture.replace('locale: "it"', 'locale: "it"\nnoIndex: true'), fixture.replace(/^---/, '---js')]) {
      expect(decodeAuthoredTranslation(source, "business", "published-story", "it")).toBeNull();
    }
    expect(isArticleLocale(["it"])).toBe(false);
    expect(isArticleLocale("../private")).toBe(false);
  });
  it("reads the existing Italian article and preserves every authored section", async () => {
    const source = await readFile('../mouth/src/content/articles/property/leasehold-vs-freehold.it.mdx', 'utf8');
    const result = await loadAuthoredTranslations("property", "leasehold-vs-freehold");
    expect(result.it?.markdown).toBe(decodeAuthoredTranslation(source, "property", "leasehold-vs-freehold", "it")?.markdown);
    expect(result.it?.metadata.title).toContain("Guida per Stranieri");
    expect([...result.it!.markdown!.matchAll(/^#{2,3} /gm)].length).toBe([...source.matchAll(/^#{2,3} /gm)].length);
  });
  it("keeps the source folder order and refuses path traversal before filesystem access", async () => {
    const source = await readFile('../mouth/src/lib/blog/articles.ts', 'utf8');
    for (const [category, folders] of Object.entries(articleFolders)) {
      expect(source).toContain(`${category}: [${folders.map((folder) => JSON.stringify(folder)).join(', ')}]`);
    }
    expect(await loadAuthoredTranslations("business", "../private")).toEqual({});
    expect(await loadAuthoredTranslations("private", "published-story")).toEqual({});
  });
});
