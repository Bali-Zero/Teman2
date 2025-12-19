import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { useSearchDocs } from './useSearchDocs';
import { api } from '@/lib/api';

vi.mock('@/lib/api', () => ({
  api: {
    isAdmin: vi.fn(() => false),
    isAuthenticated: vi.fn(() => true),
    searchDocs: vi.fn(),
  },
}));

describe('useSearchDocs', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should initialize with default values', () => {
    const { result } = renderHook(() => useSearchDocs());

    expect(result.current.query).toBe('');
    expect(result.current.level).toBe(1);
    expect(result.current.limit).toBe(8);
    expect(result.current.isLoading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(result.current.results).toEqual([]);
  });

  it('should initialize with level 3 for admin users', () => {
    (api.isAdmin as any).mockReturnValue(true);
    const { result } = renderHook(() => useSearchDocs());

    expect(result.current.level).toBe(3);
  });

  it('should update query', () => {
    const { result } = renderHook(() => useSearchDocs());

    result.current.setQuery('test query');
    expect(result.current.query).toBe('test query');
  });

  it('should update level and limit', () => {
    const { result } = renderHook(() => useSearchDocs());

    result.current.setLevel(2);
    result.current.setLimit(10);

    expect(result.current.level).toBe(2);
    expect(result.current.limit).toBe(10);
  });

  it('should run search successfully', async () => {
    const mockResponse = {
      results: [
        {
          text: 'Result 1',
          similarity_score: 0.9,
          metadata: { book_title: 'Book 1' },
        },
      ],
      total_found: 1,
      execution_time_ms: 100,
    };

    (api.searchDocs as any).mockResolvedValueOnce(mockResponse);

    const { result } = renderHook(() => useSearchDocs());

    result.current.setQuery('test');
    await result.current.runSearch();

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.results).toEqual(mockResponse.results);
    expect(result.current.totalFound).toBe(1);
    expect(result.current.executionTimeMs).toBe(100);
    expect(result.current.error).toBeNull();
  });

  it('should handle search error', async () => {
    (api.searchDocs as any).mockRejectedValueOnce(new Error('Search failed'));

    const { result } = renderHook(() => useSearchDocs());

    result.current.setQuery('test');
    await result.current.runSearch();

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBe('Search failed');
    expect(result.current.results).toEqual([]);
  });

  it('should handle authentication error', async () => {
    (api.isAuthenticated as any).mockReturnValue(false);

    const { result } = renderHook(() => useSearchDocs());

    result.current.setQuery('test');
    await result.current.runSearch();

    expect(result.current.error).toBe('Authentication required');
    expect(result.current.statusMessage).toContain('Authentication required');
  });

  it('should set status message when no results found', async () => {
    const mockResponse = {
      results: [],
      total_found: 0,
      execution_time_ms: 50,
    };

    (api.searchDocs as any).mockResolvedValueOnce(mockResponse);
    (api.isAuthenticated as any).mockReturnValue(true);

    const { result } = renderHook(() => useSearchDocs());

    result.current.setQuery('test');
    result.current.runSearch();

    await waitFor(
      () => {
        expect(result.current.isLoading).toBe(false);
      },
      { timeout: 3000 }
    );

    expect(result.current.statusMessage).toBe('No results found for this query.');
  });

  it('should not run search if query is empty', async () => {
    const { result } = renderHook(() => useSearchDocs());

    await result.current.runSearch();

    expect(api.searchDocs).not.toHaveBeenCalled();
  });
});

