'use client';

import React, { useEffect, useState } from 'react';
import { CheckCircle, Clock, Gift } from 'lucide-react';
import * as hrApi from '@/lib/api/hr/hr';

function formatIDR(amount: number): string {
  return new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 }).format(amount);
}

const statusColors: Record<string, string> = {
  pending: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  approved: 'bg-blue-500/10 text-blue-400 border-blue-500/30',
  paid: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  rejected: 'bg-red-500/10 text-red-400 border-red-500/30',
  reversed: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/30',
};

export default function BonusesPage() {
  const [bonuses, setBonuses] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    hrApi.listBonuses().then(data => {
      setBonuses(data.bonuses || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  const handleApprove = async (id: number) => {
    try {
      await hrApi.approveBonus(id);
      setBonuses(prev => prev.map(b => b.id === id ? { ...b, status: 'approved' } : b));
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to approve');
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-zinc-100">Bonuses</h1>
        <div className="animate-pulse space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 bg-zinc-900 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-zinc-100">Bonuses</h1>
        <div className="flex items-center gap-2 text-sm text-zinc-400">
          <Gift size={16} />
          {bonuses.length} total
        </div>
      </div>

      {bonuses.length === 0 ? (
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center text-zinc-500">
          No bonuses yet. Bonuses are automatically created when practices are completed.
        </div>
      ) : (
        <div className="space-y-2">
          {bonuses.map((bonus) => (
            <div
              key={bonus.id}
              className="bg-zinc-900 border border-zinc-800 rounded-lg p-4 flex items-center justify-between"
            >
              <div className="flex-1">
                <div className="flex items-center gap-3">
                  <span className="font-medium text-zinc-200">
                    {bonus.practice_type_code?.replace(/_/g, ' ')}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded-full border ${statusColors[bonus.status] || ''}`}>
                    {bonus.status}
                  </span>
                </div>
                <div className="text-sm text-zinc-500 mt-1">
                  {bonus.employee_name || bonus.employee_email}
                  {bonus.client_name && ` — ${bonus.client_name}`}
                  {' · '}
                  {new Date(bonus.awarded_at).toLocaleDateString('id-ID')}
                </div>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-lg font-semibold text-[var(--bz-accent)]">
                  {formatIDR(bonus.amount_idr)}
                </span>
                {bonus.status === 'pending' && (
                  <button
                    onClick={() => handleApprove(bonus.id)}
                    className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 text-sm transition-colors"
                  >
                    <CheckCircle size={14} />
                    Approve
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
