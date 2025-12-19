import { useState, useCallback } from 'react';
import { api, KnowledgeSearchResult } from '@/lib/api';

export function useSearchDocs() {
  const [query, setQuery] = useState('');
  const [level, setLevel] = useState<number>(() => (api.isAdmin() ? 3 : 1));
  const [limit, setLimit] = useState<number>(8);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<KnowledgeSearchResult[]>([]);
  const [totalFound, setTotalFound] = useState<number>(0);
  const [executionTimeMs, setExecutionTimeMs] = useState<number | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const runSearch = useCallback(async () => {
    const q = query.trim();
    if (!q) return;

    if (!api.isAuthenticated()) {
      setError('Authentication required');
      setStatusMessage('Authentication required. Please login to search the archive.');
      return;
    }

    setIsLoading(true);
    setError(null);
    setStatusMessage(null);
    try {
      const resp = await api.searchDocs({ query: q, level, limit });
      setResults(resp.results || []);
      setTotalFound(resp.total_found || 0);
      setExecutionTimeMs(typeof resp.execution_time_ms === 'number' ? resp.execution_time_ms : null);
      if (!resp.results?.length) {
        setStatusMessage('No results found for this query.');
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Search failed';
      setError(message);
      setResults([]);
      setTotalFound(0);
      setExecutionTimeMs(null);
      if (/401|Authentication required/i.test(message)) {
        setStatusMessage('Authentication required. Please login to search the archive.');
      }
    } finally {
      setIsLoading(false);
    }
  }, [query, level, limit]);

  return {
    query,
    setQuery,
    level,
    setLevel,
    limit,
    setLimit,
    isLoading,
    error,
    results,
    totalFound,
    executionTimeMs,
    statusMessage,
    runSearch,
  };
}

