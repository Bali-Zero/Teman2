"use client";

import { useMemo, useCallback, useRef, useState, useEffect } from "react";

interface UseOptimizedListOptions<T> {
  items: T[];
  pageSize?: number;
  filterFn?: (item: T, query: string) => boolean;
  sortFn?: (a: T, b: T) => number;
  keyExtractor: (item: T) => string | number;
}

interface UseOptimizedListReturn<T> {
  paginatedItems: T[];
  filteredItems: T[];
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  currentPage: number;
  setCurrentPage: (page: number) => void;
  totalPages: number;
  hasMore: boolean;
  loadMore: () => void;
  isLoading: boolean;
}

/**
 * Hook for optimized list handling with pagination, filtering, and memoization.
 * Prevents unnecessary re-computations and re-renders.
 *
 * @example
 * ```tsx
 * const { paginatedItems, searchQuery, setSearchQuery } = useOptimizedList({
 *   items: clients,
 *   pageSize: 20,
 *   filterFn: (client, query) =>
 *     client.name.toLowerCase().includes(query.toLowerCase()),
 *   keyExtractor: (client) => client.id,
 * });
 * ```
 */
export function useOptimizedList<T>({
  items,
  pageSize = 50,
  filterFn,
  sortFn,
  keyExtractor,
}: UseOptimizedListOptions<T>): UseOptimizedListReturn<T> {
  const [searchQuery, setSearchQuery] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [isLoading, setIsLoading] = useState(false);

  // Use ref to track if we're in the middle of loading to prevent race conditions
  const loadingRef = useRef(false);

  // Memoized filtered items - only recompute when items or searchQuery change
  const filteredItems = useMemo(() => {
    if (!filterFn || !searchQuery) {
      return sortFn ? [...items].sort(sortFn) : items;
    }

    const filtered = items.filter((item) => filterFn(item, searchQuery));
    return sortFn ? filtered.sort(sortFn) : filtered;
  }, [items, searchQuery, filterFn, sortFn]);

  // Memoized pagination calculations
  const { paginatedItems, totalPages, hasMore } = useMemo(() => {
    const start = 0;
    const end = currentPage * pageSize;
    const paginated = filteredItems.slice(start, end);
    const total = Math.ceil(filteredItems.length / pageSize);
    const more = currentPage < total;

    return {
      paginatedItems: paginated,
      totalPages: total,
      hasMore: more,
    };
  }, [filteredItems, currentPage, pageSize]);

  // Optimized load more function
  const loadMore = useCallback(() => {
    if (loadingRef.current || !hasMore) return;

    loadingRef.current = true;
    setIsLoading(true);

    // Simulate async loading for better UX
    requestAnimationFrame(() => {
      setCurrentPage((prev) => prev + 1);
      setIsLoading(false);
      loadingRef.current = false;
    });
  }, [hasMore]);

  // Reset pagination when search changes
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery]);

  // Memoized setters to prevent unnecessary re-renders
  const memoizedSetSearchQuery = useCallback((query: string) => {
    setSearchQuery(query);
  }, []);

  const memoizedSetCurrentPage = useCallback((page: number) => {
    setCurrentPage(page);
  }, []);

  return {
    paginatedItems,
    filteredItems,
    searchQuery,
    setSearchQuery: memoizedSetSearchQuery,
    currentPage,
    setCurrentPage: memoizedSetCurrentPage,
    totalPages,
    hasMore,
    loadMore,
    isLoading,
  };
}

/**
 * Hook for infinite scroll with intersection observer.
 * More efficient than scroll event listeners.
 */
export function useInfiniteScroll(
  onLoadMore: () => void,
  hasMore: boolean,
  options?: IntersectionObserverInit,
) {
  const observerRef = useRef<IntersectionObserver | null>(null);
  const targetRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!hasMore) {
      if (observerRef.current) {
        observerRef.current.disconnect();
      }
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && hasMore) {
          onLoadMore();
        }
      },
      {
        rootMargin: "100px",
        threshold: 0.1,
        ...options,
      },
    );

    observerRef.current = observer;

    if (targetRef.current) {
      observer.observe(targetRef.current);
    }

    return () => observer.disconnect();
  }, [onLoadMore, hasMore, options]);

  return targetRef;
}
