'use client';

import React, { useState, useEffect } from 'react';
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

  useEffect(() => {
    const loadPractice = async () => {
      if (!caseId) {
        setError('Invalid case ID');
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        // TODO: Replace with dedicated getPractice(id) API endpoint
        const allPractices = await api.crm.getPractices({ limit: 1000 });
        const foundPractice = allPractices.find(p => p.id === caseId);

        if (!foundPractice) {
          setError('Case not found');
          toast.error('Error', `Case #${caseId} not found`);
        } else {
          setPractice(foundPractice);
        }
      } catch (err) {
        console.error('Failed to load case:', err);
        setError('Failed to load case details');
        toast.error('Error', 'Failed to load case details');
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
          onClick={() => router.push('/cases')}
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
            <Button variant="outline" size="sm">
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
                  onClick={() => router.push(`/clients/${practice.client_id}`)}
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
                    className="text-[var(--foreground)] hover:text-[var(--accent)] transition-colors flex items-center gap-2"
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
                  onClick={() => window.open(`mailto:${practice.client_email}`, '_blank')}
                >
                  <Mail className="w-4 h-4 mr-2" />
                  Email Client
                </Button>
              )}

              <Button
                variant="outline"
                className="w-full justify-start"
                onClick={() => router.push(`/clients/${practice.client_id}`)}
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
    </div>
  );
}
