'use client';

import React from 'react';
import { TrendingUp, TrendingDown, DollarSign, CreditCard, AlertCircle } from 'lucide-react';

interface FinancialRealityWidgetProps {
  revenue: {
    total_revenue: number;
    paid_revenue: number;
    outstanding_revenue: number;
  };
  growth: number;
}

export function FinancialRealityWidget({ revenue, growth }: FinancialRealityWidgetProps) {
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

  return (
    <div className="rounded-lg border border-white/10 bg-white/5 p-6 backdrop-blur-sm">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-white/90 uppercase tracking-wider">
          Financial Reality
        </h3>
        <div
          className={`flex items-center gap-1 ${isPositiveGrowth ? 'text-green-400' : 'text-red-400'}`}
        >
          {isPositiveGrowth ? (
            <TrendingUp className="w-4 h-4" />
          ) : (
            <TrendingDown className="w-4 h-4" />
          )}
          <span className="text-xs font-medium">{formatPercentage(growth)}</span>
        </div>
      </div>

      <div className="space-y-4">
        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <DollarSign className="w-4 h-4 text-green-500" />
              <span className="text-sm text-white/80">Total Revenue</span>
            </div>
            <span className="text-sm font-semibold text-white">
              {formatCurrency(revenue.total_revenue)}
            </span>
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <CreditCard className="w-4 h-4 text-blue-500" />
              <span className="text-sm text-white/80">Paid</span>
            </div>
            <span className="text-sm font-medium text-green-400">
              {formatCurrency(revenue.paid_revenue)}
            </span>
          </div>
          <div className="w-full bg-white/10 rounded-full h-1.5">
            <div
              className="bg-green-500 h-1.5 rounded-full transition-all"
              style={{ width: `${Math.min(paidPercentage, 100)}%` }}
            />
          </div>
          <p className="text-xs text-white/60 mt-1">{paidPercentage.toFixed(1)}% collected</p>
        </div>

        {revenue.outstanding_revenue > 0 && (
          <div className="flex items-start gap-2 p-3 rounded bg-yellow-500/10 border border-yellow-500/20">
            <AlertCircle className="w-4 h-4 text-yellow-500 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-xs font-medium text-yellow-500/90 mb-1">Outstanding</p>
              <p className="text-sm font-semibold text-yellow-400">
                {formatCurrency(revenue.outstanding_revenue)}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
