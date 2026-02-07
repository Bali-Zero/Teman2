'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  Loader2,
  Building2,
  Users,
  FileCheck,
  Calendar,
  CheckCircle,
  AlertTriangle,
  Clock,
  ChevronLeft,
  Shield,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/toast';
import { cn } from '@/lib/utils';
import type { PortalCompany, CompanyLicense, ComplianceItem } from '@/lib/api/portal/portal.types';
import { Button } from '@/components/ui/button';

export default function CompanyDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { error } = useToast();
  const [company, setCompany] = useState<PortalCompany | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const companyId = params?.id ? parseInt(params.id as string) : null;

  useEffect(() => {
    if (companyId) {
      loadCompany();
    }
  }, [companyId]);

  const loadCompany = async () => {
    if (!companyId) return;

    try {
      setIsLoading(true);
      const data = await api.portal.getCompanyDetail(companyId);
      setCompany(data);
    } catch (err) {
      error('Failed to load company details', 'Please try again later');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!company) {
    return (
      <div className="text-center py-12">
        <Building2 className="w-16 h-16 mx-auto mb-4 text-muted-foreground/30" />
        <h2 className="text-lg font-semibold text-muted-foreground">Company not found</h2>
        <Button variant="ghost" className="mt-4" onClick={() => router.push('/portal/vault')}>
          <ChevronLeft className="w-4 h-4 mr-1" />
          Back to Vault
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Back Button */}
      <Button variant="ghost" size="sm" onClick={() => router.back()} className="-ml-2">
        <ChevronLeft className="w-4 h-4 mr-1" />
        Back
      </Button>

      {/* Company Header */}
      <section className="rounded-xl border bg-card p-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-xl bg-primary/10">
              <Building2 className="w-6 h-6 text-primary" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">{company.name}</h1>
              <p className="text-sm text-muted-foreground">{company.type}</p>
            </div>
          </div>
          <StatusBadge status={company.status} />
        </div>

        {company.address && <p className="mt-4 text-sm text-muted-foreground">{company.address}</p>}

        {company.isPrimary && (
          <div className="mt-4 px-3 py-1.5 bg-primary/10 text-primary text-xs font-medium rounded-full inline-flex items-center gap-1.5">
            <Shield className="w-3.5 h-3.5" />
            Primary Company
          </div>
        )}
      </section>

      {/* Licenses Section */}
      <section className="rounded-xl border bg-card p-6 space-y-4">
        <div className="flex items-center gap-2">
          <FileCheck className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-semibold">Licenses</h2>
        </div>

        {company.licenses && company.licenses.length > 0 ? (
          <div className="space-y-3">
            {company.licenses.map((license) => (
              <LicenseCard key={license.id} license={license} />
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            <FileCheck className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No licenses on record</p>
          </div>
        )}
      </section>

      {/* Compliance Calendar Section */}
      <section className="rounded-xl border bg-card p-6 space-y-4">
        <div className="flex items-center gap-2">
          <Calendar className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-semibold">Compliance Calendar</h2>
        </div>

        {company.compliance && company.compliance.length > 0 ? (
          <div className="space-y-3">
            {company.compliance
              .sort((a, b) => new Date(a.dueDate).getTime() - new Date(b.dueDate).getTime())
              .map((item) => (
                <ComplianceCard key={item.id} item={item} />
              ))}
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            <Calendar className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No compliance deadlines</p>
          </div>
        )}
      </section>

      {/* Directors Section */}
      <section className="rounded-xl border bg-card p-6 space-y-4">
        <div className="flex items-center gap-2">
          <Users className="w-5 h-5 text-primary" />
          <h2 className="text-lg font-semibold">Directors</h2>
        </div>

        {company.directors && company.directors.length > 0 ? (
          <div className="grid gap-2">
            {company.directors.map((director, index) => (
              <div
                key={index}
                className="flex items-center gap-3 p-3 rounded-lg bg-neutral-50 dark:bg-neutral-900"
              >
                <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                  <span className="text-sm font-semibold text-primary">
                    {director.charAt(0).toUpperCase()}
                  </span>
                </div>
                <span className="font-medium text-sm">{director}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            <Users className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No directors on record</p>
          </div>
        )}
      </section>
    </div>
  );
}

// Sub-components

function StatusBadge({ status }: { status: 'active' | 'pending' }) {
  const config = {
    active: {
      icon: CheckCircle,
      label: 'Active',
      className: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
    },
    pending: {
      icon: Clock,
      label: 'Pending',
      className: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    },
  };

  const { icon: Icon, label, className } = config[status];

  return (
    <div
      className={cn(
        'px-3 py-1.5 rounded-full flex items-center gap-1.5 text-xs font-medium',
        className
      )}
    >
      <Icon className="w-3.5 h-3.5" />
      {label}
    </div>
  );
}

function LicenseCard({ license }: { license: CompanyLicense }) {
  const getStatusConfig = (status: string) => {
    switch (status) {
      case 'active':
        return {
          icon: CheckCircle,
          className: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
          borderClass: 'border-emerald-200 dark:border-emerald-800',
        };
      case 'expiring':
        return {
          icon: AlertTriangle,
          className: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
          borderClass: 'border-amber-200 dark:border-amber-800',
        };
      case 'expired':
        return {
          icon: AlertTriangle,
          className: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
          borderClass: 'border-red-200 dark:border-red-800',
        };
      default:
        return {
          icon: Clock,
          className: 'bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-400',
          borderClass: 'border-neutral-200 dark:border-neutral-700',
        };
    }
  };

  const config = getStatusConfig(license.status);
  const Icon = config.icon;

  return (
    <div className={cn('rounded-lg border p-4', config.borderClass)}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-sm">{license.name}</h3>
          <p className="text-xs text-muted-foreground mt-1">
            Expires:{' '}
            {new Date(license.expiryDate).toLocaleDateString('en-US', {
              month: 'long',
              day: 'numeric',
              year: 'numeric',
            })}
          </p>
          {license.daysRemaining !== undefined && (
            <p
              className={cn(
                'text-xs font-medium mt-1',
                license.daysRemaining <= 30
                  ? 'text-red-600 dark:text-red-400'
                  : license.daysRemaining <= 60
                    ? 'text-amber-600 dark:text-amber-400'
                    : 'text-emerald-600 dark:text-emerald-400'
              )}
            >
              {license.daysRemaining} days remaining
            </p>
          )}
        </div>
        <div
          className={cn(
            'px-2.5 py-1 rounded-full flex items-center gap-1 text-xs font-medium',
            config.className
          )}
        >
          <Icon className="w-3 h-3" />
          {license.status.charAt(0).toUpperCase() + license.status.slice(1)}
        </div>
      </div>
    </div>
  );
}

function ComplianceCard({ item }: { item: ComplianceItem }) {
  const getStatusConfig = (status: string) => {
    switch (status) {
      case 'completed':
        return {
          icon: CheckCircle,
          className: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
          bgClass: 'bg-neutral-50 dark:bg-neutral-900',
        };
      case 'overdue':
        return {
          icon: AlertTriangle,
          className: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
          bgClass: 'bg-red-50/50 dark:bg-red-950/10',
        };
      case 'upcoming':
      default:
        return {
          icon: Clock,
          className: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
          bgClass: 'bg-amber-50/50 dark:bg-amber-950/10',
        };
    }
  };

  const config = getStatusConfig(item.status);
  const Icon = config.icon;
  const dueDate = new Date(item.dueDate);
  const isPast = dueDate < new Date() && item.status !== 'completed';

  return (
    <div className={cn('rounded-lg p-4 border', config.bgClass)}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <h3 className="font-semibold text-sm">{item.name}</h3>
          <p
            className={cn(
              'text-xs mt-1',
              isPast ? 'text-red-600 dark:text-red-400 font-medium' : 'text-muted-foreground'
            )}
          >
            {isPast ? 'Was due: ' : 'Due: '}
            {dueDate.toLocaleDateString('en-US', {
              weekday: 'short',
              month: 'short',
              day: 'numeric',
              year: 'numeric',
            })}
          </p>
        </div>
        <div
          className={cn(
            'px-2.5 py-1 rounded-full flex items-center gap-1 text-xs font-medium',
            config.className
          )}
        >
          <Icon className="w-3 h-3" />
          {item.status.charAt(0).toUpperCase() + item.status.slice(1)}
        </div>
      </div>
    </div>
  );
}
