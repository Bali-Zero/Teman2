'use client';

import * as React from 'react';
import { useState, useMemo, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Calculator as CalculatorIcon,
  DollarSign,
  Info,
  Download,
  RefreshCw,
  ChevronDown,
  AlertCircle
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ============================================================================
// Types
// ============================================================================

export interface CalculatorField {
  id: string;
  label: string;
  type: 'number' | 'select' | 'checkbox' | 'slider';
  /** Description or help text */
  description?: string;
  /** Default value */
  defaultValue?: number | string | boolean;
  /** For number inputs */
  min?: number;
  max?: number;
  step?: number;
  /** For select inputs */
  options?: { value: string; label: string; multiplier?: number }[];
  /** Unit label (e.g., "IDR", "months") */
  unit?: string;
  /** If true, field affects the calculation */
  affectsResult?: boolean;
}

export interface CalculatorResult {
  label: string;
  value: number;
  format: 'currency' | 'number' | 'percentage';
  currency?: string;
  description?: string;
  isTotal?: boolean;
  highlight?: boolean;
}

export interface CalculatorProps {
  /** Unique ID */
  id: string;
  /** Title */
  title: string;
  /** Subtitle */
  subtitle?: string;
  /** Input fields */
  fields: CalculatorField[];
  /** Calculate function that returns results */
  calculate: (values: Record<string, number | string | boolean>) => CalculatorResult[];
  /** Show breakdown of costs */
  showBreakdown?: boolean;
  /** Allow PDF download */
  allowDownload?: boolean;
  /** Disclaimer text */
  disclaimer?: string;
  /** Custom class */
  className?: string;
}

// ============================================================================
// Format utilities
// ============================================================================

function formatValue(value: number, format: 'currency' | 'number' | 'percentage', currency = 'IDR'): string {
  if (format === 'currency') {
    if (currency === 'IDR') {
      return `Rp ${value.toLocaleString('id-ID')}`;
    }
    return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(value);
  }
  if (format === 'percentage') {
    return `${value.toFixed(1)}%`;
  }
  return value.toLocaleString();
}

// ============================================================================
// Main Component
// ============================================================================

export function Calculator({
  id,
  title,
  subtitle,
  fields,
  calculate,
  showBreakdown = true,
  allowDownload = false,
  disclaimer,
  className,
}: CalculatorProps) {
  // Initialize values from defaults
  const [values, setValues] = useState<Record<string, number | string | boolean>>(() => {
    const initial: Record<string, number | string | boolean> = {};
    fields.forEach((field) => {
      if (field.defaultValue !== undefined) {
        initial[field.id] = field.defaultValue;
      } else if (field.type === 'number' || field.type === 'slider') {
        initial[field.id] = field.min ?? 0;
      } else if (field.type === 'checkbox') {
        initial[field.id] = false;
      } else if (field.type === 'select' && field.options?.length) {
        initial[field.id] = field.options[0].value;
      }
    });
    return initial;
  });

  const [showResults, setShowResults] = useState(false);

  // Calculate results
  const results = useMemo(() => {
    try {
      return calculate(values);
    } catch {
      return [];
    }
  }, [values, calculate]);

  // Handle value change
  const handleChange = useCallback((fieldId: string, value: number | string | boolean) => {
    setValues((prev) => ({ ...prev, [fieldId]: value }));
    setShowResults(true);
  }, []);

  // Reset to defaults
  const handleReset = useCallback(() => {
    const initial: Record<string, number | string | boolean> = {};
    fields.forEach((field) => {
      if (field.defaultValue !== undefined) {
        initial[field.id] = field.defaultValue;
      } else if (field.type === 'number' || field.type === 'slider') {
        initial[field.id] = field.min ?? 0;
      } else if (field.type === 'checkbox') {
        initial[field.id] = false;
      } else if (field.type === 'select' && field.options?.length) {
        initial[field.id] = field.options[0].value;
      }
    });
    setValues(initial);
    setShowResults(false);
  }, [fields]);

  // Get total result
  const totalResult = results.find((r) => r.isTotal);
  const breakdownResults = results.filter((r) => !r.isTotal);

  return (
    <div className={cn('bg-black/40 rounded-2xl border border-white/10 overflow-hidden', className)}>
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/10 bg-gradient-to-r from-emerald-500/10 to-transparent">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-emerald-500/20 text-emerald-400">
              <CalculatorIcon className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-serif text-xl font-semibold text-white">{title}</h3>
              {subtitle && <p className="text-white/60 text-sm mt-0.5">{subtitle}</p>}
            </div>
          </div>
          <button
            onClick={handleReset}
            className="p-2 rounded-lg bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-colors"
            title="Reset"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="p-6">
        <div className="grid md:grid-cols-2 gap-8">
          {/* Input fields */}
          <div className="space-y-5">
            <h4 className="text-sm font-medium text-white/60 uppercase tracking-wider mb-4">
              Input Parameters
            </h4>
            {fields.map((field) => (
              <FieldInput
                key={field.id}
                field={field}
                value={values[field.id]}
                onChange={(v) => handleChange(field.id, v)}
              />
            ))}
          </div>

          {/* Results */}
          <div>
            <h4 className="text-sm font-medium text-white/60 uppercase tracking-wider mb-4">
              Estimated Costs
            </h4>

            {showResults && results.length > 0 ? (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-4"
              >
                {/* Breakdown */}
                {showBreakdown && breakdownResults.length > 0 && (
                  <div className="space-y-2">
                    {breakdownResults.map((result, index) => (
                      <motion.div
                        key={result.label}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: index * 0.05 }}
                        className={cn(
                          'flex items-center justify-between py-2 px-3 rounded-lg',
                          result.highlight ? 'bg-amber-500/10' : 'bg-white/5'
                        )}
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-white/70">{result.label}</span>
                          {result.description && (
                            <div className="group relative">
                              <Info className="w-3 h-3 text-white/30" />
                              <div className="absolute bottom-full left-0 mb-1 p-2 bg-black/90 rounded-lg text-xs text-white/60 opacity-0 group-hover:opacity-100 transition-opacity w-48 pointer-events-none">
                                {result.description}
                              </div>
                            </div>
                          )}
                        </div>
                        <span className={cn(
                          'font-mono',
                          result.highlight ? 'text-amber-400' : 'text-white'
                        )}>
                          {formatValue(result.value, result.format, result.currency)}
                        </span>
                      </motion.div>
                    ))}
                  </div>
                )}

                {/* Total */}
                {totalResult && (
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.2 }}
                    className="p-4 rounded-xl bg-gradient-to-r from-emerald-500/20 to-teal-500/20 border border-emerald-500/30"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-emerald-400/80 text-sm">{totalResult.label}</p>
                        {totalResult.description && (
                          <p className="text-white/50 text-xs mt-0.5">{totalResult.description}</p>
                        )}
                      </div>
                      <div className="text-right">
                        <p className="text-2xl font-bold text-emerald-400 font-mono">
                          {formatValue(totalResult.value, totalResult.format, totalResult.currency)}
                        </p>
                      </div>
                    </div>
                  </motion.div>
                )}

                {/* Actions */}
                {allowDownload && (
                  <button className="flex items-center gap-2 text-sm text-white/60 hover:text-white transition-colors">
                    <Download className="w-4 h-4" />
                    <span>Download estimate (PDF)</span>
                  </button>
                )}
              </motion.div>
            ) : (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <DollarSign className="w-12 h-12 text-white/10 mb-4" />
                <p className="text-white/40">
                  Adjust the parameters to see estimated costs
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Disclaimer */}
        {disclaimer && (
          <div className="mt-6 pt-4 border-t border-white/10">
            <div className="flex items-start gap-2 text-xs text-white/40">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <p>{disclaimer}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Field Input Component
// ============================================================================

function FieldInput({
  field,
  value,
  onChange,
}: {
  field: CalculatorField;
  value: number | string | boolean;
  onChange: (value: number | string | boolean) => void;
}) {
  const numValue = typeof value === 'number' ? value : 0;
  const strValue = typeof value === 'string' ? value : '';
  const boolValue = typeof value === 'boolean' ? value : false;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label className="text-sm font-medium text-white">{field.label}</label>
        {field.description && (
          <div className="group relative">
            <Info className="w-4 h-4 text-white/30 cursor-help" />
            <div className="absolute right-0 bottom-full mb-1 p-2 bg-black/90 rounded-lg text-xs text-white/60 opacity-0 group-hover:opacity-100 transition-opacity w-48 pointer-events-none z-10">
              {field.description}
            </div>
          </div>
        )}
      </div>

      {field.type === 'number' && (
        <div className="relative">
          <input
            type="number"
            value={numValue}
            onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
            min={field.min}
            max={field.max}
            step={field.step}
            className={cn(
              'w-full px-4 py-2.5 rounded-lg',
              'bg-white/5 border border-white/10',
              'text-white font-mono',
              'focus:outline-none focus:border-[#2251ff]/50 focus:ring-1 focus:ring-[#2251ff]/20',
              'transition-colors',
              field.unit && 'pr-16'
            )}
          />
          {field.unit && (
            <span className="absolute right-4 top-1/2 -translate-y-1/2 text-white/40 text-sm">
              {field.unit}
            </span>
          )}
        </div>
      )}

      {field.type === 'slider' && (
        <div className="space-y-2">
          <input
            type="range"
            value={numValue}
            onChange={(e) => onChange(parseFloat(e.target.value))}
            min={field.min ?? 0}
            max={field.max ?? 100}
            step={field.step ?? 1}
            className="w-full accent-[#2251ff]"
          />
          <div className="flex justify-between text-xs text-white/40">
            <span>{field.min ?? 0} {field.unit}</span>
            <span className="font-mono text-white">{numValue} {field.unit}</span>
            <span>{field.max ?? 100} {field.unit}</span>
          </div>
        </div>
      )}

      {field.type === 'select' && field.options && (
        <div className="relative">
          <select
            value={strValue}
            onChange={(e) => onChange(e.target.value)}
            className={cn(
              'w-full px-4 py-2.5 rounded-lg appearance-none',
              'bg-white/5 border border-white/10',
              'text-white',
              'focus:outline-none focus:border-[#2251ff]/50 focus:ring-1 focus:ring-[#2251ff]/20',
              'transition-colors cursor-pointer'
            )}
          >
            {field.options.map((option) => (
              <option key={option.value} value={option.value} className="bg-[#0a0a0a]">
                {option.label}
              </option>
            ))}
          </select>
          <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40 pointer-events-none" />
        </div>
      )}

      {field.type === 'checkbox' && (
        <label className="flex items-center gap-3 cursor-pointer group">
          <div
            className={cn(
              'w-5 h-5 rounded border flex items-center justify-center transition-colors',
              boolValue
                ? 'bg-[#2251ff] border-[#2251ff]'
                : 'bg-white/5 border-white/20 group-hover:border-white/40'
            )}
            onClick={() => onChange(!boolValue)}
          >
            {boolValue && (
              <svg className="w-3 h-3 text-white" viewBox="0 0 12 12" fill="none">
                <path d="M2 6L5 9L10 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </div>
          <span className="text-white/70 group-hover:text-white transition-colors">
            {field.description || 'Enable'}
          </span>
        </label>
      )}
    </div>
  );
}
