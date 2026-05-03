/**
 * useThrottle Hook
 *
 * Throttle a callback
 */

import { useCallback, useRef, useEffect } from "react";

/**
 * Throttle a callback
 */
export function useThrottledCallback<T extends (...args: unknown[]) => unknown>(
  callback: T,
  limit: number,
): (...args: Parameters<T>) => void {
  const inThrottleRef = useRef(false);
  const lastArgsRef = useRef<Parameters<T> | null>(null);

  useEffect(() => {
    return () => {
      inThrottleRef.current = false;
    };
  }, []);

  return useCallback(
    (...args: Parameters<T>) => {
      if (!inThrottleRef.current) {
        callback(...args);
        inThrottleRef.current = true;

        setTimeout(() => {
          inThrottleRef.current = false;
          if (lastArgsRef.current) {
            callback(...lastArgsRef.current);
            lastArgsRef.current = null;
          }
        }, limit);
      } else {
        lastArgsRef.current = args;
      }
    },
    [callback, limit],
  );
}

/**
 * Throttle a value (updates at most once per limit)
 */
export function useThrottle<T>(value: T, limit: number): T {
  const [throttledValue, setThrottledValue] = useState<T>(value);
  const lastUpdateRef = useRef<number>(0);

  useEffect(() => {
    const now = Date.now();
    const timeSinceLastUpdate = now - lastUpdateRef.current;

    if (timeSinceLastUpdate >= limit) {
      setThrottledValue(value);
      lastUpdateRef.current = now;
    } else {
      const timeoutId = setTimeout(() => {
        setThrottledValue(value);
        lastUpdateRef.current = Date.now();
      }, limit - timeSinceLastUpdate);

      return () => clearTimeout(timeoutId);
    }
  }, [value, limit]);

  return throttledValue;
}

// Add missing import
import { useState } from "react";
