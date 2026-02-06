/**
 * useCrmClients Hook
 * 
 * Hook ottimizzato per gestione clienti CRM con caching e sincronizzazione
 */

import { useCallback, useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { Client, CreateClientParams } from '@/lib/api/crm/crm.types';
import { debug, error } from '@/lib/utils';

interface UseCrmClientsOptions {
  status?: string;
  assigned_to?: string;
  search?: string;
  limit?: number;
  enabled?: boolean;
}

interface ClientsResponse {
  clients: Client[];
  total: number;
  hasMore: boolean;
}

/**
 * Hook per gestione lista clienti con infinite scroll
 */
export function useCrmClients(options: UseCrmClientsOptions = {}) {
  const { status, assigned_to, search, limit = 50, enabled = true } = options;
  const queryClient = useQueryClient();

  const queryKey = ['crm', 'clients', { status, assigned_to, search }];

  const {
    data,
    isLoading,
    isError,
    error: queryError,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useQuery({
    queryKey,
    queryFn: async ({ pageParam = 0 }): Promise<ClientsResponse> => {
      const params = new URLSearchParams();
      if (status) params.append('status', status);
      if (assigned_to) params.append('assigned_to', assigned_to);
      if (search) params.append('search', search);
      params.append('limit', limit.toString());
      params.append('offset', (pageParam * limit).toString());

      const response = await api.client.request<{
        clients: Client[];
        total: number;
      }>(`/api/crm/clients?${params.toString()}`);

      return {
        clients: response.clients,
        total: response.total,
        hasMore: response.clients.length === limit,
      };
    },
    enabled,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
  });

  // Prefetch next page
  useEffect(() => {
    if (hasNextPage && !isFetchingNextPage) {
      const nextOffset = ((data?.clients.length || 0) / limit) + 1;
      queryClient.prefetchQuery({
        queryKey: [...queryKey, nextOffset],
        queryFn: async () => {
          const params = new URLSearchParams();
          if (status) params.append('status', status);
          if (assigned_to) params.append('assigned_to', assigned_to);
          if (search) params.append('search', search);
          params.append('limit', limit.toString());
          params.append('offset', (nextOffset * limit).toString());

          return api.client.request(`/api/crm/clients?${params.toString()}`);
        },
      });
    }
  }, [hasNextPage, isFetchingNextPage, data?.clients.length, limit, queryClient, queryKey, status, assigned_to, search]);

  const loadMore = useCallback(() => {
    if (hasNextPage && !isFetchingNextPage) {
      fetchNextPage();
    }
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  return {
    clients: data?.clients || [],
    total: data?.total || 0,
    isLoading,
    isError,
    error: queryError,
    loadMore,
    hasMore: !!hasNextPage,
    isLoadingMore: isFetchingNextPage,
  };
}

/**
 * Hook per singolo cliente con caching
 */
export function useCrmClient(clientId: number | null) {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ['crm', 'clients', clientId],
    queryFn: async (): Promise<Client> => {
      if (!clientId) throw new Error('Client ID required');
      return api.client.request<Client>(`/api/crm/clients/${clientId}`);
    },
    enabled: !!clientId,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['crm', 'clients', clientId] });
  }, [queryClient, clientId]);

  return {
    ...query,
    invalidate,
  };
}

/**
 * Hook per creazione cliente
 */
export function useCreateClient() {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: async (data: CreateClientParams) => {
      return api.client.request<Client>('/api/crm/clients', {
        method: 'POST',
        body: JSON.stringify(data),
      });
    },
    onSuccess: (newClient) => {
      // Invalidate clients list
      queryClient.invalidateQueries({ queryKey: ['crm', 'clients'] });
      // Add to cache
      queryClient.setQueryData(['crm', 'clients', newClient.id], newClient);
      debug('Client created:', newClient.id);
    },
    onError: (err) => {
      error('Failed to create client:', err);
    },
  });

  return mutation;
}

/**
 * Hook per aggiornamento cliente
 */
export function useUpdateClient(clientId: number) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: async (updates: Partial<CreateClientParams>) => {
      return api.client.request<Client>(`/api/crm/clients/${clientId}`, {
        method: 'PATCH',
        body: JSON.stringify(updates),
      });
    },
    onSuccess: (updatedClient) => {
      // Update cache
      queryClient.setQueryData(['crm', 'clients', clientId], updatedClient);
      // Invalidate list
      queryClient.invalidateQueries({ queryKey: ['crm', 'clients'] });
      debug('Client updated:', clientId);
    },
    onError: (err) => {
      error('Failed to update client:', err);
    },
  });

  return mutation;
}

/**
 * Hook per statistiche CRM
 */
export function useCrmStats() {
  return useQuery({
    queryKey: ['crm', 'stats'],
    queryFn: async () => {
      return api.client.request<{
        totalClients: number;
        activePractices: number;
        revenue: { total: number; paid: number; outstanding: number };
        byStatus: Record<string, number>;
      }>('/api/crm/stats');
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
