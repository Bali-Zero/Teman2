/**
 * Second Home Studio — the 10-item readiness checklist.
 *
 * Item content sourced from the copy deck's "DOCUMENT READINESS" section
 * (COPY-DECK-studio.md §5) — supersedes the original spec-sketch list
 * (flagged in the delivery report): the deck's list is route-complete,
 * covering property-route and senior-income-route evidence the original
 * sketch omitted. `PlanState.checklist` is a free-form `Record<string,
 * boolean>` (not a frozen enum), so swapping item ids/content here does
 * not touch the frozen types.ts contract.
 *
 * Checkboxes only, no uploads. Progress is a "readiness meter" — copy
 * always frames this as preparation, never approval likelihood.
 *
 * ROUTE-AWARE CLASSIFICATION (measured defect, three production walks): the
 * ten items are a UNION across every E33/E33E/E33F route, kept deliberately
 * — a user who never sees an item may not prepare something they end up
 * needing. The defect was presenting that union as if it were the
 * visitor's PERSONAL list, with a "0 of 10" meter every route showed
 * identically even though 2-3 of the ten provably cannot apply to what the
 * user just answered.
 *
 * `classifyChecklistItem` splits the union into "applies"/"may_apply"
 * WITHOUT hiding or deleting anything — both groups stay rendered and
 * tickable. `readiness` then counts only the applicable group, so its
 * denominator is honestly reachable.
 *
 * Safety rule: an item is "may_apply" ONLY when the plan's answers make it
 * DEFINITIVELY inapplicable — route=property and route=unsure/55-59
 * ambiguity always widen, never narrow. See `resolveRouteBucket` for the
 * exact precedence, grounded in the fact registry (/secondhome corner §2)
 * and the wizard's branch structure (sequence.ts: property is structurally
 * exclusive of deposit/senior; "unsure" is scored as deposit for
 * verdict/price purposes only, never a confirmed route commitment).
 */

import type { PlanState, Verdict } from "./types";

export interface ChecklistItem {
  id: string;
  titleKey: string;
  whyKey: string;
}

export const CHECKLIST_ITEMS: readonly ChecklistItem[] = [
  {
    id: "passport_bio_page",
    titleKey: "checklist.items.passportBioPage.title",
    whyKey: "checklist.items.passportBioPage.why",
  },
  {
    id: "passport_validity",
    titleKey: "checklist.items.passportValidity.title",
    whyKey: "checklist.items.passportValidity.why",
  },
  {
    id: "passport_photo",
    titleKey: "checklist.items.passportPhoto.title",
    whyKey: "checklist.items.passportPhoto.why",
  },
  {
    id: "residential_address",
    titleKey: "checklist.items.residentialAddress.title",
    whyKey: "checklist.items.residentialAddress.why",
  },
  {
    id: "personal_history",
    titleKey: "checklist.items.personalHistory.title",
    whyKey: "checklist.items.personalHistory.why",
  },
  {
    id: "bank_deposit_evidence",
    titleKey: "checklist.items.bankDepositEvidence.title",
    whyKey: "checklist.items.bankDepositEvidence.why",
  },
  {
    id: "passive_income_evidence",
    titleKey: "checklist.items.passiveIncomeEvidence.title",
    whyKey: "checklist.items.passiveIncomeEvidence.why",
  },
  {
    id: "property_documents",
    titleKey: "checklist.items.propertyDocuments.title",
    whyKey: "checklist.items.propertyDocuments.why",
  },
  {
    id: "family_records",
    titleKey: "checklist.items.familyRecords.title",
    whyKey: "checklist.items.familyRecords.why",
  },
  {
    id: "existing_visa_permit",
    titleKey: "checklist.items.existingVisaPermit.title",
    whyKey: "checklist.items.existingVisaPermit.why",
  },
];

export type ChecklistApplicability = "applies" | "may_apply";

type RouteBucket =
  | "property" // base E33 property route — structurally exclusive of deposit/senior
  | "seniorDeposit" // E33E: USD 50k deposit + USD 3k/mo income
  | "seniorIncome" // E33F: USD 3k/mo income only, no deposit
  | "baseDeposit" // base E33 deposit route
  | "unresolved"; // route/age ambiguous or answers incomplete — never narrow

