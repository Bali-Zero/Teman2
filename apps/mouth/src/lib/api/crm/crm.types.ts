export interface StatusTransition {
  status: string;
  at: string; // ISO timestamp
}

export interface Practice {
  id: number;
  uuid?: string;
  client_id: number;
  client_name?: string;
  client_email?: string;
  client_phone?: string;
  client_lead?: string; // Lead team member assigned to client
  practice_type_id: number;
  practice_type_name?: string;
  practice_type_code?: string;
  status: string;
  priority: string;
  quoted_price?: number;
  actual_price?: number;
  payment_status: string;
  assigned_to?: string;
  start_date?: string;
  completion_date?: string;
  expiry_date?: string;
  notes?: string;
  created_at: string;
  updated_at?: string;
  status_transitions?: StatusTransition[];
}

import type { JsonObject } from "../../types/common";

export interface Interaction {
  id: number;
  client_id?: number;
  client_name?: string;
  practice_id?: number;
  conversation_id?: number;
  interaction_type: "chat" | "email" | "whatsapp" | "call" | "meeting" | "note";
  channel?: string;
  subject?: string;
  summary?: string;
  full_content?: string;
  sentiment?: string;
  team_member: string;
  direction: "inbound" | "outbound";
  interaction_date: string;
  created_at: string;
  read_receipt?: boolean; // [NEW] Real read receipt status
  read_at?: string; // [NEW] When interaction was marked as read
  read_by?: string; // [NEW] Who marked it as read
  extracted_entities?: JsonObject; // [NEW] AI extracted entities
}

export interface PracticeStats {
  total_practices: number;
  active_practices: number;
  by_status: Record<string, number>;
  by_type: Array<{ code: string; name: string; count: number }>;
  revenue: {
    total_revenue: number;
    paid_revenue: number;
    outstanding_revenue: number;
  };
}

export interface InteractionStats {
  total_interactions: number;
  last_7_days: number;
  by_type: Record<string, number>;
  by_sentiment: Record<string, number>;
  by_team_member: Array<{ team_member: string; count: number }>;
}

export interface DashboardStats {
  practices: PracticeStats;
  interactions: InteractionStats;
}

export interface Client {
  id: number;
  uuid: string;
  full_name: string;
  email?: string;
  phone?: string;
  whatsapp?: string;
  nationality?: string;
  passport_number?: string;
  passport_expiry?: string;
  date_of_birth?: string;
  gender?: "M" | "F";
  birthplace?: string;
  address?: string;
  notes?: string;
  google_drive_folder_id?: string;
  status: "lead" | "active" | "completed" | "lost" | "inactive";
  client_type: "individual" | "company";
  assigned_to?: string;
  avatar_url?: string;
  company_name?: string;
  first_contact_date?: string;
  last_interaction_date?: string;
  last_sentiment?: string;
  last_interaction_summary?: string;
  tags?: string[];
  created_at: string;
  updated_at: string;
}

// ============================================
// FAMILY MEMBERS
// ============================================

export interface FamilyMember {
  id: number;
  client_id: number;
  full_name: string;
  relationship:
    | "spouse"
    | "child"
    | "parent"
    | "sibling"
    | "dependent"
    | "other";
  date_of_birth?: string;
  nationality?: string;
  passport_number?: string;
  passport_expiry?: string;
  current_visa_type?: string;
  visa_expiry?: string;
  email?: string;
  phone?: string;
  notes?: string;
  passport_alert?: "green" | "yellow" | "red" | "expired";
  visa_alert?: "green" | "yellow" | "red" | "expired";
  created_at?: string;
  updated_at?: string;
}

export interface FamilyMemberCreate {
  full_name: string;
  relationship: string;
  date_of_birth?: string;
  nationality?: string;
  passport_number?: string;
  passport_expiry?: string;
  current_visa_type?: string;
  visa_expiry?: string;
  email?: string;
  phone?: string;
  notes?: string;
}

