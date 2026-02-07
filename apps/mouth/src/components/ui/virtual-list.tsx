'use client';

import { useRef, useCallback, memo } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { cn } from '@/lib/utils';

interface VirtualListProps<T> {
  items: T[];
  renderItem: (item: T, index: number) => React.ReactNode;
  estimateSize: number;
  gap?: number;
  className?: string;
  overscan?: number;
  keyExtractor: (item: T, index: number) => string | number;
  onEndReached?: () => void;
  endReachedThreshold?: number;
}

/**
 * Virtualized list component for rendering large datasets efficiently.
 * Only renders items visible in the viewport + overscan.
 *
 * @example
 * ```tsx
 * <VirtualList
 *   items={clients}
 *   renderItem={(client) => <ClientCard client={client} />}
 *   estimateSize={180}
 *   keyExtractor={(client) => client.id}
 * />
 * ```
 */
function VirtualListInner<T>({
  items,
  renderItem,
  estimateSize,
  gap = 0,
  className,
  overscan = 5,
  keyExtractor,
  onEndReached,
  endReachedThreshold = 0.8,
}: VirtualListProps<T>) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => estimateSize + gap,
    overscan,
  });

  const virtualItems = virtualizer.getVirtualItems();

  // Handle end reached callback
  const lastItemIndex = virtualItems[virtualItems.length - 1]?.index ?? 0;
  const progress = items.length > 0 ? lastItemIndex / items.length : 0;

  if (progress >= endReachedThreshold && onEndReached) {
    onEndReached();
  }

  return (
    <div ref={parentRef} className={cn('overflow-auto', className)} style={{ contain: 'strict' }}>
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
        }}
      >
        {virtualItems.map((virtualItem) => {
          const item = items[virtualItem.index];
          if (!item) return null;

          return (
            <div
              key={keyExtractor(item, virtualItem.index)}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: `${estimateSize}px`,
                transform: `translateY(${virtualItem.start}px)`,
              }}
            >
              {renderItem(item, virtualItem.index)}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Memoized virtual list to prevent unnecessary re-renders when parent updates.
 * Use this for large, stable lists where items don't change frequently.
 */
const VirtualListComponent = memo(VirtualListInner) as <T>(
  props: VirtualListProps<T>
) => React.ReactElement;

export { VirtualListComponent as VirtualList };

/**
 * Optimized list item wrapper that prevents re-renders when item data is stable.
 */
interface ListItemProps {
  children: React.ReactNode;
  className?: string;
}

export const ListItem = memo(function ListItem({ children, className }: ListItemProps) {
  return <div className={className}>{children}</div>;
});

ListItem.displayName = 'ListItem';
