/** Omnichannel unified inbox types. */

export type ThreadStatus = 'open' | 'assigned' | 'waiting' | 'resolved' | 'closed';
export type ThreadPriority = 'low' | 'normal' | 'high' | 'urgent';
export type MessageDirection = 'inbound' | 'outbound' | 'internal';

export interface Thread {
  id: string;
  client_id: number | null;
  client_name: string | null;
  client_email: string | null;
  status: ThreadStatus;
  priority: ThreadPriority;
  assigned_to: string | null;
  subject: string | null;
  channels: string[];
  intent: string | null;
  unread_count: number;
  last_message_preview: string | null;
  last_activity_at: string | null;
  created_at: string | null;
  metadata: Record<string, unknown>;
}

export interface ThreadMessage {
  id: number;
  channel: string;
  direction: MessageDirection;
  sender_id: string;
  content: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ThreadDetail {
  thread: Thread;
  messages: ThreadMessage[];
}

export interface ThreadFilter {
  status?: ThreadStatus;
  priority?: ThreadPriority;
  assigned_to?: string;
  channel?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface ThreadListResponse {
  threads: Thread[];
  total: number;
  limit: number;
  offset: number;
}

export interface CRMContext {
  client: {
    id: number;
    full_name: string;
    email: string;
    phone: string | null;
    whatsapp: string | null;
    nationality: string | null;
    status: string;
    company_name: string | null;
    assigned_to: string | null;
    avatar_url: string | null;
    created_at: string;
  } | null;
  practices: Array<{
    id: number;
    practice_type: string;
    status: string;
    priority: string;
    description: string | null;
    quoted_price: number | null;
    created_at: string;
  }>;
  alerts: Array<{
    id: number;
    alert_type: string;
    status: string;
    message: string;
    created_at: string;
  }>;
  interactions: Array<{
    id: number;
    interaction_type: string;
    channel: string;
    sentiment: string | null;
    summary: string | null;
    created_at: string;
  }>;
}

export interface OmnichannelStats {
  by_status: Record<string, number>;
  by_channel: Record<string, number>;
  by_priority: Record<string, number>;
  total_unread: number;
}

/** Channel display metadata. */
export const CHANNEL_COLORS: Record<string, string> = {
  whatsapp: '#25D366',
  telegram: '#0088cc',
  instagram: '#E4405F',
  twitter: '#1DA1F2',
  web: '#6B7280',
  internal: '#EAB308',
};

export const CHANNEL_LABELS: Record<string, string> = {
  whatsapp: 'WhatsApp',
  telegram: 'Telegram',
  instagram: 'Instagram',
  twitter: 'X',
  web: 'Web',
  internal: 'Note',
};
