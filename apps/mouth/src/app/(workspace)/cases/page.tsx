'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { 
  FolderKanban, Search, Filter, Plus, LayoutGrid, List, 
  ChevronRight, Loader2, User, MessageCircle, Mail, Phone, 
  FileText, MoreVertical, CheckCircle2
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api';
import type { Practice } from '@/lib/api/crm/crm.types';

type CaseStatus = 'inquiry' | 'quotation' | 'in_progress' | 'completed';

// Backend status values mapped to frontend display names
const STATUS_OPTIONS: { value: string; label: string; column: CaseStatus }[] = [
  { value: 'inquiry', label: 'Inquiry', column: 'inquiry' },
  { value: 'quotation_sent', label: 'Quotation Sent', column: 'quotation' },
  { value: 'payment_pending', label: 'Payment Pending', column: 'quotation' },
  { value: 'in_progress', label: 'In Progress', column: 'in_progress' },
  { value: 'waiting_documents', label: 'Waiting Documents', column: 'in_progress' },
  { value: 'submitted_to_gov', label: 'Submitted to Gov', column: 'in_progress' },
  { value: 'approved', label: 'Approved', column: 'completed' },
  { value: 'completed', label: 'Completed', column: 'completed' },
];

export default function PratichePage() {
  const router = useRouter();
  const toast = useToast();
  const [practices, setPractices] = useState<Practice[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  
  // Context Menu State
  const [selectedPractice, setSelectedPractice] = useState<Practice | null>(null);
  const [menuPosition, setMenuPosition] = useState<{ x: number; y: number } | null>(null);
  const [updatingId, setUpdatingId] = useState<number | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const loadPractices = async () => {
      setIsLoading(true);
      try {
        const data = await api.crm.getPractices({ limit: 100 });
        setPractices(data);
      } catch (error) {
        console.error('Failed to load practices:', error);
        toast.error('Error', 'Failed to load cases');
      } finally {
        setIsLoading(false);
      }
    };

    loadPractices();
  }, []);

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
      await api.crm.updatePractice(practiceId, { status: newStatus }, user.email);
      
      // Update local state immediately for responsiveness
      setPractices(prev => prev.map(p => 
        p.id === practiceId ? { ...p, status: newStatus } : p
      ));
      
      toast.success('Status Updated', `Case moved to ${newStatus.replace(/_/g, ' ')}`);
      
      setSelectedPractice(null);
      setMenuPosition(null);
    } catch (error) {
      console.error('Failed to update status:', error);
      toast.error('Error', 'Failed to update case status');
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
    router.push('/cases/new');
  };

  const getStatusColumn = (status: string): CaseStatus => {
    if (status === 'inquiry' || status === 'request') return 'inquiry';
    if (status === 'quotation_sent' || status === 'payment_pending' || status === 'quotation' || status === 'quote') return 'quotation';
    if (status === 'in_progress' || status === 'waiting_documents' || status === 'submitted_to_gov' || status === 'active') return 'in_progress';
    if (status === 'completed' || status === 'approved' || status === 'done') return 'completed';
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

  const SkeletonCard = () => (
    <div className="p-3 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] space-y-2">
      <div className="h-4 bg-[var(--background-secondary)] rounded w-3/4 animate-pulse" />
      <div className="h-3 bg-[var(--background-secondary)] rounded w-1/2 animate-pulse" />
      <div className="flex gap-2 pt-2 border-t border-[var(--border)]">
        <div className="h-6 w-6 bg-[var(--background-secondary)] rounded animate-pulse" />
        <div className="h-6 w-6 bg-[var(--background-secondary)] rounded animate-pulse" />
      </div>
    </div>
  );

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
        <Button className="gap-2 bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white" onClick={handleNewCase}>
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
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] text-[var(--foreground)] placeholder:text-[var(--foreground-muted)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50 transition-all"
          />
        </div>
        <div className="flex gap-2">
          <Button variant="outline" className="gap-2 border-[var(--border)] bg-[var(--background-secondary)] text-[var(--foreground)]">
            <Filter className="w-4 h-4" />
            Filters
          </Button>
          <div className="flex rounded-lg border border-[var(--border)] bg-[var(--background-secondary)] overflow-hidden">
            <button className="p-2 bg-[var(--accent)]/10 text-[var(--accent)]">
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button className="p-2 text-[var(--foreground-muted)] hover:bg-[var(--background-elevated)] transition-colors">
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
              className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]/50 p-4 flex flex-col h-full min-h-[500px]"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${
                    idx === 0 ? 'bg-blue-500' : 
                    idx === 1 ? 'bg-yellow-500' : 
                    idx === 2 ? 'bg-purple-500' : 
                    'bg-green-500'
                  }`} />
                  <h3 className="font-semibold text-[var(--foreground)]">{column}</h3>
                </div>
                <span className="text-xs px-2 py-1 rounded-full bg-[var(--background-elevated)] text-[var(--foreground-muted)]">
                  {columnPractices.length}
                </span>
              </div>
              
              <div className="flex-1 space-y-3">
                {isLoading ? (
                  <>
                    <SkeletonCard />
                    <SkeletonCard />
                    <SkeletonCard />
                  </>
                ) : columnPractices.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-32 border border-dashed border-[var(--border)] rounded-lg bg-[var(--background-elevated)]/30">
                    <FolderKanban className="w-8 h-8 text-[var(--foreground-muted)] opacity-20 mb-2" />
                    <p className="text-xs text-[var(--foreground-muted)]">No cases</p>
                  </div>
                ) : (
                  columnPractices.map((practice) => (
                    <div
                      key={practice.id}
                      className={`p-3 rounded-lg border bg-[var(--background-elevated)] cursor-pointer transition-all hover:shadow-md relative group ${
                        updatingId === practice.id ? 'opacity-70 pointer-events-none' : ''
                      } ${
                        selectedPractice?.id === practice.id
                          ? 'border-[var(--accent)] ring-1 ring-[var(--accent)]/30'
                          : 'border-[var(--border)] hover:border-[var(--accent)]/30'
                      }`}
                      onClick={() => router.push(`/cases/${practice.id}`)}
                    >
                      {updatingId === practice.id && (
                        <div className="absolute inset-0 flex items-center justify-center bg-[var(--background-elevated)]/80 rounded-lg z-10">
                          <Loader2 className="w-5 h-5 animate-spin text-[var(--accent)]" />
                        </div>
                      )}
                      
                      {/* Card Header */}
                      <div className="flex items-start justify-between mb-1">
                        <p className="text-sm font-medium text-[var(--foreground)] line-clamp-2 pr-6">
                          {practice.practice_type_code?.toUpperCase().replace(/_/g, ' ') || 'Case'}
                        </p>
                        
                        {/* 3-Dot Menu Trigger */}
                        <button
                          className="absolute top-3 right-2 p-1 rounded-md text-[var(--foreground-muted)] hover:text-[var(--foreground)] hover:bg-[var(--background-secondary)] opacity-0 group-hover:opacity-100 transition-opacity"
                          onClick={(e) => handleMenuClick(e, practice)}
                        >
                          <MoreVertical className="w-4 h-4" />
                        </button>
                      </div>

                      <p className="text-xs text-[var(--foreground-muted)] truncate mb-2">
                        {practice.client_name || 'Unknown Client'}
                      </p>
                      
                      <div className="flex items-center justify-between">
                        {practice.client_lead ? (
                          <div className="flex items-center gap-1.5 bg-[var(--accent)]/10 px-2 py-0.5 rounded text-[var(--accent)]">
                            <User className="w-3 h-3" />
                            <p className="text-[10px] font-medium truncate max-w-[80px]">
                              {practice.client_lead.split('@')[0]}
                            </p>
                          </div>
                        ) : (
                          <div />
                        )}
                        <span className="text-[10px] text-[var(--foreground-muted)]">
                          #{practice.id}
                        </span>
                      </div>

                      {/* Quick Actions */}
                      <div className="flex items-center gap-1 mt-3 pt-2 border-t border-[var(--border)]">
                        {practice.client_phone && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              const phone = practice.client_phone?.replace(/\D/g, '');
                              window.open(`https://wa.me/${phone}?text=Hi ${practice.client_name}, regarding your case...`, '_blank');
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
                            router.push(`/clients/${practice.client_id}`);
                          }}
                          className="p-1.5 rounded hover:bg-orange-500/20 text-orange-500 transition-colors ml-auto"
                          title="View Client"
                        >
                          <FileText className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Info Footer */}
      <div className="text-center py-8">
        <p className="text-xs text-[var(--foreground-muted)]">
          Pro Tip: Right-click or use the menu on cards to quickly change case status.
        </p>
      </div>

      {/* Context Menu for Status Change */}
      {selectedPractice && menuPosition && (
        <div
          ref={menuRef}
          className="fixed z-50 min-w-[200px] rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] shadow-xl py-1 animate-in fade-in zoom-in-95 duration-100"
          style={{
            top: Math.min(menuPosition.y, window.innerHeight - 300),
            left: Math.min(menuPosition.x, window.innerWidth - 220),
          }}
        >
          <div className="px-3 py-2 border-b border-[var(--border)] bg-[var(--background-secondary)]/50 rounded-t-lg">
            <p className="text-xs font-semibold text-[var(--foreground)]">
              Update Status
            </p>
            <p className="text-[10px] text-[var(--foreground-muted)]">
              Case #{selectedPractice.id}
            </p>
          </div>
          <div className="max-h-[300px] overflow-y-auto p-1 space-y-0.5">
            {STATUS_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => handleStatusChange(selectedPractice.id, option.value)}
                disabled={selectedPractice.status === option.value || updatingId !== null}
                className={`w-full px-3 py-2 text-left text-sm rounded-md transition-colors flex items-center justify-between group ${
                  selectedPractice.status === option.value
                    ? 'bg-[var(--accent)]/10 text-[var(--accent)] font-medium'
                    : 'text-[var(--foreground)] hover:bg-[var(--accent)]/10 hover:text-[var(--accent)]'
                } ${updatingId !== null ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`w-2 h-2 rounded-full ${
                      option.column === 'inquiry'
                        ? 'bg-blue-500'
                        : option.column === 'quotation'
                        ? 'bg-yellow-500'
                        : option.column === 'in_progress'
                        ? 'bg-purple-500'
                        : 'bg-green-500'
                    }`}
                  />
                  {option.label}
                </div>
                {selectedPractice.status === option.value && <CheckCircle2 className="w-3.5 h-3.5" />}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
