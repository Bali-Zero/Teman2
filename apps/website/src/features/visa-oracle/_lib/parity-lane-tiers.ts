/**
 * Parity harness two-tier lane classification (E4 slice, CP2 item 4 —
 * approved 2026-08-17, `research/visa/doctrine-factory/e4/CP2-decision-request.md`).
 *
 * Extends (does not fork) the QW-2 SHADOW-parity mechanism
 * (`shadow-parity.ts` / `preview-adapter.ts` / `gold-oracle-baseline.ts`,
 * merged #4234): this module classifies interview lanes into two fence
 * tiers, per the execution plan's E4 item (c) — "fence di regressione SOLO
 * sulle superfici che la riforma NON tocca; per le superfici riformate...
 * gli expected vengono dal claim ledger (oracolo dottrinale), e ogni
 * divergenza dal legacy è tracciata a un claim_id — mai eccezioni nominate
 * generiche." Full design:
 * `research/visa/doctrine-factory/e4/parity-harness-rescope.md`.
 *
 * Tier A (everything not in `TIER_B_LANES`) — a pure regression fence.
 * Existing test expecteds ARE the fence; no claim-ledger consultation is
 * ever needed and no divergence is ever silently accepted. A Tier-A
 * divergence is always `ESCALATE`d — either an accidental scope leak (bug)
 * or an undeclared dependency that must be re-classified into Tier B with
 * an explicit `claimId`, never silently absorbed into a generic exceptions
 * list (`parity-harness-rescope.md` §2, Tier A rule).
 *
 * Tier B (`TIER_B_LANES`) — the lanes `question-registry-audit.md` §3
 * actually reclassifies to a different runtime behavior. Their expected
 * outcome is derived from the claim ledger (`e2a-claim-ledger.md` /
 * `e2b-batch1-claim-ledger.md` / `e3a-cf1-resolution.md`), keyed by
 * `claimId` (format `CL-<code>-<NN>`, e.g. `CL-D2-03`). A divergence is
 * `ADOPT_LEDGER` only once a `claimId` is present AND the lane is not the
 * `family_sponsor_status_code` hard-sequencing exception (below);
 * otherwise it stays `KEEP_LEGACY_PENDING_CLAIM` — the safe, conservative
 * default, equivalent to leaving the lane in Tier A until proven otherwise
 * (`parity-harness-rescope.md` §2).
 *
 * CORRECTION vs. the CP2-approved source doc (not edited here — that
 * document is a frozen, already-approved artifact; this is a build-time
 * finding surfaced in this PR's review notes instead): §2's heading and
 * lead sentence both say "5 touched lanes" / "The 5 HUMAN_CONTEXT lanes...",
 * but only 4 are ever named (`trip_scope`, `investment_vehicle`,
 * `retirement_basis`, `family_sponsor_status_code`) — no 5th lane appears
 * anywhere in that section or in `question-registry-audit.md` §3's
 * 3-real-fact-candidate + 1-hard-sequencing-constraint breakdown (3 + 1 =
 * 4, matching CP2-decision-request.md item 3's own count). `TIER_B_LANES`
 * below implements the 4 lanes actually named, not the stated "5".
 */

/** `CL-<code>-<NN>`, e.g. `CL-D2-03`, `CL-E31B-01` — verified against every
 * claim id actually present in the two merged ledgers this session. */
const CLAIM_ID_PATTERN = /^CL-[A-Z0-9]+-\d{2,}$/;

export type DivergenceDisposition =
  "ADOPT_LEDGER" | "KEEP_LEGACY_PENDING_CLAIM" | "ESCALATE";

/** Mirrors `parity-harness-rescope.md` §2's `divergence_trace` YAML shape
 * verbatim — one record per Tier-A-or-Tier-B assertion whose legacy and
 * ledger-derived expected values disagree. */
export interface DivergenceTrace {
  readonly test: string;
  readonly lane: string;
  readonly legacyExpected: string;
  readonly ledgerExpected: string;
  readonly claimId: string | null;
  readonly disposition: DivergenceDisposition;
}

/**
 * The lanes `question-registry-audit.md` §3 reclassifies to a different
 * runtime behavior (real-fact-question candidates, or — for
 * `family_sponsor_status_code` — eliminate-as-direct-fact). Every other
 * reachable question id is Tier A by construction: `isTierB` is the only
 * place this distinction is made, so a lane can never drift between tiers
 * without a code change to this file.
 */
export const TIER_B_LANES: readonly string[] = [
  "trip_scope",
  "investment_vehicle",
  "retirement_basis",
  "family_sponsor_status_code",
];

/** The one Tier-B lane under a hard sequencing constraint
 * (`question-registry-audit.md` §3.1): `mapFamilySponsorStatus` must keep
 * emitting `UNVERIFIED`/`NOT_ASKED`, never `KNOWN`, until the E5 rule fix
 * for `op:known`'s value-blind predicate lands. This lane's expected can
 * never flip to `ADOPT_LEDGER` — not even once a claim exists — until that
 * fix is merged and verified in E5. */
const HARD_SEQUENCING_LANE = "family_sponsor_status_code";

export function isTierB(lane: string): boolean {
  return TIER_B_LANES.includes(lane);
}

/** `true` only for a syntactically well-formed `CL-<code>-<NN>` id — this
 * does not verify the claim actually exists in a ledger file (that is a
 * doctrine-authoring concern, out of scope for this runtime classifier). */
export function isWellFormedClaimId(claimId: string): boolean {
  return CLAIM_ID_PATTERN.test(claimId);
}

/**
 * Decides the disposition for an already-detected divergence (caller has
 * established `legacyExpected !== ledgerExpected`; this function does not
 * re-check that). Per `parity-harness-rescope.md` §2:
 *
 * - Tier A lanes never silently adopt the ledger — any divergence is
 *   `ESCALATE`.
 * - `family_sponsor_status_code` never adopts the ledger regardless of
 *   `claimId` — the E31B hard sequencing constraint holds unconditionally.
 * - Every other Tier B lane: `ADOPT_LEDGER` once a well-formed `claimId` is
 *   supplied, otherwise `KEEP_LEGACY_PENDING_CLAIM` (the safe default — "no
 *   generic known-exception list": an unclaimed divergence is never
 *   silently accepted).
 */
export function classifyDivergence(
  lane: string,
  claimId: string | null,
): DivergenceDisposition {
  if (!isTierB(lane)) return "ESCALATE";
  if (lane === HARD_SEQUENCING_LANE) return "KEEP_LEGACY_PENDING_CLAIM";
  if (claimId === null || !isWellFormedClaimId(claimId)) {
    return "KEEP_LEGACY_PENDING_CLAIM";
  }
  return "ADOPT_LEDGER";
}

/** Builds the full `DivergenceTrace` record for a detected divergence,
 * applying `classifyDivergence` for the `disposition` field. */
export function buildDivergenceTrace(input: {
  readonly test: string;
  readonly lane: string;
  readonly legacyExpected: string;
  readonly ledgerExpected: string;
  readonly claimId: string | null;
}): DivergenceTrace {
  return {
    ...input,
    disposition: classifyDivergence(input.lane, input.claimId),
  };
}
