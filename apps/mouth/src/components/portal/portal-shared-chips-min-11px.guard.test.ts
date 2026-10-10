import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Four shared client-portal components rendered text at 10px: StatusBadge
 * (status pill), CountdownChip (both variants), PracticeRecapCard (eyebrow)
 * and the timestamp line in PortalNotifications. Measured at 8c7ba3bb. They
 * now sit at 11px, the floor already held by /kbli-explorer, the portal home
 * and the portal company page.
 *
 * Declared exception: the unread-count bubble in PortalNotifications
 * (an 18px circle, `min-w-[18px] h-[18px]`) stays at 10px — a numeric badge
 * inside a fixed circle, not running text. The guard allows 10px only on a
 * line that carries `h-[18px]`.
 *
 * Declared limits: reads the four files as text and checks un-prefixed
 * arbitrary `text-[9px]` / `text-[10px]` only. It does not render, and does
 * not cover PortalBottomNav or other portal routes.
 */
const FILES = [
  "StatusBadge.tsx",
  "CountdownChip.tsx",
  "PracticeRecapCard.tsx",
  "PortalNotifications.tsx",
].map((f) => ({ f, src: readFileSync(join(__dirname, f), "utf8") }));
const BELOW_FLOOR = /(?<![\w:-])text-\[(?:9|10)px\]/;

describe("shared portal chips hold the 11px floor", () => {
  it("positive control: all four files are read and carry arbitrary px text sizes", () => {
    for (const { f, src } of FILES) {
      expect(src.match(/text-\[\d+px\]/g)?.length ?? 0, f).toBeGreaterThan(0);
    }
  });

  it("no 9px or 10px text outside the declared unread bubble", () => {
    const hits = FILES.flatMap(({ f, src }) =>
      src
        .split("\n")
        .map((line, i) => ({ line, n: i + 1 }))
        .filter(({ line }) => BELOW_FLOOR.test(line))
        .filter(({ line }) => !line.includes("h-[18px]"))
        .map(({ n }) => `${f}:${n}`),
    );
    expect(hits).toEqual([]);
  });

  it("the declared exception is still exactly one line", () => {
    const bubble = FILES.flatMap(({ src }) =>
      src
        .split("\n")
        .filter((l) => BELOW_FLOOR.test(l) && l.includes("h-[18px]")),
    );
    expect(bubble).toHaveLength(1);
  });

  it("the probe fires on the sizes it forbids", () => {
    expect(BELOW_FLOOR.test('className="text-[10px] mt-1"')).toBe(true);
    expect(BELOW_FLOOR.test('className="md:text-[10px]"')).toBe(false);
    expect(BELOW_FLOOR.test('className="text-[11px]"')).toBe(false);
  });
});
