/**
 * useChatMessages — message state management with mount/abort safety.
 *
 * Pattern from V5: safeSetMessages prevents state updates after unmount.
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Record<string, unknown>[];
  timestamp: Date;
  currentNode?: string;
  isStreaming?: boolean;
}

export interface UseChatMessagesReturn {
  messages: ChatMessage[];
  addUserMessage: (content: string) => string;
  addAssistantPlaceholder: () => string;
  appendToAssistant: (id: string, chunk: string) => void;
  updateAssistantNode: (id: string, node: string) => void;
  finalizeAssistant: (
    id: string,
    content: string,
    sources?: Record<string, unknown>[],
  ) => void;
  clearMessages: () => void;
  isMountedRef: React.RefObject<boolean>;
}

let messageCounter = 0;
function nextId(): string {
  return `msg-${++messageCounter}-${Date.now()}`;
}

export function useChatMessages(): UseChatMessagesReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const safeSet = useCallback(
    (updater: (prev: ChatMessage[]) => ChatMessage[]) => {
      if (!isMountedRef.current) return;
      setMessages(updater);
    },
    [],
  );

  const addUserMessage = useCallback(
    (content: string): string => {
      const id = nextId();
      safeSet((prev) => [
        ...prev,
        { id, role: "user", content, timestamp: new Date() },
      ]);
      return id;
    },
    [safeSet],
  );

  const addAssistantPlaceholder = useCallback((): string => {
    const id = nextId();
    safeSet((prev) => [
      ...prev,
      {
        id,
        role: "assistant",
        content: "",
        timestamp: new Date(),
        isStreaming: true,
      },
    ]);
    return id;
  }, [safeSet]);

  const appendToAssistant = useCallback(
    (id: string, chunk: string) => {
      safeSet((prev) =>
        prev.map((m) =>
          m.id === id ? { ...m, content: m.content + chunk } : m,
        ),
      );
    },
    [safeSet],
  );

  const updateAssistantNode = useCallback(
    (id: string, node: string) => {
      safeSet((prev) =>
        prev.map((m) => (m.id === id ? { ...m, currentNode: node } : m)),
      );
    },
    [safeSet],
  );

  const finalizeAssistant = useCallback(
    (id: string, content: string, sources?: Record<string, unknown>[]) => {
      safeSet((prev) =>
        prev.map((m) =>
          m.id === id
            ? {
                ...m,
                content,
                sources,
                isStreaming: false,
                currentNode: undefined,
              }
            : m,
        ),
      );
    },
    [safeSet],
  );

  const clearMessages = useCallback(() => {
    safeSet(() => []);
  }, [safeSet]);

  return {
    messages,
    addUserMessage,
    addAssistantPlaceholder,
    appendToAssistant,
    updateAssistantNode,
    finalizeAssistant,
    clearMessages,
    isMountedRef,
  };
}
