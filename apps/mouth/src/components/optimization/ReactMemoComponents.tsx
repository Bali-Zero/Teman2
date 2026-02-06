/**
 * Optimized React Components with Memoization
 * 
 * These components use React.memo to prevent unnecessary re-renders
 * when props haven't changed. Use for frequently rendered components.
 */

import React from 'react';

interface MemoCardProps {
  title: string;
  children: React.ReactNode;
  className?: string;
}

/**
 * Memoized Card component
 * Prevents re-render when parent changes but props don't
 */
export const MemoCard = React.memo<MemoCardProps>(function MemoCard({ 
  title, 
  children, 
  className = '' 
}) {
  return (
    <div className={`rounded-lg border bg-card p-4 ${className}`}>
      <h3 className="font-semibold mb-2">{title}</h3>
      {children}
    </div>
  );
});

interface MemoListItemProps {
  id: string;
  title: string;
  subtitle?: string;
  onClick?: (id: string) => void;
}

/**
 * Memoized List Item component
 * Essential for long lists - prevents all items from re-rendering
 * when only one item changes
 */
export const MemoListItem = React.memo<MemoListItemProps>(function MemoListItem({
  id,
  title,
  subtitle,
  onClick,
}) {
  return (
    <div 
      className="flex items-center justify-between p-3 hover:bg-accent rounded-md cursor-pointer"
      onClick={() => onClick?.(id)}
    >
      <div>
        <div className="font-medium">{title}</div>
        {subtitle && <div className="text-sm text-muted-foreground">{subtitle}</div>}
      </div>
    </div>
  );
});

interface MemoBadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'secondary' | 'destructive' | 'outline';
}

/**
 * Memoized Badge component
 * Prevents re-render when used in dynamic lists
 */
export const MemoBadge = React.memo<MemoBadgeProps>(function MemoBadge({
  children,
  variant = 'default',
}) {
  const variantClasses = {
    default: 'bg-primary text-primary-foreground',
    secondary: 'bg-secondary text-secondary-foreground',
    destructive: 'bg-destructive text-destructive-foreground',
    outline: 'border border-input bg-background',
  };

  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors ${variantClasses[variant]}`}>
      {children}
    </span>
  );
});

// Export optimization utilities
export const optimizationUtils = {
  /**
   * Custom comparison function for React.memo
   * Use when you need to compare specific props
   */
  compareProps: <T extends Record<string, unknown>>(
    prevProps: T,
    nextProps: T,
    keysToCompare?: (keyof T)[]
  ): boolean => {
    const keys = keysToCompare || Object.keys(prevProps) as (keyof T)[];
    return keys.every(key => prevProps[key] === nextProps[key]);
  },

  /**
   * Memoization wrapper with display name
   */
  withMemo: <P extends object>(
    Component: React.ComponentType<P>,
    displayName?: string
  ): React.NamedExoticComponent<P> => {
    const Memoized = React.memo(Component);
    Memoized.displayName = displayName || Component.displayName || 'MemoizedComponent';
    return Memoized;
  },
};
