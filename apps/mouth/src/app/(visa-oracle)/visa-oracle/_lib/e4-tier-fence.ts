/**
 * E4 slice — parity-harness re-scope, operationalized.
 *
 * Design source of truth: research/visa/doctrine-factory/e4/parity-harness-rescope.md
 * (merged PR #4254, CP2 decision pack). That document specifies a two-tier fence for the
 * RC-1 flag-veto reform's 12 HUMAN_CONTEXT interview lanes:
 *
 *   Tier A — everything the reform does NOT touch. Existing test expecteds ARE the fence:
 *            byte-identical output before/after, no claim-ledger lookup needed.
 *   Tier B — the lanes the reform DOES reclassify. Their expected outcome must come from
 *            the claim ledger (`research/visa/doctrine-factory/claims/*.md`), keyed by
 *            claim_id. "No generic named exceptions" — every divergence traces to either a
 *            real claim_id (ADOPT_LEDGER) or an explicit block (KEEP_LEGACY_PENDING_CLAIM /
 *            ESCALATE).
 *
 * This module is the machine-checkable form of that mechanism. It does not change runtime
 * interview behavior — QUESTIONS in ./tree stays HUMAN_CONTEXT on every Tier-B lane today,
 * per the CP2 pack's own finding that zero claims currently exist for interview-branch
 * semantics on these lanes (§2, "Tier B currently has no tests to write against real
 * claims"). E5/E6 populate DIVERGENCE_REGISTRY once claims land; until then this file's
 * tests are a tripwire against silent premature reform (the exact §0 failure mode the CP2
 * pack found in the source design: shipping interview behavior with no doctrine behind it).
 *
 * CORRECTION (found by Kimi K3 adversarial review, 2026-08-17, on this file's own PR): the
 * merged design doc's §2 prose says "5 touched lanes" three times, but its own enumeration
 * names only 4 (`trip_scope`, `investment_vehicle`, `retirement_basis`,
 * `family_sponsor_status_code`), and its own Tier-A arithmetic (12 total − 8 Tier-A = 4)
 * agrees with `question-registry-audit.md` §3's split (3 real-fact candidates + 1 risk
 * case = 4 lanes reclassified in runtime behavior; the other 8 are 4 REVIEW_ONLY-in-name-only
 * + 2 structural-forever + 2 dead nodes). The "5" in the merged doc is an uncorrected
 * off-by-one in its own prose — this module implements the 4 lanes the doc's own
 * enumeration and arithmetic name, not the miscounted headline figure.
 */

/**
 * The 4 HUMAN_CONTEXT question ids the RC-1 veto reform reclassifies. Sourced from
 * parity-harness-rescope.md §2's enumeration (not its "5 touched lanes" headline count,
 * which is an internal off-by-one — see the module-level comment above). Do not add/remove
 * entries here without updating the design doc first — this list IS the Tier A/Tier B
 * partition boundary.
 */
export const TIER_B_LANE_IDS = [
  "trip_scope",
  "investment_vehicle",
  "retirement_basis",
  "family_sponsor_status_code",
] as const;

export type TierBLaneId = (typeof TIER_B_LANE_IDS)[number];

export function isTierBLane(questionId: string): questionId is TierBLaneId {
  return (TIER_B_LANE_IDS as readonly string[]).includes(questionId);
}

/**
 * The one Tier-B lane with a mandatory disposition regardless of claim availability.
 * question-registry-audit.md §3.1: family_sponsor_status_code cannot be ADOPT_LEDGER'd into
 * a KNOWN-emitting behavior until the E31B rule fix lands in E5 — it is a fail-open
 * containment currently doing its job (see fact-mapper.ts's `mapFamilySponsorStatus`, which
 * this module deliberately does not re-test — fact-mapper.test.ts already pins that
 * never-emit-KNOWN guard directly; this module's job is the interview-lane *classification*
 * coupling, not re-proving the mapper). ESCALATE (raise to a human) stays legitimate on this
 * lane; only ADOPT_LEDGER — silently trusting an un-authored rule fix — is forbidden.
 */
export const FAMILY_SPONSOR_STATUS_LANE_ID: TierBLaneId =
  "family_sponsor_status_code";

export type DivergenceDisposition =
  "ADOPT_LEDGER" | "KEEP_LEGACY_PENDING_CLAIM" | "ESCALATE";

/**
 * One traced divergence between a pre-reform (legacy) test expectation and a post-reform,
 * claim-ledger-derived expectation. Shape matches parity-harness-rescope.md §2's
 * `divergence_trace` block verbatim.
 */
export interface DivergenceTrace {
  /** "<test file>::<test name>" of the assertion this divergence was found in. */
  readonly test: string;
  readonly lane: TierBLaneId;
  readonly legacyExpected: string;
  readonly ledgerExpected: string;
  /** Required and existence-checked only when disposition === "ADOPT_LEDGER". */
  readonly claimId?: string;
  readonly disposition: DivergenceDisposition;
}

const TEST_LOCATOR_PATTERN = /^.+\.test\.ts::.+$/;

/**
 * `CL-<CODE>[-<CODE>...]` — covers both observed ledger shapes (`CL-D1-01`, `CL-D-FUNDS`).
 * This is a SHAPE check only. It is deliberately not the enforcement boundary — a
 * well-formed-but-invented id (`CL-Z9-99`) still matches this pattern. The real boundary is
 * the `options.knownClaimIds` membership check inside `assertDivergenceTraceValid` below,
 * which checks against ids actually present in the claim ledgers on disk. Callers that only
 * need shape validation (e.g. quick unit tests) omit `knownClaimIds`; callers asserting a
 * real divergence must supply it.
 */
