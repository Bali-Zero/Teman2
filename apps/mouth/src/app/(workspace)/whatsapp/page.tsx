'use client';

import React from 'react';
import { MessageCircle, Search, Filter, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function WhatsAppPage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">WhatsApp Business</h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            Gestisci le conversazioni con i clienti
          </p>
        </div>
        <Button className="gap-2">
          <Plus className="w-4 h-4" />
          Nuova Chat
        </Button>
      </div>

      {/* Search & Filter Bar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
          <input
            type="text"
            placeholder="Cerca conversazioni..."
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
        <MessageCircle className="w-16 h-16 mx-auto text-[var(--foreground-muted)] mb-4 opacity-50" />
        <h2 className="text-lg font-semibold text-[var(--foreground)] mb-2">
          WhatsApp Business Integration
        </h2>
        <p className="text-sm text-[var(--foreground-muted)] max-w-md mx-auto mb-6">
          Questa sezione permetterà di gestire tutte le conversazioni WhatsApp,
          con suggerimenti AI di Zantara e collegamento automatico alle pratiche.
        </p>
        <div className="flex flex-wrap justify-center gap-2 text-xs text-[var(--foreground-muted)]">
          <span className="px-3 py-1 rounded-full bg-[var(--background-elevated)]">Chat in tempo reale</span>
          <span className="px-3 py-1 rounded-full bg-[var(--background-elevated)]">AI Suggestions</span>
          <span className="px-3 py-1 rounded-full bg-[var(--background-elevated)]">Auto-CRM</span>
          <span className="px-3 py-1 rounded-full bg-[var(--background-elevated)]">Template Messages</span>
        </div>
      </div>
    </div>
  );
}
