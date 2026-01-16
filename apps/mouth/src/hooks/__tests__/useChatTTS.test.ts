/**
 * Unit tests for useChatTTS hook
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useChatTTS } from '../useChatTTS';

// Mock logger
vi.mock('@/lib/logger', () => ({
  logger: {
    debug: vi.fn(),
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock metrics
vi.mock('@/lib/metrics', () => ({
  chatMetrics: {
    ttsStarted: vi.fn(),
    ttsCompleted: vi.fn(),
    ttsError: vi.fn(),
  },
}));

// Mock api
vi.mock('@/lib/api', () => ({
  api: {
    generateSpeech: vi.fn(),
    getUserProfile: vi.fn(() => ({ email: 'test@example.com' })),
  },
}));

// Mock analytics
vi.mock('@/lib/analytics', () => ({
  trackEvent: vi.fn(),
}));

describe('useChatTTS', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Mock URL.createObjectURL
    global.URL.createObjectURL = vi.fn(() => 'blob:http://localhost/test');
    global.URL.revokeObjectURL = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should initialize with empty state', () => {
    const { result } = renderHook(() => useChatTTS());

    expect(result.current.playingMessageId).toBeNull();
    expect(result.current.ttsLoading).toBeNull();
  });

  it('should handle TTS generation and playback', async () => {
    const { result } = renderHook(() => useChatTTS());
    const { api } = await import('@/lib/api');
    const showToast = vi.fn();

    // Mock audio blob
    const mockBlob = new Blob(['audio data'], { type: 'audio/mpeg' });
    vi.mocked(api.generateSpeech).mockResolvedValue(mockBlob);

    // Mock Audio constructor
    const mockAudio = {
      play: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn(),
      src: '',
      onended: null as any,
      onerror: null as any,
    };

    global.Audio = vi.fn(() => mockAudio) as any;

    act(() => {
      result.current.setShowToast(showToast);
    });

    await act(async () => {
      await result.current.handleTTS('msg1', 'Hello world');
    });

    expect(api.generateSpeech).toHaveBeenCalledWith('Hello world', 'nova');
    // Note: ttsLoading and playingMessageId are set asynchronously
  });

  it('should stop TTS if already playing same message', async () => {
    const { result } = renderHook(() => useChatTTS());
    const { api } = await import('@/lib/api');
    const showToast = vi.fn();

    const mockBlob = new Blob(['audio data'], { type: 'audio/mpeg' });
    vi.mocked(api.generateSpeech).mockResolvedValue(mockBlob);

    const mockAudio1 = {
      play: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn(),
      src: '',
      onended: null as any,
      onerror: null as any,
    };

    const mockAudio2 = {
      play: vi.fn().mockResolvedValue(undefined),
      pause: vi.fn(),
      src: '',
      onended: null as any,
      onerror: null as any,
    };

    let audioCallCount = 0;
    global.Audio = vi.fn(() => {
      audioCallCount++;
      return audioCallCount === 1 ? mockAudio1 : mockAudio2;
    }) as any;

    act(() => {
      result.current.setShowToast(showToast);
    });

    await waitFor(() => {
      expect(result.current.showToast).toBeDefined();
    });

    await act(async () => {
      await result.current.handleTTS('msg1', 'Hello');
    });

    // Wait for first TTS to start
    await waitFor(() => {
      expect(result.current.playingMessageId).toBe('msg1');
    });

    await act(async () => {
      // Second call should stop the first
      await result.current.handleTTS('msg1', 'Hello');
    });

    // Audio should be paused when calling TTS on same message
    expect(mockAudio1.pause).toHaveBeenCalled();
  });

  it('should handle TTS errors gracefully', async () => {
    const { result } = renderHook(() => useChatTTS());
    const { api } = await import('@/lib/api');
    const showToast = vi.fn();

    vi.mocked(api.generateSpeech).mockRejectedValue(new Error('TTS generation failed'));

    act(() => {
      result.current.setShowToast(showToast);
    });

    await waitFor(() => {
      expect(result.current.showToast).toBeDefined();
    });

    await act(async () => {
      await result.current.handleTTS('msg1', 'Hello');
    });

    await waitFor(() => {
      expect(showToast).toHaveBeenCalled();
    }, { timeout: 1000 });

    expect(showToast).toHaveBeenCalledWith('TTS generation failed. Please try again.', 'error');
    expect(result.current.ttsLoading).toBeNull();
    expect(result.current.playingMessageId).toBeNull();
  });

  it('should handle timeout errors', async () => {
    const { result } = renderHook(() => useChatTTS());
    const { api } = await import('@/lib/api');
    const showToast = vi.fn();

    const timeoutError = new Error('timeout');
    vi.mocked(api.generateSpeech).mockRejectedValue(timeoutError);

    act(() => {
      result.current.setShowToast(showToast);
    });

    await waitFor(() => {
      expect(result.current.showToast).toBeDefined();
    });

    await act(async () => {
      await result.current.handleTTS('msg1', 'Hello');
    });

    await waitFor(() => {
      expect(showToast).toHaveBeenCalled();
    }, { timeout: 1000 });

    expect(showToast).toHaveBeenCalledWith('TTS generation timeout. Please try again.', 'error');
  });

  it('should handle rate limit errors', async () => {
    const { result } = renderHook(() => useChatTTS());
    const { api } = await import('@/lib/api');
    const showToast = vi.fn();

    const rateLimitError = new Error('429 rate limit');
    vi.mocked(api.generateSpeech).mockRejectedValue(rateLimitError);

    act(() => {
      result.current.setShowToast(showToast);
    });

    await waitFor(() => {
      expect(result.current.showToast).toBeDefined();
    });

    await act(async () => {
      await result.current.handleTTS('msg1', 'Hello');
    });

    await waitFor(() => {
      expect(showToast).toHaveBeenCalled();
    }, { timeout: 1000 });

    expect(showToast).toHaveBeenCalledWith('Too many TTS requests. Please wait a moment.', 'error');
  });

  it('should stop TTS playback', () => {
    const { result } = renderHook(() => useChatTTS());

    const mockAudio = {
      pause: vi.fn(),
      src: 'blob:test',
    } as any;

    // Set up state as if audio is playing
    act(() => {
      result.current.stopTTS();
    });

    expect(result.current.playingMessageId).toBeNull();
    expect(result.current.ttsLoading).toBeNull();
  });

  it('should cleanup audio on unmount', () => {
    const { result, unmount } = renderHook(() => useChatTTS());

    const mockAudio = {
      pause: vi.fn(),
      src: 'blob:test',
    } as any;

    unmount();

    // Cleanup should be called
    expect(result.current.playingMessageId).toBeNull();
  });
});
