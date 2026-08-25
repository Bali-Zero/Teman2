"use client";

import { useCallback, useRef, useState } from "react";
import {
  GarudaOrderError,
  GarudaOrderUnexpectedError,
  createOrder,
} from "../../orders/api-client";
import { messageFor, messageForUnknownCode } from "../../orders/messages";
import type { Applicant, OrderCheckout } from "../../orders/types";

export type CheckoutState =
  | { step: "idle" }
  | { step: "submitting" }
  | { step: "created"; order: OrderCheckout }
  | { step: "error"; message: string; retryable: boolean };

function stableKeyFor(resultId: string, applicant: Applicant): string {
  return JSON.stringify([resultId, applicant]);
}

/**
 * Drives `createOrderFromCheck`. Idempotency: a fresh key is minted only when the
 * submitted (resultId, applicant) payload actually changes — retrying after a
 * transient error with the SAME payload reuses the SAME key, which is what makes the
 * contract's exact-replay guarantee useful (no double order on a flaky connection).
 * Changing the applicant (e.g. correcting an email typo after a validation error) is a
 * genuinely new request and gets a new key, so it can never collide into
 * IDEMPOTENCY_CONFLICT against the old payload.
 */
export function useCheckout(resultId: string) {
  const [state, setState] = useState<CheckoutState>({ step: "idle" });
  const idempotencyKeyRef = useRef<string | null>(null);
  const lastPayloadKeyRef = useRef<string | null>(null);

  const submit = useCallback(
    async (applicant: Applicant) => {
      const payloadKey = stableKeyFor(resultId, applicant);
      if (payloadKey !== lastPayloadKeyRef.current) {
        idempotencyKeyRef.current =
          globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random()}`;
        lastPayloadKeyRef.current = payloadKey;
      }
      const idempotencyKey = idempotencyKeyRef.current!;

      setState({ step: "submitting" });
      try {
        const order = await createOrder({
          request: { result_id: resultId, applicant, review_confirmed: true },
          idempotencyKey,
        });
        setState({ step: "created", order });
      } catch (err) {
        if (err instanceof GarudaOrderError) {
          setState({
            step: "error",
            message: messageFor(err.code),
            retryable: err.retryable,
          });
          return;
        }
        if (err instanceof GarudaOrderUnexpectedError) {
          setState({
            step: "error",
            message:
              err.httpStatus !== null && err.httpStatus >= 500
                ? messageFor("SERVICE_UNAVAILABLE")
                : messageForUnknownCode("__network__"),
            retryable: true,
          });
          return;
        }
        setState({
          step: "error",
          message: messageForUnknownCode("__unknown__"),
          retryable: true,
        });
      }
    },
    [resultId],
  );

  return { state, submit };
}
