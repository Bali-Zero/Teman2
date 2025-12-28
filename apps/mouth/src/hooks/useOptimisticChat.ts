'use client';

import { useState, useOptimistic, useTransition, useCallback, useRef } from 'react';
import {
  sendMessageStream,
  saveConversation,
  type ChatMessage,
  type Source,
  type StreamEvent,
} from '@/app/chat/actions';

/**
 * Optimistic Chat Hook
 *
 * React 19 patterns:
 * - useOptimistic for instant UI updates
 * - useTransition for non-blocking state updates
 * - Native Web Streams for SSE consumption
 *
 * Benefits:
 * - Zero perceived latency (message appears instantly)
 * - Smooth streaming updates
 * - Automatic rollback on error
 * - Type-safe throughout
 */

interface OptimisticMessage extends ChatMessage {
  isPending?: boolean;
  isStreaming?: boolean;
}

interface UseOptimisticChatOptions {
  userId: string;
  onError?: (error: string) => void;
}

interface UseOptimisticChatReturn {
  messages: OptimisticMessage[];
  optimisticMessages: OptimisticMessage[];
  input: string;
  setInput: (value: string) => void;
  currentStatus: string;
  sources: Source[];
  isPending: boolean;
  isStreaming: boolean;
  sessionId: string;
  send: () => Promise<void>;
  newChat: () => void;
  cancelStream: () => void;
}

// Utilities
const generateId = () => `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
const generateSessionId = () => `session_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`;

export function useOptimisticChat({
  userId,
  onError,
}: UseOptimisticChatOptions): UseOptimisticChatReturn {
  // Core state
  const [messages, setMessages] = useState<OptimisticMessage[]>([]);
  const [sessionId, setSessionId] = useState(() => generateSessionId());
  const [input, setInput] = useState('');
  const [currentStatus, setCurrentStatus] = useState('');
  const [sources, setSources] = useState<Source[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);

  // Refs for cancellation
  const abortControllerRef = useRef<AbortController | null>(null);
  const currentAssistantIdRef = useRef<string | null>(null);
  const streamReaderRef = useRef<ReadableStreamDefaultReader<StreamEvent> | null>(null);

  // Transition for non-blocking updates
  const [isPending, startTransition] = useTransition();

  // ============================================
  // 🚀 Optimistic State
  // ============================================
  const [optimisticMessages, addOptimisticMessage] = useOptimistic<
    OptimisticMessage[],
    { action: 'add' | 'update'; message: OptimisticMessage }
  >(messages, (state, { action, message }) => {
    if (action === 'add') {
      return [...state, message];
    }
    // Update existing message
    return state.map((m) => (m.id === message.id ? { ...m, ...message } : m));
  });

  // ============================================
  // 📤 Send Message with Streaming
  // ============================================
  const send = useCallback(async () => {
    const trimmedInput = input.trim();
    if (!trimmedInput || isPending || isStreaming) return;

    // Clear input immediately
    setInput('');
    setIsStreaming(true);

    // Create new abort controller
    abortControllerRef.current = new AbortController();

    // Create messages
    const userMessage: OptimisticMessage = {
      id: generateId(),
      role: 'user',
      content: trimmedInput,
      timestamp: new Date(),
      isPending: false,
    };

    const assistantMessage: OptimisticMessage = {
      id: generateId(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isPending: true,
      isStreaming: true,
    };

    currentAssistantIdRef.current = assistantMessage.id;

    // 🔥 OPTIMISTIC UPDATE: Messages appear INSTANTLY
    startTransition(() => {
      addOptimisticMessage({ action: 'add', message: userMessage });
      addOptimisticMessage({ action: 'add', message: assistantMessage });
    });

    // Update actual state
    const newMessages = [...messages, userMessage, assistantMessage];
    setMessages(newMessages);

    try {
      // Get stream from Server Action
      const stream = await sendMessageStream(
        newMessages.filter((m) => !m.isStreaming),
        sessionId,
        userId
      );

      const reader = stream.getReader();
      streamReaderRef.current = reader;

      // Process stream
      while (true) {
        if (abortControllerRef.current?.signal.aborted) break;

        const { done, value } = await reader.read();
        if (done) break;

        const event = value as StreamEvent;

        switch (event.type) {
          case 'token':
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessage.id
                  ? { ...m, content: event.data as string, isPending: false }
                  : m
              )
            );
            break;

          case 'status':
            setCurrentStatus(event.data as string);
            break;

          case 'sources':
            const newSources = event.data as Source[];
            setSources(newSources);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessage.id ? { ...m, sources: newSources } : m
              )
            );
            break;

          case 'error':
            throw new Error(event.data as string);

          case 'done':
            break;
        }
      }

      // Complete streaming
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMessage.id
            ? { ...m, isStreaming: false, isPending: false }
            : m
        )
      );

      // Save in background
      startTransition(async () => {
        await saveConversation(
          messages.filter((m) => !m.isStreaming),
          sessionId
        );
      });
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : 'Failed to send message';

      // Update with error message
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMessage.id
            ? {
                ...m,
                content: `Error: ${errorMessage}. Please try again.`,
                isPending: false,
                isStreaming: false,
              }
            : m
        )
      );

      onError?.(errorMessage);
    } finally {
      setIsStreaming(false);
      setCurrentStatus('');
      currentAssistantIdRef.current = null;
      streamReaderRef.current = null;
    }
  }, [
    input,
    isPending,
    isStreaming,
    messages,
    sessionId,
    userId,
    addOptimisticMessage,
    onError,
  ]);

  // ============================================
  // ❌ Cancel Stream
  // ============================================
  const cancelStream = useCallback(() => {
    abortControllerRef.current?.abort();
    streamReaderRef.current?.cancel();
    setIsStreaming(false);
    setCurrentStatus('');

    if (currentAssistantIdRef.current) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === currentAssistantIdRef.current
            ? { ...m, content: m.content || 'Cancelled', isStreaming: false, isPending: false }
            : m
        )
      );
    }
  }, []);

  // ============================================
  // 🆕 New Chat
  // ============================================
  const newChat = useCallback(() => {
    cancelStream();
    setMessages([]);
    setSources([]);
    setCurrentStatus('');
    setSessionId(generateSessionId());
  }, [cancelStream]);

  return {
    messages,
    optimisticMessages,
    input,
    setInput,
    currentStatus,
    sources,
    isPending,
    isStreaming,
    sessionId,
    send,
    newChat,
    cancelStream,
  };
}
