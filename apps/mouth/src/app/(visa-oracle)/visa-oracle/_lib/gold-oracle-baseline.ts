import type { OracleFacts } from "./tree";

/**
 * Independent SHADOW-parity baseline (QW-2, 2026-08).
 *
 * REDESIGN NOTE (why this is not "3 NEEDS_INPUT gold personas copied
 * verbatim", the first draft of this file): the obvious approach — pin the
 * frontend's `OracleFacts` for a `NEEDS_INPUT` gold persona from
 * `apps/backend-rag/backend/tests/services/visa_engine/test_evaluator_gold.py`
 * (e.g. persona 13, "remote worker, local-clients fact unprovided") — turned
 * out to be UNREACHABLE from real browser traffic, reproducing the exact
 * "parity_match dead by construction" defect this file exists to fix,
 * one layer down:
 *
 *   1. `flow.ts`'s reducer NEVER leaves an in-path question's fact key
 *      absent at verdict time. `ANSWER` sets `facts[questionId] = value`;
 *      `SKIP` (the only user-facing way to leave a question "not really
 *      answered") sets `facts[questionId] = "unsure"` — a DEFINED sentinel,
 *      never `undefined` (flow.ts's reducer, verified by reading the ANSWER/
 *      SKIP cases and `FIXED_CATEGORY_QUESTIONS`/`computeNextNode`'s
 *      unconditional walk over every in-path question).
 *   2. `fact-mapper.ts::mapDisclosedReviewFlags` adds `"NOT_CERTAIN"` to the
 *      request's `disclosed_review_flags` whenever ANY answer in the whole
 *      interview is `"unsure"` (`Object.values(facts).includes("unsure")`).
 *   3. `evaluate_path.py::_apply_disclosed_review_flags` is a MONOTONE
 *      adapter: whenever `disclosed_review_flags` is non-empty, it
 *      unconditionally overrides the decision to `HUMAN_REVIEW_REQUIRED`
 *      with `candidates=()` and `missing_facts=()` — "This adapter cannot
 *      create or retain candidates" (its own docstring). It runs on every
 *      public evaluation (`apply_public_policy_adapters`'s ordered chain).
 *
 * So the ONE real, user-reachable way to make a fact "missing" from this
 * frontend (the SKIP/NotSure affordance) NEVER reaches the engine as a
 * `NEEDS_INPUT` — it is always overridden to `HUMAN_REVIEW_REQUIRED` before
 * the response leaves the backend. A `NEEDS_INPUT`-shaped baseline built on
 * a SKIP path would therefore never see a genuine `parity_match` in live
 * SHADOW traffic either — the SAME defect, moved.
 *
 * WHAT THIS BASELINE PINS INSTEAD: the two personas below both use the
 * SKIP/NotSure affordance on exactly one otherwise-inconsequential question,
 * and predict the `HUMAN_REVIEW_REQUIRED` state the disclosed-flags override
 * ALWAYS produces for that shape of interview. This is MORE robust than a
 * NEEDS_INPUT baseline, not a downgrade: `_DISCLOSED_REVIEW_REASON_CODES`
 * (evaluate_path.py, module-level constant) is PACK-INDEPENDENT — unlike a
 * rule-derived `NEEDS_INPUT`/`SUPPORTED_CANDIDATES` outcome, it does not
 * depend on which RulePack (the synthetic TEST gold pack vs. whatever pack
 * SHADOW production actually runs) is loaded, so this baseline cannot go
 * stale on a pack rotation the way a rule-derived one silently could.
 *
 * EMPIRICAL VERIFICATION (not inferred from reading — RUN, this turn,
 * 2026-08-16): both personas were built as `ApplicantFacts` overrides on the
 * gold suite's own `_gold_fixtures.applicant_facts()` / rule pack, pushed
 * through the REAL `evaluator.evaluate()` AND the REAL
 * `evaluate_path.apply_public_policy_adapters(..., disclosed_review_flags=
 * (NOT_CERTAIN,))` — the exact function `apply_public_policy_adapters`'s own
 * docstring calls "every deterministic abstention adapter used by the
 * public path" (minus runtime-only DB/pricing/persistence steps that do not
 * touch `state`/`review_reasons` on this path). Both personas: underlying
 * (pre-disclosure) state `NEEDS_INPUT` (never itself `HUMAN_REVIEW_REQUIRED`
 * — this matters because `_apply_disclosed_review_flags` MERGES in any
 * pre-existing review reasons, `existing_reasons`, only when the underlying
 * decision was already `HUMAN_REVIEW_REQUIRED`; here it wasn't, so the final
 * `review_reasons` is EXACTLY the disclosed reason, nothing merged in).
 * Final, for both: `state=HUMAN_REVIEW_REQUIRED`,
 * `review_reasons=[("DISCLOSED_UNCERTAINTY_REVIEW", source_refs=())]`,
 * `candidates=()`. Pin: `evaluate_path.py` sha256
 * `8ee131a989fc786f1fc54ad531ddefaa9614756361f284b6412ee8a23120e569`
 * (`_apply_disclosed_review_flags`/`_DISCLOSED_REVIEW_REASON_CODES`/
 * `apply_public_policy_adapters`).
 *
 * This file is a NON-TAUTOLOGICAL baseline by construction: every function
 * here takes only `OracleFacts` (what the applicant answered in THIS
 * browser tab) and returns a fixed, pre-authored expectation. It never
 * receives, inspects, or derives anything from a `VisaOracleEvaluateResponse`
 * — the thing SHADOW parity is checking. `shadow-parity.test.ts` and
 * `preview-adapter.test.ts` pin this with an explicit non-tautology test:
 * the SAME baseline instance is checked against several DIFFERENT mocked
 * responses, some agreeing and some not.
 *
 * SCOPE (documented, not silent): only these 2 "exactly one SKIP answer, no
 * other disclosed-flag trigger" personas are pinned — deliberately narrow
 * predicates (`matches` below checks every other answer is a SPECIFIC known
 * value, not "anything"), because `mapDisclosedReviewFlags` can add several
 * OTHER flags from unrelated answers (`ACTIVITY_BOUNDARY`,
 * `AMBIGUOUS_SPONSOR`, `MULTI_PURPOSE_TRIP`, …) that this baseline has not
 * verified the ordering/merge behaviour for. A wider "any SKIP anywhere"
 * matcher would be a false-precision trap, not a bigger baseline. This
 * baseline also predicts an EMPTY `sources` array (the disclosed-flag
 * adapter emits `source_refs=()` for its own reason, verified above; a real
 * response attaching unrelated sources elsewhere would still read as a
 * mismatch on that axis). Extending coverage is future work — not silently
 * absorbed into this subset.
 */

