'use client';

/**
 * Clients Page - CRM Workspace
 * 
 * Ottimizzata con:
 * - React Query per caching e sincronizzazione
 * - Virtualized list per grandi dataset
 * - Debounced search
 * - Error Boundary per resilienza
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  Users,
  Search,
  Filter,
  UserPlus,
  LayoutGrid,
  List,
  X,
  SortAsc,
  SortDesc,
  AlertCircle,
} from 'lucide-react';
import { useAutoAnimate } from '@formkit/auto-animate/react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import type { Client } from '@/lib/api/crm/crm.types';
import { CLIENT_STATUSES, COMMON_NATIONALITIES } from '@/lib/api/crm/crm.types';
import { ClientKanban } from '@/components/crm/ClientKanban';
import { ClientCard } from '@/components/crm/ClientCard';
import { CRMErrorBoundary, CRMSkeleton } from '@/components/crm';
import { useCrmClients, useCrmStats } from '@/hooks';
import { useDebounce } from '@/lib/hooks/optimized/useDebounce';
import { logger } from '@/lib/logger';

// Status badge styling
const STATUS_STYLES: Record<string, { bg: string; text: string }> = {
  lead: { bg: 'bg-blue-500/20', text: 'text-blue-400' },
  active: { bg: 'bg-green-500/20', text: 'text-green-400' },
  completed: { bg: 'bg-purple-500/20', text: 'text-purple-400' },
  lost: { bg: 'bg-red-500/20', text: 'text-red-400' },
  inactive: { bg: 'bg-gray-500/20', text: 'text-gray-400' },
};

type SortField = 'full_name' | 'created_at' | 'last_interaction_date' | 'status';
type SortOrder = 'asc' | 'desc';
type ViewMode = 'list' | 'kanban';

interface Filters {
  status: string;
  nationality: string;
  assigned_to: string;
}

const PAGE_SIZE = 200;
const ESTIMATED_CARD_HEIGHT = 200;
const VIRTUALIZATION_THRESHOLD = 30;
const SEARCH_DEBOUNCE_MS = 300;

/**
 * Virtualized client grid for better performance with large lists
 */
function VirtualizedClientGrid({
  clients,
  loadMoreRef,
  isLoadingMore,
  hasMore,
  totalClients,
  isMounted,
}: {
  clients: Client[];
  loadMoreRef: React.RefObject<HTMLDivElement | null>;
  isLoadingMore: boolean;
  hasMore: boolean;
  totalClients: number;
  isMounted: boolean;
}) {
  const parentRef = useRef<HTMLDivElement>(null);
  const shouldVirtualize = clients.length > VIRTUALIZATION_THRESHOLD;

  const [columns, setColumns] = useState(3);
  useEffect(() => {
    const updateColumns = () => {
      const width = window.innerWidth;
      if (width >= 1024) setColumns(3);
      else if (width >= 768) setColumns(2);
      else setColumns(1);
    };
    updateColumns();
    window.addEventListener('resize', updateColumns);
    return () => window.removeEventListener('resize', updateColumns);
  }, []);

  const rows = Math.ceil(clients.length / columns);
  const rowHeight = ESTIMATED_CARD_HEIGHT + 16;

  const virtualizer = useVirtualizer({
    count: rows,
    getScrollElement: () => parentRef.current,
    estimateSize: () => rowHeight,
    overscan: 2,
  });

  useEffect(() => {
    if (parentRef.current && shouldVirtualize) {
      virtualizer.measure();
    }
  }, [virtualizer, shouldVirtualize]);

  if (!shouldVirtualize) {
    return (
      <>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pb-4">
          {clients.map((client) => (
            <ClientCard key={client.id} client={client} />
          ))}
        </div>
        <div ref={loadMoreRef} className="h-10 flex items-center justify-center">
          {isLoadingMore && (
            <div className="flex items-center gap-2 text-sm text-[var(--foreground-muted)]">
              <div className="w-4 h-4 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
              Loading more clients...
            </div>
          )}
          {!hasMore && totalClients > PAGE_SIZE && (
            <span className="text-sm text-[var(--foreground-muted)]">
              All {isMounted ? totalClients.toLocaleString() : totalClients} clients loaded
            </span>
          )}
        </div>
      </>
    );
  }

  const virtualRows = virtualizer.getVirtualItems();

  return (
    <div ref={parentRef} className="flex-1 overflow-auto pb-4 min-h-[400px]">
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
        }}
      >
        {virtualRows.map((virtualRow) => {
          const startIndex = virtualRow.index * columns;
          const endIndex = Math.min(startIndex + columns, clients.length);
          const rowClients = clients.slice(startIndex, endIndex);

          return (
            <div
              key={virtualRow.key}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: `${virtualRow.size}px`,
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 px-1">
                {rowClients.map((client) => (
                  <ClientCard key={client.id} client={client} />
                ))}
                {rowClients.length < columns &&
                  Array.from({ length: columns - rowClients.length }).map((_, i) => (
                    <div key={`empty-${i}`} />
                  ))}
              </div>
            </div>
          );
        })}
      </div>
      <div ref={loadMoreRef} className="h-10 flex items-center justify-center">
        {isLoadingMore && (
          <div className="flex items-center gap-2 text-sm text-[var(--foreground-muted)]">
            <div className="w-4 h-4 border-2 border-[var(--accent)] border-t-transparent rounded-full animate-spin" />
            Loading more clients...
          </div>
        )}
        {!hasMore && totalClients > PAGE_SIZE && (
          <span className="text-sm text-[var(--foreground-muted)]">
            All {isMounted ? totalClients.toLocaleString() : totalClients} clients loaded
          </span>
        )}
      </div>
    </div>
  );
}

