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
 */

import type { PlanState } from "./types";

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

/** N-of-10 readiness meter. Never interpreted as approval likelihood. */
export function readiness(p: PlanState): { done: number; total: number } {
  const total = CHECKLIST_ITEMS.length;
  const done = CHECKLIST_ITEMS.reduce(
    (acc, item) => acc + (p.checklist[item.id] ? 1 : 0),
    0,
  );
  return { done, total };
}
