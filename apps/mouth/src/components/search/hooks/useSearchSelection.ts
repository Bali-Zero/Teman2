import { useState, useCallback, useMemo } from 'react';
import { KnowledgeSearchResult } from '@/lib/api';

export function useSearchSelection(results: KnowledgeSearchResult[]) {
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const toggleExpanded = useCallback((idx: number) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }, []);

  const toggleSelected = useCallback((idx: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  }, []);

  const selectedResults = useMemo(
    () => Array.from(selectedIds).sort((a, b) => a - b).map((i) => results[i]).filter(Boolean),
    [results, selectedIds]
  );

  const resetSelection = useCallback(() => {
    setExpandedIds(new Set());
    setSelectedIds(new Set());
  }, []);

  return {
    expandedIds,
    selectedIds,
    selectedResults,
    toggleExpanded,
    toggleSelected,
    resetSelection,
  };
}

