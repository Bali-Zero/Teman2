/**
 * Partners API client module
 * Spec §7.1 — CRM Partners Module
 * Uses the centralized api client for auth token management.
 */

import { api } from '@/lib/api';

// ─── TypeScript Interfaces ─────────────────────────────────────────────────

export type PartnerStatus = 'pending_review' | 'active' | 'inactive' | 'suspended';
export type EntityType = "individual" | "corporate_pt" | "corporate_cv" | "foreign";
export type CommissionTier = 'bronze' | 'silver' | 'gold' | 'platinum';
export type TaxWithholdingCategory = 'tbd' | 'withheld_tarif_umum' | 'withheld_tarif_final' | 'exempt';
export type CommissionStatus =
  | 'pending_approval'
  | 'approved'
  | 'ready_to_pay'
  | 'paid'
  | 'clawback_pending'
  | 'clawed_back'
  | 'waived';

export interface Partner {
  id: number;
  full_name: string;
  email: string;
  entity_type: EntityType;
  phone?: string;
  whatsapp?: string;
  nationality?: string;
  tax_id?: string;           // NPWP
  company_name?: string;
  work_role?: string;
  onboarding_status: PartnerStatus;
  commission_tier: CommissionTier;
  commission_rate_override?: number;
  payment_method?: string;
  bank_name?: string;
  bank_account_number?: string;
  bank_account_name?: string;
  tax_withholding_category: TaxWithholdingCategory;
  pdp_consent: boolean;
  pdp_consent_at?: string;
  assigned_to?: string;
  welcome_email_sent_at?: string;
  notes?: string;
  created_at: string;
  updated_at?: string;
  referral_count?: number;
  total_earned?: number;
}

export interface PartnerReferral {
  id: number;
  partner_id: number;
  referred_client_id?: number;
  referred_client_name?: string;
  referred_practice_id?: number;
  practice_type_name?: string;
  status: string;
  commission_amount?: number;
  commission_status: CommissionStatus;
  created_at: string;
}

export interface PartnerCommission {
  id: number;
  partner_id: number;
  partner_name?: string;
  referral_id?: number;
  practice_id?: number;
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
  tax_id?: string;
  company_name?: string;
  work_role?: string;
  commission_tier?: CommissionTier;
  commission_rate_override?: number;
  payment_method?: string;
  bank_name?: string;
  bank_account_number?: string;
  bank_account_name?: string;
  tax_withholding_category?: TaxWithholdingCategory;
  pdp_consent: boolean;
  assigned_to?: string;
  notes?: string;
}

export interface UpdatePartnerBody {
  full_name?: string;
  phone?: string;
  whatsapp?: string;
  nationality?: string;
  tax_id?: string;
  company_name?: string;
  work_role?: string;
  commission_tier?: CommissionTier;
  commission_rate_override?: number;
  payment_method?: string;
  bank_name?: string;
  bank_account_number?: string;
  bank_account_name?: string;
  tax_withholding_category?: TaxWithholdingCategory;
  notes?: string;
}

export interface ReassignBody {
  new_user_id: string;
  reason: string;
}

export interface BulkReassignBody {
  partner_ids: number[];
  new_user_id: string;
  reason: string;
}

export interface CreateReferralBody {
  process_id: number;
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

export interface MarkPaidBody {
  payment_reference?: string;
  paid_at?: string;
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

/** Get a single partner by ID */
export const getPartner = (id: number) =>
  api.get<Partner>(`${BASE}/${id}`);

/** Update partner profile fields (excludes onboarding_status, assigned_to, welcome_email_sent_at) */
export const updatePartner = (id: number, body: UpdatePartnerBody) =>
  api.patch<Partner>(`${BASE}/${id}`, body);

/** Activate a partner (set onboarding_status → active, triggers welcome email) */
export const activatePartner = (id: number) =>
  api.post<{ success: boolean; partner: Partner }>(`${BASE}/${id}/activate`, {});

/** Deactivate a partner */
export const deactivatePartner = (id: number) =>
  api.post<{ success: boolean }>(`${BASE}/${id}/deactivate`, {});

/** Suspend a partner */
export const suspendPartner = (id: number, reason?: string) =>
  api.post<{ success: boolean }>(`${BASE}/${id}/suspend`, { reason });

/** Reassign a partner to a different team member */
export const reassignPartner = (id: number, body: ReassignBody) =>
  api.post<{ success: boolean }>(`${BASE}/${id}/reassign`, body);

/** Bulk reassign multiple orphaned partners */
export const bulkReassign = (body: BulkReassignBody) =>
  api.post<{ success: boolean; updated_count: number }>(`${BASE}/bulk-reassign`, body);

/** Resend welcome email to a partner */
export const resendWelcomeEmail = (id: number) =>
  api.post<{ success: boolean }>(`${BASE}/${id}/resend-welcome`, {});

/** Create a referral for a partner (links a process to a partner) */
export const createReferral = (partnerId: number, body: CreateReferralBody) =>
  api.post<PartnerReferral>(`${BASE}/${partnerId}/referrals`, body);

/** List referrals for a specific partner */
export const listReferrals = (partnerId: number, params?: Record<string, string | number | null | undefined>) =>
  api.get<{ referrals: PartnerReferral[]; total: number }>(`${BASE}/${partnerId}/referrals${qs(params)}`);

/** List commissions for a specific partner */
export const listCommissions = (partnerId: number, params?: Record<string, string | number | null | undefined>) =>
  api.get<{ commissions: PartnerCommission[]; total: number }>(`${BASE}/${partnerId}/commissions${qs(params)}`);

/** List orphaned partners (assigned_to is null or empty) */
export const listOrphanedPartners = () =>
  api.get<{ partners: Partner[]; total: number }>(`${BASE}/orphaned`);

/** List all commissions for admin finance queue */
export const listAllCommissions = (params?: Record<string, string | number | null | undefined>) =>
  api.get<{ commissions: PartnerCommission[]; total: number; summary: Record<string, number> }>(`${BASE}/commissions${qs(params)}`);

/** Approve a commission */
export const approveCommission = (id: number) =>
  api.post<{ success: boolean; commission: PartnerCommission }>(`/api/partner-commissions/${id}/approve`, {});

/** Mark a commission as paid */
export const markPaid = (id: number, body: MarkPaidBody) =>
  api.post<{ success: boolean; commission: PartnerCommission }>(`/api/partner-commissions/${id}/mark-paid`, body);

/** Clawback a commission */
export const clawback = (id: number, body: ClawbackBody) =>
  api.post<{ success: boolean; commission: PartnerCommission }>(`/api/partner-commissions/${id}/clawback`, body);

/** Waive a commission */
export const waive = (id: number, body: WaiveBody) =>
  api.post<{ success: boolean; commission: PartnerCommission }>(`/api/partner-commissions/${id}/waive`, body);

/** Export finance CSV (pending/ready-to-pay commissions) */
export const exportFinanceCsv = (from?: string, to?: string): string => {
  const params: Record<string, string> = {};
  if (from) params['from'] = from;
  if (to) params['to'] = to;
  return `${api.getBaseUrl()}${BASE}/commissions/export${qs(params)}`;
};

/** Get active partners list for dropdown (scoped by caller role) */
export const listActivePartnersDropdown = () =>
  api.get<PartnerListResponse>(`${BASE}?status=active&page_size=200`);

/** List audit log entries for a partner */
export const listAuditLog = (partnerId: number) =>
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
