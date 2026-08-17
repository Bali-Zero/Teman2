import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { mapOracleFactsToApplicantFacts } from "./fact-mapper";
import { QUESTIONS } from "./tree";
import {
  DIVERGENCE_REGISTRY,
  DivergenceTraceError,
  FAMILY_SPONSOR_STATUS_LANE_ID,
  TIER_B_LANE_IDS,
  assertDivergenceTraceValid,
  isTierBLane,
  validateDivergenceRegistry,
  type DivergenceTrace,
} from "./e4-tier-fence";

// Every claim_id actually present in the merged claim ledgers, loaded from disk so the
// existence check below is real, not a guess about ledger contents. Repo-root-relative:
// this file lives at apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/.
const CLAIMS_DIR = join(
  __dirname,
  "../../../../../../../research/visa/doctrine-factory/claims",
);
const CLAIM_LEDGER_FILES = [
  "e2a-claim-ledger.md",
  "e2b-batch1-claim-ledger.md",
  "e3a-cf1-resolution.md",
];

function loadKnownClaimIds(): ReadonlySet<string> {
  const ids = new Set<string>();
  for (const file of CLAIM_LEDGER_FILES) {
    const text = readFileSync(join(CLAIMS_DIR, file), "utf8");
    for (const match of text.matchAll(/\bCL-[A-Z0-9]+(?:-[A-Z0-9]+)+\b/g)) {
      ids.add(match[0]);
    }
  }
  return ids;
}

const KNOWN_CLAIM_IDS = loadKnownClaimIds();

describe("e4-tier-fence — Tier-B lane identity", () => {
  it("loaded a non-trivial number of real claim ids from the merged ledgers", () => {
    // Sanity check on the loader itself, not the fence — if this is 0 the existence-check
    // tests below would pass vacuously (everything "not found").
    expect(KNOWN_CLAIM_IDS.size).toBeGreaterThan(10);
    expect(KNOWN_CLAIM_IDS.has("CL-D1-01")).toBe(true);
    expect(KNOWN_CLAIM_IDS.has("CL-D-FUNDS")).toBe(true);
  });

  it(
    "TIER_B_LANE_IDS has exactly 4 entries — the merged design doc's own 12-lane split " +
      "(question-registry-audit.md §3: 3 real-fact candidates + 1 risk case) and its own " +
      "Tier-A arithmetic (parity-harness-rescope.md §2: 12 − 8 = 4) both agree on 4, " +
      "notwithstanding that doc's uncorrected '5 touched lanes' prose",
    () => {
      expect(TIER_B_LANE_IDS.length).toBe(4);
    },
  );

  it("every Tier-B lane id resolves to a real question in the registry", () => {
    for (const laneId of TIER_B_LANE_IDS) {
      expect(QUESTIONS[laneId as keyof typeof QUESTIONS]).toBeDefined();
    }
  });

  it(
    "Tier-B lanes remain HUMAN_CONTEXT today — the reform has NOT shipped yet " +
      "(regression tripwire: flipping any of these to a decisional kind without a claim " +
      "is exactly the §0 failure mode the CP2 pack found: interview behavior with no " +
      "doctrine behind it)",
    () => {
      for (const laneId of TIER_B_LANE_IDS) {
        const question = QUESTIONS[laneId as keyof typeof QUESTIONS];
        expect(question.decisionMapping.kind).toBe("HUMAN_CONTEXT");
      }
    },
  );

  it("isTierBLane distinguishes Tier-B lanes from an arbitrary Tier-A question id", () => {
    for (const laneId of TIER_B_LANE_IDS) {
      expect(isTierBLane(laneId)).toBe(true);
    }
    expect(isTierBLane("nationality")).toBe(false);
    expect(isTierBLane("not_a_real_question_id")).toBe(false);
  });
});

describe(
  "e4-tier-fence — coupling: a Tier-B kind flip requires a traced divergence " +
    "(closes the hole where a reform PR flips tree.ts and updates the tripwire above in " +
    "the same diff, with nothing else forcing a DIVERGENCE_REGISTRY entry to exist)",
  () => {
    for (const laneId of TIER_B_LANE_IDS) {
      it(`${laneId}: HUMAN_CONTEXT, or a non-KEEP_LEGACY_PENDING_CLAIM trace exists for it`, () => {
        const question = QUESTIONS[laneId as keyof typeof QUESTIONS];
        if (question.decisionMapping.kind === "HUMAN_CONTEXT") {
          return; // unreformed — nothing to trace yet, this is the normal state today.
        }
        const hasTrace = DIVERGENCE_REGISTRY.some(
          (trace) =>
            trace.lane === laneId &&
            trace.disposition !== "KEEP_LEGACY_PENDING_CLAIM",
        );
        expect(hasTrace).toBe(true);
      });
    }
  },
);

