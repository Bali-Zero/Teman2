import { describe, it, expect } from "vitest";
import { readdirSync, statSync } from "node:fs";
import { join, sep } from "node:path";

/**
 * THE CLASS-CLOSER for the two excluded portraits (D6, 2026-09-15).
 *
 * `scripts/assert-roster-not-in-public-chunks.mjs`'s ACCEPTED_PUBLIC_FILES list
 * (pinned empty by `client-roster-boundary.test.ts`) judges an exact, known
 * path. That is an entry-closer, not a class-closer: it says nothing about
 * `faisha_card.jpg`, `team/Sahira.JPG` or `static/news/faysha-portrait.webp` —
 * paths nobody has written yet, which a per-entry list cannot see coming.
 *
 * This test judges the REPO instead of a list: no path anywhere under
 * `public/` may match an excluded person's name, in any casing, any
 * extension, any directory. Read-only, no chunk build required — it runs
 * against source-tree files, not build output.
 */

const PUBLIC_DIR = join(__dirname, "..", "..", "public");
const FORBIDDEN = /faisha|faysha|sahira/i;

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) walk(full, out);
    else out.push(full);
  }
  return out;
}

function relPublicPaths(): string[] {
  return walk(PUBLIC_DIR).map((f) =>
    f
      .slice(PUBLIC_DIR.length + 1)
      .split(sep)
      .join("/"),
  );
}

describe("no public/ file is named after an excluded person, of any shape", () => {
  it("finds files to scan — refuses to pass on an empty walk", () => {
    // The same rule the guard script already applies to an empty chunk scan: a
    // walk that silently finds nothing is a check that did not run.
    expect(relPublicPaths().length).toBeGreaterThan(0);
  });

  it("the detector catches shapes nobody has written yet (guilt control)", () => {
    expect(FORBIDDEN.test("faisha_card.jpg")).toBe(true);
    expect(FORBIDDEN.test("team/Sahira.JPG")).toBe(true);
    expect(FORBIDDEN.test("static/news/faysha-portrait.webp")).toBe(true);
  });

  it("the detector does not flag an unrelated real public file (innocence control)", () => {
    const files = relPublicPaths();
    const control = files.find((f) => f.toLowerCase().includes("adit"));
    expect(
      control,
      "static/team/adit.jpg not found under public/ — innocence-control fixture assumption broken",
    ).toBeTruthy();
    expect(FORBIDDEN.test(control!)).toBe(false);
  });

  it("no path under public/ matches an excluded person's name, in any shape", () => {
    const offenders = relPublicPaths().filter((f) => FORBIDDEN.test(f));
    expect(offenders).toEqual([]);
  });
});
