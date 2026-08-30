/**
 * Customer-facing copy keyed by the contract's closed `message_key` catalog
 * (`products/garuda-voa/contracts/errors.yaml`). The server never returns rendered text —
 * only the stable key — so localization/wording changes never require a backend deploy.
 *
 * `COPY` is typed `Record<UploadErrorCode, string>`, so TypeScript itself refuses to
 * compile this file if a code is added to `UploadErrorCode` (types.ts) without a matching
 * entry here — a new error code without copy fails the BUILD, not a lookup at runtime.
 */

import type { UploadErrorCode } from "./types";

const COPY: Record<UploadErrorCode, string> = {
  IDEMPOTENCY_KEY_REQUIRED:
    "Something went wrong preparing your upload. Please try again.",
  SESSION_REQUIRED:
    "Your session has expired. Please sign in again to continue.",
  GARUDA_PUBLIC_DISABLED:
    "Document upload isn't available right now. Please try again later.",
  RESULT_NOT_FOUND:
    "We couldn't find your application. Please start again from your check result.",
  IDEMPOTENCY_CONFLICT:
    "This upload didn't match your previous attempt. Please choose the photo again.",
  DOCUMENT_TOO_LARGE:
    "This photo is too large. Please retake it or choose a smaller file (max 15 MB).",
  UNSUPPORTED_DOCUMENT_MEDIA_TYPE:
    "Please upload a JPG, PNG, or WEBP photo of your passport.",
  INVALID_REQUEST: "We couldn't process that request. Please try again.",
  UNREADABLE_DOCUMENT:
    "We couldn't read this photo. Please retake it in good light, with the whole passport page visible, and try again.",
  PERSISTENCE_POLICY_UNAVAILABLE:
    "Uploads are temporarily unavailable. Please try again in a moment.",
  DOCUMENT_PROCESSING_UNAVAILABLE:
    "We're having trouble reading documents right now. Please try again shortly.",
  SERVICE_UNAVAILABLE:
    "Something went wrong on our end. Please try again in a moment.",
  INTERNAL_ERROR: "Something went wrong on our end. Please try again.",
};

const GENERIC_NETWORK_ERROR =
  "We couldn't reach the server. Check your connection and try again.";

export function messageFor(code: UploadErrorCode): string {
  return COPY[code];
}

export function messageForUnknownCode(code: string): string {
  return code in COPY ? COPY[code as UploadErrorCode] : GENERIC_NETWORK_ERROR;
}

export const COPY_LOW_CONFIDENCE_INSTRUCTION =
  "We could read most of your passport, but a few fields need your confirmation. Please check each one below, correcting anything that's wrong, or retake the photo.";

export const COPY_UNREADABLE_INSTRUCTION =
  "We couldn't read this photo. Please retake it: good light, no glare, and the whole biodata page visible in frame.";

export const FIELD_LABELS: Record<string, string> = {
  full_name: "Full name",
  passport_number: "Passport number",
  nationality: "Nationality",
  passport_expiry_date: "Passport expiry date",
};

export const CHECKLIST_ITEMS = [
  "The photo shows the passport's biodata page (with your photo and details) — not the cover.",
  "All four corners of the page are visible in the frame.",
  "The page is flat, in focus, and well lit — no glare or shadow across the text.",
  "The photo is a JPG, PNG, or WEBP file, under 15 MB.",
] as const;
