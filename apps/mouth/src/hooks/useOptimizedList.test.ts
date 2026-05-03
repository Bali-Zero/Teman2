import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useOptimizedList } from "./useOptimizedList";

type Item = { id: number; name: string };

const items: Item[] = Array.from({ length: 100 }, (_, i) => ({
  id: i + 1,
  name: `Item ${i + 1}`,
}));

describe("useOptimizedList", () => {
  it("returns the first page of items with default pageSize", () => {
    const { result } = renderHook(() =>
      useOptimizedList({
        items,
        keyExtractor: (item) => item.id,
      }),
    );

    // Default pageSize is 50, first page
    expect(result.current.paginatedItems).toHaveLength(50);
    expect(result.current.currentPage).toBe(1);
    expect(result.current.hasMore).toBe(true);
  });

  it("respects custom pageSize", () => {
    const { result } = renderHook(() =>
      useOptimizedList({
        items,
        pageSize: 10,
        keyExtractor: (item) => item.id,
      }),
    );

    expect(result.current.paginatedItems).toHaveLength(10);
    expect(result.current.totalPages).toBe(10);
    expect(result.current.hasMore).toBe(true);
  });

  it("filters items with filterFn", () => {
    const { result } = renderHook(() =>
      useOptimizedList({
        items,
        pageSize: 200,
        filterFn: (item, query) =>
          item.name.toLowerCase().includes(query.toLowerCase()),
        keyExtractor: (item) => item.id,
      }),
    );

    act(() => {
      result.current.setSearchQuery("Item 1");
    });

    // Items 1, 10-19, 100 = 12 items matching "Item 1"
    expect(result.current.filteredItems.length).toBe(12);
  });

  it("resets page to 1 when search query changes", () => {
    const { result } = renderHook(() =>
      useOptimizedList({
        items,
        pageSize: 10,
        filterFn: (item, query) => item.name.includes(query),
        keyExtractor: (item) => item.id,
      }),
    );

    act(() => {
      result.current.setCurrentPage(3);
    });

    expect(result.current.currentPage).toBe(3);

    act(() => {
      result.current.setSearchQuery("Item 5");
    });

    expect(result.current.currentPage).toBe(1);
  });

  it("sorts items when sortFn is provided", () => {
    const { result } = renderHook(() =>
      useOptimizedList({
        items,
        pageSize: 5,
        sortFn: (a, b) => b.id - a.id, // Descending
        keyExtractor: (item) => item.id,
      }),
    );

    expect(result.current.paginatedItems[0].id).toBe(100);
    expect(result.current.paginatedItems[4].id).toBe(96);
  });

  it("returns hasMore=false on the last page", () => {
    const shortList = [
      { id: 1, name: "A" },
      { id: 2, name: "B" },
    ];

    const { result } = renderHook(() =>
      useOptimizedList({
        items: shortList,
        pageSize: 10,
        keyExtractor: (item) => item.id,
      }),
    );

    expect(result.current.hasMore).toBe(false);
    expect(result.current.paginatedItems).toHaveLength(2);
  });
});
