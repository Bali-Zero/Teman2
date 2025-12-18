'use client';

import React from 'react';
import { FolderKanban, Search, Filter, Plus, LayoutGrid, List } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function PratichePage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">Pratiche</h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            Gestione pratiche KITAS, Visa, PT PMA, Tax e altro
          </p>
        </div>
        <Button className="gap-2">
          <Plus className="w-4 h-4" />
          Nuova Pratica
        </Button>
      </div>

      {/* Search & Filter Bar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
          <input
            type="text"
            placeholder="Cerca pratiche per ID, cliente, tipo..."
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50"
          />
        </div>
        <div className="flex gap-2">
          <Button variant="outline" className="gap-2">
            <Filter className="w-4 h-4" />
            Filtri
          </Button>
          <div className="flex rounded-lg border border-[var(--border)] overflow-hidden">
            <button className="p-2 bg-[var(--accent)]/10 text-[var(--accent)]">
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button className="p-2 text-[var(--foreground-muted)] hover:bg-[var(--background-elevated)]">
              <List className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Kanban Placeholder */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {['Richiesta', 'Preventivo', 'In Corso', 'Completate'].map((column) => (
          <div
            key={column}
            className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]/50 p-4"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-[var(--foreground)]">{column}</h3>
              <span className="text-xs px-2 py-1 rounded-full bg-[var(--background-elevated)] text-[var(--foreground-muted)]">
                0
              </span>
            </div>
            <div className="min-h-[200px] flex items-center justify-center border border-dashed border-[var(--border)] rounded-lg">
              <p className="text-xs text-[var(--foreground-muted)]">
                Nessuna pratica
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* Info Box */}
      <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-8 text-center">
        <FolderKanban className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-3 opacity-50" />
        <p className="text-sm text-[var(--foreground-muted)] max-w-md mx-auto">
          Kanban board per gestire lo stato delle pratiche con drag & drop,
          scadenze automatiche e notifiche.
        </p>
      </div>
    </div>
  );
}
