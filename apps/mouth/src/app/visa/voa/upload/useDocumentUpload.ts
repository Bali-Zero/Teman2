"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  GarudaUploadError,
  GarudaUploadUnexpectedError,
  uploadIntakeDocument,
} from "./api-client";
import { messageFor, messageForUnknownCode } from "./messages";
import {
  ALLOWED_UPLOAD_MEDIA_TYPES,
  MAX_UPLOAD_BYTES_CLIENT_HINT,
  type ReviewField,
  type UncertainReviewField,
} from "./types";

// PROCESSING is a real state in the frozen contract (async OCR is a legitimate future
// shape), but is not reachable against today's synchronous backend implementation
// (`garuda_documents/service.py` always resolves fully within the request). This lane
// still implements the replay-poll so a future async backend needs zero frontend change
// — capped so a genuinely stuck PROCESSING state surfaces as a retryable error instead of
// polling forever.
const PROCESSING_POLL_INTERVAL_MS = 2000;
const PROCESSING_POLL_MAX_ATTEMPTS = 15; // 30s total

export type UploadState =
  | { step: "idle" }
  | { step: "client_rejected"; message: string }
  | { step: "uploading" }
  | { step: "ready"; fields: ReviewField[] }
  | { step: "low_confidence"; uncertainFields: UncertainReviewField[] }
  | { step: "unreadable" }
  | { step: "error"; message: string; retryable: boolean };

function newIdempotencyKey(): string {
  return crypto.randomUUID();
}

/** Fast, client-side-only checks — real enforcement is always the server's
 * (byte_validation.py). This exists purely so a customer on a slow connection isn't made
 * to wait for a round trip to learn their file is the wrong type or too large.
 */
function precheckFile(file: File): string | null {
  if (
    !ALLOWED_UPLOAD_MEDIA_TYPES.includes(
      file.type as (typeof ALLOWED_UPLOAD_MEDIA_TYPES)[number],
    )
  ) {
    return messageFor("UNSUPPORTED_DOCUMENT_MEDIA_TYPE");
  }
  if (file.size > MAX_UPLOAD_BYTES_CLIENT_HINT) {
    return messageFor("DOCUMENT_TOO_LARGE");
  }
  return null;
}

export function useDocumentUpload(resultId: string) {
  const [state, setState] = useState<UploadState>({ step: "idle" });
  const fileRef = useRef<File | null>(null);
  const idempotencyKeyRef = useRef<string | null>(null);
  const pollAttemptRef = useRef(0);
  const pollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);

  useEffect(
    () => () => {
      mountedRef.current = false;
      abortRef.current?.abort();
      if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
    },
    [],
  );

  const runUpload = useCallback(async () => {
    const file = fileRef.current;
    const idempotencyKey = idempotencyKeyRef.current;
    if (!file || !idempotencyKey) return;

    // A stale PROCESSING poll from a PRIOR attempt (refuter finding, 2026-08-25) must
    // never fire alongside a fresh one — clear it before starting, not just on unmount.
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }

    setState({ step: "uploading" });
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    // Identity check, not `signal.aborted` alone (refuter finding, 2026-08-25): a NEW
    // runUpload() may already be in flight with its OWN controller by the time this one's
    // fetch settles — comparing `abortRef.current` catches that even in the vanishingly
    // rare case the old signal was never actually flagged aborted before the new request
    // replaced it.
    const isStale = () => abortRef.current !== controller;

    try {
      const body = await uploadIntakeDocument({
        resultId,
        file,
        idempotencyKey,
        signal: controller.signal,
      });
      if (!mountedRef.current || isStale()) return;

      if (body.processing_state === "READY_FOR_REVIEW") {
        pollAttemptRef.current = 0;
        setState({ step: "ready", fields: body.review_fields });
        return;
      }
      if (body.processing_state === "LOW_CONFIDENCE") {
        pollAttemptRef.current = 0;
        setState({
          step: "low_confidence",
          uncertainFields: body.uncertain_fields,
        });
        return;
      }
      // PROCESSING: replay the exact same request after a short wait — the contract
      // guarantees a replay is a no-op on the server, so this is safe to repeat.
      if (pollAttemptRef.current >= PROCESSING_POLL_MAX_ATTEMPTS) {
        setState({
          step: "error",
          message:
            "This is taking longer than expected. Please try again in a moment.",
          retryable: true,
        });
        return;
      }
      pollAttemptRef.current += 1;
      pollTimeoutRef.current = setTimeout(() => {
        if (mountedRef.current) void runUpload();
      }, PROCESSING_POLL_INTERVAL_MS);
    } catch (err) {
      if (!mountedRef.current || isStale()) return;
      if (err instanceof GarudaUploadError) {
        if (err.code === "UNREADABLE_DOCUMENT") {
          setState({ step: "unreadable" });
          return;
        }
        setState({
          step: "error",
          message: messageFor(err.code),
          retryable: err.retryable,
        });
        return;
      }
      if (err instanceof GarudaUploadUnexpectedError) {
        // A malformed 5xx body (raw proxy/server error page, not the contract's
        // ErrorResponse shape) is a backend problem, not the customer's connection
        // (refuter finding, 2026-08-25) — `httpStatus === null` is the true network-layer
        // case (fetch itself rejected, request never reached the server).
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
  }, [resultId]);

  /** New file selected (or retake after unreadable/low-confidence): always a fresh
   * idempotency identity — this is a NEW upload attempt, not a replay of a prior one.
   */
  const selectFile = useCallback(
    (file: File) => {
      const rejection = precheckFile(file);
      if (rejection) {
        setState({ step: "client_rejected", message: rejection });
        return;
      }
      fileRef.current = file;
      idempotencyKeyRef.current = newIdempotencyKey();
      pollAttemptRef.current = 0;
      void runUpload();
    },
    [runUpload],
  );

  /** Retries the SAME attempt (same file, same idempotency key) — only meaningful after
   * a transient/retryable error (network failure, 503). Never used for UNREADABLE_DOCUMENT
   * — that path always needs `selectFile` with a new photo.
   */
  const retryUpload = useCallback(() => {
    if (!fileRef.current || !idempotencyKeyRef.current) return;
    void runUpload();
  }, [runUpload]);

  const reset = useCallback(() => {
    if (pollTimeoutRef.current) {
      clearTimeout(pollTimeoutRef.current);
      pollTimeoutRef.current = null;
    }
    abortRef.current?.abort();
    fileRef.current = null;
    idempotencyKeyRef.current = null;
    pollAttemptRef.current = 0;
    setState({ step: "idle" });
  }, []);

  return { state, selectFile, retryUpload, reset };
}
