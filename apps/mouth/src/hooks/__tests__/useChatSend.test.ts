/**
 * Unit tests for useChatSend hook
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useChatSend } from '../useChatSend';

// Mock dependencies
vi.mock('../useChatStreaming', () => ({
  useChatStreaming: vi.fn(() => ({
    isStreaming: false,
    setIsStreaming: vi.fn(),
    sendStreamingMessage: vi.fn().mockResolvedValue(undefined),
  })),
}));

vi.mock('@/app/chat/actions', () => ({
  saveConversation: vi.fn().mockResolvedValue({ success: true }),
}));

vi.mock('@/lib/logger', () => ({
  logger: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

describe('useChatSend', () => {
  const mockCallbacks = {
    onToast: vi.fn(),
    onChunk: vi.fn(),
    onComplete: vi.fn(),
    onError: vi.fn(),
    onStep: vi.fn(),
  };

  const defaultOptions = {
    sessionId: 'test-session',
    attachedImages: [],
    conversationHistory: [],
    isMountedRef: { current: true },
    isAbortedRef: { current: false },
    ...mockCallbacks,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should initialize with empty state', () => {
    const { result } = renderHook(() => useChatSend(defaultOptions));

    expect(result.current.isStreaming).toBe(false);
    expect(result.current.streamingSteps).toEqual([]);
    expect(result.current.currentStatus).toBe('');
  });

  it('should send message with text', async () => {
    const { useChatStreaming } = await import('../useChatStreaming');
    const mockSendStreaming = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useChatStreaming).mockReturnValue({
      isStreaming: false,
      setIsStreaming: vi.fn(),
      sendStreamingMessage: mockSendStreaming,
    } as any);

    const { result } = renderHook(() => useChatSend(defaultOptions));

    await act(async () => {
      await result.current.sendMessage('Hello world');
    });

    expect(mockSendStreaming).toHaveBeenCalledWith(
      'Hello world',
      [],
      expect.objectContaining({
        onChunk: expect.any(Function),
        onComplete: expect.any(Function),
        onError: expect.any(Function),
        onStep: expect.any(Function),
      }),
      undefined
    );
  });

  it('should send message with images', async () => {
    const { useChatStreaming } = await import('../useChatStreaming');
    const mockSendStreaming = vi.fn().mockResolvedValue(undefined);
    vi.mocked(useChatStreaming).mockReturnValue({
      isStreaming: false,
      setIsStreaming: vi.fn(),
      sendStreamingMessage: mockSendStreaming,
    } as any);

    const options = {
      ...defaultOptions,
      attachedImages: [
        { id: '1', base64: 'data:image/png;base64,test', name: 'test.png', size: 1000 },
      ],
    };

    const { result } = renderHook(() => useChatSend(options));

    await act(async () => {
      await result.current.sendMessage('');
    });

    expect(mockSendStreaming).toHaveBeenCalledWith(
      '[Image attached]',
      [],
      expect.any(Object),
      expect.arrayContaining([
        expect.objectContaining({
          base64: 'test',
          name: 'test.png',
        }),
      ])
    );
  });

  it('should not send if already streaming', async () => {
    const { useChatStreaming } = await import('../useChatStreaming');
    const mockSendStreaming = vi.fn();
    vi.mocked(useChatStreaming).mockReturnValue({
      isStreaming: true,
      setIsStreaming: vi.fn(),
      sendStreamingMessage: mockSendStreaming,
    } as any);

    const { result } = renderHook(() => useChatSend(defaultOptions));

    await act(async () => {
      await result.current.sendMessage('Hello');
    });

    expect(mockSendStreaming).not.toHaveBeenCalled();
  });

  it('should handle streaming steps', async () => {
    const { useChatStreaming } = await import('../useChatStreaming');
    let stepCallback: any;
    const mockSendStreaming = vi.fn().mockImplementation((_msg, _history, callbacks) => {
      stepCallback = callbacks.onStep;
    });
    vi.mocked(useChatStreaming).mockReturnValue({
      isStreaming: false,
      setIsStreaming: vi.fn(),
      sendStreamingMessage: mockSendStreaming,
    } as any);

    const { result } = renderHook(() => useChatSend(defaultOptions));

    await act(async () => {
      await result.current.sendMessage('Hello');
      if (stepCallback) {
        stepCallback({ type: 'status', data: 'Processing...', timestamp: new Date() });
      }
    });

    await waitFor(() => {
      expect(result.current.streamingSteps.length).toBeGreaterThan(0);
    });

    expect(result.current.currentStatus).toBe('Processing...');
    expect(mockCallbacks.onStep).toHaveBeenCalled();
  });

  it('should handle errors', async () => {
    const { useChatStreaming } = await import('../useChatStreaming');
    const error = new Error('Streaming failed');
    const mockSendStreaming = vi.fn().mockRejectedValue(error);
    vi.mocked(useChatStreaming).mockReturnValue({
      isStreaming: false,
      setIsStreaming: vi.fn(),
      sendStreamingMessage: mockSendStreaming,
    } as any);

    const { result } = renderHook(() => useChatSend(defaultOptions));

    await act(async () => {
      await result.current.sendMessage('Hello');
    });

    expect(mockCallbacks.onToast).toHaveBeenCalledWith(
      expect.stringContaining('Something went wrong'),
      'error'
    );
    expect(mockCallbacks.onError).toHaveBeenCalledWith(error);
  });

  it('should update current status', () => {
    const { result } = renderHook(() => useChatSend(defaultOptions));

    act(() => {
      result.current.setCurrentStatus('Thinking...');
    });

    expect(result.current.currentStatus).toBe('Thinking...');
  });

  it('should cleanup streaming steps', async () => {
    const { useChatStreaming } = await import('../useChatStreaming');
    let stepCallback: ((step: any) => void) | null = null;

    vi.mocked(useChatStreaming).mockReturnValue({
      isStreaming: false,
      setIsStreaming: vi.fn(),
      sendStreamingMessage: vi.fn().mockImplementation((_msg, _history, callbacks) => {
        stepCallback = callbacks.onStep;
        return Promise.resolve();
      }),
    } as any);

    const { result } = renderHook(() => useChatSend(defaultOptions));

    // Simulate adding many steps through onStep callback
    act(() => {
      if (stepCallback) {
        for (let i = 0; i < 15; i++) {
          stepCallback({
            type: 'status',
            data: `Step ${i}`,
            timestamp: new Date(),
          });
        }
      }
    });

    // Wait for cleanup effect to run
    await waitFor(
      () => {
        expect(result.current.streamingSteps.length).toBeLessThanOrEqual(10);
      },
      { timeout: 2000 }
    );
  });
});
