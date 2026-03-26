'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  ArrowLeft,
  User,
  Mail,
  Phone,
  Calendar,
  DollarSign,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2,
  FileText,
  MessageCircle,
  MoreVertical,
  Edit,
  Trash2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api';
import type { Practice } from '@/lib/api/crm/crm.types';
import { casesMetrics } from '@/lib/metrics/cases-metrics';
import { logger } from '@/lib/logger';
import { toError } from '@/lib/types/common';
import { RequiredDocumentsCard } from './RequiredDocumentsCard';

// Status mapping for display — use static classes for Tailwind JIT compatibility
const STATUS_INFO: Record<string, { label: string; badgeClass: string; icon: React.ReactNode }> = {
  inquiry: {
    label: 'Inquiry',
    badgeClass: 'bg-blue-500/10 text-blue-500',
    icon: <AlertCircle className="w-4 h-4" />,
  },
  waiting_documents: {
    label: 'Waiting Documents',
    badgeClass: 'bg-amber-500/10 text-amber-500',
    icon: <FileText className="w-4 h-4" />,
  },
  sending_invoice: {
    label: 'Sending Invoice',
    badgeClass: 'bg-orange-500/10 text-orange-500',
    icon: <DollarSign className="w-4 h-4" />,
  },
  on_process: {
    label: 'On Process',
    badgeClass: 'bg-purple-500/10 text-purple-500',
    icon: <Clock className="w-4 h-4" />,
  },
  completed: {
    label: 'Completed',
    badgeClass: 'bg-green-500/10 text-green-500',
    icon: <CheckCircle2 className="w-4 h-4" />,
  },
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

  // Inline payment status update
  const [isUpdatingPayment, setIsUpdatingPayment] = useState(false);

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
        logger.error(
          'Failed to init metrics',
          { component: 'CaseDetail', action: 'initMetrics' },
          toError(err)
        );
      }
    };

    initMetrics();
  }, [caseId]);

  useEffect(() => {
    const loadPractice = async () => {
      if (!caseId) {
        setError('Invalid process ID');
        setIsLoading(false);
        casesMetrics.trackError(
          'Invalid Case ID',
          'No case ID provided',
          'CasesDetailPage',
          undefined,
          userEmail.current || undefined
        );
        return;
      }

      setIsLoading(true);
      setError(null);
      casesMetrics.startPerformanceMark('case_detail_load');
      const apiStart = performance.now();

      try {
        // ✅ Using dedicated GET endpoint for single practice (efficient: 1 query instead of loading 200 practices)
        const foundPractice = await api.crm.getPractice(caseId);
        const apiDuration = performance.now() - apiStart;
        casesMetrics.trackApiCall(
          `/api/crm/practices/${caseId}`,
          'GET',
          true,
          apiDuration,
          caseId,
          userEmail.current || undefined
        );

        setPractice(foundPractice);
        casesMetrics.endPerformanceMark('case_detail_load', caseId, userEmail.current || undefined);
      } catch (err) {
        const apiDuration = performance.now() - apiStart;
        casesMetrics.trackApiCall(
          `/api/crm/practices/${caseId}`,
          'GET',
          false,
          apiDuration,
          caseId,
          userEmail.current || undefined
        );

        logger.error(
          'Failed to load process',
          { component: 'CaseDetail', action: 'loadProcess' },
          toError(err)
        );
        setError('Failed to load process details');
        toast.error('Error', 'Failed to load process details');
        casesMetrics.trackError(
          'API Error',
          (err as Error).message,
          'CasesDetailPage',
          caseId,
          userEmail.current || undefined
        );
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
    return new Intl.NumberFormat('id-ID', {
      style: 'currency',
      currency: 'IDR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const cyclePaymentStatus = async () => {
    if (!practice || !caseId || isUpdatingPayment) return;
    const cycle: string[] = ['unpaid', 'partial', 'paid'];
    const current = practice.payment_status || 'unpaid';
    const nextIndex = (cycle.indexOf(current) + 1) % cycle.length;
    const nextStatus = cycle[nextIndex];
    setIsUpdatingPayment(true);
    try {
      const user = await api.getProfile();
      await api.crm.updatePractice(caseId, { payment_status: nextStatus }, user.email);
      setPractice((prev) => prev ? { ...prev, payment_status: nextStatus } : prev);
      toast.success('Payment status updated', `→ ${nextStatus}`);
    } catch (err) {
      toast.error('Failed to update payment status', (err as Error).message);
    } finally {
      setIsUpdatingPayment(false);
    }
  };

  const handleEditClick = () => {
    if (!practice) return;

    casesMetrics.trackButtonClick(
      'Edit',
      'CasesDetailPage',
      caseId || undefined,
      undefined,
      userEmail.current || undefined
    );
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
      const updates: Partial<
        Pick<Practice, 'status' | 'priority' | 'payment_status' | 'quoted_price' | 'actual_price'>
      > = {};

      if (editForm.status && editForm.status !== practice.status) updates.status = editForm.status;
      if (editForm.priority && editForm.priority !== practice.priority)
        updates.priority = editForm.priority;
      if (editForm.payment_status && editForm.payment_status !== practice.payment_status)
        updates.payment_status = editForm.payment_status;
      if (editForm.quoted_price && Number(editForm.quoted_price) !== practice.quoted_price)
        updates.quoted_price = Number(editForm.quoted_price);
      if (editForm.actual_price && Number(editForm.actual_price) !== practice.actual_price)
        updates.actual_price = Number(editForm.actual_price);

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
      logger.info(`Attempting to update case ${caseId}`, {
        component: 'CaseDetail',
        action: 'updateCase',
        user: user.email,
      });

      await api.crm.updatePractice(caseId, updates, user.email);
      const apiDuration = performance.now() - apiStart;
      casesMetrics.trackApiCall(
        '/api/crm/practices/update',
        'PATCH',
        true,
        apiDuration,
        caseId,
        user.email
      );

      // Reload practice data with dedicated endpoint
      const updatedPractice = await api.crm.getPractice(caseId);
      setPractice(updatedPractice);

      // Track case update
      casesMetrics.trackCaseUpdate(caseId, fieldsUpdated, updateType, user.email);
      casesMetrics.trackModal('edit', 'submit', caseId, user.email);

      toast.success('Process Updated', 'Successfully updated process details.');
      setIsEditModalOpen(false);
    } catch (err) {
      const apiDuration = performance.now() - apiStart;
      casesMetrics.trackApiCall(
        '/api/crm/practices/update',
        'PATCH',
        false,
        apiDuration,
        caseId,
        userEmail.current || undefined
      );
      casesMetrics.trackError(
        'Update Failed',
        (err as Error).message,
        'CasesDetailPage',
        caseId,
        userEmail.current || undefined
      );

      // Detailed error logging
      const errorDetails = {
        caseId,
        updates: editForm,
        userEmail: userEmail.current,
        error:
          err instanceof Error
            ? {
                message: err.message,
                name: err.name,
                stack: err.stack,
              }
            : err,
        apiDuration,
        timestamp: new Date().toISOString(),
        endpoint: `/api/crm/practices/${caseId}`,
      };

      logger.error(
        'Failed to update case details',
        { component: 'CaseDetail', action: 'updateCase' },
        toError(err)
      );

      // Check for specific error types and provide user-friendly messages
      let errorMessage = 'Failed to update process details.';
      if (err instanceof Error) {
        if (err.message.includes('401') || err.message.includes('Unauthorized')) {
          errorMessage = 'Authentication failed. Please login again.';
          logger.error('Authentication error - user may need to re-authenticate', {
            component: 'CaseDetail',
            action: 'updateCase',
          });
        } else if (err.message.includes('403') || err.message.includes('Forbidden')) {
          errorMessage = 'You do not have permission to update this process.';
          logger.error('Authorization error - user may not have permission', {
            component: 'CaseDetail',
            action: 'updateCase',
          });
        } else if (err.message.includes('404') || err.message.includes('Not Found')) {
          errorMessage = 'Process not found. It may have been deleted.';
          logger.error('Case not found - may have been deleted', {
            component: 'CaseDetail',
            action: 'updateCase',
          });
        } else if (err.message.includes('Network') || err.message.includes('fetch')) {
          errorMessage = 'Network error. Please check your connection and try again.';
          logger.error('Network error - backend may be unreachable', {
            component: 'CaseDetail',
            action: 'updateCase',
          });
        } else if (err.message.includes('CORS')) {
          errorMessage = 'CORS error. Please contact support.';
          logger.error('CORS error - backend CORS configuration may be incorrect', {
            component: 'CaseDetail',
            action: 'updateCase',
          });
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
          <Loader2
            className="w-12 h-12 animate-spin mx-auto mb-4"
            style={{ color: 'var(--bz-accent)' }}
          />
          <p style={{ color: 'var(--bz-text-2)' }}>Loading process details...</p>
        </div>
      </div>
    );
  }

  if (error || !practice) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-2xl font-bold mb-2" style={{ color: 'var(--bz-text-1)' }}>
            {error || 'Process Not Found'}
          </h2>
          <p className="mb-6" style={{ color: 'var(--bz-text-2)' }}>
            The process you're looking for doesn't exist or you don't have permission to view it.
          </p>
          <Button onClick={() => router.push('/process')} variant="default">
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Process
          </Button>
        </div>
      </div>
    );
  }

  const statusInfo = STATUS_INFO[practice.status] || {
    label: practice.status,
    badgeClass: 'bg-gray-500/10 text-gray-400',
    icon: <FileText className="w-4 h-4" />,
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-4">
          <button
            onClick={() => {
              casesMetrics.trackButtonClick(
                'Back to Process',
                'CasesDetailPage',
                caseId || undefined,
                '/process',
                userEmail.current || undefined
              );
              router.back();
            }}
            className="flex items-center gap-2 transition-colors"
            style={{ color: 'var(--bz-text-2)' }}
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Back</span>
          </button>
          {practice.client_id && (
            <>
              <span style={{ color: 'var(--bz-text-2)' }} className="opacity-30">
                /
              </span>
              <button
                onClick={() => router.push(`/clients/${practice.client_id}?tab=process`)}
                className="flex items-center gap-1.5 transition-colors text-sm"
                style={{ color: 'var(--bz-text-2)' }}
              >
                <User className="w-3.5 h-3.5" />
                <span>{practice.client_name || `Client #${practice.client_id}`}</span>
              </button>
            </>
          )}
        </div>

        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <h1 className="text-3xl font-bold" style={{ color: 'var(--bz-text-1)' }}>
                {practice.practice_type_code?.toUpperCase().replace(/_/g, ' ') || 'Process'} #
                {practice.id}
              </h1>
              <div
                className={`flex items-center gap-2 px-3 py-1 rounded-full ${statusInfo.badgeClass}`}
              >
                {statusInfo.icon}
                <span className="text-sm font-medium">{statusInfo.label}</span>
              </div>
            </div>
            <p style={{ color: 'var(--bz-text-2)' }}>
              {practice.practice_type_name || 'Process Details'}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={handleEditClick}>
              <Edit className="w-4 h-4 mr-2" />
              Edit
            </Button>
            <Button variant="outline" size="sm" aria-label="More options">
              <MoreVertical className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Client Information */}
          <div
            className="rounded-xl p-6"
            style={{
              border: '1px solid var(--bz-border)',
              background: 'rgba(26,26,30,0.5)',
            }}
          >
            <h2
              className="text-xl font-semibold mb-4 flex items-center gap-2"
              style={{ color: 'var(--bz-text-1)' }}
            >
              <User className="w-5 h-5" />
              Client Information
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm mb-1 block" style={{ color: 'var(--bz-text-2)' }}>
                  Client Name
                </label>
                <button
                  onClick={() => {
                    casesMetrics.trackButtonClick(
                      'Client Name Link',
                      'CasesDetailPage',
                      caseId || undefined,
                      `/clients/${practice.client_id}`,
                      userEmail.current || undefined
                    );
                    router.push(`/clients/${practice.client_id}`);
                  }}
                  className="hover:underline font-medium text-left transition-colors"
                  style={{ color: 'var(--bz-text-1)' }}
                >
                  {practice.client_name || 'Not specified'}
                </button>
              </div>

              <div>
                <label className="text-sm mb-1 block" style={{ color: 'var(--bz-text-2)' }}>
                  Client ID
                </label>
                <button
                  onClick={() => {
                    casesMetrics.trackButtonClick(
                      'Client ID Link',
                      'CasesDetailPage',
                      caseId || undefined,
                      `/clients/${practice.client_id}`,
                      userEmail.current || undefined
                    );
                    router.push(`/clients/${practice.client_id}`);
                  }}
                  className="hover:underline font-medium"
                  style={{ color: 'var(--bz-accent)' }}
                >
                  #{practice.client_id}
                </button>
              </div>

              {practice.client_email && (
                <div>
                  <label className="text-sm mb-1 block" style={{ color: 'var(--bz-text-2)' }}>
                    Email
                  </label>
                  <a
                    href={`mailto:${practice.client_email}`}
                    onClick={() =>
                      casesMetrics.trackQuickAction(
                        'email',
                        caseId || 0,
                        'CasesDetailPage',
                        userEmail.current || undefined
                      )
                    }
                    className="transition-colors flex items-center gap-2"
                    style={{ color: 'var(--bz-text-1)' }}
                  >
                    <Mail className="w-4 h-4" />
                    {practice.client_email}
                  </a>
                </div>
              )}

              {practice.client_phone && (
                <div>
                  <label className="text-sm mb-1 block" style={{ color: 'var(--bz-text-2)' }}>
                    Phone
                  </label>
                  <a
                    href={`https://wa.me/${practice.client_phone.replace(/\D/g, '')}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={() =>
                      casesMetrics.trackQuickAction(
                        'whatsapp',
                        caseId || 0,
                        'CasesDetailPage',
                        userEmail.current || undefined
                      )
                    }
                    className="transition-colors flex items-center gap-2"
                    style={{ color: 'var(--bz-text-1)' }}
                  >
                    <Phone className="w-4 h-4" />
                    {practice.client_phone}
                  </a>
                </div>
              )}

              {practice.client_lead && (
                <div>
                  <label className="text-sm mb-1 block" style={{ color: 'var(--bz-text-2)' }}>
                    Lead Team Member
                  </label>
                  <p className="font-medium" style={{ color: 'var(--bz-text-1)' }}>
                    {practice.client_lead}
                  </p>
                </div>
              )}

              {practice.assigned_to && (
                <div>
                  <label className="text-sm mb-1 block" style={{ color: 'var(--bz-text-2)' }}>
                    Assigned To
                  </label>
                  <p className="font-medium" style={{ color: 'var(--bz-text-1)' }}>
                    {practice.assigned_to}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Process Details */}
          <div
            className="rounded-xl p-6"
            style={{
              border: '1px solid var(--bz-border)',
              background: 'rgba(26,26,30,0.5)',
            }}
          >
            <h2
              className="text-xl font-semibold mb-4 flex items-center gap-2"
              style={{ color: 'var(--bz-text-1)' }}
            >
              <FileText className="w-5 h-5" />
              Process Details
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm mb-1 block" style={{ color: 'var(--bz-text-2)' }}>
                  Status
                </label>
                <div
                  className={`inline-flex items-center gap-2 px-3 py-1 rounded-full ${statusInfo.badgeClass}`}
                >
                  {statusInfo.icon}
                  <span className="font-medium">{statusInfo.label}</span>
                </div>
              </div>

              <div>
                <label className="text-sm mb-1 block" style={{ color: 'var(--bz-text-2)' }}>
                  Priority
                </label>
                <p className="font-medium capitalize" style={{ color: 'var(--bz-text-1)' }}>
                  {practice.priority || 'Normal'}
                </p>
              </div>

              <div>
                <label className="text-sm mb-1 block" style={{ color: 'var(--bz-text-2)' }}>
                  Payment Status
                </label>
                <button
                  onClick={cyclePaymentStatus}
                  disabled={isUpdatingPayment}
                  title="Click to cycle: unpaid → partial → paid"
                  className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium transition-colors cursor-pointer ${
                    practice.payment_status === 'paid'
                      ? 'bg-green-500/15 text-green-400 hover:bg-green-500/25'
                      : practice.payment_status === 'partial'
                        ? 'bg-yellow-500/15 text-yellow-400 hover:bg-yellow-500/25'
                        : 'bg-red-500/15 text-red-400 hover:bg-red-500/25'
                  }`}
                >
                  {isUpdatingPayment ? (
                    <Loader2 className="w-3 h-3 animate-spin" />
                  ) : (
                    <span className="w-1.5 h-1.5 rounded-full bg-current" />
                  )}
                  <span className="capitalize">{practice.payment_status || 'unpaid'}</span>
                </button>
              </div>

              <div>
                <label className="text-sm mb-1 block" style={{ color: 'var(--bz-text-2)' }}>
                  Quoted Price
                </label>
                <p className="font-medium" style={{ color: 'var(--bz-text-1)' }}>
                  {formatCurrency(practice.quoted_price)}
                </p>
              </div>

              <div>
                <label className="text-sm mb-1 block" style={{ color: 'var(--bz-text-2)' }}>
                  Actual Price
                </label>
                <p className="font-medium" style={{ color: 'var(--bz-text-1)' }}>
                  {formatCurrency(practice.actual_price)}
                </p>
              </div>

              <div>
                <label className="text-sm mb-1 block" style={{ color: 'var(--bz-text-2)' }}>
                  Created
                </label>
                <p style={{ color: 'var(--bz-text-1)' }}>{formatDate(practice.created_at)}</p>
              </div>

              {practice.start_date && (
                <div>
                  <label className="text-sm mb-1 block" style={{ color: 'var(--bz-text-2)' }}>
                    Start Date
                  </label>
                  <p style={{ color: 'var(--bz-text-1)' }}>{formatDate(practice.start_date)}</p>
                </div>
              )}

              {practice.completion_date && (
                <div>
                  <label className="text-sm mb-1 block" style={{ color: 'var(--bz-text-2)' }}>
                    Completion Date
                  </label>
                  <p style={{ color: 'var(--bz-text-1)' }}>
                    {formatDate(practice.completion_date)}
                  </p>
                </div>
              )}

              {practice.expiry_date && (
                <div>
                  <label className="text-sm mb-1 block" style={{ color: 'var(--bz-text-2)' }}>
                    Expiry Date
                  </label>
                  <p style={{ color: 'var(--bz-text-1)' }}>{formatDate(practice.expiry_date)}</p>
                </div>
              )}
            </div>
          </div>

          {/* Notes Section - Coming soon */}
          {/* Feature: Notes functionality - Tracked in backlog */}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Quick Actions */}
          <div
            className="rounded-xl p-6"
            style={{
              border: '1px solid var(--bz-border)',
              background: 'rgba(26,26,30,0.5)',
            }}
          >
            <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--bz-text-1)' }}>
              Quick Actions
            </h3>
            <div className="space-y-2">
              {practice.client_phone && (
                <Button
                  variant="outline"
                  className="w-full justify-start"
                  onClick={() => {
                    casesMetrics.trackQuickAction(
                      'whatsapp',
                      caseId || 0,
                      'CasesDetailPage',
                      userEmail.current || undefined
                    );
                    const phone = practice.client_phone?.replace(/\D/g, '');
                    window.open(
                      `https://wa.me/${phone}?text=Hi ${practice.client_name}, regarding your process...`,
                      '_blank'
                    );
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
                    casesMetrics.trackQuickAction(
                      'email',
                      caseId || 0,
                      'CasesDetailPage',
                      userEmail.current || undefined
                    );
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
                  casesMetrics.trackButtonClick(
                    'View Client Profile',
                    'CasesDetailPage',
                    caseId || undefined,
                    `/clients/${practice.client_id}`,
                    userEmail.current || undefined
                  );
                  router.push(`/clients/${practice.client_id}`);
                }}
              >
                <User className="w-4 h-4 mr-2" />
                View Client Profile
              </Button>
            </div>
          </div>

          {/* Required Documents */}
          {caseId && <RequiredDocumentsCard practiceId={caseId} />}

          {/* Status History */}
          {practice.status_transitions && practice.status_transitions.length > 0 && (
            <div
              className="rounded-xl p-6"
              style={{
                border: '1px solid var(--bz-border)',
                background: 'rgba(26,26,30,0.5)',
              }}
            >
              <h3
                className="text-lg font-semibold mb-4 flex items-center gap-2"
                style={{ color: 'var(--bz-text-1)' }}
              >
                <Clock className="w-5 h-5" />
                Status History
              </h3>
              <div className="space-y-2">
                {[...practice.status_transitions].reverse().map((t, idx) => (
                  <div key={idx} className="flex items-center justify-between text-sm">
                    <span
                      className="capitalize font-medium"
                      style={{ color: 'var(--bz-text-1)' }}
                    >
                      {t.status.replace(/_/g, ' ')}
                    </span>
                    <span className="text-xs" style={{ color: 'var(--bz-text-2)' }}>
                      {formatDate(t.at)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Edit Modal */}
      {isEditModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div
            className="rounded-xl shadow-2xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto"
            style={{
              background: 'var(--bz-surface)',
              border: '1px solid var(--bz-border)',
            }}
          >
            <div
              className="p-6 flex items-center justify-between sticky top-0 z-10"
              style={{
                borderBottom: '1px solid var(--bz-border)',
                background: 'var(--bz-surface)',
              }}
            >
              <h2 className="text-xl font-bold" style={{ color: 'var(--bz-text-1)' }}>
                Edit Process #{practice.id}
              </h2>
              <button
                onClick={() => setIsEditModalOpen(false)}
                className="transition-colors"
                style={{ color: 'var(--bz-text-2)' }}
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Status */}
              <div className="space-y-2">
                <label className="text-sm font-medium" style={{ color: 'var(--bz-text-1)' }}>
                  Status
                </label>
                <select
                  value={editForm.status}
                  onChange={(e) => setEditForm((prev) => ({ ...prev, status: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg focus:outline-none"
                  style={{
                    border: '1px solid var(--bz-border)',
                    background: 'var(--bz-card)',
                    color: 'var(--bz-text-1)',
                  }}
                >
                  <option value="inquiry">Inquiry</option>
                  <option value="waiting_documents">Waiting Documents</option>
                  <option value="sending_invoice">Sending Invoice</option>
                  <option value="on_process">On Process</option>
                  <option value="completed">Completed</option>
                </select>
              </div>

              {/* Priority */}
              <div className="space-y-2">
                <label className="text-sm font-medium" style={{ color: 'var(--bz-text-1)' }}>
                  Priority
                </label>
                <select
                  value={editForm.priority}
                  onChange={(e) =>
                    setEditForm((prev) => ({
                      ...prev,
                      priority: e.target.value,
                    }))
                  }
                  className="w-full px-3 py-2 rounded-lg focus:outline-none"
                  style={{
                    border: '1px solid var(--bz-border)',
                    background: 'var(--bz-card)',
                    color: 'var(--bz-text-1)',
                  }}
                >
                  <option value="low">Low</option>
                  <option value="normal">Normal</option>
                  <option value="high">High</option>
                  <option value="urgent">Urgent</option>
                </select>
              </div>

              {/* Payment Status */}
              <div className="space-y-2">
                <label className="text-sm font-medium" style={{ color: 'var(--bz-text-1)' }}>
                  Payment Status
                </label>
                <select
                  value={editForm.payment_status}
                  onChange={(e) =>
                    setEditForm((prev) => ({
                      ...prev,
                      payment_status: e.target.value,
                    }))
                  }
                  className="w-full px-3 py-2 rounded-lg focus:outline-none"
                  style={{
                    border: '1px solid var(--bz-border)',
                    background: 'var(--bz-card)',
                    color: 'var(--bz-text-1)',
                  }}
                >
                  <option value="unpaid">Unpaid</option>
                  <option value="partial">Partial</option>
                  <option value="paid">Paid</option>
                </select>
              </div>

              {/* Quoted Price */}
              <div className="space-y-2">
                <label className="text-sm font-medium" style={{ color: 'var(--bz-text-1)' }}>
                  Quoted Price (IDR)
                </label>
                <input
                  type="number"
                  value={editForm.quoted_price}
                  onChange={(e) =>
                    setEditForm((prev) => ({
                      ...prev,
                      quoted_price: e.target.value,
                    }))
                  }
                  className="w-full px-3 py-2 rounded-lg focus:outline-none"
                  style={{
                    border: '1px solid var(--bz-border)',
                    background: 'var(--bz-card)',
                    color: 'var(--bz-text-1)',
                  }}
                  placeholder="0.00"
                  step="0.01"
                />
              </div>

              {/* Actual Price */}
              <div className="space-y-2">
                <label className="text-sm font-medium" style={{ color: 'var(--bz-text-1)' }}>
                  Actual Price (IDR)
                </label>
                <input
                  type="number"
                  value={editForm.actual_price}
                  onChange={(e) =>
                    setEditForm((prev) => ({
                      ...prev,
                      actual_price: e.target.value,
                    }))
                  }
                  className="w-full px-3 py-2 rounded-lg focus:outline-none"
                  style={{
                    border: '1px solid var(--bz-border)',
                    background: 'var(--bz-card)',
                    color: 'var(--bz-text-1)',
                  }}
                  placeholder="0.00"
                  step="0.01"
                />
              </div>
            </div>

            <div
              className="p-6 flex justify-end gap-3 sticky bottom-0"
              style={{
                borderTop: '1px solid var(--bz-border)',
                background: 'var(--bz-surface)',
              }}
            >
              <Button
                variant="outline"
                onClick={() => setIsEditModalOpen(false)}
                disabled={isSaving}
              >
                Cancel
              </Button>
              <Button
                className="text-white"
                style={{ background: 'var(--bz-accent)' }}
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
