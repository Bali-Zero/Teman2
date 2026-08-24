import { trackPiiFreeEvent } from "@/lib/analytics";

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
  | "TEMPORARILY_UNAVAILABLE"
  /**
   * NOT one of the five engine outcomes (C1's frozen contract, `enums.py`).
   * The ever-present consultant control (`ConsultantAccess.tsx`) can be
   * invoked from any wizard screen — framing, a question, confirmation —
   * before an evaluation has ever run, and there is no honest engine state
   * to report at that point. This value exists so the handoff message and
   * telemetry never claim one of the five real states for a visitor who has
   * not been evaluated yet.
   */
  | "IN_PROGRESS";

export interface VisaOracleTelemetry {
  event: VisaOracleTelemetryEvent;
  state?: VisaOracleTelemetryState;
  /** SHA-256 only. Raw facts, category, nationality, or payload are forbidden. */
  correlationHash?: string;
  /**
   * SHADOW-parity events only (QW-2). Identifies the independent gold-oracle
   * baseline's PINNED rule-pack (`gold-oracle-baseline.ts`'s
   * `GOLD_ORACLE_PACK_HASH`) that produced this match/mismatch verdict —
   * never a live server value, so a rotation of the pinned pack is visible
   * in the event stream without a schema change. PII-free by construction:
   * it is a build-time constant, not a value read from applicant data.
   */
  packHash?: string;
  /**
   * SHADOW-parity events only (QW-2). Build identifier for the frontend
   * that emitted the verdict, so a parity_mismatch spike can be correlated
   * to a specific deploy. PII-free (a commit SHA / build id, never a
   * request-derived value).
   */
  frontendVersion?: string;
}

const SHA256_HEX = /^[a-f0-9]{64}$/;

export async function nonReversibleHash(value: string): Promise<string> {
  const encoded = new TextEncoder().encode(value);
  const digest = await crypto.subtle.digest("SHA-256", encoded);
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

/**
 * Build identifier for this frontend deploy. Vercel does not auto-expose its
 * system `VERCEL_GIT_COMMIT_SHA` to client bundles (only `NEXT_PUBLIC_`-
 * prefixed vars are inlined) — `NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA` must be
 * added to the Vercel project's environment variables for this to carry a
 * real commit; until then it deliberately falls back to `"unknown"` rather
 * than fabricating a value. The repository is public, so the SHA is not a
 * secret (same posture as `app/api/health/route.ts`'s server-side `COMMIT`).
 */
export function resolveFrontendVersion(
  value: string | undefined = process.env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA,
): string {
  return value && value.trim().length > 0 ? value : "unknown";
}

/** Closed telemetry boundary: only event, terminal state, SHA-256, and (for
 * SHADOW-parity events) the pinned pack/build identifiers leave. */
export function emitVisaOracleTelemetry(input: VisaOracleTelemetry): void {
  const properties: Record<string, string> = {};
  if (input.state) properties.state = input.state;
  if (input.correlationHash && SHA256_HEX.test(input.correlationHash)) {
    properties.correlation_hash = input.correlationHash;
  }
  if (input.packHash) properties.pack_hash = input.packHash;
  if (input.frontendVersion)
    properties.frontend_version = input.frontendVersion;
  trackPiiFreeEvent(input.event, properties);
}
