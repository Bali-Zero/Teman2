/**
 * Single source for the Google Business Profile figures we publish.
 *
 * These are external numbers that move on their own. Before this module they
 * were typed by hand in seven places across five files, which meant they were
 * true on the day someone typed them and drifted every day after, with nothing
 * to re-measure them: the count sat at 627 while the live listing had reached
 * 693. Nobody was wrong — there was simply no place for the correction to land
 * once, so it never landed at all.
 *
 * A single source does not stop the drift. It makes the next correction one
 * edit instead of seven, and it puts the measurement date next to the number so
 * a reader can see how old it is.
 *
 * HOW TO UPDATE: open the Google Business Profile listing, read the rating and
 * the review count, change the three fields below together, and move
 * MEASURED_ON to the day you read them. Do not update one without the others —
 * a fresh count beside a stale date is worse than an honestly old number.
 *
 * NOT covered here: the "5,000+ clients since 2019" claim that appears on other
 * surfaces. It has no verifiable source in any system we run — the CRM only
 * goes back to 2025-12-22 and holds 1,886 live records — so it is deliberately
 * left where it is rather than given a false home in a module named "source".
 */

/**
 * Our Google Business Profile. The figures below are read off it, and the
 * contact page links to it for directions — one listing, two uses, so it lives
 * here rather than being typed once per purpose.
 */
export const GOOGLE_MAPS_URL = "https://maps.app.goo.gl/whiMUTNchcDR5naz8";

/** Star rating shown on the Google listing. */
export const GOOGLE_RATING = "4.9";

/** Review count shown on the Google listing. */
export const GOOGLE_REVIEW_COUNT = 693;

/**
 * The day the two values above were last read off the live listing.
 * ISO date, and it is a claim like any other: only change it when you looked.
 */
export const MEASURED_ON = "2026-08-14";

/** "693" — grouped for locales that need it once the count passes a thousand. */
export const reviewCount = (): string =>
  GOOGLE_REVIEW_COUNT.toLocaleString("en-US");

/** "4.9 ★ · 693 Google reviews" */
export const ratingWithReviews = (): string =>
  `${GOOGLE_RATING} ★ · ${reviewCount()} Google reviews`;

/** "693 Google reviews" */
export const reviewsLabel = (): string => `${reviewCount()} Google reviews`;

/** "693 Reviews" — the shorter form the trust bar uses. */
export const reviewsShort = (): string => `${reviewCount()} Reviews`;

/** "4.9 ★" */
export const ratingBadge = (): string => `${GOOGLE_RATING} ★`;
