'use client';

import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

// Create a client for React Query with enterprise configuration
function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Enterprise-grade caching strategy
        staleTime: 30 * 1000, // 30 seconds
        gcTime: 5 * 60 * 1000, // 5 minutes (formerly cacheTime)
        retry: (failureCount, error: any) => {
          // Retry on network errors but not on 4xx errors
          if (error?.status >= 400 && error?.status < 500) return false;
          return failureCount < 3;
        },
        retryDelay: attemptIndex => Math.min(1000 * 2 ** attemptIndex, 30000),
        refetchOnWindowFocus: false, // Don't refetch on window focus for enterprise
        refetchOnReconnect: true, // Do refetch on reconnect
        refetchOnMount: false, // Don't refetch on mount for better UX
      },
      mutations: {
        retry: 1,
        retryDelay: 1000,
      },
    },
  });
}

let browserQueryClient: QueryClient | undefined = undefined;

function getQueryClient() {
  if (typeof window === 'undefined') {
    // Server: always make a new query client
    return createQueryClient();
  } else {
    // Browser: use a singleton pattern to keep the same query client
    if (!browserQueryClient) browserQueryClient = createQueryClient();
    return browserQueryClient;
  }
}

export function QueryProvider({ children }: { children: React.ReactNode }) {
  // NOTE: Avoid useState when initializing the query client if you don't
  // have a suspense boundary between this and the code that may
  // suspend because React will throw away the client on every render.
  const queryClient = getQueryClient();

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {/* Enhanced DevTools with enterprise features */}
      <ReactQueryDevtools 
        initialIsOpen={false}
        buttonPosition="bottom-left"
        position="bottom"
      />
    </QueryClientProvider>
  );
}
