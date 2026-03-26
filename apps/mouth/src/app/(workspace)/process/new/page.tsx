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
  Briefcase,
  DollarSign,
  UserCheck,
} from 'lucide-react';
import Link from 'next/link';
import { api } from '@/lib/api';
import type { CreatePracticeParams, Client } from '@/lib/api/crm/crm.types';
import { createPracticeSchema, flattenErrors } from '@/lib/api/crm/crm.schemas';
import { casesMetrics } from '@/lib/metrics/cases-metrics';
import { logger } from '@/lib/logger';
import { toError } from '@/lib/types/common';

export default function NewPracticePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const toast = useToast();

  const [isLoading, setIsLoading] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const preselectedClientId = searchParams?.get('client_id')
    ? Number(searchParams.get('client_id'))
    : undefined;

  const [formData, setFormData] = useState({
    title: '', // Maps to notes
    practice_type_code: 'visa',
    client_id: preselectedClientId,
    quoted_price: '',
    assigned_to: '',
    priority: 'normal',
  });

  // Client Search State
  const [clientSearch, setClientSearch] = useState('');
  const [clients, setClients] = useState<Client[]>([]);
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const [isSearchingClients, setIsSearchingClients] = useState(false);
  const [showClientDropdown, setShowClientDropdown] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  // Metrics tracking
  const startTime = useRef(performance.now());
  const userEmail = useRef<string | null>(null);

  // Initialize metrics tracking on mount
  useEffect(() => {
    const initMetrics = async () => {
      try {
        const user = await api.getProfile();
        userEmail.current = user.email;
        casesMetrics.trackPageView('new', undefined, user.email);
      } catch (err) {
        logger.error(
          'Failed to init metrics',
          { component: 'NewProcess', action: 'initMetrics' },
          toError(err)
        );
      }
    };

    initMetrics();
  }, []);

  // Load initial client if provided in URL
  useEffect(() => {
    const preselectedId = searchParams?.get('client_id');
    if (preselectedId) {
      api.crm
        .getClient(Number(preselectedId))
        .then((client) => {
          setSelectedClient(client);
          setFormData((prev) => ({ ...prev, client_id: client.id }));
        })
        .catch((err) => logger.error('Failed to load preselected client', err));
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
      const apiStart = performance.now();

      try {
        // ✅ Increased limit from 5 to 20 to show more search results
        const results = await api.crm.getClients({
          search: clientSearch,
          limit: 20,
        });
        const apiDuration = performance.now() - apiStart;
        casesMetrics.trackApiCall(
          '/api/crm/clients/search',
          'GET',
          true,
          apiDuration,
          undefined,
          userEmail.current || undefined
        );
        casesMetrics.trackClientSearch(
          clientSearch,
          results.length,
          userEmail.current || undefined
        );
        setClients(results);
      } catch (error) {
        const apiDuration = performance.now() - apiStart;
        casesMetrics.trackApiCall(
          '/api/crm/clients/search',
          'GET',
          false,
          apiDuration,
          undefined,
          userEmail.current || undefined
        );
        casesMetrics.trackError(
          'Client Search Failed',
          (error as Error).message,
          'CasesNewPage',
          undefined,
          userEmail.current || undefined
        );
        logger.error(
          'Failed to search clients',
          { component: 'NewProcess', action: 'searchClients' },
          toError(error)
        );
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
    setFieldErrors({});

    // Validate with Zod schema
    const result = createPracticeSchema.safeParse({
      client_id: formData.client_id,
      practice_type_code: formData.practice_type_code,
      notes: formData.title,
    });

    if (!result.success) {
      const errors = flattenErrors(result.error);
      setFieldErrors(errors);
      casesMetrics.trackError(
        'Validation Error',
        Object.values(errors).join(', '),
        'CasesNewPage',
        undefined,
        userEmail.current || undefined
      );
      return;
    }

    setIsLoading(true);
    casesMetrics.trackButtonClick(
      'Create Case',
      'CasesNewPage',
      undefined,
      undefined,
      userEmail.current || undefined
    );
    casesMetrics.startPerformanceMark('case_creation');
    const apiStart = performance.now();

    try {
      const user = await api.getProfile();

      // Check for duplicate practices (same client + same type + active status)
      const existingPractices = await api.crm.getClientPractices(result.data.client_id);
      const duplicateCheck = existingPractices.find(
        (p) =>
          p.practice_type_code === result.data.practice_type_code &&
          !['completed', 'cancelled'].includes(p.status)
      );

      if (duplicateCheck) {
        toast.error(
          'Duplicate Process',
          `Client already has an active ${result.data.practice_type_code} process (ID: #${duplicateCheck.id}, Status: ${duplicateCheck.status}). Please complete or cancel it first.`
        );
        casesMetrics.trackError(
          'Duplicate Process Blocked',
          `Prevented duplicate ${result.data.practice_type_code} for client ${result.data.client_id}`,
          'CasesNewPage',
          duplicateCheck.id,
          user.email
        );
        return;
      }

      const backendData: CreatePracticeParams = {
        client_id: result.data.client_id,
        practice_type_code: result.data.practice_type_code,
        status: 'inquiry',
        priority: (formData.priority || 'normal') as 'normal' | 'high' | 'urgent',
        notes: result.data.notes,
        ...(formData.quoted_price ? { quoted_price: Number(formData.quoted_price) } : {}),
        ...(formData.assigned_to ? { assigned_to: formData.assigned_to } : {}),
      };

      const createdPractice = await api.crm.createPractice(backendData, user.email);
      const apiDuration = performance.now() - apiStart;
      casesMetrics.trackApiCall(
        '/api/crm/practices/create',
        'POST',
        true,
        apiDuration,
        undefined,
        user.email
      );

      // Track case creation
      const caseId = (createdPractice as any)?.id || 0;
      casesMetrics.trackCaseCreation(
        caseId,
        result.data.practice_type_code,
        result.data.client_id,
        user.email
      );
      casesMetrics.endPerformanceMark('case_creation', caseId, user.email);

      toast.success('Process Created', 'Successfully created new process.');
      // Return to client page if we came from one, otherwise go to the new process detail
      if (preselectedClientId) {
        router.push(`/clients/${preselectedClientId}?tab=process`);
      } else {
        const newId = (createdPractice as any)?.id;
        router.push(newId ? `/process/${newId}` : '/process');
      }
    } catch (error) {
      const apiDuration = performance.now() - apiStart;
      casesMetrics.trackApiCall(
        '/api/crm/practices/create',
        'POST',
        false,
        apiDuration,
        undefined,
        userEmail.current || undefined
      );
      casesMetrics.trackError(
        'Create Case Failed',
        (error as Error).message,
        'CasesNewPage',
        undefined,
        userEmail.current || undefined
      );

      logger.error(
        'Failed to create case',
        { component: 'NewProcess', action: 'createCase' },
        toError(error)
      );
      toast.error('Error', (error as Error).message);
    } finally {
      setIsLoading(false);
    }
  };

  const inputClass =
    'w-full pl-10 pr-4 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 transition-all';
  const labelClass = 'text-sm font-medium text-[var(--foreground)] mb-1.5 block';

  return (
    <div className="space-y-6 max-w-2xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/process">
          <Button variant="ghost" size="icon" aria-label="Go back to process list">
            <ArrowLeft className="w-5 h-5" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)]">New Process</h1>
          <p className="text-sm text-[var(--foreground-muted)]">Start a new process</p>
        </div>
      </div>

      {/* Form */}
      <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)] p-8 shadow-sm">
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Form-level error */}
          {fieldErrors._form && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-400">
              {fieldErrors._form}
            </div>
          )}

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
                    <p className="text-sm font-medium text-[var(--foreground)]">
                      {selectedClient.full_name}
                    </p>
                    <p className="text-xs text-[var(--foreground-muted)]">
                      {selectedClient.email || 'No email'}
                    </p>
                  </div>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setSelectedClient(null);
                    setFormData((prev) => ({ ...prev, client_id: undefined }));
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
                      clients.map((client) => (
                        <button
                          key={client.id}
                          type="button"
                          onClick={() => {
                            setSelectedClient(client);
                            setFormData((prev) => ({
                              ...prev,
                              client_id: client.id,
                            }));
                            setShowClientDropdown(false);
                          }}
                          className="w-full text-left px-4 py-3 hover:bg-[var(--background-secondary)] transition-colors border-b border-[var(--border)] last:border-0 flex items-center justify-between group"
                        >
                          <div>
                            <p className="text-sm font-medium text-[var(--foreground)] group-hover:text-[var(--accent)] transition-colors">
                              {client.full_name}
                            </p>
                            <p className="text-xs text-[var(--foreground-muted)]">
                              {client.email || client.phone || 'No contact info'}
                            </p>
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
                    {/* Show hint if max results reached */}
                    {clients.length === 20 && (
                      <div className="px-4 py-2 text-xs text-[var(--foreground-muted)] border-t border-[var(--border)] bg-[var(--background-secondary)]/30">
                        Showing top 20 results. Type more to refine search.
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
            {fieldErrors.client_id && (
              <p className="text-xs text-red-400 mt-1">{fieldErrors.client_id}</p>
            )}
          </div>

          {/* Process Type */}
          <div className="space-y-2">
            <label className={labelClass}>Process Type</label>
            <div className="relative">
              <Briefcase className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
              <select
                value={formData.practice_type_code}
                onChange={(e) =>
                  setFormData((prev) => ({
                    ...prev,
                    practice_type_code: e.target.value,
                  }))
                }
                className={`${inputClass} appearance-none cursor-pointer`}
              >
                <option value="visa">VISA</option>
                <option value="extension_visa">EXTENSION VISA</option>
                <option value="kitas">KITAS</option>
                <option value="extension_kitas">EXTENSION KITAS</option>
                <option value="tax">TAX</option>
                <option value="new_pt">NEW PT</option>
                <option value="revision_pt">REVISION PT</option>
                <option value="accessories">ACCESSORIES</option>
              </select>
            </div>
          </div>

          {/* Quoted Price + Assigned To (optional, side by side) */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className={labelClass}>
                Quoted Price{' '}
                <span className="text-[var(--foreground-muted)] font-normal">(IDR, optional)</span>
              </label>
              <div className="relative">
                <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
                <input
                  type="number"
                  min="0"
                  step="100000"
                  value={formData.quoted_price}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, quoted_price: e.target.value }))
                  }
                  className={inputClass}
                  placeholder="e.g. 5000000"
                />
              </div>
            </div>
            <div className="space-y-2">
              <label className={labelClass}>
                Assigned To{' '}
                <span className="text-[var(--foreground-muted)] font-normal">(optional)</span>
              </label>
              <div className="relative">
                <UserCheck className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--foreground-muted)]" />
                <select
                  value={formData.assigned_to}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, assigned_to: e.target.value }))
                  }
                  className={`${inputClass} appearance-none cursor-pointer`}
                >
                  <option value="">— unassigned —</option>
                  <option value="zero@balizero.com">Zero</option>
                  <option value="asya@balizero.com">Asya</option>
                  <option value="antonellosiano@gmail.com">Antonello</option>
                </select>
              </div>
            </div>
          </div>

          {/* Priority */}
          <div className="space-y-2">
            <label className={labelClass}>Priority</label>
            <div className="flex gap-2">
              {(
                [
                  { value: 'normal', label: 'Normal', color: 'text-zinc-400', activeBg: 'bg-zinc-500/20', activeBorder: 'border-zinc-500/40' },
                  { value: 'high', label: '↑ High', color: 'text-orange-400', activeBg: 'bg-orange-500/20', activeBorder: 'border-orange-500/40' },
                  { value: 'urgent', label: '🔥 Urgent', color: 'text-red-400', activeBg: 'bg-red-500/20', activeBorder: 'border-red-500/40' },
                ] as const
              ).map((p) => (
                <button
                  key={p.value}
                  type="button"
                  onClick={() => setFormData((prev) => ({ ...prev, priority: p.value }))}
                  className={`flex-1 py-2 rounded-lg border text-sm font-medium transition-colors ${
                    formData.priority === p.value
                      ? `${p.activeBg} ${p.activeBorder} ${p.color}`
                      : 'border-[var(--border)] bg-[var(--background-elevated)] text-[var(--foreground-muted)] hover:border-[var(--border)] hover:text-[var(--foreground)]'
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          {/* Title / Initial Notes */}
          <div className="space-y-2">
            <label className={labelClass}>Initial Notes / Title</label>
            <div className="relative">
              <FolderKanban className="absolute left-3 top-3 w-4 h-4 text-[var(--foreground-muted)]" />
              <textarea
                value={formData.title}
                onChange={(e) => setFormData((prev) => ({ ...prev, title: e.target.value }))}
                className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 transition-all resize-none"
                placeholder="e.g. KITAS Renewal 2025, special requirements..."
                rows={3}
              />
            </div>
          </div>

          <div className="pt-4 flex justify-end gap-3 border-t border-[var(--border)]">
            <Link href="/process">
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
                  Create Process
                </>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
