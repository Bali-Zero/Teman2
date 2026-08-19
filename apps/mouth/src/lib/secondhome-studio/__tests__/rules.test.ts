import { describe, expect, it } from "vitest";

import { getCopy } from "../copy";
import { HUMAN_REVIEW_KEYS, REASON_KEYS, evaluatePlan } from "../rules";
import type {
  AgeBand,
  PlanState,
  PropertyStatus,
  SeniorFunding,
} from "../types";

function basePlan(overrides: Partial<PlanState> = {}): PlanState {
  return {
    v: 1,
    age: null,
    route: null,
    capital: null,
    seniorFunding: null,
    property: null,
    family: { spouse: false, children: 0, parents: 0 },
    horizon: null,
    location: null,
    checklist: {},
    updatedAt: "2026-08-19T00:00:00.000Z",
    ...overrides,
  };
}

const ALL_AGES: AgeBand[] = ["under_55", "55_59", "60_plus"];
const ALL_PROPERTY_STATUSES: PropertyStatus[] = [
  "owns_qualifying_strata",
  "buying_completed_strata",
  "villa_land_leasehold",
  "none",
];
const ALL_SENIOR_FUNDING: SeniorFunding[] = [
  "deposit_50k_income",
  "income_only_3k",
  "neither",
  "not_applicable",
];

describe("REASON_KEYS / HUMAN_REVIEW_KEYS stay in sync with copy.ts", () => {
  it("every reason key resolves to a real copy string, never falls back to the key itself", () => {
    for (const key of Object.values(REASON_KEYS)) {
      expect(getCopy(key)).not.toBe(key);
    }
  });

  it("every human-review key resolves to a real copy string", () => {
    for (const key of Object.values(HUMAN_REVIEW_KEYS)) {
      expect(getCopy(key)).not.toBe(key);
    }
  });
});

describe("row 7 — globally required answers null => edge_case incomplete", () => {
  it("age missing", () => {
    const v = evaluatePlan(
      basePlan({ age: null, route: "deposit", capital: "ready_130k" }),
    );
    expect(v.band).toBe("edge_case");
    expect(v.product).toBeNull();
    expect(v.reasons).toEqual([REASON_KEYS.incompleteAnswers]);
  });

  it("route missing", () => {
    const v = evaluatePlan(basePlan({ age: "under_55", route: null }));
    expect(v.band).toBe("edge_case");
    expect(v.reasons).toEqual([REASON_KEYS.incompleteAnswers]);
  });
});

describe("row 1 — property route: ALWAYS edge_case, NEVER strong/likely fit", () => {
  it("owns_qualifying_strata: pending-standard only, no does-not-qualify reason", () => {
    const v = evaluatePlan(
      basePlan({
        age: "under_55",
        route: "property",
        property: "owns_qualifying_strata",
      }),
    );
    expect(v.band).toBe("edge_case");
    expect(v.product).toBeNull();
    expect(v.reasons).toEqual([REASON_KEYS.propertyPendingStandard]);
  });

  it("buying_completed_strata: pending-standard only, no does-not-qualify reason", () => {
    const v = evaluatePlan(
      basePlan({
        age: "under_55",
        route: "property",
        property: "buying_completed_strata",
      }),
    );
    expect(v.band).toBe("edge_case");
    expect(v.reasons).toEqual([REASON_KEYS.propertyPendingStandard]);
  });

  it("villa_land_leasehold: pending-standard PLUS does-not-qualify", () => {
    const v = evaluatePlan(
      basePlan({
        age: "under_55",
        route: "property",
        property: "villa_land_leasehold",
      }),
    );
    expect(v.band).toBe("edge_case");
    expect(v.reasons).toEqual([
      REASON_KEYS.propertyPendingStandard,
      REASON_KEYS.propertyDoesNotQualify,
    ]);
  });

  it("none: pending-standard PLUS does-not-qualify", () => {
    const v = evaluatePlan(
      basePlan({ age: "under_55", route: "property", property: "none" }),
    );
    expect(v.band).toBe("edge_case");
    expect(v.reasons).toEqual([
      REASON_KEYS.propertyPendingStandard,
      REASON_KEYS.propertyDoesNotQualify,
    ]);
  });

  it("property status missing => incomplete, not silently qualified", () => {
    const v = evaluatePlan(
      basePlan({ age: "under_55", route: "property", property: null }),
    );
    expect(v.band).toBe("edge_case");
    expect(v.reasons).toEqual([REASON_KEYS.incompleteAnswers]);
  });

  it("across every age x every property status, the band is never strong_fit or likely_fit", () => {
    for (const age of ALL_AGES) {
      for (const property of ALL_PROPERTY_STATUSES) {
        const v = evaluatePlan(basePlan({ age, route: "property", property }));
        expect(v.band).not.toBe("strong_fit");
        expect(v.band).not.toBe("likely_fit");
      }
    }
  });
});

