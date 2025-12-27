import { useState, useCallback, useRef, useEffect } from 'react';
import { Message, AgentStep } from '@/types';

export interface UseChatMessagesReturn {
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  addMessage: (message: Message) => void;
  addMessages: (messages: Message[]) => void;
  updateLastAssistantMessage: (updates: Partial<Message>) => void;
  appendToLastAssistantContent: (chunk: string) => void;
  addStepToLastAssistant: (step: AgentStep) => void;
  updateLastAssistantStatus: (status: string) => void;
  clearMessages: () => void;
  getLastMessage: () => Message | undefined;
  isMountedRef: React.MutableRefObject<boolean>;
  isAbortedRef: React.MutableRefObject<boolean>;
}

export function useChatMessages(): UseChatMessagesReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const isMountedRef = useRef(true);
  const isAbortedRef = useRef(false);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const safeSetMessages = useCallback(
    (updater: (prev: Message[]) => Message[]) => {
      if (!isMountedRef.current || isAbortedRef.current) return;
      setMessages((prev) => {
        if (!isMountedRef.current || isAbortedRef.current) return prev;
        return updater(prev);
      });
    },
    []
  );

  const addMessage = useCallback(
    (message: Message) => {
      safeSetMessages((prev) => [...prev, message]);
    },
    [safeSetMessages]
  );

  const addMessages = useCallback(
    (newMessages: Message[]) => {
      safeSetMessages((prev) => [...prev, ...newMessages]);
    },
    [safeSetMessages]
  );

  const updateLastAssistantMessage = useCallback(
    (updates: Partial<Message>) => {
      safeSetMessages((prev) => {
        const newMessages = [...prev];
        const lastMsg = newMessages[newMessages.length - 1];
        if (lastMsg?.role === 'assistant') {
          newMessages[newMessages.length - 1] = { ...lastMsg, ...updates };
        }
        return newMessages;
      });
    },
    [safeSetMessages]
  );

  const appendToLastAssistantContent = useCallback(
    (chunk: string) => {
      safeSetMessages((prev) => {
        const newMessages = [...prev];
        const lastMsg = newMessages[newMessages.length - 1];
        if (lastMsg?.role === 'assistant') {
          newMessages[newMessages.length - 1] = {
            ...lastMsg,
            content: lastMsg.content + chunk,
          };
        }
        return newMessages;
      });
    },
    [safeSetMessages]
  );

  const addStepToLastAssistant = useCallback(
    (step: AgentStep) => {
      safeSetMessages((prev) => {
        const newMessages = [...prev];
        const lastMsg = newMessages[newMessages.length - 1];
        if (lastMsg?.role === 'assistant') {
          const updatedSteps = [...(lastMsg.steps || []), step];
          let newStatus = lastMsg.currentStatus;

          if (step.type === 'status') {
            newStatus = step.data;
          } else if (step.type === 'phase') {
            const phaseName = step.data.name;
            const phaseStatus = step.data.status;
            if (phaseStatus === 'started') {
              newStatus =
                phaseName === 'giant'
                  ? 'Giant Reasoning...'
                  : phaseName === 'cell'
                    ? 'Cell Calibration...'
                    : 'Zantara Synthesis...';
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
    [safeSetMessages]
  );

  const updateLastAssistantStatus = useCallback(
    (status: string) => {
      updateLastAssistantMessage({ currentStatus: status });
    },
    [updateLastAssistantMessage]
  );

  const clearMessages = useCallback(() => {
    if (isMountedRef.current) {
      setMessages([]);
    }
  }, []);

  const getLastMessage = useCallback(() => {
    return messages[messages.length - 1];
  }, [messages]);

  return {
    messages,
    setMessages,
    addMessage,
    addMessages,
    updateLastAssistantMessage,
    appendToLastAssistantContent,
    addStepToLastAssistant,
    updateLastAssistantStatus,
    clearMessages,
    getLastMessage,
    isMountedRef,
    isAbortedRef,
  };
}
