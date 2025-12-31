'use client';

import React, { useState, useEffect } from 'react';
import {
  Plane,
  Building2,
  Receipt,
  FileText,
  AlertCircle,
  CheckCircle2,
  Clock,
  ArrowRight,
  MessageSquare,
} from 'lucide-react';
import Link from 'next/link';
import { api } from '@/lib/api';
import type { PortalDashboard } from '@/lib/api/portal/portal.types';

interface StatusCardProps {
  title: string;
  status: 'active' | 'pending' | 'warning' | 'expired';
  description: string;
  href: string;
  icon: React.ReactNode;
  daysRemaining?: number;
}

function StatusCard({ title, status, description, href, icon, daysRemaining }: StatusCardProps) {
  const statusConfig = {
    active: { bg: 'bg-emerald-50', border: 'border-emerald-200', text: 'text-emerald-700', icon: <CheckCircle2 className="w-4 h-4" /> },
    pending: { bg: 'bg-amber-50', border: 'border-amber-200', text: 'text-amber-700', icon: <Clock className="w-4 h-4" /> },
    warning: { bg: 'bg-orange-50', border: 'border-orange-200', text: 'text-orange-700', icon: <AlertCircle className="w-4 h-4" /> },
    expired: { bg: 'bg-red-50', border: 'border-red-200', text: 'text-red-700', icon: <AlertCircle className="w-4 h-4" /> },
  };

  const config = statusConfig[status];

  return (
    <Link href={href} className="block">
      <div className={`p-5 rounded-xl border ${config.border} ${config.bg} hover:shadow-md transition-shadow`}>
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-white shadow-sm">
              {icon}
            </div>
            <div>
              <h3 className="font-medium text-slate-800">{title}</h3>
              <p className="text-sm text-slate-600 mt-0.5">{description}</p>
            </div>
          </div>
          <div className={`flex items-center gap-1 px-2 py-1 rounded-full ${config.bg} ${config.text} text-xs font-medium`}>
            {config.icon}
            <span className="capitalize">{status}</span>
          </div>
        </div>
        {daysRemaining !== undefined && daysRemaining <= 60 && (
          <div className="mt-3 pt-3 border-t border-slate-200">
            <p className={`text-sm ${daysRemaining <= 30 ? 'text-red-600' : 'text-orange-600'} font-medium`}>
              {daysRemaining <= 0 ? 'Expired' : `${daysRemaining} days remaining`}
            </p>
          </div>
        )}
      </div>
    </Link>
  );
}

interface ActionItemProps {
  title: string;
  description: string;
  priority: 'high' | 'medium' | 'low';
  href: string;
}

function ActionItem({ title, description, priority, href }: ActionItemProps) {
  const priorityColors = {
    high: 'bg-red-100 text-red-700',
    medium: 'bg-amber-100 text-amber-700',
    low: 'bg-blue-100 text-blue-700',
  };

  return (
    <Link href={href} className="flex items-center gap-4 p-4 bg-white rounded-lg border border-slate-200 hover:border-slate-300 hover:shadow-sm transition-all">
      <span className={`px-2 py-1 text-xs font-medium rounded ${priorityColors[priority]}`}>
        {priority.toUpperCase()}
      </span>
      <div className="flex-1">
        <p className="font-medium text-slate-800">{title}</p>
        <p className="text-sm text-slate-500">{description}</p>
      </div>
      <ArrowRight className="w-5 h-5 text-slate-400" />
    </Link>
  );
}

