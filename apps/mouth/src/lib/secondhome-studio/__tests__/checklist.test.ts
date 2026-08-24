import { describe, expect, it } from "vitest";

import {
  CHECKLIST_ITEMS,
  classifyChecklistItem,
  readiness,
  type ChecklistApplicability,
} from "../checklist";
import { getCopy } from "../copy";
import { emptyPlan } from "../plan-codec";
import { evaluatePlan } from "../rules";
import type { PlanState, Verdict } from "../types";

/**
 * Not one of the spec's 4 named test files (rules/plan-codec/timeline/
 * forbidden-claims) — added as a value-add since checklist.ts carries real
 * logic (`readiness`, `classifyChecklistItem`). Flagged in the delivery
 * report as an addition beyond the frozen spec's minimum, not a scope
 * change.
 *
 * Pins the defect measured across three production walks: every route
 * rendered the byte-identical 10-item union with an identical "0 of 10"
 * meter, so a bank-deposit applicant was told to prepare property documents
 * and a senior income applicant was told to prepare deposit evidence.
 * `classifyChecklistItem`/`readiness` split the union into
 * "applies"/"may_apply" without deleting anything — see checklist.ts's
 * module doc for the fail-safe precedence.
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

function plan(overrides: Partial<PlanState>): PlanState {
  return { ...emptyPlan(), ...overrides };
}

/** Asserts classifyChecklistItem for every item against `overrides`; any
 *  item NOT named defaults to "applies" — the safety rule itself ("default
 *  to APPLICABLE, only 'may_apply' when definitively inapplicable") made
 *  literal as the test helper's own default. This also covers the six
 *  route-independent items (always "applies") without a separate test. */
function expectClassification(
  testPlan: PlanState,
  verdict: Verdict,
  overrides: Partial<Record<string, ChecklistApplicability>>,
) {
  for (const item of CHECKLIST_ITEMS) {
    expect(classifyChecklistItem(item.id, testPlan, verdict)).toBe(
      overrides[item.id] ?? "applies",
    );
  }
}

// Representative plans, grounded in the same four the conductor walked live.
const depositRoutePlan = plan({
  age: "under_55",
  route: "deposit",
  capital: "ready_130k",
});
const propertyRoutePlan = plan({
  age: "under_55",
  route: "property",
  property: "buying_completed_strata",
});
const seniorDepositPlan = plan({
  age: "60_plus",
  route: "deposit",
  seniorFunding: "deposit_50k_income",
});
const seniorIncomePlan = plan({
  age: "60_plus",
  route: "deposit",
  seniorFunding: "income_only_3k",
});
const notSureYetPlan = plan({
  age: "under_55",
  route: "unsure",
  capital: "ready_130k",
  // family_records is governed by its OWN rule (a member present or not —
  // see the dedicated test below), not the route fail-safe. Populated here
  // so "all ten applicable" holds for its own correct reason too.
  family: { spouse: true, children: 0, parents: 0 },
});

