/**
 * Second Home Studio — the 7-step public timeline (spec §5).
 *
 * Every step carries an owner tag (You / Bali Zero / Imigrasi) and a range
 * label that is explicitly "typical, not a promise" — no promised dates
 * anywhere. `location` changes the documents-gathering range (logistics
 * differ abroad vs. already-in-Indonesia); `horizon` changes the pace note
 * attached to that same first step (how urgently the client should move,
 * never how fast Imigrasi processes the file).
 */

import type { Location, TimelineHorizon } from "./types";

export type TimelineStepId =
  | "documents"
  | "bank_deposit"
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
): TimelineStep[] {
  const documentsRangeKey =
    location === "abroad"
      ? "timeline.steps.documents.range.abroad"
      : "timeline.steps.documents.range.local";

  const documentsPaceKey = `timeline.steps.documents.pace.${horizon}`;

  return [
    {
      id: "documents",
      ownerKey: "you",
      titleKey: "timeline.steps.documents.title",
      rangeKey: documentsRangeKey,
      paceNoteKey: documentsPaceKey,
    },
    {
      id: "bank_deposit",
      ownerKey: "you",
      titleKey: "timeline.steps.bankDeposit.title",
      rangeKey: "timeline.steps.bankDeposit.range",
    },
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
