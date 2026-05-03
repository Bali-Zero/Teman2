import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useChatSnapshot } from './useChatSnapshot';
import { snapshotKey, saveSnapshot } from '@/lib/chat-session-storage';
import type { ChatMessage } from '@/app/chat/actions';
import { api } from '@/lib/api';

vi.mock('@/lib/api', () => ({
  api: {
    getConversationHistory: vi.fn(),
  },
}));

vi.mock('@/lib/device-id', () => ({
  getDeviceId: () => 'dev-test',
}));

const buildMessage = (i: number): ChatMessage => ({
  id: `msg_${i}`,
  role: i % 2 === 0 ? 'user' : 'assistant',
  content: `local ${i}`,
  timestamp: new Date('2026-04-18T10:00:00Z'),
});

const mockedGetHistory = api.getConversationHistory as ReturnType<typeof vi.fn>;

describe('useChatSnapshot', () => {
  beforeEach(() => {
    window.localStorage.clear();
    mockedGetHistory.mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('paints from localStorage synchronously on first render', async () => {
    const key = snapshotKey({ userEmail: 'zero@balizero.com', deviceId: 'dev-test' });
    saveSnapshot(key, {
      sessionId: 'sess-1',
      messages: [buildMessage(0), buildMessage(1)],
    });
    mockedGetHistory.mockResolvedValue({
      success: true,
      messages: [],
      total_messages: 0,
    });

    const { result } = renderHook(() =>
      useChatSnapshot({ sessionId: 'sess-1', userEmail: 'zero@balizero.com' })
    );

    // Sync paint: the snapshot is already populated before any effect runs.
    expect(result.current.snapshot).toHaveLength(2);
    expect(result.current.snapshot?.[0]?.content).toBe('local 0');
  });

  it('adopts remote messages when DB has more recent data', async () => {
    mockedGetHistory.mockResolvedValue({
      success: true,
      messages: [
        { role: 'user', content: 'remote 0' },
        { role: 'assistant', content: 'remote 1' },
        { role: 'user', content: 'remote 2' },
      ],
      total_messages: 3,
    });

    const { result } = renderHook(() =>
      useChatSnapshot({ sessionId: 'sess-1', userEmail: 'zero@balizero.com' })
    );

    await waitFor(() => expect(result.current.isHydrated).toBe(true));
    expect(result.current.snapshot).toHaveLength(3);
    expect(result.current.snapshot?.[0]?.content).toBe('remote 0');
  });

  it('keeps local snapshot when DB returns empty messages', async () => {
    const key = snapshotKey({ userEmail: null, deviceId: 'dev-test' });
    saveSnapshot(key, {
      sessionId: 'sess-1',
      messages: [buildMessage(0)],
    });
    mockedGetHistory.mockResolvedValue({
      success: true,
      messages: [],
      total_messages: 0,
    });

    const { result } = renderHook(() => useChatSnapshot({ sessionId: 'sess-1', userEmail: null }));

    await waitFor(() => expect(result.current.isHydrated).toBe(true));
    expect(result.current.snapshot).toHaveLength(1);
    expect(result.current.snapshot?.[0]?.content).toBe('local 0');
  });

  it('survives DB fetch failure and keeps local snapshot', async () => {
    const key = snapshotKey({ userEmail: null, deviceId: 'dev-test' });
    saveSnapshot(key, {
      sessionId: 'sess-1',
      messages: [buildMessage(0)],
    });
    mockedGetHistory.mockRejectedValue(new Error('network down'));

    const { result } = renderHook(() => useChatSnapshot({ sessionId: 'sess-1', userEmail: null }));

    await waitFor(() => expect(result.current.isHydrated).toBe(true));
    expect(result.current.snapshot).toHaveLength(1);
  });

  it('save() writes through to localStorage and clear() drops it', async () => {
    mockedGetHistory.mockResolvedValue({
      success: true,
      messages: [],
      total_messages: 0,
    });
    const key = snapshotKey({ userEmail: 'zero@balizero.com', deviceId: 'dev-test' });

    const { result } = renderHook(() =>
      useChatSnapshot({ sessionId: 'sess-1', userEmail: 'zero@balizero.com' })
    );

    act(() => {
      result.current.save([buildMessage(0), buildMessage(1)]);
    });

    expect(window.localStorage.getItem(key)).not.toBeNull();

    act(() => {
      result.current.clear();
    });

    expect(window.localStorage.getItem(key)).toBeNull();
    expect(result.current.snapshot).toBeNull();
  });

  it('is inert when enabled=false', () => {
    mockedGetHistory.mockResolvedValue({
      success: true,
      messages: [],
      total_messages: 0,
    });

    renderHook(() =>
      useChatSnapshot({
        sessionId: 'sess-1',
        userEmail: null,
        enabled: false,
      })
    );

    expect(mockedGetHistory).not.toHaveBeenCalled();
  });
});
