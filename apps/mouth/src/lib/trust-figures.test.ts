import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  GOOGLE_MAPS_URL,
  GOOGLE_RATING,
  GOOGLE_REVIEW_COUNT,
  MEASURED_ON,
  ratingBadge,
  ratingWithReviews,
  reviewCount,
  reviewsLabel,
  reviewsShort,
} from "./trust-figures";

/**
 * The Google figures were hand-typed in seven places across five files. The
 * count read 627 while the live listing had reached 693 — not a lie, just a
 * measurement frozen into a constant with no single place for the correction
 * to land. This test exists so the next hand-typed copy fails instead of
 * quietly re-creating that state.
 *
 * Declared limit: this cannot tell whether the figures are CURRENT. Nothing in
 * this repo can — the listing is external and nobody re-reads it on a
 * schedule. What it can do is keep the number in one place and keep the
 * measurement date attached to it, so staleness is visible rather than
 * invisible. Article content under src/content is out of scope: .mdx prose is
 * not code and cannot import a module.
 */

const SRC = join(__dirname, "..");
const SCANNED = ["app", "components", "lib"];
const SELF = "trust-figures";

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) {
      out.push(...walk(full));
    } else if (/\.tsx?$/.test(entry) && !entry.includes(SELF)) {
      out.push(full);
    }
  }
  return out;
}

const FILES = SCANNED.flatMap((d) => walk(join(SRC, d)));

describe("trust-figures is the only source of the Google figures", () => {
  it("scans a plausible number of files", () => {
    // A broken walk would return nothing and let every assertion below pass by
    // having no files to look at.
    expect(FILES.length).toBeGreaterThan(100);
  });

  it("no file hard-codes the review count", () => {
    const offenders = FILES.filter((f) =>
      // Anchored to the claim, not the digits: `#596275` contains "627" and an
      // SVG path contains "6.627". Counting digits measures digits.
      /\b\d{3,4}\s*(Google\s+)?[Rr]eviews?\b/.test(readFileSync(f, "utf8")),
    ).map((f) => f.slice(SRC.length + 1));
    expect(offenders).toEqual([]);
  });

  it("no file hard-codes the star rating next to a star", () => {
    const offenders = FILES.filter((f) =>
      /\b\d\.\d\s*★/.test(readFileSync(f, "utf8")),
    ).map((f) => f.slice(SRC.length + 1));
    expect(offenders).toEqual([]);
  });

  // The two guards above match the PROSE form — a number followed by the word
  // "reviews", or a number followed by a star. Structured data writes the same
  // claim the other way round, as a key: `reviewCount: "700"`. That is why
  // JsonLd.tsx kept a hand-typed 700 (and a ratingValue of 5.0 against the
  // page's 4.9) straight through the PR that added these guards — the guard
  // that let the defect past was part of the defect. These two add the key
  // form; they do not replace the prose form, which still catches the shape
  // a page renders.
  it("no file hard-codes the count as a schema key", () => {
    const offenders = FILES.filter((f) =>
      // Requires a literal number after the colon, so `String(GOOGLE_REVIEW_COUNT)`
      // passes. Two digits minimum, so a `reviewCount: 0` default passes too —
      // the workspace sidebar has a prop of the same name that counts documents,
      // and a homonym is not a claim about Google.
      /(ratingCount|reviewCount)\s*:\s*"?\d{2,5}"?/.test(
        readFileSync(f, "utf8"),
      ),
    ).map((f) => f.slice(SRC.length + 1));
    expect(offenders).toEqual([]);
  });

  it("no file hard-codes the rating as a schema key", () => {
    const offenders = FILES.filter((f) =>
      /ratingValue\s*:\s*"?\d\.\d"?/.test(readFileSync(f, "utf8")),
    ).map((f) => f.slice(SRC.length + 1));
    expect(offenders).toEqual([]);
  });

  it("innocence: the new key-form guards do not fire on the cured shapes", () => {
    // Measured against the exact strings the cure introduces, plus the
    // schema.org scale constants and the workspace homonym. A guard that
    // trips on its own remedy teaches the next person to delete it.
    const key = /(ratingCount|reviewCount)\s*:\s*"?\d{2,5}"?/;
    const star = /ratingValue\s*:\s*"?\d\.\d"?/;
    for (const cured of [
      'import { GOOGLE_RATING, GOOGLE_REVIEW_COUNT } from "@/lib/trust-figures";',
      "      ratingValue: GOOGLE_RATING,",
      "      ratingCount: String(GOOGLE_REVIEW_COUNT),",
      "      reviewCount: String(GOOGLE_REVIEW_COUNT),",
      '      bestRating: "5",',
      '      worstRating: "1",',
      "  reviewCount?: number;",
      "  reviewCount = 0,",
      "  reviewCount={gateStatus?.sections?.documents?.count ?? 0}",
    ]) {
      expect(key.test(cured), `key guard fired on: ${cured}`).toBe(false);
      expect(star.test(cured), `star guard fired on: ${cured}`).toBe(false);
    }
    // guilt: the shapes they must still catch
    expect(key.test('      ratingCount: "700",')).toBe(true);
    expect(key.test('      reviewCount: "700",')).toBe(true);
    expect(star.test('      ratingValue: "5.0",')).toBe(true);
  });

  it("no file re-declares the Maps URL", () => {
    // Declared limit: this bans every maps.app.goo.gl short-link, not just
    // ours. A future page that legitimately links a DIFFERENT Google listing
    // will trip it. That is the right default — the three copies this found
    // were all the same listing, and the contact page's was for directions
    // rather than reviews, which is exactly the kind of second use that reads
    // as unrelated and drifts. Narrow it when a genuinely different listing
    // shows up, not before.
    const offenders = FILES.filter((f) =>
      readFileSync(f, "utf8").includes("maps.app.goo.gl"),
    ).map((f) => f.slice(SRC.length + 1));
    expect(offenders).toEqual([]);
  });

  it("the measurement date is a real ISO date, not a placeholder", () => {
    expect(MEASURED_ON).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(Number.isNaN(Date.parse(MEASURED_ON))).toBe(false);
  });

  it("formats the shapes the surfaces actually use", () => {
    expect(reviewCount()).toBe("693");
    expect(ratingBadge()).toBe("4.9 ★");
    expect(reviewsLabel()).toBe("693 Google reviews");
    expect(reviewsShort()).toBe("693 Reviews");
    expect(ratingWithReviews()).toBe("4.9 ★ · 693 Google reviews");
  });

  it("innocence: the exported values are the ones the formatters use", () => {
    // If someone changes GOOGLE_REVIEW_COUNT and not the formatters (or vice
    // versa), the surfaces and the constant would disagree silently.
    expect(reviewCount()).toBe(GOOGLE_REVIEW_COUNT.toLocaleString("en-US"));
    expect(ratingBadge()).toContain(GOOGLE_RATING);
    expect(GOOGLE_MAPS_URL).toMatch(/^https:\/\/maps\.app\.goo\.gl\//);
  });
});
