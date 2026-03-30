"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  ClientProfile,
  Interaction,
  DocumentCategory,
} from "@/lib/api/crm/crm.types";

/**
 * Fetches the full client profile (client, family, documents, practices,
 * expiry_alerts, company_links, stats) with React Query caching.
 */
export function useClientDetail(clientId: string | number) {
  return useQuery<ClientProfile>({
    queryKey: ["client", String(clientId)],
    queryFn: () => api.crm.getClientProfile(Number(clientId)),
    staleTime: 2 * 60 * 1000,
    refetchOnWindowFocus: true,
    enabled: !!clientId && Number(clientId) > 0,
  });
}

/**
 * Fetches the client timeline (interactions) with React Query caching.
 * Kept separate from the profile so it can be invalidated independently.
 */
export function useClientTimeline(clientId: string | number) {
  return useQuery<Interaction[]>({
    queryKey: ["client", String(clientId), "timeline"],
    queryFn: () => api.crm.getClientTimeline(Number(clientId), 50),
    staleTime: 2 * 60 * 1000,
    refetchOnWindowFocus: true,
    enabled: !!clientId && Number(clientId) > 0,
  });
}

/**
 * Fetches document categories (static reference data).
 * Long staleTime since categories rarely change.
 */
export function useDocumentCategories() {
  return useQuery<DocumentCategory[]>({
    queryKey: ["document-categories"],
    queryFn: () => api.crm.getDocumentCategories(),
    staleTime: 10 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}

/**
 * Returns a function that invalidates the client profile query,
 * triggering a background refetch.
 */
export function useInvalidateClient(clientId: string | number) {
  const queryClient = useQueryClient();
  return () =>
    queryClient.invalidateQueries({ queryKey: ["client", String(clientId)] });
}
