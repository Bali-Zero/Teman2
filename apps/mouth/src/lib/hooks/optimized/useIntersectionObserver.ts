/**
 * useIntersectionObserver Hook
 *
 * Efficient intersection observer for lazy loading
 */

import { useEffect, useRef, useState, useCallback } from "react";

interface UseIntersectionObserverOptions {
  threshold?: number | number[];
  root?: Element | null;
  rootMargin?: string;
  triggerOnce?: boolean;
}

/**
 * Track element visibility
 */
export function useIntersectionObserver(
  options: UseIntersectionObserverOptions = {},
): [(node: Element | null) => void, boolean, IntersectionObserverEntry | null] {
  const {
    threshold = 0,
    root = null,
    rootMargin = "0px",
    triggerOnce = false,
  } = options;
  const [isIntersecting, setIsIntersecting] = useState(false);
  const [entry, setEntry] = useState<IntersectionObserverEntry | null>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);
  const hasTriggeredRef = useRef(false);

  const setRef = useCallback(
    (node: Element | null) => {
      if (observerRef.current) {
        observerRef.current.disconnect();
      }

      if (node) {
        observerRef.current = new IntersectionObserver(
          ([entry]) => {
            setEntry(entry);

            if (triggerOnce && hasTriggeredRef.current) {
              return;
            }

            setIsIntersecting(entry.isIntersecting);

            if (entry.isIntersecting && triggerOnce) {
              hasTriggeredRef.current = true;
            }
          },
          { threshold, root, rootMargin },
        );

        observerRef.current.observe(node);
      }
    },
    [threshold, root, rootMargin, triggerOnce],
  );

  useEffect(() => {
    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
    };
  }, []);

  return [setRef, isIntersecting, entry];
}

/**
 * Simple visibility hook
 */
export function useIsVisible(
  options: Omit<UseIntersectionObserverOptions, "triggerOnce"> = {},
): [(node: Element | null) => void, boolean] {
  const [ref, isVisible] = useIntersectionObserver({
    ...options,
    triggerOnce: false,
  });
  return [ref, isVisible];
}

/**
 * Entered viewport once
 */
export function useHasEnteredViewport(
  options: Omit<UseIntersectionObserverOptions, "triggerOnce"> = {},
): [(node: Element | null) => void, boolean] {
  const [ref, hasEntered] = useIntersectionObserver({
    ...options,
    triggerOnce: true,
  });
  return [ref, hasEntered];
}
