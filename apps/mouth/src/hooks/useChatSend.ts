/**
 * Custom hook for sending chat messages with streaming
 * 
 * Handles only the streaming logic, not message state management.
 * Message state should be managed by the component using useOptimistic.
 * 
 * @returns Send message handler and streaming state
 */

import { useCallback, useState, useEffect } from 'react';
import { useChatStreaming } from './useChatStreaming';
import { saveConversation } from '@/app/chat/actions';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { chatMetrics } from '@/lib/metrics';
import type { Source } from '@/types';
import type { ChatMessage, ChatImage } from '@/app/chat/actions';
import type { AgentStep } from '@/types';

export interface UseChatSendOptions {
  sessionId: string;
  attachedImages: ChatImage[];
  conversationHistory: Array<{ role: string; content: string }>;
  isMountedRef: React.MutableRefObject<boolean>;
  isAbortedRef: React.MutableRefObject<boolean>;
  onToast: (message: string, type: 'success' | 'error') => void;
  onChunk: (chunk: string) => void;
  onComplete: (fullResponse: string, sources: Source[], metadata?: ChatMessage['metadata']) => void;
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
  const { isStreaming, setIsStreaming, sendStreamingMessage } = useChatStreaming({
    sessionId,
    isMountedRef,
    isAbortedRef,
  });

  const [streamingSteps, setStreamingSteps] = useState<Array<AgentStep>>([]);
  const [currentStatus, setCurrentStatus] = useState('');

  const sendMessage = useCallback(
    async (input: string) => {
      const trimmedInput = input.trim();
      const hasImages = attachedImages.length > 0;

      // Allow sending if there's text OR images
      if ((!trimmedInput && !hasImages) || isStreaming) return;

      // Capture images before clearing
      const imagesToSend = [...attachedImages];

      logger.info('Message send started', {
        component: 'useChatSend',
        action: 'sendMessage',
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
      setCurrentStatus('');
      setIsStreaming(true);

      try {
        await sendStreamingMessage(
          trimmedInput || '[Image attached]',
          conversationHistory,
          {
            onChunk,
            onComplete,
            onError: (error: Error) => {
              const streamingDuration = (Date.now() - streamingStartTime) / 1000;
              chatMetrics.streamingError(sessionId, error.name || 'Unknown');
              setCurrentStatus('');
              onError(error);
            },
            onStep: (step) => {
              setStreamingSteps(prev => [...prev, step]);
              if (step.type === 'status' && typeof step.data === 'string') {
                setCurrentStatus(step.data);
              }
              onStep(step);
            },
          },
          imagesToSend.length > 0
            ? imagesToSend.map(img => ({
                base64: img.base64.replace(/^data:image\/[^;]+;base64,/, ''),
                name: img.name,
              }))
            : undefined
        );
      } catch (error) {
        logger.error(
          'Message send failed',
          {
            component: 'useChatSend',
            action: 'sendMessage',
            metadata: {
              sessionId,
              hasImages: imagesToSend.length > 0,
              messageLength: trimmedInput.length,
            },
          },
          error instanceof Error ? error : new Error(String(error))
        );

        const streamingDuration = (Date.now() - streamingStartTime) / 1000;
        chatMetrics.streamingError(sessionId, error instanceof Error ? error.name : 'Unknown');
        
        setCurrentStatus('');
        setStreamingSteps([]);
        const errorMessage = error instanceof Error ? error.message : 'Unknown error';
        onToast(`Failed to send message: ${errorMessage}`, 'error');
        onError(error instanceof Error ? error : new Error(String(error)));
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
    ]
  );

  // Cleanup streaming steps to prevent memory leak
  useEffect(() => {
    if (!isStreaming && streamingSteps.length > 10) {
      setStreamingSteps(prev => prev.slice(-10));
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
