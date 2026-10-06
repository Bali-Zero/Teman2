import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The /kbli-explorer left panel (desktop: always visible) rendered its
 * labels at 9px ("Business Code Guide") and 10px (both section headings,
 * the "Ask about your codes" sentence, the assistant footer). Measured at
 * 279d063447. Floor here is 11px, the same floor kita uses for labels.
 *
 * Declared limits: reads page.tsx only, by regex over arbitrary
 * `text-[Npx]` classes inside the first <aside>…</aside> block. It does not
 * render, does not cover ./components, and does not check contrast.
 */
const PAGE = readFileSync(join(__dirname, "page.tsx"), "utf8");
const start = PAGE.indexOf("<aside");
const end = PAGE.indexOf("</aside>", start);
const PANEL = start >= 0 && end > start ? PAGE.slice(start, end) : "";
const SIZES = [...PANEL.matchAll(/(?<![\w-])text-\[(\d+(?:\.\d+)?)px\]/g)].map(
  (m) => Number(m[1]),
);

describe("/kbli-explorer left panel has no text below 11px", () => {
  it("positive control: the scan reaches the left panel and its size classes", () => {
    expect(PANEL).toContain("Official Sources");
    expect(PANEL).toContain("Business Code Guide");
    expect(SIZES.length).toBeGreaterThanOrEqual(6);
  });

  it("no arbitrary text size below 11px in the left panel", () => {
    expect(SIZES.filter((s) => s < 11)).toEqual([]);
  });

  it("the 'Business Code Guide' tagline reads the floor size", () => {
    const tagline = PANEL.match(
      /className="([^"]*)"\s*>\s*Business Code Guide/,
    );
    expect(tagline?.[1]).toContain("text-[11px]");
  });
});
