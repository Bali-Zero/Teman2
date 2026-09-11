"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  GarudaOrderError,
  GarudaOrderUnexpectedError,
  getOrderAndPractice,
} from "./api-client";
import { messageFor, messageForUnknownCode } from "./messages";
import type { OrderView } from "./types";

const POLL_INTERVAL_MS = 5000;

/** Pipeline states where the customer benefits from a live refresh without pressing
 * reload — mirrors a parcel tracker's "still moving" states. Terminal order states
 * (failed/expired/refunded) and terminal practice states (Delivered/Rejected) stop
 * polling: nothing left to wait for, and Delivered/paid must never silently regress
 * back to a "checking…" flicker on a stray re-render. */
function isStillMoving(order: OrderView): boolean {
  if (
    order.order_state === "created" ||
    order.order_state === "awaiting_payment"
  ) {
    return true;
  }
  if (order.order_state !== "paid") return false;
  const practiceState = order.practice?.state;
  return (
    practiceState === undefined ||
    practiceState === "Received" ||
    practiceState === "In review" ||
    practiceState === "Submitted" ||
    practiceState === "Approved" ||
    practiceState === "Blocked"
  );
}

export type OrderTrackingState =
  | { step: "loading" }
  | { step: "ready"; order: OrderView }
  | { step: "error"; message: string; retryable: boolean };

export function useOrderTracking(orderId: string) {
  const [state, setState] = useState<OrderTrackingState>({ step: "loading" });
  const mountedRef = useRef(true);
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const order = await getOrderAndPractice({
        orderId,
        signal: controller.signal,
      });
      if (!mountedRef.current || abortRef.current !== controller) return;
      setState({ step: "ready", order });

      if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
      if (isStillMoving(order)) {
        pollTimeoutRef.current = setTimeout(() => {
          if (mountedRef.current) void load();
        }, POLL_INTERVAL_MS);
      }
    } catch (err) {
      if (!mountedRef.current || abortRef.current !== controller) return;
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
  }, [orderId]);

  useEffect(() => {
    mountedRef.current = true;
    void load();
    return () => {
      mountedRef.current = false;
      abortRef.current?.abort();
      if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
    };
  }, [load]);

  const retry = useCallback(() => {
    void load();
  }, [load]);

  return { state, retry };
}