// ============================================
// DOCUMENTS
// ============================================

export type DocumentCategoryType =
  | "immigration"
  | "pma"
  | "tax"
  | "personal"
  | "other";

export interface ClientDocument {
  id: number;
  client_id: number;
  document_type: string;
  document_category?: DocumentCategoryType;
  file_name?: string;
  file_id?: string;
  file_url?: string;
  google_drive_file_url?: string;
  status?: "pending" | "received" | "verified" | "rejected" | "expired";
  issue_date?: string;
  expiry_date?: string;
  notes?: string;
  is_archived?: boolean;
  family_member_id?: number;
  family_member_name?: string;
  practice_id?: number;
  alert_color?: "green" | "yellow" | "red" | "expired";
  created_at?: string;
  updated_at?: string;
}

export interface DocumentCreate {
  document_type: string;
  document_category?: DocumentCategoryType;
  file_name?: string;
  file_id?: string;
  file_url?: string;
  google_drive_file_url?: string;
  expiry_date?: string;
  notes?: string;
  family_member_id?: number;
  practice_id?: number;
}

export interface DocumentCategory {
  code: string;
  name: string;
  category_group: "immigration" | "pma" | "tax" | "personal" | "other";
  description?: string;
  has_expiry: boolean;
}

// ============================================
// EXPIRY ALERTS
// ============================================

export interface ExpiryAlert {
  entity_type: "client" | "family_member" | "document";
  entity_id: number;
  entity_name: string;
  client_id: number;
  client_name: string;
  document_type: string;
  expiry_date: string;
  days_until_expiry: number;
  alert_color: "green" | "yellow" | "red" | "expired";
  assigned_to?: string;
}

export interface ExpiryAlertsSummary {
  counts: {
    expired: number;
    red: number;
    yellow: number;
    green: number;
  };
  urgent_alerts: Array<{
    client_name: string;
    entity_name: string;
    document_type: string;
    expiry_date: string;
    days_until_expiry: number;
    alert_color: string;
  }>;
}

// ============================================
// CLIENT PROFILE (Enhanced)
// ============================================

export interface ClientProfile {
  client: Client;
  family_members: FamilyMember[];
  documents: ClientDocument[];
  expiry_alerts: ExpiryAlert[];
  practices: Array<{
    id: number;
    status: string;
    priority?: string;
    expiry_date?: string;
    start_date?: string;
    completion_date?: string;
    estimated_completion?: string;
    title?: string;
    practice_type_code: string;
    practice_type_name: string;
    alert_color?: string;
    quoted_price?: number;
    actual_price?: number;
    payment_status?: string;
    assigned_to?: string;
  }>;
  company_links?: ClientCompanyLink[];
  stats: {
    family_count: number;
    documents_count: number;
    practices_count: number;
    company_count?: number;
    expired_count: number;
    red_alerts: number;
    yellow_alerts: number;
  };
}

export interface ClientSummary {
  client: Client;
  practices: {
    total: number;
    active: number;
    completed: number;
    items: Practice[];
  };
  interactions: {
    total: number;
    recent: Interaction[];
  };
  revenue: {
    total: number;
    paid: number;
    outstanding: number;
  };
  renewals: RenewalAlert[];
}

export interface CreateClientParams {
  full_name: string;
  email?: string;
  phone?: string;
  whatsapp?: string;
  company_name?: string;
  nationality?: string;
  passport_number?: string;
  passport_expiry?: string;
  date_of_birth?: string;
  gender?: "M" | "F";
  birthplace?: string;
  notes?: string;
  status?: "lead" | "active" | "completed" | "lost" | "inactive";
  client_type?: "individual" | "company";
  assigned_to?: string;
  tags?: string[];
  address?: string;
  lead_source?:
    | "website"
    | "whatsapp"
    | "referral"
    | "social_media"
    | "walk_in"
    | "other";
  service_interest?: string[]; // e.g., ['kitas', 'pt_pma', 'tax']
  avatar_url?: string;
}

