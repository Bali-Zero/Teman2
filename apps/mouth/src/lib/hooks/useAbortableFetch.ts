/**
 * useAbortableFetch - Hook for cancellable fetch operations
 *
 * Prevents race conditions and memory leaks when:
 * - Component unmounts during fetch
 * - User navigates away quickly
 * - Multiple rapid requests (search, pagination)
 *
 * Usage:
 * ```typescript
 * const { fetchData, abort, isLoading } = useAbortableFetch<Client[]>();
 *
 * useEffect(() => {
 *   fetchData(() => api.crm.getClients());
 *   return () => abort(); // Cleanup on unmount
 * }, []);
 * ```
 */

import { useCallback, useEffect, useRef, useState } from "react";

interface UseAbortableFetchOptions {
  onError?: (error: Error) => void;
  onSuccess?: <T>(data: T) => void;
}

export function useAbortableFetch<T>(options: UseAbortableFetchOptions = {}) {
  const abortControllerRef = useRef<AbortController | null>(null);
  const isMountedRef = useRef(true);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [data, setData] = useState<T | null>(null);

  // Track mount state
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      abort();
    };
  }, []);

  /**
   * Abort any in-flight request
   */
  const abort = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  /**
   * Execute a fetch operation with automatic cleanup
   * @param fetchFn - Function that returns a Promise
   * @returns Promise that resolves to the data or null if aborted
   */
  const fetchData = useCallback(
    async (fetchFn: (signal: AbortSignal) => Promise<T>): Promise<T | null> => {
      // Abort any previous request
      abort();

      // Create new abort controller
      abortControllerRef.current = new AbortController();
      const { signal } = abortControllerRef.current;

      setIsLoading(true);
      setError(null);

      try {
        const result = await fetchFn(signal);

        // Only update state if component still mounted and not aborted
        if (isMountedRef.current && !signal.aborted) {
          setData(result);
          options.onSuccess?.(result);
          return result;
        }
        return null;
      } catch (err) {
        // Don't treat abort as error
        if (err instanceof Error && err.name === "AbortError") {
          return null;
        }

        // Only update error state if component still mounted
        if (isMountedRef.current && !signal.aborted) {
          const error = err instanceof Error ? err : new Error(String(err));
          setError(error);
          options.onError?.(error);
        }
        return null;
      } finally {
        // Only update loading state if component still mounted
        if (isMountedRef.current && !signal.aborted) {
          setIsLoading(false);
        }
      }
    },
    [abort, options],
  );

  /**
   * Reset all state
   */
  const reset = useCallback(() => {
    abort();
    setData(null);
    setError(null);
    setIsLoading(false);
  }, [abort]);

  return {
    fetchData,
    abort,
    reset,
    isLoading,
    error,
    data,
  };
}

/**
 * useCancellableEffect - Hook for effects that need cleanup on dependency change
 *
 * Usage:
 * ```typescript
 * useCancellableEffect((isCancelled) => {
 *   const loadData = async () => {
 *     const data = await api.getData();
 *     if (!isCancelled()) {
 *       setData(data);
 *     }
 *   };
 *   loadData();
 * }, [dependency]);
 * ```
 */
export function useCancellableEffect(
  effect: (isCancelled: () => boolean) => void | (() => void),
  deps: React.DependencyList,
): void {
  const cancelledRef = useRef(false);

  useEffect(() => {
    cancelledRef.current = false;
    const cleanup = effect(() => cancelledRef.current);

    return () => {
      cancelledRef.current = true;
      if (cleanup) {
        cleanup();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

/**
 * createAbortableApi - Wraps API calls with abort signal support
 *
 * Usage:
 * ```typescript
 * const apiWithAbort = createAbortableApi(signal);
 * const clients = await apiWithAbort.crm.getClients();
 * ```
 */
export function createAbortableWrapper<T extends Record<string, any>>(
  api: T,
  signal: AbortSignal,
): T {
  const wrapped = {} as T;

  for (const [key, value] of Object.entries(api)) {
    if (typeof value === "function") {
      (wrapped as Record<string, unknown>)[key] = (...args: unknown[]) => {
        if (signal.aborted) {
          return Promise.reject(new Error("Request aborted"));
        }
        return (value as (...args: unknown[]) => unknown)(...args);
      };
    } else if (typeof value === "object" && value !== null) {
      (wrapped as Record<string, unknown>)[key] = createAbortableWrapper(
        value,
        signal,
      );
    } else {
      (wrapped as Record<string, unknown>)[key] = value;
    }
  }

  return wrapped;
}
