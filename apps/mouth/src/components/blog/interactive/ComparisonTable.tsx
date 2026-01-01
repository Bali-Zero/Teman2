'use client';

import * as React from 'react';
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Check,
  X,
  Minus,
  ChevronDown,
  Eye,
  EyeOff,
  Trophy,
  AlertCircle,
  ExternalLink
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ============================================================================
// Types
// ============================================================================

export interface ComparisonItem {
  id: string;
  name: string;
  description?: string;
  icon?: string;
  color?: 'blue' | 'green' | 'amber' | 'red' | 'purple';
  recommended?: boolean;
  learnMoreUrl?: string;
}

export interface ComparisonFeature {
  id: string;
  name: string;
  category?: string;
  description?: string;
  /** Values for each item: true = yes, false = no, string = custom value, null = N/A */
  values: Record<string, boolean | string | null>;
  /** Highlight this row */
  important?: boolean;
}

export interface ComparisonTableProps {
  /** Title */
  title: string;
  /** Subtitle */
  subtitle?: string;
  /** Items to compare */
  items: ComparisonItem[];
  /** Features/rows */
  features: ComparisonFeature[];
  /** Show only differences */
  showDifferencesOnly?: boolean;
  /** Enable toggle for differences only */
  allowToggleDifferences?: boolean;
  /** Show winner recommendation */
  showRecommendation?: boolean;
  /** Custom recommendation text */
  recommendationText?: string;
  /** Custom class */
  className?: string;
}

// ============================================================================
// Color utilities
// ============================================================================

const itemColors = {
  blue: {
    header: 'bg-blue-500/10 border-blue-500/30',
    text: 'text-blue-400',
    badge: 'bg-blue-500/20 text-blue-400',
  },
  green: {
    header: 'bg-emerald-500/10 border-emerald-500/30',
    text: 'text-emerald-400',
    badge: 'bg-emerald-500/20 text-emerald-400',
  },
  amber: {
    header: 'bg-amber-500/10 border-amber-500/30',
    text: 'text-amber-400',
    badge: 'bg-amber-500/20 text-amber-400',
  },
  red: {
    header: 'bg-red-500/10 border-red-500/30',
    text: 'text-red-400',
    badge: 'bg-red-500/20 text-red-400',
  },
  purple: {
    header: 'bg-purple-500/10 border-purple-500/30',
    text: 'text-purple-400',
    badge: 'bg-purple-500/20 text-purple-400',
  },
};

// ============================================================================
// Main Component
// ============================================================================

