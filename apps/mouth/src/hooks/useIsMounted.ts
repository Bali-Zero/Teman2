import { useRef, useEffect, useCallback } from 'react';

/**
 * Hook to track component mount status.
 * Prevents state updates on unmounted components during async operations.
 *
 * @example
 * const { isMounted, safeSetState } = useIsMounted();
 *
 * useEffect(() => {
 *   fetchData().then(data => {
 *     if (isMounted()) setState(data);
 *   });
 * }, [isMounted]);
 */
export function useIsMounted() {
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  /**
   * Check if component is currently mounted
   */
  const isMounted = useCallback(() => isMountedRef.current, []);

  /**
   * Safely execute a callback only if component is mounted
   */
  const safeCallback = useCallback(<T extends (...args: unknown[]) => unknown>(fn: T) => {
    return ((...args: Parameters<T>) => {
      if (isMountedRef.current) {
        return fn(...args);
      }
    }) as T;
  }, []);

  return {
    isMounted,
    isMountedRef,
    safeCallback,
  };
}

export default useIsMounted;
