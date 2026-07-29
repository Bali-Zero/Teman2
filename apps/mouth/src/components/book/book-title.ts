/**
 * How a book chapter's title becomes the page title.
 *
 * `(book)/layout.tsx` declares `title.template = '%s — Bali Zero'`, so Next.js
 * appends the brand to every chapter title on its own. One chapter — the cover —
 * is literally titled "Bali Zero", and the append produced a stutter that was
 * live in production until 2026-07-29:
 *
 *   /book/cover → <title>Bali Zero — Bali Zero</title>
 *
 * It lives here, not inline in the route, so the rule can be composed against
 * the real chapter data in a test instead of being asserted about itself.
 */

/** The brand the (book) layout's title template appends. */
export const BOOK_BRAND = "Bali Zero";

/** The `— Bali Zero` suffix that template adds. */
export const BOOK_TITLE_SUFFIX = ` — ${BOOK_BRAND}`;

/**
 * The `title` a chapter page should export.
 *
 * A title that already carries the brand opts out of the parent template via
 * `absolute` (Next.js: `absolute` ignores any ancestor `template`); every other
 * chapter returns a plain string and keeps the template.
 */
export function chapterTitleMetadata(
  chapterTitle: string,
): string | { absolute: string } {
  return chapterTitle.includes(BOOK_BRAND)
    ? { absolute: chapterTitle }
    : chapterTitle;
}

/** What Next.js will actually render for that chapter — the composed title. */
export function renderedChapterTitle(chapterTitle: string): string {
  const meta = chapterTitleMetadata(chapterTitle);
  return typeof meta === "string" ? meta + BOOK_TITLE_SUFFIX : meta.absolute;
}
