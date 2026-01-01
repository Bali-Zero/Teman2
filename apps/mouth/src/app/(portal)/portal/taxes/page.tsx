'use client';

import React, { useState, useEffect } from 'react';
import {
  Receipt,
  Calendar,
  AlertCircle,
  CheckCircle2,
  Clock,
  FileText,
  TrendingUp,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { TaxOverview } from '@/lib/api/portal/portal.types';

export default function TaxesPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [taxData, setTaxData] = useState<TaxOverview | null>(null);

  useEffect(() => {
    const loadData = async () => {
      try {
        setIsLoading(true);
        setError(null);
        const data = await api.portal.getTaxOverview();
        setTaxData(data);
      } catch (err) {
        console.error('Failed to load tax data:', err);
        setError('Unable to load tax information. Please try again.');
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, []);

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-[#1A1D24] rounded w-64"></div>
        <div className="h-48 bg-[#1A1D24] rounded-xl"></div>
      </div>
    );
  }

  if (error || !taxData) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="w-12 h-12 text-red-400 mb-4" />
        <h2 className="text-lg font-medium text-[#E6E7EB] mb-2">Unable to load tax data</h2>
        <p className="text-[#9AA0AE] mb-4">{error || 'No tax information available'}</p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 bg-[#4FD1C5] text-[#0B0E13] font-medium rounded-lg hover:bg-[#38B2AC] transition-colors"
        >
          Try Again
        </button>
      </div>
    );
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      minimumFractionDigits: 0,
    }).format(amount);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'compliant':
      case 'filed': return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      case 'attention':
      case 'pending': return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
      case 'overdue': return 'bg-red-500/10 text-red-400 border-red-500/20';
      default: return 'bg-[#1A1D24] text-[#9AA0AE] border-white/10';
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-[#E6E7EB]">Tax Overview</h1>
        <p className="text-[#9AA0AE] mt-1">Your tax obligations and filing status</p>
      </div>

      {/* Summary Card */}
      <div className="bg-[#1A1D24] rounded-xl border border-white/5 overflow-hidden">
        <div className="p-6 border-b border-white/5">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-4">
              <div className={`p-3 rounded-xl ${taxData.summary.status === 'compliant' ? 'bg-emerald-500/10' : taxData.summary.status === 'attention' ? 'bg-amber-500/10' : 'bg-red-500/10'}`}>
                <Receipt className={`w-6 h-6 ${taxData.summary.status === 'compliant' ? 'text-emerald-400' : taxData.summary.status === 'attention' ? 'text-amber-400' : 'text-red-400'}`} />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-[#E6E7EB]">Tax Status</h2>
                <p className="text-sm text-[#9AA0AE]">
                  {taxData.summary.nextDeadline
                    ? `Next deadline: ${taxData.summary.nextDeadline} (${taxData.summary.daysToDeadline} days)`
                    : 'No upcoming deadlines'}
                </p>
              </div>
            </div>
            <span className={`px-3 py-1 rounded-full text-sm font-medium border ${getStatusColor(taxData.summary.status)}`}>
              {taxData.summary.status === 'compliant' ? 'All Filed' : taxData.summary.status === 'attention' ? 'Action Needed' : 'Overdue'}
            </span>
          </div>
        </div>

        <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="p-4 bg-[#2a2a2a] rounded-lg">
            <div className="flex items-center gap-2 text-[#9AA0AE] mb-2">
              <TrendingUp className="w-4 h-4" />
              <span className="text-sm">Total Due</span>
            </div>
            <p className="text-2xl font-semibold text-[#E6E7EB]">{formatCurrency(taxData.summary.totalDue)}</p>
          </div>
          <div className="p-4 bg-[#2a2a2a] rounded-lg">
            <div className="flex items-center gap-2 text-[#9AA0AE] mb-2">
              <Calendar className="w-4 h-4" />
              <span className="text-sm">Next Deadline</span>
            </div>
            <p className="text-2xl font-semibold text-[#E6E7EB]">{taxData.summary.nextDeadline || '-'}</p>
          </div>
          <div className="p-4 bg-[#2a2a2a] rounded-lg">
            <div className="flex items-center gap-2 text-[#9AA0AE] mb-2">
              <Clock className="w-4 h-4" />
              <span className="text-sm">Days Remaining</span>
            </div>
            <p className={`text-2xl font-semibold ${taxData.summary.daysToDeadline !== null && taxData.summary.daysToDeadline <= 7 ? 'text-red-400' : taxData.summary.daysToDeadline !== null && taxData.summary.daysToDeadline <= 14 ? 'text-amber-400' : 'text-[#E6E7EB]'}`}>
              {taxData.summary.daysToDeadline !== null ? `${taxData.summary.daysToDeadline} days` : '-'}
            </p>
          </div>
        </div>
      </div>

      {/* Upcoming Obligations */}
      {taxData.obligations.length > 0 && (
        <div>
          <h2 className="text-lg font-medium text-[#E6E7EB] mb-4">Upcoming Obligations</h2>
          <div className="bg-[#1A1D24] rounded-xl border border-white/5 divide-y divide-white/5">
            {taxData.obligations.map((item) => (
              <div key={item.id} className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${item.status === 'filed' ? 'bg-emerald-500/10' : item.status === 'pending' ? 'bg-amber-500/10' : 'bg-red-500/10'}`}>
                    {item.status === 'filed' ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    ) : item.status === 'pending' ? (
                      <Clock className="w-4 h-4 text-amber-400" />
                    ) : (
                      <AlertCircle className="w-4 h-4 text-red-400" />
                    )}
                  </div>
                  <div>
                    <p className="font-medium text-[#E6E7EB]">{item.name}</p>
                    <p className="text-sm text-[#9AA0AE]">{item.type} - {item.period}</p>
                  </div>
                </div>
                <div className="text-right">
                  <span className={`px-2 py-1 text-xs rounded-full border ${getStatusColor(item.status)}`}>
                    {item.status}
                  </span>
                  {item.amount && (
                    <p className="text-sm text-[#E6E7EB] mt-1">{formatCurrency(item.amount)}</p>
                  )}
                  <p className="text-xs text-[#9AA0AE] mt-0.5">Due: {item.dueDate}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state for obligations */}
      {taxData.obligations.length === 0 && (
        <div>
          <h2 className="text-lg font-medium text-[#E6E7EB] mb-4">Upcoming Obligations</h2>
          <div className="bg-[#1A1D24] rounded-xl border border-white/5 p-8 text-center">
            <Calendar className="w-12 h-12 text-[#9AA0AE] mx-auto mb-4" />
            <h3 className="font-medium text-[#E6E7EB]">No Upcoming Obligations</h3>
            <p className="text-sm text-[#9AA0AE] mt-1">Your tax obligations will appear here</p>
          </div>
        </div>
      )}

      {/* Filing History */}
      {taxData.history.length > 0 && (
        <div>
          <h2 className="text-lg font-medium text-[#E6E7EB] mb-4">Filing History</h2>
          <div className="bg-[#1A1D24] rounded-xl border border-white/5 divide-y divide-white/5">
            {taxData.history.map((item) => (
              <div key={item.id} className="p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-emerald-500/10 rounded-lg">
                    <FileText className="w-4 h-4 text-emerald-400" />
                  </div>
                  <div>
                    <p className="font-medium text-[#E6E7EB]">{item.name}</p>
                    <p className="text-sm text-[#9AA0AE]">Filed: {item.filedDate}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-medium text-[#E6E7EB]">{formatCurrency(item.amount)}</p>
                  <p className="text-xs text-[#9AA0AE]">{item.period}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state for history */}
      {taxData.history.length === 0 && (
        <div>
          <h2 className="text-lg font-medium text-[#E6E7EB] mb-4">Filing History</h2>
          <div className="bg-[#1A1D24] rounded-xl border border-white/5 p-8 text-center">
            <FileText className="w-12 h-12 text-[#9AA0AE] mx-auto mb-4" />
            <h3 className="font-medium text-[#E6E7EB]">No Filing History</h3>
            <p className="text-sm text-[#9AA0AE] mt-1">Your tax filing history will appear here</p>
          </div>
        </div>
      )}
    </div>
  );
}
