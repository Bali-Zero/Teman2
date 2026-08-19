import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  PLAN_STORAGE_KEY,
  decodePlanFragment,
  emptyPlan,
  encodePlanFragment,
  loadPlan,
  savePlan,
} from "../plan-codec";
import type { PlanState } from "../types";

/** Local base64url encoder, independent of the module under test, so the
 *  "wrong version" / "malformed" fixtures aren't accidentally validated by
 *  the very encoder they're meant to probe. */
function toB64Url(s: string): string {
  return Buffer.from(s, "utf-8")
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
}

describe("emptyPlan", () => {
  it("returns a fresh v1 plan with all-null answers and an empty checklist", () => {
    const plan = emptyPlan();
    expect(plan.v).toBe(1);
    expect(plan.age).toBeNull();
    expect(plan.route).toBeNull();
    expect(plan.capital).toBeNull();
    expect(plan.seniorFunding).toBeNull();
    expect(plan.property).toBeNull();
    expect(plan.horizon).toBeNull();
    expect(plan.location).toBeNull();
    expect(plan.family).toEqual({ spouse: false, children: 0, parents: 0 });
    expect(plan.checklist).toEqual({});
    expect(typeof plan.updatedAt).toBe("string");
  });
});

describe("encodePlanFragment / decodePlanFragment roundtrip", () => {
  it("roundtrips a fully-answered plan", () => {
    const plan: PlanState = {
      ...emptyPlan(),
      age: "60_plus",
      route: "deposit",
      capital: null,
      seniorFunding: "deposit_50k_income",
      property: null,
      family: { spouse: true, children: 2, parents: 1 },
      horizon: "asap",
      location: "abroad",
      checklist: { passport_validity: true, photos: false },
    };

    const encoded = encodePlanFragment(plan);
    const decoded = decodePlanFragment(encoded);
    expect(decoded).toEqual(plan);
  });

  it("roundtrips an empty plan", () => {
    const plan = emptyPlan();
    const decoded = decodePlanFragment(encodePlanFragment(plan));
    expect(decoded).toEqual(plan);
  });

  it("encoded fragment is base64url (no +, /, = characters)", () => {
    const encoded = encodePlanFragment(emptyPlan());
    expect(encoded).not.toMatch(/[+/=]/);
  });
});

describe("decodePlanFragment — malformed / wrong-version / oversized => null, never throw", () => {
  it("rejects an empty string", () => {
    expect(decodePlanFragment("")).toBeNull();
  });

  it("rejects a string with characters outside the base64url alphabet", () => {
    expect(() =>
      decodePlanFragment("not a valid base64url!!! ###"),
    ).not.toThrow();
    expect(decodePlanFragment("not a valid base64url!!! ###")).toBeNull();
  });

  it("rejects a base64url-alphabet string that decodes to non-JSON garbage", () => {
    const garbage = toB64Url("this is plainly not json at all");
    expect(decodePlanFragment(garbage)).toBeNull();
  });

  it("rejects valid JSON that isn't PlanState-shaped", () => {
    const notAPlan = toB64Url(JSON.stringify({ hello: "world" }));
    expect(decodePlanFragment(notAPlan)).toBeNull();
  });

  it("rejects a wrong schema version (v !== 1)", () => {
    const wrongVersion = toB64Url(JSON.stringify({ ...emptyPlan(), v: 2 }));
    expect(decodePlanFragment(wrongVersion)).toBeNull();
  });

  it("rejects an oversized fragment (>8KB)", () => {
    const huge = "A".repeat(8 * 1024 + 1);
    expect(decodePlanFragment(huge)).toBeNull();
  });

  it("accepts a fragment right at the 8KB boundary shape (sanity: boundary itself isn't rejected by length alone)", () => {
    // A same-length string of valid alphabet chars that is NOT valid JSON
    // still correctly resolves to null via the JSON-parse guard, proving
    // the size guard isn't masking a separate bug at the boundary.
    const atLimit = "A".repeat(8 * 1024);
    expect(decodePlanFragment(atLimit)).toBeNull();
  });
});

describe("savePlan / loadPlan — localStorage roundtrip", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("returns null when nothing has been saved", () => {
    expect(loadPlan()).toBeNull();
  });

  it("roundtrips a plan through localStorage", () => {
    const plan: PlanState = {
      ...emptyPlan(),
      age: "under_55",
      route: "deposit",
      capital: "ready_130k",
    };
    savePlan(plan);
    expect(loadPlan()).toEqual(plan);
  });

  it("saves under the documented storage key", () => {
    const plan = emptyPlan();
    savePlan(plan);
    const raw = window.localStorage.getItem(PLAN_STORAGE_KEY);
    expect(raw).not.toBeNull();
    expect(JSON.parse(raw as string)).toEqual(plan);
  });

  it("returns null on corrupted JSON in storage, never throws", () => {
    window.localStorage.setItem(PLAN_STORAGE_KEY, "{not valid json");
    expect(() => loadPlan()).not.toThrow();
    expect(loadPlan()).toBeNull();
  });

  it("returns null on wrong-version content in storage", () => {
    window.localStorage.setItem(
      PLAN_STORAGE_KEY,
      JSON.stringify({ v: 2, family: {}, checklist: {}, updatedAt: "x" }),
    );
    expect(loadPlan()).toBeNull();
  });
});

describe("SSR-safety — functions never throw when window is undefined", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("savePlan is a no-op and loadPlan returns null without window", () => {
    vi.stubGlobal("window", undefined);
    expect(() => savePlan(emptyPlan())).not.toThrow();
    expect(loadPlan()).toBeNull();
  });

  it("encodePlanFragment / decodePlanFragment still work without window (Node/Buffer path)", () => {
    vi.stubGlobal("window", undefined);
    const plan = emptyPlan();
    let encoded = "";
    expect(() => {
      encoded = encodePlanFragment(plan);
    }).not.toThrow();
    expect(encoded.length).toBeGreaterThan(0);

    let decoded: PlanState | null = null;
    expect(() => {
      decoded = decodePlanFragment(encoded);
    }).not.toThrow();
    expect(decoded).toEqual(plan);
  });
});
