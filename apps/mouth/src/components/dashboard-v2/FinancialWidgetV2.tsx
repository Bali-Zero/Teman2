'use client';

import React from 'react';
import { TrendingUp, TrendingDown, DollarSign, CreditCard, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface FinancialWidgetV2Props {
  revenue: {
    total_revenue: number;
    paid_revenue: number;
    outstanding_revenue: number;
  };
  growth: number;
}

/**
 * FinancialWidgetV2 - Improved financial widget with:
 * - Full CSS variables (no hardcoded colors)
 * - Accessible progress bar with proper ARIA
 * - Consistent with Design System v2.0
 */
export function FinancialWidgetV2({ revenue, growth }: Readonly<FinancialWidgetV2Props>) {
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const formatPercentage = (value: number) => {
    const sign = value >= 0 ? '+' : '';
    return `${sign}${value.toFixed(1)}%`;
  };

  const isPositiveGrowth = growth >= 0;
  const paidPercentage =
    revenue.total_revenue > 0 ? (revenue.paid_revenue / revenue.total_revenue) * 100 : 0;
  const progressWidthPercent = Math.min(paidPercentage, 100);

  return (
    <div
      className={cn(
        'rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-6',
        'transition-all duration-[var(--transition-normal)]',
        'hover:border-[var(--border-hover)]'
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-[var(--foreground)] uppercase tracking-wider">
          Financial Reality
        </h3>
        <div
          className={cn(
            'flex items-center gap-1',
            isPositiveGrowth ? 'text-[var(--success)]' : 'text-[var(--error)]'
          )}
          aria-label={`Growth: ${formatPercentage(growth)}`}
        >
          {isPositiveGrowth ? (
            <TrendingUp className="w-4 h-4" aria-hidden="true" />
          ) : (
            <TrendingDown className="w-4 h-4" aria-hidden="true" />
          )}
          <span className="text-xs font-medium">{formatPercentage(growth)}</span>
        </div>
      </div>

      <div className="space-y-4">
        {/* Total Revenue */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <DollarSign className="w-4 h-4 text-[var(--success)]" aria-hidden="true" />
              <span className="text-sm text-[var(--foreground-secondary)]">Total Revenue</span>
            </div>
            <span className="text-sm font-semibold text-[var(--foreground)]">
              {formatCurrency(revenue.total_revenue)}
            </span>
          </div>
        </div>

        {/* Paid Revenue with Progress Bar */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <CreditCard className="w-4 h-4 text-[var(--info)]" aria-hidden="true" />
              <span className="text-sm text-[var(--foreground-secondary)]">Paid</span>
            </div>
            <span className="text-sm font-medium text-[var(--success)]">
              {formatCurrency(revenue.paid_revenue)}
            </span>
          </div>

          {/* Accessible Progress Bar */}
          <div
            className="w-full bg-[var(--background-elevated)] rounded-full h-2 overflow-hidden"
            role="progressbar"
            aria-valuenow={Math.round(paidPercentage)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`${paidPercentage.toFixed(1)}% collected`}
          >
            <div
              className="h-full bg-[var(--success)] rounded-full transition-all duration-500"
              style={{ width: `${progressWidthPercent}%` }}
            />
          </div>
          <p className="text-xs text-[var(--foreground-muted)] mt-1">
            {paidPercentage.toFixed(1)}% collected
          </p>
        </div>

        {/* Outstanding Alert */}
        {revenue.outstanding_revenue > 0 && (
          <div
            className={cn(
              'flex items-start gap-2 p-3 rounded-lg',
              'bg-[var(--warning-muted)] border border-[var(--warning)]/30'
            )}
            role="alert"
          >
            <AlertCircle
              className="w-4 h-4 text-[var(--warning)] mt-0.5 flex-shrink-0"
              aria-hidden="true"
            />
            <div className="flex-1">
              <p className="text-xs font-medium text-[var(--warning)] mb-1">Outstanding</p>
              <p className="text-sm font-semibold text-[var(--warning)]">
                {formatCurrency(revenue.outstanding_revenue)}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default FinancialWidgetV2;
