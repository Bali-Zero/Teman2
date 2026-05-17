/**
 * Portal API Types
 * Types for the client-facing portal
 */

// ============================================================================
// Dashboard Types
// ============================================================================

export interface PortalDashboard {
  visa: {
    status: "active" | "pending" | "warning" | "expired" | "none";
    type: string | null;
    expiryDate: string | null;
    daysRemaining: number | null;
  };
  company: {
    status: "active" | "pending" | "none";
    primaryCompanyName: string | null;
    totalCompanies: number;
  };
  taxes: {
    status: "compliant" | "attention" | "overdue";
    nextDeadline: string | null;
    daysToDeadline: number | null;
  };
  documents: {
    total: number;
    pending: number;
  };
  messages: {
    unread: number;
  };
  actions: PortalAction[];
}

export interface PortalAction {
  id: string;
  title: string;
  description: string;
  priority: "high" | "medium" | "low";
  type: string;
  href: string;
}

// ============================================================================
// Visa Types
// ============================================================================

export interface VisaInfo {
  current: {
    type: string;
    status: "active" | "pending" | "warning" | "expired";
    issueDate: string;
    expiryDate: string;
    daysRemaining: number;
    permitNumber: string;
    sponsor: string;
  } | null;
  history: VisaHistoryItem[];
  documents: PortalDocument[];
}

export interface VisaHistoryItem {
  id: string;
  type: string;
  period: string;
  status: "completed" | "expired";
}

// ============================================================================
// Company Types
// ============================================================================

export interface PortalCompany {
  id: number;
  // /api/portal/companies returns id=client_company_links.id (the relation row)
  // and company_id=companies.id (the real company). The detail endpoint needs
  // the latter — keep both so the list can route correctly.
  company_id?: number;
  name: string;
  type: string;
  status: "active" | "pending";
  isPrimary: boolean;
  address?: string;
  nib?: string;
  npwp?: string;
  kbli?: string;
  email?: string;
  phone?: string;
  aktaNo?: string;
  aktaDate?: string;
  // Legacy snake_case alternatives that may come from the workspace shape
  // when the portal endpoint is refactored — typed so the company detail
  // page can read either without runtime casts.
  akta_pendirian_no?: string;
  akta_pendirian_date?: string;
  akta_perubahan_no?: string;
  akta_perubahan_date?: string;
  skNumber?: string;
  taxOffice?: string;
  companyStatus?: string;
  investmentType?: string;
  authorizedCapital?: string | null;
  directors?: string[];
  shareholders?: { name: string; pct: number | null }[];
  documents?: Array<{ id?: string; name?: string; url?: string }>;
  licenses?: CompanyLicense[];
  compliance?: ComplianceItem[];
}

export interface CompanyLicense {
  id: string;
  name: string;
  status: "active" | "expiring" | "expired";
  expiryDate: string;
  daysRemaining?: number;
}

export interface ComplianceItem {
  id: string;
  name: string;
  dueDate: string;
  status: "upcoming" | "overdue" | "completed";
}

// ============================================================================
// Tax Types
// ============================================================================

export interface TaxOverview {
  summary: {
    status: "ok" | "attention" | "critical";
    totalDue: number;
    nextDeadline: string | null;
    daysToDeadline: number | null;
    pendingCount: number;
    overdueCount: number;
  };
  obligations: TaxObligation[];
}

export interface TaxObligation {
  id: string;
  name: string;
  type: string;
  period: string;
  dueDate: string;
  status: "pending" | "upcoming" | "filed" | "paid" | "overdue";
  amount?: number;
}

export interface TaxHistoryItem {
  id: string;
  name: string;
  period: string;
  filedDate: string;
  amount: number;
}

// ============================================================================
// Document Types
// ============================================================================

export interface PortalDocument {
  id: number | string;
  name: string;
  type: string;
  category: string;
  status: "verified" | "pending" | "received" | "rejected" | "expired";
  uploadDate: string;
  expiryDate?: string;
  size: string;
  downloadUrl?: string;
}

// ============================================================================
// Message Types
// ============================================================================

export interface PortalMessage {
  id: string;
  content: string;
  direction: "client_to_team" | "team_to_client";
  sentBy: string;
  subject?: string;
  practiceId?: number;
  practiceName?: string;
  createdAt: string;
  readAt?: string;
}

export interface MessagesResponse {
  messages: PortalMessage[];
  total: number;
  unreadCount: number;
}

