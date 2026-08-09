/**
 * Upload size cap. Configurable via NEXT_PUBLIC_VAULT_MAX_SIZE; default 10 MB.
 */
const DEFAULT_MAX = 10 * 1024 * 1024;
const raw = process.env.NEXT_PUBLIC_VAULT_MAX_SIZE;
const parsed = raw ? Number(raw) : DEFAULT_MAX;
export const MAX_SIZE_BYTES =
  Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_MAX;

/**
 * Upload MIME allowlist — enforced client-side only as a defensive UX check.
 * The backend has its own validation; this prevents obvious mistakes before
 * bytes go over the wire.
 */
export const ALLOWED_UPLOAD_MIMES = [
  "application/pdf",
  "image/jpeg",
  "image/png",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
] as const satisfies readonly string[];

export const UPLOAD_ACCEPT = ".pdf,.jpg,.jpeg,.png,.docx";
export const UPLOAD_FORMAT_LABEL = "PDF, JPG, PNG, or DOCX up to 10 MB";

export type AllowedUploadMime = (typeof ALLOWED_UPLOAD_MIMES)[number];

export function isAllowedUploadMime(mime: string): boolean {
  return (ALLOWED_UPLOAD_MIMES as readonly string[]).includes(mime);
}
