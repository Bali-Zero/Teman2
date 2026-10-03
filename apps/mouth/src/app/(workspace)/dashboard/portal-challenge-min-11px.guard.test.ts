import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, it, expect } from "vitest";

/**
 * kita dashboard — the Portal Champion widget has no arbitrary text size
 * below 11px, the floor the kita readability work settled on (PR 7601).
 *
 * WHAT THIS GUARD PROVES. Every `text-[Npx]` class in
 * `PortalChallengeWidget.tsx` is >= 11px, with no exceptions. It reads the
 * source the widget ships, so a new 9px or 10px label fails here.
 *
 * WHAT IT DOES NOT PROVE:
 *   - It only sees arbitrary `text-[Npx]` classes. Named Tailwind sizes
 *     (`text-xs` = 12px) and inline `fontSize` are not read; at the time of
 *     writing the widget has zero inline `fontSize`, and the positive control
 *     below proves the probe does see `text-[Npx]` classes.
 *   - It does not render. Computed size under a parent override is not seen.
 *
 * The RulesDrawer ("Aturan") trigger was the last 10px label; it was held
 * back while PR 7624 changed the same class line, and now reads 11px. The
 * PENDING exception that covered it is gone, so it is checked like the rest.
 */

const FLOOR_PX = 11;

const src = readFileSync(join(__dirname, "PortalChallengeWidget.tsx"), "utf-8");

type Hit = { line: number; px: number; text: string };

function sizes(source: string): Hit[] {
  const hits: Hit[] = [];
  source.split("\n").forEach((text, i) => {
    for (const m of text.matchAll(/(?<![\w-])text-\[(\d+(?:\.\d+)?)px\]/g)) {
      hits.push({ line: i + 1, px: Number(m[1]), text });
    }
  });
  return hits;
}

const all = sizes(src);
const below = all.filter((h) => h.px < FLOOR_PX);

describe("probe positive controls", () => {
  it("reads arbitrary px sizes from the widget", () => {
    // A probe that matched nothing would make every assertion below pass.
    expect(all.length).toBeGreaterThan(20);
    expect(all.some((h) => h.px === 11)).toBe(true);
  });

  it("GUILT: a 10px label is caught by the same probe", () => {
    const planted = sizes('<p className="text-[10px] text-x">a</p>');
    expect(planted.filter((h) => h.px < FLOOR_PX)).toHaveLength(1);
  });

  it("does not mistake a variant or other utility for a size", () => {
    // `max-text-[9px]`-style prefixes are not the text-size utility.
    expect(sizes('<p className="foo-text-[9px]">a</p>')).toHaveLength(0);
  });
});

describe("Portal Champion widget — text floor", () => {
  it(`no text below ${FLOOR_PX}px`, () => {
    expect(
      below.map((h) => `:${h.line} ${h.px}px`),
      "labels below the floor",
    ).toEqual([]);
  });

  it("the Aturan trigger reads the floor size", () => {
    // Named so the old exception cannot quietly come back as a 10px edit.
    const trigger = all.filter((h) =>
      /rounded-full border border-\[var\(--bz-kita-ink-panel-copper\)\].*py-1\.5/.test(
        h.text,
      ),
    );
    expect(trigger.map((h) => h.px)).toEqual([FLOOR_PX]);
  });
});
