import { useState, useCallback } from 'react';
import { api, type ApiError } from '@/lib/api';
import { Message, AgentStep } from '@/types';
import { useConversationMonitoring } from '@/lib/monitoring';

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [showImagePrompt, setShowImagePrompt] = useState(false);

  // Conversation monitoring
  const monitoring = useConversationMonitoring(currentSessionId);

  const generateSessionId = () => {
    return `session-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

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

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setInput('');
    setIsLoading(true);

    const messageToSend = input;

    // Build conversation history from current messages (excluding the new user message and empty assistant message)
    // This ensures the LLM has context even if DB is unavailable
    const conversationHistory = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));
    // Add the new user message to history
    conversationHistory.push({ role: 'user', content: messageToSend });

    await api.sendMessageStreaming(
      messageToSend,
      sessionId || undefined,
      (chunk: string) => {
        setMessages((prev) => {
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
        // Track successful message
        monitoring.trackMessage(false);

        setMessages((prev) => {
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
            api.saveConversation(messagesToSave, sessionId!, metadata).catch(console.error);

            return newMessages;
          }
          return newMessages;
        });
        setIsLoading(false);
      },
      (error: Error) => {
        console.error('Failed to send message:', error);

        // Track error in monitoring
        const err = error as ApiError;
        const errorCode =
          err.code || (error.message.includes('429') ? 'QUOTA_EXCEEDED' : 'UNKNOWN');
        monitoring.trackError(errorCode);

        setMessages((prev) => {
          const newMessages = [...prev];
          const lastMsg = newMessages[newMessages.length - 1];

          let errorMessage = 'Sorry, there was an error processing your request. Please try again.';

          // Check for specific error codes or messages
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
        setIsLoading(false);
      },
      (step: AgentStep) => {
        setMessages((prev) => {
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
      conversationHistory
    );
  };

  const handleImageGenerate = async () => {
    if (!input.trim() || isLoading) return;

    const promptToGenerate = input;
    const userMessage: Message = {
      role: 'user',
      content: `Generate image: ${promptToGenerate}`,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setShowImagePrompt(false);

    try {
      const response = await api.generateImage(promptToGenerate);
      const assistantMessage: Message = {
        role: 'assistant',
        content: 'Here is your generated image:',
        imageUrl: response.image_url,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error) {
      console.error('Failed to generate image:', error);
      const errorMessage: Message = {
        role: 'assistant',
        content: 'Sorry, failed to generate the image. Please try again.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const clearMessages = useCallback(() => {
    setMessages([]);
    setCurrentSessionId(null);
  }, []);

  const loadConversation = useCallback(async (conversationId: number) => {
    setIsLoading(true);
    try {
      const response = await api.getConversation(conversationId);
      if (response.success && response.messages) {
        const formattedMessages: Message[] = response.messages.map((msg, index) => ({
          id: `conv-${conversationId}-${index}`,
          role: msg.role as 'user' | 'assistant',
          content: msg.content,
          sources: msg.sources,
          imageUrl: msg.imageUrl,
          timestamp: new Date(response.created_at || Date.now()),
        }));
        setMessages(formattedMessages);
        if (response.session_id) {
          setCurrentSessionId(response.session_id);
        }
      }
    } catch (error) {
      console.error('Failed to load conversation:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const handleFileUpload = async (file: File) => {
    setIsLoading(true);
    try {
      const response = await api.uploadFile(file);
      setIsLoading(false);
      return response;
    } catch (error) {
      console.error('Failed to upload file:', error);
      setIsLoading(false);
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
