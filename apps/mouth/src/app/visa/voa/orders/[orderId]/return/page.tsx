"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { AppFrame } from "@balizero/core";
import {
  GarudaOrderError,
  GarudaOrderUnexpectedError,
  observePaymentBrowserReturn,
} from "../../api-client";

/**
 * `/visa/voa/orders/{orderId}/return` — where the payment provider redirects the
 * browser back to us (owner decision 1: Xendit). This route's ONLY job is OP-07: record
 * the untrusted `return_nonce` as a non-authoritative observation, then hand off to the
 * tracker (`/visa/voa/orders/{orderId}`), which is the sole place order state is read
 * from the server and rendered.
 *
 * Hard rule (contract + mandate): "The browser return is an OBSERVATION, not a truth."
 * This page must NEVER render a success/paid state on the strength of the redirect
 * alone — not while the observation call is in flight, not after it commits (204 means
 * "recorded", not "paid"), and not on error. It always forwards to the tracker, which
 * decides what actually happened from `order_state`.
 *
 * `return_nonce` and `orderId` are opaque, non-PII tokens — carrying them in the query
 * string is exactly what the contract's own `BrowserReturnObservationRequest` shape
 * expects a provider redirect to do, and is not the PII the product rules forbid in
 * URLs (name/email/passport/document-id-that-encodes-one).
 */
export default function OrderReturnPage() {
  const params = useParams<{ orderId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const startedRef = useRef(false);

  const orderId = params?.orderId;
  const returnNonce = searchParams.get("return_nonce");

  useEffect(() => {
    if (!orderId || startedRef.current) return;
    startedRef.current = true;

    if (!returnNonce) {
      // Nothing to observe (e.g. the customer navigated here directly) — just move to
      // the tracker, which reads the real state regardless.
      router.replace(`/visa/voa/orders/${orderId}`);
      return;
    }

    void (async () => {
      try {
        await observePaymentBrowserReturn({
          orderId,
          returnNonce,
          idempotencyKey:
            globalThis.crypto?.randomUUID?.() ?? `return-${Date.now()}`,
        });
      } catch (err) {
        // Deliberately swallowed beyond a transient local message: an observation
        // failure must not block the customer from seeing their REAL order state on
        // the tracker, and it must not be presented as a payment failure — it is
        // neither.
        if (
          err instanceof GarudaOrderError ||
          err instanceof GarudaOrderUnexpectedError
        ) {
          setError(
            "We had trouble recording your return, but your order is safe.",
          );
        }
      } finally {
        router.replace(`/visa/voa/orders/${orderId}`);
      }
    })();
  }, [orderId, returnNonce, router]);

  return (
    <AppFrame
      funnel="visa"
      title="Your Visa on Arrival"
      subtitle={error ?? "Confirming your payment…"}
    >
      <p aria-live="polite" style={{ color: "var(--color-text-muted)" }}>
        One moment while we check your order status.
      </p>
    </AppFrame>
  );
}
