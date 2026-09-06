import { describe, expect, it } from "vitest";
import {
  developmentOnlyArticleFixture,
  getPublicJournalArticles,
  journalArticleRecords,
} from "./journal";

describe("journal content contract", () => {
  it("starts from the six existing R19 story records without duplicates", () => {
    expect(journalArticleRecords).toHaveLength(6);
    expect(new Set(journalArticleRecords.map(({ slug }) => slug)).size).toBe(6);
    expect(
      new Set(journalArticleRecords.map(({ sourceUrl }) => sourceUrl)).size,
    ).toBe(6);
  });

  it("admits only verified records to the public index", () => {
    expect(getPublicJournalArticles()).toHaveLength(6);
    expect(
      getPublicJournalArticles().every(
        ({ verificationStatus }) => verificationStatus === "verified",
      ),
    ).toBe(true);
    expect(getPublicJournalArticles()).not.toContain(
      developmentOnlyArticleFixture.metadata,
    );
  });

  it("keeps observed publication metadata and final destinations complete", () => {
    for (const article of getPublicJournalArticles()) {
      expect(article.category).toBeTruthy();
      expect(article.date).toEqual({
        iso: expect.stringMatching(/^2026-\d{2}-\d{2}$/),
        label: expect.stringMatching(/2026$/),
      });
      expect(article.finalSourceUrl).toBe(article.sourceUrl);
    }
  });

  it("keeps the fixture outside the public record collection", () => {
    expect(developmentOnlyArticleFixture.indexing).toBe("excluded");
    expect(developmentOnlyArticleFixture.metadata.verificationStatus).toBe(
      "development-only",
    );
    expect(
      journalArticleRecords.some(
        ({ slug }) => slug === developmentOnlyArticleFixture.metadata.slug,
      ),
    ).toBe(false);
  });
});
