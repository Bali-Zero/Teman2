/**
 * useChatPage — composite hook orchestrating useGraph + useChatMessages.
 *
 * Pattern from V5: page component is purely presentational,
 * all logic lives in this hook.
 */

"use client";

import { useCallback, useRef } from "react";
import { StreamEventType } from "@nuzantara/ts-schemas";
import { useGraph } from "./useGraph";
import { useChatMessages } from "./useChatMessages";
import { graphClient } from "@/lib/api/client";
import type { ChatMessage } from "./useChatMessages";

export interface UseChatPageReturn {
  messages: ChatMessage[];
  currentNode: string;
  isLoading: boolean;
  error: string | null;
  handleSend: (query: string) => Promise<void>;
  handleAbort: () => void;
  handleNewChat: () => void;
}

// Stable session ID for this browser tab — persists across new chats via ref reset
function generateSessionId(): string {
  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function useChatPage(): UseChatPageReturn {
  const chatMessages = useChatMessages();
  const assistantIdRef = useRef<string | null>(null);
  // Fix: use ref instead of useState to avoid stale closure in onDone callback
  const lastAnswerRef = useRef("");
  // Stable session ID — links conversation turns together for multi-turn memory
  const sessionIdRef = useRef<string>(generateSessionId());

  const graph = useGraph({
    onNodeStart: (node) => {
      if (assistantIdRef.current) {
        chatMessages.updateAssistantNode(assistantIdRef.current, node);
      }
    },
    onNodeEnd: (node, data) => {
      if (data?.answer && typeof data.answer === "string") {
        lastAnswerRef.current = data.answer;
      }
    },
    onDone: () => {
      if (assistantIdRef.current && lastAnswerRef.current) {
        chatMessages.finalizeAssistant(
          assistantIdRef.current,
          lastAnswerRef.current,
        );
      }
    },
    onError: (err) => {
      if (assistantIdRef.current) {
        chatMessages.finalizeAssistant(assistantIdRef.current, `Error: ${err}`);
      }
    },
  });

  const handleSend = useCallback(
    async (query: string) => {
      if (!query.trim() || graph.isRunning) return;

      chatMessages.addUserMessage(query);
      const aId = chatMessages.addAssistantPlaceholder();
      assistantIdRef.current = aId;
      lastAnswerRef.current = "";

      await graph.execute(query, { session_id: sessionIdRef.current });

      // Finalize with the last captured answer
      if (chatMessages.isMountedRef.current && assistantIdRef.current) {
        // Find the answer from events (last NODE_END with answer data)
        const answerEvent = [...graph.events]
          .reverse()
          .find(
            (e) =>
              e.event_type === StreamEventType.NODE_END &&
              e.data?.answer &&
              typeof e.data.answer === "string",
          );
        const finalAnswer =
          (answerEvent?.data?.answer as string) ||
          lastAnswerRef.current ||
          "No answer received.";
        chatMessages.finalizeAssistant(assistantIdRef.current, finalAnswer);
      }
    },
    [graph, chatMessages],
  );

  const handleAbort = useCallback(() => {
    graph.abort();
    if (assistantIdRef.current) {
      chatMessages.finalizeAssistant(
        assistantIdRef.current,
        "Request cancelled.",
      );
    }
  }, [graph, chatMessages]);

  const handleNewChat = useCallback(() => {
    graph.abort();
    // Clear server-side session memory
    graphClient.clearSession(sessionIdRef.current).catch(() => {});
    // Generate a new session ID for the next conversation
    sessionIdRef.current = generateSessionId();
    chatMessages.clearMessages();
    assistantIdRef.current = null;
    lastAnswerRef.current = "";
  }, [graph, chatMessages]);

  return {
    messages: chatMessages.messages,
    currentNode: graph.currentNode,
    isLoading: graph.isRunning,
    error: graph.error,
    handleSend,
    handleAbort,
    handleNewChat,
  };
}
