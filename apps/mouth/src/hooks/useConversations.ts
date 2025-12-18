import { useState, useCallback } from 'react';
import { api, ConversationListItem } from '@/lib/api';

export function useConversations() {
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [currentConversationId, setCurrentConversationId] = useState<number | null>(null);

  const loadConversationList = useCallback(async () => {
    setIsLoading(true);
    try {
      const response = await api.listConversations(20, 0);
      if (response.success) {
        setConversations(response.conversations);
      }
    } catch (error) {
      console.error('Failed to load conversations:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const deleteConversation = async (conversationId: number) => {
    try {
      await api.deleteConversation(conversationId);
      if (currentConversationId === conversationId) {
        setCurrentConversationId(null);
      }
      loadConversationList();
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    }
  };

  const clearHistory = async () => {
    try {
      await api.clearConversations();
      setConversations([]);
      setCurrentConversationId(null);
    } catch (error) {
      console.error('Failed to clear history:', error);
    }
  };

  return {
    conversations,
    isLoading,
    currentConversationId,
    setCurrentConversationId,
    loadConversationList,
    deleteConversation,
    clearHistory,
  };
}
