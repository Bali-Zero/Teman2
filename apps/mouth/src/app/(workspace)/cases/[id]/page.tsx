'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  ArrowLeft, User, Mail, Phone, Calendar, DollarSign,
  Clock, CheckCircle2, AlertCircle, Loader2, FileText,
  MessageCircle, MoreVertical, Edit, Trash2
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api';
import type { Practice } from '@/lib/api/crm/crm.types';
import { casesMetrics } from '@/lib/metrics/cases-metrics';

// Status mapping for display
const STATUS_INFO: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  inquiry: { label: 'Inquiry', color: 'blue', icon: <AlertCircle className="w-4 h-4" /> },
  quotation_sent: { label: 'Quotation Sent', color: 'yellow', icon: <FileText className="w-4 h-4" /> },
  payment_pending: { label: 'Payment Pending', color: 'orange', icon: <DollarSign className="w-4 h-4" /> },
  in_progress: { label: 'In Progress', color: 'purple', icon: <Clock className="w-4 h-4" /> },
  waiting_documents: { label: 'Waiting Documents', color: 'amber', icon: <FileText className="w-4 h-4" /> },
  submitted_to_gov: { label: 'Submitted to Gov', color: 'indigo', icon: <FileText className="w-4 h-4" /> },
  approved: { label: 'Approved', color: 'green', icon: <CheckCircle2 className="w-4 h-4" /> },
  completed: { label: 'Completed', color: 'green', icon: <CheckCircle2 className="w-4 h-4" /> },
};