/**
 * Resolves which route family THIS plan's answers definitively commit to,
 * or "unresolved" when they don't — the single place the fail-safe lives.
 *
 * Order matters:
 * 1. Missing age/route -> unresolved (never narrow on an absent answer).
 * 2. route="property" -> "property", REGARDLESS of age. Property is a
 *    structurally separate wizard branch (sequence.ts never asks
 *    seniorFunding/capital once route=property) and neither senior product
 *    (E33E/E33F) has a property variant in the fact registry — so a
 *    property answer is definitive independent of the 55-59 ambiguity below.
 * 3. route="unsure" -> unresolved. evaluatePlan() scores "unsure" AS IF it
 *    were the deposit route so it can still show a verdict/price, but that
 *    is a scoring convenience, not a confirmed deposit-vs-property choice —
 *    narrowing on it would tell a user who never picked a route that a
 *    property document does not apply to them.
 * 4. age="55_59" -> unresolved. BERSYARAT (fact registry §2 disputed age
 *    band): both the base route and the senior products remain open for
 *    this band regardless of which seniorFunding was answered.
 * 5. Otherwise, narrow on the computed verdict.product (E33E/E33F/E33).
 * 6. product=null with none of the above (incomplete answers, or 60+ with
 *    seniorFunding genuinely unresolved) -> unresolved.
 */
function resolveRouteBucket(plan: PlanState, verdict: Verdict): RouteBucket {
  if (plan.age == null || plan.route == null) return "unresolved";
  if (plan.route === "property") return "property";
  if (plan.route === "unsure") return "unresolved";
  if (plan.age === "55_59") return "unresolved";

  if (verdict.product === "E33E") return "seniorDeposit";
  if (verdict.product === "E33F") return "seniorIncome";
  if (verdict.product === "E33") return "baseDeposit";
  return "unresolved";
}

function hasFamilyMembers(family: PlanState["family"]): boolean {
  return family.spouse || family.children > 0 || family.parents > 0;
}

/**
 * Classifies one checklist item against THIS plan's answers. Never returns
 * anything but "applies" for the six route-independent items (passport bio
 * page, passport validity, passport photo, residential address, personal
 * history, existing visa/permit) — only the three route-conditioned items
 * and `family_records` can ever read "may_apply".
 */
export function classifyChecklistItem(
  itemId: string,
  plan: PlanState,
  verdict: Verdict,
): ChecklistApplicability {
  if (itemId === "family_records") {
    return hasFamilyMembers(plan.family) ? "applies" : "may_apply";
  }

  const bucket = resolveRouteBucket(plan, verdict);
  if (bucket === "unresolved") return "applies";

  switch (itemId) {
    case "bank_deposit_evidence":
      // Required on base E33 deposit route + E33E. Not on property (no
      // deposit route was taken) or E33F (income only, no deposit).
      return bucket === "property" || bucket === "seniorIncome"
        ? "may_apply"
        : "applies";
    case "passive_income_evidence":
      // Required on E33E and E33F only — base E33 has no income test,
      // on either route.
      return bucket === "seniorDeposit" || bucket === "seniorIncome"
        ? "applies"
        : "may_apply";
    case "property_documents":
      // Required on the base E33 property route only.
      return bucket === "property" ? "applies" : "may_apply";
    default:
      return "applies";
  }
}

/**
 * N-of-M readiness meter. M is the count of items classified "applies" for
 * THIS plan — never the full 10 — so the denominator is honestly reachable;
 * an item classified "may_apply" is still rendered and tickable, but never
 * counted toward the meter, so `done` can never exceed `total`. Never
 * interpreted as approval likelihood.
 */
export function readiness(
  plan: PlanState,
  verdict: Verdict,
): { done: number; total: number } {
  const applicable = CHECKLIST_ITEMS.filter(
    (item) => classifyChecklistItem(item.id, plan, verdict) === "applies",
  );
  const total = applicable.length;
  const done = applicable.reduce(
    (acc, item) => acc + (plan.checklist[item.id] ? 1 : 0),
    0,
  );
  return { done, total };
}
