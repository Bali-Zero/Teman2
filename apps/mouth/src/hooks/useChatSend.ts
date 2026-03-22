/**
 * Custom hook for sending chat messages with streaming
 *
 * Handles only the streaming logic, not message state management.
 * Message state should be managed by the component using useOptimistic.
 *
 * @returns Send message handler and streaming state
 */

import { useCallback, useState, useRef } from "react";
import { useChatStreaming } from "./useChatStreaming";
import { logger } from "@/lib/logger";
import { chatMetrics } from "@/lib/metrics";
import type { Source } from "@/types";
import type { ChatMessage, ChatImage } from "@/app/chat/actions";
import type { AgentStep } from "@/types";

// Error message configurations for user-friendly feedback
const ERROR_MESSAGES: Record<string, { title: string; description: string }> = {
  TIMEOUT: {
    title: "Response Timeout",
    description: "The AI took too long to respond. Please try again.",
  },
  NETWORK: {
    title: "Connection Lost",
    description: "Please check your internet connection.",
  },
  RATE_LIMIT: {
    title: "Too Many Requests",
    description: "Please wait a moment before sending another message.",
  },
  SERVER_ERROR: {
    title: "Server Error",
    description: "Something went wrong. Our team has been notified.",
  },
  ABORTED: {
    title: "Message Stopped",
    description: "You stopped the message generation.",
  },
};

export interface UseChatSendOptions {
  sessionId: string;
  conversationHistory: Array<{ role: string; content: string }>;
  isMountedRef: React.MutableRefObject<boolean>;
  isAbortedRef: React.MutableRefObject<boolean>;
  onToast: (message: string, type: "success" | "error") => void;
  onChunk: (chunk: string) => void;
  onComplete: (
    fullResponse: string,
    sources: Source[],
    metadata?: ChatMessage["metadata"],
  ) => void;
  onError: (error: Error) => void;
  onStep: (step: AgentStep) => void;
}

export interface UseChatSendReturn {
  isStreaming: boolean;
  sendMessage: (input: string, attachedImages?: ChatImage[]) => Promise<void>;
  streamingSteps: Array<AgentStep>;
  currentStatus: string;
  setCurrentStatus: (status: string) => void;
}

export function useChatSend({
  sessionId,
  conversationHistory,
  isMountedRef,
  isAbortedRef,
  onToast,
  onChunk,
  onComplete,
  onError,
  onStep,
}: UseChatSendOptions): UseChatSendReturn {
  const { isStreaming, setIsStreaming, sendStreamingMessage } = useChatStreaming({
    sessionId,
    isMountedRef,
    isAbortedRef,
  });

  const [streamingSteps, setStreamingSteps] = useState<Array<AgentStep>>([]);
  const [currentStatus, setCurrentStatus] = useState("");

  // Toast deduplication - max 1 toast per 5s per error type
  const lastToastTime = useRef<Record<string, number>>({});

  const showErrorToast = useCallback(
    (error: Error) => {
      let errorType = "SERVER_ERROR";
      const errorMsg = error.message?.toLowerCase() || "";

      if (errorMsg.includes("timeout")) {
        errorType = "TIMEOUT";
      } else if (errorMsg.includes("aborted") || errorMsg.includes("abort")) {
        errorType = "ABORTED";
      } else if (errorMsg.includes("network") || errorMsg.includes("fetch")) {
        errorType = "NETWORK";
      } else if (errorMsg.includes("rate limit") || errorMsg.includes("429")) {
        errorType = "RATE_LIMIT";
      }

      const now = Date.now();
      const lastShown = lastToastTime.current[errorType] || 0;

      if (now - lastShown < 5000) {
        return;
      }

      const config = ERROR_MESSAGES[errorType] || ERROR_MESSAGES.SERVER_ERROR;
      onToast(config.description, "error");
      lastToastTime.current[errorType] = now;
    },
    [onToast],
  );

  const sendMessage = useCallback(
    async (input: string, attachedImages: ChatImage[] = []) => {
      const trimmedInput = input.trim();
      const hasImages = attachedImages.length > 0;

      if ((!trimmedInput && !hasImages) || isStreaming) return;

      const streamingStartTime = Date.now();
      chatMetrics.streamingStarted(sessionId);

      setCurrentStatus("Inizializzazione...");
      setStreamingSteps([]);
      setIsStreaming(true);

      const mappedImages = hasImages
        ? attachedImages.map((img) => ({
            base64: img.base64.replace(/^data:image\/[^;]+;base64,/, ""),
            name: img.name,
          }))
        : undefined;

      try {
        await sendStreamingMessage(
          trimmedInput || "[Image attached]",
          conversationHistory,
          {
            onChunk,
            onComplete: (fullResponse, sources, metadata) => {
              setCurrentStatus("");
              onComplete(fullResponse, sources, metadata);
            },
            onError: (error: Error) => {
              chatMetrics.streamingError(sessionId, error.name || "Unknown");
              setCurrentStatus("");
              showErrorToast(error);
              onError(error);
            },
            onStep: (step) => {
              setStreamingSteps((prev) => [...prev, step]);
              if (step.type === "status" && typeof step.data === "string") {
                setCurrentStatus(step.data);
              }
              onStep(step);
            },
          },
          mappedImages
        );
      } catch (error) {
        onToast(error instanceof Error ? error.message : "Errore di rete", "error");
      }
    },
    [isStreaming, conversationHistory, sendStreamingMessage, onChunk, onComplete, onError, onStep, onToast, sessionId, setIsStreaming, showErrorToast]
  );

  return { isStreaming, sendMessage, streamingSteps, currentStatus, setCurrentStatus };
}