export interface SendMessageRequest {
  content: string;
  subject?: string;
  practiceId?: number;
}

// ============================================================================
// Settings Types
// ============================================================================

export interface PortalPreferences {
  emailNotifications: boolean;
  whatsappNotifications: boolean;
  language: string;
  timezone: string;
}

export interface AssignedTeamMember {
  email: string;
  name: string;
  avatarUrl?: string;
}

export interface PortalProfile {
  id: number;
  fullName: string;
  email: string;
  phone?: string;
  whatsapp?: string;
  nationality?: string;
  passportNumber?: string;
  passportExpiry?: string;
  dateOfBirth?: string;
  gender?: "M" | "F";
  address?: string;
  memberSince: string;
  assignedTo?: AssignedTeamMember;
}

// ============================================================================
// Invitation Types
// ============================================================================

export interface InviteValidationResponse {
  valid: boolean;
  error?: string;
  message?: string;
  clientName?: string;
  email?: string;
  invitationId?: number;
  clientId?: number;
}

export interface CompleteRegistrationRequest {
  token: string;
  pin: string;
}

export interface RegistrationResponse {
  success: boolean;
  message: string;
  userId?: string; // UUID string from team_members
  redirectTo?: string;
}

// ============================================================================
// LKPM Types (Investment Activity Reports)
// ============================================================================

// Matches backend/app/models/lkpm.py:InvestmentRealization.
// Backend splits only the three categories that can be imported
// (equipment, building, vehicle). Land, working_capital, and "other" are
// single-column totals (no import distinction per OSS schema).
export interface LKPMInvestmentRealization {
  equipment_domestic: number;
  equipment_import: number;
  building_domestic: number;
  building_import: number;
  vehicle_domestic: number;
  vehicle_import: number;
  land: number;
  working_capital: number;
  other: number;
  total_domestic: number;
  total_import: number;
  grand_total: number;
}

export interface LKPMEmploymentData {
  tki: number;
  tka: number;
  total: number;
}

export interface LKPMValidationAlert {
  field: string;
  severity: "red" | "yellow" | "green";
  message: string;
  details?: string;
}

export interface LKPMDraftSummary {
  id: number;
  quarter: string;
  year: number;
  status:
    | "draft"
    | "validated"
    | "client_review"
    | "approved"
    | "submitted"
    | "archived";
  realized_total: number;
  oss_submitted?: boolean;
  oss_receipt_number?: string | null;
  client_approved?: boolean;
  lkpm_assigned_to?: string | null;
  days_to_deadline?: number | null;
  created_at: string;
  updated_at: string;
}

export interface LKPMDraft {
  id: number;
  client_id: number;
  quarter: string;
  year: number;
  status:
    | "draft"
    | "validated"
    | "client_review"
    | "approved"
    | "submitted"
    | "archived";
  realized: LKPMInvestmentRealization;
  cumulative: LKPMInvestmentRealization;
  employment: LKPMEmploymentData;
  revenue_quarterly?: number;
  revenue_annual?: number;
  obstacles?: string;
  plans?: string;
  validation_alerts: LKPMValidationAlert[];
  data_source: string;
  created_at: string;
  updated_at: string;
}

export interface LKPMReadyPack {
  draft_id: number;
  company_name: string;
  quarter: string;
  year: number;
  realized: LKPMInvestmentRealization;
  cumulative: LKPMInvestmentRealization;
  employment: LKPMEmploymentData;
  validation_summary: {
    is_valid: boolean;
    red_count: number;
    yellow_count: number;
    green_count: number;
  };
  html_content: string;
}

export interface LKPMBatchItem {
  id: number;
  client_id: number;
  company_name: string;
  quarter: string;
  year: number;
  status:
    | "draft"
    | "validated"
    | "client_review"
    | "approved"
    | "submitted"
    | "archived";
  realized_total: number;
  red_alerts: number;
  yellow_alerts: number;
  oss_submitted: boolean;
  oss_receipt_number?: string | null;
  client_approved: boolean;
  lkpm_assigned_to?: string | null;
  days_to_deadline?: number | null;
  updated_at: string;
}

export interface LKPMOSSCredentials {
  client_id: number;
  company_name: string;
  oss_username: string | null;
  oss_password: string | null;
  oss_creds_updated_at: string | null;
  oss_creds_updated_by: string | null;
}

/**
 * OSS "Tanda Terima" receipt — one per Nomor Kegiatan Usaha.
 * A lkpm_report typically has 1–5 of these.
 * Schema: `lkpm_receipts` (migration 100).
 */
