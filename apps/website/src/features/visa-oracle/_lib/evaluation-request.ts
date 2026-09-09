import {
  mapOracleFactsToApplicantFacts,
  stableEvaluationInputKey,
} from "./fact-mapper";
import {
  getOrCreateEvaluationIdentity,
  type EvaluationIdentity,
} from "./evaluation-identity-store";
import { nonReversibleHash } from "./telemetry";
import type { OracleFacts } from "./tree";
import type { VisaOracleEvaluateRequest } from "./visa-oracle-contract";

const PLACEHOLDER_ASSESSMENT_ID = "00000000-0000-4000-8000-000000000000";

export interface PrepareEvaluationRequestOptions {
  facts: OracleFacts;
  attempt: number;
  now?: Date;
  storage?: Pick<Storage, "getItem" | "setItem" | "removeItem">;
  createId?: () => string;
  hash?: (value: string) => Promise<string>;
}

export interface PreparedEvaluationRequest {
  request: VisaOracleEvaluateRequest;
  identity: EvaluationIdentity;
  evaluationHash: string;
}

/**
 * Bind one durable identity to the complete semantic evaluation input. The
 * volatile envelope fields are intentionally excluded from the hash; after an
 * identity is recovered, its original creation time becomes `collected_at` so
 * a reload replays the exact same bytes with the same Idempotency-Key.
 */
export async function prepareEvaluationRequest(
  options: PrepareEvaluationRequestOptions,
): Promise<PreparedEvaluationRequest> {
  const now = options.now ?? new Date();
  const provisional = mapOracleFactsToApplicantFacts(options.facts, {
    assessmentId: PLACEHOLDER_ASSESSMENT_ID,
    collectedAt: now,
  });
  const evaluationHash = await (options.hash ?? nonReversibleHash)(
    stableEvaluationInputKey(provisional),
  );
  const identity = getOrCreateEvaluationIdentity({
    attempt: options.attempt,
    evaluationHash,
    storage: options.storage,
    now,
    createId: options.createId,
  });
  const request = mapOracleFactsToApplicantFacts(options.facts, {
    assessmentId: identity.assessmentId,
    collectedAt: new Date(identity.createdAtIso),
  });
  return {
    request,
    identity,
    evaluationHash,
  };
}
