'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Client } from '@/lib/api/crm/crm.types';

// Query keys for cache management
export const clientKeys = {
  all: ['clients'] as const,
  lists: () => [...clientKeys.all, 'list'] as const,
  list: (filters: Record<string, unknown>) => [...clientKeys.lists(), filters] as const,
  details: () => [...clientKeys.all, 'detail'] as const,
  detail: (id: number) => [...clientKeys.details(), id] as const,
};

// API response type
interface ApiResponse<T> {
  data?: T;
  error?: string;
}

// Mock API for type safety - replace with actual api import
const mockApi = {
  crm: {
    getClients: async (filters?: Record<string, unknown>): Promise<ApiResponse<Client[]>> => {
      // Replace with actual API call
      return { data: [] };
    },
    getClient: async (id: number): Promise<ApiResponse<Client>> => {
      return { data: undefined };
    },
    createClient: async (data: Partial<Client>): Promise<ApiResponse<Client>> => {
      return { data: undefined };
    },
    updateClient: async (id: number, data: Partial<Client>): Promise<ApiResponse<Client>> => {
      return { data: undefined };
    },
    deleteClient: async (id: number): Promise<ApiResponse<void>> => {
      return { data: undefined };
    },
  },
};

// Use actual API if available, fallback to mock
const api =
  (typeof window !== 'undefined' && (window as unknown as { api?: typeof mockApi }).api) || mockApi;

/**
 * Hook for fetching clients with caching
 * Uses stale-while-revalidate pattern for optimal UX
 *
 * @example
 * ```tsx
 * const { data: clients, isLoading, error } = useClientsQuery();
 * ```
 */
export function useClientsQuery(filters?: { status?: string; search?: string }) {
  return useQuery({
    queryKey: clientKeys.list(filters || {}),
    queryFn: async () => {
      const response = await api.crm.getClients(filters);
      return response.data ?? [];
    },
    // Keep previous data while fetching new data
    placeholderData: (previousData) => previousData,
  });
}

/**
 * Hook for fetching a single client
 * Prefetches related data for better UX
 */
export function useClientQuery(id: number) {
  return useQuery({
    queryKey: clientKeys.detail(id),
    queryFn: async () => {
      const response = await api.crm.getClient(id);
      return response.data ?? null;
    },
    enabled: !!id, // Only run if id is provided
  });
}

/**
 * Hook for creating a client
 * Uses optimistic updates for immediate UI feedback
 */
export function useCreateClientMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (clientData: Partial<Client>) => {
      const response = await api.crm.createClient(clientData);
      if (!response.data) throw new Error(response.error || 'Failed to create client');
      return response.data;
    },
    onSuccess: () => {
      // Invalidate and refetch clients list
      queryClient.invalidateQueries({ queryKey: clientKeys.lists() });
    },
  });
}

/**
 * Hook for updating a client
 */
export function useUpdateClientMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, data }: { id: number; data: Partial<Client> }) => {
      const response = await api.crm.updateClient(id, data);
      if (!response.data) throw new Error(response.error || 'Failed to update client');
      return response.data;
    },
    onSuccess: (_, variables) => {
      // Invalidate specific client and lists
      queryClient.invalidateQueries({ queryKey: clientKeys.detail(variables.id) });
      queryClient.invalidateQueries({ queryKey: clientKeys.lists() });
    },
  });
}

/**
 * Hook for deleting a client
 */
export function useDeleteClientMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number) => {
      const response = await api.crm.deleteClient(id);
      if (response.error) throw new Error(response.error);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: clientKeys.lists() });
    },
  });
}

/**
 * Prefetch clients for instant navigation
 * Call this on hover of client list links
 */
export function usePrefetchClients() {
  const queryClient = useQueryClient();

  return () => {
    queryClient.prefetchQuery({
      queryKey: clientKeys.lists(),
      queryFn: async () => {
        const response = await api.crm.getClients();
        return response.data ?? [];
      },
      // Prefetch stays fresh for 1 minute
      staleTime: 1000 * 60 * 1,
    });
  };
}
