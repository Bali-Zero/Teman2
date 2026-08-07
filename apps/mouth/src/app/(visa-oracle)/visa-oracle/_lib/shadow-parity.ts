import { buildShadowComparisonOutcome } from "./engine-adapter";
import type {
  InterviewAssumption,
  OutcomeReason,
  OutcomeViewModel,
} from "./outcome-view-model";
import type { VisaOracleEvaluateResponse } from "./visa-oracle-contract";

function reasons(values: readonly OutcomeReason[]) {
  return values.map((reason) => ({
    code: reason.code,
    sourceRefs: [...reason.sourceIds],
  }));
}

function assumptions(values: readonly InterviewAssumption[]) {
  return values.map((assumption) => ({
    id: assumption.id,
    questionId: assumption.questionId,
    message: assumption.message ?? null,
    assumedValue: assumption.assumedValue ?? null,
    editable: assumption.editable,
  }));
}

/**
 * Decision semantics visible to the applicant. Authority provenance,
 * assessment identifiers and evaluation clocks are deliberately excluded:
 * they differ between independently executed engines without changing the
 * recommendation a shadow comparison is meant to promote.
 */
function semanticProjection(outcome: OutcomeViewModel) {
  return {
    state: outcome.state,
    pathsRemaining: outcome.pathsRemaining,
    assumptions: assumptions(outcome.assumptions),
    candidates: outcome.candidates.map((candidate) => ({
      id: candidate.id,
      code: candidate.code,
      rank: candidate.rank,
      name: candidate.name,
      tagline: candidate.tagline ?? null,
      legal: {
        status: candidate.legal.status,
        reasons: reasons(candidate.legal.reasons),
      },
      operational: {
        status: candidate.operational.status,
        reasons: reasons(candidate.operational.reasons),
      },
      service: {
        status: candidate.service.status,
        reasons: reasons(candidate.service.reasons),
      },
      decisionReasons: reasons(candidate.decisionReasons),
      price:
        candidate.price.status === "AVAILABLE"
          ? {
              status: candidate.price.status,
              currency: candidate.price.currency,
              amount: candidate.price.amount,
              allInclusive: candidate.price.allInclusive,
              validUntil: candidate.price.validUntilIso ?? null,
            }
          : candidate.price,
      timeline: candidate.timeline,
      documents: candidate.documents.map((document) => ({
        label: document.label,
        status: document.status,
        sourceRefs: [...document.sourceIds],
      })),
    })),
    missingInputs:
      outcome.state === "NEEDS_INPUT"
        ? outcome.missingInputs.map((input) => ({
            ...reasons([input])[0],
            questionId: input.questionId ?? null,
          }))
        : [],
    reviewReasons:
      outcome.state === "HUMAN_REVIEW_REQUIRED"
        ? reasons(outcome.reviewReasons)
        : [],
    noPathReasons:
      outcome.state === "NO_SUPPORTED_PATH"
        ? reasons(outcome.noPathReasons)
        : [],
    alternatives:
      outcome.state === "NO_SUPPORTED_PATH"
        ? outcome.alternatives.map((alternative) => ({
            category: alternative.category,
            message: alternative.message ?? null,
          }))
        : [],
    outage:
      outcome.state === "TEMPORARILY_UNAVAILABLE"
        ? {
            code: outcome.outage.code,
            retryable: outcome.outage.retryable,
          }
        : null,
    sources: outcome.sources.map((source) => ({
      id: source.id,
      title: source.title,
      publisher: source.publisher,
      url: source.url,
      authority: source.authority,
      primary: source.primary,
      freshness: source.freshness,
    })),
    nextSteps: outcome.nextSteps.map((step) => ({
      id: step.id,
      title: step.title,
      body: step.body ?? null,
    })),
  };
}

/** A match is emitted only when the complete public decision semantics agree. */
export function shadowParityMatches(
  response: VisaOracleEvaluateResponse,
  visibleBaseline: OutcomeViewModel,
): boolean {
  try {
    const engineOutcome = buildShadowComparisonOutcome(response, {
      assumptions: visibleBaseline.assumptions,
      interviewBranchesRemaining: visibleBaseline.pathsRemaining,
    });
    return (
      JSON.stringify(semanticProjection(engineOutcome)) ===
      JSON.stringify(semanticProjection(visibleBaseline))
    );
  } catch {
    return false;
  }
}
