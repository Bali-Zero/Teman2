import {
  FORBIDDEN_PATTERNS,
  JSX_PRICE_LITERAL_RE,
  PRICE_LITERAL_PATTERN,
} from "@/lib/secondhome-studio/claim-patterns";
import { E33_FACTS, type E33Fact } from "../data/e33-facts";

/**
 * Which registry facts the Facts drawer may put on the shelf, and in which
 * group. The registry itself (`../data/e33-facts.ts`) is a verbatim copy and
 * is never edited to make a fact fit; the decision lives here, in three
 * gates applied in order:
 *
 *  1. STATUS — `confirmed` and `pending` only. `disputed` and `unknown` stay
 *     off the shelf (BRIEF-v2 §3.2); pending facts are labelled as open.
 *  2. THE CLAIM GUARD — the Studio's own forbidden-claims patterns
 *     (`claim-patterns.ts`, the same regexes the copy sweep runs) plus both
 *     IDR price-literal patterns, over every string the drawer renders
 *     (topic + value). A fact that trips one is withheld whole: the guard
 *     is never loosened for a fact, and a fact is never paraphrased to pass.
 *  3. EDITORIAL HOLDS — named below with the reason, for facts that pass the
 *     regexes but restate a guarded concept under another name.
 *
 * `notes` and `source` are research-internal (letter numbers, pipeline
 * names) and are never rendered.
 */
export type ShelfGroup = "basis" | "senior" | "family" | "bank" | "stay";

export const SHELF_GROUP_ORDER: readonly ShelfGroup[] = [
  "basis",
  "senior",
  "family",
  "bank",
  "stay",
];

/** Presentation grouping by fact id — the registry carries no category. */
export const FACT_GROUP: Record<string, ShelfGroup> = {
  e33_base_deposit_amount: "basis",
  e33_base_property_alternative: "basis",
  e33_base_property_title_type: "basis",
  e33_first_grant_duration: "basis",
  e33_not_work_visa: "basis",
  pasal_113_cumulative_caps: "basis",
  e33e_requirements: "senior",
  e33f_requirements: "senior",
  age_55_59_ambiguity_e33e: "senior",
  e33f_family_inclusion: "family",
  e33f_sponsor_requirement: "senior",
  dependent_spouse_code_e31b: "family",
  dependent_codes_confirmation: "family",
  pnbp_5y_amount: "stay",
  pnbp_5y_amount_and_refundability: "stay",
  entry_window_90d_and_force_majeure: "stay",
  itap_after_3y_criteria: "stay",
  processing_time_4wd: "stay",
  basis_switch_deposit_property_mid_permit: "basis",
  bank_proof_format: "bank",
  bsi_sharia_accepted: "bank",
  split_deposit_accepted: "bank",
  annual_maintenance_proof_and_fx_grace: "bank",
  bank_kyc_nonresident: "bank",
  bank_confirmation_letter_format_and_timing: "bank",
  bank_split_placement_operations: "bank",
  usd_deposit_rates_and_lps_cap_confirmation: "bank",
  bank_annual_proof_documents: "bank",
  fund_release_process: "bank",
  bank_liaison_contact: "bank",
  blocked_deposit_requirement: "bank",
  remote_account_opening: "bank",
  idr_equivalence_and_fx_date: "bank",
  property_validation_standard: "basis",
};

/** Gate 3. Each entry passes the regexes and is still held, for the reason given. */
export const EDITORIAL_HOLDS: Record<string, string> = {
  bank_split_placement_operations:
    "split placement is the split-deposit question under another name (copy.ts hard rule: no split-deposit phrasing)",
  processing_time_4wd:
    "a processing time is never shown on a funnel, not even as an open question (BRIEF-v2 §2.7)",
};

const SHELF_PATTERNS: RegExp[] = [
  ...Object.values(FORBIDDEN_PATTERNS),
  JSX_PRICE_LITERAL_RE,
  PRICE_LITERAL_PATTERN,
];

/** The strings the drawer renders for a fact. */
export function renderedFactStrings(fact: E33Fact): string[] {
  return [fact.topic, fact.value];
}

export function tripsClaimGuard(text: string): boolean {
  return SHELF_PATTERNS.some((pattern) => pattern.test(text));
}

export type ShelfDecision =
  | { shown: true }
  | { shown: false; reason: "status" | "claim-guard" | "editorial" };

export function decideFact(fact: E33Fact): ShelfDecision {
  if (fact.status !== "confirmed" && fact.status !== "pending") {
    return { shown: false, reason: "status" };
  }
  if (renderedFactStrings(fact).some(tripsClaimGuard)) {
    return { shown: false, reason: "claim-guard" };
  }
  if (Object.prototype.hasOwnProperty.call(EDITORIAL_HOLDS, fact.id)) {
    return { shown: false, reason: "editorial" };
  }
  return { shown: true };
}

export interface ShelfFactGroup {
  group: ShelfGroup;
  facts: E33Fact[];
}

/** Shelf order: group order, then confirmed before pending, registry order within. */
export function shelfFacts(
  facts: readonly E33Fact[] = E33_FACTS,
): ShelfFactGroup[] {
  const shown = facts.filter((fact) => decideFact(fact).shown);
  return SHELF_GROUP_ORDER.map((group) => ({
    group,
    facts: shown
      .filter((fact) => (FACT_GROUP[fact.id] ?? "stay") === group)
      .sort(
        (a, b) =>
          Number(a.status !== "confirmed") - Number(b.status !== "confirmed"),
      ),
  })).filter((entry) => entry.facts.length > 0);
}
