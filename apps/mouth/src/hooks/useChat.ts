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

  // #region agent log
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      // Abort any ongoing streaming request
      const currentController = abortControllerRef.current;
      isAbortedRef.current = true;
      if (currentController) {
        // #region agent log
        const logData = {
          location: 'useChat.ts:cleanup:aborting',
          message: 'Aborting streaming request on unmount',
          data: { streamingRequestId: streamingRequestIdRef.current },
          timestamp: Date.now(),
          sessionId: 'debug-session',
          runId: 'run1',
          hypothesisId: 'E',
        };
        console.warn('[DEBUG]', logData);
        fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(logData),
        }).catch(() => {});
        // #endregion
        currentController.abort();
        abortControllerRef.current = null;
      }
      fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          location: 'useChat.ts:cleanup',
          message: 'Component unmounted',
          data: { streamingRequestId: streamingRequestIdRef.current, hadController: !!currentController },
          timestamp: Date.now(),
          sessionId: 'debug-session',
          runId: 'run1',
          hypothesisId: 'E',
        }),
      }).catch(() => {});
    };
  }, []);
  // #endregion

  const generateSessionId = () => {
    return `session-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    // Generate request ID early for logging
    const requestId = `req-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    streamingRequestIdRef.current = requestId;

    // Hypothesis E: Closure captures old values
    // Capture current values at function start
    const initialIsMounted = isMountedRef.current;
    const initialIsAborted = isAbortedRef.current;
    
    // #region agent log
    const logData = {
      location: 'useChat.ts:handleSend:entry',
      message: 'handleSend called',
      data: { requestId, initialIsMounted, initialIsAborted },
      timestamp: Date.now(),
      sessionId: 'debug-session',
      runId: 'run1',
      hypothesisId: 'E',
    };
    console.warn('[DEBUG]', logData);
    fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(logData),
    }).catch(() => {});
    // #endregion

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
      // #region agent log
      const logData = {
        location: 'useChat.ts:handleSend:blocked',
        message: 'handleSend blocked after unmount check',
        data: { requestId, isMounted: isMountedRef.current, isAborted: isAbortedRef.current },
        timestamp: Date.now(),
        sessionId: 'debug-session',
        runId: 'run1',
        hypothesisId: 'A',
      };
      console.warn('[DEBUG]', logData);
      fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(logData),
      }).catch(() => {});
      // #endregion
      return;
    }

    const messageToSend = input;

    // Create abort controller for this request
    const abortController = new AbortController();
    abortControllerRef.current = abortController;
    isAbortedRef.current = false;

    // #region agent log
    fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        location: 'useChat.ts:handleSend:start',
        message: 'Starting streaming request',
        data: { requestId, isMounted: isMountedRef.current, messageCount: messages.length },
        timestamp: Date.now(),
        sessionId: 'debug-session',
        runId: 'run1',
        hypothesisId: 'B',
      }),
    }).catch(() => {});
    // #endregion

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
        
        // #region agent log
        const logData = {
          location: 'useChat.ts:chunk',
          message: 'Chunk received',
          data: { 
            requestId, 
            isMounted: currentIsMounted, 
            isAborted: currentIsAborted, 
            chunkLength: chunk.length,
          },
          timestamp: Date.now(),
          sessionId: 'debug-session',
          runId: 'run1',
          hypothesisId: 'E',
        };
        console.warn('[DEBUG]', logData);
        fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(logData),
        }).catch(() => {});
        // #endregion

        if (!currentIsMounted || currentIsAborted) {
          // #region agent log
          const logData = {
            location: 'useChat.ts:chunk:unmounted',
            message: 'Chunk received after unmount',
            data: { requestId, isMounted: currentIsMounted, isAborted: currentIsAborted },
            timestamp: Date.now(),
            sessionId: 'debug-session',
            runId: 'run1',
            hypothesisId: 'A',
          };
          console.warn('[DEBUG]', logData);
          fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(logData),
          }).catch(() => {});
          // #endregion
          return;
        }

        // Double-check before updating messages
        if (!currentIsMounted || currentIsAborted) {
          // #region agent log
          const logData = {
            location: 'useChat.ts:onChunk:setMessages:blocked',
            message: 'setMessages blocked in onChunk after unmount check',
            data: { requestId, isMounted: isMountedRef.current, isAborted: isAbortedRef.current },
            timestamp: Date.now(),
            sessionId: 'debug-session',
            runId: 'run1',
            hypothesisId: 'A',
          };
          console.warn('[DEBUG]', logData);
          fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(logData),
          }).catch(() => {});
          // #endregion
          return;
        }

        setMessages((prev) => {
          // #region agent log
          // Hypothesis B: setMessages function executes after unmount
          const logData = {
            location: 'useChat.ts:onChunk:setMessages:executing',
            message: 'setMessages function executing in onChunk',
            data: { requestId, isMounted: isMountedRef.current, isAborted: isAbortedRef.current, prevLength: prev.length },
            timestamp: Date.now(),
            sessionId: 'debug-session',
            runId: 'run1',
            hypothesisId: 'B',
          };
          console.warn('[DEBUG]', logData);
          fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(logData),
          }).catch(() => {});
          // #endregion
          
          // Double-check INSIDE the setState function (Hypothesis B)
          if (!isMountedRef.current || isAbortedRef.current) {
            // #region agent log
            const logData = {
              location: 'useChat.ts:onChunk:setMessages:inside:unmounted',
              message: 'setMessages function executing AFTER unmount detected',
              data: { requestId, isMounted: isMountedRef.current, isAborted: isAbortedRef.current },
              timestamp: Date.now(),
              sessionId: 'debug-session',
              runId: 'run1',
              hypothesisId: 'B',
            };
            console.warn('[DEBUG]', logData);
            fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(logData),
            }).catch(() => {});
            // #endregion
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
        }
      ) => {
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            location: 'useChat.ts:onComplete',
            message: 'Streaming completed',
            data: { requestId, isMounted: isMountedRef.current, responseLength: fullResponse.length },
            timestamp: Date.now(),
            sessionId: 'debug-session',
            runId: 'run1',
            hypothesisId: 'E',
          }),
        }).catch(() => {});
        // #endregion

        if (!isMountedRef.current || isAbortedRef.current) {
          // #region agent log
          const logData = {
            location: 'useChat.ts:onComplete:unmounted',
            message: 'Completion callback after unmount',
            data: { requestId, isMounted: isMountedRef.current, isAborted: isAbortedRef.current },
            timestamp: Date.now(),
            sessionId: 'debug-session',
            runId: 'run1',
            hypothesisId: 'E',
          };
          console.warn('[DEBUG]', logData);
          fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(logData),
          }).catch(() => {});
          // #endregion
          return;
        }

        // Double-check before updating messages
        if (!isMountedRef.current || isAbortedRef.current) {
          // #region agent log
          const logData = {
            location: 'useChat.ts:onComplete:setMessages:blocked',
            message: 'setMessages blocked in onComplete after unmount check',
            data: { requestId, isMounted: isMountedRef.current, isAborted: isAbortedRef.current },
            timestamp: Date.now(),
            sessionId: 'debug-session',
            runId: 'run1',
            hypothesisId: 'A',
          };
          console.warn('[DEBUG]', logData);
          fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(logData),
          }).catch(() => {});
          // #endregion
          return;
        }

        // Track successful message (only if still mounted)
        if (isMountedRef.current && !isAbortedRef.current) {
          monitoring.trackMessage(false);
        }

        setMessages((prev) => {
          // #region agent log
          // Hypothesis B: setMessages function executes after unmount
          const logData = {
            location: 'useChat.ts:onComplete:setMessages:executing',
            message: 'setMessages function executing in onComplete',
            data: { requestId, isMounted: isMountedRef.current, isAborted: isAbortedRef.current, prevLength: prev.length },
            timestamp: Date.now(),
            sessionId: 'debug-session',
            runId: 'run1',
            hypothesisId: 'B',
          };
          console.warn('[DEBUG]', logData);
          fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(logData),
          }).catch(() => {});
          // #endregion
          
          // Double-check INSIDE the setState function (Hypothesis B)
          if (!isMountedRef.current || isAbortedRef.current) {
            // #region agent log
            const logData = {
              location: 'useChat.ts:onComplete:setMessages:inside:unmounted',
              message: 'setMessages function executing AFTER unmount detected',
              data: { requestId, isMounted: isMountedRef.current, isAborted: isAbortedRef.current },
              timestamp: Date.now(),
              sessionId: 'debug-session',
              runId: 'run1',
              hypothesisId: 'B',
            };
            console.warn('[DEBUG]', logData);
            fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(logData),
            }).catch(() => {});
            // #endregion
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
              // #region agent log
              const logData = {
                location: 'useChat.ts:onComplete:saveConversation:called',
                message: 'saveConversation called in onComplete',
                data: { requestId, isMounted: isMountedRef.current, isAborted: isAbortedRef.current },
                timestamp: Date.now(),
                sessionId: 'debug-session',
                runId: 'run1',
                hypothesisId: 'D',
              };
              console.warn('[DEBUG]', logData);
              fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(logData),
              }).catch(() => {});
              // #endregion
              
              api.saveConversation(messagesToSave, sessionId!, metadata)
                .then(() => {
                  // Hypothesis D: Promise resolves after unmount
                  if (!isMountedRef.current) {
                    // #region agent log
                    const logData = {
                      location: 'useChat.ts:onComplete:saveConversation:resolved:unmounted',
                      message: 'saveConversation promise resolved AFTER unmount',
                      data: { requestId, isMounted: isMountedRef.current },
                      timestamp: Date.now(),
                      sessionId: 'debug-session',
                      runId: 'run1',
                      hypothesisId: 'D',
                    };
                    console.warn('[DEBUG]', logData);
                    fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify(logData),
                    }).catch(() => {});
                    // #endregion
                  }
                })
                .catch((err) => {
                  // Only log if still mounted
                  if (isMountedRef.current) {
                    console.error('Failed to save conversation:', err);
                  } else {
                    // #region agent log
                    const logData = {
                      location: 'useChat.ts:onComplete:saveConversation:rejected:unmounted',
                      message: 'saveConversation promise rejected AFTER unmount',
                      data: { requestId, isMounted: isMountedRef.current, error: err.message },
                      timestamp: Date.now(),
                      sessionId: 'debug-session',
                      runId: 'run1',
                      hypothesisId: 'D',
                    };
                    console.warn('[DEBUG]', logData);
                    fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify(logData),
                    }).catch(() => {});
                    // #endregion
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
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            location: 'useChat.ts:onError',
            message: 'Streaming error',
            data: { requestId, isMounted: isMountedRef.current, errorMessage: error.message },
            timestamp: Date.now(),
            sessionId: 'debug-session',
            runId: 'run1',
            hypothesisId: 'E',
          }),
        }).catch(() => {});
        // #endregion

        if (!isMountedRef.current || isAbortedRef.current) {
          // #region agent log
          fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              location: 'useChat.ts:onError:unmounted',
              message: 'Error callback after unmount',
              data: { requestId, isMounted: isMountedRef.current, isAborted: isAbortedRef.current },
              timestamp: Date.now(),
              sessionId: 'debug-session',
              runId: 'run1',
              hypothesisId: 'E',
            }),
          }).catch(() => {});
          // #endregion
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
          // #region agent log
          const logData = {
            location: 'useChat.ts:onError:setMessages:blocked',
            message: 'setMessages blocked in onError after unmount check',
            data: { requestId, isMounted: isMountedRef.current, isAborted: isAbortedRef.current },
            timestamp: Date.now(),
            sessionId: 'debug-session',
            runId: 'run1',
            hypothesisId: 'A',
          };
          console.warn('[DEBUG]', logData);
          fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(logData),
          }).catch(() => {});
          // #endregion
          return;
        }

        setMessages((prev) => {
          // #region agent log
          // Hypothesis B: setMessages function executes after unmount
          const logData = {
            location: 'useChat.ts:onError:setMessages:executing',
            message: 'setMessages function executing in onError',
            data: { requestId, isMounted: isMountedRef.current, isAborted: isAbortedRef.current, prevLength: prev.length },
            timestamp: Date.now(),
            sessionId: 'debug-session',
            runId: 'run1',
            hypothesisId: 'B',
          };
          console.warn('[DEBUG]', logData);
          fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(logData),
          }).catch(() => {});
          // #endregion
          
          // Double-check INSIDE the setState function (Hypothesis B)
          if (!isMountedRef.current || isAbortedRef.current) {
            // #region agent log
            const logData = {
              location: 'useChat.ts:onError:setMessages:inside:unmounted',
              message: 'setMessages function executing AFTER unmount detected',
              data: { requestId, isMounted: isMountedRef.current, isAborted: isAbortedRef.current },
              timestamp: Date.now(),
              sessionId: 'debug-session',
              runId: 'run1',
              hypothesisId: 'B',
            };
            console.warn('[DEBUG]', logData);
            fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(logData),
            }).catch(() => {});
            // #endregion
            return prev; // Return previous state without modification
          }
          
          const newMessages = [...prev];
          const lastMsg = newMessages[newMessages.length - 1];

          let errorMessage = 'Sorry, there was an error processing your request. Please try again.';

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
        // #region agent log
        fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            location: 'useChat.ts:onStep',
            message: 'Step callback',
            data: { requestId, isMounted: isMountedRef.current, stepType: step.type },
            timestamp: Date.now(),
            sessionId: 'debug-session',
            runId: 'run1',
            hypothesisId: 'B',
          }),
        }).catch(() => {});
        // #endregion

        if (!isMountedRef.current || isAbortedRef.current) {
          // #region agent log
          const logData = {
            location: 'useChat.ts:onStep:unmounted',
            message: 'Step callback after unmount',
            data: { requestId, isMounted: isMountedRef.current, isAborted: isAbortedRef.current },
            timestamp: Date.now(),
            sessionId: 'debug-session',
            runId: 'run1',
            hypothesisId: 'E',
          };
          console.warn('[DEBUG]', logData);
          fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(logData),
          }).catch(() => {});
          // #endregion
          return;
        }

        // Double-check before updating messages
        if (!isMountedRef.current || isAbortedRef.current) {
          // #region agent log
          const logData = {
            location: 'useChat.ts:onStep:setMessages:blocked',
            message: 'setMessages blocked in onStep after unmount check',
            data: { requestId, isMounted: isMountedRef.current, isAborted: isAbortedRef.current },
            timestamp: Date.now(),
            sessionId: 'debug-session',
            runId: 'run1',
            hypothesisId: 'A',
          };
          console.warn('[DEBUG]', logData);
          fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(logData),
          }).catch(() => {});
          // #endregion
          return;
        }

        setMessages((prev) => {
          // #region agent log
          // Hypothesis B: setMessages function executes after unmount
          const logData = {
            location: 'useChat.ts:onStep:setMessages:executing',
            message: 'setMessages function executing in onStep',
            data: { requestId, isMounted: isMountedRef.current, isAborted: isAbortedRef.current, prevLength: prev.length },
            timestamp: Date.now(),
            sessionId: 'debug-session',
            runId: 'run1',
            hypothesisId: 'B',
          };
          console.warn('[DEBUG]', logData);
          fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(logData),
          }).catch(() => {});
          // #endregion
          
          // Double-check INSIDE the setState function (Hypothesis B)
          if (!isMountedRef.current || isAbortedRef.current) {
            // #region agent log
            const logData = {
              location: 'useChat.ts:onStep:setMessages:inside:unmounted',
              message: 'setMessages function executing AFTER unmount detected',
              data: { requestId, isMounted: isMountedRef.current, isAborted: isAbortedRef.current },
              timestamp: Date.now(),
              sessionId: 'debug-session',
              runId: 'run1',
              hypothesisId: 'B',
            };
            console.warn('[DEBUG]', logData);
            fetch('http://127.0.0.1:7242/ingest/48de47fc-54d6-439e-b870-9304357bbf28', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(logData),
            }).catch(() => {});
            // #endregion
            return prev; // Return previous state without modification
          }
          
          const newMessages = [...prev];
          const lastMsg = newMessages[newMessages.length - 1];
          if (lastMsg.role === 'assistant') {
            const updatedSteps = [...(lastMsg.steps || []), step];
            let newStatus = lastMsg.currentStatus;

            if (step.type === 'status') {
              newStatus = step.data;
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
      abortController.signal
      );
    } catch (error) {
      // Handle any unhandled errors from sendMessageStreaming
      if (!isMountedRef.current || isAbortedRef.current) {
        console.warn('[DEBUG] Unhandled error in sendMessageStreaming after unmount', error);
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
      console.warn('[DEBUG] handleImageGenerate called after unmount/abort');
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
      console.warn('[DEBUG] setMessages called in handleImageGenerate after unmount check failed');
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
        console.warn('[DEBUG] setMessages called in handleImageGenerate success after unmount check failed');
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
        console.warn('[DEBUG] setMessages called in handleImageGenerate error after unmount check failed');
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
          console.warn('[DEBUG] setMessages called in loadConversation after unmount check failed');
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