export interface LKPMReceipt {
  id: number;
  lkpm_report_id: number;
  nomor_laporan: string;
  nomor_kegiatan_usaha: string;
  kbli_code: string | null;
  kegiatan_usaha_desc: string | null;
  stage: string | null; // "KONSTRUKSI" | "PRODUKSI"
  oss_status: string | null; // "Terkirim" | "Disetujui"
  lokasi: string | null;
  tanggal_diterima: string | null; // ISO date
  nama_perusahaan_oss: string | null;
  file_drive_id: string | null;
  file_drive_url: string | null;
  file_name: string | null;
  // Joined from lkpm_reports when returned by /receipts/me and /receipts/by-client:
  quarter?: string;
  year?: number;
  client_id?: number;
  company_id?: number;
  company_name?: string;
}

export interface LKPMDeadline {
  quarter: string;
  year: number;
  deadline: string;
  days_remaining: number;
  is_overdue: boolean;
}

// ============================================================================
// API Response Types
// ============================================================================

export interface PortalApiResponse<T> {
  success: boolean;
  data?: T;
  message?: string;
  error?: string;
}

// ============================================================================
// Process Timeline Types
// ============================================================================

export interface ProcessTimelineStep {
  status: string;
  label: string;
  completed: boolean;
  is_current: boolean;
  changed_at: string | null;
  changed_by: string | null;
}

export interface ProcessTimeline {
  practice_id: number;
  practice_name: string;
  practice_category: string;
  current_status: string;
  assigned_to: string | null;
  start_date: string | null;
  completion_date: string | null;
  expiry_date: string | null;
  steps: ProcessTimelineStep[];
}

// ============================================================================
// Drive File Types
// ============================================================================

export interface DriveFolder {
  id: string;
  name: string;
}

export interface DriveFilesResponse {
  root_id?: string;
  root_name?: string;
  folders: DriveFolder[];
  total_files: number;
  total_size_bytes?: number;
  message?: string;
}

// ============================================================================
// Billing Types
// ============================================================================

export interface PortalInvoice {
  id: number;
  invoice_number: string;
  amount_idr: number;
  invoice_source: string;
  has_pdf: boolean;
  drive_web_link?: null;
  email_sent: boolean;
  generated_at: string | null;
  created_at: string | null;
  practice_id: number;
  practice_name: string;
  practice_category: string;
  payment_status: string;
}

export interface BillingSummary {
  total_invoiced: number;
  total_paid: number;
  total_pending: number;
  count: number;
}

export interface BillingResponse {
  invoices: PortalInvoice[];
  summary: BillingSummary;
}

// ============================================================================
// Profile Update Types
// ============================================================================

export interface UpdateProfileRequest {
  phone?: string;
  whatsapp?: string;
  address?: string;
  language?: string;
}

// ============================================================================
// Notification Types
// ============================================================================

export interface PortalNotification {
  id: number;
  type: string;
  title: string;
  body: string | null;
  data: string | null;
  read: boolean;
  created_at: string | null;
}

export interface NotificationsResponse {
  notifications: PortalNotification[];
  unread_count: number;
}

// V2 Matter-first dashboard summary (3 hero cards)
export interface DashboardSummaryAction {
  id: number | string;
  title: string;
  type: string | null;
  pending_from_client: string | null;
  status: string | null;
}

export interface DashboardSummaryDeadline {
  id: string;
  label: string;
  due_date: string | null;
  kind: string | null;
}

export interface DashboardSummary {
  open_actions: DashboardSummaryAction[];
  upcoming_deadlines: DashboardSummaryDeadline[];
  unread_messages: number;
}

export interface PortalMatter {
  id: number;
  title: string;
  type: "visa" | "company" | "tax" | "property" | "other";
  progress: number;
  pending_docs: string[];
  next_deadline: string | null;
  next_step: string | null;
}

export interface PortalApprovedIntelligenceFact {
  category: "identity" | "person" | "compliance";
  label: string;
  detail: string;
  confidence: string;
}

export interface PortalApprovedIntelligence {
  available: boolean;
  status: "approved" | "pending";
  company_name: string | null;
  summary: string | null;
  last_reviewed_at: string | null;
  facts: PortalApprovedIntelligenceFact[];
  missing_items: string[];
  next_steps: string[];
}

export interface PortalMatterDetail extends PortalMatter {
  status_label: string;
  description: string;
  approved_intelligence: PortalApprovedIntelligence;
}
