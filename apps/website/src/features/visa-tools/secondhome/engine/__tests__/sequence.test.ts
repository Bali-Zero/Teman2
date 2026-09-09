import { describe, expect, it } from "vitest";

import {
  decodePlanFragment,
  emptyPlan,
  encodePlanFragment,
} from "../plan-codec";
import { computeSequence, relevantPlan } from "../sequence";
import type { PlanState } from "../types";

function basePlan(overrides: Partial<PlanState> = {}): PlanState {
  return { ...emptyPlan(), ...overrides };
}

describe("computeSequence — unchanged behavior (P2-6 hoist, no behavior change)", () => {
  it("under_55 route: age, route, capital, family, horizon, location", () => {
    const seq = computeSequence(
      basePlan({ age: "under_55", route: "deposit" }),
    );
    expect(seq).toEqual([
      "age",
      "route",
      "capital",
      "family",
      "horizon",
      "location",
    ]);
  });

  it("property route: age, route, property, family, horizon, location", () => {
    const seq = computeSequence(basePlan({ route: "property" }));
    expect(seq).toEqual([
      "age",
      "route",
      "property",
      "family",
      "horizon",
      "location",
    ]);
  });

  it("55-59: age, route, seniorFunding, family, horizon, location (never capital)", () => {
    const seq = computeSequence(basePlan({ age: "55_59", route: "deposit" }));
    expect(seq).toEqual([
      "age",
      "route",
      "seniorFunding",
      "family",
      "horizon",
      "location",
    ]);
  });

  it("60_plus + seniorFunding unresolved: includes both seniorFunding and capital", () => {
    const seq = computeSequence(basePlan({ age: "60_plus", route: "deposit" }));
    expect(seq).toContain("seniorFunding");
    expect(seq).toContain("capital");
  });

  it("60_plus + seniorFunding matched to a senior product: capital is skipped", () => {
    const seq = computeSequence(
      basePlan({
        age: "60_plus",
        route: "deposit",
        seniorFunding: "deposit_50k_income",
      }),
    );
    expect(seq).toContain("seniorFunding");
    expect(seq).not.toContain("capital");
  });
});

describe("relevantPlan — nulls branch-only answers not reachable in the current sequence (P2-6)", () => {
  it("nulls capital after switching from deposit to property", () => {
    const p = basePlan({
      age: "under_55",
      route: "property",
      capital: "ready_130k",
      property: "none",
    });
    const sanitized = relevantPlan(p);
    expect(sanitized.capital).toBeNull();
    expect(sanitized.property).toBe("none");
  });

  it("nulls property after switching from property to deposit", () => {
    const p = basePlan({
      age: "under_55",
      route: "deposit",
      capital: "ready_130k",
      property: "villa_land_leasehold",
    });
    const sanitized = relevantPlan(p);
    expect(sanitized.property).toBeNull();
    expect(sanitized.capital).toBe("ready_130k");
  });

  it("nulls seniorFunding for under_55 (never reachable at that age)", () => {
    const p = basePlan({
      age: "under_55",
      route: "deposit",
      capital: "ready_130k",
      seniorFunding: "deposit_50k_income",
    });
    expect(relevantPlan(p).seniorFunding).toBeNull();
  });

  it("nulls capital for 55-59 (seniorFunding-only age band)", () => {
    const p = basePlan({
      age: "55_59",
      route: "deposit",
      capital: "ready_130k",
      seniorFunding: "income_only_3k",
    });
    expect(relevantPlan(p).capital).toBeNull();
    expect(relevantPlan(p).seniorFunding).toBe("income_only_3k");
  });

  it("keeps capital for 60_plus once seniorFunding resolves to neither (fallthrough still reachable)", () => {
    const p = basePlan({
      age: "60_plus",
      route: "deposit",
      capital: "close_100k_130k",
      seniorFunding: "neither",
    });
    expect(relevantPlan(p).capital).toBe("close_100k_130k");
  });

  it("nulls capital for 60_plus once seniorFunding matches a senior product", () => {
    const p = basePlan({
      age: "60_plus",
      route: "deposit",
      capital: "ready_130k",
      seniorFunding: "income_only_3k",
    });
    expect(relevantPlan(p).capital).toBeNull();
  });

  it("leaves age/route/family/horizon/location untouched", () => {
    const p = basePlan({
      age: "under_55",
      route: "deposit",
      capital: "ready_130k",
      family: { spouse: true, children: 1, parents: 0 },
      horizon: "asap",
      location: "abroad",
    });
    const sanitized = relevantPlan(p);
    expect(sanitized.age).toBe("under_55");
    expect(sanitized.route).toBe("deposit");
    expect(sanitized.family).toEqual({ spouse: true, children: 1, parents: 0 });
    expect(sanitized.horizon).toBe("asap");
    expect(sanitized.location).toBe("abroad");
  });

  it("innocence: a fully-relevant deposit plan is untouched by relevantPlan", () => {
    const p = basePlan({
      age: "under_55",
      route: "deposit",
      capital: "ready_130k",
    });
    expect(relevantPlan(p)).toEqual(p);
  });
});

describe("encodePlanFragment(relevantPlan(p)) — the shared-link surface never leaks a stale answer (P2-6)", () => {
  it("dropping the stale capital answer after switching to property round-trips as null", () => {
    const p = basePlan({
      age: "under_55",
      route: "property",
      capital: "ready_130k",
      property: "none",
    });
    const encoded = encodePlanFragment(relevantPlan(p));
    const decoded = decodePlanFragment(encoded);
    expect(decoded).not.toBeNull();
    expect(decoded?.capital).toBeNull();
    expect(decoded?.property).toBe("none");
  });
});