describe("rows 2-4 — under_55 + deposit route, driven by capital", () => {
  it("row 2: ready_130k => strong_fit E33", () => {
    const v = evaluatePlan(
      basePlan({ age: "under_55", route: "deposit", capital: "ready_130k" }),
    );
    expect(v.band).toBe("strong_fit");
    expect(v.product).toBe("E33");
    expect(v.reasons).toEqual([REASON_KEYS.depositReadyStrong]);
    expect(v.humanReviewNote).toBeNull();
  });

  it("innocence: close_100k_130k must NOT be strong_fit", () => {
    const v = evaluatePlan(
      basePlan({
        age: "under_55",
        route: "deposit",
        capital: "close_100k_130k",
      }),
    );
    expect(v.band).not.toBe("strong_fit");
  });

  it("row 3: close_100k_130k => likely_fit E33", () => {
    const v = evaluatePlan(
      basePlan({
        age: "under_55",
        route: "deposit",
        capital: "close_100k_130k",
      }),
    );
    expect(v.band).toBe("likely_fit");
    expect(v.product).toBe("E33");
    expect(v.reasons).toEqual([REASON_KEYS.capitalCloseVerify]);
  });

  it("innocence: ready_130k must NOT be likely_fit", () => {
    const v = evaluatePlan(
      basePlan({ age: "under_55", route: "deposit", capital: "ready_130k" }),
    );
    expect(v.band).not.toBe("likely_fit");
  });

  it("row 4: below_100k => not_eligible, product null, honest why + senior-routes-exist note", () => {
    const v = evaluatePlan(
      basePlan({ age: "under_55", route: "deposit", capital: "below_100k" }),
    );
    expect(v.band).toBe("not_eligible");
    expect(v.product).toBeNull();
    expect(v.reasons).toEqual([
      REASON_KEYS.capitalBelowThreshold,
      REASON_KEYS.seniorRoutesExistNote,
    ]);
  });

  it("innocence: ready_130k must NOT be not_eligible", () => {
    const v = evaluatePlan(
      basePlan({ age: "under_55", route: "deposit", capital: "ready_130k" }),
    );
    expect(v.band).not.toBe("not_eligible");
  });

  it("capital missing => incomplete", () => {
    const v = evaluatePlan(
      basePlan({ age: "under_55", route: "deposit", capital: null }),
    );
    expect(v.band).toBe("edge_case");
    expect(v.reasons).toEqual([REASON_KEYS.incompleteAnswers]);
  });
});