// Common nationalities for dropdown
export const COMMON_NATIONALITIES = [
  "Australian",
  "American",
  "British",
  "Canadian",
  "Chinese",
  "Dutch",
  "French",
  "German",
  "Indian",
  "Indonesian",
  "Italian",
  "Japanese",
  "Korean",
  "Malaysian",
  "Russian",
  "Singaporean",
  "Spanish",
  "Swedish",
  "Swiss",
  "Ukrainian",
] as const;

// Client statuses
export const CLIENT_STATUSES = [
  { value: "lead", label: "Lead", color: "blue" },
  { value: "active", label: "Active", color: "green" },
  { value: "completed", label: "Completed", color: "purple" },
  { value: "lost", label: "Lost", color: "red" },
  { value: "inactive", label: "Inactive", color: "gray" },
] as const;

// Lead sources
export const LEAD_SOURCES = [
  { value: "website", label: "Website" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "referral", label: "Referral" },
  { value: "social_media", label: "Social Media" },
  { value: "walk_in", label: "Walk-in" },
  { value: "other", label: "Other" },
] as const;

// Service interests
export const SERVICE_INTERESTS = [
  { value: "kitas_work", label: "KITAS Work Permit" },
  { value: "kitas_investor", label: "KITAS Investor" },
  { value: "kitas_spouse", label: "KITAS Spouse" },
  { value: "kitap", label: "KITAP Permanent" },
  { value: "pt_pma", label: "PT PMA Setup" },
  { value: "tax_consulting", label: "Tax Consulting" },
  { value: "visa_extension", label: "Visa Extension" },
  { value: "retirement_visa", label: "Retirement Visa" },
  { value: "second_home", label: "Second Home Visa" },
  { value: "other", label: "Other" },
] as const;

// ============================================
// COMPANIES (Company-Centric CRM)
// ============================================

