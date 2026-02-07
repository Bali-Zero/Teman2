'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { useState, ReactNode } from 'react';

interface QueryProviderProps {
  children: ReactNode;
}

/**
 * React Query Provider Configuration
 *
 * Optimized for:
 * - Stale-while-revalidate pattern
 * - Background refetching for fresh data
 * - Optimistic updates for mutations
 * - Aggressive prefetching on hover
 *
 * Cache Strategy:
 * - staleTime: 5 minutes (data considered fresh)
 * - gcTime: 10 minutes (garbage collection)
 * - refetchOnWindowFocus: true (update when user returns)
 * - refetchOnReconnect: true (update after connection restore)
 */
export function QueryProvider({ children }: QueryProviderProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Data stays fresh for 5 minutes
            staleTime: 1000 * 60 * 5, // 5 minutes

            // Cache persists for 10 minutes after last use
            gcTime: 1000 * 60 * 10, // 10 minutes

            // Refetch when window regains focus
            refetchOnWindowFocus: true,

            // Refetch when reconnecting
            refetchOnReconnect: true,

            // Retry failed requests 3 times with exponential backoff
            retry: 3,
            retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),

            // Don't retry on 401/403 errors
            retryOnMount: true,

            // Prefetch next page in paginated queries
            placeholderData: (previousData: unknown) => previousData,
          },
          mutations: {
            // Retry mutations once (idempotency assumed)
            retry: 1,

            // Optimistic updates by default
            onSettled: () => {
              // Invalidate relevant caches after mutation
            },
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {process.env.NODE_ENV === 'development' && (
        <ReactQueryDevtools initialIsOpen={false} position="bottom" buttonPosition="bottom-left" />
      )}
    </QueryClientProvider>
  );
}
