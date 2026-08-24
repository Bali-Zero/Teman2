/**
 * Fire-and-forget emitter for the frozen C3 `ConsultantAssignmentEvent`
 * (`docs/plans/2026-08-24-visa-oracle-live/contracts/FROZEN.md`).
 *
 * This is the "shortest jump" wiring: the "Talk to a consultant" control
 * must never be blocked, delayed, or visibly degraded by this call — the
 * durable signal it produces is a side-effect of the control being used,
 * never a precondition for it. Every failure mode (network, timeout,
 * `fetch` unavailable, non-2xx response) is swallowed here; the backend
 * router already logs a persistence failure server-side
 * (`app/routers/visa_oracle_consultant.py`), and there is no useful
 * client-side recovery for an anonymous, best-effort signal.
 *
 * Deliberately NOT built on `evaluation-client.ts`'s bounded-retry,
 * idempotency-keyed client: that client's whole design is "the caller is
 * waiting on this response to render a verdict". This call is the opposite
 * shape — nobody is waiting on it, and it must never grow retries that
 * could out-live the screen that triggered it.
 */

export type ConsultantAssignmentOriginScreen =
  "wizard" | "verdict" | "checkout" | "portal";

export type ConsultantAssignmentTier = "T1" | "T2" | "T3";

export type ConsultantAssignmentLocale = "en" | "id";

export const CONSULTANT_ASSIGNMENT_URL =
  "/api/visa-oracle/consultant-assignment";
export const CONSULTANT_ASSIGNMENT_TIMEOUT_MS = 8_000;

export interface RequestConsultantAssignmentOptions {
  evaluationId: string;
  /** Present only once a client identity exists — the whole point of C3 is
   * that this control must be emittable before one does. */
  clientId?: string | null;
  originScreen: ConsultantAssignmentOriginScreen;
  tier: ConsultantAssignmentTier;
  /** Present only once a candidate has been resolved (SUPPORTED_CANDIDATES
   * verdicts). Never fabricated for any other outcome state. */
  productVersionId?: string | null;
  locale: ConsultantAssignmentLocale;
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
}

/**
 * Emits the C3 event. Never throws and never rejects — callers `void` this
 * call rather than await it on the interaction path.
 */
export async function requestConsultantAssignment(
  options: RequestConsultantAssignmentOptions,
): Promise<void> {
  const body: Record<string, string> = {
    evaluation_id: options.evaluationId,
    origin_screen: options.originScreen,
    tier: options.tier,
    locale: options.locale,
  };
  if (options.clientId) body.client_id = options.clientId;
  if (options.productVersionId)
    body.product_version_id = options.productVersionId;

  let payload: string;
  try {
    payload = JSON.stringify(body);
  } catch {
    return;
  }

  const controller = new AbortController();
  const timeout = setTimeout(
    () => controller.abort(),
    options.timeoutMs ?? CONSULTANT_ASSIGNMENT_TIMEOUT_MS,
  );
  try {
    await (options.fetchImpl ?? fetch)(CONSULTANT_ASSIGNMENT_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: payload,
      cache: "no-store",
      credentials: "same-origin",
      signal: controller.signal,
    });
    // Response status is intentionally not inspected — see module docstring.
  } catch {
    // Network failure, abort/timeout, or `fetch` unavailable — never
    // propagate. This channel is best-effort by design.
  } finally {
    clearTimeout(timeout);
  }
}
