import { trackEvent } from "@/lib/analytics";

export const VISA_ORACLE_TELEMETRY_EVENTS = [
  "visa_oracle_v2_engine_result",
  "visa_oracle_v2_client_guard",
  "visa_oracle_v2_network_failure",
  "visa_oracle_v2_parity_match",
  "visa_oracle_v2_parity_mismatch",
  "visa_oracle_v2_consent_granted",
  "visa_oracle_v2_handoff_opened",
] as const;

export type VisaOracleTelemetryEvent =
  (typeof VISA_ORACLE_TELEMETRY_EVENTS)[number];

export type VisaOracleTelemetryState =
  | "SUPPORTED_CANDIDATES"
  | "NEEDS_INPUT"
  | "HUMAN_REVIEW_REQUIRED"
  | "NO_SUPPORTED_PATH"
  | "TEMPORARILY_UNAVAILABLE";

export interface VisaOracleTelemetry {
  event: VisaOracleTelemetryEvent;
  state?: VisaOracleTelemetryState;
  /** SHA-256 only. Raw facts, category, nationality, or payload are forbidden. */
  correlationHash?: string;
}

const SHA256_HEX = /^[a-f0-9]{64}$/;

export async function nonReversibleHash(value: string): Promise<string> {
  const encoded = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", encoded);
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

/** Closed telemetry boundary: only event, terminal state, and SHA-256 leave. */
export function emitVisaOracleTelemetry(input: VisaOracleTelemetry): void {
  const properties: Record<string, string> = {};
  if (input.state) properties.state = input.state;
  if (input.correlationHash && SHA256_HEX.test(input.correlationHash)) {
    properties.correlation_hash = input.correlationHash;
  }
  trackEvent(input.event, properties);
}
