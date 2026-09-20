import { trackPiiFreeEvent } from "@/lib/analytics";

export const VISA_ORACLE_TELEMETRY_EVENTS = [
  "visa_oracle_v2_engine_result",
  "visa_oracle_v2_client_guard",
  "visa_oracle_v2_network_failure",
  "visa_oracle_v2_parity_match",
  "visa_oracle_v2_parity_mismatch",
  "visa_oracle_v2_consent_granted",
  "visa_oracle_v2_handoff_opened",
  // PR-O4 / Δ2: the contact panel stopped showing the visitor a
  // configuration string, so this is the only remaining signal that the
  // WhatsApp number never reached ConsentHandoff. Carries the terminal state
  // at most — no number, no facts.
  "visa_oracle_v2_handoff_unconfigured",
  // Slice A2 (PLAN VISA-ORACLE-DW-20260919 N3): a `notices[]` code with no
  // dedicated copy in `engine-adapter.ts`'s `NOTICE_CONDITION_COPY`. Should
  // never fire once every code the backend can emit has copy — the code
  // itself is a fixed system identifier (the engine's `ReasonCode` open
  // pattern, `models.py:95-96`), never applicant-supplied text.
  "visa_oracle_v2_notice_unmapped_code",
  // Slice A5: a review-reason code with no dedicated copy in
  // `engine-adapter.ts`'s `REVIEW_REASON_COPY`.
  "visa_oracle_v2_review_reason_unmapped_code",
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
  /**
   * `visa_oracle_v2_notice_unmapped_code` and
   * `visa_oracle_v2_review_reason_unmapped_code`. A fixed system reason code
   * (never applicant-supplied text) — validated against the engine's own
   * `ReasonCode` pattern (`models.py:95-96`) before it leaves the closed
   * boundary below.
   */
  code?: string;
}

const SHA256_HEX = /^[a-f0-9]{64}$/;
const REASON_CODE = /^[A-Z][A-Z0-9_]{0,127}$/;

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
  if (input.code && REASON_CODE.test(input.code)) properties.code = input.code;
  trackPiiFreeEvent(input.event, properties);
}
