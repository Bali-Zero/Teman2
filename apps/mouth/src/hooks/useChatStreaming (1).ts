import { useState, useRef, useCallback, useEffect } from 'react';
import { api, type ApiError } from '@/lib/api';
import { Message, AgentStep, Source } from '@/types';
import { useConversationMonitoring } from '@/lib/monitoring';

export interface StreamingCallbacks {
  onChunk: (chunk: string) => void;
  onComplete: (
    fullResponse: string,
    sources: Source[],
    metadata?: Message['metadata']
  ) => void;
  onError: (error: Error) => void;
  onStep: (step: AgentStep) => void;
}

export interface UseChatStreamingOptions {
  sessionId: string | null;
  isMountedRef: React.MutableRefObject<boolean>;
  isAbortedRef: React.MutableRefObject<boolean>;
}

export interface UseChatStreamingReturn {
  isStreaming: boolean;
  setIsStreaming: React.Dispatch<React.SetStateAction<boolean>>;
  sendStreamingMessage: (
    message: string,
    conversationHistory: Array<{ role: string; content: string }>,
    callbacks: StreamingCallbacks
  ) => Promise<void>;
  abortStream: () => void;
  monitoring: ReturnType<typeof useConversationMonitoring>;
}

export function useChatStreaming(
  options: UseChatStreamingOptions
): UseChatStreamingReturn {
  const { sessionId, isMountedRef, isAbortedRef } = options;
  const [isStreaming, setIsStreaming] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const streamingRequestIdRef = useRef<string | null>(null);

  const monitoring = useConversationMonitoring(sessionId);

  useEffect(() => {
    return () => {
      const currentController = abortControllerRef.current;
      if (currentController) {
        currentController.abort();
        abortControllerRef.current = null;
      }
    };
  }, []);

  const abortStream = useCallback(() => {
    isAbortedRef.current = true;
    const currentController = abortControllerRef.current;
    if (currentController) {
      currentController.abort();
      abortControllerRef.current = null;
    }
  }, [isAbortedRef]);

  const sendStreamingMessage = useCallback(
    async (
      message: string,
      conversationHistory: Array<{ role: string; content: string }>,
      callbacks: StreamingCallbacks
    ) => {
      const requestId = `req-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      streamingRequestIdRef.current = requestId;

      const abortController = new AbortController();
      abortControllerRef.current = abortController;
      isAbortedRef.current = false;

      try {
        await api.sendMessageStreaming(
          message,
          sessionId || undefined,
          // onChunk
          (chunk: string) => {
            if (!isMountedRef.current || isAbortedRef.current) return;
            callbacks.onChunk(chunk);
          },
          // onComplete
          (
            fullResponse: string,
            sources: Array<{ title?: string; content?: string }>,
            metadata?: Message['metadata']
          ) => {
            if (!isMountedRef.current || isAbortedRef.current) return;
            if (isMountedRef.current && !isAbortedRef.current) {
              monitoring.trackMessage(false);
            }
            callbacks.onComplete(fullResponse, sources as Source[], metadata);
            if (isMountedRef.current && !isAbortedRef.current) {
              setIsStreaming(false);
            }
          },
          // onError
          (error: Error) => {
            if (!isMountedRef.current || isAbortedRef.current) return;
            console.error('Failed to send message:', error);
            if (isMountedRef.current && !isAbortedRef.current) {
              const err = error as ApiError;
              const errorCode =
                err.code || (error.message.includes('429') ? 'QUOTA_EXCEEDED' : 'UNKNOWN');
              monitoring.trackError(errorCode);
            }
            callbacks.onError(error);
            if (isMountedRef.current && !isAbortedRef.current) {
              setIsStreaming(false);
            }
          },
          // onStep
          (step: AgentStep) => {
            if (!isMountedRef.current || isAbortedRef.current) return;
            callbacks.onStep(step);
          },
          120000,
          conversationHistory,
          abortController.signal,
          requestId,
          60000,
          600000
        );
      } catch (error) {
        if (!isMountedRef.current || isAbortedRef.current) return;
        console.error('Unhandled error in sendMessageStreaming:', error);
        if (isMountedRef.current && !isAbortedRef.current) {
          setIsStreaming(false);
          callbacks.onError(error as Error);
        }
      } finally {
        if (abortControllerRef.current === abortController) {
          abortControllerRef.current = null;
        }
      }
    },
    [sessionId, isMountedRef, isAbortedRef, monitoring]
  );

  return {
    isStreaming,
    setIsStreaming,
    sendStreamingMessage,
    abortStream,
    monitoring,
  };
}
