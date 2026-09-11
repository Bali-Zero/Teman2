"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  Client,
  ClientCompanyLink,
  ClientProfile,
  Interaction,
  DocumentCategory,
  TaxCompanyPilotMap,
} from "@/lib/api/crm/crm.types";

export const clientDetailQueryKey = (clientId: string | number) =>
  ["client", String(clientId)] as const;

export function buildBusinessStorySearchTerms(
  clientName: string,
  companyLinks: ClientCompanyLink[] | undefined,
): string[] {
  const normalizedClientName = clientName.trim();
  const companyNames =
    companyLinks
      ?.map((link) => link.company_name.trim())
      .filter((companyName) => companyName.length > 0) ?? [];
  /* A client with no linked company searches for THEMSELVES and nothing
     else. This used to append ["ocean", "bimala"] — the two curated pilot
     keys of the standalone /clients/tax-pilot demo, which are real client
     companies, not placeholders. So opening any unlinked client's page
     fired
       GET /api/crm/intelligence/evidence-dossiers?company=<this client>
           &company=<real company A>&company=<real company B>
     naming two unrelated clients' companies in a URL, an access log and
     whatever analytics observes them (portal audit finding F-06). Nothing
     was ever displayed from it: BusinessStoryPanel filters the response
     down to maps matching THIS client's own name or companies, which for
     an unlinked client is always empty. The fallback bought no UI and
     leaked two names on every such page view. */
  const rawTerms = [normalizedClientName, ...companyNames].filter(
    (term) => term.length > 0,
  );

  const seen = new Set<string>();
  return rawTerms.filter((term) => {
    const key = term.toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

/**
 * Fetches the full client profile (client, family, documents, practices,
 * expiry_alerts, company_links, stats) with React Query caching.
 */
export function useClientDetail(clientId: string | number) {
  return useQuery<ClientProfile>({
    queryKey: clientDetailQueryKey(clientId),
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

export function useClientBusinessStory(
  clientId: string | number,
  clientName: string,
  companyLinks: ClientCompanyLink[] | undefined,
) {
  const searchTerms = buildBusinessStorySearchTerms(clientName, companyLinks);

  return useQuery<TaxCompanyPilotMap[]>({
    queryKey: ["client", String(clientId), "business-story", searchTerms],
    queryFn: () =>
      api.crm.getEvidenceDossiers({
        companies: searchTerms,
        limit: Math.max(searchTerms.length, 2),
      }),
    staleTime: 2 * 60 * 1000,
    refetchOnWindowFocus: false,
    enabled: !!clientId && Number(clientId) > 0 && searchTerms.length > 0,
  });
}

/**
 * Returns a function that invalidates the client profile query,
 * refetching it even when it is currently inactive.
 */
export function useInvalidateClient(clientId?: string | number | null) {
  const queryClient = useQueryClient();
  return () => {
    if (!clientId || Number(clientId) <= 0) {
      return Promise.resolve();
    }
    return queryClient.invalidateQueries({
      queryKey: clientDetailQueryKey(clientId),
      exact: true,
      refetchType: "all",
    });
  };
}

export function useSetClientCache(clientId: string | number) {
  const queryClient = useQueryClient();
  return (client: Client) =>
    queryClient.setQueryData<ClientProfile>(
      clientDetailQueryKey(clientId),
      (profile) => (profile ? { ...profile, client } : profile),
    );
}
