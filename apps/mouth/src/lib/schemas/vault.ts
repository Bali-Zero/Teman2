/**
 * Vault (Documents) Zod Schemas
 *
 * Validates responses from the portal document endpoints:
 *   - GET  /api/portal/documents
 *   - POST /api/portal/documents/upload
 *
 * Backend sources of truth:
 *   - Router:  apps/backend-rag/backend/app/routers/portal.py
 *              (`get_documents` @ line 482, `upload_document` @ line 512)
 *   - Service: apps/backend-rag/backend/services/portal/_mixins/documents.py
 *              (`PortalDocumentsMixin.get_documents` @ line 117,
 *               `PortalDocumentsMixin.upload_document` @ line 169)
 *
 * IMPORTANT — Shape notes (verified against BE code, 2026-04-18):
 *
 * 1. The list endpoint emits RENAMED keys, NOT the DB column names:
 *    - DB `document_type`  → response `type`
 *    - DB `file_name`      → response `name`
 *    - DB `file_size_kb`   → response `size_kb`
 *    So the item shape is: { id, type, name, status, expiry_date, size_kb,
 *    practice_id, practice_name, downloadable, created_at }.
 *    There is NO `mime_type`, `drive_file_id`, `preview_url`, `download_url`,
 *    or `uploaded_at`/`uploaded_by` in the list response.
 *
 * 2. `scan_status` is NOT exposed on the list endpoint. The VirusScanner
 *    returns `{clean, threats, scanner}` during upload and raises on threat
 *    (no status is persisted or echoed to the client). We therefore do NOT
 *    model a `scan_status` field on `VaultFile`. If the BE later exposes one,
 *    add it as an optional enum — do not gate parsing on its presence.
 *
 * 3. `documents.status` has NO CHECK constraint at the DB level. Known
 *    values observed in code: "received" (insert default on portal upload),
 *    "verified", "issued" (used by the `downloadable` boolean derivation),
 *    plus whatever workspace/CRM flows may set. Hence we use z.string()
 *    instead of a strict enum — real data has history.
 *
 * 4. `created_at` is produced by `.isoformat()` on a non-nullable DB column
 *    (documents.created_at defaults to NOW() in the upload INSERT). Required,
 *    not nullable.
 *
 * 5. `expiry_date` is `.isoformat()` on nullable column OR null. Explicit
 *    three-way: present-string | null | absent (optional).
 *
 * 6. `practice_id` / `practice_name` come from a LEFT JOIN — null when the
 *    document is not linked to a practice.
 *
 * 7. `size_kb` is `file_size_kb` (integer kilobytes) from the DB. Non-negative
 *    when present, but historically some rows may be null — tolerate it.
 */

import { z } from "zod";

// ============================================
// SCAN STATUS (future-proof, currently unused in list response)
// ============================================

/**
 * Enum values the BE MIGHT expose if `scan_status` is ever added to the list
 * response. The current ClamAV integration is a stubbed heuristic (see
 * `document_processing.py:112-114`) and the result is not persisted nor
 * echoed. Exported so callers can consume it when the field arrives.
 */
export const VaultScanStatus = z.enum([
  "pending",
  "clean",
  "infected",
  "error",
]);
export type VaultScanStatus = z.infer<typeof VaultScanStatus>;

// ============================================
// VAULT FILE (list-endpoint item)
// ============================================

/**
 * A single document as emitted by `GET /api/portal/documents`.
 *
 * Shape mirrors the dict produced at
 * `PortalDocumentsMixin.get_documents` (documents.py:146-160).
 */
export const VaultFile = z.object({
  // DB `documents.id` (serial int).
  id: z.number().int().nonnegative(),

  // Renamed from DB `document_type`. Free-form string (e.g. "passport",
  // "kitas", "nib", "akta_pendirian" — see `_classify_document_category`
  // heuristic for the canonical vocabulary, but BE stores whatever the
  // uploader passes).
  type: z.string(),

  // Renamed from DB `file_name`. Sanitized by `_sanitize_filename`, so
  // will match /^[\w\-.]+$/ in practice, but we don't enforce that here.
  name: z.string(),

  // DB `documents.status`. No CHECK constraint — tolerate any string, allow
  // null just in case (the schema has no NOT NULL enforced in the read path).
  status: z.string().nullable().optional(),

  // `.isoformat()` of a DATE/TIMESTAMP column, OR null when not set.
  expiry_date: z.string().nullable().optional(),

  // Renamed from DB `file_size_kb`. Integer kilobytes. Nullable (historical
  // rows may not have populated it).
  size_kb: z.number().int().nonnegative().nullable().optional(),

  // LEFT-JOIN result — null when document is not tied to a practice.
  practice_id: z.number().int().nonnegative().nullable().optional(),
  practice_name: z.string().nullable().optional(),

  // Derived boolean: `status in ("verified", "issued") AND file_url is not null`.
  downloadable: z.boolean(),

  // `.isoformat()` of DB `created_at` (NOT NULL, defaults to NOW()).
  created_at: z.string(),
});
export type VaultFile = z.infer<typeof VaultFile>;

// ============================================
// LIST ENDPOINT ENVELOPE
// ============================================

/**
 * Response envelope for `GET /api/portal/documents`.
 * Shape: `{ "success": true, "data": VaultFile[] }`.
 */
export const VaultListResponse = z.object({
  success: z.boolean(),
  data: z.array(VaultFile),
});
export type VaultListResponse = z.infer<typeof VaultListResponse>;

// ============================================
// UPLOAD ENDPOINT RESPONSE
// ============================================

/**
 * Inner `processing` block returned by the upload endpoint.
 * Mirrors `documents.py:491-495`.
 */
export const VaultUploadProcessing = z.object({
  virus_clean: z.boolean(),
  ocr_pages: z.number().int().nonnegative().nullable().optional(),
  drive_uploaded: z.boolean(),
});
export type VaultUploadProcessing = z.infer<typeof VaultUploadProcessing>;

/**
 * Inner `data` payload of the upload response.
 * Mirrors the dict returned at `documents.py:478-496`.
 *
 * Note: the upload response shape is a SUPERSET of the list-item shape but
 * intentionally modelled separately because it has different fields
 * (`extracted_text_preview`, `processing`) and lacks `downloadable`,
 * `practice_id`, `practice_name`.
 */
export const VaultUploadedFile = z.object({
  id: z.number().int().nonnegative(),
  type: z.string(),
  name: z.string(),
  status: z.string().nullable().optional(),
  size_kb: z.number().int().nonnegative().nullable().optional(),
  created_at: z.string(),
  expiry_date: z.string().nullable().optional(),
  extracted_text_preview: z.string().nullable().optional(),
  processing: VaultUploadProcessing,
});
export type VaultUploadedFile = z.infer<typeof VaultUploadedFile>;

/**
 * Response envelope for `POST /api/portal/documents/upload`.
 * Shape: `{ success, message, data: VaultUploadedFile }`.
 */
export const VaultUploadResponse = z.object({
  success: z.boolean(),
  message: z.string().optional(),
  data: VaultUploadedFile,
});
export type VaultUploadResponse = z.infer<typeof VaultUploadResponse>;
