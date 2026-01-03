'use client';

import * as React from 'react';
import {
  Info,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Lightbulb,
  Zap,
  BookOpen,
  ExternalLink
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ============================================================================
// Types
// ============================================================================

export type InfoCardVariant =
  | 'info'
  | 'warning'
  | 'success'
  | 'error'
  | 'tip'
  | 'important'
  | 'note'
  | 'highlight';

export interface InfoCardProps {
  /** Variant determines color and icon */
  variant?: InfoCardVariant;
  /** Custom title (optional, uses default based on variant) */
  title?: string;
  /** Content */
  children: React.ReactNode;
  /** Optional icon override */
  icon?: React.ReactNode;
  /** Collapsible */
  collapsible?: boolean;
  /** Default collapsed state */
  defaultCollapsed?: boolean;
  /** Link */
  link?: { label: string; url: string };
  /** Custom class */
  className?: string;
}

// ============================================================================
// Variant styles
// ============================================================================

const variantStyles: Record<InfoCardVariant, {
  bg: string;
  border: string;
  iconBg: string;
  iconColor: string;
  titleColor: string;
  defaultTitle: string;
  icon: React.ComponentType<{ className?: string }>;
}> = {
  info: {
    bg: 'bg-blue-500/5',
    border: 'border-blue-500/20',
    iconBg: 'bg-blue-500/20',
    iconColor: 'text-blue-400',
    titleColor: 'text-blue-400',
    defaultTitle: 'Information',
    icon: Info,
  },
  warning: {
    bg: 'bg-amber-500/5',
    border: 'border-amber-500/20',
    iconBg: 'bg-amber-500/20',
    iconColor: 'text-amber-400',
    titleColor: 'text-amber-400',
    defaultTitle: 'Warning',
    icon: AlertTriangle,
  },
  success: {
    bg: 'bg-emerald-500/5',
    border: 'border-emerald-500/20',
    iconBg: 'bg-emerald-500/20',
    iconColor: 'text-emerald-400',
    titleColor: 'text-emerald-400',
    defaultTitle: 'Success',
    icon: CheckCircle2,
  },
  error: {
    bg: 'bg-red-500/5',
    border: 'border-red-500/20',
    iconBg: 'bg-red-500/20',
    iconColor: 'text-red-400',
    titleColor: 'text-red-400',
    defaultTitle: 'Error',
    icon: XCircle,
  },
  tip: {
    bg: 'bg-purple-500/5',
    border: 'border-purple-500/20',
    iconBg: 'bg-purple-500/20',
    iconColor: 'text-purple-400',
    titleColor: 'text-purple-400',
    defaultTitle: 'Pro Tip',
    icon: Lightbulb,
  },
  important: {
    bg: 'bg-rose-500/5',
    border: 'border-rose-500/20',
    iconBg: 'bg-rose-500/20',
    iconColor: 'text-rose-400',
    titleColor: 'text-rose-400',
    defaultTitle: 'Important',
    icon: Zap,
  },
  note: {
    bg: 'bg-white/5',
    border: 'border-white/10',
    iconBg: 'bg-white/10',
    iconColor: 'text-white/60',
    titleColor: 'text-white/80',
    defaultTitle: 'Note',
    icon: BookOpen,
  },
  highlight: {
    bg: 'bg-[#2251ff]/10',
    border: 'border-[#2251ff]/30',
    iconBg: 'bg-[#2251ff]/20',
    iconColor: 'text-[#2251ff]',
    titleColor: 'text-[#2251ff]',
    defaultTitle: 'Highlight',
    icon: Zap,
  },
};

// ============================================================================
// Main Component
// ============================================================================

export function InfoCard({
  variant = 'info',
  title,
  children,
  icon,
  collapsible = false,
  defaultCollapsed = false,
  link,
  className,
}: InfoCardProps) {
  const [isCollapsed, setIsCollapsed] = React.useState(defaultCollapsed);
  const styles = variantStyles[variant];
  const Icon = styles.icon;
  const displayTitle = title || styles.defaultTitle;

  return (
    <div
      className={cn(
        'rounded-xl border overflow-hidden',
        styles.bg,
        styles.border,
        className
      )}
    >
      {/* Header */}
      <div
        className={cn(
          'flex items-center gap-3 px-4 py-3',
          collapsible && 'cursor-pointer hover:bg-white/5 transition-colors'
        )}
        onClick={collapsible ? () => setIsCollapsed(!isCollapsed) : undefined}
      >
        <div className={cn('p-1.5 rounded-lg', styles.iconBg)}>
          {icon || <Icon className={cn('w-4 h-4', styles.iconColor)} />}
        </div>
        <span className={cn('font-medium text-sm', styles.titleColor)}>
          {displayTitle}
        </span>
        {collapsible && (
          <svg
            className={cn(
              'w-4 h-4 ml-auto transition-transform text-white/40',
              isCollapsed && 'rotate-180'
            )}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        )}
      </div>

      {/* Content */}
      {(!collapsible || !isCollapsed) && (
        <div className="px-4 pb-4">
          <div className="text-sm text-white/70 leading-relaxed">
            {children}
          </div>

          {/* Link */}
          {link && (
            <a
              href={link.url}
              className={cn(
                'inline-flex items-center gap-1.5 mt-3 text-sm',
                styles.titleColor,
                'hover:underline'
              )}
            >
              <span>{link.label}</span>
              <ExternalLink className="w-3 h-3" />
            </a>
          )}
        </div>
      )}
    </div>
  );
}
