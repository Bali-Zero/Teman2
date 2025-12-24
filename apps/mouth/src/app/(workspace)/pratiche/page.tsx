'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { FolderKanban, Search, Filter, Plus, LayoutGrid, List } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import type { Practice } from '@/lib/api/crm/crm.types';

type CaseStatus = 'inquiry' | 'quotation' | 'in_progress' | 'completed';

export default function PratichePage() {
  const router = useRouter();
  const [practices, setPractices] = useState<Practice[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    const loadPractices = async () => {
      setIsLoading(true);
      try {
        const data = await api.crm.getPractices({ limit: 100 });
        setPractices(data);
      } catch (error) {
        console.error('Failed to load practices:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadPractices();
  }, []);

  const handleNewCase = () => {
    router.push('/pratiche/nuova');
  };

  const getStatusColumn = (status: string): CaseStatus => {
    if (status === 'inquiry' || status === 'request') return 'inquiry';
    if (status === 'quotation' || status === 'quote') return 'quotation';
    if (status === 'in_progress' || status === 'active') return 'in_progress';
    if (status === 'completed' || status === 'done') return 'completed';
    return 'inquiry';
  };

  const filteredPractices = searchQuery
    ? practices.filter(
        (p) =>
          p.id.toString().includes(searchQuery) ||
          p.client_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
          p.practice_type_code?.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : practices;

  const practicesByStatus = {
    inquiry: filteredPractices.filter((p) => getStatusColumn(p.status) === 'inquiry'),
    quotation: filteredPractices.filter((p) => getStatusColumn(p.status) === 'quotation'),
    in_progress: filteredPractices.filter((p) => getStatusColumn(p.status) === 'in_progress'),
    completed: filteredPractices.filter((p) => getStatusColumn(p.status) === 'completed'),
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">Cases</h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            Manage KITAS, Visa, PT PMA, Tax and other cases
          </p>
        </div>
        <Button className="gap-2" onClick={handleNewCase}>
          <Plus className="w-4 h-4" />
          New Case
        </Button>
      </div>

      {/* Search & Filter Bar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
          <input
            type="text"
            placeholder="Search cases by ID, client, type..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50"
          />
        </div>
        <div className="flex gap-2">
          <Button variant="outline" className="gap-2">
            <Filter className="w-4 h-4" />
            Filters
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

      {/* Kanban Board */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {(['Inquiry', 'Quotation', 'In Progress', 'Completed'] as const).map((column, idx) => {
          const statusKey = ['inquiry', 'quotation', 'in_progress', 'completed'][idx] as CaseStatus;
          const columnPractices = practicesByStatus[statusKey] || [];
          
          return (
            <div
              key={column}
              className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]/50 p-4"
            >
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-[var(--foreground)]">{column}</h3>
                <span className="text-xs px-2 py-1 rounded-full bg-[var(--background-elevated)] text-[var(--foreground-muted)]">
                  {columnPractices.length}
                </span>
              </div>
              <div className="min-h-[200px] space-y-2">
                {isLoading ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="animate-pulse text-xs text-[var(--foreground-muted)]">Loading...</div>
                  </div>
                ) : columnPractices.length === 0 ? (
                  <div className="flex items-center justify-center h-full border border-dashed border-[var(--border)] rounded-lg">
                    <p className="text-xs text-[var(--foreground-muted)]">No cases</p>
                  </div>
                ) : (
                  columnPractices.map((practice) => (
                    <div
                      key={practice.id}
                      className="p-3 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] hover:border-[var(--accent)]/30 cursor-pointer transition-colors"
                      onClick={() => router.push(`/pratiche/${practice.id}`)}
                    >
                      <p className="text-sm font-medium text-[var(--foreground)] truncate">
                        {practice.practice_type_code?.toUpperCase().replace(/_/g, ' ') || 'Case'}
                      </p>
                      <p className="text-xs text-[var(--foreground-muted)] truncate">
                        {practice.client_name || 'Unknown Client'}
                      </p>
                    </div>
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Info Box */}
      <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-8 text-center">
        <FolderKanban className="w-12 h-12 mx-auto text-[var(--foreground-muted)] mb-3 opacity-50" />
        <p className="text-sm text-[var(--foreground-muted)] max-w-md mx-auto">
          Kanban board to manage case status with drag & drop,
          automatic deadlines and notifications.
        </p>
      </div>
    </div>
  );
}
