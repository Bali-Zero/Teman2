'use client';

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useRouter, useSearchParams, usePathname } from 'next/navigation';
import {
  FolderKanban,
  Search,
  Filter,
  Plus,
  LayoutGrid,
  List,
  ChevronRight,
  Loader2,
  User,
  MessageCircle,
  Mail,
  Phone,
  FileText,
  MoreVertical,
  CheckCircle,
  CheckCircle2,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Download,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { toError } from '@/lib/types/common';
import type { Practice } from '@/lib/api/crm/crm.types';
import type { StatusTransition } from '@/lib/api/crm/crm.types';
import { MonthPillTabs } from '@/components/process/MonthPillTabs';
import { GhostCard } from '@/components/process/GhostCard';
import {
  COLUMN_COLORS,
  COLUMN_ORDER,
  getStatusColumn,
  type CaseStatus,
} from '@/components/process/kanban-colors';
import {
  trackViewModeChange,
  trackFilterApplied,
  trackFilterRemoved,
  trackSortApplied,
  trackSearch,
  trackCaseStatusChanged,
  trackPaginationChange,
  initializeAnalytics,
} from '@/lib/analytics';

// SIMPLIFIED WORKFLOW (Feb 2026) - 5 Steps:
// inquiry → waiting_documents → sending_invoice → on_process → completed
//
// NOTE: waiting_payment, submitted_to_gov, approved are now internal substates
// handled within the main workflow steps
//
// LEGACY STATUS (for backward compatibility):
// quotation_sent, payment_pending, waiting_payment, in_progress, submitted_to_gov, approved

// Backend status values mapped to frontend display names and kanban columns
// Simplified 5-step workflow
const STATUS_OPTIONS: { value: string; label: string; column: CaseStatus }[] = [
  // Main workflow states (5 steps)
  { value: 'inquiry', label: 'Inquiry', column: 'inquiry' },
  {
    value: 'waiting_documents',
    label: 'Waiting Documents',
    column: 'waiting_documents',
  },
  {
    value: 'sending_invoice',
    label: 'Sending Invoice',
    column: 'sending_invoice',
  },
  { value: 'on_process', label: 'On Process', column: 'on_process' },
  { value: 'completed', label: 'Completed', column: 'completed' },
  // Legacy states mapped to simplified workflow
  {
    value: 'quotation_sent',
    label: 'Quotation Sent (Legacy)',
    column: 'sending_invoice',
  },
  {
    value: 'payment_pending',
    label: 'Payment Pending (Legacy)',
    column: 'sending_invoice',
  },
  {
    value: 'waiting_payment',
    label: 'Waiting Payment (Legacy)',
    column: 'sending_invoice',
  },
  {
    value: 'in_progress',
    label: 'In Progress (Legacy)',
    column: 'on_process',
  },
  {
    value: 'submitted_to_gov',
    label: 'Submitted to Gov (Legacy)',
    column: 'on_process',
  },
  {
    value: 'approved',
    label: 'Approved (Legacy)',
    column: 'on_process',
  },
];

type ViewMode = 'kanban' | 'list';
type SortField =
  | 'id'
  | 'practice_type_code'
  | 'client_name'
  | 'client_lead'
  | 'status'
  | 'created_at';
type SortOrder = 'asc' | 'desc';

interface FilterState {
  status: string;
  type: string;
  assigned_to: string;
  payment_filter: string;
  priority: string;
  expiring: boolean;
}

export default function PratichePage() {
  const router = useRouter();
  const toast = useToast();
  const [practices, setPractices] = useState<Practice[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<ViewMode>('kanban');
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<FilterState>({
    status: '',
    type: '',
    assigned_to: '',
    payment_filter: '',
    priority: '',
    expiring: false,
  });
  const [sortField, setSortField] = useState<SortField>('created_at');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [currentUserEmail, setCurrentUserEmail] = useState<string>('');

  // Context Menu State
  const [selectedPractice, setSelectedPractice] = useState<Practice | null>(null);
  const [menuPosition, setMenuPosition] = useState<{
    x: number;
    y: number;
  } | null>(null);
  const [updatingId, setUpdatingId] = useState<number | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const previousFiltersRef = useRef<FilterState>(filters);

  // Pagination for large datasets
  const [listPageNumber, setListPageNumber] = useState(1);
  const itemsPerPage = 25;

  // Month navigation
  const searchParams = useSearchParams();
  const pathname = usePathname();

  const now = new Date();
  const currentMonthDefault = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  const [selectedMonth, setSelectedMonth] = useState(
    searchParams.get('month') || currentMonthDefault
  );
  const [expandedGhosts, setExpandedGhosts] = useState<Record<string, boolean>>({});

  const handleMonthChange = useCallback(
    (month: string) => {
      setSelectedMonth(month);
      setListPageNumber(1);
      setExpandedGhosts({});
      const params = new URLSearchParams(searchParams.toString());
      params.set('month', month);
      window.history.replaceState(null, '', `${pathname}?${params.toString()}`);
    },
    [searchParams, pathname]
  );

  useEffect(() => {
    // Load current user for "My Work" filter
    api
      .getProfile()
      .then((profile) => {
        if (profile?.email) setCurrentUserEmail(profile.email);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    // Initialize analytics on component mount
    initializeAnalytics();

    const loadPractices = async () => {
      setIsLoading(true);
      try {
        // Enforce RBAC: team members see only their assigned practices
        let assignedTo: string | undefined;
        const user = await api.getProfile();
        if (user && user.role !== 'admin') {
          assignedTo = user.email;
        }

        const data = await api.crm.getPractices({
          limit: 200,
          month: selectedMonth,
          include_history: true,
          ...(assignedTo ? { assigned_to: assignedTo } : {}),
        });
        setPractices(data);
      } catch (error) {
        logger.error(
          'Failed to load practices',
          { component: 'Process', action: 'loadPractices' },
          toError(error)
        );
        toast.error('Error', 'Failed to load process');
      } finally {
        setIsLoading(false);
      }
    };

    loadPractices();
  }, [selectedMonth]);

  // Track view mode changes
  useEffect(() => {
    trackViewModeChange(viewMode);
  }, [viewMode]);

  // Track filter changes
  useEffect(() => {
    Object.keys(filters).forEach((key) => {
      if (
        filters[key as keyof typeof filters] !==
        previousFiltersRef.current[key as keyof typeof filters]
      ) {
        if (filters[key as keyof typeof filters]) {
          if (key === 'status' || key === 'type' || key === 'assigned_to') {
            const val = filters[key as keyof typeof filters];
            if (typeof val === 'string') trackFilterApplied(key, val);
          }
        } else {
          trackFilterRemoved(key);
        }
      }
    });
    previousFiltersRef.current = filters;
  }, [filters]);

  // Track sort changes
  useEffect(() => {
    trackSortApplied(sortField, sortOrder);
  }, [sortField, sortOrder]);

  // Track pagination changes
  useEffect(() => {
    if (listPageNumber > 1) {
      trackPaginationChange(listPageNumber, itemsPerPage);
    }
  }, [listPageNumber]);

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setSelectedPractice(null);
        setMenuPosition(null);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleStatusChange = async (practiceId: number, newStatus: string) => {
    setUpdatingId(practiceId);
    try {
      const user = await api.getProfile();

      // Find old status for tracking
      const practice = practices.find((p) => p.id === practiceId);
      const oldStatus = practice?.status || 'unknown';

      await api.crm.updatePractice(practiceId, { status: newStatus }, user.email);

      // Update local state immediately for responsiveness
      setPractices((prev) =>
        prev.map((p) => (p.id === practiceId ? { ...p, status: newStatus } : p))
      );

      // Track status change
      trackCaseStatusChanged(practiceId, oldStatus, newStatus);

      toast.success('Status Updated', `Process moved to ${newStatus.replace(/_/g, ' ')}`);

      setSelectedPractice(null);
      setMenuPosition(null);
    } catch (error) {
      logger.error(
        'Failed to update status',
        { component: 'Process', action: 'updateStatus' },
        toError(error)
      );
      toast.error('Error', 'Failed to update process status');
    } finally {
      setUpdatingId(null);
    }
  };

  const handleMenuClick = (e: React.MouseEvent, practice: Practice) => {
    e.preventDefault();
    e.stopPropagation();

    // Position menu near the click
    const rect = (e.target as HTMLElement).getBoundingClientRect();
    setSelectedPractice(practice);
    setMenuPosition({ x: rect.right - 10, y: rect.bottom + 5 });
  };

  const handleNewCase = () => {
    router.push('/process/new');
  };

  const clearFilters = () => {
    setFilters({
      status: '',
      type: '',
      assigned_to: '',
      payment_filter: '',
      priority: '',
      expiring: false,
    });
  };

  const toggleSort = useCallback((field: SortField) => {
    setSortField((prevField) => {
      if (prevField === field) {
        setSortOrder((prevOrder) => (prevOrder === 'asc' ? 'desc' : 'asc'));
        return prevField;
      } else {
        setSortOrder('asc');
        return field;
      }
    });
  }, []);

  const getGhostPractices = useCallback(
    (columnStatus: CaseStatus) => {
      return practices.filter((p) => {
        const currentColumn = getStatusColumn(p.status);
        if (currentColumn === columnStatus) return false;
        const transitions = (p as any).status_transitions as StatusTransition[] | undefined;
        if (!transitions || transitions.length === 0) return false;
        return transitions.some((t) => getStatusColumn(t.status) === columnStatus);
      });
    },
    [practices]
  );

  const activeFiltersCount = Object.values(filters).filter(Boolean).length;

  // Memoize filtered and sorted practices to avoid unnecessary recalculations
  const filteredPractices = useMemo(
    () =>
      practices
        .filter((p) => {
          // Search filter
          if (searchQuery) {
            const matchesSearch =
              p.id.toString().includes(searchQuery) ||
              p.client_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
              p.practice_type_code?.toLowerCase().includes(searchQuery.toLowerCase());
            if (!matchesSearch) return false;
          }

          // Status filter
          if (filters.status && getStatusColumn(p.status) !== filters.status) {
            return false;
          }

          // Type filter
          if (filters.type && p.practice_type_code !== filters.type) {
            return false;
          }

          // Assigned to filter
          if (filters.assigned_to && p.client_lead !== filters.assigned_to) {
            return false;
          }

          // Payment filter
          if (filters.payment_filter === 'unpaid') {
            if (p.payment_status !== 'unpaid' && p.payment_status !== 'partial') {
              return false;
            }
          }

          // Priority filter
          if (filters.priority && p.priority !== filters.priority) {
            return false;
          }

          // Expiring soon filter (within 30 days)
          if (filters.expiring) {
            if (!p.expiry_date) return false;
            const daysLeft = Math.ceil((new Date(p.expiry_date).getTime() - Date.now()) / 86400000);
            if (daysLeft < 0 || daysLeft > 30) return false;
          }

          return true;
        })
        .sort((a, b) => {
          let comparison = 0;

          switch (sortField) {
            case 'id':
              comparison = (a.id || 0) - (b.id || 0);
              break;
            case 'practice_type_code':
              comparison = (a.practice_type_code || '').localeCompare(b.practice_type_code || '');
              break;
            case 'client_name':
              comparison = (a.client_name || '').localeCompare(b.client_name || '');
              break;
            case 'client_lead':
              comparison = (a.client_lead || '').localeCompare(b.client_lead || '');
              break;
            case 'status':
              comparison = (a.status || '').localeCompare(b.status || '');
              break;
            case 'created_at':
              comparison =
                new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime();
              break;
            default:
              comparison = 0;
          }

          return sortOrder === 'asc' ? comparison : -comparison;
        }),
    [practices, searchQuery, filters, sortField, sortOrder]
  );

  // Memoize practices by status to avoid unnecessary recalculations
  // Simplified 5-step workflow: inquiry → waiting_documents → sending_invoice → on_process → completed
  const practicesByStatus = useMemo(
    () => ({
      inquiry: filteredPractices.filter((p) => getStatusColumn(p.status) === 'inquiry'),
      waiting_documents: filteredPractices.filter(
        (p) => getStatusColumn(p.status) === 'waiting_documents'
      ),
      sending_invoice: filteredPractices.filter(
        (p) => getStatusColumn(p.status) === 'sending_invoice'
      ),
      on_process: filteredPractices.filter((p) => getStatusColumn(p.status) === 'on_process'),
      completed: filteredPractices.filter((p) => getStatusColumn(p.status) === 'completed'),
    }),
    [filteredPractices]
  );

  // Track search operations (moved after filteredPractices declaration)
  useEffect(() => {
    if (searchQuery) {
      trackSearch(searchQuery, filteredPractices.length);
    }
  }, [searchQuery, filteredPractices.length]);

  const exportCSV = useCallback(() => {
    const rows = filteredPractices.map((p) => ({
      ID: p.id,
      Client: p.client_name || '',
      Type: p.practice_type_code || '',
      Status: p.status || '',
      'Assigned To': p.client_lead?.split('@')[0] || '',
      'Payment Status': p.payment_status || '',
      'Quoted Price': p.quoted_price || '',
      'Actual Price': p.actual_price || '',
      'Created At': p.created_at ? new Date(p.created_at).toLocaleDateString('en-GB') : '',
      'Updated At': p.updated_at ? new Date(p.updated_at).toLocaleDateString('en-GB') : '',
    }));
    const headers = Object.keys(rows[0] || {});
    const csv = [
      headers.join(','),
      ...rows.map((r) =>
        headers.map((h) => `"${String(r[h as keyof typeof r]).replace(/"/g, '""')}"`).join(',')
      ),
    ].join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `processes_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success('Exported', `${rows.length} processes downloaded`);
  }, [filteredPractices, toast]);

  // Pagination for list view
  const paginatedPractices = useMemo(() => {
    const startIdx = (listPageNumber - 1) * itemsPerPage;
    return filteredPractices.slice(startIdx, startIdx + itemsPerPage);
  }, [filteredPractices, listPageNumber]);

  const totalPages = Math.ceil(filteredPractices.length / itemsPerPage);

  const SkeletonCard = () => (
    <div className="p-3 rounded-lg border border-[rgba(255,255,255,0.05)] bg-[rgba(35,35,40,0.45)] backdrop-blur-md space-y-2">
      <div className="h-4 bg-[rgba(255,255,255,0.05)] rounded w-3/4 animate-pulse" />
      <div className="h-3 bg-[rgba(255,255,255,0.05)] rounded w-1/2 animate-pulse" />
      <div className="flex gap-2 mt-4 pt-3 border-t border-[var(--bz-border)]">
        <div className="h-6 w-6 bg-[rgba(255,255,255,0.05)] rounded animate-pulse" />
        <div className="h-6 w-6 bg-[rgba(255,255,255,0.05)] rounded animate-pulse" />
      </div>
    </div>
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--bz-text-1)]">Process</h1>
          <p className="text-sm text-[var(--bz-text-2)]">
            Manage KITAS, Visa, PT PMA, Tax and other processes
          </p>
        </div>
        <Button
          className="gap-2 bg-[var(--bz-accent)] hover:bg-[var(--bz-accent)]/90 text-white"
          onClick={handleNewCase}
        >
          <Plus className="w-4 h-4" />
          New Process
        </Button>
      </div>

      {/* Month Navigation */}
      <MonthPillTabs selectedMonth={selectedMonth} onMonthChange={handleMonthChange} />

      {/* Quick Stats Row */}
      {!isLoading &&
        filteredPractices.length > 0 &&
        (() => {
          const active = filteredPractices.filter(
            (p) => getStatusColumn(p.status) !== 'completed'
          ).length;
          const completed = filteredPractices.filter(
            (p) => getStatusColumn(p.status) === 'completed'
          ).length;
          const unpaidRevenue = filteredPractices
            .filter((p) => p.payment_status === 'unpaid' || p.payment_status === 'partial')
            .reduce((s, p) => s + (p.actual_price || p.quoted_price || 0), 0);
          const totalRevenue = filteredPractices
            .filter((p) => p.payment_status === 'paid')
            .reduce((s, p) => s + (p.actual_price || p.quoted_price || 0), 0);
          return (
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.06)] text-[var(--bz-text-2)]">
                <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
                {active} active
              </span>
              <span className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.06)] text-[var(--bz-text-2)]">
                <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
                {completed} completed
              </span>
              {totalRevenue > 0 && (
                <span className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-green-500/10 border border-green-500/20 text-green-400">
                  {new Intl.NumberFormat('id-ID', {
                    notation: 'compact',
                    currency: 'IDR',
                    style: 'currency',
                    maximumFractionDigits: 0,
                  }).format(totalRevenue)}{' '}
                  paid
                </span>
              )}
              {unpaidRevenue > 0 && (
                <span className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-red-500/10 border border-red-500/20 text-red-400">
                  {new Intl.NumberFormat('id-ID', {
                    notation: 'compact',
                    currency: 'IDR',
                    style: 'currency',
                    maximumFractionDigits: 0,
                  }).format(unpaidRevenue)}{' '}
                  unpaid
                </span>
              )}
            </div>
          );
        })()}

      {/* Search & Filter Bar */}
      <div className="flex flex-col gap-3">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--bz-text-2)]" />
            <input
              type="text"
              placeholder="Search process by ID, client, type..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-lg border border-[rgba(255,255,255,0.05)] bg-[rgba(35,35,40,0.6)] backdrop-blur-md text-[var(--bz-text-1)] placeholder:text-[var(--bz-text-2)] focus:outline-none focus:ring-2 focus:ring-[var(--bz-accent)]/50 transition-all"
            />
          </div>
          <div className="flex gap-2">
            <Button
              variant={showFilters ? 'default' : 'outline'}
              className="gap-2 border-[rgba(255,255,255,0.05)] bg-[rgba(35,35,40,0.6)] backdrop-blur-md text-[var(--bz-text-1)] hover:bg-[rgba(45,45,50,0.8)]"
              onClick={() => setShowFilters(!showFilters)}
            >
              <Filter className="w-4 h-4" />
              Filters
              {activeFiltersCount > 0 && (
                <span className="ml-1 px-1.5 py-0.5 text-xs rounded-full bg-[var(--bz-accent)] text-white">
                  {activeFiltersCount}
                </span>
              )}
            </Button>
            <Button
              variant="outline"
              className="gap-2 border-[rgba(255,255,255,0.05)] bg-[rgba(35,35,40,0.6)] backdrop-blur-md text-[var(--bz-text-2)] hover:bg-[rgba(45,45,50,0.8)] hover:text-[var(--bz-text-1)]"
              onClick={exportCSV}
              title={`Export ${filteredPractices.length} processes as CSV`}
            >
              <Download className="w-4 h-4" />
              <span className="hidden sm:inline">Export</span>
            </Button>
            <div className="flex rounded-lg border border-[rgba(255,255,255,0.05)] bg-[rgba(35,35,40,0.6)] backdrop-blur-md overflow-hidden">
              <button
                onClick={() => setViewMode('kanban')}
                className={`p-2 transition-all ${
                  viewMode === 'kanban'
                    ? 'bg-[var(--bz-accent)]/10 text-[var(--bz-accent)]'
                    : 'text-[var(--bz-text-2)] hover:bg-[var(--bz-card)]'
                }`}
                title="Kanban Board"
              >
                <LayoutGrid className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`p-2 transition-all ${
                  viewMode === 'list'
                    ? 'bg-[var(--bz-accent)]/10 text-[var(--bz-accent)]'
                    : 'text-[var(--bz-text-2)] hover:bg-[var(--bz-card)]'
                }`}
                title="List View"
              >
                <List className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Quick Filter Chips */}
        <div className="flex items-center gap-2 flex-wrap">
          {currentUserEmail && (
            <button
              onClick={() =>
                setFilters((f) => ({
                  ...f,
                  assigned_to: f.assigned_to === currentUserEmail ? '' : currentUserEmail,
                }))
              }
              className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-colors border ${
                filters.assigned_to === currentUserEmail
                  ? 'bg-[var(--bz-accent)]/20 text-[var(--bz-accent)] border-[var(--bz-accent)]/40'
                  : 'bg-[rgba(255,255,255,0.04)] text-[var(--bz-text-2)] border-[rgba(255,255,255,0.06)] hover:border-[var(--bz-accent)]/30 hover:text-[var(--bz-accent)]'
              }`}
            >
              <User className="w-3 h-3" />
              My Work
            </button>
          )}
          <button
            onClick={() =>
              setFilters((f) => ({
                ...f,
                payment_filter: f.payment_filter === 'unpaid' ? '' : 'unpaid',
              }))
            }
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-colors border ${
              filters.payment_filter === 'unpaid'
                ? 'bg-red-500/20 text-red-400 border-red-500/40'
                : 'bg-[rgba(255,255,255,0.04)] text-[var(--bz-text-2)] border-[rgba(255,255,255,0.06)] hover:border-red-500/30 hover:text-red-400'
            }`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-current" />
            Unpaid
          </button>
          <button
            onClick={() =>
              setFilters((f) => ({
                ...f,
                priority: f.priority === 'urgent' ? '' : 'urgent',
              }))
            }
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-colors border ${
              filters.priority === 'urgent'
                ? 'bg-red-500/20 text-red-400 border-red-500/40'
                : 'bg-[rgba(255,255,255,0.04)] text-[var(--bz-text-2)] border-[rgba(255,255,255,0.06)] hover:border-red-500/30 hover:text-red-400'
            }`}
          >
            🔥 Urgent
          </button>
          <button
            onClick={() =>
              setFilters((f) => ({
                ...f,
                priority: f.priority === 'high' ? '' : 'high',
              }))
            }
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-colors border ${
              filters.priority === 'high'
                ? 'bg-orange-500/20 text-orange-400 border-orange-500/40'
                : 'bg-[rgba(255,255,255,0.04)] text-[var(--bz-text-2)] border-[rgba(255,255,255,0.06)] hover:border-orange-500/30 hover:text-orange-400'
            }`}
          >
            ↑ High
          </button>
          <button
            onClick={() => setFilters((f) => ({ ...f, expiring: !f.expiring }))}
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium transition-colors border ${
              filters.expiring
                ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/40'
                : 'bg-[rgba(255,255,255,0.04)] text-[var(--bz-text-2)] border-[rgba(255,255,255,0.06)] hover:border-yellow-500/30 hover:text-yellow-400'
            }`}
          >
            ⏰ Expiring 30d
          </button>
        </div>

        {/* Filters Panel */}
        {showFilters && (
          <div className="p-4 rounded-lg border border-[rgba(255,255,255,0.05)] bg-[rgba(32,32,36,0.7)] backdrop-blur-xl shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-medium text-[var(--bz-text-1)]">Filters</h3>
              {activeFiltersCount > 0 && (
                <button
                  onClick={clearFilters}
                  className="text-sm text-[var(--bz-accent)] hover:underline flex items-center gap-1"
                >
                  Clear all
                </button>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {/* Status Filter */}
              <div>
                <label
                  htmlFor="status-filter"
                  className="block text-sm font-medium text-[var(--bz-text-2)] mb-1.5"
                >
                  Status
                </label>
                <select
                  id="status-filter"
                  value={filters.status}
                  onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-base)] text-[var(--bz-text-1)] focus:outline-none focus:ring-2 focus:ring-[var(--bz-accent)]/50"
                >
                  <option value="">All statuses</option>
                  <option value="inquiry">Inquiry</option>
                  <option value="waiting_documents">Waiting Documents</option>
                  <option value="sending_invoice">Sending Invoice</option>
                  <option value="waiting_payment">Waiting Payment</option>
                  <option value="on_process">On Process</option>
                  <option value="submitted_to_gov">Submitted to Gov</option>
                  <option value="approved">Approved</option>
                  <option value="completed">Completed</option>
                </select>
              </div>

              {/* Type Filter */}
              <div>
                <label
                  htmlFor="type-filter"
                  className="block text-sm font-medium text-[var(--bz-text-2)] mb-1.5"
                >
                  Process Type
                </label>
                <select
                  id="type-filter"
                  value={filters.type}
                  onChange={(e) => setFilters({ ...filters, type: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-base)] text-[var(--bz-text-1)] focus:outline-none focus:ring-2 focus:ring-[var(--bz-accent)]/50"
                >
                  <option value="">All types</option>
                  <option value="kitas">KITAS Work Permit</option>
                  <option value="extension_kitas">KITAS Extension</option>
                  <option value="visa">Visa</option>
                  <option value="extension_visa">Visa Extension</option>
                  <option value="new_pt">PT PMA Setup</option>
                  <option value="revision_pt">PT Revision</option>
                  <option value="tax">Tax Consulting</option>
                  <option value="accessories">Accessories</option>
                </select>
              </div>

              {/* Assigned To Filter */}
              <div>
                <label
                  htmlFor="assigned-to-filter"
                  className="block text-sm font-medium text-[var(--bz-text-2)] mb-1.5"
                >
                  Assigned To
                </label>
                <select
                  id="assigned-to-filter"
                  value={filters.assigned_to}
                  onChange={(e) => setFilters({ ...filters, assigned_to: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-base)] text-[var(--bz-text-1)] focus:outline-none focus:ring-2 focus:ring-[var(--bz-accent)]/50"
                >
                  <option value="">All team members</option>
                  {Array.from(new Set(practices.map((p) => p.client_lead).filter(Boolean))).map(
                    (lead) => (
                      <option key={lead} value={lead || ''}>
                        {lead?.split('@')[0]}
                      </option>
                    )
                  )}
                </select>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Kanban Board View - Simplified 5-Step Workflow */}
      {viewMode === 'kanban' && (
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4 overflow-x-auto">
          {COLUMN_ORDER.map((statusKey) => {
            const colors = COLUMN_COLORS[statusKey];
            const columnPractices = practicesByStatus[statusKey] || [];
            const ghosts = getGhostPractices(statusKey);
            const isExpanded = expandedGhosts[statusKey] ?? false;
            const visibleGhosts = isExpanded ? ghosts : ghosts.slice(0, 2);
            const hiddenGhostCount = ghosts.length - 2;
            const isCompleted = statusKey === 'completed';

            return (
              <div
                key={statusKey}
                className="rounded-xl flex flex-col h-full min-h-[500px] min-w-[280px] overflow-hidden shadow-xl backdrop-blur-md"
                style={{
                  background: colors.tintBg,
                  border: `1px solid rgba(255,255,255,0.05)`,
                }}
              >
                {/* Gradient top bar */}
                <div
                  className="h-[3px] w-full"
                  style={{
                    background: `linear-gradient(90deg, ${colors.gradientStart}, ${colors.gradientEnd})`,
                  }}
                />

                <div className="p-4 flex flex-col flex-1">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${colors.dotColor}`} />
                      <h3 className="font-semibold text-sm" style={{ color: colors.textColor }}>
                        {colors.label}
                      </h3>
                    </div>
                    <span
                      className="text-xs px-2 py-1 rounded-full font-medium"
                      style={{
                        background: colors.badgeBg,
                        color: colors.textColor,
                      }}
                    >
                      {columnPractices.length}
                    </span>
                  </div>

                  <div className="flex-1 space-y-3">
                    {isLoading ? (
                      <div data-testid="loading-skeleton">
                        <SkeletonCard />
                        <SkeletonCard />
                        <SkeletonCard />
                      </div>
                    ) : columnPractices.length === 0 && ghosts.length === 0 ? (
                      <div className="flex flex-col items-center justify-center h-32 border border-dashed border-[var(--bz-border)] rounded-lg bg-[var(--bz-card)]/30">
                        <FolderKanban className="w-8 h-8 text-[var(--bz-text-2)] opacity-20 mb-2" />
                        <p className="text-xs text-[var(--bz-text-2)]">No process</p>
                      </div>
                    ) : (
                      <>
                        {columnPractices.map((practice) => {
                          const cardIsCompleted = getStatusColumn(practice.status) === 'completed';

                          return (
                            <div
                              key={practice.id}
                              className={`p-3 rounded-lg border cursor-pointer transition-all hover:shadow-xl relative group backdrop-blur-sm hover:-translate-y-1 ${
                                updatingId === practice.id ? 'opacity-70 pointer-events-none' : ''
                              } ${
                                selectedPractice?.id === practice.id
                                  ? 'border-[var(--bz-accent)] ring-1 ring-[var(--bz-accent)]/30'
                                  : cardIsCompleted
                                    ? 'border-green-500/30'
                                    : 'border-[rgba(255,255,255,0.06)] hover:border-[var(--bz-accent)]/30'
                              }`}
                              style={
                                cardIsCompleted
                                  ? {
                                      background:
                                        'linear-gradient(145deg, rgba(34, 197, 94, 0.12) 0%, rgba(34, 197, 94, 0.05) 100%)',
                                      boxShadow: '0 4px 20px rgba(34, 197, 94, 0.15)',
                                    }
                                  : {
                                      background:
                                        'linear-gradient(145deg, rgba(40,40,45,0.7) 0%, rgba(30,30,35,0.4) 100%)',
                                    }
                              }
                              onClick={() => router.push(`/process/${practice.id}`)}
                            >
                              {updatingId === practice.id && (
                                <div className="absolute inset-0 flex items-center justify-center bg-[var(--bz-card)]/80 rounded-lg z-10">
                                  <Loader2 className="w-5 h-5 animate-spin text-[var(--bz-accent)]" />
                                </div>
                              )}

                              {/* Card Header */}
                              <div className="flex items-start justify-between mb-1">
                                <p className="text-sm font-medium text-[var(--bz-text-1)] line-clamp-2 pr-6 flex items-center gap-1.5">
                                  {cardIsCompleted && (
                                    <CheckCircle className="w-3.5 h-3.5 text-green-500 flex-shrink-0" />
                                  )}
                                  {practice.priority === 'urgent' && (
                                    <span className="shrink-0 text-[9px] font-bold px-1 py-0.5 rounded bg-red-500/20 text-red-400 uppercase tracking-wide">
                                      urgent
                                    </span>
                                  )}
                                  {practice.priority === 'high' && (
                                    <span className="shrink-0 text-[9px] font-bold px-1 py-0.5 rounded bg-orange-500/15 text-orange-400 uppercase tracking-wide">
                                      high
                                    </span>
                                  )}
                                  {practice.practice_type_code?.toUpperCase().replace(/_/g, ' ') ||
                                    'Process'}
                                </p>

                                {/* 3-Dot Menu Trigger */}
                                <button
                                  className="absolute top-3 right-2 p-1 rounded-md text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)] hover:bg-[rgba(255,255,255,0.05)] opacity-0 group-hover:opacity-100 transition-opacity"
                                  onClick={(e) => handleMenuClick(e, practice)}
                                >
                                  <MoreVertical className="w-4 h-4" />
                                </button>
                              </div>

                              <div className="flex items-center gap-1.5 mb-2">
                                {practice.client_id ? (
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      router.push(`/clients/${practice.client_id}`);
                                    }}
                                    className="text-xs text-[var(--bz-text-2)] truncate hover:text-[var(--bz-accent)] transition-colors text-left"
                                    title="Open client profile"
                                  >
                                    {practice.client_name || 'Unknown Client'}
                                  </button>
                                ) : (
                                  <p className="text-xs text-[var(--bz-text-2)] truncate">
                                    {practice.client_name || 'Unknown Client'}
                                  </p>
                                )}
                                {practice.payment_status && practice.payment_status !== 'paid' && (
                                  <span
                                    className={`text-[9px] px-1.5 py-0.5 rounded-full shrink-0 font-medium ${
                                      practice.payment_status === 'unpaid'
                                        ? 'bg-red-500/20 text-red-400'
                                        : 'bg-yellow-500/20 text-yellow-400'
                                    }`}
                                  >
                                    {practice.payment_status}
                                  </span>
                                )}
                              </div>

                              <div className="flex items-center justify-between">
                                {practice.client_lead ? (
                                  <div className="flex items-center gap-1.5 bg-[var(--bz-accent)]/10 px-2 py-0.5 rounded text-[var(--bz-accent)]">
                                    <User className="w-3 h-3" />
                                    <p className="text-[10px] font-medium truncate max-w-[80px]">
                                      {practice.client_lead.split('@')[0]}
                                    </p>
                                  </div>
                                ) : (
                                  <div />
                                )}
                                <div className="flex items-center gap-1.5">
                                  {practice.actual_price || practice.quoted_price ? (
                                    <span
                                      className={`text-[10px] font-medium ${
                                        practice.payment_status === 'paid'
                                          ? 'text-green-400'
                                          : 'text-[var(--bz-accent)]'
                                      }`}
                                    >
                                      {new Intl.NumberFormat('id-ID', {
                                        notation: 'compact',
                                        currency: 'IDR',
                                        style: 'currency',
                                        maximumFractionDigits: 0,
                                      }).format(
                                        practice.actual_price || practice.quoted_price || 0
                                      )}
                                    </span>
                                  ) : null}
                                  <span className="text-[10px] text-[var(--bz-text-2)]">
                                    #{practice.id}
                                  </span>
                                  {practice.updated_at &&
                                    (() => {
                                      const ageDays = Math.floor(
                                        (Date.now() - new Date(practice.updated_at).getTime()) /
                                          86400000
                                      );
                                      if (ageDays === 0) return null;
                                      const label =
                                        ageDays >= 7
                                          ? `${Math.floor(ageDays / 7)}w`
                                          : `${ageDays}d`;
                                      return (
                                        <span
                                          className={`text-[9px] px-1 py-0.5 rounded tabular-nums ${
                                            ageDays > 14
                                              ? 'bg-red-500/15 text-red-400'
                                              : ageDays > 7
                                                ? 'bg-yellow-500/15 text-yellow-400'
                                                : 'text-[var(--bz-text-2)]'
                                          }`}
                                          title={`Last updated ${ageDays} days ago`}
                                        >
                                          {label}
                                        </span>
                                      );
                                    })()}
                                </div>
                              </div>

                              {/* Quick Actions */}
                              <div className="flex items-center gap-1 mt-3 pt-2 border-t border-[var(--bz-border)]">
                                {practice.client_phone && (
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      const phone = practice.client_phone?.replace(/\D/g, '');
                                      window.open(
                                        `https://wa.me/${phone}?text=Hi ${practice.client_name}, regarding your process...`,
                                        '_blank'
                                      );
                                    }}
                                    className="p-1.5 rounded hover:bg-green-500/20 text-green-500 transition-colors"
                                    title="WhatsApp"
                                  >
                                    <MessageCircle className="w-3.5 h-3.5" />
                                  </button>
                                )}
                                {practice.client_email && (
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      window.open(`mailto:${practice.client_email}`, '_blank');
                                    }}
                                    className="p-1.5 rounded hover:bg-blue-500/20 text-blue-500 transition-colors"
                                    title="Email"
                                  >
                                    <Mail className="w-3.5 h-3.5" />
                                  </button>
                                )}
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    router.push(`/clients/${practice.client_id}?tab=documents`);
                                  }}
                                  className="p-1.5 rounded hover:bg-orange-500/20 text-orange-500 transition-colors ml-auto"
                                  title="View Documents"
                                >
                                  <FileText className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </div>
                          );
                        })}

                        {/* Ghost section */}
                        {ghosts.length > 0 && (
                          <>
                            <div className="flex items-center gap-2 py-1">
                              <div className="flex-1 border-t border-dashed border-[var(--bz-border)]" />
                              <span className="text-[9px] uppercase tracking-wider text-[var(--bz-text-2)]/50 font-medium">
                                passate
                              </span>
                              <div className="flex-1 border-t border-dashed border-[var(--bz-border)]" />
                            </div>
                            {visibleGhosts.map((gp) => (
                              <GhostCard
                                key={`ghost-${gp.id}`}
                                practice={gp}
                                onClick={() => router.push(`/process/${gp.id}`)}
                              />
                            ))}
                            {!isExpanded && hiddenGhostCount > 0 && (
                              <button
                                onClick={() =>
                                  setExpandedGhosts((prev) => ({
                                    ...prev,
                                    [statusKey]: true,
                                  }))
                                }
                                className="w-full text-center text-[10px] text-[var(--bz-text-2)]/60 hover:text-[var(--bz-text-2)] py-1 transition-colors"
                              >
                                +{hiddenGhostCount} passate
                              </button>
                            )}
                          </>
                        )}
                      </>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* List View */}
      {viewMode === 'list' && (
        <div className="rounded-xl border border-[rgba(255,255,255,0.05)] bg-[rgba(32,32,36,0.6)] backdrop-blur-md shadow-2xl overflow-hidden">
          {isLoading ? (
            <div className="p-12 text-center">
              <div className="animate-pulse space-y-4">
                <div className="h-4 bg-[var(--bz-card)] rounded w-1/3 mx-auto" />
                <div className="h-4 bg-[var(--bz-card)] rounded w-1/2 mx-auto" />
              </div>
            </div>
          ) : filteredPractices.length === 0 ? (
            <div className="flex flex-col items-center justify-center p-12">
              <FolderKanban className="w-16 h-16 text-[var(--bz-text-2)] opacity-50 mb-4" />
              <h3 className="text-lg font-semibold text-[var(--bz-text-1)] mb-2">
                No process found
              </h3>
              <p className="text-sm text-[var(--bz-text-2)] max-w-md">
                Try adjusting your search or filters to find process.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-[rgba(35,35,40,0.8)] border-b border-[rgba(255,255,255,0.05)] backdrop-blur-lg">
                  <tr>
                    <th
                      onClick={() => toggleSort('id')}
                      className="px-4 py-3 text-left text-sm font-semibold text-[var(--bz-text-1)] cursor-pointer hover:bg-[var(--bz-base)]/50 transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        ID
                        {sortField === 'id' &&
                          (sortOrder === 'asc' ? (
                            <ArrowUp className="w-4 h-4" />
                          ) : (
                            <ArrowDown className="w-4 h-4" />
                          ))}
                        {sortField !== 'id' && <ArrowUpDown className="w-4 h-4 opacity-30" />}
                      </div>
                    </th>
                    <th
                      onClick={() => toggleSort('practice_type_code')}
                      className="px-4 py-3 text-left text-sm font-semibold text-[var(--bz-text-1)] cursor-pointer hover:bg-[var(--bz-base)]/50 transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        Process Type
                        {sortField === 'practice_type_code' &&
                          (sortOrder === 'asc' ? (
                            <ArrowUp className="w-4 h-4" />
                          ) : (
                            <ArrowDown className="w-4 h-4" />
                          ))}
                        {sortField !== 'practice_type_code' && (
                          <ArrowUpDown className="w-4 h-4 opacity-30" />
                        )}
                      </div>
                    </th>
                    <th
                      onClick={() => toggleSort('client_name')}
                      className="px-4 py-3 text-left text-sm font-semibold text-[var(--bz-text-1)] cursor-pointer hover:bg-[var(--bz-base)]/50 transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        Client
                        {sortField === 'client_name' &&
                          (sortOrder === 'asc' ? (
                            <ArrowUp className="w-4 h-4" />
                          ) : (
                            <ArrowDown className="w-4 h-4" />
                          ))}
                        {sortField !== 'client_name' && (
                          <ArrowUpDown className="w-4 h-4 opacity-30" />
                        )}
                      </div>
                    </th>
                    <th
                      onClick={() => toggleSort('client_lead')}
                      className="px-4 py-3 text-left text-sm font-semibold text-[var(--bz-text-1)] cursor-pointer hover:bg-[var(--bz-base)]/50 transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        Assigned To
                        {sortField === 'client_lead' &&
                          (sortOrder === 'asc' ? (
                            <ArrowUp className="w-4 h-4" />
                          ) : (
                            <ArrowDown className="w-4 h-4" />
                          ))}
                        {sortField !== 'client_lead' && (
                          <ArrowUpDown className="w-4 h-4 opacity-30" />
                        )}
                      </div>
                    </th>
                    <th
                      onClick={() => toggleSort('status')}
                      className="px-4 py-3 text-left text-sm font-semibold text-[var(--bz-text-1)] cursor-pointer hover:bg-[var(--bz-base)]/50 transition-colors"
                    >
                      <div className="flex items-center gap-2">
                        Status
                        {sortField === 'status' &&
                          (sortOrder === 'asc' ? (
                            <ArrowUp className="w-4 h-4" />
                          ) : (
                            <ArrowDown className="w-4 h-4" />
                          ))}
                        {sortField !== 'status' && <ArrowUpDown className="w-4 h-4 opacity-30" />}
                      </div>
                    </th>
                    <th className="px-4 py-3 text-left text-sm font-semibold text-[var(--bz-text-1)]">
                      Payment
                    </th>
                    <th className="px-4 py-3 text-right text-sm font-semibold text-[var(--bz-text-1)]">
                      Price
                    </th>
                    <th className="px-4 py-3 text-left text-sm font-semibold text-[var(--bz-text-1)]">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[rgba(255,255,255,0.05)]">
                  {paginatedPractices.map((practice) => (
                    <tr
                      key={practice.id}
                      className="hover:bg-[rgba(255,255,255,0.05)] transition-colors cursor-pointer"
                      onClick={() => router.push(`/process/${practice.id}`)}
                    >
                      <td className="px-4 py-3 text-sm font-medium text-[var(--bz-text-1)]">
                        #{practice.id}
                      </td>
                      <td className="px-4 py-3 text-sm text-[var(--bz-text-1)]">
                        {practice.practice_type_code?.toUpperCase().replace(/_/g, ' ') || '-'}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {practice.client_id ? (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              router.push(`/clients/${practice.client_id}`);
                            }}
                            className="text-[var(--bz-text-1)] hover:text-[var(--bz-accent)] transition-colors text-left"
                          >
                            {practice.client_name || 'Unknown'}
                          </button>
                        ) : (
                          <span className="text-[var(--bz-text-1)]">
                            {practice.client_name || 'Unknown'}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {practice.client_lead ? (
                          <div className="inline-flex items-center gap-1.5 bg-[var(--bz-accent)]/10 px-2 py-0.5 rounded text-[var(--bz-accent)]">
                            <User className="w-3 h-3" />
                            <span className="text-[10px] font-medium">
                              {practice.client_lead.split('@')[0]}
                            </span>
                          </div>
                        ) : (
                          <span className="text-[var(--bz-text-2)]">-</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        <div className="inline-flex items-center gap-1.5 flex-wrap">
                          <span
                            className={`w-2 h-2 rounded-full shrink-0 ${
                              {
                                inquiry: 'bg-gray-400',
                                waiting_documents: 'bg-orange-400',
                                sending_invoice: 'bg-yellow-400',
                                // Legacy states mapped to sending_invoice
                                waiting_payment: 'bg-yellow-400',
                                on_process: 'bg-blue-500',
                                // Legacy states mapped to on_process
                                submitted_to_gov: 'bg-blue-500',
                                approved: 'bg-blue-500',
                                completed: 'bg-green-500',
                              }[getStatusColumn(practice.status)] || 'bg-gray-400'
                            }`}
                          />
                          <span className="text-[var(--bz-text-1)]">
                            {practice.status?.replace(/_/g, ' ').charAt(0).toUpperCase() +
                              practice.status?.replace(/_/g, ' ').slice(1) || '-'}
                          </span>
                          {practice.priority === 'urgent' && (
                            <span className="text-[9px] font-bold px-1 py-0.5 rounded bg-red-500/20 text-red-400 uppercase">
                              🔥
                            </span>
                          )}
                          {practice.priority === 'high' && (
                            <span className="text-[9px] font-bold px-1 py-0.5 rounded bg-orange-500/15 text-orange-400 uppercase tracking-wide">
                              ↑hi
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {practice.payment_status ? (
                          <span
                            className={`inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full font-medium ${
                              practice.payment_status === 'paid'
                                ? 'bg-green-500/15 text-green-400'
                                : practice.payment_status === 'partial'
                                  ? 'bg-yellow-500/15 text-yellow-400'
                                  : 'bg-red-500/15 text-red-400'
                            }`}
                          >
                            <span className="w-1.5 h-1.5 rounded-full bg-current" />
                            {practice.payment_status}
                          </span>
                        ) : (
                          <span className="text-[var(--bz-text-2)] text-xs">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-right">
                        {practice.actual_price || practice.quoted_price ? (
                          <span
                            className="font-medium tabular-nums"
                            style={{ color: 'var(--bz-accent)' }}
                          >
                            {new Intl.NumberFormat('id-ID', {
                              notation: 'compact',
                              currency: 'IDR',
                              style: 'currency',
                              maximumFractionDigits: 0,
                            }).format(practice.actual_price || practice.quoted_price || 0)}
                          </span>
                        ) : (
                          <span className="text-[var(--bz-text-2)] text-xs">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        <div
                          className="flex items-center gap-1"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {practice.client_phone && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                const phone = practice.client_phone?.replace(/\D/g, '');
                                window.open(
                                  `https://wa.me/${phone}?text=Hi ${practice.client_name}, regarding your process...`,
                                  '_blank'
                                );
                              }}
                              className="p-1.5 rounded hover:bg-green-500/20 text-green-500 transition-colors"
                              title="WhatsApp"
                            >
                              <MessageCircle className="w-3.5 h-3.5" />
                            </button>
                          )}
                          {practice.client_email && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                window.open(`mailto:${practice.client_email}`, '_blank');
                              }}
                              className="p-1.5 rounded hover:bg-blue-500/20 text-blue-500 transition-colors"
                              title="Email"
                            >
                              <Mail className="w-3.5 h-3.5" />
                            </button>
                          )}
                          <button
                            className="p-1.5 rounded text-[var(--bz-text-2)] hover:text-[var(--bz-text-1)] hover:bg-[rgba(255,255,255,0.1)] transition-colors"
                            onClick={(e) => handleMenuClick(e, practice)}
                            title="More options"
                          >
                            <MoreVertical className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Pagination Controls */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between px-4 py-3 border-t border-[rgba(255,255,255,0.05)] bg-[rgba(35,35,40,0.8)] backdrop-blur-lg">
                  <div className="text-sm text-[var(--bz-text-2)]">
                    Showing {(listPageNumber - 1) * itemsPerPage + 1} to{' '}
                    {Math.min(listPageNumber * itemsPerPage, filteredPractices.length)} of{' '}
                    {filteredPractices.length} process
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setListPageNumber((p) => Math.max(1, p - 1))}
                      disabled={listPageNumber === 1}
                      className="px-3 py-1 rounded-lg border border-[rgba(255,255,255,0.05)] bg-[rgba(45,45,50,0.5)] backdrop-blur-md text-[var(--bz-text-1)] hover:bg-[rgba(65,65,70,0.8)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      Previous
                    </button>
                    <div className="flex items-center gap-2 px-3 py-1">
                      {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                        const pageNum = i + 1;
                        return (
                          <button
                            key={pageNum}
                            onClick={() => setListPageNumber(pageNum)}
                            className={`px-2 py-1 rounded-lg transition-colors ${
                              listPageNumber === pageNum
                                ? 'bg-[var(--bz-accent)] text-white'
                                : 'bg-[rgba(45,45,50,0.5)] backdrop-blur-md text-[var(--bz-text-1)] hover:bg-[rgba(65,65,70,0.8)]'
                            }`}
                          >
                            {pageNum}
                          </button>
                        );
                      })}
                      {totalPages > 5 && <span className="text-[var(--bz-text-2)]">...</span>}
                    </div>
                    <button
                      onClick={() => setListPageNumber((p) => Math.min(totalPages, p + 1))}
                      disabled={listPageNumber === totalPages}
                      className="px-3 py-1 rounded-lg border border-[var(--bz-border)] bg-[var(--bz-surface)] text-[var(--bz-text-1)] hover:bg-[var(--bz-base)] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Info Footer */}
      <div className="text-center py-8">
        <p className="text-xs text-[var(--bz-text-2)]">
          Pro Tip: Right-click or use the menu on cards to quickly change process status.
        </p>
      </div>

      {/* Context Menu for Status Change */}
      {selectedPractice && menuPosition && (
        <div
          ref={menuRef}
          className="fixed z-50 min-w-[200px] rounded-lg border border-[rgba(255,255,255,0.05)] bg-[rgba(30,30,35,0.8)] backdrop-blur-xl shadow-2xl py-1 animate-in fade-in zoom-in-95 duration-100"
          style={{
            // ✅ Smart positioning: adjusts based on viewport boundaries
            // Menu height ~340px (header 40px + 9 items * 32px + padding)
            // Menu width: 220px (min-w-[200px] + padding)
            top:
              menuPosition.y + 340 > window.innerHeight
                ? Math.max(10, menuPosition.y - 340) // Open above if not enough space below
                : menuPosition.y,
            left:
              menuPosition.x + 220 > window.innerWidth
                ? Math.max(10, menuPosition.x - 220) // Open to left if not enough space to right
                : menuPosition.x,
            // Ensure menu never goes offscreen
            maxHeight: 'calc(100vh - 20px)',
            maxWidth: 'calc(100vw - 20px)',
          }}
        >
          <div className="px-3 py-2 border-b border-[rgba(255,255,255,0.05)] bg-[rgba(40,40,45,0.6)] backdrop-blur-md rounded-t-lg">
            <p className="text-xs font-semibold text-[var(--bz-text-1)]">Update Status</p>
            <p className="text-[10px] text-[var(--bz-text-2)]">Process #{selectedPractice.id}</p>
          </div>
          <div className="max-h-[300px] overflow-y-auto p-1 space-y-0.5">
            {STATUS_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => handleStatusChange(selectedPractice.id, option.value)}
                disabled={selectedPractice.status === option.value || updatingId !== null}
                className={`w-full px-3 py-2 text-left text-sm rounded-md transition-colors flex items-center justify-between group ${
                  selectedPractice.status === option.value
                    ? 'bg-[var(--bz-accent)]/10 text-[var(--bz-accent)] font-medium'
                    : 'text-[var(--bz-text-1)] hover:bg-[var(--bz-accent)]/10 hover:text-[var(--bz-accent)]'
                } ${updatingId !== null ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      {
                        inquiry: 'bg-gray-400',
                        waiting_documents: 'bg-orange-400',
                        sending_invoice: 'bg-yellow-400',
                        on_process: 'bg-blue-500',
                        completed: 'bg-green-500',
                      }[option.column] || 'bg-gray-400'
                    }`}
                  />
                  {option.label}
                </div>
                {selectedPractice.status === option.value && (
                  <CheckCircle2 className="w-3.5 h-3.5" />
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