export default function PortalDashboard() {
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dashboardData, setDashboardData] = useState<{
    visa: { status: 'active' | 'pending' | 'warning' | 'expired'; type: string; expiryDate?: string; daysRemaining?: number };
    company: { status: 'active' | 'pending' | 'warning' | 'expired'; name?: string; licenses: number };
    taxes: { status: 'active' | 'pending' | 'warning' | 'expired'; nextDeadline?: string; daysToDeadline?: number };
    documents: { total: number; pending: number };
    messages: { unread: number };
    actions: Array<{ id: string; title: string; description: string; priority: 'high' | 'medium' | 'low'; href: string }>;
  } | null>(null);

  useEffect(() => {
    const loadDashboard = async () => {
      try {
        setIsLoading(true);
        setError(null);

        const data: PortalDashboard = await api.portal.getDashboard();

        // Map API response to component state
        setDashboardData({
          visa: {
            status: mapVisaStatus(data.visa.status),
            type: data.visa.type || 'No visa on record',
            expiryDate: data.visa.expiryDate || undefined,
            daysRemaining: data.visa.daysRemaining || undefined,
          },
          company: {
            status: mapCompanyStatus(data.company.status),
            name: data.company.primaryCompanyName || undefined,
            licenses: data.company.totalCompanies,
          },
          taxes: {
            status: mapTaxStatus(data.taxes.status),
            nextDeadline: data.taxes.nextDeadline || undefined,
            daysToDeadline: data.taxes.daysToDeadline || undefined,
          },
          documents: data.documents,
          messages: data.messages,
          actions: data.actions.map(a => ({
            id: a.id,
            title: a.title,
            description: a.description,
            priority: a.priority,
            href: a.href,
          })),
        });
      } catch (err) {
        console.error('Failed to load dashboard:', err);
        setError('Unable to load dashboard. Please try again.');
      } finally {
        setIsLoading(false);
      }
    };

    loadDashboard();
  }, []);

  // Helper functions to map API status to component status
  function mapVisaStatus(status: string): 'active' | 'pending' | 'warning' | 'expired' {
    switch (status) {
      case 'active': return 'active';
      case 'pending': return 'pending';
      case 'warning': return 'warning';
      case 'expired': return 'expired';
      case 'none': return 'pending';
      default: return 'pending';
    }
  }

  function mapCompanyStatus(status: string): 'active' | 'pending' | 'warning' | 'expired' {
    switch (status) {
      case 'active': return 'active';
      case 'pending': return 'pending';
      case 'none': return 'pending';
      default: return 'pending';
    }
  }

  function mapTaxStatus(status: string): 'active' | 'pending' | 'warning' | 'expired' {
    switch (status) {
      case 'compliant': return 'active';
      case 'attention': return 'warning';
      case 'overdue': return 'expired';
      default: return 'pending';
    }
  }

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-slate-200 rounded w-48"></div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-32 bg-slate-200 rounded-xl"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="w-12 h-12 text-red-500 mb-4" />
        <h2 className="text-lg font-medium text-slate-800 mb-2">Unable to load dashboard</h2>
        <p className="text-slate-500 mb-4">{error}</p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 transition-colors"
        >
          Try Again
        </button>
      </div>
    );
  }

  if (!dashboardData) return null;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-slate-800">Welcome back</h1>
        <p className="text-slate-500 mt-1">Here's an overview of your services</p>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatusCard
          title="Visa Status"
          status={dashboardData.visa.status}
          description={dashboardData.visa.type}
          href="/portal/visa"
          icon={<Plane className="w-5 h-5 text-emerald-600" />}
          daysRemaining={dashboardData.visa.daysRemaining}
        />
        <StatusCard
          title="Company"
          status={dashboardData.company.status}
          description={dashboardData.company.name || 'No company linked'}
          href="/portal/company"
          icon={<Building2 className="w-5 h-5 text-blue-600" />}
        />
        <StatusCard
          title="Taxes"
          status={dashboardData.taxes.status}
          description={dashboardData.taxes.nextDeadline ? `Next: ${dashboardData.taxes.nextDeadline}` : 'No deadlines'}
          href="/portal/taxes"
          icon={<Receipt className="w-5 h-5 text-purple-600" />}
          daysRemaining={dashboardData.taxes.daysToDeadline}
        />
        <StatusCard
          title="Documents"
          status={dashboardData.documents.pending > 0 ? 'pending' : 'active'}
          description={`${dashboardData.documents.total} documents, ${dashboardData.documents.pending} pending`}
          href="/portal/documents"
          icon={<FileText className="w-5 h-5 text-orange-600" />}
        />
      </div>

      {/* Messages Banner */}
      {dashboardData.messages.unread > 0 && (
        <Link href="/portal/messages" className="block">
          <div className="flex items-center gap-4 p-4 bg-blue-50 border border-blue-200 rounded-xl hover:bg-blue-100 transition-colors">
            <div className="p-2 bg-blue-100 rounded-lg">
              <MessageSquare className="w-5 h-5 text-blue-600" />
            </div>
            <div className="flex-1">
              <p className="font-medium text-blue-800">
                You have {dashboardData.messages.unread} unread message{dashboardData.messages.unread > 1 ? 's' : ''}
              </p>
              <p className="text-sm text-blue-600">Click to view your messages</p>
            </div>
            <ArrowRight className="w-5 h-5 text-blue-400" />
          </div>
        </Link>
      )}

      {/* Required Actions */}
      {dashboardData.actions.length > 0 && (
        <div>
          <h2 className="text-lg font-medium text-slate-800 mb-4">Required Actions</h2>
          <div className="space-y-3">
            {dashboardData.actions.map((action) => (
              <ActionItem key={action.id} {...action} />
            ))}
          </div>
        </div>
      )}

      {/* Quick Links */}
      <div>
        <h2 className="text-lg font-medium text-slate-800 mb-4">Quick Links</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Link href="/portal/documents" className="p-4 bg-white border border-slate-200 rounded-xl text-center hover:border-emerald-200 hover:bg-emerald-50 transition-colors">
            <FileText className="w-6 h-6 text-slate-600 mx-auto mb-2" />
            <span className="text-sm font-medium text-slate-700">Upload Document</span>
          </Link>
          <Link href="/portal/messages" className="p-4 bg-white border border-slate-200 rounded-xl text-center hover:border-emerald-200 hover:bg-emerald-50 transition-colors">
            <MessageSquare className="w-6 h-6 text-slate-600 mx-auto mb-2" />
            <span className="text-sm font-medium text-slate-700">Contact Team</span>
          </Link>
          <Link href="/portal/visa" className="p-4 bg-white border border-slate-200 rounded-xl text-center hover:border-emerald-200 hover:bg-emerald-50 transition-colors">
            <Plane className="w-6 h-6 text-slate-600 mx-auto mb-2" />
            <span className="text-sm font-medium text-slate-700">Visa History</span>
          </Link>
          <Link href="/portal/settings" className="p-4 bg-white border border-slate-200 rounded-xl text-center hover:border-emerald-200 hover:bg-emerald-50 transition-colors">
            <Receipt className="w-6 h-6 text-slate-600 mx-auto mb-2" />
            <span className="text-sm font-medium text-slate-700">Preferences</span>
          </Link>
        </div>
      </div>
    </div>
  );
}
