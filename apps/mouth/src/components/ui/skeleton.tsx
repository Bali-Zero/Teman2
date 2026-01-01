'use client';

import { cn } from '@/lib/utils';

interface SkeletonProps {
  className?: string;
  variant?: 'text' | 'circular' | 'rectangular' | 'rounded';
  width?: string | number;
  height?: string | number;
  lines?: number;
}

/**
 * Base Skeleton component with shimmer animation
 * Uses CSS classes from globals.css for consistent styling
 */
export function Skeleton({
  className,
  variant = 'rectangular',
  width,
  height,
  lines = 1,
}: SkeletonProps) {
  const baseStyles = 'skeleton';

  const variantStyles = {
    text: 'h-4 rounded',
    circular: 'rounded-full',
    rectangular: 'rounded-none',
    rounded: 'rounded-lg',
  };

  const style: React.CSSProperties = {
    width: typeof width === 'number' ? `${width}px` : width,
    height: typeof height === 'number' ? `${height}px` : height,
  };

  if (lines > 1) {
    return (
      <div className="space-y-2">
        {Array.from({ length: lines }).map((_, i) => (
          <div
            key={i}
            className={cn(baseStyles, variantStyles[variant], className)}
            style={{
              ...style,
              width: i === lines - 1 ? '75%' : style.width, // Last line shorter
            }}
          />
        ))}
      </div>
    );
  }

  return (
    <div
      className={cn(baseStyles, variantStyles[variant], className)}
      style={style}
    />
  );
}

/**
 * Skeleton for message bubbles in chat
 */
export function MessageBubbleSkeleton({ isUser = false }: { isUser?: boolean }) {
  return (
    <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'} mb-6`}>
      <div className={`flex max-w-[75%] gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
        {/* Avatar skeleton */}
        <Skeleton
          variant="circular"
          width={isUser ? 40 : 56}
          height={isUser ? 40 : 56}
        />

        {/* Content skeleton */}
        <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} min-w-0 flex-1`}>
          <div
            className={cn(
              'px-5 py-4 rounded-2xl w-full max-w-md',
              isUser
                ? 'bg-[var(--background-secondary)] rounded-tr-sm'
                : 'bg-[var(--background-elevated)] rounded-tl-sm border border-[var(--border)]/50'
            )}
          >
            {/* Header badges (AI only) */}
            {!isUser && (
              <div className="flex gap-2 mb-3">
                <Skeleton variant="rounded" width={80} height={18} />
                <Skeleton variant="rounded" width={50} height={18} />
              </div>
            )}

            {/* Message lines */}
            <Skeleton variant="text" lines={isUser ? 1 : 3} className="w-full" />
          </div>

          {/* Timestamp skeleton */}
          <div className="mt-1 px-1">
            <Skeleton variant="text" width={60} height={12} />
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Skeleton for chat message list (multiple messages)
 */
export function ChatMessageListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-4 p-4">
      {Array.from({ length: count }).map((_, i) => (
        <MessageBubbleSkeleton key={i} isUser={i % 2 === 0} />
      ))}
    </div>
  );
}

/**
 * Skeleton for dashboard stat cards
 */
export function StatCardSkeleton() {
  return (
    <div className="p-6 rounded-xl bg-[var(--background-elevated)] border border-[var(--border)]">
      <div className="flex items-center justify-between mb-4">
        <Skeleton variant="text" width={100} height={14} />
        <Skeleton variant="circular" width={32} height={32} />
      </div>
      <Skeleton variant="text" width={80} height={32} className="mb-2" />
      <Skeleton variant="text" width={120} height={12} />
    </div>
  );
}

/**
 * Skeleton for dashboard widget cards
 */
export function WidgetSkeleton({ height = 200 }: { height?: number }) {
  return (
    <div
      className="p-6 rounded-xl bg-[var(--background-elevated)] border border-[var(--border)]"
      style={{ height }}
    >
      <div className="flex items-center justify-between mb-4">
        <Skeleton variant="text" width={140} height={18} />
        <Skeleton variant="rounded" width={60} height={24} />
      </div>
      <div className="space-y-3">
        <Skeleton variant="rounded" height={40} className="w-full" />
        <Skeleton variant="rounded" height={40} className="w-full" />
        <Skeleton variant="rounded" height={40} className="w-3/4" />
      </div>
    </div>
  );
}

/**
 * Skeleton for sidebar conversation items
 */
export function ConversationItemSkeleton() {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg">
      <Skeleton variant="circular" width={36} height={36} />
      <div className="flex-1 min-w-0">
        <Skeleton variant="text" width="80%" height={14} className="mb-1" />
        <Skeleton variant="text" width="60%" height={12} />
      </div>
    </div>
  );
}

/**
 * Skeleton for sidebar (list of conversations)
 */
export function SidebarSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="space-y-2 p-2">
      {Array.from({ length: count }).map((_, i) => (
        <ConversationItemSkeleton key={i} />
      ))}
    </div>
  );
}

/**
 * Skeleton for table rows
 */
export function TableRowSkeleton({ columns = 4 }: { columns?: number }) {
  return (
    <tr className="border-b border-[var(--border)]">
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="p-4">
          <Skeleton variant="text" width={i === 0 ? '60%' : '80%'} height={16} />
        </td>
      ))}
    </tr>
  );
}

/**
 * Full page loading skeleton
 */
export function PageSkeleton() {
  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Skeleton variant="text" width={200} height={32} />
        <div className="flex gap-2">
          <Skeleton variant="rounded" width={100} height={40} />
          <Skeleton variant="rounded" width={100} height={40} />
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <StatCardSkeleton />
        <StatCardSkeleton />
        <StatCardSkeleton />
      </div>

      {/* Main content */}
      <WidgetSkeleton height={300} />
    </div>
  );
}

export default Skeleton;
