'use client';

import React, { useState, useEffect } from 'react';
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
} from 'lucide-react';
import { useAutoAnimate } from '@formkit/auto-animate/react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import type { Client } from '@/lib/api/crm/crm.types';
import { CLIENT_STATUSES, COMMON_NATIONALITIES } from '@/lib/api/crm/crm.types';
import { ClientKanban } from '@/components/crm/ClientKanban';
import { ClientCard } from '@/components/crm/ClientCard';

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

// ============================================
// ACCESS CONTROL RULES
// ============================================
// ZERO: can see ALL contacts
// RUSLANA: can see own + Anton, Rina, Dea's contacts
// OTHER MEMBERS: can only see their OWN contacts
// ============================================

const ACCESS_RULES = {
  // Users who can see ALL contacts
  superAdmins: ['zero'],
  // Ruslana can see her contacts + these team members' contacts
  ruslanaCanSee: ['ruslana', 'anton', 'rina', 'dea'],
};

function getVisibleClients(clients: Client[], currentUserEmail: string): Client[] {
  const emailLower = currentUserEmail.toLowerCase();
  const userName = emailLower.split('@')[0];

  // ZERO can see all
  if (ACCESS_RULES.superAdmins.includes(userName)) {
    return clients;
  }

  // RUSLANA can see her contacts + Anton, Rina, Dea
  if (userName === 'ruslana') {
    return clients.filter((client) => {
      if (!client.assigned_to) return true; // Unassigned visible to Ruslana
      const assignedTo = client.assigned_to.toLowerCase().split('@')[0];
      return ACCESS_RULES.ruslanaCanSee.includes(assignedTo);
    });
  }

  // Other members can only see their own contacts
  return clients.filter((client) => {
    if (!client.assigned_to) return false; // Unassigned not visible
    const assignedTo = client.assigned_to.toLowerCase().split('@')[0];
    return assignedTo === userName;
  });
}

export default function ClientiPage() {
  const router = useRouter();
  const [clients, setClients] = useState<Client[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [listParent] = useAutoAnimate();
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
  const [viewMode, setViewMode] = useState<ViewMode>('list');

  // Load current user profile for access control
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

  const loadClients = async () => {
    setIsLoading(true);
    try {
      const data = await api.crm.getClients({ search: searchQuery || undefined });
      setClients(data);
    } catch (error) {
      console.error('Failed to load clients:', error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    const debounceTimer = setTimeout(loadClients, searchQuery ? 300 : 0);
    return () => clearTimeout(debounceTimer);
  }, [searchQuery]);

  // Handle status change (e.g. from Kanban)
  const handleStatusChange = async (clientId: number, newStatus: string) => {
    // Optimistic update
    setClients(prev => prev.map(c =>
      c.id === clientId ? { ...c, status: newStatus as Client['status'] } : c
    ));

    try {
      // Assuming we have an updateClient method, otherwise we need to use PATCH endpoint
      // NOTE: crm.api.ts needs updateClient or patch support
      const currentUser = api.getUserProfile();
      await api.crm.updateClient(clientId, { status: newStatus }, currentUser?.email || 'system');
    } catch (error) {
      console.error('Failed to update status:', error);
      // Revert on error
      loadClients();
    }
  };

  // Visibility & Filtering
  const visibleClients = profileLoaded && currentUserEmail
    ? getVisibleClients(clients, currentUserEmail)
    : [];
  const uniqueAssignees = Array.from(new Set(visibleClients.map(c => c.assigned_to).filter(Boolean)));

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

  return (
    <div className="space-y-6 h-full flex flex-col">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">Clients</h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            {filteredClients.length} client{filteredClients.length !== 1 ? 's' : ''}
            {activeFiltersCount > 0 && ` (filtered from ${visibleClients.length})`}
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
                <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-1.5">Status</label>
                <select
                  value={filters.status}
                  onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50"
                >
                  <option value="">All statuses</option>
                  {CLIENT_STATUSES.map(({ value, label }) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-1.5">Nationality</label>
                <select
                  value={filters.nationality}
                  onChange={(e) => setFilters({ ...filters, nationality: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50"
                >
                  <option value="">All nationalities</option>
                  {COMMON_NATIONALITIES.map((nat) => (
                    <option key={nat} value={nat}>{nat}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-1.5">Assigned To</label>
                <select
                  value={filters.assigned_to}
                  onChange={(e) => setFilters({ ...filters, assigned_to: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50"
                >
                  <option value="">All team members</option>
                  {uniqueAssignees.map((assignee) => (
                    <option key={assignee} value={assignee}>{assignee?.split('@')[0]}</option>
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
                {sortField === field && (
                  sortOrder === 'asc' ? <SortAsc className="w-3 h-3" /> : <SortDesc className="w-3 h-3" />
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* CONTENT AREA */}
      {isLoading ? (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-12 text-center">
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-[var(--background-elevated)] rounded w-1/3 mx-auto" />
            <div className="h-4 bg-[var(--background-elevated)] rounded w-1/2 mx-auto" />
          </div>
        </div>
      ) : filteredClients.length > 0 ? (
        <div className="flex-1 overflow-hidden">
          {viewMode === 'list' ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pb-4">
              {filteredClients.map((client) => (
                <ClientCard key={client.id} client={client} />
              ))}
            </div>
          ) : (
            <ClientKanban clients={filteredClients} onStatusChange={handleStatusChange} />
          )}
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-12 text-center">
          <Users className="w-16 h-16 mx-auto text-[var(--foreground-muted)] mb-4 opacity-50" />
          <h2 className="text-lg font-semibold text-[var(--foreground)] mb-2">No clients found</h2>
          <p className="text-sm text-[var(--foreground-muted)] max-w-md mx-auto mb-6">
            Try adjusting your search or filters.
          </p>
          {activeFiltersCount > 0 && (
            <Button variant="outline" onClick={clearFilters} className="gap-2">
              <X className="w-4 h-4" />
              Clear Filters
            </Button>
          )}
        </div>
      )}
    </div>
  );
}