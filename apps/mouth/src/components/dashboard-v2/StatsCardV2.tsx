'use client';

import React from 'react';
import Link from 'next/link';
import { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

interface StatsCardV2Props {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  href?: string;
  trend?: {
    value: string;
    isPositive: boolean;
  };
  variant?: 'default' | 'warning' | 'danger' | 'success';
}

const variantStyles = {
  default: {
    icon: 'text-[var(--foreground-secondary)]',
    iconBg: 'bg-[var(--background-elevated)]',
    value: 'text-[var(--foreground)]',
  },
  warning: {
    icon: 'text-[var(--warning)]',
    iconBg: 'bg-[var(--warning-muted)]',
    value: 'text-[var(--warning)]',
  },
  danger: {
    icon: 'text-[var(--error)]',
    iconBg: 'bg-[var(--error-muted)]',
    value: 'text-[var(--error)]',
  },
  success: {
    icon: 'text-[var(--success)]',
    iconBg: 'bg-[var(--success-muted)]',
    value: 'text-[var(--success)]',
  },
};

/**
 * StatsCardV2 - Improved stats card with:
 * - Full CSS variables (no hardcoded colors)
 * - Better accessibility (aria-label on links)
 * - Improved focus states
 * - Consistent with Design System v2.0
 */
export function StatsCardV2({
  title,
  value,
  subtitle,
  icon: Icon,
  href,
  trend,
  variant = 'default',
}: StatsCardV2Props) {
  const styles = variantStyles[variant];

  const content = (
    <div
      className={cn(
        'p-5 rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]',
        'transition-all duration-[var(--transition-normal)]',
        href && 'hover:border-[var(--border-hover)] hover:bg-[var(--background-elevated)] cursor-pointer'
      )}
    >
      {/* Header: Icon + Trend */}
      <div className="flex items-center justify-between mb-3">
        <div
          className={cn(
            'w-10 h-10 rounded-lg flex items-center justify-center',
            styles.iconBg
          )}
        >
          <Icon className={cn('w-5 h-5', styles.icon)} aria-hidden="true" />
        </div>
        {trend && (
          <span
            className={cn(
              'text-xs font-medium px-2 py-1 rounded-full',
              trend.isPositive
                ? 'text-[var(--success)] bg-[var(--success-muted)]'
                : 'text-[var(--error)] bg-[var(--error-muted)]'
            )}
            aria-label={`Trend: ${trend.isPositive ? 'up' : 'down'} ${trend.value}`}
          >
            {trend.isPositive ? '↑' : '↓'} {trend.value}
          </span>
        )}
      </div>

      {/* Title */}
      <p className="text-sm text-[var(--foreground-muted)] mb-1">{title}</p>

      {/* Value */}
      <p className={cn('text-2xl font-bold tracking-tight', styles.value)}>{value}</p>

      {/* Subtitle */}
      {subtitle && (
        <p className="text-xs text-[var(--foreground-muted)] mt-1">{subtitle}</p>
      )}
    </div>
  );

  if (href) {
    return (
      <Link
        href={href}
        className="block focus-ring rounded-xl"
        aria-label={`${title}: ${value}. Click to view details.`}
      >
        {content}
      </Link>
    );
  }

  return content;
}

export default StatsCardV2;