/**
 * Clients list content component
 */
function ClientsListContent() {
  const router = useRouter();
  const [listParent] = useAutoAnimate();
  const [searchQuery, setSearchQuery] = useState('');
  const debouncedSearch = useDebounce(searchQuery, SEARCH_DEBOUNCE_MS);
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<Filters>({
    status: '',
    nationality: '',
    assigned_to: '',
  });
  const [sortField, setSortField] = useState<SortField>('created_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [currentUserEmail, setCurrentUserEmail] = useState<string>('');
  const [profileLoaded, setProfileLoaded] = useState(false);
  const [isMounted, setIsMounted] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const loadMoreRef = useRef<HTMLDivElement>(null);

  // Load current user profile
  useEffect(() => {
    const loadProfile = () => {
      const profile = api.getUserProfile();
      if (profile?.email) {
        setCurrentUserEmail(profile.email);
        setProfileLoaded(true);
      }
    };
    loadProfile();
    const interval = setInterval(loadProfile, 500);
    const timeout = setTimeout(() => clearInterval(interval), 3000);
    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, []);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  // Use optimized CRM hook with caching
  const {
    clients,
    total,
    isLoading,
    isError,
    error,
    loadMore,
    hasMore,
    isLoadingMore,
  } = useCrmClients({
    status: filters.status || undefined,
    assigned_to: filters.assigned_to || undefined,
    search: debouncedSearch || undefined,
    limit: PAGE_SIZE,
  });

  // Stats hook
  const { data: stats } = useCrmStats();

  // Infinite scroll observer
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !isLoading && !isLoadingMore) {
          loadMore();
        }
      },
      { threshold: 0.1 }
    );

    if (loadMoreRef.current) {
      observer.observe(loadMoreRef.current);
    }

    return () => observer.disconnect();
  }, [hasMore, isLoading, isLoadingMore, loadMore]);

  // Handle status change
  const handleStatusChange = useCallback(async (clientId: number, newStatus: string) => {
    try {
      const currentUser = api.getUserProfile();
      await api.crm.updateClient(clientId, { status: newStatus }, currentUser?.email || 'system');
    } catch (error) {
      logger.error('Failed to update status:', {}, error as Error);
    }
  }, []);

  // Filtering
  const visibleClients = profileLoaded && isMounted ? clients : [];
  const uniqueAssignees = Array.from(
    new Set(visibleClients.map((c) => c.assigned_to).filter(Boolean))
  );

  const filteredClients = visibleClients
    .filter((client) => {
      if (filters.status && client.status !== filters.status) return false;
      if (filters.nationality && client.nationality !== filters.nationality) return false;
      if (filters.assigned_to && client.assigned_to !== filters.assigned_to) return false;
      return true;
    })
    .sort((a, b) => {
      let comparison = 0;
      switch (sortField) {
        case 'full_name':
          comparison = (a.full_name || '').localeCompare(b.full_name || '');
          break;
        case 'created_at':
          comparison = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
          break;
        case 'last_interaction_date':
          const aDate = a.last_interaction_date ? new Date(a.last_interaction_date).getTime() : 0;
          const bDate = b.last_interaction_date ? new Date(b.last_interaction_date).getTime() : 0;
          comparison = aDate - bDate;
          break;
        case 'status':
          comparison = (a.status || '').localeCompare(b.status || '');
          break;
      }
      return sortOrder === 'asc' ? comparison : -comparison;
    });

  const handleNewClient = () => {
    router.push('/clients/new');
  };

  const clearFilters = () => {
    setFilters({ status: '', nationality: '', assigned_to: '' });
  };

  const activeFiltersCount = Object.values(filters).filter(Boolean).length;

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  // Error state
  if (isError) {
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 dark:bg-red-950/20 dark:border-red-900 p-8 text-center">
        <AlertCircle className="w-12 h-12 mx-auto text-red-500 mb-4" />
        <h2 className="text-lg font-semibold text-red-900 dark:text-red-100 mb-2">
          Error loading clients
        </h2>
        <p className="text-sm text-red-600 dark:text-red-300 mb-4">
          {error instanceof Error ? error.message : 'An unexpected error occurred'}
        </p>
        <Button onClick={() => window.location.reload()} variant="outline">
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6 h-full flex flex-col">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">Clients</h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            {isMounted ? filteredClients.length.toLocaleString() : filteredClients.length} client
            {filteredClients.length !== 1 ? 's' : ''}
            {hasMore && ' (scroll for more)'}
            {activeFiltersCount > 0 &&
              ` • filtered from ${isMounted ? visibleClients.length.toLocaleString() : visibleClients.length}`}
            {stats && (
              <span className="ml-2 text-xs">
                • {stats.totalClients} total
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* View Toggle */}
          <div className="bg-[var(--background-secondary)] p-1 rounded-lg border border-[var(--border)] flex">
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 rounded-md transition-all ${viewMode === 'list' ? 'bg-[var(--background-elevated)] shadow-sm text-[var(--foreground)]' : 'text-[var(--foreground-muted)] hover:text-[var(--foreground)]'}`}
              title="List View"
            >
              <List className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('kanban')}
              className={`p-2 rounded-md transition-all ${viewMode === 'kanban' ? 'bg-[var(--background-elevated)] shadow-sm text-[var(--foreground)]' : 'text-[var(--foreground-muted)] hover:text-[var(--foreground)]'}`}
              title="Kanban Board"
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
          </div>

          <Button className="gap-2" onClick={handleNewClient}>
            <UserPlus className="w-4 h-4" />
            New Client
          </Button>
        </div>
      </div>

      {/* Controls Row */}
      <div className="flex flex-col gap-3">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
            <input
              type="text"
              placeholder="Search clients..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--foreground-muted)] hover:text-[var(--foreground)]"
              >
                <X className="w-4 h-4" />
              </button>
            )}
          </div>
          <Button
            variant={showFilters ? 'default' : 'outline'}
            className="gap-2"
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter className="w-4 h-4" />
            Filters
            {activeFiltersCount > 0 && (
              <span className="ml-1 px-1.5 py-0.5 text-xs rounded-full bg-[var(--accent)] text-white">
                {activeFiltersCount}
              </span>
            )}
          </Button>
        </div>

        {/* Expanded Filters Panel */}
        {showFilters && (
          <div className="p-4 rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-medium text-[var(--foreground)]">Filters</h3>
              {activeFiltersCount > 0 && (
                <button
                  onClick={clearFilters}
                  className="text-sm text-[var(--accent)] hover:underline flex items-center gap-1"
                >
                  <X className="w-3 h-3" />
                  Clear all
                </button>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-1.5">
                  Status
                </label>
                <select
                  value={filters.status}
                  onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50"
                >
                  <option value="">All statuses</option>
                  {CLIENT_STATUSES.map(({ value, label }) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-1.5">
                  Nationality
                </label>
                <select
                  value={filters.nationality}
                  onChange={(e) => setFilters({ ...filters, nationality: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50"
                >
                  <option value="">All nationalities</option>
                  {COMMON_NATIONALITIES.map((nat) => (
                    <option key={nat} value={nat}>
                      {nat}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-1.5">
                  Assigned To
                </label>
                <select
                  value={filters.assigned_to}
                  onChange={(e) => setFilters({ ...filters, assigned_to: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50"
                >
                  <option value="">All team members</option>
                  {uniqueAssignees.map((assignee) => (
                    <option key={assignee} value={assignee}>
                      {assignee?.split('@')[0]}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Sorting (List View Only) */}
      {viewMode === 'list' && (
        <div className="flex items-center gap-2 text-sm">
          <span className="text-[var(--foreground-muted)]">Sort by:</span>
          <div className="flex gap-1">
            {[
              { field: 'created_at' as SortField, label: 'Created' },
              { field: 'full_name' as SortField, label: 'Name' },
              { field: 'last_interaction_date' as SortField, label: 'Last Contact' },
              { field: 'status' as SortField, label: 'Status' },
            ].map(({ field, label }) => (
              <button
                key={field}
                onClick={() => toggleSort(field)}
                className={`px-3 py-1 rounded-full flex items-center gap-1 transition-colors ${
                  sortField === field
                    ? 'bg-[var(--accent)]/20 text-[var(--accent)]'
                    : 'bg-[var(--background-secondary)] text-[var(--foreground-muted)] hover:bg-[var(--background-elevated)]'
                }`}
              >
                {label}
                {sortField === field &&
                  (sortOrder === 'asc' ? (
                    <SortAsc className="w-3 h-3" />
                  ) : (
                    <SortDesc className="w-3 h-3" />
                  ))}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* CONTENT AREA */}
      {isLoading && !clients.length ? (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-12 text-center">
          <CRMSkeleton count={6} />
        </div>
      ) : filteredClients.length > 0 ? (
        <div className="flex-1 overflow-auto">
          {viewMode === 'list' ? (
            <VirtualizedClientGrid
              clients={filteredClients}
              loadMoreRef={loadMoreRef}
              isLoadingMore={isLoadingMore}
              hasMore={hasMore}
              totalClients={clients.length}
              isMounted={isMounted}
            />
          ) : (
            <ClientKanban clients={filteredClients} onStatusChange={handleStatusChange} />
          )}
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-12 text-center">
          <Users className="w-16 h-16 mx-auto text-[var(--foreground-muted)] mb-4 opacity-50" />
          <h2 className="text-lg font-semibold text-[var(--foreground)] mb-2">No clients found</h2>
          <p className="text-sm text-[var(--foreground-muted)] max-w-md mx-auto mb-6">
            {searchQuery 
              ? 'No clients match your search. Try different keywords.'
              : activeFiltersCount > 0
              ? 'No clients match the selected filters.'
              : 'Get started by adding your first client.'}
          </p>
          {activeFiltersCount > 0 ? (
            <Button variant="outline" onClick={clearFilters} className="gap-2">
              <X className="w-4 h-4" />
              Clear Filters
            </Button>
          ) : (
            <Button onClick={handleNewClient} className="gap-2">
              <UserPlus className="w-4 h-4" />
              Add First Client
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Main page component with error boundary
 */
export default function ClientiPage() {
  return (
    <CRMErrorBoundary section="Clients">
      <ClientsListContent />
    </CRMErrorBoundary>
  );
}
