/**
 * Hand-written types mirroring the FROZEN GARUDA VOA contract
 * (`products/garuda-voa/contracts/openapi.yaml` + `errors.yaml`) for the one endpoint
 * this lane calls: `POST /api/visa/voa/eligibility-checks/{result_id}/documents`.
 *
 * These are hand-written because the typed-contract toolchain (OpenAPI -> generated TS
 * client) is not wired into this repo yet — ASSEMBLY-LINE.md's Enforcement backlog #4
 * tracks it as a follow-up for "the first product" (GARUDA VOA itself). Once that lands,
 * this file is the one to delete in favor of the generated client — every shape below is
 * a direct transcription of the contract, not an invention, so the swap should be
 * mechanical. Do NOT let this file drift from the contract without checking both.
 */

export const PASSPORT_REVIEW_FIELD_NAMES = [
  "full_name",
  "passport_number",
  "nationality",
  "passport_expiry_date",
] as const;

export type PassportReviewFieldName =
  (typeof PASSPORT_REVIEW_FIELD_NAMES)[number];

export interface ReviewField {
  field_path: PassportReviewFieldName;
  value: string;
  confirmation_required: boolean;
}

export interface UncertainReviewField {
  field_path: PassportReviewFieldName;
  confirmation_required: true;
}

export interface ReadyDocument {
  document_id: string;
  processing_state: "READY_FOR_REVIEW";
  review_fields: ReviewField[];
}

export interface ProcessingDocument {
  document_id: string;
  processing_state: "PROCESSING";
}

export interface LowConfidenceDocument {
  document_id: string;
  processing_state: "LOW_CONFIDENCE";
  uncertain_fields: UncertainReviewField[];
}

export type UploadSuccessBody =
  ReadyDocument | ProcessingDocument | LowConfidenceDocument;

/** Closed error catalog — see contracts/errors.yaml. Only the codes this one endpoint's
 * openapi.yaml operation actually documents are listed; an unlisted code from the network
 * is still handled (see api-client.ts) but treated as a generic retryable failure.
 */
export type UploadErrorCode =
  | "IDEMPOTENCY_KEY_REQUIRED"
  | "SESSION_REQUIRED"
  | "GARUDA_PUBLIC_DISABLED"
  | "RESULT_NOT_FOUND"
  | "IDEMPOTENCY_CONFLICT"
  | "DOCUMENT_TOO_LARGE"
  | "UNSUPPORTED_DOCUMENT_MEDIA_TYPE"
  | "INVALID_REQUEST"
  | "UNREADABLE_DOCUMENT"
  | "PERSISTENCE_POLICY_UNAVAILABLE"
  | "DOCUMENT_PROCESSING_UNAVAILABLE"
  | "SERVICE_UNAVAILABLE"
  | "INTERNAL_ERROR";

export interface ErrorResponse {
  code: UploadErrorCode;
  retryable: boolean;
  message_key: string;
}

export const DOCUMENT_KIND_PASSPORT_BIODATA = "PASSPORT_BIODATA" as const;

export const ALLOWED_UPLOAD_MEDIA_TYPES = [
  "image/jpeg",
  "image/png",
  "image/webp",
] as const;

// Must stay in sync with `apps/backend-rag/backend/services/garuda_documents/byte_validation.py`
// (MAX_UPLOAD_BYTES) — the contract has no machine-readable bound for a `format: binary`
// field yet, so this is a manually-mirrored client-side fast-fail, not the enforcement
// boundary (the server always re-validates; this only saves the customer a wasted upload).
export const MAX_UPLOAD_BYTES_CLIENT_HINT = 15 * 1024 * 1024;
