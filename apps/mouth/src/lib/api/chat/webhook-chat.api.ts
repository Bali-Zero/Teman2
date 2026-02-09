/**
 * Webhook Chat API
 * New endpoint with automatic conversation persistence
 * Replaces /api/agentic-rag/stream for webapp chat
 */

import type { IApiClient } from '../types/api-client.types';
import { logger } from '@/lib/logger';

export interface WebhookChatRequest {
  query: string;
  session_id: string;
  metadata?: Record<string, unknown>;
}

export interface WebhookChatResponse {
  answer: string;
  session_id: string;
  conversation_id: number | null;
  sources: Array<{ title?: string; content?: string }>;
  execution_time: number;
  persisted: boolean;
  error?: string;
}

export interface ConversationHistoryResponse {
  success: boolean;
  session_id: string;
  messages: Array<{ role: string; content: string; timestamp?: string }>;
  total_messages: number;
}

/**
 * Webhook Chat API Client
 * Handles conversation persistence with session management
 */
export class WebhookChatApi {
  constructor(private client: IApiClient) {}

  /**
   * Send message with automatic conversation persistence
   * 
   * @param query - User message
   * @param sessionId - Session ID for conversation continuity
   * @param metadata - Optional metadata (source, query_type, etc.)
   * @returns Response with conversation_id and persistence status
   */
  async sendMessage(
    query: string,
    sessionId: string,
    metadata?: Record<string, unknown>
  ): Promise<WebhookChatResponse> {
    const response = await this.client.request<WebhookChatResponse>('/webhook/chat', {
      method: 'POST',
      body: JSON.stringify({
        query,
        session_id: sessionId,
        metadata: {
          source: 'webapp',
          timestamp: new Date().toISOString(),
          ...metadata,
        },
      }),
    });

    // Log persistence status
    if (response.persisted) {
      logger.info('Message persisted', {
        component: 'WebhookChatApi',
        action: 'sendMessage',
        metadata: {
          conversation_id: response.conversation_id,
          session_id: sessionId,
          execution_time: response.execution_time,
        },
      });
    } else {
      logger.warn('Message not persisted', {
        component: 'WebhookChatApi',
        action: 'sendMessage',
        metadata: { session_id: sessionId },
      });
    }

    return response;
  }

  /**
   * Retrieve conversation history for a session
   * 
   * @param sessionId - Session ID
   * @param limit - Max messages to retrieve (default: 20, 0 = all)
   * @returns Conversation history
   */
  async getHistory(
    sessionId: string,
    limit: number = 20
  ): Promise<ConversationHistoryResponse> {
    const params = new URLSearchParams();
    if (limit > 0) {
      params.append('limit', limit.toString());
    }

    const url = `/webhook/chat/history/${sessionId}${params.toString() ? `?${params.toString()}` : ''}`;
    
    const response = await this.client.request<ConversationHistoryResponse>(url, {
      method: 'GET',
    });

    logger.info('Retrieved conversation history', {
      component: 'WebhookChatApi',
      action: 'getHistory',
      metadata: {
        session_id: sessionId,
        message_count: response.total_messages,
      },
    });

    return response;
  }
}
