'use client';

import React, { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  Building2,
  Users,
  FileCheck,
  Calendar,
  CheckCircle,
  AlertTriangle,
  Clock,
  ChevronLeft,
  Shield,
  MapPin,
  Mail,
  Phone,
  Hash,
  Briefcase,
  FileText,
  Copy,
  Check,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/toast';
import { cn } from '@/lib/utils';
import { logger } from '@/lib/logger';
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
      logger.error('Failed to load portal company detail', {}, err as Error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6 animate-in fade-in duration-500">
        {/* Back button */}
        <div className="h-8 w-16 rounded animate-pulse" style={{ background: 'var(--bz-border)' }} />
        {/* Company header card */}
        <section className="rounded-xl border p-6 animate-pulse" style={{ background: 'rgba(30,30,35,0.7)', borderColor: 'rgba(255,255,255,0.05)' }}>
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl" style={{ background: 'var(--bz-border)' }} />
            <div className="space-y-2 flex-1">
              <div className="h-6 w-48 rounded" style={{ background: 'var(--bz-border)' }} />
              <div className="h-4 w-24 rounded" style={{ background: 'var(--bz-border)', opacity: 0.5 }} />
            </div>
            <div className="h-6 w-20 rounded-full" style={{ background: 'var(--bz-border)', opacity: 0.4 }} />
          </div>
          <div className="mt-4 space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="flex items-center gap-2">
                <div className="h-4 w-4 rounded" style={{ background: 'var(--bz-border)', opacity: 0.4 }} />
                <div className="h-4 w-40 rounded" style={{ background: 'var(--bz-border)', opacity: 0.4 }} />
              </div>
            ))}
          </div>
        </section>
        {/* Licenses section skeleton */}
        <div className="rounded-xl border p-6 space-y-3 animate-pulse" style={{ background: 'rgba(30,30,35,0.7)', borderColor: 'rgba(255,255,255,0.05)' }}>
          <div className="h-5 w-24 rounded" style={{ background: 'var(--bz-border)' }} />
          {[1, 2].map((i) => (
            <div key={i} className="rounded-lg border p-3 space-y-1.5" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
              <div className="h-4 w-36 rounded" style={{ background: 'var(--bz-border)' }} />
              <div className="h-3 w-28 rounded" style={{ background: 'var(--bz-border)', opacity: 0.4 }} />
            </div>
          ))}
        </div>
        {/* Compliance section skeleton */}
        <div className="rounded-xl border p-6 space-y-3 animate-pulse" style={{ background: 'rgba(30,30,35,0.7)', borderColor: 'rgba(255,255,255,0.05)' }}>
          <div className="h-5 w-32 rounded" style={{ background: 'var(--bz-border)' }} />
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex items-center justify-between">
              <div className="h-4 w-40 rounded" style={{ background: 'var(--bz-border)', opacity: 0.5 }} />
              <div className="h-5 w-16 rounded-full" style={{ background: 'var(--bz-border)', opacity: 0.4 }} />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!company) {
    return (
      <div className="text-center py-12">
        <Building2
          className="w-16 h-16 mx-auto mb-4 opacity-30"
          style={{ color: 'var(--bz-text-2)' }}
        />
        <h2 className="text-lg font-semibold" style={{ color: 'var(--bz-text-2)' }}>
          Company not found
        </h2>
        <Button variant="ghost" className="mt-4" onClick={() => router.push('/portal/companies')}>
          <ChevronLeft className="w-4 h-4 mr-1" />
          Back to Companies
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
      <section
        className="rounded-xl border p-6"
        style={{
          background: 'rgba(30,30,35,0.7)',
          borderColor: 'rgba(255,255,255,0.05)',
          backdropFilter: 'blur(24px)',
        }}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="p-3 rounded-xl" style={{ background: 'rgba(201,169,110,0.1)' }}>
              <Building2 className="w-6 h-6" style={{ color: 'var(--bz-accent-warm)' }} />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">{company.name}</h1>
              <p className="text-sm" style={{ color: 'var(--bz-text-2)' }}>
                {company.type}
              </p>
            </div>
          </div>
          <StatusBadge status={company.status} />
        </div>

        {company.address && (
          <p className="mt-4 text-sm" style={{ color: 'var(--bz-text-2)' }}>
            {company.address}
          </p>
        )}

        {company.isPrimary && (
          <div
            className="mt-4 px-3 py-1.5 text-xs font-medium rounded-full inline-flex items-center gap-1.5"
            style={{
              background: 'rgba(201,169,110,0.1)',
              color: 'var(--bz-accent-warm)',
            }}
          >
            <Shield className="w-3.5 h-3.5" />
            Primary Company
          </div>
        )}
      </section>

      {/* Business Details Section */}
      <BusinessDetailsSection company={company} />

      {/* Licenses Section */}
      <section
        className="rounded-xl border p-6 space-y-4"
        style={{
          background: 'rgba(30,30,35,0.7)',
          borderColor: 'rgba(255,255,255,0.05)',
          backdropFilter: 'blur(24px)',
        }}
      >
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <FileCheck className="w-5 h-5" style={{ color: 'var(--bz-accent-warm)' }} />
            <h2 className="text-lg font-semibold">Licenses</h2>
          </div>
          {company.licenses &&
            company.licenses.length > 0 &&
            (() => {
              const expiring = company.licenses.filter((l) => l.status === 'expiring').length;
              const expired = company.licenses.filter((l) => l.status === 'expired').length;
              if (expired > 0)
                return (
                  <span
                    className="text-xs px-2 py-1 rounded-full font-medium"
                    style={{ background: 'rgba(239,68,68,0.12)', color: '#f87171' }}
                  >
                    {expired} expired
                  </span>
                );
              if (expiring > 0)
                return (
                  <span
                    className="text-xs px-2 py-1 rounded-full font-medium"
                    style={{ background: 'rgba(245,158,11,0.12)', color: '#fbbf24' }}
                  >
                    {expiring} expiring soon
                  </span>
                );
              return (
                <span
                  className="text-xs px-2 py-1 rounded-full font-medium"
                  style={{ background: 'rgba(16,185,129,0.12)', color: '#34d399' }}
                >
                  All valid
                </span>
              );
            })()}
        </div>

        {company.licenses && company.licenses.length > 0 ? (
          <div className="space-y-3">
            {company.licenses.map((license) => (
              <LicenseCard key={license.id} license={license} />
            ))}
          </div>
        ) : (
          <div className="text-center py-8" style={{ color: 'var(--bz-text-2)' }}>
            <FileCheck className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No licenses on record</p>
          </div>
        )}
      </section>

      {/* Compliance Calendar Section */}
      <section
        className="rounded-xl border p-6 space-y-4"
        style={{
          background: 'rgba(30,30,35,0.7)',
          borderColor: 'rgba(255,255,255,0.05)',
          backdropFilter: 'blur(24px)',
        }}
      >
        <div className="flex items-center gap-2">
          <Calendar className="w-5 h-5" style={{ color: 'var(--bz-accent-warm)' }} />
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
          <div className="text-center py-8" style={{ color: 'var(--bz-text-2)' }}>
            <Calendar className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No compliance deadlines</p>
          </div>
        )}
      </section>

      {/* Directors Section */}
      <section
        className="rounded-xl border p-6 space-y-4"
        style={{
          background: 'rgba(30,30,35,0.7)',
          borderColor: 'rgba(255,255,255,0.05)',
          backdropFilter: 'blur(24px)',
        }}
      >
        <div className="flex items-center gap-2">
          <Users className="w-5 h-5" style={{ color: 'var(--bz-accent-warm)' }} />
          <h2 className="text-lg font-semibold">Directors</h2>
        </div>

        {company.directors && company.directors.length > 0 ? (
          <div className="grid gap-2">
            {company.directors.map((director, index) => (
              <div
                key={index}
                className="flex items-center gap-3 p-3 rounded-lg"
                style={{ background: 'rgba(255,255,255,0.03)' }}
              >
                <div
                  className="w-10 h-10 rounded-full flex items-center justify-center"
                  style={{ background: 'rgba(201,169,110,0.1)' }}
                >
                  <span
                    className="text-sm font-semibold"
                    style={{ color: 'var(--bz-accent-warm)' }}
                  >
                    {director.charAt(0).toUpperCase()}
                  </span>
                </div>
                <span className="font-medium text-sm">{director}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8" style={{ color: 'var(--bz-text-2)' }}>
            <Users className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p className="text-sm">No directors on record</p>
          </div>
        )}
      </section>
    </div>
  );
}

// Sub-components

const COPYABLE_FIELDS = new Set(['NIB', 'NPWP', 'KBLI']);

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <button
      onClick={handleCopy}
      className="ml-1 p-0.5 rounded opacity-40 hover:opacity-100 transition-opacity flex-shrink-0"
      style={{ color: 'var(--bz-text-2)' }}
      aria-label="Copy to clipboard"
    >
      {copied ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
    </button>
  );
}

