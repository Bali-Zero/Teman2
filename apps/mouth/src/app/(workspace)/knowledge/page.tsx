'use client';

import React from 'react';
import { BookOpen, Search, Filter, Plus, FileText, FolderOpen, Tag } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function KnowledgePage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">Knowledge Base</h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            Documenti, procedure e informazioni aziendali
          </p>
        </div>
        <Button className="gap-2">
          <Plus className="w-4 h-4" />
          Nuovo Documento
        </Button>
      </div>

      {/* Search Bar */}
      <div className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-[var(--foreground-muted)]" />
        <input
          type="text"
          placeholder="Cerca nella knowledge base..."
          className="w-full pl-12 pr-4 py-3 rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 text-lg"
        />
      </div>

      {/* Categories */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { name: 'KITAS & Visa', icon: FileText, count: 0 },
          { name: 'PT PMA', icon: FolderOpen, count: 0 },
          { name: 'Tax & NPWP', icon: FileText, count: 0 },
          { name: 'Procedure', icon: Tag, count: 0 },
        ].map((category) => (
          <div
            key={category.name}
            className="p-4 rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] hover:bg-[var(--background-elevated)]/50 cursor-pointer transition-colors"
          >
            <category.icon className="w-8 h-8 text-[var(--accent)] mb-3" />
            <h3 className="font-medium text-[var(--foreground)]">{category.name}</h3>
            <p className="text-xs text-[var(--foreground-muted)]">{category.count} documenti</p>
          </div>
        ))}
      </div>

      {/* Recent Documents Placeholder */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]">
        <div className="p-4 border-b border-[var(--border)]">
          <h2 className="font-semibold text-[var(--foreground)]">Documenti Recenti</h2>
        </div>
        <div className="p-8 text-center">
          <BookOpen className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-3 opacity-50" />
          <p className="text-sm text-[var(--foreground-muted)]">
            Nessun documento recente
          </p>
        </div>
      </div>

      {/* Info Box */}
      <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-8 text-center">
        <p className="text-sm text-[var(--foreground-muted)] max-w-md mx-auto">
          La Knowledge Base contiene tutti i documenti aziendali, procedure operative,
          template e informazioni legali/fiscali per l&apos;Indonesia.
          Integrata con Zantara AI per ricerca semantica.
        </p>
      </div>
    </div>
  );
}
