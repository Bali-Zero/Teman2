/**
 * Custom hook for sending chat messages with streaming
 *
 * Handles only the streaming logic, not message state management.
 * Message state should be managed by the component using useOptimistic.
 *
 * @returns Send message handler and streaming state
 */

import { useCallback, useState, useEffect, useRef } from "react";
import { useChatStreaming } from "./useChatStreaming";
import { saveConversation } from "@/app/chat/actions";
import { api } from "@/lib/api";
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
  attachedImages: ChatImage[];
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
  sendMessage: (input: string) => Promise<void>;
  streamingSteps: Array<AgentStep>;
  currentStatus: string;
  setCurrentStatus: (status: string) => void;
}

export function useChatSend({
  sessionId,
  attachedImages,
  conversationHistory,
  isMountedRef,
  isAbortedRef,
  onToast,
  onChunk,
  onComplete,
  onError,
  onStep,
}: UseChatSendOptions): UseChatSendReturn {
  const { isStreaming, setIsStreaming, sendStreamingMessage } =
    useChatStreaming({
      sessionId,
      isMountedRef,
      isAbortedRef,
    });

  const [streamingSteps, setStreamingSteps] = useState<Array<AgentStep>>([]);
  const [currentStatus, setCurrentStatus] = useState("");

  // Toast deduplication - max 1 toast per 5s per error type
  const lastToastTime = useRef<Record<string, number>>({});

  /**
   * Classify error type and show appropriate toast notification
   * with deduplication to prevent toast spam
   */
  const showErrorToast = useCallback(
    (error: Error) => {
      // Classify error type based on error message
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

      // Check deduplication - max 1 toast per 5s per error type
      const now = Date.now();
      const lastShown = lastToastTime.current[errorType] || 0;

      if (now - lastShown < 5000) {
        logger.info("Toast deduplication: skipping duplicate error toast", {
          component: "useChatSend",
          metadata: { errorType, timeSinceLastToast: now - lastShown },
        });
        return;
      }

      // Show toast with user-friendly message
      const config = ERROR_MESSAGES[errorType] || ERROR_MESSAGES.SERVER_ERROR;
      onToast(config.description, "error");

      // Update last toast time
      lastToastTime.current[errorType] = now;

      logger.info("Error toast shown", {
        component: "useChatSend",
        metadata: { errorType, title: config.title },
      });
    },
    [onToast],
  );

  const sendMessage = useCallback(
    async (input: string) => {
      const trimmedInput = input.trim();
      const hasImages = attachedImages.length > 0;

      // Allow sending if there's text OR images
      if ((!trimmedInput && !hasImages) || isStreaming) return;

      // Capture images before clearing
      const imagesToSend = [...attachedImages];

      logger.info("Message send started", {
        component: "useChatSend",
        action: "sendMessage",
        metadata: {
          sessionId,
          textLength: trimmedInput.length,
          hasImages: imagesToSend.length > 0,
          imageCount: imagesToSend.length,
        },
      });

      // Track metrics
      const streamingStartTime = Date.now();
      chatMetrics.streamingStarted(sessionId);

      setStreamingSteps([]);
      setCurrentStatus("");
      setIsStreaming(true);

      try {
        await sendStreamingMessage(
          trimmedInput || "[Image attached]",
          conversationHistory,
          {
            onChunk,
            onComplete,
            onError: (error: Error) => {
              const streamingDuration =
                (Date.now() - streamingStartTime) / 1000;
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
          imagesToSend.length > 0
            ? imagesToSend.map((img) => ({
                base64: img.base64.replace(/^data:image\/[^;]+;base64,/, ""),
                name: img.name,
              }))
            : undefined,
        );
      } catch (error) {
        logger.error(
          "Message send failed",
          {
            component: "useChatSend",
            action: "sendMessage",
            metadata: {
              sessionId,
              hasImages: imagesToSend.length > 0,
              messageLength: trimmedInput.length,
            },
          },
          error instanceof Error ? error : new Error(String(error)),
        );

        const streamingDuration = (Date.now() - streamingStartTime) / 1000;
        chatMetrics.streamingError(
          sessionId,
          error instanceof Error ? error.name : "Unknown",
        );

        setCurrentStatus("");
        setStreamingSteps([]);
        const errorObj =
          error instanceof Error ? error : new Error(String(error));
        showErrorToast(errorObj);
        onError(errorObj);
      } finally {
        setIsStreaming(false);
      }
    },
    [
      attachedImages,
      isStreaming,
      sessionId,
      conversationHistory,
      onToast,
      sendStreamingMessage,
      setIsStreaming,
      onChunk,
      onComplete,
      onError,
      onStep,
      showErrorToast,
    ],
  );

  // Cleanup streaming steps to prevent memory leak
  useEffect(() => {
    if (!isStreaming && streamingSteps.length > 10) {
      setStreamingSteps((prev) => prev.slice(-10));
    }
  }, [isStreaming, streamingSteps.length]);

  return {
    isStreaming,
    sendMessage,
    streamingSteps,
    currentStatus,
    setCurrentStatus,
  };
}
