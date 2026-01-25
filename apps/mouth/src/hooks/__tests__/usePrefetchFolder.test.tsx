/**
 * Unit tests for usePrefetchFolder hook
 *
 * Tests cover:
 * - Prefetch trigger
 * - Cache check before prefetch
 * - Query client interaction
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

// Mock the api module
vi.mock('@/lib/api', () => ({
  api: {
    drive: {
      listFiles: vi.fn().mockResolvedValue({
        files: [{ id: '1', name: 'Test File' }],
        breadcrumb: [],
      }),
    },
  },
}));

// Import after mocking
import { usePrefetchFolder } from '../useDrive';
import { api } from '@/lib/api';

describe('usePrefetchFolder', () => {
  let queryClient: QueryClient;

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );

  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });
  });

  it('should return prefetchFolder function', () => {
    const { result } = renderHook(() => usePrefetchFolder(), { wrapper });

    expect(result.current.prefetchFolder).toBeDefined();
    expect(typeof result.current.prefetchFolder).toBe('function');
  });

  it('should call prefetchQuery when folder is not cached', async () => {
    const prefetchSpy = vi.spyOn(queryClient, 'prefetchInfiniteQuery');

    const { result } = renderHook(() => usePrefetchFolder(), { wrapper });

    await act(async () => {
      result.current.prefetchFolder('folder-123');
    });

    expect(prefetchSpy).toHaveBeenCalled();
    expect(prefetchSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: ['drive', 'files', 'folder-123', ''],
      })
    );
  });

  it('should not call prefetchQuery when folder is already cached', async () => {
    // Pre-populate cache
    queryClient.setQueryData(['drive', 'files', 'folder-456', ''], {
      files: [],
      breadcrumb: [],
    });

    const prefetchSpy = vi.spyOn(queryClient, 'prefetchInfiniteQuery');

    const { result } = renderHook(() => usePrefetchFolder(), { wrapper });

    await act(async () => {
      result.current.prefetchFolder('folder-456');
    });

    expect(prefetchSpy).not.toHaveBeenCalled();
  });

  it('should check cache before prefetching', async () => {
    const getQueryDataSpy = vi.spyOn(queryClient, 'getQueryData');

    const { result } = renderHook(() => usePrefetchFolder(), { wrapper });

    await act(async () => {
      result.current.prefetchFolder('folder-789');
    });

    expect(getQueryDataSpy).toHaveBeenCalledWith(['drive', 'files', 'folder-789', '']);
  });

  it('should call api.drive.listFiles with correct folder_id', async () => {
    const { result } = renderHook(() => usePrefetchFolder(), { wrapper });

    await act(async () => {
      result.current.prefetchFolder('folder-abc');
    });

    // Wait for prefetch to complete
    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(api.drive.listFiles).toHaveBeenCalledWith(expect.objectContaining({ folder_id: 'folder-abc' }));
  });

  it('should be stable across re-renders (memoized)', () => {
    const { result, rerender } = renderHook(() => usePrefetchFolder(), { wrapper });

    const firstRender = result.current.prefetchFolder;
    rerender();
    const secondRender = result.current.prefetchFolder;

    expect(firstRender).toBe(secondRender);
  });

  it('should handle multiple prefetch calls for different folders', async () => {
    const prefetchSpy = vi.spyOn(queryClient, 'prefetchInfiniteQuery');

    const { result } = renderHook(() => usePrefetchFolder(), { wrapper });

    await act(async () => {
      result.current.prefetchFolder('folder-1');
      result.current.prefetchFolder('folder-2');
      result.current.prefetchFolder('folder-3');
    });

    expect(prefetchSpy).toHaveBeenCalledTimes(3);
  });
});
