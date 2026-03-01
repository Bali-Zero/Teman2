/**
 * useCrmClients Hook
 *
 * Hook ottimizzato per gestione clienti CRM con caching e sincronizzazione
 */

import { useCallback, useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Client, CreateClientParams } from "@/lib/api/crm/crm.types";

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

// Debug helper
const debug = (...args: unknown[]) => {
  if (process.env.NODE_ENV === "development") {
    console.log("[CRM]", ...args);
  }
};

const logError = (...args: unknown[]) => {
  console.error("[CRM]", ...args);
};

/**
 * Hook per gestione lista clienti
 */
export function useCrmClients(options: UseCrmClientsOptions = {}) {
  const { status, assigned_to, search, limit = 50, enabled = true } = options;
  const queryClient = useQueryClient();
  const [offset, setOffset] = useState(0);

  const queryKey = ["crm", "clients", { status, assigned_to, search, offset }];

  const {
    data,
    isLoading,
    isError,
    error: queryError,
    refetch,
  } = useQuery({
    queryKey,
    queryFn: async (): Promise<ClientsResponse> => {
      const clients = await api.crm.getClients({
        search: search || undefined,
        limit,
        offset,
      });

      return {
        clients,
        total: clients.length, // Backend doesn't return total, estimate
        hasMore: clients.length === limit,
      };
    },
    enabled,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes
  });

  const loadMore = useCallback(() => {
    if (data?.hasMore && !isLoading) {
      setOffset((prev) => prev + limit);
    }
  }, [data?.hasMore, isLoading, limit]);

  const reset = useCallback(() => {
    setOffset(0);
    refetch();
  }, [refetch]);

  return {
    clients: data?.clients || [],
    total: data?.total || 0,
    isLoading,
    isError,
    error: queryError,
    loadMore,
    hasMore: data?.hasMore || false,
    isLoadingMore: isLoading && offset > 0,
    reset,
    refetch,
  };
}

/**
 * Hook per singolo cliente con caching
 */
export function useCrmClient(clientId: number | null) {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["crm", "clients", clientId],
    queryFn: async (): Promise<Client> => {
      if (!clientId) throw new Error("Client ID required");
      return api.crm.getClient(clientId);
    },
    enabled: !!clientId,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["crm", "clients", clientId] });
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
    mutationFn: async ({
      data,
      createdBy,
    }: {
      data: CreateClientParams;
      createdBy: string;
    }) => {
      return api.crm.createClient(data, createdBy);
    },
    onSuccess: (newClient) => {
      // Invalidate clients list
      queryClient.invalidateQueries({ queryKey: ["crm", "clients"] });
      // Add to cache
      queryClient.setQueryData(["crm", "clients", newClient.id], newClient);
      debug("Client created:", newClient.id);
    },
    onError: (err) => {
      logError("Failed to create client:", err);
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
    mutationFn: async ({
      updates,
      updatedBy,
    }: {
      updates: Partial<CreateClientParams>;
      updatedBy: string;
    }) => {
      return api.crm.updateClient(clientId, updates, updatedBy);
    },
    onSuccess: (updatedClient) => {
      // Update cache
      queryClient.setQueryData(["crm", "clients", clientId], updatedClient);
      // Invalidate list
      queryClient.invalidateQueries({ queryKey: ["crm", "clients"] });
      debug("Client updated:", clientId);
    },
    onError: (err) => {
      logError("Failed to update client:", err);
    },
  });

  return mutation;
}

/**
 * Hook per statistiche CRM
 */
export function useCrmStats() {
  return useQuery({
    queryKey: ["crm", "stats"],
    queryFn: async () => {
      const [practiceStats, interactionStats] = await Promise.all([
        api.crm.getPracticeStats(),
        api.crm.getInteractionStats(),
      ]);

      return {
        totalClients: practiceStats.total_practices,
        activePractices: practiceStats.active_practices,
        revenue: {
          total: practiceStats.revenue.total_revenue,
          paid: practiceStats.revenue.paid_revenue,
          outstanding: practiceStats.revenue.outstanding_revenue,
        },
        byStatus: practiceStats.by_status,
        interactions: interactionStats,
      };
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}
