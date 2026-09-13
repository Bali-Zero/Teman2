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

/** What a visitor is asked to DO about a named condition. Mirrors the
 * engine's `ConditionNextStep` closed vocabulary one-for-one — a member added
 * on one side and not the other is a type error here, which is the point. */
export type OutcomeConditionNextStep =
  | "ANSWER_AGAIN"
  | "BRING_TO_CONSULTATION"
  | "APPLY_THROUGH_GUARDIAN"
  | "ASSISTED_APPLICATION"
  | "NO_ACTION_NEEDED"
  | "CONSULTANT_REVIEW"
  | "AWAIT_SOURCE_REFRESH";

/**
 * A named condition carried BESIDE a verdict (RULED 2026-09-13).
 *
 * It is an `OutcomeReason` plus a next step, and the extension is deliberate:
 * a condition renders through the SAME `REVIEW_REASON_COPY` table the old
 * human-review sentences used, so every code that already had reviewed EN/ID
 * copy keeps exactly the sentence it had. What the ruling changed is where
 * that sentence appears — under a live verdict instead of instead of one.
 */
export interface OutcomeCondition extends OutcomeReason {
  nextStep: OutcomeConditionNextStep;
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
  /** Named conditions on this verdict. On `OutcomeBase` and not on one state
   * because a condition does not pick a state: the same disclosed health
   * concern conditions a SUPPORTED verdict, a NEEDS_INPUT one and a
   * NO_SUPPORTED_PATH one identically. A held outcome carries one too, so the
   * hold explains itself. */
  conditions: readonly OutcomeCondition[];
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
  /** The interview tile this door belongs to. */
  category: CategoryKey;
  /**
   * The product the signed pack supports behind this door, by code, plus the
   * pack's own name for it. NEVER an adapter's opinion: every code rendered
   * here is one a replay of the signed pack returned for this applicant's own
   * stated facts (`_lib/fixtures/no-path-doors.replay.json`). Optional
   * because a door may still name a category alone.
   */
  productCode?: string;
  productName?: LocalizedText;
  message?: LocalizedText;
  /**
   * `false` when nothing the visitor can answer today opens this door — a
   * fact about the world has to change first (turning 55). Rendered as a
   * sentence and never as a button, because the button would restart an
   * interview that ends in exactly the same place.
   */
  actionable?: boolean;
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
