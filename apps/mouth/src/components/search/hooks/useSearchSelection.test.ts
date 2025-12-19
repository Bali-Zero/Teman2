import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useSearchSelection } from './useSearchSelection';
import type { KnowledgeSearchResult } from '@/lib/api';

const mockResults: KnowledgeSearchResult[] = [
  {
    text: 'Result 1',
    similarity_score: 0.9,
    metadata: { book_title: 'Book 1' },
  },
  {
    text: 'Result 2',
    similarity_score: 0.8,
    metadata: { book_title: 'Book 2' },
  },
  {
    text: 'Result 3',
    similarity_score: 0.7,
    metadata: { book_title: 'Book 3' },
  },
];

describe('useSearchSelection', () => {
  it('should initialize with empty selection', () => {
    const { result } = renderHook(() => useSearchSelection(mockResults));

    expect(result.current.expandedIds.size).toBe(0);
    expect(result.current.selectedIds.size).toBe(0);
    expect(result.current.selectedResults).toEqual([]);
  });

  it('should toggle expanded state', () => {
    const { result } = renderHook(() => useSearchSelection(mockResults));

    act(() => {
      result.current.toggleExpanded(0);
    });

    expect(result.current.expandedIds.has(0)).toBe(true);

    act(() => {
      result.current.toggleExpanded(0);
    });

    expect(result.current.expandedIds.has(0)).toBe(false);
  });

  it('should toggle multiple expanded items', () => {
    const { result } = renderHook(() => useSearchSelection(mockResults));

    act(() => {
      result.current.toggleExpanded(0);
      result.current.toggleExpanded(2);
    });

    expect(result.current.expandedIds.has(0)).toBe(true);
    expect(result.current.expandedIds.has(2)).toBe(true);
    expect(result.current.expandedIds.has(1)).toBe(false);
  });

  it('should toggle selected state', () => {
    const { result } = renderHook(() => useSearchSelection(mockResults));

    act(() => {
      result.current.toggleSelected(0);
    });

    expect(result.current.selectedIds.has(0)).toBe(true);
    expect(result.current.selectedResults).toHaveLength(1);
    expect(result.current.selectedResults[0]).toEqual(mockResults[0]);

    act(() => {
      result.current.toggleSelected(0);
    });

    expect(result.current.selectedIds.has(0)).toBe(false);
    expect(result.current.selectedResults).toHaveLength(0);
  });

  it('should return selected results in order', () => {
    const { result } = renderHook(() => useSearchSelection(mockResults));

    act(() => {
      result.current.toggleSelected(2);
      result.current.toggleSelected(0);
      result.current.toggleSelected(1);
    });

    expect(result.current.selectedResults).toHaveLength(3);
    expect(result.current.selectedResults[0]).toEqual(mockResults[0]);
    expect(result.current.selectedResults[1]).toEqual(mockResults[1]);
    expect(result.current.selectedResults[2]).toEqual(mockResults[2]);
  });

  it('should reset selection', () => {
    const { result } = renderHook(() => useSearchSelection(mockResults));

    act(() => {
      result.current.toggleExpanded(0);
      result.current.toggleSelected(1);
      result.current.toggleSelected(2);
    });

    expect(result.current.expandedIds.size).toBe(1);
    expect(result.current.selectedIds.size).toBe(2);

    act(() => {
      result.current.resetSelection();
    });

    expect(result.current.expandedIds.size).toBe(0);
    expect(result.current.selectedIds.size).toBe(0);
    expect(result.current.selectedResults).toEqual([]);
  });

  it('should handle empty results array', () => {
    const { result } = renderHook(() => useSearchSelection([]));

    act(() => {
      result.current.toggleSelected(0);
    });

    expect(result.current.selectedResults).toEqual([]);
  });
});

