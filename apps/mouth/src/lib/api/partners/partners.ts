/**
 * Partners API client module
 * Spec §7.1 — CRM Partners Module
 * Uses the centralized api client for auth token management.
 */

import { api } from '@/lib/api';

// ─── TypeScript Interfaces ─────────────────────────────────────────────────

// CRIT-8: PartnerStatus aligned to backend Literal (migration 119 + models.py).
// 'pending_approval' replaces legacy 'pending_review'. 'suspended' dropped —
// backend has no suspend endpoint; use deactivate instead.
export type PartnerStatus = 'pending_approval' | 'active' | 'inactive';
export type EntityType = "individual" | "corporate_pt" | "corporate_cv" | "foreign";
// NB: "foreign" is accepted by the type but REJECTED by the backend service
// layer as of 2026-04-21 (CRIT-5). Do not offer it in UI dropdowns until
// v1.1 splits into foreign_kitap / foreign_offshore.
// See: docs/superpowers/reviews/2026-04-21-partners-v1/04-nb2.md
// CRIT-8: CommissionTier removed — backend uses default_commission_type + default_commission_value.
// Kept here as a local UI-only enum so TierBadge / ReferrerDropdown display still compiles.
// The field is NOT sent in create/update payloads.
export type CommissionTier = 'bronze' | 'silver' | 'gold' | 'platinum';
// CRIT-8: aligned to backend Literal — pph21/pph23 replace legacy withheld_tarif_umum/final.
export type TaxWithholdingCategory = 'tbd' | 'pph21' | 'pph23' | 'exempt';
// CommissionStatus: values confirmed from commission engine FSM + migration 119.
// Legacy values (pending_approval, ready_to_pay, clawed_back) kept as defensive
// union members in case older records surface; backend will not emit them going forward.
export type CommissionStatus =
  | 'accrued'           // commission engine FSM
  | 'approved'
  | 'paid'
  | 'clawback_pending'
  | 'offset_applied'    // commission engine FSM
  | 'waived'
  | 'repaid'            // commission engine FSM
  // defensive: legacy values that may exist in older records
  | 'pending_approval'
  | 'ready_to_pay'
  | 'clawed_back';

export interface Partner {
  // CRIT-8: id is UUID (string), not number. Number(uuid) → NaN.
  id: string;
  full_name: string;
  email: string;
  entity_type: EntityType;
  phone?: string;
  whatsapp?: string;
  nationality?: string;
  // CRIT-8: backend field is 'npwp', not 'tax_id'.
  npwp?: string;
  company_name?: string;
  work_role?: string;
  onboarding_status: PartnerStatus;
  // commission_tier is a display-only field. Backend uses
  // default_commission_type + default_commission_value instead.
  // Included here for TierBadge / ReferrerDropdown display compatibility.
  commission_tier?: CommissionTier;
  default_commission_type?: 'percentage' | 'flat';
  default_commission_value?: number | string;
  commission_rate_override?: number;
  payment_method?: string;
  bank_name?: string;
  bank_account_number?: string;
  // CRIT-8: backend field is 'bank_account_holder', not 'bank_account_name'.
  bank_account_holder?: string;
  tax_withholding_category: TaxWithholdingCategory;
  // pdp_consent (boolean) is not emitted by the backend; use pdp_consent_at presence.
  pdp_consent_at?: string;
  pdp_consent_version?: string;
  assigned_to?: string;
  welcome_email_sent_at?: string;
  notes?: string;
  created_at: string;
  updated_at?: string;
  referral_count?: number;
  total_earned?: number;
}

export interface PartnerReferral {
  // CRIT-8: all IDs are UUIDs (strings)
  id: string;
  partner_id: string;
  referred_client_id?: string;
  referred_client_name?: string;      // kept for backward-compat with team-side endpoints
  client_display?: string;            // from /api/partners/me/referrals (sterilized name)
  referred_practice_id?: string;
  practice_id?: string;
  process_status?: string;            // from /me/referrals
  practice_type_name?: string;
  service_type?: string;              // from /me/referrals
  status: string;
  commission_amount?: number;
  commission_status: CommissionStatus;
  created_at: string;
  referred_at?: string;               // /me/referrals uses this instead of created_at
}

export interface PartnerCommission {
  // CRIT-8: all IDs are UUIDs (strings)
  id: string;
  partner_id: string;
  partner_name?: string;
  referral_id?: string;
  practice_id?: string;
  practice_type_name?: string;
  client_name?: string;
  gross_amount: number;
  withholding_amount: number;
  net_amount: number;
  status: CommissionStatus;
  approved_by?: string;
  approved_at?: string;
  paid_at?: string;
  payment_reference?: string;
  clawback_reason?: string;
  waive_reason?: string;
  created_at: string;
  updated_at?: string;
}

