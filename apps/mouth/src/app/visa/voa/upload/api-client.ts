/**
 * Fetch wrapper for the one frozen GARUDA VOA endpoint this lane owns:
 * `POST /api/visa/voa/eligibility-checks/{result_id}/documents`.
 *
 * Auth is the contract's `MagicSession` — a Secure, HttpOnly `garuda_session` cookie set
 * by L4's magic-link exchange, `Domain` set by the backend's `get_cookie_domain()`
 * (`.balizero.com` in production, `garuda_portal_auth.py`'s `_set_account_session_cookie`)
 * — never sent to a request that goes directly to `nuzantara-rag.fly.dev`. `fetch` sends
 * same-origin cookies by default, so no token handling belongs here, but the base URL
 * MUST stay same-origin `/api` (2026-09-03: `NEXT_PUBLIC_API_URL` pointing at the Fly host
 * directly 401'd the sibling staff lane's cookie-session calls the same way — see
 * `(workspace)/garuda-voa/api-client.ts`).
 */

import {
  ALLOWED_UPLOAD_MEDIA_TYPES,
  DOCUMENT_KIND_PASSPORT_BIODATA,
  type ErrorResponse,
  type UploadErrorCode,
  type UploadSuccessBody,
} from "./types";

const API_BASE_URL = "/api";

export class GarudaUploadError extends Error {
  constructor(
    public readonly code: UploadErrorCode,
    public readonly retryable: boolean,
    public readonly httpStatus: number,
  ) {
    super(`GarudaUploadError(${code})`);
    this.name = "GarudaUploadError";
  }
}

/** Thrown when the response body cannot be parsed as the contract's ErrorResponse or
 * success shapes at all — a network-layer or truly unexpected-server failure, distinct
 * from a well-formed error the contract documents.
 */
export class GarudaUploadUnexpectedError extends Error {
  public readonly sourceCause: unknown;

  constructor(
    public readonly httpStatus: number | null,
    cause?: unknown,
  ) {
    super("GarudaUploadUnexpectedError");
    this.name = "GarudaUploadUnexpectedError";
    this.sourceCause = cause;
  }
}

function isErrorResponseShape(body: unknown): body is ErrorResponse {
  return (
    typeof body === "object" &&
    body !== null &&
    "code" in body &&
    "retryable" in body &&
    "message_key" in body
  );
}

export interface UploadIntakeDocumentParams {
  resultId: string;
  file: File;
  idempotencyKey: string;
  signal?: AbortSignal;
}

/**
 * Uploads one passport-biodata photo. Only `document_kind: PASSPORT_BIODATA` exists in
 * the frozen contract today — nothing here accepts a different kind.
 *
 * Callers are responsible for the contract's replay semantics: calling this again with
 * the SAME `idempotencyKey` and the SAME `file` bytes is always safe (the server returns
 * the original committed outcome, `Idempotency-Replayed: true`, no repeated effect) — this
 * is how `useDocumentUpload.ts` polls past a 202 PROCESSING response.
 */
export async function uploadIntakeDocument({
  resultId,
  file,
  idempotencyKey,
  signal,
}: UploadIntakeDocumentParams): Promise<UploadSuccessBody> {
  const form = new FormData();
  form.set("document_kind", DOCUMENT_KIND_PASSPORT_BIODATA);
  form.set("file", file);

  let response: Response;
  try {
    response = await fetch(
      `${API_BASE_URL}/visa/voa/eligibility-checks/${encodeURIComponent(resultId)}/documents`,
      {
        method: "POST",
        credentials: "same-origin",
        headers: { "Idempotency-Key": idempotencyKey },
        body: form,
        signal,
      },
    );
  } catch (cause) {
    // Network failure never reached the server at all — always safe to retry with the
    // same idempotency key.
    throw new GarudaUploadUnexpectedError(null, cause);
  }

  let body: unknown;
  try {
    body = await response.json();
  } catch (cause) {
    throw new GarudaUploadUnexpectedError(response.status, cause);
  }

  if (response.ok) {
    // 201 or 202 — both success shapes are already the contract's exact union.
    return body as UploadSuccessBody;
  }

  if (isErrorResponseShape(body)) {
    throw new GarudaUploadError(body.code, body.retryable, response.status);
  }

  throw new GarudaUploadUnexpectedError(response.status, body);
}

export { ALLOWED_UPLOAD_MEDIA_TYPES };
