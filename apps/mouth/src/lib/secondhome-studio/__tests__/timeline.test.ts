import { describe, expect, it } from "vitest";

import { getCopy } from "../copy";
import { buildTimeline } from "../timeline";
import type { Location, TimelineHorizon } from "../types";

const ALL_HORIZONS: TimelineHorizon[] = ["asap", "this_quarter", "exploring"];
const ALL_LOCATIONS: Location[] = ["in_indonesia", "abroad"];

describe("buildTimeline — 7 public steps, always", () => {
  it("returns exactly 7 steps for every horizon x location combination", () => {
    for (const horizon of ALL_HORIZONS) {
      for (const location of ALL_LOCATIONS) {
        expect(buildTimeline(horizon, location)).toHaveLength(7);
      }
    }
  });

  it("returns the 7 steps in the spec's fixed order", () => {
    const steps = buildTimeline("this_quarter", "in_indonesia");
    expect(steps.map((s) => s.id)).toEqual([
      "documents",
      "bank_deposit",
      "filing",
      "imigrasi_processing",
      "entry_activation",
      "first_90_days",
      "annual_life",
    ]);
  });
});

describe("owner tags — You / Bali Zero / Imigrasi", () => {
  it("assigns exactly one of the three owner keys to every step", () => {
    const steps = buildTimeline("asap", "in_indonesia");
    for (const step of steps) {
      expect(["you", "balizero", "imigrasi"]).toContain(step.ownerKey);
    }
  });

  it("Imigrasi processing is owned by imigrasi, filing and the 90-day duty by bali zero", () => {
    const steps = buildTimeline("asap", "in_indonesia");
    const byId = Object.fromEntries(steps.map((s) => [s.id, s]));
    expect(byId.imigrasi_processing.ownerKey).toBe("imigrasi");
    expect(byId.filing.ownerKey).toBe("balizero");
    expect(byId.first_90_days.ownerKey).toBe("balizero");
    expect(byId.documents.ownerKey).toBe("you");
    expect(byId.bank_deposit.ownerKey).toBe("you");
    expect(byId.entry_activation.ownerKey).toBe("you");
    expect(byId.annual_life.ownerKey).toBe("you");
  });

  it("every ownerKey has a resolvable label in copy.ts", () => {
    const steps = buildTimeline("asap", "in_indonesia");
    for (const step of steps) {
      const key = `timeline.ownerLabels.${step.ownerKey}`;
      expect(getCopy(key)).not.toBe(key);
    }
  });
});

describe("every titleKey and rangeKey resolves to real copy (no drift)", () => {
  it("resolves for every horizon x location combination", () => {
    for (const horizon of ALL_HORIZONS) {
      for (const location of ALL_LOCATIONS) {
        for (const step of buildTimeline(horizon, location)) {
          expect(getCopy(step.titleKey)).not.toBe(step.titleKey);
          expect(getCopy(step.rangeKey)).not.toBe(step.rangeKey);
          if (step.paceNoteKey) {
            expect(getCopy(step.paceNoteKey)).not.toBe(step.paceNoteKey);
          }
        }
      }
    }
  });
});

describe("location variant — documents step range differs abroad vs in_indonesia", () => {
  it("produces a different rangeKey for the documents step", () => {
    const local = buildTimeline("asap", "in_indonesia").find(
      (s) => s.id === "documents",
    )!;
    const abroad = buildTimeline("asap", "abroad").find(
      (s) => s.id === "documents",
    )!;
    expect(local.rangeKey).not.toBe(abroad.rangeKey);
    expect(getCopy(local.rangeKey)).not.toBe(getCopy(abroad.rangeKey));
  });

  it("does not change the range for steps unrelated to document logistics", () => {
    const local = buildTimeline("asap", "in_indonesia").find(
      (s) => s.id === "filing",
    )!;
    const abroad = buildTimeline("asap", "abroad").find(
      (s) => s.id === "filing",
    )!;
    expect(local.rangeKey).toBe(abroad.rangeKey);
  });
});

