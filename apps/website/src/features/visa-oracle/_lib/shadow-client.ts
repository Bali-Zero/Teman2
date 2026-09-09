/**
 * Visa Oracle v2 — SHADOW-mode network client.
 *
 * The ONLY module in this route allowed to talk to the network for the
 * live `visa_engine`. Fire-and-forget by construction — this is the hard
 * invariant the whole mandate is built around (see `OracleShell.tsx`'s
 * second one-shot effect, the only call site):
 *
 *  - `sendShadowEvaluation` returns `void`, never a `Promise` — there is
 *    nothing for a caller to `await`, by construction, not by convention.
 *  - Every failure mode is swallowed HERE: `fetch` throwing synchronously
 *    (bad URL, no network stack), the returned value not actually being a
 *    thenable (only possible under a stubbed `global.fetch` in a test
 *    harness — real `fetch` always returns a `Promise`), a network error,
 *    a non-2xx status, a timeout. Nothing downstream ever observes any of
 *    it — no state is set, no error is logged, no retry is scheduled.
 *  - The response body is never read.
 *
 * Endpoint contract (verified 2026-07-27 against
 * `apps/backend-rag/backend/app/routers/visa_oracle_evaluate.py` +
 * `app/auth/public_endpoints.py`): `POST /api/visa-oracle/evaluate` is a
 * fully anonymous, exact-match public endpoint (no token, no auth
 * header), rate-limited 30 req/60s per IP, and returns HTTP 200 for every
 * well-formed body (including its own fail-closed
 * TEMPORARILY_UNAVAILABLE shape). Organic browser SHADOW traffic is
 * labelled explicitly with `traffic_source=real`; this client does not
 * rely on a server default that could silently misclassify an unlabeled
 * caller. The `synthetic_*` classes are gated behind an
 * `X-Visa-Driver-Token` header this UI has no business sending.
 *
 * `API_BASE` mirrors `lib/visa-oracle/api.ts`'s existing pattern verbatim
 * — same env var, same fallback host, so this module resolves to the
 * identical origin the rest of the v1 funnel already talks to.
 */
import type { OracleFacts } from "./tree";
import { mapOracleFactsToApplicantFacts } from "./fact-mapper";

const API_BASE =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "https://nuzantara-rag.fly.dev";

export const SHADOW_EVALUATE_URL = `${API_BASE}/api/visa-oracle/evaluate?traffic_source=real`;

/**
 * Fire the SHADOW evaluate POST for one completed interview. `today` MUST
 * be the caller's already-frozen clock (`OracleShell`'s `frozenToday`) —
 * see `fact-mapper.ts`'s `MapFactsOptions.collectedAt` docstring for why a
 * second independent `new Date()` read here would be unsafe.
 *
 * `keepalive: true` mirrors the house fire-and-forget pattern
 * (`lib/analytics.ts`'s `sendAnalyticsEvent`, `WhatsAppLeadButton`'s
 * capture POST) so the request survives a fast navigation away from the
 * verdict screen instead of being aborted mid-flight.
 */
export function sendShadowEvaluation(facts: OracleFacts, today: Date): void {
  try {
    const payload = mapOracleFactsToApplicantFacts(facts, {
      assessmentId: crypto.randomUUID(),
      collectedAt: today,
    });

    const result = fetch(SHADOW_EVALUATE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      keepalive: true,
    });

    // Defensive: only chain `.catch` if what came back is actually
    // thenable. Real `fetch` always returns a `Promise`; a test harness's
    // `global.fetch = vi.fn()` with no configured resolution returns
    // `undefined`, which has no `.catch` and would otherwise throw
    // synchronously right here — still caught by the outer `try`, but
    // this avoids relying on that as the only backstop.
    if (result && typeof (result as Promise<Response>).catch === "function") {
      (result as Promise<Response>).catch(() => {
        // Ignored by design — SHADOW mode reads nothing back.
      });
    }
  } catch {
    // Ignored by design — a SHADOW-mode network failure must never
    // surface to the render path. See module docstring.
  }
}