describe(
  "e4-tier-fence — family_sponsor_status_code never-emit-KNOWN guard " +
    "(this file does not re-test fact-mapper.ts's mapFamilySponsorStatus — " +
    "fact-mapper.test.ts already pins that directly; this is a pointer, not a duplicate, " +
    "confirming the guard this module's ADOPT_LEDGER prohibition exists to protect is real)",
  () => {
    it("a fully-answered sponsor-status interview never emits KNOWN on the wire", () => {
      const result = mapOracleFactsToApplicantFacts(
        {
          family_sponsor_confirmed: "yes",
          family_sponsor_status_code: "PLAUSIBLE_LOOKING_CODE",
        } as Parameters<typeof mapOracleFactsToApplicantFacts>[0],
        {
          assessmentId: "11111111-1111-4111-8111-111111111111",
          collectedAt: new Date("2026-08-17T00:00:00.000Z"),
        },
      );
      expect(result.facts["family.sponsor_status_code"].status).toBe("UNKNOWN");
    });
  },
);

describe("e4-tier-fence — divergence trace validation", () => {
  const baseTrace: DivergenceTrace = {
    test: "example.test.ts::example",
    lane: "trip_scope",
    legacyExpected: "HUMAN_CONTEXT",
    ledgerExpected: "some claim-derived value",
    disposition: "KEEP_LEGACY_PENDING_CLAIM",
  };

  it("accepts KEEP_LEGACY_PENDING_CLAIM with no claim_id", () => {
    expect(() => assertDivergenceTraceValid(baseTrace)).not.toThrow();
  });

  it("accepts ADOPT_LEDGER with a well-formed, real claim_id", () => {
    expect(() =>
      assertDivergenceTraceValid(
        { ...baseTrace, disposition: "ADOPT_LEDGER", claimId: "CL-D1-03" },
        { knownClaimIds: KNOWN_CLAIM_IDS },
      ),
    ).not.toThrow();
  });

  it("accepts the compound claim_id shape observed in the ledger (CL-D-FUNDS)", () => {
    expect(() =>
      assertDivergenceTraceValid(
        { ...baseTrace, disposition: "ADOPT_LEDGER", claimId: "CL-D-FUNDS" },
        { knownClaimIds: KNOWN_CLAIM_IDS },
      ),
    ).not.toThrow();
  });

  it("rejects ADOPT_LEDGER with a missing claim_id — no generic named exceptions", () => {
    expect(() =>
      assertDivergenceTraceValid({ ...baseTrace, disposition: "ADOPT_LEDGER" }),
    ).toThrow(DivergenceTraceError);
  });

  it("rejects ADOPT_LEDGER with a malformed claim_id", () => {
    expect(() =>
      assertDivergenceTraceValid({
        ...baseTrace,
        disposition: "ADOPT_LEDGER",
        claimId: "not-a-claim-id",
      }),
    ).toThrow(DivergenceTraceError);
  });

  it(
    "rejects ADOPT_LEDGER with a well-formed but NON-EXISTENT claim_id — the hole a " +
      "regex-only check leaves open (found by Kimi K3 review on this file's own PR)",
    () => {
      expect(() =>
        assertDivergenceTraceValid(
          { ...baseTrace, disposition: "ADOPT_LEDGER", claimId: "CL-Z9-99" },
          { knownClaimIds: KNOWN_CLAIM_IDS },
        ),
      ).toThrow(DivergenceTraceError);
    },
  );

  it("without knownClaimIds supplied, existence is not checked (shape-only mode)", () => {
    expect(() =>
      assertDivergenceTraceValid({
        ...baseTrace,
        disposition: "ADOPT_LEDGER",
        claimId: "CL-Z9-99",
      }),
    ).not.toThrow();
  });

  it("rejects a trace citing a Tier-A (non-reformed) lane", () => {
    expect(() =>
      assertDivergenceTraceValid({
        ...baseTrace,
        // @ts-expect-error — deliberately testing a lane outside the Tier-B type
        lane: "nationality",
      }),
    ).toThrow(DivergenceTraceError);
  });

  it("rejects a phantom divergence — legacyExpected identical to ledgerExpected", () => {
    expect(() =>
      assertDivergenceTraceValid({
        ...baseTrace,
        legacyExpected: "HUMAN_CONTEXT",
        ledgerExpected: "HUMAN_CONTEXT",
      }),
    ).toThrow(DivergenceTraceError);
  });

  it('rejects a malformed "test" locator', () => {
    expect(() =>
      assertDivergenceTraceValid({ ...baseTrace, test: "not-a-locator" }),
    ).toThrow(DivergenceTraceError);
  });

  it(
    "rejects ADOPT_LEDGER on family_sponsor_status_code even with a real claim_id — " +
      "this lane can never silently adopt a ledger value ahead of the E31B rule fix",
    () => {
      expect(() =>
        assertDivergenceTraceValid(
          {
            ...baseTrace,
            lane: FAMILY_SPONSOR_STATUS_LANE_ID,
            disposition: "ADOPT_LEDGER",
            claimId: "CL-D1-03",
          },
          { knownClaimIds: KNOWN_CLAIM_IDS },
        ),
      ).toThrow(DivergenceTraceError);
    },
  );

  it(
    "accepts ESCALATE on family_sponsor_status_code — raising to a human stays a legitimate " +
      "exit even on the risk-case lane; only silent ADOPT_LEDGER is forbidden " +
      "(corrected after Kimi K3 review found the first draft over-blocked ESCALATE too)",
    () => {
      expect(() =>
        assertDivergenceTraceValid({
          ...baseTrace,
          lane: FAMILY_SPONSOR_STATUS_LANE_ID,
          disposition: "ESCALATE",
        }),
      ).not.toThrow();
    },
  );

  it("accepts KEEP_LEGACY_PENDING_CLAIM on family_sponsor_status_code", () => {
    expect(() =>
      assertDivergenceTraceValid({
        ...baseTrace,
        lane: FAMILY_SPONSOR_STATUS_LANE_ID,
        disposition: "KEEP_LEGACY_PENDING_CLAIM",
      }),
    ).not.toThrow();
  });
});

