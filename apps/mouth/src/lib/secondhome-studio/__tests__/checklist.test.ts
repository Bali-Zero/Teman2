import { describe, expect, it } from "vitest";

import { CHECKLIST_ITEMS, readiness } from "../checklist";
import { getCopy } from "../copy";
import { emptyPlan } from "../plan-codec";

/**
 * Not one of the spec's 4 named test files (rules/plan-codec/timeline/
 * forbidden-claims) — added as a value-add since checklist.ts carries real
 * logic (`readiness`). Flagged in the delivery report as an addition
 * beyond the frozen spec's minimum, not a scope change.
 */

describe("CHECKLIST_ITEMS", () => {
  it("has exactly 10 items per spec §5", () => {
    expect(CHECKLIST_ITEMS).toHaveLength(10);
  });

  it("every item has a unique id", () => {
    const ids = CHECKLIST_ITEMS.map((i) => i.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("every item's titleKey and whyKey resolve to real copy", () => {
    for (const item of CHECKLIST_ITEMS) {
      expect(getCopy(item.titleKey)).not.toBe(item.titleKey);
      expect(getCopy(item.whyKey)).not.toBe(item.whyKey);
    }
  });
});

describe("readiness", () => {
  it("reports 0 of 10 for a fresh plan", () => {
    expect(readiness(emptyPlan())).toEqual({ done: 0, total: 10 });
  });

  it("counts only items marked true", () => {
    const plan = {
      ...emptyPlan(),
      checklist: {
        passport_validity: true,
        passport_scan: true,
        photos: false,
        unknown_id_not_in_the_list: true,
      },
    };
    expect(readiness(plan)).toEqual({ done: 2, total: 10 });
  });

  it("reports 10 of 10 when every item is checked", () => {
    const checklist = Object.fromEntries(
      CHECKLIST_ITEMS.map((i) => [i.id, true]),
    );
    const plan = { ...emptyPlan(), checklist };
    expect(readiness(plan)).toEqual({ done: 10, total: 10 });
  });
});
