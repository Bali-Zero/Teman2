/**
 * API Response Caching Layer
 *
 * Implements in-memory caching for API responses with:
 * - TTL (Time To Live) support
 * - Cache invalidation
 * - Stale-while-revalidate pattern
 */

import { error } from "@/lib/utils/console";

interface CacheEntry<T> {
  data: T;
  timestamp: number;
  ttl: number;
}

class APICache {
  private cache: Map<string, CacheEntry<unknown>> = new Map();

  /**
   * Get cached data if valid
   */
  get<T>(key: string): T | null {
    const entry = this.cache.get(key);
    if (!entry) return null;

    const isExpired = Date.now() - entry.timestamp > entry.ttl;
    if (isExpired) {
      this.cache.delete(key);
      return null;
    }

    return entry.data as T;
  }

  /**
   * Store data in cache
   */
  set<T>(key: string, data: T, ttlMs: number = 5 * 60 * 1000): void {
    this.cache.set(key, {
      data,
      timestamp: Date.now(),
      ttl: ttlMs,
    });
  }

  /**
   * Remove specific entry
   */
  invalidate(key: string): void {
    this.cache.delete(key);
  }

  /**
   * Clear all cache
   */
  clear(): void {
    this.cache.clear();
  }

  /**
   * Get cache stats
   */
  getStats(): { size: number; keys: string[] } {
    return {
      size: this.cache.size,
      keys: Array.from(this.cache.keys()),
    };
  }
}

// Global cache instance
export const apiCache = new APICache();

interface FetchWithCacheOptions<T> {
  key: string;
  fetcher: () => Promise<T>;
  ttl?: number;
  staleWhileRevalidate?: boolean;
}

/**
 * Fetch with caching support
 *
 * Usage:
 * const data = await fetchWithCache({
 *   key: 'users-list',
 *   fetcher: () => fetch('/api/users').then(r => r.json()),
 *   ttl: 60000, // 1 minute
 * });
 */
export async function fetchWithCache<T>({
  key,
  fetcher,
  ttl = 5 * 60 * 1000,
  staleWhileRevalidate = false,
}: FetchWithCacheOptions<T>): Promise<T> {
  const cached = apiCache.get<T>(key);

  if (cached) {
    // Return cached data immediately
    if (staleWhileRevalidate) {
      // Refresh in background
      fetcher()
        .then((data) => apiCache.set(key, data, ttl))
        .catch((err) => error(err));
    }
    return cached;
  }

  // Fetch fresh data
  const data = await fetcher();
  apiCache.set(key, data, ttl);
  return data;
}

/**
 * React hook for cached data fetching
 *
 * Usage:
 * const { data, error, isLoading, refetch } = useCachedQuery({
 *   key: 'user-profile',
 *   fetcher: () => fetchUserProfile(),
 *   ttl: 60000,
 * });
 */
export function useCachedQuery<T>({
  key,
  fetcher,
  ttl = 5 * 60 * 1000,
}: {
  key: string;
  fetcher: () => Promise<T>;
  ttl?: number;
}) {
  const [data, setData] = React.useState<T | null>(apiCache.get<T>(key));
  const [error, setError] = React.useState<Error | null>(null);
  const [isLoading, setIsLoading] = React.useState(!data);

  const refetch = React.useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await fetchWithCache({ key, fetcher, ttl });
      setData(result);
      setError(null);
      return result;
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [key, fetcher, ttl]);

  React.useEffect(() => {
    if (!data) {
      refetch();
    }
  }, [data, refetch]);

  return { data, error, isLoading, refetch };
}

// Import React for hook
import React from "react";
