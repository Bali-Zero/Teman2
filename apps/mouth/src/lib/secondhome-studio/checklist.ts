/**
 * Second Home Studio — the 10-item readiness checklist (spec §5).
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
    id: "passport_validity",
    titleKey: "checklist.items.passportValidity.title",
    whyKey: "checklist.items.passportValidity.why",
  },
  {
    id: "passport_scan",
    titleKey: "checklist.items.passportScan.title",
    whyKey: "checklist.items.passportScan.why",
  },
  {
    id: "proof_of_funds",
    titleKey: "checklist.items.proofOfFunds.title",
    whyKey: "checklist.items.proofOfFunds.why",
  },
  {
    id: "personal_statement",
    titleKey: "checklist.items.personalStatement.title",
    whyKey: "checklist.items.personalStatement.why",
  },
  {
    id: "photos",
    titleKey: "checklist.items.photos.title",
    whyKey: "checklist.items.photos.why",
  },
  {
    id: "address_abroad",
    titleKey: "checklist.items.addressAbroad.title",
    whyKey: "checklist.items.addressAbroad.why",
  },
  {
    id: "health_insurance",
    titleKey: "checklist.items.healthInsurance.title",
    whyKey: "checklist.items.healthInsurance.why",
  },
  {
    id: "family_documents",
    titleKey: "checklist.items.familyDocuments.title",
    whyKey: "checklist.items.familyDocuments.why",
  },
  {
    id: "travel_plan",
    titleKey: "checklist.items.travelPlan.title",
    whyKey: "checklist.items.travelPlan.why",
  },
  {
    id: "deposit_source",
    titleKey: "checklist.items.depositSource.title",
    whyKey: "checklist.items.depositSource.why",
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
