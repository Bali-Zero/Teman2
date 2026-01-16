/**
 * Custom hook for sending chat messages with streaming
 * 
 * Composes useChatMessages and useChatStreaming to provide
 * a complete message sending flow with optimistic updates
 * 
 * @returns Send message handler and related state
 */

/**
 * Custom hook for sending chat messages with streaming
 * 
 * Composes useChatMessages and useChatStreaming to provide
 * a complete message sending flow with optimistic updates
 * 
 * @returns Send message handler and related state
 */

import { useCallback, useTransition, useOptimistic, useState, useEffect } from 'react';
import { useChatMessages } from './useChatMessages';
import { useChatStreaming } from './useChatStreaming';
import { saveConversation } from '@/app/chat/actions';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import type { Source } from '@/types';
import type { ChatMessage, ChatImage } from '@/app/chat/actions';

export interface OptimisticMessage extends ChatMessage {
  isPending?: boolean;
  isStreaming?: boolean;
}

export interface UseChatSendOptions {
  sessionId: string;
  attachedImages: ChatImage[];
  onToast: (message: string, type: 'success' | 'error') => void;
}

export interface UseChatSendReturn {
  isPending: boolean;
  sendMessage: (input: string) => Promise<void>;
  streamingSteps: Array<{ type: string; data: unknown; timestamp: Date }>;
  currentStatus: string;
  setCurrentStatus: (status: string) => void;
  optimisticMessages: OptimisticMessage[];
}

