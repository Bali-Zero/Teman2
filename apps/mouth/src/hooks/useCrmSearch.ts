/**
 * useCrmSearch Hook
 *
 * Ricerca clienti con debounce e suggerimenti
 */

import { useState, useCallback, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useDebounce } from "@/lib/hooks/optimized/useDebounce";
import type { Client, SearchResult } from "@/lib/api/crm/crm.types";

interface UseCrmSearchOptions {
  debounceMs?: number;
  minChars?: number;
  limit?: number;
  enabled?: boolean;
}

interface SearchFilters {
  status?: string[];
  client_type?: string[];
  assigned_to?: string[];
  nationality?: string[];
}

interface SearchResponse {
  clients: Client[];
  total: number;
  suggestions: string[];
}

/**
 * Hook per ricerca clienti con debounce
 */
export function useCrmSearch(options: UseCrmSearchOptions = {}) {
  const {
    debounceMs = 300,
    minChars = 2,
    limit = 20,
    enabled = true,
  } = options;

  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState<SearchFilters>({});
  const debouncedQuery = useDebounce(query, debounceMs);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["crm", "search", debouncedQuery, filters, limit],
    queryFn: async (): Promise<SearchResponse> => {
      if (debouncedQuery.length < minChars && !Object.keys(filters).length) {
        return { clients: [], total: 0, suggestions: [] };
      }

      // Use getClients with search parameter
      const clients = await api.crm.getClients({
        search: debouncedQuery,
        limit,
      });

      // Generate suggestions from client names
      const suggestions = clients
        .map((c: Client) => c.full_name)
        .filter((name: string) =>
          name.toLowerCase().includes(debouncedQuery.toLowerCase()),
        )
        .slice(0, 5);

      return {
        clients,
        total: clients.length,
        suggestions,
      };
    },
    enabled:
      enabled &&
      (debouncedQuery.length >= minChars || Object.keys(filters).length > 0),
    staleTime: 30 * 1000, // 30 seconds
  });

  const updateQuery = useCallback((newQuery: string) => {
    setQuery(newQuery);
  }, []);

  const updateFilters = useCallback((newFilters: Partial<SearchFilters>) => {
    setFilters((prev) => ({ ...prev, ...newFilters }));
  }, []);

  const clearFilters = useCallback(() => {
    setFilters({});
  }, []);

  const clearSearch = useCallback(() => {
    setQuery("");
    setFilters({});
  }, []);

  return {
    query,
    debouncedQuery,
    filters,
    results: data?.clients || [],
    total: data?.total || 0,
    suggestions: data?.suggestions || [],
    isLoading,
    isError,
    error,
    updateQuery,
    updateFilters,
    clearFilters,
    clearSearch,
  };
}

/**
 * Hook per ricerca veloce (command palette style)
 */
export function useQuickSearch(options: { limit?: number } = {}) {
  const { limit = 10 } = options;
  const [isOpen, setIsOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);

  const { query, updateQuery, results, isLoading, clearSearch } = useCrmSearch({
    debounceMs: 150,
    limit,
  });

  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => {
    setIsOpen(false);
    clearSearch();
    setSelectedIndex(0);
  }, [clearSearch]);

  const toggle = useCallback(() => {
    setIsOpen((prev) => !prev);
    if (isOpen) {
      clearSearch();
      setSelectedIndex(0);
    }
  }, [isOpen, clearSearch]);

  const selectNext = useCallback(() => {
    setSelectedIndex((prev) => (prev < results.length - 1 ? prev + 1 : prev));
  }, [results.length]);

  const selectPrev = useCallback(() => {
    setSelectedIndex((prev) => (prev > 0 ? prev - 1 : 0));
  }, []);

  const selectCurrent = useCallback(() => {
    return results[selectedIndex] || null;
  }, [results, selectedIndex]);

  // Reset selection when results change
  useEffect(() => {
    setSelectedIndex(0);
  }, [results.length]);

  return {
    isOpen,
    setIsOpen,
    open,
    close,
    toggle,
    query,
    setQuery: updateQuery,
    results,
    isLoading,
    selectedIndex,
    selectNext,
    selectPrev,
    selectedClient: results[selectedIndex] || null,
  };
}

/**
 * Hook per ricerca globale (clienti + pratiche + documenti)
 */
export function useGlobalSearch(options: { limit?: number } = {}) {
  const { limit = 20 } = options;
  const [query, setQuery] = useState("");
  const debouncedQuery = useDebounce(query, 300);

  const { data, isLoading } = useQuery({
    queryKey: ["crm", "global-search", debouncedQuery],
    queryFn: async (): Promise<SearchResult[]> => {
      if (debouncedQuery.length < 2) return [];

      // Search clients
      const clients = await api.crm.getClients({
        search: debouncedQuery,
        limit,
      });

      // Map to SearchResult format
      return clients.map(
        (client: Client): SearchResult => ({
          id: client.id,
          type: "client",
          title: client.full_name,
          subtitle: client.email || client.phone || undefined,
          status: client.status,
          url: `/clients/${client.id}`,
          metadata: {
            nationality: client.nationality,
            assignedTo: client.assigned_to,
          },
        }),
      );
    },
    enabled: debouncedQuery.length >= 2,
    staleTime: 30 * 1000,
  });

  return {
    query,
    setQuery,
    results: data || [],
    isLoading,
    hasResults: (data?.length || 0) > 0,
  };
}
