'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Users, Search, Filter, Plus, UserPlus } from 'lucide-react';
import { useAutoAnimate } from '@formkit/auto-animate/react';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import type { Client } from '@/lib/api/crm/crm.types';

export default function ClientiPage() {
  const router = useRouter();
  const [clients, setClients] = useState<Client[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [listParent] = useAutoAnimate();

  useEffect(() => {
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

    const debounceTimer = setTimeout(loadClients, searchQuery ? 300 : 0);
    return () => clearTimeout(debounceTimer);
  }, [searchQuery]);

  const handleNewClient = () => {
    router.push('/clients/new');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">Clients</h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            Client database and contact management
          </p>
        </div>
        <Button className="gap-2" onClick={handleNewClient}>
          <UserPlus className="w-4 h-4" />
          New Client
        </Button>
      </div>

      {/* Search & Filter Bar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
          <input
            type="text"
            placeholder="Search clients by name, email, phone..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50"
          />
        </div>
        <Button variant="outline" className="gap-2">
          <Filter className="w-4 h-4" />
          Filters
        </Button>
      </div>

      {/* Clients List */}
      {isLoading ? (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-12 text-center">
          <div className="animate-pulse space-y-4">
            <div className="h-4 bg-[var(--background-elevated)] rounded w-1/3 mx-auto" />
            <div className="h-4 bg-[var(--background-elevated)] rounded w-1/2 mx-auto" />
          </div>
        </div>
      ) : clients.length > 0 ? (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]">
          <div className="p-4 border-b border-[var(--border)]">
            <h2 className="font-semibold text-[var(--foreground)]">
              Clients ({clients.length})
            </h2>
          </div>
          <div ref={listParent} className="divide-y divide-[var(--border)]">
            {clients.map((client) => (
              <div
                key={client.id}
                className="p-4 hover:bg-[var(--background-elevated)]/50 transition-colors cursor-pointer"
                onClick={() => router.push(`/clients/${client.id}`)}
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-medium text-[var(--foreground)]">{client.full_name}</h3>
                    {client.email && (
                      <p className="text-sm text-[var(--foreground-muted)]">{client.email}</p>
                    )}
                    {client.phone && (
                      <p className="text-sm text-[var(--foreground-muted)]">{client.phone}</p>
                    )}
                  </div>
                  {client.company_name && (
                    <span className="text-xs text-[var(--foreground-muted)] bg-[var(--background-elevated)] px-2 py-1 rounded">
                      {client.company_name}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="rounded-xl border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-12 text-center">
          <Users className="w-16 h-16 mx-auto text-[var(--foreground-muted)] mb-4 opacity-50" />
          <h2 className="text-lg font-semibold text-[var(--foreground)] mb-2">
            CRM Clients
          </h2>
          <p className="text-sm text-[var(--foreground-muted)] max-w-md mx-auto mb-6">
            {searchQuery ? 'No clients found matching your search.' : 'No clients yet. Create your first client to get started.'}
          </p>
          <div className="flex flex-wrap justify-center gap-2 text-xs text-[var(--foreground-muted)]">
            <span className="px-3 py-1 rounded-full bg-[var(--background-elevated)]">Database</span>
            <span className="px-3 py-1 rounded-full bg-[var(--background-elevated)]">Documents</span>
            <span className="px-3 py-1 rounded-full bg-[var(--background-elevated)]">Timeline</span>
            <span className="px-3 py-1 rounded-full bg-[var(--background-elevated)]">Notes</span>
          </div>
        </div>
      )}
    </div>
  );
}
