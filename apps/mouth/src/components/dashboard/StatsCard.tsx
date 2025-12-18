'use client';

import React from 'react';
import Link from 'next/link';
import { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

interface StatsCardProps {
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
    value: 'text-[var(--foreground)]',
  },
  warning: {
    icon: 'text-[var(--warning)]',
    value: 'text-[var(--warning)]',
  },
  danger: {
    icon: 'text-[var(--error)]',
    value: 'text-[var(--error)]',
  },
  success: {
    icon: 'text-[var(--success)]',
    value: 'text-[var(--success)]',
  },
};

export function StatsCard({
  title,
  value,
  subtitle,
  icon: Icon,
  href,
  trend,
  variant = 'default',
}: StatsCardProps) {
  const styles = variantStyles[variant];

  const content = (
    <div
      className={cn(
        'p-5 rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]',
        'transition-all duration-200',
        href && 'hover:border-[var(--border-hover)] hover:bg-[var(--background-elevated)]/30 cursor-pointer'
      )}
    >
      {/* Icon */}
      <div className="flex items-center justify-between mb-3">
        <div
          className={cn(
            'w-10 h-10 rounded-lg flex items-center justify-center',
            'bg-[var(--background-elevated)]/50'
          )}
        >
          <Icon className={cn('w-5 h-5', styles.icon)} />
        </div>
        {trend && (
          <span
            className={cn(
              'text-xs font-medium px-2 py-1 rounded-full',
              trend.isPositive
                ? 'text-[var(--success)] bg-[var(--success)]/10'
                : 'text-[var(--error)] bg-[var(--error)]/10'
            )}
          >
            {trend.isPositive ? '↑' : '↓'} {trend.value}
          </span>
        )}
      </div>

      {/* Title */}
      <p className="text-sm text-[var(--foreground-muted)] mb-1">{title}</p>

      {/* Value */}
      <p className={cn('text-2xl font-bold', styles.value)}>{value}</p>

      {/* Subtitle */}
      {subtitle && (
        <p className="text-xs text-[var(--foreground-muted)] mt-1">{subtitle}</p>
      )}
    </div>
  );

  if (href) {
    return <Link href={href}>{content}</Link>;
  }

  return content;
}
