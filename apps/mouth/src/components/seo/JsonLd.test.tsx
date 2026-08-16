import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { GOOGLE_RATING, GOOGLE_REVIEW_COUNT } from "@/lib/trust-figures";
import { AggregateRatingJsonLd } from "./JsonLd";

/**
 * AggregateRatingJsonLd is rendered from the ROOT layout
 * (apps/mouth/src/app/layout.tsx:254), so this block ships on every page —
 * including pages that show no review figure at all.
 *
 * It used to carry its own hand-typed rating and count. Measured live on
 * 2026-08-14 at age:0 / x-vercel-cache: MISS, https://balizero.com/ served —
 * in ONE response — a trust bar rendered from trust-figures.ts beside a
 * JSON-LD block claiming a higher rating from a larger count. Same page, two
 * different claims, and the schema one is the claim Google reads.
 *
 * These tests assert against the imported constants, never against the
 * figures written out. A test that re-types the number is another copy of
 * the defect wearing a green tick — and the guards in
 * src/lib/trust-figures.test.ts enforce that on this file too: an earlier
 * draft of this very comment quoted the figures and was correctly rejected.
 *
 * Declared limit: this proves the schema and the module agree. It cannot
 * prove either is CURRENT — the Google listing is external and nothing in
 * this repo re-reads it. MEASURED_ON in trust-figures.ts is what makes that
 * staleness visible.
 */

/** Extract the JSON-LD payload the component embeds in its <script> tag.
 *
 * String ops, not a regex on HTML: CodeQL's js/bad-tag-filter flags a
 * hand-rolled `<script>...</script>` regex as unsound. Same approach as
 * apps/mouth/src/components/kbli/KBLIStructuredData.test.tsx.
 */
function aggregateRatingSchema(): Record<string, unknown> {
  const html = renderToStaticMarkup(<AggregateRatingJsonLd />);
  const openTag = html.indexOf("<script");
  const start = html.indexOf(">", openTag) + 1;
  const end = html.lastIndexOf("</script>");
  expect(openTag).toBeGreaterThanOrEqual(0);
  expect(start).toBeGreaterThan(0);
  expect(end).toBeGreaterThanOrEqual(0);
  return JSON.parse(html.slice(start, end));
}

function ratingBlock(): Record<string, unknown> {
  const rating = aggregateRatingSchema().aggregateRating;
  // Guard the premise: if the shape moved, every assertion below would pass
  // vacuously against `undefined`.
  expect(rating, "schema has no aggregateRating block").toBeTypeOf("object");
  return rating as Record<string, unknown>;
}

describe("AggregateRatingJsonLd reads its figures from trust-figures", () => {
  it("guilt: ratingValue is the module's rating, not a second copy", () => {
    expect(ratingBlock().ratingValue).toBe(GOOGLE_RATING);
  });

  it("guilt: ratingCount and reviewCount are the module's count", () => {
    const rating = ratingBlock();
    expect(rating.ratingCount).toBe(String(GOOGLE_REVIEW_COUNT));
    expect(rating.reviewCount).toBe(String(GOOGLE_REVIEW_COUNT));
  });

  it("guilt: schema.org wants strings, so the count is converted, not coerced", () => {
    const rating = ratingBlock();
    expect(typeof rating.ratingCount).toBe("string");
    expect(typeof rating.reviewCount).toBe("string");
    expect(typeof rating.ratingValue).toBe("string");
  });

  it("innocence: the scale constants are untouched", () => {
    // bestRating/worstRating describe schema.org's 1-5 scale. They are not
    // measurements and must NOT follow the Google figures.
    const rating = ratingBlock();
    expect(rating.bestRating).toBe("5");
    expect(rating.worstRating).toBe("1");
    expect(rating["@type"]).toBe("AggregateRating");
  });

  it("innocence: the surrounding schema is unchanged", () => {
    const schema = aggregateRatingSchema();
    expect(schema["@context"]).toBe("https://schema.org");
    expect(schema["@type"]).toBe("ProfessionalService");
    expect(schema.name).toBe("Bali Zero");
    expect(schema.priceRange).toBe("$$");
    expect(schema.address).toEqual({
      "@type": "PostalAddress",
      addressLocality: "Bali",
      addressCountry: "ID",
    });
    expect(typeof schema.url).toBe("string");
    expect(typeof schema["@id"]).toBe("string");
  });
});
