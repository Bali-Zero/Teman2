/**
 * useCrmPractices Hook
 * 
 * Hook ottimizzato per gestione pratiche CRM
 */

import { useCallback, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { Practice, CreatePracticeParams } from '@/lib/api/crm/crm.types';
import { debug, error } from '@/lib/utils';

interface UseCrmPracticesOptions {
  clientId?: number;
  status?: string;
  assigned_to?: string;
  limit?: number;
  enabled?: boolean;
}

interface PracticesResponse {
  practices: Practice[];
  total: number;
  hasMore: boolean;
}

const PRACTICE_STATUSES = [
  { value: 'inquiry', label: 'Inquiry', color: 'blue' },
  { value: 'quotation_sent', label: 'Quotation Sent', color: 'yellow' },
  { value: 'payment_pending', label: 'Payment Pending', color: 'orange' },
  { value: 'in_progress', label: 'In Progress', color: 'indigo' },
  { value: 'completed', label: 'Completed', color: 'green' },
  { value: 'cancelled', label: 'Cancelled', color: 'red' },
  { value: 'on_hold', label: 'On Hold', color: 'gray' },
] as const;

const PRACTICE_PRIORITIES = [
  { value: 'low', label: 'Low', color: 'gray' },
  { value: 'normal', label: 'Normal', color: 'blue' },
  { value: 'high', label: 'High', color: 'orange' },
  { value: 'urgent', label: 'Urgent', color: 'red' },
] as const;

/**
 * Hook per lista pratiche
 */
export function useCrmPractices(options: UseCrmPracticesOptions = {}) {
  const { clientId, status, assigned_to, limit = 50, enabled = true } = options;
  const [offset, setOffset] = useState(0);

  const queryKey = ['crm', 'practices', { clientId, status, assigned_to, offset }];

  const {
    data,
    isLoading,
    isError,
    error: queryError,
    refetch,
  } = useQuery({
    queryKey,
    queryFn: async (): Promise<PracticesResponse> => {
      const params = new URLSearchParams();
      if (clientId) params.append('client_id', clientId.toString());
      if (status) params.append('status', status);
      if (assigned_to) params.append('assigned_to', assigned_to);
      params.append('limit', limit.toString());
      params.append('offset', offset.toString());

      const response = await api.client.request<{
        practices: Practice[];
        total: number;
      }>(`/api/crm/practices?${params.toString()}`);

      return {
        practices: response.practices,
        total: response.total,
        hasMore: response.practices.length === limit,
      };
    },
    enabled,
    staleTime: 3 * 60 * 1000, // 3 minutes
  });

  const loadMore = useCallback(() => {
    if (data?.hasMore) {
      setOffset((prev) => prev + limit);
    }
  }, [data?.hasMore, limit]);

  const reset = useCallback(() => {
    setOffset(0);
    refetch();
  }, [refetch]);

  return {
    practices: data?.practices || [],
    total: data?.total || 0,
    isLoading,
    isError,
    error: queryError,
    loadMore,
    hasMore: data?.hasMore || false,
    reset,
    refetch,
  };
}

/**
 * Hook per singola pratica
 */
export function useCrmPractice(practiceId: number | null) {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ['crm', 'practices', practiceId],
    queryFn: async (): Promise<Practice> => {
      if (!practiceId) throw new Error('Practice ID required');
      return api.client.request<Practice>(`/api/crm/practices/${practiceId}`);
    },
    enabled: !!practiceId,
    staleTime: 2 * 60 * 1000,
  });

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['crm', 'practices', practiceId] });
  }, [queryClient, practiceId]);

  return {
    ...query,
    invalidate,
  };
}

/**
 * Hook per creazione pratica
 */
export function useCreatePractice() {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: async (data: CreatePracticeParams) => {
      return api.client.request<Practice>('/api/crm/practices', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    onSuccess: (newPractice, variables) => {
      // Invalidate practices list
      queryClient.invalidateQueries({ queryKey: ['crm', 'practices'] });
      // Invalidate client practices if client_id provided
      if (variables.client_id) {
        queryClient.invalidateQueries({
          queryKey: ['crm', 'practices', { clientId: variables.client_id }],
        });
      }
      debug('Practice created:', newPractice.id);
    },
    onError: (err) => {
      error('Failed to create practice:', err);
    },
  });

  return mutation;
}

/**
 * Hook per aggiornamento stato pratica
 */
export function useUpdatePracticeStatus(practiceId: number) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: async ({ status, notes }: { status: string; notes?: string }) => {
      return api.client.request<Practice>(`/api/crm/practices/${practiceId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status, notes }),
      });
    },
    onSuccess: (updatedPractice) => {
      // Update cache
      queryClient.setQueryData(['crm', 'practices', practiceId], updatedPractice);
      // Invalidate lists
      queryClient.invalidateQueries({ queryKey: ['crm', 'practices'] });
      debug('Practice status updated:', practiceId);
    },
    onError: (err) => {
      error('Failed to update practice status:', err);
    },
  });

  return mutation;
}

/**
 * Hook per pratiche in scadenza
 */
export function useOverduePractices(days: number = 30) {
  return useQuery({
    queryKey: ['crm', 'practices', 'overdue', days],
    queryFn: async () => {
      return api.client.request<Practice[]>(`/api/crm/practices/overdue?days=${days}`);
    },
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Hook per assegnazione pratica
 */
export function useAssignPractice(practiceId: number) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: async (assignedTo: string) => {
      return api.client.request<Practice>(`/api/crm/practices/${practiceId}/assign`, {
        method: 'POST',
        body: JSON.stringify({ assigned_to: assignedTo }),
      });
    },
    onSuccess: (updatedPractice) => {
      queryClient.setQueryData(['crm', 'practices', practiceId], updatedPractice);
      queryClient.invalidateQueries({ queryKey: ['crm', 'practices'] });
      debug('Practice assigned:', practiceId);
    },
    onError: (err) => {
      error('Failed to assign practice:', err);
    },
  });

  return mutation;
}

export { PRACTICE_STATUSES, PRACTICE_PRIORITIES };
