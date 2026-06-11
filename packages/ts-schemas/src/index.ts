export enum StreamEventType {
  NODE_START = "node_start",
  NODE_END = "node_end",
  NODE_ERROR = "node_error",
  ANSWER_CHUNK = "answer_chunk",
  GRADE_RESULT = "grade_result",
  CORRECTION_START = "correction_start",
  TOOL_CALL = "tool_call",
  TOOL_RESULT = "tool_result",
  STATE_UPDATE = "state_update",
  DONE = "done",
  ERROR = "error",
}

export type ChannelType = "web" | "whatsapp" | "telegram" | "instagram";

export interface QueryRequest {
  query: string;
  user_id?: string;
  channel?: ChannelType;
  session_id?: string;
}

export interface QueryResponse {
  run_id: string;
  answer: string;
  sources: Record<string, unknown>[];
  confidence: Record<string, unknown>;
  intent: string;
  domain: string | null;
  token_usage: Record<string, unknown>;
  error: string | null;
}

export interface StreamNodeEvent {
  run_id: string;
  event_type: StreamEventType;
  node: string;
  data: Record<string, unknown>;
  sequence: number;
}

export interface ConfidenceScores {
  retrieval_relevance: number;
  source_authority: number;
  reasoning_coherence: number;
  factual_grounding: number;
  domain_coverage: number;
  answer_completeness: number;
}

const CONFIDENCE_WEIGHTS: Record<keyof ConfidenceScores, number> = {
  retrieval_relevance: 0.2,
  source_authority: 0.15,
  reasoning_coherence: 0.2,
  factual_grounding: 0.2,
  domain_coverage: 0.15,
  answer_completeness: 0.1,
};

export function computeOverallConfidence(scores: ConfidenceScores): number {
  const total = Object.entries(CONFIDENCE_WEIGHTS).reduce(
    (acc, [field, weight]) =>
      acc + scores[field as keyof ConfidenceScores] * weight,
    0,
  );
  return Math.round(total * 10_000) / 10_000;
}
