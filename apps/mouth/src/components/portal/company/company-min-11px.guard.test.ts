import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * The client portal company page (/portal/company/[id]) rendered 15 labels
 * below the 11px floor: 6 at 9px (divider labels, identity row labels,
 * Shares/Role labels, legal timeline type labels) and 9 at 10px (fact box
 * captions, hero eyebrow, status and KBLI chips, key-number labels).
 * Measured at b8cf9e56. They now sit at 11px, the floor /kbli-explorer
 * already holds.
 *
 * Declared limits: reads the component files in this folder as text and
 * checks un-prefixed arbitrary `text-[9px]` / `text-[10px]` only. It does not
 * render, and does not cover the route file
 * app/portal/(authenticated)/company/[id]/page.tsx (0 such classes there at
 * b8cf9e56) or the rest of the portal.
 */
const FILES = readdirSync(__dirname)
  .filter((f) => f.endsWith(".tsx") && !f.includes(".test."))
  .map((f) => ({ f, src: readFileSync(join(__dirname, f), "utf8") }));
const BELOW_FLOOR = /(?<![\w:-])text-\[(?:9|10)px\]/g;

describe("portal company components hold the 11px floor", () => {
  it("positive control: the folder is read and carries arbitrary px text sizes", () => {
    const names = FILES.map(({ f }) => f);
    for (const f of [
      "DividerLabel.tsx",
      "IdentityRow.tsx",
      "PeopleColumn.tsx",
      "LegalTimeline.tsx",
      "FactBoxes.tsx",
    ]) {
      expect(names).toContain(f);
    }
    const sized = FILES.flatMap(({ src }) =>
      [...src.matchAll(/text-\[\d+px\]/g)].map((m) => m[0]),
    );
    expect(sized.length).toBeGreaterThan(0);
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
