/**
 * useCrmPractices Hook
 *
 * Hook ottimizzato per gestione pratiche CRM
 */

import { useCallback, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";
import type { Practice, CreatePracticeParams } from "@/lib/api/crm/crm.types";

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
  { value: "inquiry", label: "Inquiry", color: "blue" },
  { value: "quotation_sent", label: "Quotation Sent", color: "yellow" },
  { value: "payment_pending", label: "Payment Pending", color: "orange" },
  { value: "in_progress", label: "In Progress", color: "indigo" },
  { value: "completed", label: "Completed", color: "green" },
  { value: "cancelled", label: "Cancelled", color: "red" },
  { value: "on_hold", label: "On Hold", color: "gray" },
] as const;

const PRACTICE_PRIORITIES = [
  { value: "low", label: "Low", color: "gray" },
  { value: "normal", label: "Normal", color: "blue" },
  { value: "high", label: "High", color: "orange" },
  { value: "urgent", label: "Urgent", color: "red" },
] as const;

// Debug helper
const debug = (message: string, value?: unknown) => {
  if (process.env.NODE_ENV === "development") {
    logger.debug(
      `[CRM] ${message}`,
      value !== undefined ? { note: String(value) } : {},
    );
  }
};

const logError = (message: string, err?: unknown) => {
  logger.error(`[CRM] ${message}`, {}, err as Error);
};

/**
 * Hook per lista pratiche
 */
export function useCrmPractices(options: UseCrmPracticesOptions = {}) {
  const { clientId, status, assigned_to, limit = 50, enabled = true } = options;
  const [offset, setOffset] = useState(0);

  const queryKey = [
    "crm",
    "practices",
    { clientId, status, assigned_to, offset },
  ];

  const {
    data,
    isLoading,
    isError,
    error: queryError,
    refetch,
  } = useQuery({
    queryKey,
    queryFn: async (): Promise<PracticesResponse> => {
      let practices: Practice[];

      if (clientId) {
        practices = await api.crm.getClientPractices(clientId);
      } else {
        practices = await api.crm.getPractices({
          status: status || undefined,
          assigned_to: assigned_to || undefined,
          limit,
          offset,
        });
      }

      return {
        practices,
        total: practices.length,
        hasMore: !clientId && practices.length === limit,
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
    queryKey: ["crm", "practices", practiceId],
    queryFn: async (): Promise<Practice> => {
      if (!practiceId) throw new Error("Practice ID required");
      return api.crm.getPractice(practiceId);
    },
    enabled: !!practiceId,
    staleTime: 2 * 60 * 1000,
  });

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({
      queryKey: ["crm", "practices", practiceId],
    });
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
    mutationFn: async ({
      data,
    }: {
      data: CreatePracticeParams;
      createdBy?: string;
    }) => {
      return api.crm.createPractice(data);
    },
    onSuccess: (newPractice, variables) => {
      // Invalidate practices list
      queryClient.invalidateQueries({ queryKey: ["crm", "practices"] });
      // Invalidate client practices if client_id provided
      if (variables.data.client_id) {
        queryClient.invalidateQueries({
          queryKey: [
            "crm",
            "practices",
            { clientId: variables.data.client_id },
          ],
        });
      }
      debug("Practice created:", newPractice.id);
    },
    onError: (err) => {
      logError("Failed to create practice:", err);
    },
  });

  return mutation;
}

/**
 * Hook per aggiornamento pratica
 */
export function useUpdatePractice(practiceId: number) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: async ({
      updates,
    }: {
      updates: Parameters<typeof api.crm.updatePractice>[1];
      updatedBy?: string;
    }) => {
      return api.crm.updatePractice(practiceId, updates);
    },
    onSuccess: (updatedPractice) => {
      // Update cache
      queryClient.setQueryData(
        ["crm", "practices", practiceId],
        updatedPractice,
      );
      // Invalidate lists
      queryClient.invalidateQueries({ queryKey: ["crm", "practices"] });
      debug("Practice updated:", practiceId);
    },
    onError: (err) => {
      logError("Failed to update practice:", err);
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
    mutationFn: async ({ status }: { status: string; updatedBy?: string }) => {
      return api.crm.updatePractice(practiceId, { status });
    },
    onSuccess: (updatedPractice) => {
      // Update cache
      queryClient.setQueryData(
        ["crm", "practices", practiceId],
        updatedPractice,
      );
      // Invalidate lists
      queryClient.invalidateQueries({ queryKey: ["crm", "practices"] });
      debug("Practice status updated:", practiceId);
    },
    onError: (err) => {
      logError("Failed to update practice status:", err);
    },
  });

  return mutation;
}

/**
 * Hook per pratiche in scadenza
 */
export function useUpcomingRenewals(days: number = 90) {
  return useQuery({
    queryKey: ["crm", "practices", "renewals", days],
    queryFn: async () => {
      return api.crm.getUpcomingRenewals(days);
    },
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Hook per cancellazione pratica
 */
export function useDeletePractice(practiceId: number) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: async (deletedBy: string) => {
      return api.crm.deletePractice(practiceId, deletedBy);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["crm", "practices"] });
      debug("Practice deleted:", practiceId);
    },
    onError: (err) => {
      logError("Failed to delete practice:", err);
    },
  });

  return mutation;
}

export { PRACTICE_STATUSES, PRACTICE_PRIORITIES };
