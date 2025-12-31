'use client';

import * as React from 'react';
import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Check,
  Circle,
  Download,
  RotateCcw,
  ListChecks,
  Printer
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ============================================================================
// Types
// ============================================================================

export interface ChecklistItem {
  id: string;
  label: string;
  description?: string;
  required?: boolean;
  /** Group/category */
  group?: string;
}

export interface ChecklistProps {
  /** Unique ID for saving progress */
  id: string;
  /** Title */
  title: string;
  /** Subtitle */
  subtitle?: string;
  /** Items */
  items: ChecklistItem[];
  /** Persist to localStorage */
  persist?: boolean;
  /** Allow download as PDF */
  allowDownload?: boolean;
  /** Allow print */
  allowPrint?: boolean;
  /** Custom class */
  className?: string;
}

// ============================================================================
// Main Component
// ============================================================================

export function Checklist({
  id,
  title,
  subtitle,
  items,
  persist = true,
  allowDownload = true,
  allowPrint = true,
  className,
}: ChecklistProps) {
  const storageKey = `checklist-${id}`;

  // Initialize checked items
  const [checked, setChecked] = useState<Set<string>>(() => {
    if (typeof window === 'undefined' || !persist) return new Set();
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) return new Set(JSON.parse(saved));
    } catch {}
    return new Set();
  });

  // Persist to localStorage
  useEffect(() => {
    if (!persist || typeof window === 'undefined') return;
    localStorage.setItem(storageKey, JSON.stringify(Array.from(checked)));
  }, [checked, persist, storageKey]);

  // Toggle item
  const toggle = (itemId: string) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) {
        next.delete(itemId);
      } else {
        next.add(itemId);
      }
      return next;
    });
  };

  // Reset all
  const reset = () => {
    setChecked(new Set());
    if (persist && typeof window !== 'undefined') {
      localStorage.removeItem(storageKey);
    }
  };

  // Calculate progress
  const progress = (checked.size / items.length) * 100;
  const requiredItems = items.filter((i) => i.required);
  const requiredComplete = requiredItems.filter((i) => checked.has(i.id)).length;

  // Group items by group
  const groups = Array.from(new Set(items.map((i) => i.group || 'Items')));
  const itemsByGroup = groups.reduce((acc, group) => {
    acc[group] = items.filter((i) => (i.group || 'Items') === group);
    return acc;
  }, {} as Record<string, ChecklistItem[]>);

  // Handle print
  const handlePrint = () => {
    window.print();
  };

  return (
    <div className={cn('bg-black/40 rounded-2xl border border-white/10 overflow-hidden', className)}>
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-[#2251ff]/20 text-[#2251ff]">
              <ListChecks className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-serif text-xl font-semibold text-white">{title}</h3>
              {subtitle && <p className="text-white/60 text-sm mt-0.5">{subtitle}</p>}
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            {allowPrint && (
              <button
                onClick={handlePrint}
                className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-colors"
                title="Print checklist"
              >
                <Printer className="w-4 h-4" />
              </button>
            )}
            {allowDownload && (
              <button
                className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-colors"
                title="Download PDF"
              >
                <Download className="w-4 h-4" />
              </button>
            )}
            <button
              onClick={reset}
              className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-colors"
              title="Reset checklist"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Progress */}
        <div className="mt-4">
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-white/60">
              {checked.size} of {items.length} completed
            </span>
            <span className="text-white/40">
              {requiredItems.length > 0 && `${requiredComplete}/${requiredItems.length} required`}
            </span>
          </div>
          <div className="h-2 bg-white/10 rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${progress}%` }}
              className={cn(
                'h-full rounded-full',
                progress === 100
                  ? 'bg-gradient-to-r from-emerald-500 to-emerald-400'
                  : 'bg-gradient-to-r from-[#2251ff] to-[#4d73ff]'
              )}
            />
          </div>
        </div>
      </div>

      {/* Items */}
      <div className="p-6 space-y-6">
        {groups.map((group) => (
          <div key={group}>
            {groups.length > 1 && (
              <h4 className="text-sm font-medium text-white/60 uppercase tracking-wider mb-3">
                {group}
              </h4>
            )}
            <div className="space-y-2">
              {itemsByGroup[group].map((item, index) => {
                const isChecked = checked.has(item.id);

                return (
                  <motion.div
                    key={item.id}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.02 }}
                  >
                    <button
                      onClick={() => toggle(item.id)}
                      className={cn(
                        'w-full flex items-start gap-3 p-3 rounded-xl text-left transition-colors',
                        isChecked
                          ? 'bg-emerald-500/10 border border-emerald-500/30'
                          : 'bg-white/5 border border-transparent hover:bg-white/10'
                      )}
                    >
                      {/* Checkbox */}
                      <div
                        className={cn(
                          'flex-shrink-0 w-5 h-5 rounded-md border-2 flex items-center justify-center transition-colors mt-0.5',
                          isChecked
                            ? 'bg-emerald-500 border-emerald-500'
                            : 'border-white/30'
                        )}
                      >
                        {isChecked && <Check className="w-3 h-3 text-white" />}
                      </div>

                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className={cn(
                            'font-medium transition-colors',
                            isChecked ? 'text-emerald-400 line-through opacity-70' : 'text-white'
                          )}>
                            {item.label}
                          </span>
                          {item.required && (
                            <span className="text-xs px-1.5 py-0.5 rounded bg-red-500/20 text-red-400">
                              Required
                            </span>
                          )}
                        </div>
                        {item.description && (
                          <p className={cn(
                            'text-sm mt-0.5 transition-colors',
                            isChecked ? 'text-white/30' : 'text-white/50'
                          )}>
                            {item.description}
                          </p>
                        )}
                      </div>
                    </button>
                  </motion.div>
                );
              })}
            </div>
          </div>
        ))}

        {/* All complete message */}
        {progress === 100 && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="p-4 rounded-xl bg-gradient-to-r from-emerald-500/20 to-teal-500/20 border border-emerald-500/30 text-center"
          >
            <div className="flex items-center justify-center gap-2 text-emerald-400">
              <Check className="w-5 h-5" />
              <span className="font-medium">All items completed!</span>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}
