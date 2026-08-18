/**
 * E33 Second Home Zod Validation Schemas
 *
 * Single source of truth for the second-home console form validation.
 * Types are derived from these schemas via z.infer<>.
 *
 * The backend is always the authority (`validate_evidence_metadata`,
 * `validate_dependent_code`, `E33Case.advance`) — these schemas exist to
 * give the user instant feedback and to pin the no-custody / dependent-pair
 * invariants in a test, not to replace server-side validation.
 */

import { z } from "@/lib/zod";

// ============================================
// SHARED ENUMS
// ============================================

export const guaranteeBasisEnum = z.enum(["deposit", "property"]);

/** Candidate dependent codes — pending official confirmation (letter 006,
 *  DEFAULT_DEPENDENT_CODES in e33_lifecycle.py). */
export const dependentCodeEnum = z.enum(["E31B", "E31E", "E31H", "E31J"]);

export const evidenceKindEnum = z.enum([
  "bank_confirmation",
  "property_title",
  "immigration_filing",
  "immigration_receipt",
  "other",
]);

// ============================================
// HELPERS
// ============================================

/** ISO date string (YYYY-MM-DD) — rejects empty strings. */
const optionalDate = z
  .string()
  .optional()
  .transform((v) => (v === "" ? undefined : v))
  .pipe(
    z
      .string()
      .regex(/^\d{4}-\d{2}-\d{2}$/, "Invalid date format (YYYY-MM-DD)")
      .optional(),
  );

const emptyToUndefined = z
  .string()
  .optional()
  .transform((v) => (v === "" ? undefined : v));

/**
 * No-custody guard mirror (client-side UX only — the backend
 * `validate_evidence_metadata` in e33_lifecycle.py is authoritative).
 * Normalized (lower-cased, non-alphanumerics stripped) substring match, so
 * compound keys like `account_balance` / `deposit_amount` are caught too.
 */
const FORBIDDEN_METADATA_KEY_SUBSTRINGS = [
  "accountnumber",
  "account",
  "balance",
  "amount",
  "iban",
  "swift",
  "nomorrekening",
  "norekening",
  "norek",
  "saldo",
  "jumlah",
] as const;

export function normalizeMetadataKey(key: string): string {
  return key
    .toLowerCase()
    .split("")
    .filter((ch) => /[a-z0-9]/.test(ch))
    .join("");
}

export function isForbiddenMetadataKey(key: string): boolean {
  const normalized = normalizeMetadataKey(key);
  return FORBIDDEN_METADATA_KEY_SUBSTRINGS.some((forbidden) =>
    normalized.includes(forbidden),
  );
}

/** Reference-only metadata: KEYS are guarded client-side as a UX nicety;
 *  the console's own add-evidence form never exposes a generic key/value
 *  editor (per the no-custody hard constraint), so this only fires for
 *  programmatic callers. */
export const evidenceMetadataSchema = z
  .record(z.string(), z.string())
  .optional()
  .superRefine((metadata, ctx) => {
    if (!metadata) return;
    for (const key of Object.keys(metadata)) {
      if (isForbiddenMetadataKey(key)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `Evidence metadata key "${key}" looks like custody data (account/balance/amount) — store document references and dates only, never account numbers, balances or amounts.`,
          path: [key],
        });
      }
    }
  });

// ============================================
// CREATE CASE
// ============================================

export const createCaseSchema = z
  .object({
    client_id: z.number().positive("Select a client"),
    basis: guaranteeBasisEnum,
    practice_id: z.number().positive().optional(),
    owner_email: z
      .string()
      .email("Invalid email address")
      .optional()
      .or(z.literal("")),
    dependent_code: dependentCodeEnum.optional(),
    principal_case_id: emptyToUndefined,
    note: emptyToUndefined,
  })
  .superRefine((data, ctx) => {
    // dependent_code requires principal_case_id and vice versa (422 on the
    // backend too — validated client-side first for instant feedback).
    if (data.dependent_code && !data.principal_case_id) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message:
          "A dependent case requires the principal's existing E33 case ID.",
        path: ["principal_case_id"],
      });
    }
    if (data.principal_case_id && !data.dependent_code) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Select the dependent code for this dependent case.",
        path: ["dependent_code"],
      });
    }
  });

export type CreateCaseInput = z.input<typeof createCaseSchema>;
export type CreateCaseOutput = z.output<typeof createCaseSchema>;

// ============================================
// ADD EVIDENCE
// ============================================

export const addEvidenceSchema = z.object({
  kind: evidenceKindEnum,
  document_ref: z
    .string()
    .min(1, "Document reference is required")
    .max(500, "Document reference is too long"),
  issuing_party: emptyToUndefined,
  issued_on: optionalDate,
  filed_on: optionalDate,
  note: emptyToUndefined,
  metadata: evidenceMetadataSchema,
});

export type AddEvidenceInput = z.input<typeof addEvidenceSchema>;
export type AddEvidenceOutput = z.output<typeof addEvidenceSchema>;

// ============================================
// VALIDATION HELPERS
// ============================================

export { flattenErrors } from "../crm/crm.schemas";
