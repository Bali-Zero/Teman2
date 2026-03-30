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
  skNumber?: string;
  taxOffice?: string;
  companyStatus?: string;
  investmentType?: string;
  authorizedCapital?: string;
  directors: string[];
  shareholders?: { name: string; pct: number | null }[];
  licenses: CompanyLicense[];
  compliance: ComplianceItem[];
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
    status: "compliant" | "attention" | "overdue";
    totalDue: number;
    nextDeadline: string | null;
    daysToDeadline: number | null;
  };
  obligations: TaxObligation[];
  history: TaxHistoryItem[];
}

export interface TaxObligation {
  id: string;
  name: string;
  type: string;
  period: string;
  dueDate: string;
  status: "pending" | "filed" | "overdue";
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

export interface LKPMInvestmentRealization {
  land_building_domestic: number;
  land_building_import: number;
  machinery_domestic: number;
  machinery_import: number;
  equipment_domestic: number;
  equipment_import: number;
  vehicles_domestic: number;
  vehicles_import: number;
  other_fixed_domestic: number;
  other_fixed_import: number;
  working_capital_domestic: number;
  working_capital_import: number;
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
  status: "draft" | "validated" | "approved" | "submitted";
  realized_total: number;
  created_at: string;
  updated_at: string;
}

export interface LKPMDraft {
  id: number;
  client_id: number;
  quarter: string;
  year: number;
  status: "draft" | "validated" | "approved" | "submitted";
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
  status: "draft" | "validated" | "approved" | "submitted";
  realized_total: number;
  red_alerts: number;
  yellow_alerts: number;
  updated_at: string;
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
  drive_web_link: string | null;
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
