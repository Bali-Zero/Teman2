'use client';

import React from 'react';
import { Users, Search, Filter, Plus, UserPlus } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function ClientiPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">Clienti</h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            Gestione anagrafica clienti e contatti
          </p>
        </div>
        <Button className="gap-2">
          <UserPlus className="w-4 h-4" />
          Nuovo Cliente
        </Button>
      </div>

      {/* Search & Filter Bar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
          <input
            type="text"
            placeholder="Cerca clienti per nome, email, telefono..."
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50"
          />
        </div>
        <Button variant="outline" className="gap-2">
          <Filter className="w-4 h-4" />
          Filtri
        </Button>
      </div>

      {/* Placeholder Content */}
      <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-12 text-center">
        <Users className="w-16 h-16 mx-auto text-[var(--foreground-muted)] mb-4 opacity-50" />
        <h2 className="text-lg font-semibold text-[var(--foreground)] mb-2">
          CRM Clienti
        </h2>
        <p className="text-sm text-[var(--foreground-muted)] max-w-md mx-auto mb-6">
          Gestisci tutti i clienti Bali Zero con anagrafica completa,
          storico pratiche, documenti e comunicazioni.
        </p>
        <div className="flex flex-wrap justify-center gap-2 text-xs text-[var(--foreground-muted)]">
          <span className="px-3 py-1 rounded-full bg-[var(--background-elevated)]">Anagrafica</span>
          <span className="px-3 py-1 rounded-full bg-[var(--background-elevated)]">Documenti</span>
          <span className="px-3 py-1 rounded-full bg-[var(--background-elevated)]">Timeline</span>
          <span className="px-3 py-1 rounded-full bg-[var(--background-elevated)]">Note</span>
        </div>
      </div>
    </div>
  );
}
