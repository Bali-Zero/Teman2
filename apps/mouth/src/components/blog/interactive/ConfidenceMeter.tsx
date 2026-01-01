'use client';

import * as React from 'react';
import { motion } from 'framer-motion';
import { Info, AlertTriangle, CheckCircle2, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

// ============================================================================
// Types
// ============================================================================

export interface ConfidenceItem {
  label: string;
  value: number; // 0-100
  source?: string;
  note?: string;
}

export interface ConfidenceMeterProps {
  /** Items to show */
  items: ConfidenceItem[];
  /** Title */
  title?: string;
  /** Show legend */
  showLegend?: boolean;
  /** Variant */
  variant?: 'compact' | 'detailed';
  /** Custom class */
  className?: string;
}

// ============================================================================
// Color utilities
// ============================================================================

function getConfidenceColor(value: number): {
  bg: string;
  fill: string;
  text: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
} {
  if (value >= 80) {
    return {
      bg: 'bg-emerald-500/10',
      fill: 'bg-gradient-to-r from-emerald-500 to-emerald-400',
      text: 'text-emerald-400',
      label: 'High confidence',
      icon: CheckCircle2,
    };
  }
  if (value >= 60) {
    return {
      bg: 'bg-blue-500/10',
      fill: 'bg-gradient-to-r from-blue-500 to-blue-400',
      text: 'text-blue-400',
      label: 'Good confidence',
      icon: Info,
    };
  }
  if (value >= 40) {
    return {
      bg: 'bg-amber-500/10',
      fill: 'bg-gradient-to-r from-amber-500 to-amber-400',
      text: 'text-amber-400',
      label: 'Moderate confidence',
      icon: AlertCircle,
    };
  }
  return {
    bg: 'bg-red-500/10',
    fill: 'bg-gradient-to-r from-red-500 to-red-400',
    text: 'text-red-400',
    label: 'Low confidence',
    icon: AlertTriangle,
  };
}

// ============================================================================
// Main Component
// ============================================================================

export function ConfidenceMeter({
  items,
  title = 'Data Reliability',
  showLegend = true,
  variant = 'detailed',
  className,
}: ConfidenceMeterProps) {
  const isCompact = variant === 'compact';

  return (
    <div className={cn(
      'rounded-xl border border-white/10 overflow-hidden',
      isCompact ? 'bg-white/5 p-3' : 'bg-black/40 p-4',
      className
    )}>
      {/* Header */}
      {!isCompact && (
        <div className="flex items-center gap-2 mb-4">
          <Info className="w-4 h-4 text-white/40" />
          <h4 className="text-sm font-medium text-white/80">{title}</h4>
        </div>
      )}

      {/* Items */}
      <div className={cn('space-y-3', isCompact && 'space-y-2')}>
        {items.map((item, index) => {
          const colors = getConfidenceColor(item.value);
          const Icon = colors.icon;

          return (
            <div key={item.label}>
              {/* Label and value */}
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  {!isCompact && <Icon className={cn('w-3.5 h-3.5', colors.text)} />}
                  <span className={cn(
                    'text-white/70',
                    isCompact ? 'text-xs' : 'text-sm'
                  )}>
                    {item.label}
                  </span>
                </div>
                <span className={cn(
                  'font-mono font-medium',
                  colors.text,
                  isCompact ? 'text-xs' : 'text-sm'
                )}>
                  {item.value}%
                </span>
              </div>

              {/* Progress bar */}
              <div className={cn(
                'rounded-full overflow-hidden',
                colors.bg,
                isCompact ? 'h-1.5' : 'h-2'
              )}>
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${item.value}%` }}
                  transition={{ duration: 0.5, delay: index * 0.1 }}
                  className={cn('h-full rounded-full', colors.fill)}
                />
              </div>

              {/* Source and note */}
              {!isCompact && (item.source || item.note) && (
                <div className="mt-1 flex items-center gap-2 text-xs text-white/40">
                  {item.source && <span>Source: {item.source}</span>}
                  {item.source && item.note && <span>•</span>}
                  {item.note && <span>{item.note}</span>}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Legend */}
      {showLegend && !isCompact && (
        <div className="mt-4 pt-3 border-t border-white/10">
          <div className="flex flex-wrap gap-4 text-xs">
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-emerald-500" />
              <span className="text-white/40">80-100%: High</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-blue-500" />
              <span className="text-white/40">60-79%: Good</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-amber-500" />
              <span className="text-white/40">40-59%: Moderate</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 rounded-full bg-red-500" />
              <span className="text-white/40">0-39%: Low</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
