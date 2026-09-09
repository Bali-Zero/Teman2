import type { OutcomeReason } from "./outcome-view-model";

// Presentation only: codes whose public copy describes the facts tested by a
// matching rule. Everything else remains visible as conditions/rule context.
// Do not infer semantics from prose or change candidate membership or ordering.
const MATCH_CODES = new Set([
  "A1_BVK_ELIGIBLE", "B1_VOA_ELIGIBLE", "C1_VISIT_ELIGIBLE",
  "C2_BUSINESS_ELIGIBLE", "C6_SOCIAL_ELIGIBLE", "E28A_INVESTMENT_ELIGIBLE",
  "E33E_RETIREMENT_ELIGIBLE", "E33F_RETIREMENT_ELIGIBLE",
  "E33_DEPOSIT_BASIS_ELIGIBLE", "E33_PROPERTY_BASIS_ELIGIBLE",
  "REMOTE_WORK_ELIGIBLE", "BRIDGING_DESTINATION_STATED", "PURPOSE_PRODUCT_MATCH",
]);

export function partitionCandidateReasons(reasons: readonly OutcomeReason[]) {
  return {
    matches: reasons.filter((reason) => MATCH_CODES.has(reason.code)),
    conditions: reasons.filter((reason) => !MATCH_CODES.has(reason.code)),
  };
}
