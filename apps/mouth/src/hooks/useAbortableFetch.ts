import { useRef, useEffect, useCallback } from "react";

export function useAbortableFetch() {
  const abortControllerRef = useRef<AbortController | null>(null);

  const createFetch = useCallback(
    <T>(fetchFn: (signal: AbortSignal) => Promise<T>): Promise<T> => {
      // Cancel previous request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      // Create new controller
      abortControllerRef.current = new AbortController();

      return fetchFn(abortControllerRef.current.signal);
    },
    [],
  );

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  return { createFetch };
}
