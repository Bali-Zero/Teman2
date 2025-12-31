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
        <div className="h-8 bg-slate-200 rounded w-64"></div>
        <div className="h-48 bg-slate-200 rounded-xl"></div>
      </div>
    );
  }

  if (error || !taxData) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="w-12 h-12 text-red-500 mb-4" />
        <h2 className="text-lg font-medium text-slate-800 mb-2">Unable to load tax data</h2>
        <p className="text-slate-500 mb-4">{error || 'No tax information available'}</p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
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
      case 'filed': return 'bg-emerald-100 text-emerald-700';
      case 'attention':
      case 'pending': return 'bg-amber-100 text-amber-700';
      case 'overdue': return 'bg-red-100 text-red-700';
      default: return 'bg-slate-100 text-slate-700';
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-slate-800">Tax Overview</h1>
        <p className="text-slate-500 mt-1">Your tax obligations and filing status</p>
      </div>

      {/* Summary Card */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="p-6 border-b border-slate-100">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-4">
              <div className={`p-3 rounded-xl ${taxData.summary.status === 'compliant' ? 'bg-emerald-100' : taxData.summary.status === 'attention' ? 'bg-amber-100' : 'bg-red-100'}`}>
                <Receipt className={`w-6 h-6 ${taxData.summary.status === 'compliant' ? 'text-emerald-600' : taxData.summary.status === 'attention' ? 'text-amber-600' : 'text-red-600'}`} />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-slate-800">Tax Status</h2>
                <p className="text-sm text-slate-500">
                  {taxData.summary.nextDeadline
                    ? `Next deadline: ${taxData.summary.nextDeadline} (${taxData.summary.daysToDeadline} days)`
                    : 'No upcoming deadlines'}
                </p>
              </div>
            </div>
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusColor(taxData.summary.status)}`}>
              {taxData.summary.status === 'compliant' ? 'All Filed' : taxData.summary.status === 'attention' ? 'Action Needed' : 'Overdue'}
            </span>
          </div>
        </div>

        <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="p-4 bg-slate-50 rounded-lg">
            <div className="flex items-center gap-2 text-slate-500 mb-2">
              <TrendingUp className="w-4 h-4" />
              <span className="text-sm">Total Due</span>
            </div>
            <p className="text-2xl font-semibold text-slate-800">{formatCurrency(taxData.summary.totalDue)}</p>
          </div>
          <div className="p-4 bg-slate-50 rounded-lg">
            <div className="flex items-center gap-2 text-slate-500 mb-2">
              <Calendar className="w-4 h-4" />
              <span className="text-sm">Next Deadline</span>
            </div>
            <p className="text-2xl font-semibold text-slate-800">{taxData.summary.nextDeadline || '-'}</p>
          </div>
          <div className="p-4 bg-slate-50 rounded-lg">
            <div className="flex items-center gap-2 text-slate-500 mb-2">
              <Clock className="w-4 h-4" />
              <span className="text-sm">Days Remaining</span>
            </div>
            <p className={`text-2xl font-semibold ${taxData.summary.daysToDeadline !== null && taxData.summary.daysToDeadline <= 7 ? 'text-red-600' : taxData.summary.daysToDeadline !== null && taxData.summary.daysToDeadline <= 14 ? 'text-amber-600' : 'text-slate-800'}`}>
              {taxData.summary.daysToDeadline !== null ? `${taxData.summary.daysToDeadline} days` : '-'}
            </p>
          </div>
        </div>
      </div>

      {/* Upcoming Obligations */}
      <div>
        <h2 className="text-lg font-medium text-slate-800 mb-4">Upcoming Obligations</h2>
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
          {taxData.obligations.map((item) => (
            <div key={item.id} className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${item.status === 'filed' ? 'bg-emerald-100' : item.status === 'pending' ? 'bg-amber-100' : 'bg-red-100'}`}>
                  {item.status === 'filed' ? (
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  ) : item.status === 'pending' ? (
                    <Clock className="w-4 h-4 text-amber-600" />
                  ) : (
                    <AlertCircle className="w-4 h-4 text-red-600" />
                  )}
                </div>
                <div>
                  <p className="font-medium text-slate-800">{item.name}</p>
                  <p className="text-sm text-slate-500">{item.type} - {item.period}</p>
                </div>
              </div>
              <div className="text-right">
                <span className={`px-2 py-1 text-xs rounded-full ${getStatusColor(item.status)}`}>
                  {item.status}
                </span>
                {item.amount && (
                  <p className="text-sm text-slate-600 mt-1">{formatCurrency(item.amount)}</p>
                )}
                <p className="text-xs text-slate-500 mt-0.5">Due: {item.dueDate}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Filing History */}
      <div>
        <h2 className="text-lg font-medium text-slate-800 mb-4">Filing History</h2>
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
          {taxData.history.map((item) => (
            <div key={item.id} className="p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-emerald-100 rounded-lg">
                  <FileText className="w-4 h-4 text-emerald-600" />
                </div>
                <div>
                  <p className="font-medium text-slate-800">{item.name}</p>
                  <p className="text-sm text-slate-500">Filed: {item.filedDate}</p>
                </div>
              </div>
              <div className="text-right">
                <p className="font-medium text-slate-800">{formatCurrency(item.amount)}</p>
                <p className="text-xs text-slate-500">{item.period}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
