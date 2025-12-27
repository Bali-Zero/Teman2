import { useState, useCallback, useRef, useEffect } from 'react';
import { api, type ApiError } from '@/lib/api';
import { Message, AgentStep } from '@/types';
import { useConversationMonitoring } from '@/lib/monitoring';

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [showImagePrompt, setShowImagePrompt] = useState(false);
  const isMountedRef = useRef(true);
  const streamingRequestIdRef = useRef<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const isAbortedRef = useRef(false);

  // Conversation monitoring
  const monitoring = useConversationMonitoring(currentSessionId);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      // Abort any ongoing streaming request
      const currentController = abortControllerRef.current;
      isAbortedRef.current = true;
      if (currentController) {
        currentController.abort();
        abortControllerRef.current = null;
      }
    };
  }, []);

  const generateSessionId = () => {
    return `session-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    // Generate request ID early for logging
    const requestId = `req-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    streamingRequestIdRef.current = requestId;

    // Hypothesis E: Closure captures old values
    // Note: Values captured but not used in current implementation

    // Initialize session ID if not present
    let sessionId = currentSessionId;
    if (!sessionId) {
      sessionId = generateSessionId();
      setCurrentSessionId(sessionId);
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    // Temporary ID for assistant message to update it later
    const assistantMessageId = (Date.now() + 1).toString();

    const assistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      steps: [],
      currentStatus: 'Thinking...',
    };

    // Double-check before setting messages
    if (isMountedRef.current && !isAbortedRef.current) {
      setMessages((prev) => {
        // Double-check INSIDE the setState function
        if (!isMountedRef.current || isAbortedRef.current) {
          return prev; // Return previous state without modification
        }
        return [...prev, userMessage, assistantMessage];
      });
      setInput('');
      setIsLoading(true);
    } else {
      return;
    }

    const messageToSend = input;

    // Create abort controller for this request
    const abortController = new AbortController();
    abortControllerRef.current = abortController;
    isAbortedRef.current = false;

    // Build conversation history from current messages (excluding the new user message and empty assistant message)
    // This ensures the LLM has context even if DB is unavailable
    const conversationHistory = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));
    // Add the new user message to history
    conversationHistory.push({ role: 'user', content: messageToSend });

    try {
      await api.sendMessageStreaming(
        messageToSend,
        sessionId || undefined,
        (chunk: string) => {
          // Hypothesis E: Closure captures old values
          // Check if closure captured old values by comparing with current ref values
          const currentIsMounted = isMountedRef.current;
          const currentIsAborted = isAbortedRef.current;

          if (!currentIsMounted || currentIsAborted) {
            return;
          }

          // Double-check before updating messages
          if (!currentIsMounted || currentIsAborted) {
            return;
          }

          setMessages((prev) => {
            // Double-check INSIDE the setState function (Hypothesis B)
            if (!isMountedRef.current || isAbortedRef.current) {
              return prev; // Return previous state without modification
            }

            const newMessages = [...prev];
            const lastMsg = newMessages[newMessages.length - 1];
            if (lastMsg.role === 'assistant') {
              newMessages[newMessages.length - 1] = {
                ...lastMsg,
                content: lastMsg.content + chunk,
              };
            }
            return newMessages;
          });
        },

        (
          fullResponse: string,
          sources: Array<{ title?: string; content?: string }>,
          metadata?: {
            execution_time?: number;
            route_used?: string;
            context_length?: number;
            emotional_state?: string;
            status?: string;
            user_memory_facts?: string[];
            collective_memory_facts?: string[];
            golden_answer_used?: boolean;
            followup_questions?: string[];
          }
        ) => {
          if (!isMountedRef.current || isAbortedRef.current) {
            return;
          }

          // Double-check before updating messages
          if (!isMountedRef.current || isAbortedRef.current) {
            return;
          }

          // Track successful message (only if still mounted)
          if (isMountedRef.current && !isAbortedRef.current) {
            monitoring.trackMessage(false);
          }

          setMessages((prev) => {
            // Double-check INSIDE the setState function (Hypothesis B)
            if (!isMountedRef.current || isAbortedRef.current) {
              return prev; // Return previous state without modification
            }

            const newMessages = [...prev];
            const lastMsg = newMessages[newMessages.length - 1];
            if (lastMsg.role === 'assistant') {
              const updatedMsg = {
                ...lastMsg,
                content: fullResponse,
                sources,
                metadata,
              };
              newMessages[newMessages.length - 1] = updatedMsg;

              // Save conversation with the updated messages
              // We need to map to the API format
              const messagesToSave = newMessages.map((m) => ({
                role: m.role,
                content: m.content,
                sources: m.sources,
                imageUrl: m.imageUrl,
              }));
              // Pass metadata if it's the last message (not granular per message in saveConversation API yet, but we can try passing it in metadata field)
              // Only save if component is still mounted
              // Hypothesis D: Promise chain not cancelled
              if (isMountedRef.current && !isAbortedRef.current) {
                api
                  .saveConversation(messagesToSave, sessionId!, metadata)
                  .then(() => {
                    // Hypothesis D: Promise resolves after unmount
                    if (!isMountedRef.current) {
                    }
                  })
                  .catch((err) => {
                    // Only log if still mounted
                    if (isMountedRef.current) {
                      console.error('Failed to save conversation:', err);
                    } else {
                    }
                  });
              }

              return newMessages;
            }
            return newMessages;
          });
          if (isMountedRef.current && !isAbortedRef.current) {
            setIsLoading(false);
          }
        },
        (error: Error) => {
          if (!isMountedRef.current || isAbortedRef.current) {
            return;
          }

          console.error('Failed to send message:', error);

          // Track error in monitoring (only if still mounted)
          if (isMountedRef.current && !isAbortedRef.current) {
            const err = error as ApiError;
            const errorCode =
              err.code || (error.message.includes('429') ? 'QUOTA_EXCEEDED' : 'UNKNOWN');
            monitoring.trackError(errorCode);
          }

          // Double-check before updating messages
          if (!isMountedRef.current || isAbortedRef.current) {
            return;
          }

          setMessages((prev) => {
            // Double-check INSIDE the setState function (Hypothesis B)
            if (!isMountedRef.current || isAbortedRef.current) {
              return prev; // Return previous state without modification
            }

            const newMessages = [...prev];
            const lastMsg = newMessages[newMessages.length - 1];

            let errorMessage =
              'Sorry, there was an error processing your request. Please try again.';

            // Check for specific error codes or messages
            const err = error as ApiError;
            if (err.code === 'QUOTA_EXCEEDED' || error.message.includes('429')) {
              errorMessage = '⚠️ Usage limit reached. Please wait a moment before trying again.';
            } else if (
              err.code === 'SERVICE_UNAVAILABLE' ||
              error.message.includes('Database service temporarily unavailable')
            ) {
              errorMessage = '⚠️ System is currently busy. Please try again in a few seconds.';
            }

            if (lastMsg.role === 'assistant') {
              newMessages[newMessages.length - 1] = {
                ...lastMsg,
                content: errorMessage,
              };
            }
            return newMessages;
          });
          if (isMountedRef.current && !isAbortedRef.current) {
            setIsLoading(false);
          }
        },
        (step: AgentStep) => {
          if (!isMountedRef.current || isAbortedRef.current) {
            return;
          }

          // Double-check before updating messages
          if (!isMountedRef.current || isAbortedRef.current) {
            return;
          }

          setMessages((prev) => {
            // Double-check INSIDE the setState function (Hypothesis B)
            if (!isMountedRef.current || isAbortedRef.current) {
              return prev; // Return previous state without modification
            }

            const newMessages = [...prev];
            const lastMsg = newMessages[newMessages.length - 1];
            if (lastMsg.role === 'assistant') {
              const updatedSteps = [...(lastMsg.steps || []), step];
              let newStatus = lastMsg.currentStatus;

              if (step.type === 'status') {
                newStatus = step.data;
              } else if (step.type === 'phase') {
                const phaseName = step.data.name;
                const phaseStatus = step.data.status;
                if (phaseStatus === 'started') {
                  newStatus = phaseName === 'giant' ? 'Giant Reasoning...' : phaseName === 'cell' ? 'Cell Calibration...' : 'Zantara Synthesis...';
                } else {
                  newStatus = `${phaseName} Complete`;
                }
              } else if (step.type === 'tool_start') {
                newStatus = `Using tool: ${step.data.name || 'External Tool'}...`;
              } else if (step.type === 'tool_end') {
                newStatus = 'Analyzing results...';
              }

              newMessages[newMessages.length - 1] = {
                ...lastMsg,
                steps: updatedSteps,
                currentStatus: newStatus,
              };
            }
            return newMessages;
          });
        },
        120000,
        conversationHistory,
        abortController.signal,
        requestId, // correlationId
        60000, // idleTimeoutMs
        600000, // maxTotalTimeMs
        undefined // useCellGiant deprecated - no longer used
      );
    } catch (error) {
      // Handle any unhandled errors from sendMessageStreaming
      if (!isMountedRef.current || isAbortedRef.current) {
        return;
      }

      // If error wasn't handled by onError callback, handle it here
      console.error('Unhandled error in sendMessageStreaming:', error);

      // Only update state if still mounted
      if (isMountedRef.current && !isAbortedRef.current) {
        setIsLoading(false);

        // Update the assistant message with error
        setMessages((prev) => {
          // Double-check INSIDE the setState function
          if (!isMountedRef.current || isAbortedRef.current) {
            return prev; // Return previous state without modification
          }

          const newMessages = [...prev];
          const lastMsg = newMessages[newMessages.length - 1];
          if (lastMsg.role === 'assistant') {
            newMessages[newMessages.length - 1] = {
              ...lastMsg,
              content: 'Sorry, there was an unexpected error. Please try again.',
            };
          }
          return newMessages;
        });
      }
    } finally {
      // Clear abort controller reference after request completes
      if (abortControllerRef.current === abortController) {
        abortControllerRef.current = null;
      }
    }
  };

  const handleImageGenerate = async () => {
    if (!input.trim() || isLoading) return;

    // Check if component is still mounted before starting
    if (!isMountedRef.current || isAbortedRef.current) {
      return;
    }

    const promptToGenerate = input;
    const userMessage: Message = {
      role: 'user',
      content: `Generate image: ${promptToGenerate}`,
      timestamp: new Date(),
    };

    // Double-check before setting messages
    if (!isMountedRef.current || isAbortedRef.current) {
      return;
    }

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setShowImagePrompt(false);

    try {
      const response = await api.generateImage(promptToGenerate);
      if (!isMountedRef.current) return;

      // Double-check before setting messages
      if (!isMountedRef.current || isAbortedRef.current) {
        return;
      }

      const assistantMessage: Message = {
        role: 'assistant',
        content: 'Here is your generated image:',
        imageUrl: response.image_url,
        timestamp: new Date(),
      };
      setMessages((prev) => {
        // Double-check INSIDE the setState function
        if (!isMountedRef.current || isAbortedRef.current) {
          return prev; // Return previous state without modification
        }
        return [...prev, assistantMessage];
      });
    } catch (error) {
      if (!isMountedRef.current) return;

      // Double-check before setting messages
      if (!isMountedRef.current || isAbortedRef.current) {
        return;
      }

      console.error('Failed to generate image:', error);
      const errorMessage: Message = {
        role: 'assistant',
        content: 'Sorry, failed to generate the image. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => {
        // Double-check INSIDE the setState function
        if (!isMountedRef.current || isAbortedRef.current) {
          return prev; // Return previous state without modification
        }
        return [...prev, errorMessage];
      });
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  };

  const clearMessages = useCallback(() => {
    // Only clear if still mounted
    if (isMountedRef.current) {
      setMessages([]);
      setCurrentSessionId(null);
    }
  }, []);

  const loadConversation = useCallback(async (conversationId: number) => {
    setIsLoading(true);
    try {
      const response = await api.getConversation(conversationId);
      if (!isMountedRef.current) return;

      if (response.success && response.messages) {
        // Double-check before setting messages
        if (!isMountedRef.current || isAbortedRef.current) {
          return;
        }

        const formattedMessages: Message[] = response.messages.map((msg, index) => ({
          id: `conv-${conversationId}-${index}`,
          role: msg.role as 'user' | 'assistant',
          content: msg.content,
          sources: msg.sources,
          imageUrl: msg.imageUrl,
          timestamp: new Date(response.created_at || Date.now()),
        }));
        setMessages((prev) => {
          // Double-check INSIDE the setState function
          if (!isMountedRef.current || isAbortedRef.current) {
            return prev; // Return previous state without modification
          }
          return formattedMessages;
        });
        if (response.session_id && isMountedRef.current && !isAbortedRef.current) {
          setCurrentSessionId(response.session_id);
        }
      }
    } catch (error) {
      if (!isMountedRef.current) return;
      console.error('Failed to load conversation:', error);
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  }, []);

  const handleFileUpload = async (file: File) => {
    setIsLoading(true);
    try {
      const response = await api.uploadFile(file);
      if (!isMountedRef.current) return null;
      if (isMountedRef.current) {
        setIsLoading(false);
      }
      return response;
    } catch (error) {
      if (!isMountedRef.current) return null;
      console.error('Failed to upload file:', error);
      if (isMountedRef.current) {
        setIsLoading(false);
      }
      return null;
    }
  };

  return {
    messages,
    setMessages,
    input,
    setInput,
    isLoading,
    currentSessionId,
    setCurrentSessionId,
    showImagePrompt,
    setShowImagePrompt,
    handleSend,
    handleImageGenerate,
    clearMessages,
    loadConversation,
    handleFileUpload,
  };
}