describe("row 5 — age 55-59: ALWAYS edge_case (bersyarat), whatever the funding", () => {
  it.each(ALL_SENIOR_FUNDING)(
    "seniorFunding=%s stays edge_case",
    (seniorFunding) => {
      const v = evaluatePlan(
        basePlan({ age: "55_59", route: "deposit", seniorFunding }),
      );
      expect(v.band).toBe("edge_case");
      expect(v.humanReviewNote).toBe(HUMAN_REVIEW_KEYS.age5559Disclosure);
    },
  );

  it("deposit_50k_income => product E33E", () => {
    const v = evaluatePlan(
      basePlan({
        age: "55_59",
        route: "deposit",
        seniorFunding: "deposit_50k_income",
      }),
    );
    expect(v.product).toBe("E33E");
    expect(v.reasons).toEqual([REASON_KEYS.seniorBersyarat]);
  });

  it("income_only_3k => product E33F", () => {
    const v = evaluatePlan(
      basePlan({
        age: "55_59",
        route: "deposit",
        seniorFunding: "income_only_3k",
      }),
    );
    expect(v.product).toBe("E33F");
    expect(v.reasons).toEqual([REASON_KEYS.seniorBersyarat]);
  });

  it("neither => product null, with unclear-funding reason", () => {
    const v = evaluatePlan(
      basePlan({ age: "55_59", route: "deposit", seniorFunding: "neither" }),
    );
    expect(v.product).toBeNull();
    expect(v.reasons).toEqual([
      REASON_KEYS.seniorBersyarat,
      REASON_KEYS.seniorFundingUnclear,
    ]);
  });

  it("not_applicable => product null, with unclear-funding reason (same as neither)", () => {
    const v = evaluatePlan(
      basePlan({
        age: "55_59",
        route: "deposit",
        seniorFunding: "not_applicable",
      }),
    );
    expect(v.product).toBeNull();
    expect(v.reasons).toEqual([
      REASON_KEYS.seniorBersyarat,
      REASON_KEYS.seniorFundingUnclear,
    ]);
  });

  it("seniorFunding missing => incomplete, never silently strong/likely", () => {
    const v = evaluatePlan(
      basePlan({ age: "55_59", route: "deposit", seniorFunding: null }),
    );
    expect(v.band).toBe("edge_case");
    expect(v.reasons).toEqual([REASON_KEYS.incompleteAnswers]);
  });
});

describe("row 6 — age 60_plus", () => {
  it("deposit_50k_income => strong_fit E33E", () => {
    const v = evaluatePlan(
      basePlan({
        age: "60_plus",
        route: "deposit",
        seniorFunding: "deposit_50k_income",
      }),
    );
    expect(v.band).toBe("strong_fit");
    expect(v.product).toBe("E33E");
    expect(v.reasons).toEqual([REASON_KEYS.seniorDepositStrong]);
    expect(v.humanReviewNote).toBeNull();
  });

  it("income_only_3k => strong_fit E33F", () => {
    const v = evaluatePlan(
      basePlan({
        age: "60_plus",
        route: "deposit",
        seniorFunding: "income_only_3k",
      }),
    );
    expect(v.band).toBe("strong_fit");
    expect(v.product).toBe("E33F");
    expect(v.reasons).toEqual([REASON_KEYS.seniorIncomeOnlyStrong]);
  });

  describe("neither/not_applicable falls through to the base E33 deposit rows", () => {
    it("neither + ready_130k => strong_fit E33", () => {
      const v = evaluatePlan(
        basePlan({
          age: "60_plus",
          route: "deposit",
          seniorFunding: "neither",
          capital: "ready_130k",
        }),
      );
      expect(v.band).toBe("strong_fit");
      expect(v.product).toBe("E33");
      expect(v.reasons).toEqual([REASON_KEYS.depositReadyStrong]);
    });

    it("neither + close_100k_130k => likely_fit E33", () => {
      const v = evaluatePlan(
        basePlan({
          age: "60_plus",
          route: "deposit",
          seniorFunding: "neither",
          capital: "close_100k_130k",
        }),
      );
      expect(v.band).toBe("likely_fit");
      expect(v.product).toBe("E33");
    });

    it("neither + below_100k => not_eligible", () => {
      const v = evaluatePlan(
        basePlan({
          age: "60_plus",
          route: "deposit",
          seniorFunding: "neither",
          capital: "below_100k",
        }),
      );
      expect(v.band).toBe("not_eligible");
      expect(v.product).toBeNull();
    });

    it("neither + capital null => edge_case incomplete (capital unknown is NOT allowed to pass through)", () => {
      const v = evaluatePlan(
        basePlan({
          age: "60_plus",
          route: "deposit",
          seniorFunding: "neither",
          capital: null,
        }),
      );
      expect(v.band).toBe("edge_case");
      expect(v.reasons).toEqual([REASON_KEYS.incompleteAnswers]);
    });

    it("not_applicable + ready_130k => strong_fit E33 (same fallthrough as neither)", () => {
      const v = evaluatePlan(
        basePlan({
          age: "60_plus",
          route: "deposit",
          seniorFunding: "not_applicable",
          capital: "ready_130k",
        }),
      );
      expect(v.band).toBe("strong_fit");
      expect(v.product).toBe("E33");
    });
  });

  it("seniorFunding missing => incomplete", () => {
    const v = evaluatePlan(
      basePlan({ age: "60_plus", route: "deposit", seniorFunding: null }),
    );
    expect(v.band).toBe("edge_case");
    expect(v.reasons).toEqual([REASON_KEYS.incompleteAnswers]);
  });
});

