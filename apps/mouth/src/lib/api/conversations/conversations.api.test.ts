import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ConversationsApi } from './conversations.api';
import { ApiClientBase } from '../client';
import { UserMemoryContext } from '@/types';
import type {
  ConversationHistoryResponse,
  ConversationListResponse,
  SingleConversationResponse,
} from './conversations.types';

describe('ConversationsApi', () => {
  let conversationsApi: ConversationsApi;
  let mockClient: ApiClientBase;
  let mockRequest: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mockRequest = vi.fn();
    mockClient = {
      request: mockRequest,
    } as any;
    conversationsApi = new ConversationsApi(mockClient);
  });

  describe('getConversationHistory', () => {
    it('should get conversation history without sessionId', async () => {
      const mockResponse: ConversationHistoryResponse = {
        success: true,
        messages: [
          { role: 'user', content: 'Hello' },
          { role: 'assistant', content: 'Hi there!' },
        ],
        total_messages: 2,
        session_id: 'session-123',
      };

      mockRequest.mockResolvedValueOnce(mockResponse);

      const result = await conversationsApi.getConversationHistory();

      expect(mockRequest).toHaveBeenCalledWith(
        '/api/bali-zero/conversations/history?limit=50'
      );
      expect(result).toEqual(mockResponse);
    });

    it('should get conversation history with sessionId', async () => {
      const mockResponse: ConversationHistoryResponse = {
        success: true,
        messages: [],
        total_messages: 0,
        session_id: 'session-123',
      };

      mockRequest.mockResolvedValueOnce(mockResponse);

      await conversationsApi.getConversationHistory('session-123');

      expect(mockRequest).toHaveBeenCalledWith(
        '/api/bali-zero/conversations/history?session_id=session-123&limit=50'
      );
    });
  });

  describe('saveConversation', () => {
    it('should save conversation successfully', async () => {
      const mockResponse = {
        success: true,
        conversation_id: 1,
        messages_saved: 2,
      };

      mockRequest.mockResolvedValueOnce(mockResponse);

      const messages = [
        { role: 'user', content: 'Hello' },
        { role: 'assistant', content: 'Hi!' },
      ];

      const result = await conversationsApi.saveConversation(messages, 'session-123');

      expect(mockRequest).toHaveBeenCalledWith('/api/bali-zero/conversations/save', {
        method: 'POST',
        body: JSON.stringify({
          messages,
          session_id: 'session-123',
          metadata: undefined,
        }),
      });
      expect(result).toEqual(mockResponse);
    });

    it('should save conversation with metadata', async () => {
      const mockResponse = {
        success: true,
        conversation_id: 1,
        messages_saved: 2,
      };

      mockRequest.mockResolvedValueOnce(mockResponse);

      const messages = [{ role: 'user', content: 'Hello' }];
      const metadata = { execution_time: 1.5 };

      await conversationsApi.saveConversation(messages, 'session-123', metadata);

      expect(mockRequest).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: expect.stringContaining('"metadata"'),
        })
      );
    });
  });

  describe('clearConversations', () => {
    it('should clear conversations without sessionId', async () => {
      const mockResponse = {
        success: true,
        deleted_count: 5,
      };

      mockRequest.mockResolvedValueOnce(mockResponse);

      const result = await conversationsApi.clearConversations();

      expect(mockRequest).toHaveBeenCalledWith('/api/bali-zero/conversations/clear?', {
        method: 'DELETE',
      });
      expect(result).toEqual(mockResponse);
    });

    it('should clear conversations with sessionId', async () => {
      const mockResponse = {
        success: true,
        deleted_count: 3,
      };

      mockRequest.mockResolvedValueOnce(mockResponse);

      await conversationsApi.clearConversations('session-123');

      expect(mockRequest).toHaveBeenCalledWith(
        '/api/bali-zero/conversations/clear?session_id=session-123',
        {
          method: 'DELETE',
        }
      );
    });
  });

  describe('getConversationStats', () => {
    it('should get conversation stats', async () => {
      const mockResponse = {
        success: true,
        user_email: 'test@example.com',
        total_conversations: 10,
        total_messages: 50,
        last_conversation: '2024-01-01T00:00:00Z',
      };

      mockRequest.mockResolvedValueOnce(mockResponse);

      const result = await conversationsApi.getConversationStats();

      expect(mockRequest).toHaveBeenCalledWith('/api/bali-zero/conversations/stats');
      expect(result).toEqual(mockResponse);
    });
  });

  describe('listConversations', () => {
    it('should list conversations with default pagination', async () => {
      const mockResponse: ConversationListResponse = {
        success: true,
        conversations: [],
        total: 0,
      };

      mockRequest.mockResolvedValueOnce(mockResponse);

      const result = await conversationsApi.listConversations();

      expect(mockRequest).toHaveBeenCalledWith(
        '/api/bali-zero/conversations/list?limit=20&offset=0'
      );
      expect(result).toEqual(mockResponse);
    });

    it('should list conversations with custom pagination', async () => {
      const mockResponse: ConversationListResponse = {
        success: true,
        conversations: [],
        total: 0,
      };

      mockRequest.mockResolvedValueOnce(mockResponse);

      await conversationsApi.listConversations(50, 10);

      expect(mockRequest).toHaveBeenCalledWith(
        '/api/bali-zero/conversations/list?limit=50&offset=10'
      );
    });
  });

  describe('getConversation', () => {
    it('should get single conversation by ID', async () => {
      const mockResponse: SingleConversationResponse = {
        success: true,
        id: 1,
        messages: [
          { role: 'user', content: 'Hello' },
          { role: 'assistant', content: 'Hi!' },
        ],
        message_count: 2,
        created_at: '2024-01-01T00:00:00Z',
        session_id: 'session-123',
      };

      mockRequest.mockResolvedValueOnce(mockResponse);

      const result = await conversationsApi.getConversation(1);

      expect(mockRequest).toHaveBeenCalledWith('/api/bali-zero/conversations/1');
      expect(result).toEqual(mockResponse);
    });
  });

  describe('deleteConversation', () => {
    it('should delete conversation by ID', async () => {
      const mockResponse = {
        success: true,
        deleted_id: 1,
      };

      mockRequest.mockResolvedValueOnce(mockResponse);

      const result = await conversationsApi.deleteConversation(1);

      expect(mockRequest).toHaveBeenCalledWith('/api/bali-zero/conversations/1', {
        method: 'DELETE',
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('getUserMemoryContext', () => {
    it('should get user memory context', async () => {
      const mockResponse: UserMemoryContext = {
        success: true,
        user_id: 'user-123',
        profile_facts: [],
        summary: 'Test summary',
        counters: {
          total_conversations: 10,
          total_messages: 50,
        },
        has_data: true,
      };

      mockRequest.mockResolvedValueOnce(mockResponse);

      const result = await conversationsApi.getUserMemoryContext();

      expect(mockRequest).toHaveBeenCalledWith(
        '/api/bali-zero/conversations/memory/context'
      );
      expect(result).toEqual(mockResponse);
    });
  });
});