/** Identifies the pinned evaluator source this baseline was verified
 * against — the disclosed-review-flags policy is pack-independent (see file
 * doc comment), so this is a source digest, not a RulePack id. */
export const GOLD_ORACLE_PACK_HASH =
  "evaluate_path.py@8ee131a989fc786f1fc54ad531ddefaa9614756361f284b6412ee8a23120e569";

/** The one review reason `_apply_disclosed_review_flags` attaches for a
 * lone `NOT_CERTAIN` disclosure — `DisclosedReviewFlag.NOT_CERTAIN` ->
 * `_DISCLOSED_REVIEW_REASON_CODES` in `evaluate_path.py`. Empty `sourceIds`
 * is not a simplification: the adapter emits `source_refs=()` verbatim,
 * "these codes describe an applicant disclosure requiring a human workflow,
 * not a legal eligibility claim" (its own docstring). */
const DISCLOSED_UNCERTAINTY_REVIEW_CODE = "DISCLOSED_UNCERTAINTY_REVIEW";

export interface GoldOraclePersona {
  readonly personaId: string;
  readonly label: string;
  /** True when `facts` (this browser tab's interview answers, keyed by
   * question id — see `tree.ts`'s `OracleFacts` doc) matches this persona's
   * exact, narrow fact pattern. */
  matches(facts: OracleFacts): boolean;
}

const HUMAN_REVIEW_PERSONAS: readonly GoldOraclePersona[] = [
  {
    // Empirically verified via evaluator.evaluate + apply_public_policy_adapters
    // (see file doc comment) — remote worker, uncertain whether the employer
    // is an Indonesian entity; every other REMOTE_WORK-relevant fact known.
    //
    // REACHABILITY (2026-09-06): this persona's `work_payer` answer was
    // UNREACHABLE from a real browser walk until PR-3 of the decisiveness
    // wave — `work_payer` was in the `work` branch only, never in `remote`,
    // so no remote interview could ever produce these facts and the
    // baseline could never match live SHADOW traffic. Adding the question
    // to the remote branch (it is the only input to
    // `work.employer_is_indonesian_entity`) makes the persona live. The
    // predicted outcome is unchanged: an "unsure" answer anywhere still
    // yields `NOT_CERTAIN` -> `HUMAN_REVIEW_REQUIRED`. Pinned by
    // `gold-oracle-baseline.test.ts`.
    personaId: "remote-worker-payer-unsure",
    label: "remote worker, unsure whether employer is an Indonesian entity",
    matches: (facts) =>
      facts.category === "remote" &&
      facts.work_payer === "unsure" &&
      facts.remote_compensation === "no" &&
      facts.remote_clients === "foreign" &&
      facts.review_gate === "none",
  },
  {
    // Empirically verified the same way — spouse-sponsored family route,
    // uncertain whether the marriage is registered; every other FAMILY-
    // relevant fact known.
    personaId: "family-spouse-marriage-registered-unsure",
    label: "family spouse route, unsure whether marriage is registered",
    matches: (facts) =>
      facts.category === "family" &&
      facts.family_relation === "SPOUSE" &&
      facts.family_sponsor_nationalities === "ID" &&
      facts.family_sponsor_confirmed === "yes" &&
      facts.family_marriage_registered === "unsure" &&
      facts.review_gate === "none",
  },
];

/** First matching pinned persona, or `undefined` when this interview's
 * answers were not curated into the subset (documented SCOPE above). */
export function findGoldOraclePersona(
  facts: OracleFacts,
): GoldOraclePersona | undefined {
  return HUMAN_REVIEW_PERSONAS.find((persona) => persona.matches(facts));
}

/** The `HUMAN_REVIEW_REQUIRED` reason every matched persona predicts. */
export function goldOracleReviewReasonCode(): string {
  return DISCLOSED_UNCERTAINTY_REVIEW_CODE;
}
