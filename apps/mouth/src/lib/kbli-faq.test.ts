import { describe, expect, it } from "vitest";
import { buildKbliFaq } from "./kbli-faq";
import { getCode } from "./kbli-data";
import type { KBLICode } from "./kbli-types";

describe("buildKbliFaq", () => {
  it("qualifies the open answer on a Bali-blocked code — never an unqualified yes", () => {
    const blocked = getCode("56101");
    expect(blocked).toBeDefined();
    const base = blocked as KBLICode;
    const synthetic: KBLICode = {
      ...base,
      pma: { ...base.pma, status: "open" },
      baliL4: { ...(base.baliL4 ?? {}), blocked: true, reason: "test reason" },
    } as KBLICode;

    const pmaAnswer = buildKbliFaq(synthetic)[0].answer;
    expect(pmaAnswer).toContain("NOT in Bali");
    expect(pmaAnswer).not.toMatch(/^Yes\./);
  });

  it("handles capSpecial restricted codes without stating a numeric cap as fact", () => {
    const base = getCode("56101") as KBLICode;
    const synthetic: KBLICode = {
      ...base,
      baliL4: undefined,
      pma: {
        ...base.pma,
        status: "restricted",
        capSpecial: true,
        maxForeign: 0,
      },
    } as KBLICode;

    const pmaAnswer = buildKbliFaq(synthetic)[0].answer;
    expect(pmaAnswer).toContain("special distribution conditions");
    expect(pmaAnswer).not.toContain("capped at 0%");
  });

  it("returns 3-4 entries and every answer names the code", () => {
    const code = getCode("56101") as KBLICode;
    const faq = buildKbliFaq(code);
    expect(faq.length).toBeGreaterThanOrEqual(3);
    expect(faq.length).toBeLessThanOrEqual(4);
    for (const entry of faq) {
      expect(entry.answer).toContain(code.code);
    }
  });
});
