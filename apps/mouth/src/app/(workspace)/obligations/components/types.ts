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
