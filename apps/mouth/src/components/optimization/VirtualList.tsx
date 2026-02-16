"use client";

/**
 * VirtualList Component
 *
 * Efficiently render large lists using virtualization
 */

import { useRef, useCallback, ReactNode } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";

interface VirtualListProps<T> {
  items: T[];
  renderItem: (item: T, index: number) => ReactNode;
  itemHeight: number;
  overscan?: number;
  className?: string;
  estimateSize?: (index: number) => number;
}

export function VirtualList<T>({
  items,
  renderItem,
  itemHeight,
  overscan = 5,
  className = "",
  estimateSize,
}: VirtualListProps<T>) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: estimateSize || (() => itemHeight),
    overscan,
  });

  return (
    <div
      ref={parentRef}
      className={`overflow-auto ${className}`}
      style={{ height: "100%" }}
    >
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: "100%",
          position: "relative",
        }}
      >
        {virtualizer.getVirtualItems().map((virtualItem) => (
          <div
            key={virtualItem.key}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: `${virtualItem.size}px`,
              transform: `translateY(${virtualItem.start}px)`,
            }}
          >
            {renderItem(items[virtualItem.index], virtualItem.index)}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Simple fixed-height virtual list
 */
export function FixedVirtualList<T>({
  items,
  renderItem,
  itemHeight,
  height,
  className = "",
}: Omit<VirtualListProps<T>, "estimateSize" | "overscan"> & {
  height: number;
}) {
  return (
    <div style={{ height }} className={className}>
      <VirtualList
        items={items}
        renderItem={renderItem}
        itemHeight={itemHeight}
      />
    </div>
  );
}