export function ComparisonTable({
  title,
  subtitle,
  items,
  features,
  showDifferencesOnly: initialShowDifferences = false,
  allowToggleDifferences = true,
  showRecommendation = true,
  recommendationText,
  className,
}: ComparisonTableProps) {
  const [showDifferencesOnly, setShowDifferencesOnly] = useState(initialShowDifferences);
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set());

  // Get recommended item
  const recommendedItem = items.find((item) => item.recommended);

  // Filter features based on differences
  const filteredFeatures = showDifferencesOnly
    ? features.filter((feature) => {
        const values = Object.values(feature.values);
        const first = JSON.stringify(values[0]);
        return !values.every((v) => JSON.stringify(v) === first);
      })
    : features;

  // Group features by category
  const categories = Array.from(new Set(filteredFeatures.map((f) => f.category || 'General')));
  const featuresByCategory = categories.reduce((acc, cat) => {
    acc[cat] = filteredFeatures.filter((f) => (f.category || 'General') === cat);
    return acc;
  }, {} as Record<string, ComparisonFeature[]>);

  // Toggle category
  const toggleCategory = (category: string) => {
    const next = new Set(expandedCategories);
    if (next.has(category)) {
      next.delete(category);
    } else {
      next.add(category);
    }
    setExpandedCategories(next);
  };

  return (
    <div className={cn('bg-black/40 rounded-2xl border border-white/10 overflow-hidden', className)}>
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/10">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-serif text-xl font-semibold text-white">{title}</h3>
            {subtitle && <p className="text-white/60 text-sm mt-1">{subtitle}</p>}
          </div>
          {allowToggleDifferences && (
            <button
              onClick={() => setShowDifferencesOnly(!showDifferencesOnly)}
              className={cn(
                'flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-colors',
                showDifferencesOnly
                  ? 'bg-[#2251ff]/20 text-[#2251ff]'
                  : 'bg-white/5 text-white/60 hover:bg-white/10'
              )}
            >
              {showDifferencesOnly ? (
                <>
                  <Eye className="w-4 h-4" />
                  <span>Differences only</span>
                </>
              ) : (
                <>
                  <EyeOff className="w-4 h-4" />
                  <span>Show all</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>

      {/* Recommendation banner */}
      {showRecommendation && recommendedItem && (
        <div className="px-6 py-3 bg-gradient-to-r from-amber-500/10 to-transparent border-b border-amber-500/20">
          <div className="flex items-center gap-2 text-amber-400">
            <Trophy className="w-4 h-4" />
            <span className="text-sm font-medium">
              {recommendationText || `Recommended: ${recommendedItem.name}`}
            </span>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          {/* Column headers */}
          <thead>
            <tr>
              <th className="text-left p-4 border-b border-white/10 min-w-[200px]">
                <span className="text-white/40 text-sm font-normal">Feature</span>
              </th>
              {items.map((item) => {
                const colors = itemColors[item.color || 'blue'];
                return (
                  <th
                    key={item.id}
                    className={cn(
                      'p-4 border-b min-w-[160px] text-center',
                      colors.header
                    )}
                  >
                    <div className="flex flex-col items-center gap-2">
                      {item.icon && <span className="text-2xl">{item.icon}</span>}
                      <span className={cn('font-semibold', colors.text)}>{item.name}</span>
                      {item.recommended && (
                        <span className={cn('text-xs px-2 py-0.5 rounded-full', colors.badge)}>
                          Recommended
                        </span>
                      )}
                      {item.description && (
                        <span className="text-white/40 text-xs font-normal">{item.description}</span>
                      )}
                    </div>
                  </th>
                );
              })}
            </tr>
          </thead>

          {/* Body - grouped by category */}
          <tbody>
            {categories.map((category) => (
              <React.Fragment key={category}>
                {/* Category header */}
                {categories.length > 1 && (
                  <tr>
                    <td
                      colSpan={items.length + 1}
                      className="bg-white/5 border-b border-white/10"
                    >
                      <button
                        onClick={() => toggleCategory(category)}
                        className="w-full flex items-center justify-between px-4 py-2 text-left"
                      >
                        <span className="text-white/80 font-medium text-sm">{category}</span>
                        <ChevronDown
                          className={cn(
                            'w-4 h-4 text-white/40 transition-transform',
                            expandedCategories.has(category) && 'rotate-180'
                          )}
                        />
                      </button>
                    </td>
                  </tr>
                )}

                {/* Features in category */}
                <AnimatePresence>
                  {(categories.length === 1 || !expandedCategories.has(category)) &&
                    featuresByCategory[category].map((feature, featureIndex) => (
                      <motion.tr
                        key={feature.id}
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className={cn(
                          'border-b border-white/5',
                          feature.important && 'bg-amber-500/5'
                        )}
                      >
                        {/* Feature name */}
                        <td className="p-4">
                          <div className="flex items-center gap-2">
                            <span className={cn(
                              'text-white/80',
                              feature.important && 'font-medium text-amber-400'
                            )}>
                              {feature.name}
                            </span>
                            {feature.description && (
                              <div className="group relative">
                                <AlertCircle className="w-3.5 h-3.5 text-white/30 cursor-help" />
                                <div className="absolute left-0 bottom-full mb-1 p-2 bg-black/90 rounded-lg text-xs text-white/60 opacity-0 group-hover:opacity-100 transition-opacity w-48 pointer-events-none z-10">
                                  {feature.description}
                                </div>
                              </div>
                            )}
                          </div>
                        </td>

                        {/* Values for each item */}
                        {items.map((item) => {
                          const value = feature.values[item.id];
                          return (
                            <td key={item.id} className="p-4 text-center">
                              <ValueCell value={value} />
                            </td>
                          );
                        })}
                      </motion.tr>
                    ))}
                </AnimatePresence>
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer with learn more links */}
      {items.some((item) => item.learnMoreUrl) && (
        <div className="px-6 py-4 border-t border-white/10 flex flex-wrap gap-4">
          {items.map((item) =>
            item.learnMoreUrl ? (
              <a
                key={item.id}
                href={item.learnMoreUrl}
                className="flex items-center gap-1 text-sm text-white/60 hover:text-white transition-colors"
              >
                <span>Learn more about {item.name}</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            ) : null
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Value Cell Component
// ============================================================================

function ValueCell({ value }: { value: boolean | string | null }) {
  if (value === null) {
    return (
      <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-white/5">
        <Minus className="w-4 h-4 text-white/30" />
      </span>
    );
  }

  if (typeof value === 'boolean') {
    return value ? (
      <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-emerald-500/20">
        <Check className="w-4 h-4 text-emerald-400" />
      </span>
    ) : (
      <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-red-500/20">
        <X className="w-4 h-4 text-red-400" />
      </span>
    );
  }

  return <span className="text-white/80 text-sm">{value}</span>;
}
