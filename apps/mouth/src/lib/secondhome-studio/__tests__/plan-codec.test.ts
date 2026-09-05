import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  PLAN_STORAGE_KEY,
  clearPlan,
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

/** A fully-valid, fully-populated plan — shared by the clearPlan URL-strip
 *  test (P2-C11) and the P0-C1/P2-1 shape-validation table below. */
function fullPlanFixture(): PlanState {
  return {
    v: 1,
    age: "under_55",
    route: "deposit",
    capital: "ready_130k",
    seniorFunding: null,
    property: null,
    family: { spouse: false, children: 0, parents: 0 },
    horizon: "asap",
    location: "in_indonesia",
    checklist: { x: true },
    updatedAt: "2026-08-19T00:00:00.000Z",
  };
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
    expect(savePlan(plan)).toBe(true);
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

  it.each(["SecurityError", "QuotaExceededError"])(
    "returns false when storage rejects the write with %s",
    (name) => {
      const setItem = vi
        .spyOn(window.localStorage, "setItem")
        .mockImplementation(() => {
          throw new DOMException("Cannot store plan", name);
        });
      try {
        expect(savePlan(emptyPlan())).toBe(false);
        expect(loadPlan()).toBeNull();
      } finally {
        setItem.mockRestore();
      }
    },
  );
});

describe("clearPlan — SavePlanBar 'Clear saved plan' action", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.location.hash = "";
  });

  afterEach(() => {
    window.location.hash = "";
  });

  it("removes a previously saved plan so loadPlan returns null", () => {
    savePlan({ ...emptyPlan(), age: "under_55" });
    expect(loadPlan()).not.toBeNull();

    clearPlan();
    expect(loadPlan()).toBeNull();
    expect(window.localStorage.getItem(PLAN_STORAGE_KEY)).toBeNull();
  });

  it("is a safe no-op when nothing was ever saved", () => {
    expect(() => clearPlan()).not.toThrow();
    expect(loadPlan()).toBeNull();
  });

  it("P2-C11: also strips a #p= plan fragment from the URL, so a 'cleared' plan cannot reappear on reload", () => {
    savePlan({ ...emptyPlan(), age: "under_55" });
    window.location.hash = `#p=${encodePlanFragment(fullPlanFixture())}`;
    expect(window.location.hash).not.toBe("");

    clearPlan();

    expect(window.location.hash).toBe("");
  });

  it("P2-C11: stripping the fragment is a safe no-op when there was no fragment to begin with", () => {
    window.location.hash = "";
    expect(() => clearPlan()).not.toThrow();
    expect(window.location.hash).toBe("");
  });
});

describe("P0-C1 / P2-1 — isValidPlanShape validates PRESENCE + whitelist for EVERY PlanState key", () => {
  it("accepts a fully-valid, fully-populated plan", () => {
    const encoded = toB64Url(JSON.stringify(fullPlanFixture()));
    expect(decodePlanFragment(encoded)).toEqual(fullPlanFixture());
  });

  it("rejects the crafted ABSENT-field fragment that used to manufacture a strong_fit verdict (P0-C1, Codex-verified)", () => {
    // age/route are ABSENT (not null) — the old validator only checked
    // v/family/checklist/updatedAt, so this shape decoded successfully and
    // evaluatePlan's `=== null` guards let the missing fields slip through
    // as "under_55 + deposit + ready_130k" => strong_fit E33.
    const crafted = toB64Url(
      JSON.stringify({
        v: 1,
        family: {},
        checklist: {},
        updatedAt: "x",
        capital: "ready_130k",
      }),
    );
    expect(decodePlanFragment(crafted)).toBeNull();
  });

  const REQUIRED_KEYS: (keyof PlanState)[] = [
    "age",
    "route",
    "capital",
    "seniorFunding",
    "property",
    "family",
    "horizon",
    "location",
    "checklist",
    "updatedAt",
  ];

  it.each(REQUIRED_KEYS)(
    "rejects the fragment when '%s' is absent (per-field absence table test)",
    (key) => {
      const obj: Record<string, unknown> = { ...fullPlanFixture() };
      delete obj[key];
      const encoded = toB64Url(JSON.stringify(obj));
      expect(decodePlanFragment(encoded)).toBeNull();
    },
  );

  it("rejects an out-of-whitelist enum value (age: 123, not a real AgeBand)", () => {
    const obj = { ...fullPlanFixture(), age: 123 };
    expect(decodePlanFragment(toB64Url(JSON.stringify(obj)))).toBeNull();
  });

  it("rejects an out-of-whitelist enum value (horizon: 'next_year')", () => {
    const obj = { ...fullPlanFixture(), horizon: "next_year" };
    expect(decodePlanFragment(toB64Url(JSON.stringify(obj)))).toBeNull();
  });

  it("rejects the exact crafted-link fragment from the refuter report (strong_fit + raw dot-paths)", () => {
    const obj = {
      ...fullPlanFixture(),
      age: "under_55",
      route: "deposit",
      capital: 123,
      horizon: "next_year",
    };
    expect(decodePlanFragment(toB64Url(JSON.stringify(obj)))).toBeNull();
  });

  it("rejects a family with a non-boolean spouse", () => {
    const obj = {
      ...fullPlanFixture(),
      family: { spouse: "yes", children: 0, parents: 0 },
    };
    expect(decodePlanFragment(toB64Url(JSON.stringify(obj)))).toBeNull();
  });

  it("rejects a family with a negative children count", () => {
    const obj = {
      ...fullPlanFixture(),
      family: { spouse: false, children: -1, parents: 0 },
    };
    expect(decodePlanFragment(toB64Url(JSON.stringify(obj)))).toBeNull();
  });

  it("rejects a checklist with a non-boolean value", () => {
    const obj = { ...fullPlanFixture(), checklist: { x: "yes" } };
    expect(decodePlanFragment(toB64Url(JSON.stringify(obj)))).toBeNull();
  });

  it("innocence: an empty checklist ({}) is still valid", () => {
    const obj = { ...fullPlanFixture(), checklist: {} };
    expect(decodePlanFragment(toB64Url(JSON.stringify(obj)))).not.toBeNull();
  });
});

describe("P2-C12 — a throwing localStorage GETTER never crashes the codec", () => {
  let originalDescriptor: PropertyDescriptor | undefined;

  beforeEach(() => {
    originalDescriptor = Object.getOwnPropertyDescriptor(
      window,
      "localStorage",
    );
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      get() {
        throw new DOMException("The operation is insecure.", "SecurityError");
      },
    });
  });

  afterEach(() => {
    if (originalDescriptor) {
      Object.defineProperty(window, "localStorage", originalDescriptor);
    }
  });

  it("loadPlan returns null and never throws", () => {
    expect(() => loadPlan()).not.toThrow();
    expect(loadPlan()).toBeNull();
  });

  it("savePlan is a safe no-op and never throws", () => {
    expect(() => savePlan(emptyPlan())).not.toThrow();
    expect(savePlan(emptyPlan())).toBe(false);
  });

  it("clearPlan is a safe no-op and never throws", () => {
    expect(() => clearPlan()).not.toThrow();
  });
});

describe("SSR-safety — functions never throw when window is undefined", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("savePlan is a no-op and loadPlan returns null without window", () => {
    vi.stubGlobal("window", undefined);
    expect(() => savePlan(emptyPlan())).not.toThrow();
    expect(savePlan(emptyPlan())).toBe(false);
    expect(loadPlan()).toBeNull();
  });

  it("clearPlan is a no-op without window", () => {
    vi.stubGlobal("window", undefined);
    expect(() => clearPlan()).not.toThrow();
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
