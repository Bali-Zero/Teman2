'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Loader2,
  Building2,
  ChevronRight,
  CheckCircle,
  Clock,
  Shield,
  AlertTriangle,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/toast';
import { cn } from '@/lib/utils';
import { logger } from '@/lib/logger';
import type { PortalCompany } from '@/lib/api/portal/portal.types';

export default function CompaniesPage() {
  const router = useRouter();
  const { error, success } = useToast();
  const [companies, setCompanies] = useState<PortalCompany[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [settingPrimaryId, setSettingPrimaryId] = useState<number | null>(null);

  useEffect(() => {
    loadCompanies();
  }, []);

  const loadCompanies = async () => {
    try {
      setIsLoading(true);
      const data = await api.portal.getCompanies();
      setCompanies(data);
    } catch (err) {
      error('Failed to load companies', 'Please try again later');
      logger.error('Failed to load portal companies', {}, err as Error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSetPrimary = async (companyId: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      setSettingPrimaryId(companyId);
      await api.portal.setPrimaryCompany(companyId);
      setCompanies((prev) => prev.map((c) => ({ ...c, isPrimary: c.id === companyId })));
      success('Primary company updated', 'Your primary company has been set.');
      logger.info('Primary company set', {});
    } catch (err) {
      error('Failed to set primary company', 'Please try again');
      logger.error('Failed to set primary company', {}, err as Error);
    } finally {
      setSettingPrimaryId(null);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin" style={{ color: 'var(--bz-accent-warm)' }} />
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section>
        <h1 className="text-2xl font-bold tracking-tight">Your Companies</h1>
        <p style={{ color: 'var(--bz-text-2)' }}>Manage your business entities in Indonesia</p>
      </section>

      {/* Companies List */}
      {companies.length === 0 ? (
        <section
          className="rounded-xl border border-dashed p-12 text-center"
          style={{
            background: 'rgba(30,30,35,0.7)',
            borderColor: 'rgba(255,255,255,0.05)',
            backdropFilter: 'blur(24px)',
          }}
        >
          <Building2
            className="w-16 h-16 mx-auto mb-4 opacity-30"
            style={{ color: 'var(--bz-text-2)' }}
          />
          <h2 className="text-lg font-semibold" style={{ color: 'var(--bz-text-2)' }}>
            No companies yet
          </h2>
          <p className="text-sm mt-1" style={{ color: 'var(--bz-text-3)' }}>
            Contact us to set up your Indonesian business entity.
          </p>
          <a
            href="/portal/chat"
            className="inline-flex items-center gap-1.5 mt-4 px-4 py-2 rounded-full text-sm font-medium transition-opacity hover:opacity-80"
            style={{
              background: 'rgba(201,169,110,0.12)',
              color: 'var(--bz-accent-warm)',
            }}
          >
            Message our team
          </a>
        </section>
      ) : (
        <section className="space-y-3">
          {companies.map((company) => (
            <CompanyCard
              key={company.id}
              company={company}
              onClick={() => router.push(`/portal/company/${company.id}`)}
              onSetPrimary={(e) => handleSetPrimary(company.id, e)}
              isSettingPrimary={settingPrimaryId === company.id}
            />
          ))}
        </section>
      )}
    </div>
  );
}

function CompanyCard({
  company,
  onClick,
  onSetPrimary,
  isSettingPrimary,
}: {
  company: PortalCompany;
  onClick: () => void;
  onSetPrimary: (e: React.MouseEvent) => void;
  isSettingPrimary: boolean;
}) {
  const getComplianceStatus = () => {
    if (!company.compliance || company.compliance.length === 0) return null;

    const hasOverdue = company.compliance.some((c) => c.status === 'overdue');
    const hasUpcoming = company.compliance.some((c) => c.status === 'upcoming');

    if (hasOverdue) {
      return { label: 'Overdue', color: '#f87171' };
    }
    if (hasUpcoming) {
      return { label: 'Upcoming', color: '#fbbf24' };
    }
    return { label: 'Compliant', color: '#34d399' };
  };

  const getLicenseStatus = () => {
    if (!company.licenses || company.licenses.length === 0) return null;

    const hasExpired = company.licenses.some((l) => l.status === 'expired');
    const hasExpiring = company.licenses.some((l) => l.status === 'expiring');

    if (hasExpired) {
      return { icon: AlertTriangle, className: 'text-red-500' };
    }
    if (hasExpiring) {
      return { icon: AlertTriangle, className: 'text-amber-500' };
    }
    return { icon: CheckCircle, className: 'text-emerald-500' };
  };

  const compliance = getComplianceStatus();
  const licenseStatus = getLicenseStatus();

  return (
    <div
      onClick={onClick}
      className="rounded-xl border p-4 cursor-pointer transition-all active:scale-[0.99]"
      style={{
        background: 'rgba(30,30,35,0.7)',
        borderColor: 'rgba(255,255,255,0.05)',
        backdropFilter: 'blur(24px)',
      }}
    >
      <div className="flex items-start gap-4">
        <div
          className="p-3 rounded-xl flex-shrink-0"
          style={{ background: 'rgba(201,169,110,0.1)' }}
        >
          <Building2 className="w-6 h-6" style={{ color: 'var(--bz-accent-warm)' }} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-base truncate">{company.name}</h3>
                {company.isPrimary && (
                  <Shield
                    className="w-4 h-4 flex-shrink-0"
                    style={{ color: 'var(--bz-accent-warm)' }}
                  />
                )}
              </div>
              <p className="text-sm mt-0.5" style={{ color: 'var(--bz-text-2)' }}>
                {company.type}
              </p>
            </div>

            <div className="flex items-center gap-2 flex-shrink-0">
              {!company.isPrimary && (
                <button
                  onClick={onSetPrimary}
                  disabled={isSettingPrimary}
                  className="text-xs px-2 py-1 rounded-full border transition-opacity hover:opacity-80 disabled:opacity-40 whitespace-nowrap"
                  style={{
                    borderColor: 'rgba(201,169,110,0.3)',
                    color: 'var(--bz-accent-warm)',
                    background: 'rgba(201,169,110,0.06)',
                  }}
                >
                  {isSettingPrimary ? (
                    <Loader2 className="w-3 h-3 animate-spin inline" />
                  ) : (
                    'Set primary'
                  )}
                </button>
              )}
              <StatusBadge status={company.status} />
              <ChevronRight className="w-5 h-5" style={{ color: 'var(--bz-text-2)' }} />
            </div>
          </div>

          {/* Quick Stats */}
          <div
            className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-3 text-xs"
            style={{ color: 'var(--bz-text-2)' }}
          >
            {company.nib && <span>NIB: {company.nib}</span>}
            {company.kbli && <span>KBLI: {company.kbli}</span>}
            {company.licenses && company.licenses.length > 0 && licenseStatus && (
              <div className="flex items-center gap-1.5">
                <licenseStatus.icon className={cn('w-3.5 h-3.5', licenseStatus.className)} />
                <span>
                  {company.licenses.length} license
                  {company.licenses.length !== 1 ? 's' : ''}
                </span>
              </div>
            )}

            {company.directors && company.directors.length > 0 && (
              <span>
                {company.directors.length} director
                {company.directors.length !== 1 ? 's' : ''}
              </span>
            )}

            {compliance && (
              <div className="font-medium" style={{ color: compliance.color }}>
                {compliance.label}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
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
      className="px-2 py-1 rounded-full flex items-center gap-1 text-xs font-medium"
      style={style}
    >
      <Icon className="w-3 h-3" />
      {label}
    </div>
  );
}