describe("horizon variant — documents step pace note differs by horizon", () => {
  it("produces three distinct paceNoteKey values across asap/this_quarter/exploring", () => {
    const keys = ALL_HORIZONS.map(
      (h) =>
        buildTimeline(h, "in_indonesia").find((s) => s.id === "documents")!
          .paceNoteKey,
    );
    expect(new Set(keys).size).toBe(3);
  });

  it("only the documents step carries a paceNoteKey", () => {
    const steps = buildTimeline("asap", "in_indonesia");
    const withPace = steps.filter((s) => s.paceNoteKey !== undefined);
    expect(withPace.map((s) => s.id)).toEqual(["documents"]);
  });
});

describe("P1-C9 — the second step is route/product-aware (never a blind bank-deposit instruction)", () => {
  it("default call (no route/product args) still returns bank_deposit — unchanged for every existing caller", () => {
    const steps = buildTimeline("asap", "in_indonesia");
    expect(steps[1].id).toBe("bank_deposit");
  });

  it("route=property replaces the second step with property_evidence, never bank_deposit", () => {
    const steps = buildTimeline("asap", "in_indonesia", "property", null);
    expect(steps).toHaveLength(7);
    expect(steps[1].id).toBe("property_evidence");
    expect(steps.map((s) => s.id)).not.toContain("bank_deposit");
    expect(getCopy(steps[1].titleKey)).not.toBe(steps[1].titleKey);
    expect(getCopy(steps[1].rangeKey)).not.toBe(steps[1].rangeKey);
  });

  it("product=E33F (income-only) replaces the second step with income_evidence, never bank_deposit", () => {
    const steps = buildTimeline("asap", "in_indonesia", "deposit", "E33F");
    expect(steps[1].id).toBe("income_evidence");
    expect(steps.map((s) => s.id)).not.toContain("bank_deposit");
    expect(getCopy(steps[1].titleKey)).not.toBe(steps[1].titleKey);
    expect(getCopy(steps[1].rangeKey)).not.toBe(steps[1].rangeKey);
  });

  it("innocence: product=E33E (deposit-holding senior route) keeps bank_deposit", () => {
    const steps = buildTimeline("asap", "in_indonesia", "deposit", "E33E");
    expect(steps[1].id).toBe("bank_deposit");
  });

  it("innocence: route=deposit + product=E33 (base strong_fit) keeps bank_deposit", () => {
    const steps = buildTimeline("asap", "in_indonesia", "deposit", "E33");
    expect(steps[1].id).toBe("bank_deposit");
  });

  it("innocence: route=unsure keeps bank_deposit (evaluated as deposit per rules.ts row 8)", () => {
    const steps = buildTimeline("asap", "in_indonesia", "unsure", "E33");
    expect(steps[1].id).toBe("bank_deposit");
  });

  it("property route wins over product even if product happens to be non-null", () => {
    const steps = buildTimeline("asap", "in_indonesia", "property", null);
    expect(steps[1].id).toBe("property_evidence");
  });

  it("owner/step count/order are unchanged regardless of route/product", () => {
    const steps = buildTimeline("asap", "in_indonesia", "property", null);
    expect(steps.map((s) => s.ownerKey)).toEqual([
      "you",
      "you",
      "balizero",
      "imigrasi",
      "you",
      "balizero",
      "you",
    ]);
  });
});

describe("every range label reads as typical, not a promise", () => {
  it("every step's range copy hedges with 'typical'/'varies' and never promises or guarantees", () => {
    const steps = buildTimeline("asap", "in_indonesia");
    for (const step of steps) {
      const range = getCopy(step.rangeKey).toLowerCase();
      expect(range).toMatch(/typical|varies|several weeks/);
      expect(range).not.toMatch(/guarantee[ds]?/);
    }
  });
});
