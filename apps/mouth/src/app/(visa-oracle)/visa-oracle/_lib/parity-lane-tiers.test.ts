import { describe, expect, it } from "vitest";
import {
  TIER_B_LANES,
  buildDivergenceTrace,
  classifyDivergence,
  isTierB,
  isWellFormedClaimId,
} from "./parity-lane-tiers";

describe("TIER_B_LANES — the 4 lanes actually named by parity-harness-rescope.md §2", () => {
  it("is exactly the 4 lanes named, matching question-registry-audit.md §3's 3-real-fact + 1-hard-sequencing split", () => {
    // Guilt: adding/removing a lane here without updating this pin is
    // exactly the silent-drift this two-tier fence exists to prevent.
    expect([...TIER_B_LANES].sort()).toEqual(
      [
        "family_sponsor_status_code",
        "investment_vehicle",
        "retirement_basis",
        "trip_scope",
      ].sort(),
    );
  });

  it("does not include either of the 2 dead nodes deleted in this slice", () => {
    expect(TIER_B_LANES).not.toContain("tourism_duration");
    expect(TIER_B_LANES).not.toContain("remote_income");
  });
});

describe("isTierB", () => {
  it("is true only for the 4 reformed lanes (innocence: a random unreformed lane is Tier A)", () => {
    for (const lane of TIER_B_LANES) {
      expect(isTierB(lane)).toBe(true);
    }
    for (const lane of [
      "business_activity",
      "work_role",
      "diaspora_connection",
      "diaspora_documents",
      "other_purpose",
      "other_paid_activity",
      "stay_days",
      "category",
    ]) {
      expect(isTierB(lane)).toBe(false);
    }
  });
});

describe("isWellFormedClaimId", () => {
  it("accepts every claim id actually present in the merged ledgers", () => {
    for (const id of [
      "CL-D1-01",
      "CL-D1-02",
      "CL-D1-03",
      "CL-D2-01",
      "CL-D2-02",
      "CL-D2-03",
      "CL-D12-01",
      "CL-D12-05",
      "CL-E31B-01",
      "CL-E31D-01",
    ]) {
      expect(isWellFormedClaimId(id)).toBe(true);
    }
  });

  it("rejects malformed ids", () => {
    for (const bad of ["", "CL-D1", "D1-01", "cl-d1-01", "CL-D1-1", "CL--01"]) {
      expect(isWellFormedClaimId(bad)).toBe(false);
    }
  });
});

describe("classifyDivergence — the two-tier fence (parity-harness-rescope.md §2)", () => {
  it("Tier A: any divergence is ESCALATE, never silently accepted, even with a well-formed claimId supplied", () => {
    // Guilt: a Tier-A lane must never resolve to ADOPT_LEDGER or
    // KEEP_LEGACY_PENDING_CLAIM by accident — those two dispositions are
    // Tier-B-only vocabulary. A "helpful" claimId must not change this.
    expect(classifyDivergence("business_activity", null)).toBe("ESCALATE");
    expect(classifyDivergence("business_activity", "CL-D2-03")).toBe(
      "ESCALATE",
    );
    expect(classifyDivergence("stay_days", "CL-D1-01")).toBe("ESCALATE");
  });

  it("Tier B, no claimId: KEEP_LEGACY_PENDING_CLAIM (the safe default — 0 claims exist today for any of the 4)", () => {
    for (const lane of TIER_B_LANES) {
      expect(classifyDivergence(lane, null)).toBe("KEEP_LEGACY_PENDING_CLAIM");
    }
  });

  it("Tier B, malformed claimId: still KEEP_LEGACY_PENDING_CLAIM, never ADOPT_LEDGER", () => {
    expect(classifyDivergence("trip_scope", "not-a-claim-id")).toBe(
      "KEEP_LEGACY_PENDING_CLAIM",
    );
  });

  it("Tier B (non-sequencing lane), well-formed claimId: ADOPT_LEDGER — the mechanism activates once a claim exists", () => {
    expect(classifyDivergence("trip_scope", "CL-D1-03")).toBe("ADOPT_LEDGER");
    expect(classifyDivergence("investment_vehicle", "CL-D2-03")).toBe(
      "ADOPT_LEDGER",
    );
    expect(classifyDivergence("retirement_basis", "CL-D12-05")).toBe(
      "ADOPT_LEDGER",
    );
  });

  it("family_sponsor_status_code: KEEP_LEGACY_PENDING_CLAIM unconditionally, even with a well-formed claimId (E31B hard sequencing constraint)", () => {
    // Guilt: this is the RC-1 reform's central risk case
    // (question-registry-audit.md §3 row 5 / §3.1). A claim existing for
    // the sponsor-status doctrine is NOT sufficient to unblock this lane —
    // only the E5 `op:known` rule fix is. This must hold even when a
    // claimId is supplied, unlike every other Tier-B lane.
    expect(classifyDivergence("family_sponsor_status_code", null)).toBe(
      "KEEP_LEGACY_PENDING_CLAIM",
    );
    expect(classifyDivergence("family_sponsor_status_code", "CL-E31B-01")).toBe(
      "KEEP_LEGACY_PENDING_CLAIM",
    );
  });
});

describe("buildDivergenceTrace", () => {
  it("produces the exact divergence_trace shape from parity-harness-rescope.md §2, with the computed disposition", () => {
    const trace = buildDivergenceTrace({
      test: "trip-scope.test.ts::single vs multiple entry",
      lane: "trip_scope",
      legacyExpected: "HUMAN_CONTEXT (advisory only)",
      ledgerExpected: "single => KNOWN(false)",
      claimId: "CL-D1-03",
    });
    expect(trace).toEqual({
      test: "trip-scope.test.ts::single vs multiple entry",
      lane: "trip_scope",
      legacyExpected: "HUMAN_CONTEXT (advisory only)",
      ledgerExpected: "single => KNOWN(false)",
      claimId: "CL-D1-03",
      disposition: "ADOPT_LEDGER",
    });
  });

  it("defaults to KEEP_LEGACY_PENDING_CLAIM with claimId: null when no claim exists yet (today's actual state, per §3)", () => {
    const trace = buildDivergenceTrace({
      test: "investment-vehicle.test.ts::property branch",
      lane: "investment_vehicle",
      legacyExpected: "HUMAN_CONTEXT (advisory only)",
      ledgerExpected: "unknown — no claim yet",
      claimId: null,
    });
    expect(trace.disposition).toBe("KEEP_LEGACY_PENDING_CLAIM");
  });
});
