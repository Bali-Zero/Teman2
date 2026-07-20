import { describe, it, expect } from "vitest";

import { getRiskBadge, getRiskLevel } from "./KBLIInspector";

// Zero decision 2026-07-17: an undefined/unclassified KBLI risk must surface as
// an honest "Not Classified" gap, NEVER the old false-reassuring "low"/"Low Risk"
// default. A cured false-friend code (per_skala detached) has no risk basis.
// Guilt + innocence corpus per scar #3 (a guard must not fire on legit neighbours).

describe("getRiskLevel", () => {
  it("INNOCENCE: real Indonesian risk tiers still map correctly", () => {
    expect(getRiskLevel("Tinggi")).toBe("high");
    expect(getRiskLevel("Menengah Tinggi")).toBe("medium-high");
    expect(getRiskLevel("Menengah")).toBe("medium");
    expect(getRiskLevel("Menengah Rendah")).toBe("medium-low");
    expect(getRiskLevel("Rendah")).toBe("low");
    // English aliases the router/licenses can emit.
    expect(getRiskLevel("High")).toBe("high");
    expect(getRiskLevel("Low")).toBe("low");
  });

  it("GUILT: undefined risk returns 'not-classified', never 'low'", () => {
    expect(getRiskLevel("Not classified")).toBe("not-classified");
    expect(getRiskLevel("")).toBe("not-classified");
    expect(getRiskLevel("Unknown")).toBe("not-classified");
    // A value matching no known tier is a gap, not a low reading.
    expect(getRiskLevel("¯\\_(ツ)_/¯")).toBe("not-classified");
  });
});

describe("getRiskBadge", () => {
  it("INNOCENCE: real risk tiers keep their labels", () => {
    expect(getRiskBadge("Rendah").label).toBe("Low Risk");
    expect(getRiskBadge("Tinggi").label).toBe("High Risk");
    expect(getRiskBadge("Menengah Tinggi").label).toBe("Medium-High Risk");
    expect(getRiskBadge("Menengah Rendah").label).toBe("Medium-Low Risk");
  });

  it("GUILT: undefined risk is neutral 'Not Classified', not 'Low Risk'", () => {
    const badge = getRiskBadge("Not classified");
    expect(badge.label).toBe("Not Classified");
    expect(badge.className).toContain("badge-neutral");
    expect(badge.label).not.toMatch(/low/i);
    expect(getRiskBadge("").label).toBe("Not Classified");
    expect(getRiskBadge("Unknown").label).toBe("Not Classified");
  });
});
