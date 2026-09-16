import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The cache rule for fonts must match the ENTITY, not a spelling.
 *
 * It used to read `source: "/:path*.woff2"` under a comment that said
 * "Cache public assets (fonts, etc) for 1 year". The two stopped agreeing the
 * day the R19 faces landed: Fraunces and Manrope ship as variable .ttf, so
 * they fell through to the default and production served 525 KB of font with
 * `max-age=0, must-revalidate` on every navigation (measured on
 * balizero.com, 2026-09-16).
 *
 * So this test takes its obligations from the FONT FILES ON DISK, never from
 * the rule — a test that read the rule's own extension list could only ever
 * agree with itself. Drop a new face into public/fonts in any format and this
 * goes red until the rule covers it; narrow the rule and it goes red too.
 *
 * What the rule actually does at runtime was measured separately, on a real
 * `next dev` server rather than a local path-to-regexp (the repo root's copy
 * is a different major version than the one Next bundles, and compiling the
 * source against it fails on a pattern Next accepts):
 *   /fonts/fraunces-variable.ttf -> public, max-age=31536000, immutable
 *   /fonts/fraunces-OFL.txt      -> public, max-age=0        (not over-matched)
 *   /visa/voa                    -> no-cache, must-revalidate (not over-matched)
 */

const FONT_DIR = join(__dirname, "..", "..", "public", "fonts");
const CONFIG = readFileSync(
  join(__dirname, "..", "..", "next.config.ts"),
  "utf-8",
);

/** Extensions of the binaries a browser actually downloads as a typeface. */
const FONT_BINARY_RE = /\.(woff2|woff|ttf|otf|eot)$/i;

function immutableRuleSource(): string {
  // The one rule whose value is the year-long immutable policy.
  const idx = CONFIG.indexOf("max-age=31536000, immutable");
  expect(idx, "a year-long immutable cache rule must exist").toBeGreaterThan(
    -1,
  );
  const before = CONFIG.slice(0, idx);
  const srcIdx = before.lastIndexOf("source:");
  return before.slice(srcIdx, before.indexOf("\n", srcIdx));
}

describe("apps/mouth cache headers — every shipped font is cached as a font", () => {
  const fontFiles = readdirSync(FONT_DIR).filter((f) => FONT_BINARY_RE.test(f));

  it("finds font binaries to reason about (guards against an empty-set pass)", () => {
    expect(fontFiles.length).toBeGreaterThan(0);
  });

  it.each(fontFiles)(
    "%s — its extension is named by the immutable cache rule",
    (file) => {
      const ext = file.match(FONT_BINARY_RE)![1].toLowerCase();
      expect(
        immutableRuleSource(),
        `public/fonts/${file} ships to every visitor; the immutable rule must name .${ext}`,
      ).toContain(ext);
    },
  );

  it("does not hand the immutable policy to the licence files sitting next to them", () => {
    const src = immutableRuleSource();
    for (const ext of ["txt", "md", "json"]) {
      expect(
        src,
        `.${ext} must not inherit a year-long immutable cache`,
      ).not.toContain(`${ext}`);
    }
  });
});
