import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ChatApi } from './chat.api';
import { ApiClientBase } from '../client';
import type { AgenticQueryResponse } from './chat.types';

describe('ChatApi', () => {
  let chatApi: ChatApi;
  let mockClient: ApiClientBase;

  beforeEach(() => {
    mockClient = {
      request: vi.fn(),
      getUserProfile: vi.fn(),
      getToken: vi.fn(),
      getCsrfToken: vi.fn(),
      getBaseUrl: vi.fn(() => 'https://api.test.com'),
    } as any;
    chatApi = new ChatApi(mockClient);
  });

  describe('sendMessage', () => {
    it('should send message successfully', async () => {
      const mockResponse: AgenticQueryResponse = {
        answer: 'Test response',
        sources: [{ title: 'Source 1', content: 'Content 1' }],
        context_length: 1000,
        execution_time: 1.5,
        route_used: 'fast',
      };

      (mockClient.getUserProfile as any).mockReturnValue({
        id: '123',
        email: 'test@example.com',
      });
      (mockClient.request as any).mockResolvedValueOnce(mockResponse);

      const result = await chatApi.sendMessage('Hello', 'user-123');

      expect(mockClient.request).toHaveBeenCalledWith('/api/agentic-rag/query', {
        method: 'POST',
        body: JSON.stringify({
          query: 'Hello',
          user_id: 'user-123',
          enable_vision: false,
        }),
      });
      expect(result).toEqual({
        response: 'Test response',
        sources: mockResponse.sources,
      });
    });

    it('should use anonymous user_id when not provided', async () => {
      const mockResponse: AgenticQueryResponse = {
        answer: 'Test response',
        sources: [],
        context_length: 1000,
        execution_time: 1.5,
        route_used: null,
      };

      (mockClient.getUserProfile as any).mockReturnValue(null);
      (mockClient.request as any).mockResolvedValueOnce(mockResponse);

      await chatApi.sendMessage('Hello');

      expect(mockClient.request).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: expect.stringContaining('"user_id":"anonymous"'),
        })
      );
    });
  });

  describe('sendMessageStreaming', () => {
    beforeEach(() => {
      global.fetch = vi.fn();
      (mockClient.getUserProfile as any).mockReturnValue({
        id: '123',
        email: 'test@example.com',
      });
      (mockClient.getToken as any).mockReturnValue('test-token');
      (mockClient.getCsrfToken as any).mockReturnValue('csrf-token');
    });

    it('should handle streaming response successfully', async () => {
      const mockReader = {
        read: vi
          .fn()
          .mockResolvedValueOnce({
            done: false,
            value: new TextEncoder().encode('data: {"type":"token","content":"Hello"}\n'),
          })
          .mockResolvedValueOnce({
            done: false,
            value: new TextEncoder().encode('data: {"type":"token","content":" World"}\n'),
          })
          .mockResolvedValueOnce({
            done: false,
            value: new TextEncoder().encode('data: {"type":"sources","data":[]}\n'),
          })
          .mockResolvedValueOnce({
            done: false,
            value: new TextEncoder().encode('data: {"type":"metadata","data":{"execution_time":1.5}}\n'),
          })
          .mockResolvedValueOnce({
            done: false,
            value: new TextEncoder().encode('data: [DONE]\n'),
          })
          .mockResolvedValueOnce({ done: true }),
        cancel: vi.fn(),
      };

      const mockResponse = {
        ok: true,
        body: {
          getReader: () => mockReader,
        },
      };

      (global.fetch as any).mockResolvedValueOnce(mockResponse);

      const onChunk = vi.fn();
      const onDone = vi.fn();
      const onError = vi.fn();

      await chatApi.sendMessageStreaming('Hello', undefined, onChunk, onDone, onError);

      expect(onChunk).toHaveBeenCalledWith('Hello');
      expect(onChunk).toHaveBeenCalledWith(' World');
      expect(onDone).toHaveBeenCalledWith(
        'Hello World',
        [],
        expect.objectContaining({ execution_time: 1.5 })
      );
    });

    it('should handle abort signal', async () => {
      const abortController = new AbortController();
      const mockReader = {
        read: vi.fn().mockImplementation(() => {
          abortController.abort();
          return Promise.resolve({ done: false, value: new TextEncoder().encode('data: {"type":"token","content":"Test"}\n') });
        }),
        cancel: vi.fn(),
      };

      const mockResponse = {
        ok: true,
        body: {
          getReader: () => mockReader,
        },
      };

      (global.fetch as any).mockResolvedValueOnce(mockResponse);

      const onChunk = vi.fn();
      const onDone = vi.fn();
      const onError = vi.fn();

      await chatApi.sendMessageStreaming(
        'Hello',
        undefined,
        onChunk,
        onDone,
        onError,
        undefined,
        120000,
        undefined,
        abortController.signal
      );

      expect(mockReader.cancel).toHaveBeenCalled();
    });

    it('should handle tool steps', async () => {
      const mockReader = {
        read: vi
          .fn()
          .mockResolvedValueOnce({
            done: false,
            value: new TextEncoder().encode(
              'data: {"type":"tool_start","data":{"name":"search","args":{}}}\n'
            ),
          })
          .mockResolvedValueOnce({
            done: false,
            value: new TextEncoder().encode('data: {"type":"tool_end","data":{"result":"done"}}\n'),
          })
          .mockResolvedValueOnce({
            done: false,
            value: new TextEncoder().encode('data: [DONE]\n'),
          })
          .mockResolvedValueOnce({ done: true }),
        cancel: vi.fn(),
      };

      const mockResponse = {
        ok: true,
        body: {
          getReader: () => mockReader,
        },
      };

      (global.fetch as any).mockResolvedValueOnce(mockResponse);

      const onStep = vi.fn();
      const onDone = vi.fn();
      const onError = vi.fn();

      await chatApi.sendMessageStreaming('Hello', undefined, vi.fn(), onDone, onError, onStep);

      expect(onStep).toHaveBeenCalledWith({
        type: 'tool_start',
        data: { name: 'search', args: {} },
        timestamp: expect.any(Date),
      });
      expect(onStep).toHaveBeenCalledWith({
        type: 'tool_end',
        data: { result: 'done' },
        timestamp: expect.any(Date),
      });
    });

    it('should handle errors in streaming', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      const onError = vi.fn();

      await chatApi.sendMessageStreaming('Hello', undefined, vi.fn(), vi.fn(), onError);

      expect(onError).toHaveBeenCalledWith(expect.any(Error));
    });

    it('should include conversation history when provided', async () => {
      const mockReader = {
        read: vi.fn().mockResolvedValueOnce({ done: true }),
        cancel: vi.fn(),
      };

      const mockResponse = {
        ok: true,
        body: {
          getReader: () => mockReader,
        },
      };

      (global.fetch as any).mockResolvedValueOnce(mockResponse);

      const conversationHistory = [
        { role: 'user', content: 'Hello' },
        { role: 'assistant', content: 'Hi there!' },
      ];

      await chatApi.sendMessageStreaming(
        'How are you?',
        'session-123',
        vi.fn(),
        vi.fn(),
        vi.fn(),
        undefined,
        120000,
        conversationHistory
      );

      expect(global.fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          body: expect.stringContaining('"conversation_history"'),
        })
      );
    });
  });
});

