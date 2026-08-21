/**
 * Second Home Studio — the wizard question sequence (spec §4), hoisted out
 * of StudioApp so it is the SINGLE source of truth for "which questions are
 * reachable from the current plan" (P2-6/P1-C8/P0-C3 fix-mandate round 1).
 *
 * Question order: age -> route -> [deposit/unsure? capital] ->
 * [55+? seniorFunding] -> [property? property] -> family -> horizon ->
 * location -> VERDICT. The sequence is recomputed from the CURRENT plan on
 * every call (never cached against a stale branch), so answering an earlier
 * question (e.g. switching route from deposit to property, or seniorFunding
 * from "neither" to "income_only_3k") immediately changes what the NEXT
 * step is — no dangling questions from an abandoned branch.
 *
 * `relevantPlan` uses the same sequence to null out any branch-only answer
 * (capital / seniorFunding / property) that is NOT reachable from the
 * current plan — e.g. a `capital` answer left over from a deposit route the
 * user has since switched away from. Every surface that SHARES a plan
 * outside the wizard's own component state (the "copy plan link" fragment,
 * the WhatsApp handoff bullets) must sanitize through this first, so an
 * abandoned-branch answer never leaks into a saved/sent artifact.
 */

import type { PlanState } from "./types";

export type QuestionId =
  | "age"
  | "route"
  | "capital"
  | "seniorFunding"
  | "property"
  | "family"
  | "horizon"
  | "location";

export function computeSequence(p: PlanState): QuestionId[] {
  const seq: QuestionId[] = ["age", "route"];

  if (p.route === "property") {
    seq.push("property");
  } else if (p.age === "55_59") {
    // Row 5 (rules.ts): 55-59 is always edge_case from seniorFunding alone
    // — capital is never consulted for this age band.
    seq.push("seniorFunding");
  } else if (p.age === "60_plus") {
    seq.push("seniorFunding");
    // Row 6 fallthrough: only "neither"/"not_applicable" (or not yet
    // answered) reaches the base deposit rows, so only THEN is capital
    // needed. Once seniorFunding matches a senior product, capital is
    // skipped entirely — this branch re-evaluates every render, so the
    // skip takes effect the moment seniorFunding resolves.
    if (
      p.seniorFunding === null ||
      p.seniorFunding === "neither" ||
      p.seniorFunding === "not_applicable"
    ) {
      seq.push("capital");
    }
  } else {
    // under_55 (or age not yet known — capital is the conservative
    // default until age resolves; by the time we actually reach this
    // position in the sequence, age is always answered for real).
    seq.push("capital");
  }

  seq.push("family", "horizon", "location");
  return seq;
}

/**
 * Nulls every branch-only answer (capital / seniorFunding / property) not
 * reachable in the CURRENT sequence, leaving every other field untouched.
 * Used before sharing a plan OUTSIDE the wizard's own component state (P2-6)
 * — localStorage keeps the raw plan so resuming the wizard never loses an
 * answer the user might switch back to, but a shared link or a WhatsApp
 * handoff should never carry an abandoned branch's stale answer.
 */
export function relevantPlan(p: PlanState): PlanState {
  const reachable = new Set(computeSequence(p));
  return {
    ...p,
    capital: reachable.has("capital") ? p.capital : null,
    seniorFunding: reachable.has("seniorFunding") ? p.seniorFunding : null,
    property: reachable.has("property") ? p.property : null,
  };
}