export default function CaseDetailPage() {
  const router = useRouter();
  const params = useParams();
  const toast = useToast();
  const caseId = params?.id ? parseInt(params.id as string) : null;

  const [practice, setPractice] = useState<Practice | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Edit modal state
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [editForm, setEditForm] = useState({
    status: '',
    priority: '',
    payment_status: '',
    quoted_price: '',
    actual_price: '',
  });

  // Performance tracking
  const startTime = useRef(performance.now());
  const userEmail = useRef<string | null>(null);

  // Track page view and performance on mount
  useEffect(() => {
    const initMetrics = async () => {
      try {
        const user = await api.getProfile();
        userEmail.current = user.email;

        if (caseId) {
          casesMetrics.trackPageView('detail', caseId, user.email);
        }
      } catch (err) {
        console.error('Failed to init metrics:', err);
      }
    };

    initMetrics();
  }, [caseId]);

  useEffect(() => {
    const loadPractice = async () => {
      if (!caseId) {
        setError('Invalid case ID');
        setIsLoading(false);
        casesMetrics.trackError('Invalid Case ID', 'No case ID provided', 'CasesDetailPage', undefined, userEmail.current || undefined);
        return;
      }

      setIsLoading(true);
      setError(null);
      casesMetrics.startPerformanceMark('case_detail_load');
      const apiStart = performance.now();

      try {
        // TODO: Replace with dedicated getPractice(id) API endpoint
        const allPractices = await api.crm.getPractices({ limit: 200 });
        const apiDuration = performance.now() - apiStart;
        casesMetrics.trackApiCall('/api/crm/practices', 'GET', true, apiDuration, caseId, userEmail.current || undefined);

        const foundPractice = allPractices.find(p => p.id === caseId);

        if (!foundPractice) {
          setError('Case not found');
          toast.error('Error', `Case #${caseId} not found`);
          casesMetrics.trackError('Case Not Found', `Case #${caseId} not found`, 'CasesDetailPage', caseId, userEmail.current || undefined);
        } else {
          setPractice(foundPractice);
          casesMetrics.endPerformanceMark('case_detail_load', caseId, userEmail.current || undefined);
        }
      } catch (err) {
        const apiDuration = performance.now() - apiStart;
        casesMetrics.trackApiCall('/api/crm/practices', 'GET', false, apiDuration, caseId, userEmail.current || undefined);

        console.error('Failed to load case:', err);
        setError('Failed to load case details');
        toast.error('Error', 'Failed to load case details');
        casesMetrics.trackError('API Error', (err as Error).message, 'CasesDetailPage', caseId, userEmail.current || undefined);
      } finally {
        setIsLoading(false);
      }
    };

    loadPractice();
  }, [caseId]);

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Not set';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const formatCurrency = (amount?: number) => {
    if (amount === undefined || amount === null) return 'Not set';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
    }).format(amount);
  };

  const handleEditClick = () => {
    if (!practice) return;

    casesMetrics.trackButtonClick('Edit', 'CasesDetailPage', caseId || undefined, undefined, userEmail.current || undefined);
    casesMetrics.trackModal('edit', 'open', caseId || undefined, userEmail.current || undefined);

    setEditForm({
      status: practice.status || '',
      priority: practice.priority || 'normal',
      payment_status: practice.payment_status || 'unpaid',
      quoted_price: practice.quoted_price?.toString() || '',
      actual_price: practice.actual_price?.toString() || '',
    });
    setIsEditModalOpen(true);
  };

  const handleSaveChanges = async () => {
    if (!practice || !caseId) return;
    setIsSaving(true);

    const apiStart = performance.now();

    try {
      const user = await api.getProfile();
      const updates: any = {};

      if (editForm.status && editForm.status !== practice.status) updates.status = editForm.status;
      if (editForm.priority && editForm.priority !== practice.priority) updates.priority = editForm.priority;
      if (editForm.payment_status && editForm.payment_status !== practice.payment_status) updates.payment_status = editForm.payment_status;
      if (editForm.quoted_price && Number(editForm.quoted_price) !== practice.quoted_price) updates.quoted_price = Number(editForm.quoted_price);
      if (editForm.actual_price && Number(editForm.actual_price) !== practice.actual_price) updates.actual_price = Number(editForm.actual_price);

      if (Object.keys(updates).length === 0) {
        toast.error('No Changes', 'No fields were modified.');
        casesMetrics.trackModal('edit', 'close', caseId, user.email);
        setIsEditModalOpen(false);
        setIsSaving(false);
        return;
      }

      const fieldsUpdated = Object.keys(updates);
      const updateType = updates.status ? 'status' : updates.payment_status ? 'payment' : 'details';

      // Log pre-request details
      console.log('[Cases] Attempting to update case:', {
        caseId,
        updates,
        userEmail: user.email,
        fieldsUpdated,
        updateType,
        timestamp: new Date().toISOString(),
      });

      await api.crm.updatePractice(caseId, updates, user.email);
      const apiDuration = performance.now() - apiStart;
      casesMetrics.trackApiCall('/api/crm/practices/update', 'PATCH', true, apiDuration, caseId, user.email);

      // Reload practice data
      const allPractices = await api.crm.getPractices({ limit: 200 });
      const updatedPractice = allPractices.find(p => p.id === caseId);
      if (updatedPractice) {
        setPractice(updatedPractice);
      }

      // Track case update
      casesMetrics.trackCaseUpdate(caseId, fieldsUpdated, updateType, user.email);
      casesMetrics.trackModal('edit', 'submit', caseId, user.email);

      toast.success('Case Updated', 'Successfully updated case details.');
      setIsEditModalOpen(false);
    } catch (err) {
      const apiDuration = performance.now() - apiStart;
      casesMetrics.trackApiCall('/api/crm/practices/update', 'PATCH', false, apiDuration, caseId, userEmail.current || undefined);
      casesMetrics.trackError('Update Failed', (err as Error).message, 'CasesDetailPage', caseId, userEmail.current || undefined);

      // Detailed error logging
      const errorDetails = {
        caseId,
        updates: editForm,
        userEmail: userEmail.current,
        error: err instanceof Error ? {
          message: err.message,
          name: err.name,
          stack: err.stack,
        } : err,
        apiDuration,
        timestamp: new Date().toISOString(),
        endpoint: `/api/crm/practices/${caseId}`,
      };

      console.error('[Cases] Failed to update case details:', errorDetails);

      // Check for specific error types and provide user-friendly messages
      let errorMessage = 'Failed to update case details.';
      if (err instanceof Error) {
        if (err.message.includes('401') || err.message.includes('Unauthorized')) {
          errorMessage = 'Authentication failed. Please login again.';
          console.error('[Cases] Authentication error - user may need to re-authenticate');
        } else if (err.message.includes('403') || err.message.includes('Forbidden')) {
          errorMessage = 'You do not have permission to update this case.';
          console.error('[Cases] Authorization error - user may not have permission');
        } else if (err.message.includes('404') || err.message.includes('Not Found')) {
          errorMessage = 'Case not found. It may have been deleted.';
          console.error('[Cases] Case not found - may have been deleted');
        } else if (err.message.includes('Network') || err.message.includes('fetch')) {
          errorMessage = 'Network error. Please check your connection and try again.';
          console.error('[Cases] Network error - backend may be unreachable');
        } else if (err.message.includes('CORS')) {
          errorMessage = 'CORS error. Please contact support.';
          console.error('[Cases] CORS error - backend CORS configuration may be incorrect');
        }
      }

      toast.error('Error', errorMessage);
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-[var(--accent)] mx-auto mb-4" />
          <p className="text-[var(--foreground-muted)]">Loading case details...</p>
        </div>
      </div>
    );
  }

  if (error || !practice) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold text-[var(--foreground)] mb-2">
            {error || 'Case Not Found'}
          </h2>
          <p className="text-[var(--foreground-muted)] mb-6">
            The case you're looking for doesn't exist or you don't have permission to view it.
          </p>
          <Button onClick={() => router.push('/cases')} variant="default">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Cases
          </Button>
        </div>
      </div>
    );
  }

  const statusInfo = STATUS_INFO[practice.status] || {
    label: practice.status,
    color: 'gray',
    icon: <FileText className="w-4 h-4" />,
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <button
          onClick={() => {
            casesMetrics.trackButtonClick('Back to Cases', 'CasesDetailPage', caseId || undefined, '/cases', userEmail.current || undefined);
            router.push('/cases');
          }}
          className="flex items-center gap-2 text-[var(--foreground-muted)] hover:text-[var(--foreground)] transition-colors mb-4"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Cases</span>
        </button>

        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-3xl font-bold text-[var(--foreground)]">
                {practice.practice_type_code?.toUpperCase().replace(/_/g, ' ') || 'Case'} #{practice.id}
              </h1>
              <div className={`flex items-center gap-2 px-3 py-1 rounded-full bg-${statusInfo.color}-500/10 text-${statusInfo.color}-500`}>
                {statusInfo.icon}
                <span className="text-sm font-medium">{statusInfo.label}</span>
              </div>
            </div>
            <p className="text-[var(--foreground-muted)]">
              {practice.practice_type_name || 'Case Details'}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleEditClick}>
              <Edit className="w-4 h-4 mr-2" />
              Edit
            </Button>
            <Button variant="outline" size="sm">
              <MoreVertical className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Client Information */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]/50 p-6">
            <h2 className="text-xl font-semibold text-[var(--foreground)] mb-4 flex items-center gap-2">
              <User className="w-5 h-5" />
              Client Information
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-[var(--foreground-muted)] mb-1 block">Client Name</label>
                <p className="text-[var(--foreground)] font-medium">{practice.client_name || 'Not specified'}</p>
              </div>

              <div>
                <label className="text-sm text-[var(--foreground-muted)] mb-1 block">Client ID</label>
                <button
                  onClick={() => {
                    casesMetrics.trackButtonClick('Client ID Link', 'CasesDetailPage', caseId || undefined, `/clients/${practice.client_id}`, userEmail.current || undefined);
                    router.push(`/clients/${practice.client_id}`);
                  }}
                  className="text-[var(--accent)] hover:underline font-medium"
                >
                  #{practice.client_id}
                </button>
              </div>

              {practice.client_email && (
                <div>
                  <label className="text-sm text-[var(--foreground-muted)] mb-1 block">Email</label>
                  <a
                    href={`mailto:${practice.client_email}`}
                    onClick={() => casesMetrics.trackQuickAction('email', caseId || 0, 'CasesDetailPage', userEmail.current || undefined)}
                    className="text-[var(--foreground)] hover:text-[var(--accent)] transition-colors flex items-center gap-2"
                  >
                    <Mail className="w-4 h-4" />
                    {practice.client_email}
                  </a>
                </div>
              )}

              {practice.client_phone && (
                <div>
                  <label className="text-sm text-[var(--foreground-muted)] mb-1 block">Phone</label>
                  <a
                    href={`https://wa.me/${practice.client_phone.replace(/\D/g, '')}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={() => casesMetrics.trackQuickAction('whatsapp', caseId || 0, 'CasesDetailPage', userEmail.current || undefined)}
                    className="text-[var(--foreground)] hover:text-[var(--foreground-accent)] transition-colors flex items-center gap-2"
                  >
                    <Phone className="w-4 h-4" />
                    {practice.client_phone}
                  </a>
                </div>
              )}

              {practice.client_lead && (
                <div>
                  <label className="text-sm text-[var(--foreground-muted)] mb-1 block">Lead Team Member</label>
                  <p className="text-[var(--foreground)] font-medium">{practice.client_lead}</p>
                </div>
              )}

              {practice.assigned_to && (
                <div>
                  <label className="text-sm text-[var(--foreground-muted)] mb-1 block">Assigned To</label>
                  <p className="text-[var(--foreground)] font-medium">{practice.assigned_to}</p>
                </div>
              )}
            </div>
          </div>

          {/* Case Details */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]/50 p-6">
            <h2 className="text-xl font-semibold text-[var(--foreground)] mb-4 flex items-center gap-2">
              <FileText className="w-5 h-5" />
              Case Details
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm text-[var(--foreground-muted)] mb-1 block">Status</label>
                <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full bg-${statusInfo.color}-500/10 text-${statusInfo.color}-500`}>
                  {statusInfo.icon}
                  <span className="font-medium">{statusInfo.label}</span>
                </div>
              </div>

              <div>
                <label className="text-sm text-[var(--foreground-muted)] mb-1 block">Priority</label>
                <p className="text-[var(--foreground)] font-medium capitalize">{practice.priority || 'Normal'}</p>
              </div>

              <div>
                <label className="text-sm text-[var(--foreground-muted)] mb-1 block">Payment Status</label>
                <p className="text-[var(--foreground)] font-medium capitalize">{practice.payment_status || 'Not set'}</p>
              </div>

              <div>
                <label className="text-sm text-[var(--foreground-muted)] mb-1 block">Quoted Price</label>
                <p className="text-[var(--foreground)] font-medium">{formatCurrency(practice.quoted_price)}</p>
              </div>

              <div>
                <label className="text-sm text-[var(--foreground-muted)] mb-1 block">Actual Price</label>
                <p className="text-[var(--foreground)] font-medium">{formatCurrency(practice.actual_price)}</p>
              </div>

              <div>
                <label className="text-sm text-[var(--foreground-muted)] mb-1 block">Created</label>
                <p className="text-[var(--foreground)]">{formatDate(practice.created_at)}</p>
              </div>

              {practice.start_date && (
                <div>
                  <label className="text-sm text-[var(--foreground-muted)] mb-1 block">Start Date</label>
                  <p className="text-[var(--foreground)]">{formatDate(practice.start_date)}</p>
                </div>
              )}

              {practice.completion_date && (
                <div>
                  <label className="text-sm text-[var(--foreground-muted)] mb-1 block">Completion Date</label>
                  <p className="text-[var(--foreground)]">{formatDate(practice.completion_date)}</p>
                </div>
              )}

              {practice.expiry_date && (
                <div>
                  <label className="text-sm text-[var(--foreground-muted)] mb-1 block">Expiry Date</label>
                  <p className="text-[var(--foreground)]">{formatDate(practice.expiry_date)}</p>
                </div>
              )}
            </div>
          </div>

          {/* Notes Section - Coming soon */}
          {/* TODO: Add notes field to Practice type and implement notes functionality */}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Quick Actions */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]/50 p-6">
            <h3 className="text-lg font-semibold text-[var(--foreground)] mb-4">Quick Actions</h3>
            <div className="space-y-2">
              {practice.client_phone && (
                <Button
                  variant="outline"
                  className="w-full justify-start"
                  onClick={() => {
                    casesMetrics.trackQuickAction('whatsapp', caseId || 0, 'CasesDetailPage', userEmail.current || undefined);
                    const phone = practice.client_phone?.replace(/\D/g, '');
                    window.open(`https://wa.me/${phone}?text=Hi ${practice.client_name}, regarding your case...`, '_blank');
                  }}
                >
                  <MessageCircle className="w-4 h-4 mr-2" />
                  WhatsApp Client
                </Button>
              )}

              {practice.client_email && (
                <Button
                  variant="outline"
                  className="w-full justify-start"
                  onClick={() => {
                    casesMetrics.trackQuickAction('email', caseId || 0, 'CasesDetailPage', userEmail.current || undefined);
                    window.open(`mailto:${practice.client_email}`, '_blank');
                  }}
                >
                  <Mail className="w-4 h-4 mr-2" />
                  Email Client
                </Button>
              )}

              <Button
                variant="outline"
                className="w-full justify-start"
                onClick={() => {
                  casesMetrics.trackButtonClick('View Client Profile', 'CasesDetailPage', caseId || undefined, `/clients/${practice.client_id}`, userEmail.current || undefined);
                  router.push(`/clients/${practice.client_id}`);
                }}
              >
                <User className="w-4 h-4 mr-2" />
                View Client Profile
              </Button>
            </div>
          </div>

          {/* Timeline Placeholder */}
          <div className="rounded-xl border border-[var(--border)] bg-[var(--background-secondary)]/50 p-6">
            <h3 className="text-lg font-semibold text-[var(--foreground)] mb-4 flex items-center gap-2">
              <Clock className="w-5 h-5" />
              Activity Timeline
            </h3>
            <p className="text-[var(--foreground-muted)] text-sm">
              Timeline feature coming soon...
            </p>
          </div>
        </div>
      </div>

      {/* Edit Modal */}
      {isEditModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[var(--background-secondary)] rounded-xl border border-[var(--border)] shadow-2xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-[var(--border)] flex items-center justify-between sticky top-0 bg-[var(--background-secondary)] z-10">
              <h2 className="text-xl font-bold text-[var(--foreground)]">Edit Case #{practice.id}</h2>
              <button
                onClick={() => setIsEditModalOpen(false)}
                className="text-[var(--foreground-muted)] hover:text-[var(--foreground)] transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Status */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-[var(--foreground)]">Status</label>
                <select
                  value={editForm.status}
                  onChange={(e) => setEditForm(prev => ({ ...prev, status: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50"
                >
                  <option value="inquiry">Inquiry</option>
                  <option value="quotation_sent">Quotation Sent</option>
                  <option value="payment_pending">Payment Pending</option>
                  <option value="in_progress">In Progress</option>
                  <option value="waiting_documents">Waiting Documents</option>
                  <option value="submitted_to_gov">Submitted to Gov</option>
                  <option value="approved">Approved</option>
                  <option value="completed">Completed</option>
                </select>
              </div>

              {/* Priority */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-[var(--foreground)]">Priority</label>
                <select
                  value={editForm.priority}
                  onChange={(e) => setEditForm(prev => ({ ...prev, priority: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50"
                >
                  <option value="low">Low</option>
                  <option value="normal">Normal</option>
                  <option value="high">High</option>
                  <option value="urgent">Urgent</option>
                </select>
              </div>

              {/* Payment Status */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-[var(--foreground)]">Payment Status</label>
                <select
                  value={editForm.payment_status}
                  onChange={(e) => setEditForm(prev => ({ ...prev, payment_status: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50"
                >
                  <option value="unpaid">Unpaid</option>
                  <option value="partial">Partial</option>
                  <option value="paid">Paid</option>
                </select>
              </div>

              {/* Quoted Price */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-[var(--foreground)]">Quoted Price (USD)</label>
                <input
                  type="number"
                  value={editForm.quoted_price}
                  onChange={(e) => setEditForm(prev => ({ ...prev, quoted_price: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50"
                  placeholder="0.00"
                  step="0.01"
                />
              </div>

              {/* Actual Price */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-[var(--foreground)]">Actual Price (USD)</label>
                <input
                  type="number"
                  value={editForm.actual_price}
                  onChange={(e) => setEditForm(prev => ({ ...prev, actual_price: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/50"
                  placeholder="0.00"
                  step="0.01"
                />
              </div>
            </div>

            <div className="p-6 border-t border-[var(--border)] flex justify-end gap-3 sticky bottom-0 bg-[var(--background-secondary)]">
              <Button variant="outline" onClick={() => setIsEditModalOpen(false)} disabled={isSaving}>
                Cancel
              </Button>
              <Button
                className="bg-[var(--accent)] hover:bg-[var(--accent)]/90 text-white"
                onClick={handleSaveChanges}
                disabled={isSaving}
              >
                {isSaving ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4 mr-2" />
                    Save Changes
                  </>
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
