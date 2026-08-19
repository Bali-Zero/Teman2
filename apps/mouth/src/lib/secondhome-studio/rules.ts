/**
 * Second Home Studio — deterministic fit rules.
 *
 * Pure function, PINNED by rules.test.ts against every row of
 * SPEC-secondhome-studio-phaseB.md §3's decision table (checked in priority
 * order, top to bottom — the first matching row wins).
 *
 * Facts used are CONFIRMED registry facts only: USD 130k own-name BUMN
 * deposit OR USD 1M completed strata; E33E 55+ = USD 50k deposit + USD
 * 3k/mo income, 5y; E33F 55+ = USD 3k/mo income only, 1y, 6y cap; base
 * first grant up to 5y (Pasal 113 caps). Nothing else asserted.
 *
 * `reasons` and `humanReviewNote` are COPY KEYS (dot-paths into
 * `copy.ts`'s COPY object), never free strings — `REASON_KEYS` below is the
 * single source of truth for that vocabulary, kept in sync with
 * `copy.ts`'s `verdict.reasons` / `verdict.humanReview` trees (drift is
 * caught by rules.test.ts resolving every key through `getCopy`).
 */

import type { PlanState, Verdict, VerdictBand } from "./types";

export const REASON_KEYS = {
  propertyPendingStandard: "verdict.reasons.propertyPendingStandard",
  propertyDoesNotQualify: "verdict.reasons.propertyDoesNotQualify",
  unsureRoute: "verdict.reasons.unsureRoute",
  seniorBersyarat: "verdict.reasons.seniorBersyarat",
  seniorFundingUnclear: "verdict.reasons.seniorFundingUnclear",
  seniorDepositStrong: "verdict.reasons.seniorDepositStrong",
  seniorIncomeOnlyStrong: "verdict.reasons.seniorIncomeOnlyStrong",
  depositReadyStrong: "verdict.reasons.depositReadyStrong",
  capitalCloseVerify: "verdict.reasons.capitalCloseVerify",
  capitalBelowThreshold: "verdict.reasons.capitalBelowThreshold",
  seniorRoutesExistNote: "verdict.reasons.seniorRoutesExistNote",
  incompleteAnswers: "verdict.reasons.incompleteAnswers",
} as const;

export const HUMAN_REVIEW_KEYS = {
  age5559Disclosure: "verdict.humanReview.age5559Disclosure",
} as const;

function edgeCaseIncomplete(reasons: string[] = []): Verdict {
  return {
    band: "edge_case",
    product: null,
    reasons: [...reasons, REASON_KEYS.incompleteAnswers],
    humanReviewNote: null,
  };
}

/** Rows 2-4 (and the 60_plus/neither fallthrough of row 6): evaluate the
 *  base E33 deposit route purely from the capital band. */
function evaluateDepositCapital(
  capital: PlanState["capital"],
  reasons: string[],
): Verdict {
  if (capital === null) return edgeCaseIncomplete(reasons);

  if (capital === "ready_130k") {
    return {
      band: "strong_fit",
      product: "E33",
      reasons: [...reasons, REASON_KEYS.depositReadyStrong],
      humanReviewNote: null,
    };
  }

  if (capital === "close_100k_130k") {
    return {
      band: "likely_fit",
      product: "E33",
      reasons: [...reasons, REASON_KEYS.capitalCloseVerify],
      humanReviewNote: null,
    };
  }

  // below_100k
  return {
    band: "not_eligible",
    product: null,
    reasons: [
      ...reasons,
      REASON_KEYS.capitalBelowThreshold,
      REASON_KEYS.seniorRoutesExistNote,
    ],
    humanReviewNote: null,
  };
}

export function evaluatePlan(p: PlanState): Verdict {
  // Globally required answers (row 7 backstop) — age and route are asked
  // first in the wizard flow and gate every other question.
  if (p.age === null || p.route === null) {
    return edgeCaseIncomplete();
  }

  // Row 1 (highest priority, independent of age): the property route is
  // ALWAYS edge_case — never a green "qualified", honest pending-standard
  // note always present, plus a does-not-qualify reason for the property
  // statuses that never qualify regardless of validation outcome.
  if (p.route === "property") {
    if (p.property === null) return edgeCaseIncomplete();

    const reasons: string[] = [REASON_KEYS.propertyPendingStandard];
    if (p.property === "villa_land_leasehold" || p.property === "none") {
      reasons.push(REASON_KEYS.propertyDoesNotQualify);
    }

    return {
      band: "edge_case",
      product: null,
      reasons,
      humanReviewNote: null,
    };
  }

  // Row 8: route=unsure is evaluated as deposit, with an extra reason and
  // (component-level) a prominent RouteComparator. The reason is prepended
  // so it always appears first in the returned array below.
  const reasons: string[] = [];
  if (p.route === "unsure") {
    reasons.push(REASON_KEYS.unsureRoute);
  }

  // Row 5: age 55-59 is ALWAYS edge_case (BERSYARAT), whatever the funding.
  if (p.age === "55_59") {
    if (p.seniorFunding === null) return edgeCaseIncomplete(reasons);

    const product =
      p.seniorFunding === "deposit_50k_income"
        ? "E33E"
        : p.seniorFunding === "income_only_3k"
          ? "E33F"
          : null;

    const bandReasons = [...reasons, REASON_KEYS.seniorBersyarat];
    if (product === null) {
      bandReasons.push(REASON_KEYS.seniorFundingUnclear);
    }

    return {
      band: "edge_case",
      product,
      reasons: bandReasons,
      humanReviewNote: HUMAN_REVIEW_KEYS.age5559Disclosure,
    };
  }

  // Row 6: age 60_plus.
  if (p.age === "60_plus") {
    if (p.seniorFunding === null) return edgeCaseIncomplete(reasons);

    if (p.seniorFunding === "deposit_50k_income") {
      return {
        band: "strong_fit",
        product: "E33E",
        reasons: [...reasons, REASON_KEYS.seniorDepositStrong],
        humanReviewNote: null,
      };
    }

    if (p.seniorFunding === "income_only_3k") {
      return {
        band: "strong_fit",
        product: "E33F",
        reasons: [...reasons, REASON_KEYS.seniorIncomeOnlyStrong],
        humanReviewNote: null,
      };
    }

    // "neither" or "not_applicable" falls through to the base E33 deposit
    // rows (a 60+ can still take the base route with the full 130k).
    return evaluateDepositCapital(p.capital, reasons);
  }

  // age === "under_55": rows 2-4, driven purely by capital.
  return evaluateDepositCapital(p.capital, reasons);
}

/** Convenience re-export for callers that want the literal band list. */
export const VERDICT_BANDS: readonly VerdictBand[] = [
  "strong_fit",
  "likely_fit",
  "edge_case",
  "not_eligible",
];
