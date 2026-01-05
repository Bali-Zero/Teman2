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
  accentColor?: 'blue' | 'teal' | 'amber' | 'purple' | 'pink' | 'emerald' | 'cyan';
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

const accentStyles: Record<string, { border: string; icon: string }> = {
  blue: { border: 'border-l-[3px] border-l-[#60A5FA]', icon: 'text-[#60A5FA]' },
  teal: { border: 'border-l-[3px] border-l-[#2DD4BF]', icon: 'text-[#2DD4BF]' },
  amber: { border: 'border-l-[3px] border-l-[#FBBF24]', icon: 'text-[#FBBF24]' },
  purple: { border: 'border-l-[3px] border-l-[#A78BFA]', icon: 'text-[#A78BFA]' },
  pink: { border: 'border-l-[3px] border-l-[#F472B6]', icon: 'text-[#F472B6]' },
  emerald: { border: 'border-l-[3px] border-l-[#34D399]', icon: 'text-[#34D399]' },
  cyan: { border: 'border-l-[3px] border-l-[#22D3EE]', icon: 'text-[#22D3EE]' },
};

export function StatsCard({
  title,
  value,
  subtitle,
  icon: Icon,
  href,
  trend,
  variant = 'default',
  accentColor,
}: StatsCardProps) {
  const styles = variantStyles[variant];
  const accent = accentColor ? accentStyles[accentColor] : null;

  const content = (
    <div
      className={cn(
        'p-5 rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]',
        'transition-all duration-200',
        href && 'hover:border-[var(--border-hover)] hover:bg-[var(--background-elevated)]/30 cursor-pointer',
        accent?.border
      )}
    >
      <div className="flex items-center justify-between mb-3">
        <div
          className={cn(
            'w-10 h-10 rounded-lg flex items-center justify-center',
            'bg-[var(--background-elevated)]/50'
          )}
        >
          <Icon className={cn('w-5 h-5', accent ? accent.icon : styles.icon)} />
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

      <p className="text-sm text-[var(--foreground-muted)] mb-1">{title}</p>
      <p className={cn('text-2xl font-bold', styles.value)}>{value}</p>
      
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
