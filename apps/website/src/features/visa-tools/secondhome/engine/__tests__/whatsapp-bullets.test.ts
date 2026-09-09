import { describe, expect, it } from "vitest";

import {
  MAX_BULLET_ROWS,
  MAX_LABEL_LENGTH,
  MAX_VALUE_LENGTH,
  buildWhatsAppBullets,
} from "../whatsapp-bullets";
import { emptyPlan } from "../plan-codec";
import { evaluatePlan } from "../rules";
import type { PlanState } from "../types";

/**
 * P0-C3 + P0-C4 CONTRACT TEST: the built bullet list must satisfy
 * `apps/backend-rag/backend/app/routers/lead_capture.py:38-47` exactly —
 * <=6 rows, label <=64 chars, value <=160 chars, every row non-empty.
 * Constants (MAX_BULLET_ROWS/MAX_LABEL_LENGTH/MAX_VALUE_LENGTH) mirror
 * that file's `ContextLine` / `whatsapp_context` field constraints.
 */

function basePlan(overrides: Partial<PlanState> = {}): PlanState {
  return { ...emptyPlan(), ...overrides };
}

function assertContract(bullets: ReturnType<typeof buildWhatsAppBullets>) {
  expect(bullets.length).toBeLessThanOrEqual(MAX_BULLET_ROWS);
  for (const bullet of bullets) {
    expect(bullet.label.length).toBeGreaterThan(0);
    expect(bullet.label.length).toBeLessThanOrEqual(MAX_LABEL_LENGTH);
    expect(bullet.value.length).toBeGreaterThan(0);
    expect(bullet.value.length).toBeLessThanOrEqual(MAX_VALUE_LENGTH);
  }
}

describe("buildWhatsAppBullets — backend contract (P0-C3/C4)", () => {
  it("deposit fixture: <=6 rows, every label/value within contract bounds", () => {
    const plan = basePlan({
      age: "under_55",
      route: "deposit",
      capital: "ready_130k",
      family: { spouse: true, children: 2, parents: 0 },
      horizon: "asap",
      location: "in_indonesia",
    });
    const bullets = buildWhatsAppBullets(plan, evaluatePlan(plan));
    assertContract(bullets);
  });

  it("senior (55-59) fixture: <=6 rows, every label/value within contract bounds", () => {
    const plan = basePlan({
      age: "55_59",
      route: "deposit",
      seniorFunding: "deposit_50k_income",
      family: { spouse: false, children: 0, parents: 1 },
      horizon: "this_quarter",
      location: "abroad",
    });
    const bullets = buildWhatsAppBullets(plan, evaluatePlan(plan));
    assertContract(bullets);
  });

  it("property fixture: <=6 rows, every label/value within contract bounds", () => {
    const plan = basePlan({
      age: "under_55",
      route: "property",
      property: "villa_land_leasehold",
      family: { spouse: false, children: 0, parents: 0 },
      horizon: "exploring",
      location: "in_indonesia",
    });
    const bullets = buildWhatsAppBullets(plan, evaluatePlan(plan));
    assertContract(bullets);
  });

  it("60_plus income-only fixture: <=6 rows, every label/value within contract bounds", () => {
    const plan = basePlan({
      age: "60_plus",
      route: "deposit",
      seniorFunding: "income_only_3k",
      family: { spouse: true, children: 0, parents: 0 },
      horizon: "asap",
      location: "in_indonesia",
    });
    const bullets = buildWhatsAppBullets(plan, evaluatePlan(plan));
    assertContract(bullets);
  });

  it("never emits a Saved-plan/plan-link row or a Readiness row (P0-C3(b))", () => {
    const plan = basePlan({
      age: "under_55",
      route: "deposit",
      capital: "ready_130k",
    });
    const bullets = buildWhatsAppBullets(plan, evaluatePlan(plan));
    const labels = bullets.map((b) => b.label.toLowerCase());
    expect(labels).not.toContain("saved plan");
    expect(labels).not.toContain("readiness");
    for (const bullet of bullets) {
      expect(bullet.value).not.toMatch(/^https?:\/\//);
      expect(bullet.value).not.toContain("#p=");
    }
  });

  describe("P1-C8 — the funding line is branch-aware, never a blind seniorFunding read", () => {
    it("under_55 deposit: funding line reads the capital label, not '—'", () => {
      const plan = basePlan({
        age: "under_55",
        route: "deposit",
        capital: "ready_130k",
      });
      const bullets = buildWhatsAppBullets(plan, evaluatePlan(plan));
      const funding = bullets.find((b) => b.label === "Funding position");
      expect(funding).toBeDefined();
      expect(funding?.value).toBe("USD 130,000 is ready");
    });

    it("55-59 senior: funding line reads the seniorFunding label", () => {
      const plan = basePlan({
        age: "55_59",
        route: "deposit",
        seniorFunding: "income_only_3k",
      });
      const bullets = buildWhatsAppBullets(plan, evaluatePlan(plan));
      const funding = bullets.find((b) => b.label === "Funding position");
      expect(funding?.value).toBe("USD 3,000 monthly income only");
    });

    it("property route: funding line reads the property status label", () => {
      const plan = basePlan({
        age: "under_55",
        route: "property",
        property: "owns_qualifying_strata",
      });
      const bullets = buildWhatsAppBullets(plan, evaluatePlan(plan));
      const funding = bullets.find((b) => b.label === "Funding position");
      expect(funding?.value).toBe(
        "I own qualifying completed strata-title property",
      );
    });

    it("60_plus fallthrough (seniorFunding=neither): funding line reads capital", () => {
      const plan = basePlan({
        age: "60_plus",
        route: "deposit",
        seniorFunding: "neither",
        capital: "close_100k_130k",
      });
      const bullets = buildWhatsAppBullets(plan, evaluatePlan(plan));
      const funding = bullets.find((b) => b.label === "Funding position");
      expect(funding?.value).toBe("USD 100,000 to under USD 130,000");
    });
  });

  it("P2-6: a stale capital answer left over after switching to property never leaks into the funding line", () => {
    const plan = basePlan({
      age: "under_55",
      route: "property",
      property: "none",
      capital: "ready_130k", // abandoned-branch leftover
    });
    const bullets = buildWhatsAppBullets(plan, evaluatePlan(plan));
    const funding = bullets.find((b) => b.label === "Funding position");
    expect(funding?.value).not.toContain("130,000");
  });
});
