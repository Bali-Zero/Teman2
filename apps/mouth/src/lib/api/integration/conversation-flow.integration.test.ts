import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ApiClient } from '../api-client';
import { UserProfile } from '@/types';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

Object.defineProperty(window, 'localStorage', { value: localStorageMock });

describe('Conversation Flow Integration Tests', () => {
  let api: ApiClient;
  const baseUrl = 'https://api.test.com';

  beforeEach(() => {
    localStorageMock.clear();
    vi.clearAllMocks();
    api = new ApiClient(baseUrl);

    const mockProfile: UserProfile = {
      id: '123',
      email: 'test@example.com',
      name: 'Test User',
      role: 'user',
    };
    api.setUserProfile(mockProfile);
    api.setToken('test-token');
    api.setCsrfToken('csrf-token');
  });

  describe('Complete Conversation Lifecycle', () => {
    it('should create, save, list, and delete conversation', async () => {
      // Step 1: Send initial message
      const chatResponse = {
        answer: 'Hello! How can I help you?',
        sources: [],
        context_length: 1000,
        execution_time: 1.5,
        route_used: 'fast',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => chatResponse,
      });

      const messageResult = await api.sendMessage('Hello');
      expect(messageResult.response).toBe('Hello! How can I help you?');

      // Step 2: Save conversation
      const saveResponse = {
        success: true,
        conversation_id: 1,
        messages_saved: 2,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => saveResponse,
      });

      const saveResult = await api.saveConversation(
        [
          { role: 'user', content: 'Hello' },
          { role: 'assistant', content: 'Hello! How can I help you?' },
        ],
        'session-123'
      );
      expect(saveResult.conversation_id).toBe(1);

      // Step 3: List conversations
      const listResponse = {
        success: true,
        conversations: [
          {
            id: 1,
            title: 'Test Conversation',
            preview: 'Hello',
            message_count: 2,
            created_at: '2024-01-01T00:00:00Z',
            session_id: 'session-123',
          },
        ],
        total: 1,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => listResponse,
      });

      const conversations = await api.listConversations();
      expect(conversations.conversations).toHaveLength(1);

      // Step 4: Get conversation details
      const getResponse = {
        success: true,
        id: 1,
        messages: [
          { role: 'user', content: 'Hello' },
          { role: 'assistant', content: 'Hello! How can I help you?' },
        ],
        message_count: 2,
        created_at: '2024-01-01T00:00:00Z',
        session_id: 'session-123',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => getResponse,
      });

      const conversation = await api.getConversation(1);
      expect(conversation.messages).toHaveLength(2);

      // Step 5: Delete conversation
      const deleteResponse = {
        success: true,
        deleted_id: 1,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => deleteResponse,
      });

      const deleteResult = await api.deleteConversation(1);
      expect(deleteResult.success).toBe(true);
    });

    it('should handle multi-turn conversation with history', async () => {
      const sessionId = 'session-123';
      const conversationHistory: Array<{ role: string; content: string }> = [];

      // Turn 1: User asks question
      const mockReader1 = {
        read: vi
          .fn()
          .mockResolvedValueOnce({
            done: false,
            value: new TextEncoder().encode('data: {"type":"token","content":"Answer 1"}\n'),
          })
          .mockResolvedValueOnce({
            done: false,
            value: new TextEncoder().encode('data: [DONE]\n'),
          })
          .mockResolvedValueOnce({ done: true }),
        cancel: vi.fn(),
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: {
          getReader: () => mockReader1,
        },
      });

      const onDone1 = vi.fn();
      await api.sendMessageStreaming('Question 1', sessionId, vi.fn(), onDone1, vi.fn());

      conversationHistory.push({ role: 'user', content: 'Question 1' });
      conversationHistory.push({ role: 'assistant', content: 'Answer 1' });

      // Turn 2: Follow-up question with history
      const mockReader2 = {
        read: vi
          .fn()
          .mockResolvedValueOnce({
            done: false,
            value: new TextEncoder().encode('data: {"type":"token","content":"Answer 2"}\n'),
          })
          .mockResolvedValueOnce({
            done: false,
            value: new TextEncoder().encode('data: [DONE]\n'),
          })
          .mockResolvedValueOnce({ done: true }),
        cancel: vi.fn(),
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        body: {
          getReader: () => mockReader2,
        },
      });

      const onDone2 = vi.fn();
      await api.sendMessageStreaming(
        'Question 2',
        sessionId,
        vi.fn(),
        onDone2,
        vi.fn(),
        undefined,
        120000,
        conversationHistory
      );

      // Verify conversation history was included
      const callArgs = mockFetch.mock.calls[1];
      const body = JSON.parse(callArgs[1].body);
      expect(body.conversation_history).toBeDefined();
      expect(body.conversation_history.length).toBe(2);
    });
  });

  describe('Conversation Statistics', () => {
    it('should get conversation stats', async () => {
      const statsResponse = {
        success: true,
        user_email: 'test@example.com',
        total_conversations: 10,
        total_messages: 50,
        last_conversation: '2024-01-01T00:00:00Z',
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => statsResponse,
      });

      const stats = await api.getConversationStats();
      expect(stats.total_conversations).toBe(10);
      expect(stats.total_messages).toBe(50);
    });

    it('should get user memory context', async () => {
      const memoryResponse = {
        profile_facts: ['Fact 1', 'Fact 2'],
        summary: 'User summary',
        counters: {
          total_conversations: 10,
          total_messages: 50,
        },
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        status: 200,
        headers: new Headers({ 'content-type': 'application/json' }),
        json: async () => memoryResponse,
      });

      const memory = await api.getUserMemoryContext();
      expect(memory.profile_facts).toHaveLength(2);
      expect(memory.summary).toBe('User summary');
    });
  });
});

