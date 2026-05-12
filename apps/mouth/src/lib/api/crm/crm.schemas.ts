/**
 * CRM Zod Validation Schemas
 *
 * Single source of truth for CRM form validation.
 * Types are derived from these schemas via z.infer<>.
 */

import { z } from "zod";

// ============================================
// SHARED ENUMS & CONSTANTS
// ============================================

export const clientStatusEnum = z.enum([
  "lead",
  "active",
  "completed",
  "lost",
  "inactive",
]);
export const clientTypeEnum = z.enum(["individual", "company"]);
export const genderEnum = z.enum(["M", "F"]);
export const leadSourceEnum = z.enum([
  "website",
  "whatsapp",
  "referral",
  "social_media",
  "walk_in",
  "other",
]);

// Practice type codes are now loaded dynamically from the backend catalog
// (69 services across 9 categories). Validate as non-empty string.
export const practiceTypeCodeEnum = z
  .string({ error: "Service type is required" })
  .min(1, "Service type is required");

export const practiceStatusEnum = z.enum([
  "inquiry",
  "quotation_sent",
  "payment_pending",
  "in_progress",
  "completed",
  "cancelled",
  "on_hold",
]);

export const practicePriorityEnum = z.enum(["low", "normal", "high", "urgent"]);

export const familyRelationshipEnum = z.enum([
  "spouse",
  "child",
  "parent",
  "sibling",
  "other",
]);

export const documentCategoryEnum = z.enum([
  "immigration",
  "pma",
  "tax",
  "personal",
  "other",
]);
export const documentStatusEnum = z.enum([
  "pending",
  "received",
  "verified",
  "rejected",
  "expired",
]);

// ============================================
// HELPERS
// ============================================

/** Transforms empty strings to undefined for optional fields */
const emptyToUndefined = z
  .string()
  .optional()
  .transform((v) => (v === "" ? undefined : v));

/** ISO date string (YYYY-MM-DD) — rejects empty strings */
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

// ============================================
// CREATE CLIENT
// ============================================

export const createClientSchema = z
  .object({
    full_name: z
      .string()
      .min(2, "Name must be at least 2 characters")
      .max(200, "Name is too long"),
    email: z
      .string()
      .email("Invalid email address")
      .optional()
      .or(z.literal("")),
    phone: emptyToUndefined,
    whatsapp: emptyToUndefined,
    company_name: emptyToUndefined,
    nationality: emptyToUndefined,
    passport_number: emptyToUndefined,
    passport_expiry: optionalDate,
    date_of_birth: optionalDate,
    gender: genderEnum.optional(),
    birthplace: emptyToUndefined,
    notes: emptyToUndefined,
    status: clientStatusEnum.default("lead"),
    client_type: clientTypeEnum.default("individual"),
    assigned_to: emptyToUndefined,
    tags: z.array(z.string()).optional(),
    address: emptyToUndefined,
    lead_source: leadSourceEnum.optional(),
    service_interest: z.array(z.string()).optional(),
    avatar_url: z.string().optional(),
  })
  .superRefine((data, ctx) => {
    // Minor check: block standalone profiles for under-18
    if (data.date_of_birth) {
      const dob = new Date(data.date_of_birth);
      const today = new Date();
      const age = Math.floor(
        (today.getTime() - dob.getTime()) / (365.25 * 24 * 60 * 60 * 1000),
      );
      if (age < 18) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `Client is ${age} years old. Minors cannot have a standalone profile — add them as a Family Member instead.`,
          path: ["date_of_birth"],
        });
      }
    }

    // If client_type is company, company_name should be provided
    if (data.client_type === "company" && !data.company_name) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Company name is required for company clients",
        path: ["company_name"],
      });
    }
  });

export type CreateClientInput = z.input<typeof createClientSchema>;
export type CreateClientOutput = z.output<typeof createClientSchema>;

// ============================================
// CREATE PRACTICE
// ============================================

export const createPracticeSchema = z
  .object({
    client_id: z
      .number({ error: "Client is required" })
      .positive("Invalid client ID"),
    practice_type_code: practiceTypeCodeEnum,
    status: practiceStatusEnum.default("inquiry"),
    priority: practicePriorityEnum.default("normal"),
    notes: emptyToUndefined,
    internal_notes: emptyToUndefined,
    quoted_price: z.number().nonnegative("Price cannot be negative").optional(),
    // Discount (added 2026-05-06, owner Q1=a/Q4=a/Q5=c). Cross-field check
    // below enforces discount_amount <= quoted_price so the form catches
    // an over-discount before the backend round-trip.
    discount_amount: z
      .number()
      .nonnegative("Discount cannot be negative")
      .optional(),
    discount_reason: emptyToUndefined,
    start_date: optionalDate,
    family_member_id: z.number().positive().optional(),
  })
  .refine(
    (data) =>
      data.discount_amount === undefined ||
      data.quoted_price === undefined ||
      data.discount_amount <= data.quoted_price,
    {
      message: "Discount cannot exceed quoted price",
      path: ["discount_amount"],
    },
  );

export type CreatePracticeInput = z.input<typeof createPracticeSchema>;
export type CreatePracticeOutput = z.output<typeof createPracticeSchema>;

// ============================================
// FAMILY MEMBER
// ============================================

export const createFamilyMemberSchema = z.object({
  full_name: z
    .string()
    .min(2, "Name must be at least 2 characters")
    .max(200, "Name is too long"),
  relationship: familyRelationshipEnum,
  date_of_birth: optionalDate,
  nationality: emptyToUndefined,
  passport_number: emptyToUndefined,
  passport_expiry: optionalDate,
  current_visa_type: emptyToUndefined,
  visa_expiry: optionalDate,
  email: z.string().email("Invalid email address").optional().or(z.literal("")),
  phone: emptyToUndefined,
  notes: emptyToUndefined,
});

export type CreateFamilyMemberInput = z.input<typeof createFamilyMemberSchema>;

// ============================================
// DOCUMENT
// ============================================

export const createDocumentSchema = z.object({
  document_type: z.string().min(1, "Document type is required"),
  document_category: documentCategoryEnum.optional(),
  file_name: emptyToUndefined,
  file_id: emptyToUndefined,
  file_url: z.string().url("Invalid file URL").optional().or(z.literal("")),
  google_drive_file_url: z
    .string()
    .url("Invalid Google Drive URL")
    .optional()
    .or(z.literal("")),
  expiry_date: optionalDate,
  notes: emptyToUndefined,
  family_member_id: z.number().positive().optional(),
  practice_id: z.number().positive().optional(),
});

export type CreateDocumentInput = z.input<typeof createDocumentSchema>;

// ============================================
// VALIDATION HELPERS
// ============================================

/**
 * Extract field-level errors from a ZodError into a flat map.
 * Usage: const errors = flattenErrors(result.error)
 *        errors['full_name'] → 'Name must be at least 2 characters'
 */
export function flattenErrors(error: z.ZodError): Record<string, string> {
  const fieldErrors: Record<string, string> = {};
  for (const issue of error.issues) {
    const path = issue.path.join(".");
    if (path && !fieldErrors[path]) {
      fieldErrors[path] = issue.message;
    }
  }
  return fieldErrors;
}
