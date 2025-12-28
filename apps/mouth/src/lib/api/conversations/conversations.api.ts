import type { IApiClient } from '../types/api-client.types';
import { UserMemoryContext } from '@/types';
import type {
  ConversationHistoryResponse,
  ConversationListResponse,
  SingleConversationResponse,
} from './conversations.types';

/**
 * Conversations API methods
 */
export class ConversationsApi {
  constructor(private client: IApiClient) {}

  // Get conversation history (returns messages from most recent conversation)
  async getConversationHistory(sessionId?: string): Promise<ConversationHistoryResponse> {
    const params = new URLSearchParams();
    if (sessionId) params.append('session_id', sessionId);
    params.append('limit', '50');

    return this.client.request<ConversationHistoryResponse>(
      `/api/bali-zero/conversations/history?${params.toString()}`
    );
  }

  async saveConversation(
    messages: Array<{
      role: string;
      content: string;
      sources?: Array<{ title?: string; content?: string }>;
      imageUrl?: string;
    }>,
    sessionId?: string,
    metadata?: Record<string, unknown>
  ): Promise<{ success: boolean; conversation_id: number; messages_saved: number }> {
    return this.client.request('/api/bali-zero/conversations/save', {
      method: 'POST',
      body: JSON.stringify({
        messages,
        session_id: sessionId,
        metadata,
      }),
    });
  }

  async clearConversations(
    sessionId?: string
  ): Promise<{ success: boolean; deleted_count: number }> {
    const params = new URLSearchParams();
    if (sessionId) params.append('session_id', sessionId);

    return this.client.request(`/api/bali-zero/conversations/clear?${params.toString()}`, {
      method: 'DELETE',
    });
  }

  async getConversationStats(): Promise<{
    success: boolean;
    user_email: string;
    total_conversations: number;
    total_messages: number;
    last_conversation: string | null;
  }> {
    return this.client.request('/api/bali-zero/conversations/stats');
  }

  // List all conversations with title and preview
  async listConversations(
    limit: number = 20,
    offset: number = 0
  ): Promise<ConversationListResponse> {
    const params = new URLSearchParams();
    params.append('limit', limit.toString());
    params.append('offset', offset.toString());

    return this.client.request<ConversationListResponse>(
      `/api/bali-zero/conversations/list?${params.toString()}`
    );
  }

  // Get a single conversation by ID
  async getConversation(conversationId: number): Promise<SingleConversationResponse> {
    return this.client.request<SingleConversationResponse>(
      `/api/bali-zero/conversations/${conversationId}`
    );
  }

  // Delete a single conversation by ID
  async deleteConversation(
    conversationId: number
  ): Promise<{ success: boolean; deleted_id: number }> {
    return this.client.request(`/api/bali-zero/conversations/${conversationId}`, {
      method: 'DELETE',
    });
  }

  // Get user memory context (profile facts, summary, counters)
  async getUserMemoryContext(): Promise<UserMemoryContext> {
    return this.client.request<UserMemoryContext>(
      '/api/bali-zero/conversations/memory/context'
    );
  }
}

