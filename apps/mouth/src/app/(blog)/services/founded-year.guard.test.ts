import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const read = (rel: string) =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), "utf8");

const SURFACES = {
  "services/page.tsx": read("./page.tsx"),
  "v2/FunnelFeature.tsx": read("../../v2/_components/FunnelFeature.tsx"),
  "v2/HeroCarousel.tsx": read("../../v2/_components/HeroCarousel.tsx"),
};

describe("public founded year is 2020 on /services and /v2", () => {
  for (const [name, src] of Object.entries(SURFACES)) {
    it(`${name} never states a founding year of 2006 or 2019`, () => {
      expect(src).not.toMatch(/since\s+(2006|2019)/i);
    });

    it(`${name} states since 2020 (positive control)`, () => {
      expect(src).toMatch(/since\s+2020/i);
    });
  }

  it("the /services trust strip shows 2020 as Year founded", () => {
    const src = SURFACES["services/page.tsx"];
    expect(src).toMatch(/value:\s*"2020",\s*label:\s*"Year founded"/);
    expect(src).not.toMatch(/value:\s*"20(06|19)",\s*label:\s*"Year founded"/);
  });
});
