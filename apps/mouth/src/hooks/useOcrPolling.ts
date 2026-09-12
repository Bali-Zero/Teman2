import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

export interface UseOcrPollingOptions {
  /** Client whose OCR status is being polled. */
  clientId: number;
  /**
   * Called when polling reaches a terminal state (`pending_ocr === 0` or
   * `maxAttempts` reached). Also called on the error path unless
   * `callOnDoneOnError` is false.
   */
  onDone: () => void | Promise<void>;
  /**
   * Whether `onDone` is invoked when the status request throws.
   * Default `true` (PassportCard/VisaCard/FamilyTab behaviour).
   * CompanyDocUpload's original copy did NOT call its callback on the
   * error path — pass `false` there to preserve that.
   */
  callOnDoneOnError?: boolean;
  /**
   * Whether the (possible) promise returned by `onDone` is awaited before
   * the poll loop considers itself finished. Default `true`
   * (Passport/Visa/FamilyTab all `await onRefresh()`). CompanyDocUpload's
   * `onUploaded` is fire-and-forget — pass `false` there.
   */
  awaitOnDone?: boolean;
  /**
   * Whether the loop tracks unmount and stops scheduling further timeouts /
   * state updates. Default `true` (Passport/FamilyTab/CompanyDocUpload all
   * guard on an aborted ref). VisaCard's original copy had NO such guard —
   * pass `false` there to reproduce it as-is (pre-existing gap, not
   * introduced here).
   */
  cleanupOnUnmount?: boolean;
  /** Delay before the first status check, ms. Default 2000. */
  initialDelayMs?: number;
  /** Delay between subsequent status checks, ms. Default 3000. */
  intervalMs?: number;
  /** Max status checks before giving up. Default 10 (10 * 3s = 30s max). */
  maxAttempts?: number;
}

export interface UseOcrPollingResult {
  ocrPolling: boolean;
  pollOcrStatus: () => void;
}

/**
 * Shared OCR-result polling loop, extracted from four near-identical copies
 * in PassportCard, VisaCard, FamilyTab and CompanyDocUpload. Hits
 * `/api/crm/clients/{clientId}/ocr-status` on an interval until
 * `pending_ocr === 0` or `maxAttempts` is reached, then calls `onDone`.
 */
export function useOcrPolling({
  clientId,
  onDone,
  callOnDoneOnError = true,
  awaitOnDone = true,
  cleanupOnUnmount = true,
  initialDelayMs = 2000,
  intervalMs = 3000,
  maxAttempts = 10,
}: UseOcrPollingOptions): UseOcrPollingResult {
  const [ocrPolling, setOcrPolling] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortedRef = useRef(false);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => {
    if (!cleanupOnUnmount) return;
    abortedRef.current = false;
    return () => {
      abortedRef.current = true;
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [cleanupOnUnmount]);

  const isAborted = useCallback(
    () => cleanupOnUnmount && abortedRef.current,
    [cleanupOnUnmount],
  );

  const callOnDone = useCallback(async () => {
    const result = onDoneRef.current();
    if (awaitOnDone) await result;
  }, [awaitOnDone]);

  const pollOcrStatus = useCallback(() => {
    setOcrPolling(true);
    let attempts = 0;
    const poll = async () => {
      if (isAborted()) return;
      try {
        const status = (await api.request(
          `/api/crm/clients/${clientId}/ocr-status`,
        )) as { pending_ocr: number };
        if (status.pending_ocr === 0 || attempts >= maxAttempts) {
          if (!isAborted()) {
            setOcrPolling(false);
            await callOnDone();
          }
          return;
        }
        attempts++;
        timerRef.current = setTimeout(poll, intervalMs);
      } catch {
        if (!isAborted()) {
          setOcrPolling(false);
          if (callOnDoneOnError) await callOnDone();
        }
      }
    };
    timerRef.current = setTimeout(poll, initialDelayMs);
  }, [
    clientId,
    isAborted,
    callOnDone,
    callOnDoneOnError,
    initialDelayMs,
    intervalMs,
    maxAttempts,
  ]);

  return { ocrPolling, pollOcrStatus };
}
