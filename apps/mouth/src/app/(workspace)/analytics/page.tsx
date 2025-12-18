'use client';

import React from 'react';
import { BarChart3, TrendingUp, Users, FolderKanban, DollarSign } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function AnalyticsPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">Analytics</h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            Report e statistiche aziendali
          </p>
        </div>
        <div className="flex gap-2">
          <select className="px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] text-[var(--foreground)] text-sm">
            <option>Ultimi 7 giorni</option>
            <option>Ultimi 30 giorni</option>
            <option>Questo mese</option>
            <option>Questo anno</option>
          </select>
          <Button variant="outline">Esporta</Button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Pratiche Totali', value: '0', icon: FolderKanban, trend: null },
          { label: 'Nuovi Clienti', value: '0', icon: Users, trend: null },
          { label: 'Revenue', value: '€0', icon: DollarSign, trend: null },
          { label: 'Conversion Rate', value: '0%', icon: TrendingUp, trend: null },
        ].map((kpi) => (
          <div
            key={kpi.label}
            className="p-4 rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]"
          >
            <div className="flex items-center justify-between mb-2">
              <p className="text-sm text-[var(--foreground-muted)]">{kpi.label}</p>
              <kpi.icon className="w-4 h-4 text-[var(--foreground-muted)]" />
            </div>
            <p className="text-2xl font-bold text-[var(--foreground)]">{kpi.value}</p>
            {kpi.trend && (
              <p className="text-xs text-[var(--success)] mt-1">{kpi.trend}</p>
            )}
          </div>
        ))}
      </div>

      {/* Charts Placeholder */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Pratiche Chart */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-4">
          <h3 className="font-semibold text-[var(--foreground)] mb-4">Pratiche per Tipo</h3>
          <div className="h-64 flex items-center justify-center border border-dashed border-[var(--border)] rounded-lg">
            <div className="text-center">
              <BarChart3 className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-2 opacity-50" />
              <p className="text-sm text-[var(--foreground-muted)]">Grafico pratiche</p>
            </div>
          </div>
        </div>

        {/* Revenue Chart */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-4">
          <h3 className="font-semibold text-[var(--foreground)] mb-4">Revenue Trend</h3>
          <div className="h-64 flex items-center justify-center border border-dashed border-[var(--border)] rounded-lg">
            <div className="text-center">
              <TrendingUp className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-2 opacity-50" />
              <p className="text-sm text-[var(--foreground-muted)]">Grafico revenue</p>
            </div>
          </div>
        </div>
      </div>

      {/* More Analytics Placeholder */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Team Performance */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-4">
          <h3 className="font-semibold text-[var(--foreground)] mb-4">Performance Team</h3>
          <div className="space-y-3">
            <p className="text-sm text-[var(--foreground-muted)] text-center py-8">
              Dati non disponibili
            </p>
          </div>
        </div>

        {/* Top Clients */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-4">
          <h3 className="font-semibold text-[var(--foreground)] mb-4">Top Clienti</h3>
          <div className="space-y-3">
            <p className="text-sm text-[var(--foreground-muted)] text-center py-8">
              Dati non disponibili
            </p>
          </div>
        </div>

        {/* Service Distribution */}
        <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-4">
          <h3 className="font-semibold text-[var(--foreground)] mb-4">Servizi Richiesti</h3>
          <div className="space-y-3">
            <p className="text-sm text-[var(--foreground-muted)] text-center py-8">
              Dati non disponibili
            </p>
          </div>
        </div>
      </div>

      {/* Info Box */}
      <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-8 text-center">
        <p className="text-sm text-[var(--foreground-muted)] max-w-md mx-auto">
          Dashboard analytics con report su pratiche, clienti, revenue e performance del team.
          Export in PDF/Excel disponibile.
        </p>
      </div>
    </div>
  );
}
