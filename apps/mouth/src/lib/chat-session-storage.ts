/**
 * Client-side conversation snapshot — instant restore on mount, DB stays SSOT.
 *
 * The DB (`api.getConversationHistory(sessionId)`) is authoritative; this module
 * is a *shadow* cache so the chat UI can paint immediately on refresh while a
 * background revalidation happens. Cap of MAX_MESSAGES protects localStorage
 * quota; older messages are dropped FIFO.
 */

import type { ChatMessage } from '@/app/chat/actions';

export const SNAPSHOT_VERSION = 1;
export const SNAPSHOT_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 days
export const MAX_MESSAGES = 50;

export interface ChatSnapshot {
  version: number;
  sessionId: string;
  savedAt: number; // Date.now() at write time
  messages: ChatMessage[];
}

interface RawSnapshot {
  version?: unknown;
  sessionId?: unknown;
  savedAt?: unknown;
  messages?: unknown;
}

/**
 * Build a localStorage key. Prefer the authenticated email; fall back to the
 * anonymous device id. Both branches are namespaced to avoid collisions.
 */
export function snapshotKey(opts: { userEmail?: string | null; deviceId: string }): string {
  if (opts.userEmail && opts.userEmail.trim().length > 0) {
    return `bz_chat_session_${opts.userEmail.trim().toLowerCase()}`;
  }
  return `bz_chat_anon_${opts.deviceId}`;
}

function safeStorage(): Storage | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

function trimMessages(messages: ChatMessage[]): ChatMessage[] {
  if (messages.length <= MAX_MESSAGES) return messages;
  return messages.slice(messages.length - MAX_MESSAGES);
}

/**
 * Read and validate a snapshot. Returns null when missing, malformed, expired,
 * version-mismatched, or addressed to a different session.
 */
export function loadSnapshot(key: string, sessionId?: string): ChatSnapshot | null {
  const storage = safeStorage();
  if (!storage) return null;

  let raw: string | null;
  try {
    raw = storage.getItem(key);
  } catch {
    return null;
  }
  if (!raw) return null;

  let parsed: RawSnapshot;
  try {
    parsed = JSON.parse(raw) as RawSnapshot;
  } catch {
    safeRemove(key);
    return null;
  }

  if (parsed.version !== SNAPSHOT_VERSION) {
    safeRemove(key);
    return null;
  }
  if (typeof parsed.sessionId !== 'string') return null;
  if (typeof parsed.savedAt !== 'number') return null;
  if (Date.now() - parsed.savedAt > SNAPSHOT_TTL_MS) {
    safeRemove(key);
    return null;
  }
  if (sessionId && parsed.sessionId !== sessionId) {
    // Snapshot belongs to a different session id; keep it stored (the DB
    // will revalidate) but don't surface it under this session.
    return null;
  }
  if (!Array.isArray(parsed.messages)) return null;

  const messages = (parsed.messages as ChatMessage[]).map((m) => ({
    ...m,
    timestamp:
      m.timestamp instanceof Date
        ? m.timestamp
        : new Date(typeof m.timestamp === 'string' ? m.timestamp : Date.now()),
  }));

  return {
    version: SNAPSHOT_VERSION,
    sessionId: parsed.sessionId,
    savedAt: parsed.savedAt,
    messages,
  };
}

export function saveSnapshot(
  key: string,
  snapshot: { sessionId: string; messages: ChatMessage[] }
): void {
  const storage = safeStorage();
  if (!storage) return;

  const payload: ChatSnapshot = {
    version: SNAPSHOT_VERSION,
    sessionId: snapshot.sessionId,
    savedAt: Date.now(),
    messages: trimMessages(snapshot.messages),
  };

  try {
    storage.setItem(key, JSON.stringify(payload));
  } catch {
    // Quota exceeded or storage disabled: skip silently. DB remains SSOT.
  }
}

export function clearSnapshot(key: string): void {
  safeRemove(key);
}

function safeRemove(key: string): void {
  const storage = safeStorage();
  if (!storage) return;
  try {
    storage.removeItem(key);
  } catch {
    /* ignore */
  }
}
