import { CHAPTERS } from "./book-data";
import {
  BOOK_BRAND,
  chapterTitleMetadata,
  renderedChapterTitle,
} from "./book-title";

/**
 * Composition guard for the book chapter titles (2026-07-29).
 *
 * The sibling guard `src/app/metadata-title-template.test.ts` reads STATIC
 * `export const metadata` only, so it is structurally blind to a title built
 * inside `generateMetadata()` — which is what `(book)/book/[chapter]` does.
 * That blind spot is where the second stutter lived: measured in production,
 *
 *   /book/cover → <title>Bali Zero — Bali Zero</title>
 *
 * because the cover chapter's title IS the brand and the layout template
 * appends it again. So this file covers the shape the other one declares it
 * cannot see — a surface excluded "for later" is a surface covered never.
 *
 * It asserts against the REAL chapter data, not a fixture: a future chapter
 * titled with the brand fails here on the day it is written.
 */

describe("book chapter titles vs the (book) template", () => {
  it("has chapters to check (the probe can produce a positive)", () => {
    expect(CHAPTERS.length).toBeGreaterThan(3);
  });

  it("no chapter renders the brand twice", () => {
    const offenders = CHAPTERS.filter(
      (c) => renderedChapterTitle(c.title).split(BOOK_BRAND).length - 1 > 1,
    ).map((c) => `${c.id}: ${renderedChapterTitle(c.title)}`);
    expect(offenders).toEqual([]);
  });

  it("every chapter still shows the brand once", () => {
    // The cure must not swing the other way: opting out of the template is
    // only correct when the title already carries the brand itself.
    const missing = CHAPTERS.filter(
      (c) => !renderedChapterTitle(c.title).includes(BOOK_BRAND),
    ).map((c) => c.id);
    expect(missing).toEqual([]);
  });

  it("the cover — the chapter that shipped the stutter — is pinned (guilt)", () => {
    const cover = CHAPTERS.find((c) => c.id === "cover");
    expect(cover?.title).toBe(BOOK_BRAND);
    expect(chapterTitleMetadata(cover!.title)).toEqual({
      absolute: BOOK_BRAND,
    });
    expect(renderedChapterTitle(cover!.title)).toBe(BOOK_BRAND);
  });

  it("an ordinary chapter keeps the template (innocence)", () => {
    expect(chapterTitleMetadata("The meeting that changed everything")).toBe(
      "The meeting that changed everything",
    );
    expect(renderedChapterTitle("The meeting that changed everything")).toBe(
      "The meeting that changed everything — Bali Zero",
    );
  });
});
