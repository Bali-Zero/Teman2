/**
 * Visa Oracle v2 — mock evaluation engine.
 *
 * Pure, deterministic: same facts in, same result out (unit-tested below).
 * This is a MOCK stand-in for the real visa_engine (design doc §5, not yet
 * built) — it exists to power the frontend experience, not to make legal
 * determinations. Aligned to the PR0 5-state `RecommendState` contract
 * (`@/lib/visa-oracle/types`).
 */
import type { RecommendState } from "@/lib/visa-oracle/types";
import {
  BEHAVIORAL_CATEGORIES,
  CATEGORY_KEYS,
  MOCK_CATALOG,
  QUESTIONS,
  getLane,
  type CategoryKey,
  type EligibilityState,
  type Lane,
  type MockVisaCard,
  type OracleFacts,
} from "./tree";

/** A skipped question, visibly logged (design doc §3 "honesty receipt").
 * `questionId` is the only field — copy is looked up via i18n, never
 * stored as free text. */
export interface Assumption {
  questionId: string;
}

export interface EvaluatedCandidate extends MockVisaCard {
  /** Eligibility as computed for THIS session — may differ from the
   * catalog's static default when a soft signal downgrades it (design doc
   * §4 remote income floor: "downgraded honestly, not killed"). */
  eligibility: EligibilityState;
}

export interface EvaluateResult {
  state: RecommendState;
  candidates: EvaluatedCandidate[];
  assumptions: Assumption[];
  pathsRemaining: number;
  /** Populated only for NO_SUPPORTED_PATH — design doc §4: "three mandatory
   * 'what instead' blocks, never a bare dead end." */
  alternativeCategories?: CategoryKey[];
}

// Finding #7 (adversarial review 2026-07-17): permit_expiry joins the
// load-bearing "never guess" set — an unsure compliance deadline holds
// for a human exactly like an unsure payer/clients/income.
const FORCE_REVIEW_ON_UNSURE = new Set([
  "work_payer",
  "remote_clients",
  "remote_income",
  "permit_expiry",
]);

/** The reserved "I don't know" value NotSure writes into facts. Resolving
 * it happens in one place so candidate-matching and completeness checks
 * never have to special-case it individually. */
const UNSURE = "unsure";

/** Resolve a raw fact value to the value candidate-matching should use:
 * conservative-branch questions substitute their conservative default,
 * force-review questions resolve to `undefined` (matching is moot — the
 * state is already forced to HUMAN_REVIEW_REQUIRED by the caller). */
function resolvedFacts(facts: OracleFacts): OracleFacts {
  const out: OracleFacts = {};
  for (const [id, value] of Object.entries(facts)) {
    if (value !== UNSURE) {
      out[id] = value;
      continue;
    }
    const question = QUESTIONS[id];
    if (question?.notSure?.mode === "conservative") {
      out[id] = question.notSure.conservativeValue;
    }
    // force-review questions: leave unresolved (excluded from `out`), the
    // caller short-circuits to HUMAN_REVIEW_REQUIRED before this matters.
  }
  return out;
}

function cardMatches(
  card: MockVisaCard,
  facts: OracleFacts,
  lane: Lane | null,
): boolean {
  // category unanswered yet => still possible, don't exclude.
  if (
    facts.category !== undefined &&
    !card.categories.includes(facts.category)
  ) {
    return false;
  }
  // Finding #3: lane governs candidacy (Bridging Visa ONLY in the
  // "bridging" lane). A lane not yet known (null) never excludes — same
  // monotonic-narrowing discipline as requiredFacts below.
  if (
    card.laneRestriction &&
    lane !== null &&
    !card.laneRestriction.includes(lane)
  ) {
    return false;
  }
  const required = card.requiredFacts ?? {};
  for (const [factId, allowed] of Object.entries(required)) {
    const value = facts[factId];
    if (value === undefined) continue; // not yet answered => still possible
    if (!allowed.includes(value)) return false;
  }
  return true;
}

/** Candidates still possible given the facts known so far. Monotonically
 * non-increasing as more facts are answered (never re-admits a card). */
export function filterCandidates(
  facts: OracleFacts,
  today: Date = new Date(),
): MockVisaCard[] {
  const resolved = resolvedFacts(facts);
  const lane = getLane(resolved, today);
  return MOCK_CATALOG.filter((card) => cardMatches(card, resolved, lane));
}

/** How many candidate paths remain, given the facts known so far. */
export function pathsRemaining(
  facts: OracleFacts,
  today: Date = new Date(),
): number {
  return filterCandidates(facts, today).length;
}

function computeAssumptions(facts: OracleFacts): Assumption[] {
  return Object.entries(facts)
    .filter(([, value]) => value === UNSURE)
    .map(([questionId]) => ({ questionId }));
}

/**
 * Has enough of the interview been answered to reach a terminal decision?
 * Pure function of RESOLVED facts + the flow graph in `tree.ts`.
 *
 * Finding #2 (adversarial review 2026-07-17): takes `resolved` (not raw)
 * facts — a raw `in_indonesia === "unsure"` used to fail the `=== "yes"`
 * check below, silently skipping the permit_expiry requirement and
 * letting an unresolved onshore/offshore ambiguity reach
 * SUPPORTED_CANDIDATES. Since `resolvedFacts()` resolves unsure
 * conservatively to "yes" (tree.ts `in_indonesia.notSure.conservativeValue`),
 * checking `resolved.in_indonesia === "yes"` here now catches both the
 * literal "yes" answer and the conservative resolution of "unsure".
 */