const CLAIM_ID_PATTERN = /^CL-[A-Z0-9]+(?:-[A-Z0-9]+)+$/;

export class DivergenceTraceError extends Error {}

export interface AssertDivergenceTraceOptions {
  /**
   * The set of claim_ids that actually exist in the merged claim ledgers
   * (`research/visa/doctrine-factory/claims/*.md`). When supplied, an ADOPT_LEDGER trace's
   * claimId must be a member — closes the "well-formed but invented" hole a regex-only check
   * leaves open. Loading the ledger requires filesystem access, so this module (which may be
   * bundled client-side) never reads it itself; e4-tier-fence.test.ts loads it from disk at
   * test time and passes it in.
   */
  readonly knownClaimIds?: ReadonlySet<string>;
}

/**
 * Enforces the "never generic named exceptions" rule from the design doc: a divergence
 * claiming ADOPT_LEDGER must cite a real, ledger-verifiable claim_id, and the mandatory
 * family_sponsor_status_code containment can never adopt an un-authored rule fix.
 */
export function assertDivergenceTraceValid(
  trace: DivergenceTrace,
  options: AssertDivergenceTraceOptions = {},
): void {
  if (!isTierBLane(trace.lane)) {
    throw new DivergenceTraceError(
      `divergence trace for "${trace.test}" cites lane "${trace.lane}", which is not a ` +
        `Tier-B lane (${TIER_B_LANE_IDS.join(", ")}). Tier-A surfaces are a hard regression ` +
        `fence and must never carry a claim-ledger divergence.`,
    );
  }

  if (!TEST_LOCATOR_PATTERN.test(trace.test)) {
    throw new DivergenceTraceError(
      `divergence trace has malformed "test" locator ${JSON.stringify(trace.test)} — ` +
        `expected the shape "<file>.test.ts::<test name>".`,
    );
  }

  if (trace.legacyExpected === trace.ledgerExpected) {
    throw new DivergenceTraceError(
      `divergence trace for "${trace.test}" (lane "${trace.lane}") has identical ` +
        `legacyExpected/ledgerExpected — that is not a divergence, it is noise. Remove the ` +
        `entry or fix whichever side was mistranscribed.`,
    );
  }

  if (
    trace.lane === FAMILY_SPONSOR_STATUS_LANE_ID &&
    trace.disposition === "ADOPT_LEDGER"
  ) {
    throw new DivergenceTraceError(
      `divergence trace for "${trace.test}" sets disposition ADOPT_LEDGER on ` +
        `family_sponsor_status_code — this lane can never silently adopt a ledger value; ` +
        `the E31B rule fix must land in E5 first (question-registry-audit.md §3.1). ` +
        `KEEP_LEGACY_PENDING_CLAIM or ESCALATE (raise to a human) remain available.`,
    );
  }

  if (trace.claimId !== undefined) {
    if (!CLAIM_ID_PATTERN.test(trace.claimId)) {
      throw new DivergenceTraceError(
        `divergence trace for "${trace.test}" (lane "${trace.lane}") has a malformed ` +
          `claim_id ${JSON.stringify(trace.claimId)}.`,
      );
    }
    if (options.knownClaimIds && !options.knownClaimIds.has(trace.claimId)) {
      throw new DivergenceTraceError(
        `divergence trace for "${trace.test}" (lane "${trace.lane}") cites claim_id ` +
          `"${trace.claimId}", which does not exist in the merged claim ledgers. A ` +
          `well-formed id is not enough — it must be a REAL claim (no generic named ` +
          `exceptions, parity-harness-rescope.md §2).`,
      );
    }
  }

  if (trace.disposition === "ADOPT_LEDGER" && !trace.claimId) {
    throw new DivergenceTraceError(
      `divergence trace for "${trace.test}" (lane "${trace.lane}") has disposition ` +
        `ADOPT_LEDGER but no claim_id. Every ADOPT_LEDGER divergence must trace to a real ` +
        `claim_id — no generic named exceptions (parity-harness-rescope.md §2).`,
    );
  }
}

/**
 * Populated by E5/E6 as they land claim-backed interview reforms for the Tier-B lanes.
 * Empty today: parity-harness-rescope.md §2 measured zero claims covering interview-branch
 * semantics (as opposed to product-eligibility semantics) for any of these lanes as of
 * 2026-08-17. A test asserting this stays empty is a deliberate tripwire, not a permanent
 * invariant — update it intentionally, in the same PR that adds the first real claim-backed
 * divergence, never as a side effect of an unrelated change.
 */
export const DIVERGENCE_REGISTRY: readonly DivergenceTrace[] = [];

/**
 * Validates every entry (shape, claim existence when `knownClaimIds` supplied, mandatory
 * family_sponsor_status_code containment) AND registry-level invariants that no single trace
 * can express on its own: no duplicate (test, lane) pair silently shadowing another entry.
 */
export function validateDivergenceRegistry(
  registry: readonly DivergenceTrace[] = DIVERGENCE_REGISTRY,
  options: AssertDivergenceTraceOptions = {},
): void {
  const seen = new Set<string>();
  for (const trace of registry) {
    assertDivergenceTraceValid(trace, options);
    const key = `${trace.test}::${trace.lane}`;
    if (seen.has(key)) {
      throw new DivergenceTraceError(
        `duplicate divergence trace for (test="${trace.test}", lane="${trace.lane}") — ` +
          `each (test, lane) pair may appear at most once in the registry.`,
      );
    }
    seen.add(key);
  }
}