export interface PartnerListResponse {
  partners: Partner[];
  total: number;
  page: number;
  page_size: number;
}

export interface PartnerFilters {
  status?: string;
  assigned_to?: string;
  orphaned?: boolean;
  search?: string;
  page?: number;
  page_size?: number;
}

export interface CreatePartnerBody {
  full_name: string;
  email: string;
  entity_type: EntityType;
  phone?: string;
  whatsapp?: string;
  nationality?: string;
  // CRIT-8: backend field is 'npwp', not 'tax_id'
  npwp?: string;
  company_name?: string;
  work_role?: string;
  // CRIT-8: backend uses default_commission_type + default_commission_value, not commission_tier
  default_commission_type?: 'percentage' | 'flat';
  default_commission_value?: number;
  bank_name?: string;
  bank_account_number?: string;
  // CRIT-8: backend field is 'bank_account_holder', not 'bank_account_name'
  bank_account_holder?: string;
  tax_withholding_category?: TaxWithholdingCategory;
  // pdp_consent (boolean) is not in the backend PartnerCreate model.
  // Send pdp_consent_version instead when the user checks the consent box.
  pdp_consent_version?: string;
  assigned_to?: string;
  notes?: string;
}

export interface UpdatePartnerBody {
  full_name?: string;
  phone?: string;
  whatsapp?: string;
  nationality?: string;
  // CRIT-8: backend field is 'npwp', not 'tax_id'
  npwp?: string;
  company_name?: string;
  work_role?: string;
  // CRIT-8: backend uses default_commission_type + default_commission_value, not commission_tier
  default_commission_type?: 'percentage' | 'flat';
  default_commission_value?: number;
  bank_name?: string;
  bank_account_number?: string;
  // CRIT-8: backend field is 'bank_account_holder', not 'bank_account_name'
  bank_account_holder?: string;
  tax_withholding_category?: TaxWithholdingCategory;
  notes?: string;
}

export interface ReassignBody {
  new_user_id: string;
  reason: string;
}

export interface BulkReassignBody {
  // CRIT-8: partner_ids are UUID strings
  partner_ids: string[];
  new_user_id: string;
  reason: string;
}

export interface CreateReferralBody {
  // CRIT-8: practice_id is UUID string
  practice_id: string;
  notes?: string;
}

export interface AuditLogEntry {
  id: string;
  partner_id: string;
  actor_user_id: string | null;
  action: string;
  before_json: Record<string, unknown> | null;
  after_json: Record<string, unknown> | null;
  reason: string | null;
  at: string;
}

// CRIT-8: aligned to backend CommissionMarkPaidRequest.
// paid_via + payment_reference are REQUIRED by the backend; sending
// undefined returns 422. Callers must validate prompt/input before invoking.
export interface MarkPaidBody {
  paid_via: string;
  payment_reference: string;
  payment_proof_url?: string;
  receipt_type?: 'kwitansi' | 'invoice' | 'none';
  receipt_file_url?: string;
}

export interface ClawbackBody {
  reason: string;
}

export interface WaiveBody {
  reason: string;
}

// ─── Query String Helper ────────────────────────────────────────────────────

function qs(params?: Record<string, string | number | boolean | null | undefined>): string {
  if (!params) return '';
  const entries = Object.entries(params).filter(
    (entry): entry is [string, string | number | boolean] => entry[1] != null,
  );
  return entries.length
    ? '?' + new URLSearchParams(entries.map(([k, v]) => [k, String(v)])).toString()
    : '';
}

const BASE = '/api/partners';

// ─── API Functions ──────────────────────────────────────────────────────────

/** List partners with optional filters */
export const listPartners = (filters?: PartnerFilters) =>
  api.get<PartnerListResponse>(`${BASE}${qs(filters as Record<string, string | number | boolean | null | undefined>)}`);

/** Create a new partner */
export const createPartner = (body: CreatePartnerBody) =>
  api.post<Partner>(`${BASE}`, body);

/** Get a single partner by ID (UUID string) */
export const getPartner = (id: string) =>
  api.get<Partner>(`${BASE}/${id}`);

/** Update partner profile fields (excludes onboarding_status, assigned_to, welcome_email_sent_at) */
export const updatePartner = (id: string, body: UpdatePartnerBody) =>
  api.patch<Partner>(`${BASE}/${id}`, body);

/** Activate a partner (set onboarding_status → active, triggers welcome email) */
export const activatePartner = (id: string) =>
  api.post<{ success: boolean; partner: Partner }>(`${BASE}/${id}/activate`, {});

