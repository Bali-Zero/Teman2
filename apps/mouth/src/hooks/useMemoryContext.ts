import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import { UserMemoryContext } from '@/types';

interface UseMemoryContextReturn {
  memoryContext: UserMemoryContext | null;
  isLoading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  hasMemory: boolean;
}

/**
 * Hook to fetch and manage user memory context
 *
 * The memory context contains:
 * - profile_facts: List of facts the AI has learned about the user
 * - summary: A summary of user's interests/history
 * - counters: Usage counters (conversations, searches, tasks)
 * - has_data: Whether the user has any stored memory
 */
export function useMemoryContext(): UseMemoryContextReturn {
  const [memoryContext, setMemoryContext] = useState<UserMemoryContext | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchMemoryContext = useCallback(async () => {
    // Only fetch if user is authenticated
    if (!api.isAuthenticated()) {
      setMemoryContext(null);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const context = await api.getUserMemoryContext();
      setMemoryContext(context);
    } catch (err) {
      console.error('Failed to fetch memory context:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch memory context');
      setMemoryContext(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch on mount and when auth status changes
  useEffect(() => {
    fetchMemoryContext();
  }, [fetchMemoryContext]);

  return {
    memoryContext,
    isLoading,
    error,
    refresh: fetchMemoryContext,
    hasMemory: memoryContext?.has_data ?? false,
  };
}

/**
 * Format memory context for display
 */
export function formatMemoryForDisplay(context: UserMemoryContext | null): string[] {
  if (!context?.has_data) {
    return [];
  }

  const lines: string[] = [];

  if (context.profile_facts.length > 0) {
    lines.push(...context.profile_facts);
  }

  if (context.summary) {
    lines.push(`Summary: ${context.summary}`);
  }

  return lines;
}

/**
 * Get a brief summary of user's memory for display
 */
export function getMemorySummary(context: UserMemoryContext | null): string {
  if (!context?.has_data) {
    return 'No memory stored yet';
  }

  const factCount = context.profile_facts.length;
  const conversations = context.counters.conversations || 0;

  if (factCount === 0) {
    return 'Getting to know you...';
  }

  return `${factCount} fact${factCount !== 1 ? 's' : ''} learned from ${conversations} conversation${conversations !== 1 ? 's' : ''}`;
}
