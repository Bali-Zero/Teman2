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
   * Send message with streaming and automatic conversation persistence
   * 
   * @param query - User message
   * @param sessionId - Session ID for conversation continuity
   * @param onChunk - Callback for message chunks
   * @param onComplete - Callback when message is complete
   * @param onError - Callback for errors
   * @param metadata - Optional metadata
   */
  async sendMessageStreaming(
    query: string,
    sessionId: string,
    onChunk: (chunk: string) => void,
    onComplete: (response: WebhookChatResponse) => void,
    onError: (error: Error) => void,
    metadata?: Record<string, unknown>
  ): Promise<void> {
    try {
      const response = await fetch(`${this.client.getBaseUrl()}/webhook/chat?stream=true`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.client.getToken() || ''}`,
        },
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

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      if (!response.body) {
        throw new Error('No response body');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullAnswer = '';
      let sources: any[] = [];
      let conversationId: number | null = null;
      let executionTime = 0;
      let persisted = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          
          try {
            const data = JSON.parse(line.slice(6));
            
            if (data.type === 'token') {
              fullAnswer += data.data;
              onChunk(fullAnswer);
            } else if (data.type === 'sources') {
              sources = data.data;
            } else if (data.type === 'metadata') {
              if (data.data.conversation_id) conversationId = data.data.conversation_id;
              if (data.data.execution_time) executionTime = data.data.execution_time;
              if (data.data.persisted) persisted = data.data.persisted;
            } else if (data.type === 'error') {
              throw new Error(data.data);
            }
          } catch (e) {
            logger.error('Failed to parse SSE chunk', { error: e });
          }
        }
      }

      onComplete({
        answer: fullAnswer,
        session_id: sessionId,
        conversation_id: conversationId,
        sources,
        execution_time: executionTime,
        persisted,
      });

    } catch (error) {
      onError(error instanceof Error ? error : new Error(String(error)));
    }
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
