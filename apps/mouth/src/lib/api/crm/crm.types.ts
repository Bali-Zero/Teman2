export interface Practice {
  id: number;
  uuid?: string;
  client_id: number;
  client_name?: string;
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
  uuid?: string;
  full_name: string;
  email?: string;
  phone?: string;
  whatsapp?: string;
  company_name?: string;
  nationality?: string;
  passport_number?: string;
  notes?: string;
  created_at: string;
}

export interface CreateClientParams {
  full_name: string;
  email?: string;
  phone?: string;
  whatsapp?: string;
  company_name?: string;
  nationality?: string;
  passport_number?: string;
  notes?: string;
}

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
  client_id?: number; // Optional if creating simultaneous, but usually required
  title: string;
  practice_type_code: string;
  description?: string;
  priority?: string;
  start_date?: string;
}
