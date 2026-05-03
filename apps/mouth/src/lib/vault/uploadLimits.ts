/**
 * Upload size cap. Configurable via NEXT_PUBLIC_VAULT_MAX_SIZE; default 20 MB.
 */
const DEFAULT_MAX = 20 * 1024 * 1024;
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
  "image/webp",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/msword",
  "application/vnd.ms-excel",
] as const satisfies readonly string[];

export type AllowedUploadMime = (typeof ALLOWED_UPLOAD_MIMES)[number];

export function isAllowedUploadMime(mime: string): boolean {
  return (ALLOWED_UPLOAD_MIMES as readonly string[]).includes(mime);
}
