/**
 * Shared contract types for the obligations reviewer screen.
 *
 * Backend: apps/backend-rag/backend/app/routers/compliance_obligations.py
 * (`ObligationOut`, `ObligationListOut`, `GenerateOut`, `ApproveOut`,
 * `CatalogRuleOut`). Local interfaces rather than the generated
 * `schema.d.ts` typed paths, matching the convention the rest of this screen
 * and `(workspace)/review/page.tsx` already follow.
 */

export type ObligationStatus =
  "proposed" | "approved" | "rejected" | "alerted" | "done";

export const STATUS_FILTER_OPTIONS = [
  "proposed",
  "approved",
  "rejected",
  "alerted",
  "done",
  "all",
] as const;
export type StatusFilter = (typeof STATUS_FILTER_OPTIONS)[number];

/** The statuses the counter strip reports, in display order. */
export const COUNTER_STATUSES = [
  "proposed",
  "approved",
  "rejected",
  "alerted",
] as const;
export type CounterStatus = (typeof COUNTER_STATUSES)[number];

export interface ObligationOut {
  id: number;
  client_id: number;
  rule_id: string;
  period_key: string;
  due_date: string;
  status: ObligationStatus;
  needs_review_reason: string | null;
  reviewer_email: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  alert_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ObligationListOut {
  total: number;
  limit: number;
  offset: number;
  items: ObligationOut[];
}

export interface GenerateOut {
  client_id: number;
  inserted_count: number;
  company_type: string;
  needs_manual_classification: boolean;
  warning: string | null;
  rows: ObligationOut[];
}

export interface ApproveOut {
  obligation: ObligationOut;
  alert_id: string;
}

/**
 * One row of `GET /api/compliance/obligations/catalog` (M3).
 *
 * Rule metadata only, no client data. This screen reads the catalog from the
 * API and never keeps a copy of it: a rule renamed or verified in
 * `backend/data/obligations_catalog.yaml` changes the table without a
 * frontend deploy.
 */
export interface CatalogRuleOut {
  id: string;
  name: string;
  authority: string;
  legal_source: string;
  verified: boolean;
  frequency: string;
  roll: string;
  needs_review_reason: string | null;
  trigger: string | null;
  notes: string | null;
}

export const CARD = {
  borderColor: "var(--bz-border)",
  background: "var(--bz-card, var(--bz-surface))",
} as const;

export const INPUT_STYLE = {
  borderColor: "var(--bz-border)",
  background: "var(--bz-surface)",
  color: "var(--bz-text-1)",
} as const;

/**
 * `GET`/`PATCH /api/compliance/obligations/profile/{client_id}` (M3).
 *
 * `profile` is the computed `ClientProfile` dataclass
 * (`backend/services/compliance/obligations_register.py`) as a dict.
 * `present_keys` are the `companies.custom_fields` keys the engine parsed;
 * `missing_keys` the engine ATTRIBUTES still at their default, which is what
 * makes `applies()` propose the minimum. `company_type_raw` is the
 * `companies.company_type` string the mapping reads, `null` when the client has
 * no company row.
 */
export interface ClientProfileAttributes {
  company_type: string;
  has_employees: boolean;
  employee_count: number;
  has_foreign_employees: boolean;
  pkp: boolean;
  annual_turnover_idr: number | null;
  investment_stage: string | null;
  fiscal_year_end: string;
  serves_indonesian_users_online: boolean;
  pse_registered: boolean;
  pmse_vat_appointed: boolean;
  has_expat_staff_over_6_months: boolean;
}

export interface ProfileOut {
  client_id: number;
  profile: ClientProfileAttributes;
  present_keys: string[];
  missing_keys: string[];
  company_type_raw: string | null;
  needs_manual_classification: boolean;
}

/** The subset of ATTRIBUTES one save writes: only the fields the reviewer touched. */
export type ProfilePatch = Partial<{
  company_type: string;
  investment_stage: string;
  fiscal_year_end: string;
  employee_count: number;
  annual_turnover_idr: number;
  has_employees: boolean;
  has_foreign_employees: boolean;
  pkp: boolean;
  serves_indonesian_users_online: boolean;
  pse_registered: boolean;
  pmse_vat_appointed: boolean;
  has_expat_staff_over_6_months: boolean;
}>;

/**
 * The two closed domains PATCH validates against, mirrored from the engine's
 * COMPANY_TYPES / INVESTMENT_STAGES frozensets. Unlike the rule catalog no
 * endpoint serves them, so the select options have to live here; if they ever
 * drift the PATCH answers 422 naming the allowed set, and this screen shows
 * that detail verbatim instead of swallowing it.
 */
export const COMPANY_TYPE_OPTIONS = [
  "PT_PMA",
  "PT_PMDN",
  "CV",
  "KP3A",
  "KPPA",
  "FOREIGN_PLATFORM",
  "OTHER",
] as const;

export const INVESTMENT_STAGE_OPTIONS = ["construction", "commercial"] as const;

/** Engine BOOL_ATTRS, in the order the panel shows them. */
export const PROFILE_BOOLEAN_FIELDS: ReadonlyArray<
  readonly [keyof ClientProfileAttributes, string]
> = [
  ["has_employees", "Has employees"],
  ["has_foreign_employees", "Has foreign employees"],
  ["pkp", "Registered for VAT (PKP)"],
  ["serves_indonesian_users_online", "Serves Indonesian users online"],
  ["pse_registered", "Registered as PSE"],
  ["pmse_vat_appointed", "Appointed PMSE VAT collector"],
  ["has_expat_staff_over_6_months", "Expat staff over 6 months"],
];
