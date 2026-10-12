import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The client portal home (/portal) rendered its eyebrow labels (EYEBROW,
 * 3 uses), its status pills (StatePill, 3 uses) and the timeline item's date
 * and reply link at 10px. Measured at b8cf9e56: 4 class strings, all 10px.
 * They now sit at 11px, the floor /kbli-explorer and the portal company page
 * hold.
 *
 * Declared limits: reads the two files as text and checks un-prefixed
 * arbitrary `text-[9px]` / `text-[10px]` only. It does not render, and does
 * not cover shared portal components (StatusBadge, CountdownChip,
 * PracticeRecapCard, PortalNotifications) or other portal routes.
 */
const FILES = ["page.tsx", join("_components", "TimelineItem.tsx")].map(
  (f) => ({ f, src: readFileSync(join(__dirname, f), "utf8") }),
);
const BELOW_FLOOR = /(?<![\w:-])text-\[(?:9|10)px\]/g;

describe("portal home holds the 11px floor", () => {
  it("positive control: both files are read and carry arbitrary px text sizes", () => {
    for (const { f, src } of FILES) {
      expect(src.match(/text-\[\d+px\]/g)?.length ?? 0, f).toBeGreaterThan(0);
    }
    expect(FILES[0].src).toContain("const EYEBROW");
    expect(FILES[0].src).toContain("function StatePill");
  });

  it("no 9px or 10px text", () => {
    const hits = FILES.flatMap(({ f, src }) =>
      [...src.matchAll(BELOW_FLOOR)].map((m) => `${f}: ${m[0]}`),
    );
    expect(hits).toEqual([]);
  });

  it("the probe fires on the sizes it forbids", () => {
    const probe = 'className="text-[9px] md:text-[10px] text-[10px]"';
    expect([...probe.matchAll(BELOW_FLOOR)].map((m) => m[0])).toEqual([
      "text-[9px]",
      "text-[10px]",
    ]);
  });
});