function isComplete(resolved: OracleFacts): boolean {
  if (!resolved.in_indonesia) return false;
  if (resolved.in_indonesia === "yes" && !resolved.permit_expiry) return false;
  if (!resolved.category) return false;
  const category = resolved.category as CategoryKey | undefined;
  if (category === "work" && !resolved.work_payer) return false;
  if (
    category === "remote" &&
    (!resolved.remote_clients || !resolved.remote_income)
  )
    return false;
  if (category === "tourism" && !resolved.tourism_duration) return false;
  if (!resolved.review_gate) return false;
  return true;
}

function adjustEligibility(
  card: MockVisaCard,
  resolved: OracleFacts,
): EligibilityState {
  if (card.code === "E33G") {
    // Finding #14: mixed Indonesian/foreign clients is the honest
    // "likely-not" sample — real tolerance risk, not excluded outright
    // (the other reachable 4th state, alongside the review-gate path).
    if (resolved.remote_clients === "mixed") return "likely-not";
    // Below-floor income does not exclude the candidate, it honestly
    // downgrades it (design doc §4 "downgraded honestly, not killed").
    if (resolved.remote_income === "below") return "conditional";
  }
  return card.eligibility;
}

/**
 * Evaluate the interview so far. Deterministic: identical `(facts, today)`
 * always produce an identical result (unit-tested). `today` defaults to
 * `new Date()` at the call site and only matters for the onshore lane
 * (`getLane`) — pass it explicitly in tests for a pinned clock.
 */
export function evaluate(
  facts: OracleFacts,
  today: Date = new Date(),
): EvaluateResult {
  const assumptions = computeAssumptions(facts);
  // Finding #2: normalize ONCE — lane, completeness, and candidate
  // filtering all read `resolved`, never raw `facts`, so an
  // `in_indonesia: "unsure"` (conservative → "yes") can never disagree
  // with itself across these three checks the way it did before.
  const resolved = resolvedFacts(facts);
  const lane = getLane(resolved, today);
  const candidatesSoFar = filterCandidates(facts, today);
  const paths = candidatesSoFar.length;

  const laneForcesReview = lane === "expired" || lane === "urgent";

  const unsureForcesReview = Object.entries(facts).some(
    ([id, value]) => value === UNSURE && FORCE_REVIEW_ON_UNSURE.has(id),
  );

  const category = resolved.category as CategoryKey | undefined;
  const categoryForcesReview =
    category !== undefined && !BEHAVIORAL_CATEGORIES.has(category);

  // Finding #5: review_gate now persists the sorted, comma-joined set of
  // selected item keys ("none" mutually exclusive with any real flag) —
  // anything other than exactly "none" forces review, not just the
  // literal old "flagged" sentinel.
  const reviewGateFlagged =
    resolved.review_gate !== undefined && resolved.review_gate !== "none";

  if (
    laneForcesReview ||
    unsureForcesReview ||
    categoryForcesReview ||
    reviewGateFlagged
  ) {
    return {
      state: "HUMAN_REVIEW_REQUIRED",
      candidates: [],
      assumptions,
      pathsRemaining: paths,
    };
  }

  if (!isComplete(resolved)) {
    return {
      state: "NEEDS_INPUT",
      candidates: [],
      assumptions,
      pathsRemaining: paths,
    };
  }

  // Named, honest limitation of the prototype — not a legal gate. See
  // design doc §4 outcome-copy skeletons: "no invented dates, no 'coming
  // soon' theatre."
  if (category === "tourism" && resolved.tourism_duration === "extended") {
    return {
      state: "TEMPORARILY_UNAVAILABLE",
      candidates: [],
      assumptions,
      pathsRemaining: paths,
    };
  }

  if (candidatesSoFar.length === 0) {
    return {
      state: "NO_SUPPORTED_PATH",
      candidates: [],
      assumptions,
      pathsRemaining: 0,
      alternativeCategories: alternativesFor(category),
    };
  }

  const eligibilityRank: Record<EligibilityState, number> = {
    eligible: 0,
    likely: 1,
    conditional: 2,
    "likely-not": 3,
  };
  const ranked: EvaluatedCandidate[] = candidatesSoFar
    .map((card) => ({
      ...card,
      eligibility: adjustEligibility(card, resolved),
    }))
    .sort((a, b) => {
      // Finding #3: in the "bridging" lane, Bridging Visa ranks first —
      // it's the time-critical path, regardless of its base eligibility
      // tier.
      if (lane === "bridging") {
        if (a.code === "BRIDGING" && b.code !== "BRIDGING") return -1;
        if (b.code === "BRIDGING" && a.code !== "BRIDGING") return 1;
      }
      return eligibilityRank[a.eligibility] - eligibilityRank[b.eligibility];
    });

  return {
    state: "SUPPORTED_CANDIDATES",
    candidates: ranked,
    assumptions,
    pathsRemaining: ranked.length,
  };
}

function alternativesFor(category: CategoryKey | undefined): CategoryKey[] {
  if (category === "work") return ["remote", "business", "other"];
  return CATEGORY_KEYS.filter((c) => c !== category).slice(0, 3);
}
