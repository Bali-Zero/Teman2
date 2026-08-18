/**
 * E33 Second Home — internal console API types.
 *
 * Mirrors the FIXED JSON contracts of the backend E33 case-entrance router
 * (`apps/backend-rag/backend/app/routers/e33_cases.py`, built in parallel —
 * see SPEC-e33-internal-console.md PR-1). The domain lifecycle model these
 * contracts wrap is `apps/backend-rag/backend/services/crm/e33_lifecycle.py`.
 *
 * NO-CUSTODY (owner decision 2026-07-23, non-negotiable): these types
 * deliberately carry NO amount/account/balance/IBAN fields anywhere.
 * Evidence is references-only (document ids, issuing party, dates).
 */

// ── Stages (13 total — mirrors E33Stage in e33_lifecycle.py) ─────────────────

export type E33Stage =
  | "fit_memo"
  | "bank_precheck"
  | "application"
  | "payment"
  | "visa_issued"
  | "entry"
  | "itas_active"
  | "guarantee_proof_due"
  | "annual_maintenance"
  | "renewal"
  | "epo"
  | "status_change"
  | "itap_eval";

/** Which qualifying-guarantee route the case uses. Mirrors GuaranteeBasis. */
export type GuaranteeBasis = "deposit" | "property";

/**
 * Dependent visa codes — PENDING official confirmation (letter 006).
 * Mirrors `DEFAULT_DEPENDENT_CODES` in e33_lifecycle.py. Configurable on the
 * backend; kept as a literal union here since the console only ever offers
 * these four candidates.
 */
export type DependentCode = "E31B" | "E31E" | "E31H" | "E31J";

/** Evidence categories. All are REFERENCES, never financial data. */
export type EvidenceKind =
  | "bank_confirmation"
  | "property_title"
  | "immigration_filing"
  | "immigration_receipt"
  | "other";

export type ScanSwitchState = "unprovisioned" | "disabled" | "enabled";

export type GuaranteeAlertSeverity = "info" | "warning" | "urgent" | "critical";

// ── Requests ──────────────────────────────────────────────────────────────────

/** POST /api/e33/cases body. */
export interface CreateCaseParams {
  client_id: number;
  basis: GuaranteeBasis;
  practice_id?: number;
  owner_email?: string;
  dependent_code?: DependentCode;
  principal_case_id?: string;
  note?: string;
}

/** GET /api/e33/cases query params. */
export interface ListCasesParams {
  stage?: E33Stage;
  client_id?: number;
  basis?: GuaranteeBasis;
  active_only?: boolean;
}

/** POST /api/e33/cases/{id}/advance body. */
export interface AdvanceCaseParams {
  to_stage: E33Stage;
  note?: string;
  /** ISO date (YYYY-MM-DD) — pins the legal date of ENTRY / ITAS_ACTIVE events. */
  occurred_on?: string;
}

/**
 * POST /api/e33/cases/{id}/evidence body.
 *
 * NOTE (frontend/backend contract seam — flagged for reconciliation): the
 * spec's endpoint 5 body uses `issuing_party` / `issued_on` / `filed_on` /
 * `note`, while the domain `EvidenceRef` dataclass fields are
 * `issued_date` / `filed_date` / `confirmed_by` (no `issuing_party`/`note`).
 * This type follows the spec's REQUEST body verbatim; `EvidenceRefView`
 * below (the response shape nested in CaseDetail.evidence) follows the
 * dataclass attribute names since the spec does not fix that shape
 * explicitly. If the backend router serializes evidence differently,
 * `EvidenceRefView` is the field to reconcile.
 */
export interface AddEvidenceParams {
  kind: EvidenceKind;
  document_ref: string;
  issuing_party?: string;
  /** ISO date (YYYY-MM-DD) */
  issued_on?: string;
  /** ISO date (YYYY-MM-DD) */
  filed_on?: string;
  note?: string;
  /** Reference-only key/value pairs — KEYS are validated server-side by
   *  `validate_evidence_metadata`; never put amount/account/balance data
   *  here. The console UI never exposes a generic metadata editor, but the
   *  type stays here for API completeness. */
  metadata?: Record<string, string>;
}

// ── Responses ─────────────────────────────────────────────────────────────────

export interface CaseSummary {
  case_id: string;
  client_id: number;
  client_name: string;
  basis: GuaranteeBasis;
  stage: E33Stage;
  owner_email?: string | null;
  /** ISO date, present once the Day-90 anchor (entry/ITAS) is known. */
  guarantee_proof_deadline?: string | null;
  stayguard_eligible: boolean;
  dependent_code?: string | null;
  principal_case_id?: string | null;
  created_at: string;
}

export interface CaseListResponse {
  cases: CaseSummary[];
  total: number;
}

/** One entry of `DEFAULT_DEPENDENT_CODES` linked to a principal case. */
export interface DependentLinkView {
  code: string;
  client_id: number;
  relationship: string;
  /** Not guaranteed by the spec's fixed shapes — optional convenience join. */
  client_name?: string;
}

/** Response shape for one evidence reference inside CaseDetail.evidence.
 *  Field names follow the `EvidenceRef` dataclass attributes (see NOTE on
 *  AddEvidenceParams above regarding the request/response naming seam). */
export interface EvidenceRefView {
  evidence_id: string;
  kind: EvidenceKind;
  document_ref: string;
  issued_date?: string | null;
  filed_date?: string | null;
  confirmed_by?: string | null;
  metadata?: Record<string, string>;
}

/** One append-only stage-history entry. Mirrors `StageTransition`. */
export interface StageTransitionView {
  from_stage: E33Stage | null;
  to_stage: E33Stage;
  at: string;
  actor?: string | null;
  note?: string | null;
}

export interface GuaranteeAlertMilestone {
  date: string;
  severity: GuaranteeAlertSeverity;
}

export interface GuaranteeInfo {
  deadline: string;
  days_remaining: number;
  alert_schedule: GuaranteeAlertMilestone[];
}

/** One entry from `build_case_forecasts` (ComplianceForecast) — shape is
 *  not pinned exactly by the spec, kept permissive with the fields the
 *  console actually renders. */
export interface CaseForecast {
  document_type: string;
  expiry_date: string;
  days_until_expiry: number;
  urgency_level: GuaranteeAlertSeverity | string;
  required_docs: string[];
  notes?: string | null;
  [key: string]: unknown;
}

export interface CaseDetail extends CaseSummary {
  entry_date?: string | null;
  itas_date?: string | null;
  dependents: DependentLinkView[];
  evidence: EvidenceRefView[];
  stage_history: StageTransitionView[];
  /** From VALID_TRANSITIONS minus itap_eval while the flag is off — TRUST
   *  this list over the client-side state-machine mirror when rendering
   *  the transition control. */
  allowed_next_stages: E33Stage[];
  guarantee: GuaranteeInfo | null;
  forecasts: CaseForecast[];
}

export interface SecondHomeSummary {
  by_stage: Partial<Record<E33Stage, number>>;
  active_total: number;
  guarantee_due_30d: number;
  scan_switch: ScanSwitchState;
}