export interface Company {
  id: number;
  uuid: string;
  company_name: string;
  company_type: "PT PMA" | "PT Perorangan" | "CV" | "Other";
  brand_name?: string;
  kbli_code?: string;
  kbli_description?: string;
  nib?: string;
  npwp_company?: string;
  akta_pendirian_no?: string;
  akta_pendirian_date?: string;
  akta_perubahan_no?: string;
  akta_perubahan_date?: string;
  sk_menhumkam_no?: string;
  sk_menhumkam_date?: string;
  registered_address?: string;
  office_address?: string;
  city?: string;
  province?: string;
  postal_code?: string;
  company_phone?: string;
  company_email?: string;
  status: "active" | "dormant" | "dissolved" | "in_setup";
  setup_progress: number;
  google_drive_folder_id?: string;
  custom_fields?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface ClientCompanyLink {
  link_id: number;
  company_id: number;
  company_name: string;
  company_type: string;
  brand_name?: string;
  role: string;
  is_primary: boolean;
  ownership_percentage?: number;
  shares_count?: number;
  share_nominal_value?: number;
  start_date?: string;
  status: string;
  notes?: string;
  // Company details
  kbli_code?: string;
  kbli_description?: string;
  nib?: string;
  npwp_company?: string;
  akta_pendirian_no?: string;
  akta_pendirian_date?: string;
  akta_perubahan_no?: string;
  akta_perubahan_date?: string;
  sk_menhumkam_no?: string;
  sk_menhumkam_date?: string;
  registered_address?: string;
  office_address?: string;
  city?: string;
  province?: string;
  company_phone?: string;
  company_email?: string;
  company_status?: string;
  setup_progress?: number;
  custom_fields?: Record<string, unknown>;
}

export interface CompanyDocument {
  id: number;
  uuid: string;
  document_type: string;
  document_subtype?: string;
  document_number?: string;
  document_title?: string;
  description?: string;
  issue_date?: string;
  expiry_date?: string;
  status: "active" | "expired" | "archived" | "pending";
  google_drive_file_id?: string;
  google_drive_file_url?: string;
  file_name?: string;
  is_verified: boolean;
  created_at: string;
}

export interface TaxRecord {
  id: number;
  uuid: string;
  entity_type: "client" | "company";
  entity_id: number;
  npwp?: string;
  npwp_status?: string;
  tax_center?: string;
  is_pph21_registered: boolean;
  is_pph23_registered: boolean;
  is_pph25_registered: boolean;
  is_ppn_registered: boolean;
  is_pph29_registered: boolean;
  tax_year?: number;
  reporting_period?: string;
  next_filing_date?: string;
  compliance_status: "compliant" | "overdue" | "warning" | "exempt";
}

export interface TaxDocument {
  id: number;
  uuid: string;
  document_type: string;
  tax_type?: string;
  tax_year?: number;
  tax_period?: string;
  document_number?: string;
  filing_date?: string;
  reported_amount?: number;
  paid_amount?: number;
  status: "filed" | "paid" | "corrected" | "amended";
  google_drive_file_id?: string;
  file_name?: string;
}

// Company document types
export const COMPANY_DOCUMENT_TYPES = [
  { value: "akta_pendirian", label: "Akta Pendirian" },
  { value: "akta_perubahan", label: "Akta Perubahan" },
  { value: "sk_menhumkam", label: "SK Kemenkumham" },
  { value: "nib", label: "NIB (Business ID)" },
  { value: "npwp", label: "NPWP Company" },
  { value: "skt", label: "SKT (Tax Registration)" },
  { value: "sppkp", label: "SPPKP" },
  { value: "tdp", label: "TDP" },
  { value: "domicile_letter", label: "Domicile Letter" },
  { value: "decrees", label: "Decrees" },
  { value: "licenses", label: "Licenses" },
  { value: "contracts", label: "Contracts" },
  { value: "others", label: "Others" },
] as const;

// Company roles
export const COMPANY_ROLES = [
  { value: "Director", label: "Director" },
  { value: "Commissioner", label: "Commissioner" },
  { value: "Shareholder", label: "Shareholder" },
  { value: "Employee", label: "Employee" },
  { value: "Agent", label: "Agent" },
  { value: "Beneficial_Owner", label: "Beneficial Owner" },
  { value: "Authorized_Signatory", label: "Authorized Signatory" },
] as const;

// Tax document types
export const TAX_DOCUMENT_TYPES = [
  { value: "SPT", label: "SPT (Tax Return)" },
  { value: "Bukti_Potong", label: "Bukti Potong" },
  { value: "SSP", label: "SSP (Payment Slip)" },
  { value: "Faktur_Pajak", label: "Faktur Pajak (Tax Invoice)" },
  { value: "SKT", label: "SKT" },
  { value: "SPPKP", label: "SPPKP" },
  { value: "Tax_Certificate", label: "Tax Certificate" },
  { value: "Others", label: "Others" },
] as const;

export interface RenewalAlert {
  id: number;
  practice_id: number;
  client_id: number;
  alert_type: string;
  description: string;
  target_date: string;
  alert_date: string;
  status: string;
}

export interface CreatePracticeParams {
  client_id: number; // Required by backend
  practice_type_code: string;
  status?: string; // inquiry, quotation_sent, in_progress, completed, etc.
  priority?: string; // normal, high, urgent
  notes?: string; // Maps from frontend "title"
  internal_notes?: string;
  quoted_price?: number;
  assigned_to?: string; // team member email
  start_date?: string;
}

// ============================================
// SEARCH
// ============================================

export interface SearchResult {
  id: number;
  type: "client" | "practice" | "document";
  title: string;
  subtitle?: string;
  status?: string;
  url: string;
  metadata?: Record<string, any>;
}

export interface SearchFilters {
  status?: string[];
  client_type?: string[];
  assigned_to?: string[];
  nationality?: string[];
  date_from?: string;
  date_to?: string;
}
