import { describe, expect, it } from "vitest";
import { safeArticleUrl } from "./article-urls";

describe("article destination continuity", () => {
  it("keeps authored edition links inside the native reader", () => {
    for (const locale of ["en", "id", "it", "fr", "ru"]) {
      expect(safeArticleUrl(`https://balizero.com/${locale}/insights/property/leasehold-vs-freehold?token=private#comparison`))
        .toBe(`/property/leasehold-vs-freehold?lang=${locale}#comparison`);
    }
  });
  it("keeps every supported legacy article identifier local, including authored editions", () => {
    for (const slug of ["news_20260907_173053_1e7fa0d1", "published---story-"]) {
      expect(safeArticleUrl(`https://balizero.com/trends/${slug}#context`)).toBe(`/trends/${slug}#context`);
      expect(safeArticleUrl(`/insights/trends/${slug}`)).toBe(`/trends/${slug}`);
      expect(safeArticleUrl(`/it/insights/trends/${slug}?token=private#context`)).toBe(`/trends/${slug}?lang=it#context`);
    }
  });
  it("preserves authored email drafts while rejecting malformed recipients and executable protocols", () => {
    expect(safeArticleUrl("mailto:hello@balizero.com")).toBe("mailto:hello@balizero.com");
    expect(safeArticleUrl("mailto:hello@balizero.com?subject=Article%20question")).toBe("mailto:hello@balizero.com?subject=Article%20question");
    for (const value of ["mailto:", "mailto:not-an-address", "mailto:hello%0d%0aBcc:other@balizero.com", "data:text/html,test", "javascript:alert(1)"]) {
      expect(safeArticleUrl(value)).toBe("");
    }
  });
  it("does not rewrite a foreign origin or invent an unsupported edition", () => {
    for (const href of ["https://example.com/it/insights/property/guide", "https://balizero.com/de/insights/property/guide"]) {
      expect(safeArticleUrl(href)).toBe(href);
    }
    expect(safeArticleUrl("javascript:alert(1)")).toBe("");
    expect(safeArticleUrl("https://user:secret@balizero.com/it/insights/property/guide")).toBe("");
  });
});
