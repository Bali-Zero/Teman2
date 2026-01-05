'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/toast';
import { 
  ArrowLeft, 
  FolderKanban, 
  Loader2, 
  User, 
  Search, 
  Check, 
  Briefcase 
} from 'lucide-react';
import Link from 'next/link';
import { api } from '@/lib/api';
import type { CreatePracticeParams, Client } from '@/lib/api/crm/crm.types';
import { SERVICE_INTERESTS } from '@/lib/api/crm/crm.types';

export default function NewPracticePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();
  
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState({
    title: '', // Maps to notes
    practice_type_code: 'kitas_application',
    client_id: searchParams.get('client_id') ? Number(searchParams.get('client_id')) : undefined,
  });

  // Client Search State
  const [clientSearch, setClientSearch] = useState('');
  const [clients, setClients] = useState<Client[]>([]);
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [isSearchingClients, setIsSearchingClients] = useState(false);
  const [showClientDropdown, setShowClientDropdown] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  // Load initial client if provided in URL
  useEffect(() => {
    const preselectedId = searchParams.get('client_id');
    if (preselectedId) {
      api.crm.getClient(Number(preselectedId)).then(client => {
        setSelectedClient(client);
        setFormData(prev => ({ ...prev, client_id: client.id }));
      }).catch(err => console.error("Failed to load preselected client", err));
    }
  }, [searchParams]);

  // Client Search Logic
  useEffect(() => {
    const searchClients = async () => {
      if (!clientSearch.trim()) {
        setClients([]);
        return;
      }
      setIsSearchingClients(true);
      try {
        const results = await api.crm.getClients({ search: clientSearch, limit: 5 });
        setClients(results);
      } catch (error) {
        console.error('Failed to search clients:', error);
      } finally {
        setIsSearchingClients(false);
      }
    };

    const debounce = setTimeout(searchClients, 300);
    return () => clearTimeout(debounce);
  }, [clientSearch]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setShowClientDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.client_id) {
      toast.error('Missing Client', 'Please select a client to create this case for.');
      return;
    }

    setIsLoading(true);
    try {
      const user = await api.getProfile();
      const backendData: CreatePracticeParams = {
        client_id: formData.client_id,
        practice_type_code: formData.practice_type_code,
        status: 'inquiry',
        priority: 'normal',
        notes: formData.title,
      };
      await api.crm.createPractice(backendData, user.email);
      toast.success('Case Created', 'Successfully created new practice.');
      router.push('/cases');
    } catch (error) {
      console.error('Failed to create case', error);
      toast.error('Error', (error as Error).message);
    } finally {
      setIsLoading(false);
    }
  };

  const inputClass = 'w-full pl-10 pr-4 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 transition-all';
  const labelClass = 'text-sm font-medium text-[var(--foreground)] mb-1.5 block';

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/cases">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="w-5 h-5" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">New Case</h1>
          <p className="text-sm text-[var(--foreground-muted)]">Start a new practice or case</p>
        </div>
      </div>

      {/* Form */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-8 shadow-sm">
        <form onSubmit={handleSubmit} className="space-y-6">
          
          {/* Client Selection */}
          <div className="space-y-2 relative" ref={searchRef}>
            <label className={labelClass}>
              Client <span className="text-red-500">*</span>
            </label>
            
            {selectedClient ? (
              <div className="flex items-center justify-between p-3 rounded-lg border border-[var(--accent)]/30 bg-[var(--accent)]/10">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-[var(--accent)]/20 flex items-center justify-center">
                    <User className="w-4 h-4 text-[var(--accent)]" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-[var(--foreground)]">{selectedClient.full_name}</p>
                    <p className="text-xs text-[var(--foreground-muted)]">{selectedClient.email || 'No email'}</p>
                  </div>
                </div>
                <Button 
                  type="button" 
                  variant="ghost" 
                  size="sm" 
                  onClick={() => {
                    setSelectedClient(null);
                    setFormData(prev => ({ ...prev, client_id: undefined }));
                    setClientSearch('');
                  }}
                >
                  Change
                </Button>
              </div>
            ) : (
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
                <input
                  type="text"
                  value={clientSearch}
                  onChange={(e) => {
                    setClientSearch(e.target.value);
                    setShowClientDropdown(true);
                  }}
                  onFocus={() => setShowClientDropdown(true)}
                  className={inputClass}
                  placeholder="Search client by name or email..."
                />
                {isSearchingClients && (
                  <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 animate-spin text-[var(--foreground-muted)]" />
                )}
                
                {/* Search Results Dropdown */}
                {showClientDropdown && clientSearch && (
                  <div className="absolute z-10 w-full mt-1 bg-[var(--background-elevated)] border border-[var(--border)] rounded-lg shadow-lg max-h-60 overflow-y-auto">
                    {clients.length > 0 ? (
                      clients.map(client => (
                        <button
                          key={client.id}
                          type="button"
                          onClick={() => {
                            setSelectedClient(client);
                            setFormData(prev => ({ ...prev, client_id: client.id }));
                            setShowClientDropdown(false);
                          }}
                          className="w-full text-left px-4 py-3 hover:bg-[var(--background-secondary)] transition-colors border-b border-[var(--border)] last:border-0 flex items-center justify-between group"
                        >
                          <div>
                            <p className="text-sm font-medium text-[var(--foreground)] group-hover:text-[var(--accent)] transition-colors">{client.full_name}</p>
                            <p className="text-xs text-[var(--foreground-muted)]">{client.email || client.phone || 'No contact info'}</p>
                          </div>
                          {client.nationality && (
                            <span className="text-xs px-2 py-0.5 rounded bg-[var(--background)] text-[var(--foreground-muted)]">
                              {client.nationality}
                            </span>
                          )}
                        </button>
                      ))
                    ) : (
                      <div className="p-4 text-center text-sm text-[var(--foreground-muted)]">
                        {isSearchingClients ? 'Searching...' : 'No clients found'}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Case Type */}
          <div className="space-y-2">
            <label className={labelClass}>Case Type</label>
            <div className="relative">
              <Briefcase className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
              <select
                value={formData.practice_type_code}
                onChange={(e) => setFormData(prev => ({ ...prev, practice_type_code: e.target.value }))}
                className={`${inputClass} appearance-none cursor-pointer`}
              >
                {SERVICE_INTERESTS.map(service => (
                  <option key={service.value} value={service.value}>
                    {service.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Title / Initial Notes */}
          <div className="space-y-2">
            <label className={labelClass}>Initial Notes / Title</label>
            <div className="relative">
              <FolderKanban className="absolute left-3 top-3 w-4 h-4 text-[var(--foreground-muted)]" />
              <textarea
                value={formData.title}
                onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
                className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 transition-all resize-none"
                placeholder="e.g. KITAS Renewal 2025, special requirements..."
                rows={3}
              />
            </div>
          </div>

          <div className="pt-4 flex justify-end gap-3 border-t border-[var(--border)]">
            <Link href="/cases">
              <Button variant="outline" type="button" disabled={isLoading}>
                Cancel
              </Button>
            </Link>
            <Button
              className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white min-w-[120px]"
              type="submit"
              disabled={isLoading || !formData.client_id}
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <Check className="w-4 h-4 mr-2" />
                  Create Case
                </>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}