function BusinessDetailsSection({ company }: { company: PortalCompany }) {
  const fields = [
    { icon: Hash, label: 'NIB', value: company.nib },
    { icon: Hash, label: 'NPWP', value: company.npwp },
    { icon: Briefcase, label: 'KBLI', value: company.kbli },
    { icon: MapPin, label: 'Registered Address', value: company.address },
    { icon: Mail, label: 'Email', value: company.email },
    { icon: Phone, label: 'Phone', value: company.phone },
    {
      icon: FileText,
      label: 'Akta No.',
      value: company.aktaNo
        ? `${company.aktaNo}${company.aktaDate ? ` (${new Date(company.aktaDate).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })})` : ''}`
        : undefined,
    },
    { icon: FileText, label: 'SK Kemenkumham', value: company.skNumber },
    { icon: MapPin, label: 'Tax Office (KPP)', value: company.taxOffice },
    {
      icon: Briefcase,
      label: 'Investment Type',
      value: company.investmentType,
    },
    { icon: Briefcase, label: 'Company Status', value: company.companyStatus },
  ].filter((f) => f.value);

  if (fields.length === 0) return null;

  return (
    <section
      className="rounded-xl border p-6 space-y-4"
      style={{
        background: 'rgba(30,30,35,0.7)',
        borderColor: 'rgba(255,255,255,0.05)',
        backdropFilter: 'blur(24px)',
      }}
    >
      <div className="flex items-center gap-2">
        <Building2 className="w-5 h-5" style={{ color: 'var(--bz-accent-warm)' }} />
        <h2 className="text-lg font-semibold">Business Details</h2>
      </div>

      <div className="grid gap-3">
        {fields.map((field) => (
          <div
            key={field.label}
            className="flex items-start gap-3 p-3 rounded-lg"
            style={{ background: 'rgba(255,255,255,0.03)' }}
          >
            <field.icon
              className="w-4 h-4 mt-0.5 flex-shrink-0"
              style={{ color: 'var(--bz-accent-warm)' }}
            />
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium" style={{ color: 'var(--bz-text-3)' }}>
                {field.label}
              </p>
              <div className="flex items-center gap-0.5 mt-0.5">
                <p className="text-sm break-words">{field.value}</p>
                {COPYABLE_FIELDS.has(field.label) && field.value && (
                  <CopyButton value={field.value} />
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function StatusBadge({ status }: { status: 'active' | 'pending' }) {
  const config: Record<
    string,
    { icon: React.ElementType; label: string; style: React.CSSProperties }
  > = {
    active: {
      icon: CheckCircle,
      label: 'Active',
      style: { background: 'rgba(16,185,129,0.12)', color: '#34d399' },
    },
    pending: {
      icon: Clock,
      label: 'Pending',
      style: { background: 'rgba(245,158,11,0.12)', color: '#fbbf24' },
    },
  };

  const { icon: Icon, label, style } = config[status] ?? config.pending;

  return (
    <div
      className="px-3 py-1.5 rounded-full flex items-center gap-1.5 text-xs font-medium"
      style={style}
    >
      <Icon className="w-3.5 h-3.5" />
      {label}
    </div>
  );
}

function LicenseCard({ license }: { license: CompanyLicense }) {
  const getStatusConfig = (
    status: string
  ): {
    icon: React.ElementType;
    badgeStyle: React.CSSProperties;
    borderColor: string;
  } => {
    switch (status) {
      case 'active':
        return {
          icon: CheckCircle,
          badgeStyle: { background: 'rgba(16,185,129,0.12)', color: '#34d399' },
          borderColor: 'rgba(16,185,129,0.25)',
        };
      case 'expiring':
        return {
          icon: AlertTriangle,
          badgeStyle: { background: 'rgba(245,158,11,0.12)', color: '#fbbf24' },
          borderColor: 'rgba(245,158,11,0.3)',
        };
      case 'expired':
        return {
          icon: AlertTriangle,
          badgeStyle: { background: 'rgba(239,68,68,0.12)', color: '#f87171' },
          borderColor: 'rgba(239,68,68,0.3)',
        };
      default:
        return {
          icon: Clock,
          badgeStyle: {
            background: 'rgba(255,255,255,0.03)',
            color: 'var(--bz-text-2)',
          },
          borderColor: 'var(--bz-border)',
        };
    }
  };

  const config = getStatusConfig(license.status);
  const Icon = config.icon;

  return (
    <div
      className="rounded-lg border p-4 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg"
      style={{
        borderColor: config.borderColor,
        background: 'rgba(255,255,255,0.03)',
      }}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-sm">{license.name}</h3>
          <p className="text-xs mt-1" style={{ color: 'var(--bz-text-2)' }}>
            Expires:{' '}
            {new Date(license.expiryDate).toLocaleDateString('en-US', {
              month: 'long',
              day: 'numeric',
              year: 'numeric',
            })}
          </p>
          {license.daysRemaining !== undefined && (
            <span
              className={`inline-flex items-center text-[10px] px-1.5 py-0.5 rounded-full font-semibold mt-1.5 ${
                license.daysRemaining <= 0
                  ? 'bg-red-500/10 text-red-400'
                  : license.daysRemaining <= 30
                    ? 'bg-amber-500/10 text-amber-400'
                    : license.daysRemaining <= 90
                      ? 'bg-yellow-500/10 text-yellow-300'
                      : 'bg-emerald-500/10 text-emerald-400'
              }`}
              title={new Date(license.expiryDate).toLocaleDateString('en-US', {
                month: 'long',
                day: 'numeric',
                year: 'numeric',
              })}
            >
              {license.daysRemaining <= 0
                ? `Expired ${Math.abs(license.daysRemaining)}d ago`
                : license.daysRemaining <= 365
                  ? `⏰ ${license.daysRemaining}d left`
                  : `${Math.floor(license.daysRemaining / 30)}mo left`}
            </span>
          )}
        </div>
        <div
          className="px-2.5 py-1 rounded-full flex items-center gap-1 text-xs font-medium"
          style={config.badgeStyle}
        >
          <Icon className="w-3 h-3" />
          {license.status.charAt(0).toUpperCase() + license.status.slice(1)}
        </div>
      </div>
    </div>
  );
}

function ComplianceCard({ item }: { item: ComplianceItem }) {
  const getStatusConfig = (
    status: string
  ): {
    icon: React.ElementType;
    badgeStyle: React.CSSProperties;
    bgStyle: React.CSSProperties;
  } => {
    switch (status) {
      case 'completed':
        return {
          icon: CheckCircle,
          badgeStyle: { background: 'rgba(16,185,129,0.12)', color: '#34d399' },
          bgStyle: {
            background: 'rgba(255,255,255,0.03)',
            borderColor: 'rgba(255,255,255,0.05)',
          },
        };
      case 'overdue':
        return {
          icon: AlertTriangle,
          badgeStyle: { background: 'rgba(239,68,68,0.12)', color: '#f87171' },
          bgStyle: {
            background: 'rgba(239,68,68,0.06)',
            borderColor: 'rgba(239,68,68,0.25)',
          },
        };
      case 'upcoming':
      default:
        return {
          icon: Clock,
          badgeStyle: { background: 'rgba(245,158,11,0.12)', color: '#fbbf24' },
          bgStyle: {
            background: 'rgba(245,158,11,0.06)',
            borderColor: 'rgba(245,158,11,0.25)',
          },
        };
    }
  };

  const config = getStatusConfig(item.status);
  const Icon = config.icon;
  const dueDate = new Date(item.dueDate);
  const isPast = dueDate < new Date() && item.status !== 'completed';

  return (
    <div
      className="rounded-lg p-4 border transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg"
      style={config.bgStyle}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1">
          <h3 className="font-semibold text-sm">{item.name}</h3>
          <div className="flex items-center gap-2 mt-1 flex-wrap">
            <p
              className="text-xs"
              style={{
                color: isPast ? '#f87171' : 'var(--bz-text-2)',
                fontWeight: isPast ? 500 : 400,
              }}
            >
              {isPast ? 'Was due: ' : 'Due: '}
              {dueDate.toLocaleDateString('en-US', {
                weekday: 'short',
                month: 'short',
                day: 'numeric',
                year: 'numeric',
              })}
            </p>
            {(() => {
              const days = Math.ceil((dueDate.getTime() - Date.now()) / 86400000);
              if (item.status === 'completed') return null;
              const chipColor =
                days <= 0
                  ? 'bg-red-500/10 text-red-400'
                  : days <= 7
                    ? 'bg-red-500/10 text-red-400'
                    : days <= 30
                      ? 'bg-amber-500/10 text-amber-400'
                      : 'bg-emerald-500/10 text-emerald-400';
              const chipText =
                days <= 0
                  ? `${Math.abs(days)}d overdue`
                  : days === 1
                    ? 'tomorrow'
                    : `${days}d left`;
              return (
                <span
                  className={`text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${chipColor}`}
                >
                  {chipText}
                </span>
              );
            })()}
          </div>
        </div>
        <div
          className="px-2.5 py-1 rounded-full flex items-center gap-1 text-xs font-medium"
          style={config.badgeStyle}
        >
          <Icon className="w-3 h-3" />
          {item.status.charAt(0).toUpperCase() + item.status.slice(1)}
        </div>
      </div>
    </div>
  );
}
