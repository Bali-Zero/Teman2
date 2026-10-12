import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Nine /kbli-explorer labels were written `text-[11px] md:text-[10px]`:
 * 11px on phones, shrunk to 10px from the `md` breakpoint up, so desktop
 * visitors got the smaller text. A tenth line carried a redundant
 * `text-[10px] md:text-[10px]`. Measured at 279d063447.
 *
 * Declared limits: reads page.tsx and ./components/*.tsx as text and looks
 * for breakpoint-prefixed arbitrary sizes below 11px. It does not render and
 * does not judge unprefixed sizes (other guards and later PRs cover those).
 */
const DIR = __dirname;
const FILES = [
  join(DIR, "page.tsx"),
  ...readdirSync(join(DIR, "components"))
    .filter((f) => f.endsWith(".tsx"))
    .map((f) => join(DIR, "components", f)),
];
const SOURCES = FILES.map((f) => ({ f, src: readFileSync(f, "utf8") }));
const RESPONSIVE = /(?<![\w-])(?:sm|md|lg|xl|2xl):text-\[(\d+(?:\.\d+)?)px\]/g;

describe("/kbli-explorer never shrinks text below 11px at a breakpoint", () => {
  it("positive control: the scan reads page.tsx and KBLIInspector.tsx", () => {
    const names = SOURCES.map((s) => s.f.split("/").pop());
    expect(names).toContain("page.tsx");
    expect(names).toContain("KBLIInspector.tsx");
    const elevens = SOURCES.reduce(
      (n, s) => n + (s.src.match(/text-\[11px\]/g)?.length ?? 0),
      0,
    );
    expect(elevens).toBeGreaterThanOrEqual(9);
  });

  it("no breakpoint-prefixed text size below 11px", () => {
    const hits = SOURCES.flatMap((s) =>
      [...s.src.matchAll(RESPONSIVE)]
        .filter((m) => Number(m[1]) < 11)
        .map((m) => `${s.f.split("/").pop()}: ${m[0]}`),
    );
    expect(hits).toEqual([]);
  });
});