describe("classifyChecklistItem — route-aware mapping", () => {
  it("deposit-route plan: bank deposit applies, property + income may also apply", () => {
    const verdict = evaluatePlan(depositRoutePlan);
    expect(verdict.product).toBe("E33"); // sanity: the strong-fit deposit case
    expectClassification(depositRoutePlan, verdict, {
      passive_income_evidence: "may_apply",
      property_documents: "may_apply",
      family_records: "may_apply", // no family on this plan
    });
  });

  it("property-route plan is the mirror image of the deposit-route plan", () => {
    const verdict = evaluatePlan(propertyRoutePlan);
    expect(verdict.band).toBe("edge_case"); // property is always edge_case (pending validation standard)
    expectClassification(propertyRoutePlan, verdict, {
      bank_deposit_evidence: "may_apply",
      passive_income_evidence: "may_apply",
      family_records: "may_apply",
    });
  });

  it("senior E33E plan (60+, deposit funding): deposit + income apply, property does not", () => {
    const verdict = evaluatePlan(seniorDepositPlan);
    expect(verdict.product).toBe("E33E");
    expectClassification(seniorDepositPlan, verdict, {
      property_documents: "may_apply",
      family_records: "may_apply",
    });
  });

  it("senior E33F plan (60+, income-only funding): income applies, deposit + property do not", () => {
    const verdict = evaluatePlan(seniorIncomePlan);
    expect(verdict.product).toBe("E33F");
    expectClassification(seniorIncomePlan, verdict, {
      bank_deposit_evidence: "may_apply",
      property_documents: "may_apply",
      family_records: "may_apply",
    });
  });

  it("FAIL-SAFE: a 'not sure yet' route plan classifies all ten items as applicable", () => {
    const verdict = evaluatePlan(notSureYetPlan);
    // Sanity: this really does score as a clean deposit match under the hood
    // (evaluatePlan treats "unsure" as deposit for verdict/price purposes) —
    // the fail-safe must hold even though the verdict alone looks resolved.
    expect(verdict.product).toBe("E33");
    expectClassification(notSureYetPlan, verdict, {});
  });

  it("55-59 (BERSYARAT) classifies all ten items as applicable regardless of seniorFunding", () => {
    const bersyaratPlan = plan({
      age: "55_59",
      route: "deposit",
      seniorFunding: "deposit_50k_income",
      family: { spouse: true, children: 0, parents: 0 },
    });
    const verdict = evaluatePlan(bersyaratPlan);
    expect(verdict.band).toBe("edge_case");
    expectClassification(bersyaratPlan, verdict, {});
  });

  it("incomplete plan (no age/route yet): route items are applicable, family_records is not (no family answered)", () => {
    const incomplete = emptyPlan();
    const verdict = evaluatePlan(incomplete);
    expect(verdict.band).toBe("edge_case");
    // The two fail-safes compose independently: route/age unresolved ->
    // applicable, but a default member-less family is its OWN definitive
    // "not applicable" answer, not a missing one.
    expectClassification(incomplete, verdict, { family_records: "may_apply" });
  });

  it("family_records applies only when the plan includes a family member", () => {
    const noFamily = {
      ...depositRoutePlan,
      family: { spouse: false, children: 0, parents: 0 },
    };
    const withFamily = {
      ...depositRoutePlan,
      family: { spouse: true, children: 0, parents: 0 },
    };
    expect(
      classifyChecklistItem("family_records", noFamily, evaluatePlan(noFamily)),
    ).toBe("may_apply");
    expect(
      classifyChecklistItem(
        "family_records",
        withFamily,
        evaluatePlan(withFamily),
      ),
    ).toBe("applies");
  });
});

describe("readiness", () => {
  it("reports 0 of 9 for a fresh (incomplete) plan — everything applicable except family (no members yet)", () => {
    const fresh = emptyPlan();
    expect(readiness(fresh, evaluatePlan(fresh))).toEqual({
      done: 0,
      total: 9,
    });
  });

  it("counts only applicable items marked true, against an applicable-only total", () => {
    const withChecks: PlanState = {
      ...depositRoutePlan,
      checklist: {
        passport_validity: true, // applicable, ticked
        bank_deposit_evidence: true, // applicable, ticked
        property_documents: true, // NOT applicable for this plan — must not count
        unknown_id_not_in_the_list: true,
      },
    };
    // 7 of 10 items apply to a deposit-route, no-family plan (income,
    // property and family_records are "may_apply").
    expect(readiness(withChecks, evaluatePlan(withChecks))).toEqual({
      done: 2,
      total: 7,
    });
  });

  it("reports total=10 for the 'not sure yet' fail-safe plan even though it scores a clean match", () => {
    expect(readiness(notSureYetPlan, evaluatePlan(notSureYetPlan))).toEqual({
      done: 0,
      total: 10,
    });
  });

  it("done never exceeds total: ticking every item still only counts the 7 applicable ones", () => {
    const checklist = Object.fromEntries(
      CHECKLIST_ITEMS.map((i) => [i.id, true]), // tick all ten, including the 3 may_apply ones
    );
    const fullyTicked: PlanState = { ...depositRoutePlan, checklist };
    expect(readiness(fullyTicked, evaluatePlan(fullyTicked))).toEqual({
      done: 7,
      total: 7,
    });
  });

  it("ticking a 'may_apply' item and then switching route never yields done > total", () => {
    // property_documents is may_apply on the deposit route — still tickable
    // (both groups stay tickable) but must not count toward the meter.
    const ticked: PlanState = {
      ...depositRoutePlan,
      checklist: { property_documents: true },
    };
    expect(readiness(ticked, evaluatePlan(ticked)).done).toBe(0);

    // Switching to the property route makes it applicable — the previously
    // ticked value carries over (localStorage semantics) and now counts.
    const switched: PlanState = {
      ...propertyRoutePlan,
      checklist: { property_documents: true },
    };
    const after = readiness(switched, evaluatePlan(switched));
    expect(after.done).toBe(1);
    expect(after.done).toBeLessThanOrEqual(after.total);
  });
});