describe("e4-tier-fence — registry-level invariants", () => {
  const validEntry: DivergenceTrace = {
    test: "example.test.ts::case a",
    lane: "trip_scope",
    legacyExpected: "HUMAN_CONTEXT",
    ledgerExpected: "real fact question",
    disposition: "KEEP_LEGACY_PENDING_CLAIM",
  };

  it("accepts a well-formed synthetic registry", () => {
    expect(() =>
      validateDivergenceRegistry([
        validEntry,
        {
          ...validEntry,
          test: "example.test.ts::case b",
          lane: "investment_vehicle",
        },
      ]),
    ).not.toThrow();
  });

  it("rejects a duplicate (test, lane) pair — no silently shadowed entries", () => {
    expect(() =>
      validateDivergenceRegistry([validEntry, { ...validEntry }]),
    ).toThrow(DivergenceTraceError);
  });

  it("rejects a registry containing any invalid entry, mid-list", () => {
    expect(() =>
      validateDivergenceRegistry(
        [
          validEntry,
          {
            ...validEntry,
            test: "example.test.ts::case c",
            disposition: "ADOPT_LEDGER",
            claimId: "CL-INVENTED-99",
          },
        ],
        { knownClaimIds: KNOWN_CLAIM_IDS },
      ),
    ).toThrow(DivergenceTraceError);
  });
});

describe("e4-tier-fence — live registry state", () => {
  it(
    "DIVERGENCE_REGISTRY is currently empty — parity-harness-rescope.md §2 measured zero " +
      "claims covering interview-branch semantics for any Tier-B lane as of 2026-08-17. " +
      "Update this test intentionally, in the same PR that adds the first real entry.",
    () => {
      expect(DIVERGENCE_REGISTRY).toEqual([]);
    },
  );

  it("the live registry validates against the real claim ledgers", () => {
    expect(() =>
      validateDivergenceRegistry(DIVERGENCE_REGISTRY, {
        knownClaimIds: KNOWN_CLAIM_IDS,
      }),
    ).not.toThrow();
  });
});