const generateId = () => `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;

export function useChatSend({
  sessionId,
  attachedImages,
  onToast,
}: UseChatSendOptions): UseChatSendReturn {
  const {
    messages,
    setMessages,
    addMessage,
    updateLastAssistantMessage,
    isMountedRef,
    isAbortedRef,
  } = useChatMessages();

  const { isStreaming, setIsStreaming, sendStreamingMessage } = useChatStreaming({
    sessionId,
    isMountedRef,
    isAbortedRef,
  });

  const [isPending, startTransition] = useTransition();
  const [streamingSteps, setStreamingSteps] = useState<
    Array<{ type: string; data: unknown; timestamp: Date }>
  >([]);
  const [currentStatus, setCurrentStatus] = useState('');

  const [optimisticMessages, addOptimisticMessage] = useOptimistic<
    OptimisticMessage[],
    OptimisticMessage
  >(messages as OptimisticMessage[], (state, newMessage) => [...state, newMessage]);

  const sendMessage = useCallback(
    async (input: string) => {
      const trimmedInput = input.trim();
      const hasImages = attachedImages.length > 0;

      // Allow sending if there's text OR images
      if ((!trimmedInput && !hasImages) || isPending || isStreaming) return;

      const userProfile = api.getUserProfile();
      const userId = userProfile?.email || 'anonymous';
      const messageStartTime = Date.now();

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
          messageCount: messages.length,
        },
      });

      setStreamingSteps([]);
      setCurrentStatus('');

      const userMessage: OptimisticMessage = {
        id: generateId(),
        role: 'user',
        content: trimmedInput || (hasImages ? '[Image attached]' : ''),
        images: imagesToSend.length > 0 ? imagesToSend : undefined,
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

      startTransition(() => {
        addOptimisticMessage(userMessage);
        addOptimisticMessage(assistantMessage);
      });

      const newMessages = [...messages, userMessage, assistantMessage];
      setMessages(newMessages as typeof messages);

      // Build conversation history for context
      const conversationHistory = newMessages
        .filter(m => !(m as OptimisticMessage).isStreaming)
        .map(m => ({ role: m.role, content: m.content }));

      setIsStreaming(true);

      try {
        await sendStreamingMessage(
          trimmedInput || '[Image attached]',
          conversationHistory,
          {
            // onChunk - called for each token
            onChunk: (chunk: string) => {
              updateLastAssistantMessage({ content: chunk });
            },
            // onDone - called when complete
            onComplete: (fullResponse, sources, metadata) => {
              const messageDuration = Date.now() - messageStartTime;

              const typedMeta = metadata as {
                generated_image?: string;
                followup_questions?: string[];
                execution_time?: number;
                route_used?: string;
              } | undefined;
              const imageUrl = typedMeta?.generated_image;
              const followupQuestions = typedMeta?.followup_questions;
              const executionTime = typedMeta?.execution_time || messageDuration / 1000;

              logger.info('Message received successfully', {
                component: 'useChatSend',
                action: 'sendMessage',
                metadata: {
                  sessionId,
                  responseLength: fullResponse.length,
                  executionTime,
                  routeUsed: typedMeta?.route_used,
                  hasSources: (sources?.length || 0) > 0,
                  sourceCount: sources?.length || 0,
                  hasGeneratedImage: !!imageUrl,
                  hasFollowupQuestions: (followupQuestions?.length || 0) > 0,
                  totalDuration: messageDuration,
                },
              });

              // Track metric for received message
              const { trackEvent } = require('@/lib/analytics');
              trackEvent(
                'chat_message_received',
                {
                  sessionId,
                  responseLength: fullResponse.length,
                  executionTime,
                  routeUsed: typedMeta?.route_used,
                  hasSources: (sources?.length || 0) > 0,
                  sourceCount: sources?.length || 0,
                  hasGeneratedImage: !!imageUrl,
                },
                userId
              );

              updateLastAssistantMessage({
                content: fullResponse,
                sources: sources as Source[],
                isStreaming: false,
                isPending: false,
                ...(imageUrl ? { imageUrl } : {}),
                ...(followupQuestions && followupQuestions.length > 0
                  ? { metadata: { followup_questions: followupQuestions } }
                  : {}),
              });
              setCurrentStatus('');

              // Save conversation
              startTransition(async () => {
                try {
                  logger.debug('Saving conversation', {
                    component: 'useChatSend',
                    action: 'saveConversation',
                    metadata: { sessionId, messageCount: newMessages.length },
                  });

                  await saveConversation(
                    newMessages
                      .filter(m => !(m as OptimisticMessage).isStreaming)
                      .map(m => ({
                        ...m,
                        content:
                          (m as OptimisticMessage).id === assistantMessage.id
                            ? fullResponse
                            : m.content,
                      })),
                    sessionId
                  );

                  logger.info('Conversation saved successfully', {
                    component: 'useChatSend',
                    action: 'saveConversation',
                    metadata: { sessionId, messageCount: newMessages.length },
                  });

                  trackEvent(
                    'chat_conversation_saved',
                    { sessionId, messageCount: newMessages.length },
                    userId
                  );
                } catch (error) {
                  logger.error(
                    'Failed to save conversation',
                    {
                      component: 'useChatSend',
                      action: 'saveConversation',
                      metadata: { sessionId },
                    },
                    error instanceof Error ? error : new Error(String(error))
                  );
                }
              });
            },
            // onError - called on error
            onError: (error: Error) => {
              const errorType = error instanceof Error ? error.name : 'Unknown';
              const errorMessage = error instanceof Error ? error.message : String(error);

              logger.error(
                'Message send error',
                {
                  component: 'useChatSend',
                  action: 'sendMessage',
                  metadata: {
                    sessionId,
                    errorType,
                    errorMessage,
                    hasImages: imagesToSend.length > 0,
                    messageLength: trimmedInput.length,
                  },
                },
                error instanceof Error ? error : new Error(String(error))
              );

              updateLastAssistantMessage({
                content: 'Sorry, there was an error processing your request. Please try again.',
                isPending: false,
                isStreaming: false,
              });
              setCurrentStatus('');
              onToast('Failed to send message', 'error');
            },
            // onStep - called for all step events
            onStep: (step) => {
              setStreamingSteps(prev => [...prev, step]);
              if (step.type === 'status' && typeof step.data === 'string') {
                setCurrentStatus(step.data);
              }
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

        updateLastAssistantMessage({
          content: 'Sorry, there was an error processing your request. Please try again.',
          isPending: false,
          isStreaming: false,
        });
        setCurrentStatus('');
        setStreamingSteps([]);

        const errorMessage = error instanceof Error ? error.message : 'Unknown error';
        onToast(`Failed to send message: ${errorMessage}`, 'error');
      } finally {
        setIsStreaming(false);
      }
    },
    [
      attachedImages,
      isPending,
      isStreaming,
      messages,
      sessionId,
      addOptimisticMessage,
      onToast,
      sendStreamingMessage,
      setIsStreaming,
      updateLastAssistantMessage,
      setMessages,
    ]
  );

  // Cleanup streaming steps to prevent memory leak
  useEffect(() => {
    if (!isPending && streamingSteps.length > 10) {
      setStreamingSteps(prev => prev.slice(-10));
    }
  }, [isPending, streamingSteps.length]);

  return {
    isPending: isPending || isStreaming,
    sendMessage,
    streamingSteps,
    currentStatus,
    setCurrentStatus,
    optimisticMessages,
  };
}
