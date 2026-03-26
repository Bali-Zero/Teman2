/**
 * useCrmClients Hook
 *
 * Hook ottimizzato per gestione clienti CRM con caching e sincronizzazione
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Client, CreateClientParams } from "@/lib/api/crm/crm.types";
import { logger } from "@/lib/logger";

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

const logError = (...args: unknown[]) => {
  logger.error(
    "[CRM]",
    {},
    args[0] instanceof Error ? args[0] : new Error(String(args[0])),
  );
};

const debug = (...args: unknown[]) => {
  logger.debug("[CRM] " + args.join(" "), {});
};

/**
 * Hook per gestione lista clienti
 */
export function useCrmClients(options: UseCrmClientsOptions = {}) {
  const { status, assigned_to, search, limit = 50, enabled = true } = options;
  const queryClient = useQueryClient();
  const [allClients, setAllClients] = useState<Client[]>([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const loadingRef = useRef(false);

  // Base query key (without offset — we accumulate results)
  const queryKey = ["crm", "clients", { status, assigned_to, search }];

  const {
    data,
    isLoading,
    isError,
    error: queryError,
    refetch,
  } = useQuery({
    queryKey: [...queryKey, offset],
    queryFn: async (): Promise<Client[]> => {
      return api.crm.getClients({
        search: search || undefined,
        status: status || undefined,
        assigned_to: assigned_to || undefined,
        limit,
        offset,
      });
    },
    enabled,
    staleTime: 5 * 60 * 1000,
    gcTime: 10 * 60 * 1000,
  });

  // Accumulate results when new data arrives
  useEffect(() => {
    if (data) {
      if (offset === 0) {
        setAllClients(data);
      } else {
        setAllClients((prev) => {
          const existingIds = new Set(prev.map((c) => c.id));
          const newClients = data.filter((c) => !existingIds.has(c.id));
          return [...prev, ...newClients];
        });
      }
      setHasMore(data.length === limit);
      setIsLoadingMore(false);
      loadingRef.current = false;
    }
  }, [data, offset, limit]);

  // Reset loadingRef on error so loadMore can be retried
  useEffect(() => {
    if (isError) {
      loadingRef.current = false;
      setIsLoadingMore(false);
    }
  }, [isError]);

  // Reset when filters change
  useEffect(() => {
    setOffset(0);
    setAllClients([]);
    setHasMore(true);
  }, [status, assigned_to, search]);

  const loadMore = useCallback(() => {
    if (hasMore && !isLoading && !loadingRef.current) {
      loadingRef.current = true;
      setIsLoadingMore(true);
      setOffset((prev) => prev + limit);
    }
  }, [hasMore, isLoading, limit]);

  const reset = useCallback(() => {
    setOffset(0);
    setAllClients([]);
    setHasMore(true);
    refetch();
  }, [refetch]);

  return {
    clients: allClients,
    total: allClients.length,
    isLoading: isLoading && offset === 0,
    isError,
    error: queryError,
    loadMore,
    hasMore,
    isLoadingMore,
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
    queryKey: ["crm", "client", clientId],
    queryFn: async (): Promise<Client> => {
      if (!clientId) throw new Error("Client ID required");
      return api.crm.getClient(clientId);
    },
    enabled: !!clientId,
    staleTime: 2 * 60 * 1000, // 2 minutes
  });

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["crm", "client", clientId] });
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
      // Add to cache under both keys (plural list key + singular detail key)
      queryClient.setQueryData(["crm", "clients", newClient.id], newClient);
      queryClient.setQueryData(["crm", "client", newClient.id], newClient);
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
      // Update cache under both keys (plural list key + singular detail key)
      queryClient.setQueryData(["crm", "clients", clientId], updatedClient);
      queryClient.setQueryData(["crm", "client", clientId], updatedClient);
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
