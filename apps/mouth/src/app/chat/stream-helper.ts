/**
 * Client-side helper for streaming chat messages
 * Converts callback-based API to ReadableStream for useOptimisticChat hook
 */

import { api } from "@/lib/api";
import type { ChatMessage, Source, StreamEvent } from "./actions";

/**
 * Send message and return a ReadableStream of events
 * This is a client-side wrapper around api.sendMessageStreaming
 */
export async function sendMessageStream(
  messages: ChatMessage[],
  sessionId: string,
  userId: string,
): Promise<ReadableStream<StreamEvent>> {
  // Get the last user message
  const lastUserMessage = messages.filter((m) => m.role === "user").pop();
  if (!lastUserMessage) {
    throw new Error("No user message found");
  }

  // Convert messages to conversation history format
  // Filter out any messages that might be pending/streaming (check for optional properties)
  const conversationHistory = messages
    .filter((m) => {
      // Check if message has isStreaming/isPending (from OptimisticMessage) and skip if true
      const optimisticMsg = m as ChatMessage & {
        isStreaming?: boolean;
        isPending?: boolean;
      };
      return !optimisticMsg.isStreaming && !optimisticMsg.isPending;
    })
    .map((m) => ({
      role: m.role,
      content: m.content,
    }));

  // Create a ReadableStream that wraps the callback-based API
  return new ReadableStream<StreamEvent>({
    async start(controller) {
      let accumulatedContent = "";
      let sources: Source[] = [];

      try {
        await api.sendMessageStreaming(
          lastUserMessage.content,
          sessionId,
          // onChunk - accumulate tokens
          (chunk: string) => {
            accumulatedContent = chunk;
            controller.enqueue({
              type: "token",
              data: chunk,
            });
          },
          // onDone - finalize
          (
            fullResponse: string,
            finalSources: Array<{ title?: string; content?: string }>,
            metadata?: unknown,
          ) => {
            sources = finalSources.map((s) => ({
              title: s.title || "",
              content: s.content,
              url: undefined,
              score: undefined,
            }));

            // Send sources event
            if (sources.length > 0) {
              controller.enqueue({
                type: "sources",
                data: sources,
              });
            }

            // Send done event
            controller.enqueue({ type: "done" });
            controller.close();
          },
          // onError
          (error: Error) => {
            controller.enqueue({
              type: "error",
              data: error.message,
            });
            controller.close();
          },
          // onStep - convert to status events
          (step) => {
            if (step.type === "status" && typeof step.data === "string") {
              controller.enqueue({
                type: "status",
                data: step.data,
              });
            }
          },
          // timeoutMs
          120000,
          // conversationHistory
          conversationHistory,
          // abortSignal
          undefined,
          // correlationId
          undefined,
          // idleTimeoutMs
          60000,
          // maxTotalTimeMs
          600000,
          // images
          lastUserMessage.images?.map((img) => ({
            base64: img.base64.replace(/^data:image\/[^;]+;base64,/, ""),
            name: img.name,
          })),
        );
      } catch (error) {
        controller.enqueue({
          type: "error",
          data: error instanceof Error ? error.message : "Unknown error",
        });
        controller.close();
      }
    },
  });
}
