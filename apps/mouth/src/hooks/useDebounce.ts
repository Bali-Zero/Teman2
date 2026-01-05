import { useState, useEffect } from 'react';

/**
 * Custom hook for debouncing values
 * 
 * @param value - The value to debounce
 * @param delay - Delay in milliseconds (default: 300ms)
 * @returns Debounced value
 * 
 * @example
 * const [input, setInput] = useState('');
 * const debouncedInput = useDebounce(input, 500);
 * 
 * useEffect(() => {
 *   // This will only run 500ms after user stops typing
 *   performSearch(debouncedInput);
 * }, [debouncedInput]);
 */
export function useDebounce<T>(value: T, delay: number = 300): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    // Set up the timeout
    const handler = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    // Cleanup function: if value changes before delay, cancel the timeout
    return () => {
      clearTimeout(handler);
    };
  }, [value, delay]);

  return debouncedValue;
}