describe("row 8 — route=unsure evaluated as deposit, with an added reason", () => {
  it("under_55 + unsure + ready_130k => strong_fit E33, unsure reason first", () => {
    const v = evaluatePlan(
      basePlan({ age: "under_55", route: "unsure", capital: "ready_130k" }),
    );
    expect(v.band).toBe("strong_fit");
    expect(v.product).toBe("E33");
    expect(v.reasons).toEqual([
      REASON_KEYS.unsureRoute,
      REASON_KEYS.depositReadyStrong,
    ]);
  });

  it("55_59 + unsure + deposit_50k_income => edge_case E33E, unsure reason first", () => {
    const v = evaluatePlan(
      basePlan({
        age: "55_59",
        route: "unsure",
        seniorFunding: "deposit_50k_income",
      }),
    );
    expect(v.band).toBe("edge_case");
    expect(v.product).toBe("E33E");
    expect(v.reasons).toEqual([
      REASON_KEYS.unsureRoute,
      REASON_KEYS.seniorBersyarat,
    ]);
  });

  it("60_plus + unsure + income_only_3k => strong_fit E33F, unsure reason first", () => {
    const v = evaluatePlan(
      basePlan({
        age: "60_plus",
        route: "unsure",
        seniorFunding: "income_only_3k",
      }),
    );
    expect(v.band).toBe("strong_fit");
    expect(v.product).toBe("E33F");
    expect(v.reasons).toEqual([
      REASON_KEYS.unsureRoute,
      REASON_KEYS.seniorIncomeOnlyStrong,
    ]);
  });

  it("unsure route never triggers the property row (property is only literal route='property')", () => {
    const v = evaluatePlan(
      basePlan({ age: "under_55", route: "unsure", capital: "ready_130k" }),
    );
    expect(v.reasons).not.toContain(REASON_KEYS.propertyPendingStandard);
  });
});

describe("evaluatePlan is deterministic and pure", () => {
  it("calling it twice on the same input yields the same output", () => {
    const plan = basePlan({
      age: "under_55",
      route: "deposit",
      capital: "ready_130k",
    });
    const v1 = evaluatePlan(plan);
    const v2 = evaluatePlan(plan);
    expect(v1).toEqual(v2);
  });

  it("does not mutate the input plan", () => {
    const plan = basePlan({
      age: "under_55",
      route: "deposit",
      capital: "ready_130k",
    });
    const snapshot = JSON.parse(JSON.stringify(plan));
    evaluatePlan(plan);
    expect(plan).toEqual(snapshot);
  });
});
