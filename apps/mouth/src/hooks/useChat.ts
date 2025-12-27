import { useState, useCallback } from 'react';
import { api, type ApiError } from '@/lib/api';
import { Message } from '@/types';
import { useChatMessages } from './useChatMessages';
import { useChatStreaming } from './useChatStreaming';

export function useChat() {
  const [input, setInput] = useState('');
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [showImagePrompt, setShowImagePrompt] = useState(false);

  // Compose specialized hooks
  const chatMessages = useChatMessages();
  const {
    messages,
    setMessages,
    addMessages,
    appendToLastAssistantContent,
    updateLastAssistantMessage,
    addStepToLastAssistant,
    clearMessages: clearMessagesInternal,
    isMountedRef,
    isAbortedRef,
  } = chatMessages;

  const streaming = useChatStreaming({
    sessionId: currentSessionId,
    isMountedRef,
    isAbortedRef,
  });
  const { isStreaming, setIsStreaming, sendStreamingMessage } = streaming;

  const generateSessionId = () => {
    return `session-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
  };

  const handleSend = async () => {
    if (!input.trim() || isStreaming) return;

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

    const assistantMessage: Message = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      steps: [],
      currentStatus: 'Thinking...',
    };

    if (!isMountedRef.current || isAbortedRef.current) return;

    addMessages([userMessage, assistantMessage]);
    const messageToSend = input;
    setInput('');
    setIsStreaming(true);

    const conversationHistory = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));
    conversationHistory.push({ role: 'user', content: messageToSend });

    await sendStreamingMessage(messageToSend, conversationHistory, {
      onChunk: (chunk) => {
        appendToLastAssistantContent(chunk);
      },
      onComplete: (fullResponse, sources, metadata) => {
        updateLastAssistantMessage({ content: fullResponse, sources, metadata });
        // Save conversation
        if (isMountedRef.current && !isAbortedRef.current) {
          const allMessages = [...messages, userMessage, { ...assistantMessage, content: fullResponse, sources, metadata }];
          const messagesToSave = allMessages.map((m) => ({
            role: m.role,
            content: m.content,
            sources: m.sources,
            imageUrl: m.imageUrl,
          }));
          api.saveConversation(messagesToSave, sessionId!, metadata).catch((err) => {
            if (isMountedRef.current) console.error('Failed to save conversation:', err);
          });
        }
      },
      onError: (error) => {
        let errorMessage = 'Sorry, there was an error processing your request. Please try again.';
        const err = error as ApiError;
        if (err.code === 'QUOTA_EXCEEDED' || error.message.includes('429')) {
          errorMessage = '⚠️ Usage limit reached. Please wait a moment before trying again.';
        } else if (err.code === 'SERVICE_UNAVAILABLE' || error.message.includes('Database service temporarily unavailable')) {
          errorMessage = '⚠️ System is currently busy. Please try again in a few seconds.';
        }
        updateLastAssistantMessage({ content: errorMessage });
      },
      onStep: (step) => {
        addStepToLastAssistant(step);
      },
    });
  };

  const handleImageGenerate = async () => {
    if (!input.trim() || isStreaming) return;
    if (!isMountedRef.current || isAbortedRef.current) return;

    const promptToGenerate = input;
    const userMessage: Message = {
      role: 'user',
      content: `Generate image: ${promptToGenerate}`,
      timestamp: new Date(),
    };

    addMessages([userMessage]);
    setInput('');
    setIsStreaming(true);
    setShowImagePrompt(false);

    try {
      const response = await api.generateImage(promptToGenerate);
      if (!isMountedRef.current) return;

      const assistantMessage: Message = {
        role: 'assistant',
        content: 'Here is your generated image:',
        imageUrl: response.image_url,
        timestamp: new Date(),
      };
      addMessages([assistantMessage]);
    } catch (error) {
      if (!isMountedRef.current) return;
      console.error('Failed to generate image:', error);
      const errorMessage: Message = {
        role: 'assistant',
        content: 'Sorry, failed to generate the image. Please try again.',
        timestamp: new Date(),
      };
      addMessages([errorMessage]);
    } finally {
      if (isMountedRef.current) {
        setIsStreaming(false);
      }
    }
  };

  const clearMessages = useCallback(() => {
    clearMessagesInternal();
    setCurrentSessionId(null);
  }, [clearMessagesInternal]);

  const loadConversation = useCallback(async (conversationId: number) => {
    setIsStreaming(true);
    try {
      const response = await api.getConversation(conversationId);
      if (!isMountedRef.current) return;

      if (response.success && response.messages) {
        if (!isMountedRef.current || isAbortedRef.current) return;

        const formattedMessages: Message[] = response.messages.map((msg, index) => ({
          id: `conv-${conversationId}-${index}`,
          role: msg.role as 'user' | 'assistant',
          content: msg.content,
          sources: msg.sources,
          imageUrl: msg.imageUrl,
          timestamp: new Date(response.created_at || Date.now()),
        }));
        setMessages(formattedMessages);
        if (response.session_id && isMountedRef.current && !isAbortedRef.current) {
          setCurrentSessionId(response.session_id);
        }
      }
    } catch (error) {
      if (!isMountedRef.current) return;
      console.error('Failed to load conversation:', error);
    } finally {
      if (isMountedRef.current) {
        setIsStreaming(false);
      }
    }
  }, [isMountedRef, isAbortedRef, setMessages, setIsStreaming]);

  const handleFileUpload = async (file: File) => {
    setIsStreaming(true);
    try {
      const response = await api.uploadFile(file);
      if (!isMountedRef.current) return null;
      return response;
    } catch (error) {
      if (!isMountedRef.current) return null;
      console.error('Failed to upload file:', error);
      return null;
    } finally {
      if (isMountedRef.current) {
        setIsStreaming(false);
      }
    }
  };

  // RETURN SAME PUBLIC API AS BEFORE
  return {
    messages,
    setMessages,
    input,
    setInput,
    isLoading: isStreaming,
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
