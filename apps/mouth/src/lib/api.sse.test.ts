import { describe, it, expect, vi, beforeEach } from 'vitest';
import { api } from './api';

// Mock fetch globally
const mockFetch = vi.fn();
global.fetch = mockFetch;

describe('API SSE Parsing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockFetch.mockReset();
  });

  it('should parse structured error messages correctly', async () => {
    const mockStream = new ReadableStream({
      start(controller) {
        const errorData = {
          type: 'error',
          data: {
            code: 'QUOTA_EXCEEDED',
            message: 'Usage limit reached',
          },
        };
        const chunk = `data: ${JSON.stringify(errorData)}\n\n`;
        controller.enqueue(new TextEncoder().encode(chunk));
        controller.close();
      },
    });

    mockFetch.mockResolvedValue({
      ok: true,
      body: mockStream,
      headers: { get: () => 'text/event-stream' },
    });

    const onChunk = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    await api.sendMessageStreaming('test', undefined, onChunk, onDone, onError);

    expect(onError).toHaveBeenCalled();
    const error = onError.mock.calls[0][0];
    expect(error.message).toBe('Usage limit reached');
    expect(error.code).toBe('QUOTA_EXCEEDED');
  });

  it('should parse legacy string error messages correctly', async () => {
    const mockStream = new ReadableStream({
      start(controller) {
        const errorData = {
          type: 'error',
          data: 'Legacy error string',
        };
        const chunk = `data: ${JSON.stringify(errorData)}\n\n`;
        controller.enqueue(new TextEncoder().encode(chunk));
        controller.close();
      },
    });

    mockFetch.mockResolvedValue({
      ok: true,
      body: mockStream,
      headers: { get: () => 'text/event-stream' },
    });

    const onChunk = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    await api.sendMessageStreaming('test', undefined, onChunk, onDone, onError);

    expect(onError).toHaveBeenCalled();
    const error = onError.mock.calls[0][0];
    expect(error.message).toBe('Legacy error string');
  });

  it('should handle SSE events split across chunks', async () => {
    const mockStream = new ReadableStream({
      start(controller) {
        const tokenEvent = { type: 'token', data: 'Hello' };
        const payload = `data: ${JSON.stringify(tokenEvent)}\n\n`;
        const bytes = new TextEncoder().encode(payload);

        controller.enqueue(bytes.slice(0, 10));
        controller.enqueue(bytes.slice(10));
        controller.close();
      },
    });

    mockFetch.mockResolvedValue({
      ok: true,
      body: mockStream,
      headers: { get: () => 'text/event-stream' },
    });

    const onChunk = vi.fn();
    const onDone = vi.fn();
    const onError = vi.fn();

    await api.sendMessageStreaming('test', undefined, onChunk, onDone, onError);

    expect(onError).not.toHaveBeenCalled();
    expect(onChunk).toHaveBeenCalledWith('Hello');
    expect(onDone).toHaveBeenCalledWith('Hello', [], undefined);
  });
});
