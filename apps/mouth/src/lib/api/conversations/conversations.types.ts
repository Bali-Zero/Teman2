// Backend conversation history response
export interface ConversationHistoryResponse {
  success: boolean;
  messages: Array<{
    role: string;
    content: string;
    sources?: Array<{ title?: string; content?: string }>;
    imageUrl?: string;
  }>;
  total_messages: number;
  session_id?: string;
  error?: string;
}

// Conversation list types
export interface ConversationListItem {
  id: number;
  title: string;
  preview: string;
  message_count: number;
  created_at: string;
  updated_at?: string;
  session_id?: string;
}

export interface ConversationListResponse {
  success: boolean;
  conversations: ConversationListItem[];
  total: number;
  error?: string;
}

export interface SingleConversationResponse {
  success: boolean;
  id?: number;
  messages: Array<{
    role: string;
    content: string;
    sources?: Array<{ title?: string; content?: string }>;
    imageUrl?: string;
  }>;
  message_count: number;
  created_at?: string;
  session_id?: string;
  metadata?: Record<string, unknown>;
  error?: string;
}

