/**
 * usePrevious Hook
 *
 * Track previous value
 */

import { useRef, useEffect } from "react";

/**
 * Get the previous value of a state or prop
 */
export function usePrevious<T>(value: T): T | undefined {
  const ref = useRef<T | undefined>(undefined);
  const prevRef = useRef<T | undefined>(undefined);

  useEffect(() => {
    prevRef.current = ref.current;
    ref.current = value;
  }, [value]);

  return prevRef.current;
}

/**
 * Get previous value with custom comparison
 */
export function usePreviousWithCompare<T>(
  value: T,
  compare: (a: T, b: T) => boolean,
): T | undefined {
  const ref = useRef<T | undefined>(undefined);
  const prevRef = useRef<T | undefined>(undefined);

  useEffect(() => {
    if (ref.current === undefined || !compare(ref.current, value)) {
      prevRef.current = ref.current;
      ref.current = value;
    }
  }, [value, compare]);

  return prevRef.current;
}

/**
 * Track value history (last N values)
 */
export function useHistory<T>(value: T, maxSize = 5): T[] {
  const historyRef = useRef<T[]>([]);

  useEffect(() => {
    historyRef.current = [value, ...historyRef.current].slice(0, maxSize);
  }, [value, maxSize]);

  return historyRef.current;
}
