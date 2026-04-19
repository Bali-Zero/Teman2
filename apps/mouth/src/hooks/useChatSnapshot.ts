'use client';

/**
 * Local-first conversation snapshot — paint instantly from localStorage,
 * revalidate against the DB in the background, and let the caller persist
 * updates as the conversation evolves.
 *
 * Pattern: stale-while-revalidate. localStorage is a *cache*, the backend is
 * the source of truth. On mount we paint the cache (sync) and fire a request
 * to `/api/bali-zero/conversations/history`; if the backend has more or
 * different messages we adopt them and rewrite the cache.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { clearSnapshot, loadSnapshot, saveSnapshot, snapshotKey } from '@/lib/chat-session-storage';
import { getDeviceId } from '@/lib/device-id';
import type { ChatMessage, Source } from '@/app/chat/actions';

export interface UseChatSnapshotOptions {
  sessionId: string;
  userEmail?: string | null;
  /** When false the hook is inert (used while waiting for sessionId to load). */
  enabled?: boolean;
}

export interface UseChatSnapshotResult {
  snapshot: ChatMessage[] | null;
  isRevalidating: boolean;
  /** True after the first revalidation (success or fail) has resolved. */
  isHydrated: boolean;
  /** Snapshot the current message list to localStorage. */
  save: (messages: ChatMessage[]) => void;
  /** Drop the cached snapshot (e.g. on "New conversation"). */
  clear: () => void;
  /** Manually re-trigger DB revalidation. */
  refetch: () => void;
}

const generateClientId = () => `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;

export function useChatSnapshot({
  sessionId,
  userEmail,
  enabled = true,
}: UseChatSnapshotOptions): UseChatSnapshotResult {
  const key = useMemo(() => {
    if (!enabled || !sessionId) return null;
    const deviceId = getDeviceId();
    return snapshotKey({ userEmail, deviceId });
  }, [enabled, sessionId, userEmail]);

  // Initial paint comes from localStorage synchronously so the first render
  // already shows the conversation. Without this the user sees an empty pane
  // while we await the DB round-trip.
  const [snapshot, setSnapshot] = useState<ChatMessage[] | null>(() => {
    if (!key || !sessionId) return null;
    return loadSnapshot(key, sessionId)?.messages ?? null;
  });
  const [isRevalidating, setIsRevalidating] = useState(false);
  const [isHydrated, setIsHydrated] = useState(false);
  const [revalidateNonce, setRevalidateNonce] = useState(0);

  const lastSavedJsonRef = useRef<string | null>(null);

  useEffect(() => {
    if (!enabled || !sessionId || !key) return;

    let cancelled = false;
    setIsRevalidating(true);

    const revalidate = async () => {
      try {
        const remote = await api.getConversationHistory(sessionId);
        if (cancelled) return;
        if (!remote.success) {
          logger.warn('History fetch returned success=false', {
            component: 'useChatSnapshot',
            action: 'revalidate',
            metadata: { sessionId, error: remote.error },
          });
          return;
        }
        if (remote.messages.length === 0) {
          // DB is empty for this session: trust the cache as-is. This handles
          // the case where the user just sent a message and the snapshot has
          // it before the backend save round-trips.
          return;
        }
        const adopted: ChatMessage[] = remote.messages.map((m) => ({
          id: generateClientId(),
          role: m.role as 'user' | 'assistant',
          content: m.content,
          sources: m.sources as Source[] | undefined,
          imageUrl: m.imageUrl,
          timestamp: new Date(),
        }));
        setSnapshot(adopted);
        saveSnapshot(key, { sessionId, messages: adopted });
        lastSavedJsonRef.current = JSON.stringify(adopted);
      } catch (error) {
        if (cancelled) return;
        logger.warn('History fetch failed; keeping local snapshot', {
          component: 'useChatSnapshot',
          action: 'revalidate',
          metadata: { sessionId, error: String(error) },
        });
      } finally {
        if (!cancelled) {
          setIsRevalidating(false);
          setIsHydrated(true);
        }
      }
    };

    revalidate();
    return () => {
      cancelled = true;
    };
  }, [enabled, sessionId, key, revalidateNonce]);

  const save = useCallback(
    (messages: ChatMessage[]) => {
      if (!key || !sessionId) return;
      // Skip the write when nothing changed since the last save — keeps
      // localStorage I/O off the hot streaming path.
      const json = JSON.stringify(messages);
      if (json === lastSavedJsonRef.current) return;
      saveSnapshot(key, { sessionId, messages });
      lastSavedJsonRef.current = json;
    },
    [key, sessionId]
  );

  const clear = useCallback(() => {
    if (key) clearSnapshot(key);
    setSnapshot(null);
    lastSavedJsonRef.current = null;
  }, [key]);

  const refetch = useCallback(() => {
    setRevalidateNonce((n) => n + 1);
  }, []);

  return {
    snapshot,
    isRevalidating,
    isHydrated,
    save,
    clear,
    refetch,
  };
}
