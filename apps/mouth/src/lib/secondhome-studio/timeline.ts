/**
 * Second Home Studio — the 7-step public timeline (spec §5).
 *
 * Every step carries an owner tag (You / Bali Zero / Imigrasi) and a range
 * label that is explicitly "typical, not a promise" — no promised dates
 * anywhere. `location` changes the documents-gathering range (logistics
 * differ abroad vs. already-in-Indonesia); `horizon` changes the pace note
 * attached to that same first step (how urgently the client should move,
 * never how fast Imigrasi processes the file).
 *
 * `route`/`product` (P1-C9, optional — default preserves the original
 * always-bank-deposit shape) make the SECOND step honest about what the
 * applicant actually needs to do: the bank-deposit step used to render
 * unconditionally, telling a property applicant or an E33F (income-only,
 * explicitly "without the deposit") applicant to "open the account and
 * place the deposit" — instructions for evidence they were never asked
 * for. `route === "property"` swaps it for a property-evidence step;
 * `product === "E33F"` swaps it for an income-evidence step; every other
 * case (including E33E, which DOES keep the 50k deposit) keeps the
 * original bank-deposit step unchanged.
 */

import type { Location, RouteIntent, TimelineHorizon, Verdict } from "./types";

export type TimelineStepId =
  | "documents"
  | "bank_deposit"
  | "property_evidence"
  | "income_evidence"
  | "filing"
  | "imigrasi_processing"
  | "entry_activation"
  | "first_90_days"
  | "annual_life";

export type TimelineOwner = "you" | "balizero" | "imigrasi";

export interface TimelineStep {
  id: TimelineStepId;
  ownerKey: TimelineOwner;
  titleKey: string;
  rangeKey: string;
  /** Only present on the documents step — varies by `horizon`. */
  paceNoteKey?: string;
}

export function buildTimeline(
  horizon: TimelineHorizon,
  location: Location,
  route: RouteIntent | null = null,
  product: Verdict["product"] = null,
): TimelineStep[] {
  const documentsRangeKey =
    location === "abroad"
      ? "timeline.steps.documents.range.abroad"
      : "timeline.steps.documents.range.local";

  const documentsPaceKey = `timeline.steps.documents.pace.${horizon}`;

  // P1-C9: the second step is branch-aware. Property route always wins
  // (it never has a bank deposit at all); E33F (income-only) swaps the
  // deposit step for an income-evidence step; every other case — including
  // deposit/unsure under-55, the 60+ base-deposit fallthrough, and E33E
  // (which keeps its 50k deposit) — reuses the original bank-deposit step
  // unchanged.
  const fundingStep: TimelineStep =
    route === "property"
      ? {
          id: "property_evidence",
          ownerKey: "you",
          titleKey: "timeline.steps.propertyEvidence.title",
          rangeKey: "timeline.steps.propertyEvidence.range",
        }
      : product === "E33F"
        ? {
            id: "income_evidence",
            ownerKey: "you",
            titleKey: "timeline.steps.incomeEvidence.title",
            rangeKey: "timeline.steps.incomeEvidence.range",
          }
        : {
            id: "bank_deposit",
            ownerKey: "you",
            titleKey: "timeline.steps.bankDeposit.title",
            rangeKey: "timeline.steps.bankDeposit.range",
          };

  return [
    {
      id: "documents",
      ownerKey: "you",
      titleKey: "timeline.steps.documents.title",
      rangeKey: documentsRangeKey,
      paceNoteKey: documentsPaceKey,
    },
    fundingStep,
    {
      id: "filing",
      ownerKey: "balizero",
      titleKey: "timeline.steps.filing.title",
      rangeKey: "timeline.steps.filing.range",
    },
    {
      id: "imigrasi_processing",
      ownerKey: "imigrasi",
      titleKey: "timeline.steps.imigrasiProcessing.title",
      rangeKey: "timeline.steps.imigrasiProcessing.range",
    },
    {
      id: "entry_activation",
      ownerKey: "you",
      titleKey: "timeline.steps.entryActivation.title",
      rangeKey: "timeline.steps.entryActivation.range",
    },
    {
      id: "first_90_days",
      ownerKey: "balizero",
      titleKey: "timeline.steps.first90Days.title",
      rangeKey: "timeline.steps.first90Days.range",
    },
    {
      id: "annual_life",
      ownerKey: "you",
      titleKey: "timeline.steps.annualLife.title",
      rangeKey: "timeline.steps.annualLife.range",
    },
  ];
}
