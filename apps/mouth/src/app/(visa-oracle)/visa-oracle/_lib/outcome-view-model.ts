/**
 * Presentation-only contract for Visa Oracle.
 *
 * The deterministic engine owns state, candidate membership and ordering.
 * This module deliberately contains no evaluator and no rule logic: adapters
 * may translate a verified backend response (or an explicit preview fixture)
 * into this shape, while presentational components render it without knowing
 * where it came from.
 */

import type { CategoryKey } from "./tree";

export type OutcomeState =
  | "SUPPORTED_CANDIDATES"
  | "NEEDS_INPUT"
  | "HUMAN_REVIEW_REQUIRED"
  | "NO_SUPPORTED_PATH"
  | "TEMPORARILY_UNAVAILABLE";

/** Makes a real engine decision visibly distinguishable from local safety
 * abstentions, transport failures, public shadow verification and developer
 * previews. Every non-ENGINE origin must carry zero candidates. */
export type OutcomeOrigin =
  | { provenance: "ENGINE"; assessment: OutcomeAssessment }
  | {
      provenance: "CLIENT_GUARD" | "NETWORK_FAILURE" | "SHADOW" | "PREVIEW";
      assessment: null;
    };

/** Copy supplied by the adapter, kept co-first-class for EN and ID. */
export interface LocalizedText {
  en: string;
  id: string;
}

export type SourceFreshness = "CURRENT" | "STALE" | "UNKNOWN";

export interface OutcomeSource {
  id: string;
  title: string;
  publisher: string;
  url: string;
  authority: string;
  /** A decisive source must be primary. Secondary context may be displayed
   * but must never support a recommendation. */
  primary: boolean;
  effectiveAtIso: string;
  observedAtIso: string;
  freshness: SourceFreshness;
}

/** A stable reason code plus display copy and joinable source references. */
export interface OutcomeReason {
  code: string;
  message: LocalizedText;
  sourceIds: readonly string[];
}

export interface InterviewAssumption {
  id: string;
  questionId: string;
  message?: LocalizedText;
  assumedValue?: LocalizedText;
  editable: boolean;
}

export interface OutcomeMissingInput extends OutcomeReason {
  /** Present when the missing engine fact maps to a question the interview
   * can reopen. Omitted facts require a human handoff instead of a fake field. */
  questionId?: string;
  /**
   * `true` when `questionId` names a question this interview has NOT yet
   * asked (added 2026-09-06). The two cases must not be conflated in the
   * UI: an ALREADY-ASKED question is reopened by truncating history back to
   * it (destructive — every answer after it is discarded), while a
   * never-asked one is APPENDED to the interview and nothing is lost. Only
   * ever set alongside `questionId`.
   */
  followUp?: true;
}

export type LegalSupportStatus =
  "SUPPORTED" | "CONDITIONAL" | "NOT_SUPPORTED" | "UNKNOWN";

export type OperationalAvailabilityStatus =
  "AVAILABLE" | "TEMPORARILY_UNAVAILABLE" | "UNKNOWN";

export type ServiceAvailabilityStatus =
  "AVAILABLE" | "CONTACT_REQUIRED" | "NOT_OFFERED" | "UNKNOWN";

export interface OutcomeStatusAxis<Status extends string> {
  status: Status;
  reasons: readonly OutcomeReason[];
}

export type OutcomePrice =
  | {
      status: "AVAILABLE";
      currency: "IDR";
      /** Whole IDR amount returned by PricingTool. */
      amount: number;
      allInclusive: true;
      quotedAtIso: string;
      validUntilIso?: string;
    }
  | {
      status: "CONTACT_REQUIRED" | "UNAVAILABLE";
      message: LocalizedText;
    };

export type OutcomeTimeline =
  | {
      status: "AVAILABLE";
      /** Assessment clock used to derive the two calendar dates. */
      basisDateIso: string;
      earliestDateIso: string;
      latestDateIso: string;
      note?: LocalizedText;
    }
  | {
      status: "CONTACT_REQUIRED" | "UNAVAILABLE";
      message: LocalizedText;
    };

export interface OutcomeDocument {
  id: string;
  label: LocalizedText;
  status: "REQUIRED" | "CONDITIONAL" | "UNKNOWN";
  sourceIds: readonly string[];
}

export interface OutcomeCandidate {
  id: string;
  code: string;
  rank: number;
  name: LocalizedText;
  tagline?: LocalizedText;
  /** These three axes must never be collapsed into one badge. */
  legal: OutcomeStatusAxis<LegalSupportStatus>;
  operational: OutcomeStatusAxis<OperationalAvailabilityStatus>;
  service: OutcomeStatusAxis<ServiceAvailabilityStatus>;
  decisionReasons: readonly OutcomeReason[];
  timeline: OutcomeTimeline;
  price: OutcomePrice;
  documents: readonly OutcomeDocument[];
}

export interface OutcomeStep {
  id: string;
  title: LocalizedText;
  body?: LocalizedText;
}

export type OutcomeNextSteps = readonly [OutcomeStep, OutcomeStep, OutcomeStep];

export interface OutcomeAssessment {
  publicId?: string;
  effectiveAtIso: string;
  observedAtIso: string;
  evaluatedAtIso: string;
  ruleset?: {
    id: string;
    version: string;
    sequence: number;
  };
}

interface OutcomeBase {
  state: OutcomeState;
  pathsRemaining: number;
  assumptions: readonly InterviewAssumption[];
  sources: readonly OutcomeSource[];
  nextSteps: OutcomeNextSteps;
}

export type SupportedCandidatesOutcome = OutcomeBase &
  OutcomeOrigin & {
    state: "SUPPORTED_CANDIDATES";
    candidates: readonly [OutcomeCandidate, ...OutcomeCandidate[]];
  };

export type NeedsInputOutcome = OutcomeBase &
  OutcomeOrigin & {
    state: "NEEDS_INPUT";
    candidates: readonly [];
    missingInputs: readonly [OutcomeMissingInput, ...OutcomeMissingInput[]];
  };

export type HumanReviewOutcome = OutcomeBase &
  OutcomeOrigin & {
    state: "HUMAN_REVIEW_REQUIRED";
    candidates: readonly [];
    reviewReasons: readonly [OutcomeReason, ...OutcomeReason[]];
  };

export interface NoSupportedPathAlternative {
  category: CategoryKey;
  message?: LocalizedText;
}

export type NoSupportedPathOutcome = OutcomeBase &
  OutcomeOrigin & {
    state: "NO_SUPPORTED_PATH";
    candidates: readonly [];
    noPathReasons: readonly [OutcomeReason, ...OutcomeReason[]];
    alternatives: readonly NoSupportedPathAlternative[];
  };

export type TemporarilyUnavailableOutcome = OutcomeBase &
  OutcomeOrigin & {
    state: "TEMPORARILY_UNAVAILABLE";
    candidates: readonly [];
    outage: {
      code: string;
      message: LocalizedText;
      retryable: boolean;
    };
  };

export type OutcomeViewModel =
  | SupportedCandidatesOutcome
  | NeedsInputOutcome
  | HumanReviewOutcome
  | NoSupportedPathOutcome
  | TemporarilyUnavailableOutcome;

export function localized(text: LocalizedText, language: "en" | "id"): string {
  return text[language];
}