/** Deactivate a partner */
export const deactivatePartner = (id: string) =>
  api.post<{ success: boolean }>(`${BASE}/${id}/deactivate`, {});

// NOTE: suspendPartner removed — backend has no /suspend endpoint.
// Use deactivatePartner instead. v1.1 may re-introduce suspend as a distinct state.

/** Reassign a partner to a different team member */
export const reassignPartner = (id: string, body: ReassignBody) =>
  api.post<{ success: boolean }>(`${BASE}/${id}/reassign`, body);

/** Bulk reassign multiple orphaned partners */
export const bulkReassign = (body: BulkReassignBody) =>
  api.post<{ success: boolean; updated_count: number }>(`${BASE}/bulk-reassign`, body);

// NOTE: resendWelcomeEmail removed — backend has no /resend-welcome endpoint.
// v1 welcome email is sent atomically on activation via outbox. v1.1 may add manual resend.

/** Create a referral for a partner (links a practice to a partner) */
export const createReferral = (partnerId: string, body: CreateReferralBody) =>
  api.post<PartnerReferral>(`${BASE}/${partnerId}/referrals`, body);

/** List referrals for a specific partner */
export const listReferrals = (partnerId: string, params?: Record<string, string | number | null | undefined>) =>
  api.get<{ referrals: PartnerReferral[]; total: number }>(`${BASE}/${partnerId}/referrals${qs(params)}`);

/** List commissions for a specific partner */
export const listCommissions = (partnerId: string, params?: Record<string, string | number | null | undefined>) =>
  api.get<{ commissions: PartnerCommission[]; total: number }>(`${BASE}/${partnerId}/commissions${qs(params)}`);

/** List orphaned partners (assigned_to is null or empty) */
export const listOrphanedPartners = () =>
  api.get<{ partners: Partner[]; total: number }>(`${BASE}/orphaned`);

/** List all commissions for admin finance queue */
export const listAllCommissions = (params?: Record<string, string | number | null | undefined>) =>
  api.get<{ commissions: PartnerCommission[]; total: number; summary: Record<string, number> }>(`${BASE}/commissions${qs(params)}`);

/** Approve a commission */
// CRIT-8: was /api/partner-commissions/{id}/approve — corrected to /api/partners/commissions/{id}/approve
export const approveCommission = (id: string) =>
  api.post<{ success: boolean; commission: PartnerCommission }>(`${BASE}/commissions/${id}/approve`, {});

/** Mark a commission as paid */
// CRIT-8: was /api/partner-commissions/{id}/mark-paid — corrected
export const markPaid = (id: string, body: MarkPaidBody) =>
  api.post<{ success: boolean; commission: PartnerCommission }>(`${BASE}/commissions/${id}/mark-paid`, body);

/** Clawback a commission */
// CRIT-8: was /api/partner-commissions/{id}/clawback — corrected
export const clawback = (id: string, body: ClawbackBody) =>
  api.post<{ success: boolean; commission: PartnerCommission }>(`${BASE}/commissions/${id}/clawback`, body);

/** Waive a commission */
// CRIT-8: was /api/partner-commissions/{id}/waive — corrected
export const waive = (id: string, body: WaiveBody) =>
  api.post<{ success: boolean; commission: PartnerCommission }>(`${BASE}/commissions/${id}/waive`, body);

/** Export finance CSV (pending/ready-to-pay commissions) */
// CRIT-8: was /api/partners/commissions/export — corrected to /api/partners/finance/export
export const exportFinanceCsv = (from?: string, to?: string): string => {
  const params: Record<string, string> = {};
  if (from) params['from'] = from;
  if (to) params['to'] = to;
  return `${api.getBaseUrl()}${BASE}/finance/export${qs(params)}`;
};

/** Get active partners list for dropdown (scoped by caller role) */
export const listActivePartnersDropdown = () =>
  api.get<PartnerListResponse>(`${BASE}?status=active&page_size=200`);

/** List audit log entries for a partner */
export const listAuditLog = (partnerId: string) =>
  api.get<AuditLogEntry[]>(`${BASE}/${partnerId}/audit-log`);

// ─── Partner Self-View (role=partner) ──────────────────────────────────────

/** Get the authenticated partner's own profile */
export const getMe = () =>
  api.get<Partner>(`${BASE}/me`);

/** Get the authenticated partner's own referrals (client names already sterilized) */
export const getMyReferrals = () =>
  api.get<PartnerReferral[]>(`${BASE}/me/referrals`);

/** Get the authenticated partner's own commissions ledger */
export const getMyCommissions = () =>
  api.get<PartnerCommission[]>(`${BASE}/me/commissions`);
