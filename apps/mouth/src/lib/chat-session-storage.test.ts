import { describe, it, expect, beforeEach } from 'vitest';
import {
  loadSnapshot,
  saveSnapshot,
  clearSnapshot,
  snapshotKey,
  MAX_MESSAGES,
  SNAPSHOT_VERSION,
  SNAPSHOT_TTL_MS,
} from './chat-session-storage';
import type { ChatMessage } from '@/app/chat/actions';

const buildMessage = (i: number): ChatMessage => ({
  id: `msg_${i}`,
  role: i % 2 === 0 ? 'user' : 'assistant',
  content: `message ${i}`,
  timestamp: new Date('2026-04-18T10:00:00Z'),
});

describe('snapshotKey', () => {
  it('uses authenticated email when present', () => {
    expect(snapshotKey({ userEmail: 'Zero@balizero.com', deviceId: 'dev-1' })).toBe(
      'bz_chat_session_zero@balizero.com'
    );
  });

  it('falls back to anonymous device id when email missing', () => {
    expect(snapshotKey({ userEmail: null, deviceId: 'dev-abc' })).toBe('bz_chat_anon_dev-abc');
    expect(snapshotKey({ deviceId: 'dev-xyz' })).toBe('bz_chat_anon_dev-xyz');
  });
});

describe('save/load snapshot', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('round-trips messages and metadata', () => {
    const key = 'bz_chat_session_test';
    saveSnapshot(key, {
      sessionId: 'sess-1',
      messages: [buildMessage(0), buildMessage(1)],
    });

    const loaded = loadSnapshot(key, 'sess-1');
    expect(loaded).not.toBeNull();
    expect(loaded?.version).toBe(SNAPSHOT_VERSION);
    expect(loaded?.sessionId).toBe('sess-1');
    expect(loaded?.messages).toHaveLength(2);
    expect(loaded?.messages[0]?.timestamp).toBeInstanceOf(Date);
  });

  it('returns null when sessionId mismatches', () => {
    const key = 'bz_chat_session_test';
    saveSnapshot(key, {
      sessionId: 'sess-1',
      messages: [buildMessage(0)],
    });
    expect(loadSnapshot(key, 'sess-different')).toBeNull();
  });

  it('returns null and evicts when version mismatches', () => {
    const key = 'bz_chat_session_test';
    window.localStorage.setItem(
      key,
      JSON.stringify({
        version: 99,
        sessionId: 'sess-1',
        savedAt: Date.now(),
        messages: [],
      })
    );
    expect(loadSnapshot(key, 'sess-1')).toBeNull();
    expect(window.localStorage.getItem(key)).toBeNull();
  });

  it('returns null and evicts when expired', () => {
    const key = 'bz_chat_session_test';
    window.localStorage.setItem(
      key,
      JSON.stringify({
        version: SNAPSHOT_VERSION,
        sessionId: 'sess-1',
        savedAt: Date.now() - SNAPSHOT_TTL_MS - 1000,
        messages: [],
      })
    );
    expect(loadSnapshot(key, 'sess-1')).toBeNull();
    expect(window.localStorage.getItem(key)).toBeNull();
  });

  it('trims to MAX_MESSAGES (FIFO drop oldest)', () => {
    const key = 'bz_chat_session_test';
    const messages = Array.from({ length: MAX_MESSAGES + 10 }, (_, i) => buildMessage(i));
    saveSnapshot(key, { sessionId: 'sess-1', messages });
    const loaded = loadSnapshot(key, 'sess-1');
    expect(loaded?.messages).toHaveLength(MAX_MESSAGES);
    expect(loaded?.messages[0]?.id).toBe(`msg_${10}`);
    expect(loaded?.messages[loaded.messages.length - 1]?.id).toBe(`msg_${MAX_MESSAGES + 9}`);
  });

  it('clearSnapshot removes the key', () => {
    const key = 'bz_chat_session_test';
    saveSnapshot(key, { sessionId: 'sess-1', messages: [buildMessage(0)] });
    clearSnapshot(key);
    expect(window.localStorage.getItem(key)).toBeNull();
  });

  it('returns null on malformed JSON and evicts', () => {
    const key = 'bz_chat_session_test';
    window.localStorage.setItem(key, '{not valid json');
    expect(loadSnapshot(key, 'sess-1')).toBeNull();
    expect(window.localStorage.getItem(key)).toBeNull();
  });
});
