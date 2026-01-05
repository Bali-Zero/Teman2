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
}

export interface Interaction {
  id: number;
  client_id?: number;
  client_name?: string;
  practice_id?: number;
  conversation_id?: number;
  interaction_type: 'chat' | 'email' | 'whatsapp' | 'call' | 'meeting' | 'note';
  channel?: string;
  subject?: string;
  summary?: string;
  full_content?: string;
  sentiment?: string;
  team_member: string;
  direction: 'inbound' | 'outbound';
  interaction_date: string;
  created_at: string;
  read_receipt?: boolean; // [NEW] Real read receipt status
  read_at?: string; // [NEW] When interaction was marked as read
  read_by?: string; // [NEW] Who marked it as read
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
  address?: string;
  notes?: string;
  google_drive_folder_id?: string;
  status: 'lead' | 'active' | 'completed' | 'lost' | 'inactive' | 'prospect';
  client_type: 'individual' | 'company';
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
  relationship: 'spouse' | 'child' | 'parent' | 'sibling' | 'other';
  date_of_birth?: string;
  nationality?: string;
  passport_number?: string;
  passport_expiry?: string;
  current_visa_type?: string;
  visa_expiry?: string;
  email?: string;
  phone?: string;
  notes?: string;
  passport_alert?: 'green' | 'yellow' | 'red' | 'expired';
  visa_alert?: 'green' | 'yellow' | 'red' | 'expired';
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

export interface ClientDocument {
  id: number;
  client_id: number;
  document_type: string;
  document_category?: 'immigration' | 'pma' | 'tax' | 'personal' | 'other';
  file_name?: string;
  file_id?: string;
  file_url?: string;
  google_drive_file_url?: string;
  status?: 'pending' | 'received' | 'verified' | 'rejected' | 'expired';
  expiry_date?: string;
  notes?: string;
  is_archived?: boolean;
  family_member_id?: number;
  family_member_name?: string;
  practice_id?: number;
  alert_color?: 'green' | 'yellow' | 'red' | 'expired';
  created_at?: string;
  updated_at?: string;
}

export interface DocumentCreate {
  document_type: string;
  document_category?: string;
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
  category_group: 'immigration' | 'pma' | 'tax' | 'personal' | 'other';
  description?: string;
  has_expiry: boolean;
}

// ============================================
// EXPIRY ALERTS
// ============================================

export interface ExpiryAlert {
  entity_type: 'client' | 'family_member' | 'document';
  entity_id: number;
  entity_name: string;
  client_id: number;
  client_name: string;
  document_type: string;
  expiry_date: string;
  days_until_expiry: number;
  alert_color: 'green' | 'yellow' | 'red' | 'expired';
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
    expiry_date?: string;
    practice_type_code: string;
    practice_type_name: string;
    alert_color?: string;
  }>;
  stats: {
    family_count: number;
    documents_count: number;
    practices_count: number;
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
  notes?: string;
  status?: 'lead' | 'active' | 'completed' | 'lost' | 'inactive';
  client_type?: 'individual' | 'company';
  assigned_to?: string;
  tags?: string[];
  address?: string;
  lead_source?: 'website' | 'whatsapp' | 'referral' | 'social_media' | 'walk_in' | 'other';
  service_interest?: string[];  // e.g., ['kitas', 'pt_pma', 'tax']
}

// Common nationalities for dropdown
export const COMMON_NATIONALITIES = [
  'Australian', 'American', 'British', 'Canadian', 'Chinese', 'Dutch', 'French',
  'German', 'Indian', 'Indonesian', 'Italian', 'Japanese', 'Korean', 'Malaysian',
  'Russian', 'Singaporean', 'Spanish', 'Swedish', 'Swiss', 'Ukrainian'
] as const;

// Client statuses
export const CLIENT_STATUSES = [
  { value: 'lead', label: 'Lead', color: 'blue' },
  { value: 'active', label: 'Active', color: 'green' },
  { value: 'completed', label: 'Completed', color: 'purple' },
  { value: 'lost', label: 'Lost', color: 'red' },
  { value: 'inactive', label: 'Inactive', color: 'gray' },
] as const;

// Lead sources
export const LEAD_SOURCES = [
  { value: 'website', label: 'Website' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'referral', label: 'Referral' },
  { value: 'social_media', label: 'Social Media' },
  { value: 'walk_in', label: 'Walk-in' },
  { value: 'other', label: 'Other' },
] as const;

// Service interests
export const SERVICE_INTERESTS = [
  { value: 'kitas_work', label: 'KITAS Work Permit' },
  { value: 'kitas_investor', label: 'KITAS Investor' },
  { value: 'kitas_spouse', label: 'KITAS Spouse' },
  { value: 'kitap', label: 'KITAP Permanent' },
  { value: 'pt_pma', label: 'PT PMA Setup' },
  { value: 'tax_consulting', label: 'Tax Consulting' },
  { value: 'visa_extension', label: 'Visa Extension' },
  { value: 'retirement_visa', label: 'Retirement Visa' },
  { value: 'second_home', label: 'Second Home Visa' },
  { value: 'other', label: 'Other' },
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

export interface AutoCRMStats {
  total_extractions: number;
  successful_extractions: number;
  failed_extractions: number;
  clients_created: number;
  clients_updated: number;
  practices_created: number;
  last_24h: {
    extractions: number;
    clients: number;
    practices: number;
  };
  last_7d: {
    extractions: number;
    clients: number;
    practices: number;
  };
  extraction_confidence_avg: number | null;
  top_practice_types: Array<{
    code: string;
    name: string;
    count: number;
  }>;
  recent_extractions: Array<{
    id: number;
    client_id: number | null;
    practice_id: number | null;
    summary: string | null;
    sentiment: string | null;
    created_at: string | null;
    client_name: string | null;
    practice_type_code: string | null;
  }>;
}

export interface CreatePracticeParams {
  client_id: number; // Required by backend
  practice_type_code: string;
  status?: string; // inquiry, quotation_sent, in_progress, completed, etc.
  priority?: string; // normal, high, urgent
  notes?: string; // Maps from frontend "title"
  internal_notes?: string;
  quoted_price?: number;
  start_date?: string;
}