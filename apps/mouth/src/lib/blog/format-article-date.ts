/**
 * Article date display for the public blog / news / journal surfaces.
 *
 * The server renders in UTC (Vercel) while the reader's browser renders in its
 * own zone — Asia/Makassar (WITA) for the Bali audience. A formatter that reads
 * the process zone (`toLocaleDateString`, date-fns `format`) prints a different
 * calendar day for anything published between 16:00 and 24:00 UTC, so React
 * hydration fails (#418) on every such article. Pin the business zone
 * explicitly so the server HTML and the client agree by construction.
 */
export const BLOG_TIME_ZONE = "Asia/Makassar";

const ARTICLE_DATE = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
  timeZone: BLOG_TIME_ZONE,
});

/** "Jan 4, 2026" — the calendar day in WITA, identical on server and client. */
export function formatArticleDate(
  value: Date | string | number | null | undefined,
): string {
  if (value === null || value === undefined || value === "") return "";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return ARTICLE_DATE.format(date);
}
