import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, ConversationListItem } from '@/lib/api';

/**
 * Query key factory for conversations
 */
export const conversationsKeys = {
  all: ['conversations'] as const,
  list: () => [...conversationsKeys.all, 'list'] as const,
  stats: () => [...conversationsKeys.all, 'stats'] as const,
  detail: (id: number) => [...conversationsKeys.all, 'detail', id] as const,
};

/**
 * Hook for listing conversations with React Query
 */
export function useConversationsList(limit: number = 20, offset: number = 0) {
  return useQuery({
    queryKey: [...conversationsKeys.list(), limit, offset],
    queryFn: () => api.listConversations(limit, offset),
    staleTime: 1000 * 30, // 30 seconds
    select: (data) => data.conversations,
  });
}

/**
 * Hook for conversation mutations (delete, clear)
 */
export function useConversationMutations() {
  const queryClient = useQueryClient();

  const invalidateConversations = () => {
    queryClient.invalidateQueries({ queryKey: conversationsKeys.list() });
    queryClient.invalidateQueries({ queryKey: conversationsKeys.stats() });
  };

  const deleteConversation = useMutation({
    mutationFn: (conversationId: number) => api.deleteConversation(conversationId),
    onMutate: async (conversationId) => {
      // Optimistic update: Remove from list immediately
      await queryClient.cancelQueries({ queryKey: conversationsKeys.list() });
      const previousData = queryClient.getQueriesData<ConversationListItem[]>({
        queryKey: conversationsKeys.list(),
      });

      queryClient.setQueriesData<ConversationListItem[]>(
        { queryKey: conversationsKeys.list() },
        (old) => (old ? old.filter((c) => c.id !== conversationId) : old)
      );

      return { previousData };
    },
    onError: (_err, _conversationId, context) => {
      // Rollback on error
      if (context?.previousData) {
        context.previousData.forEach(([key, data]) => {
          queryClient.setQueryData(key, data);
        });
      }
    },
    onSettled: invalidateConversations,
  });

  const clearConversations = useMutation({
    mutationFn: (sessionId?: string) => api.clearConversations(sessionId),
    onSuccess: () => {
      // Clear the cache
      queryClient.setQueriesData<ConversationListItem[]>(
        { queryKey: conversationsKeys.list() },
        () => []
      );
    },
    onSettled: invalidateConversations,
  });

  return {
    deleteConversation,
    clearConversations,
  };
}

/**
 * Combined hook with local state for current conversation selection
 * Maintains backward compatibility with the original API
 */
export function useConversations() {
  const [currentConversationId, setCurrentConversationId] = useState<number | null>(null);

  const {
    data: conversations = [],
    isLoading,
    refetch: loadConversationList,
  } = useConversationsList();

  const { deleteConversation: deleteConversationMutation, clearConversations: clearHistoryMutation } =
    useConversationMutations();

  const deleteConversation = async (conversationId: number) => {
    try {
      await deleteConversationMutation.mutateAsync(conversationId);
      if (currentConversationId === conversationId) {
        setCurrentConversationId(null);
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    }
  };

  const clearHistory = async () => {
    try {
      await clearHistoryMutation.mutateAsync(undefined);
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
    loadConversationList: () => {
      loadConversationList();
    },
    deleteConversation,
    clearHistory,
  };
}
