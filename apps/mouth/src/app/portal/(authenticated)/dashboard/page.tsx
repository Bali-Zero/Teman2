'use client';

import React, { useEffect, useState } from 'react';
import {
  Loader2,
  User,
  CreditCard,
  FileText,
  Upload,
  AlertTriangle,
  AlertCircle,
  FolderOpen,
  Loader,
  CheckCircle,
  Plane,
} from 'lucide-react';
import { api } from '@/lib/api';
import { logger } from '@/lib/logger';
import { useToast } from '@/components/ui/toast';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import type { PortalProfile } from '@/lib/api/portal/portal.types';
import type { VisaInfo } from '@/lib/api/portal/portal.types';

interface PassportValidityInfo {
  color: string;
  label: string;
  alertLevel: 'ok' | 'warning' | 'critical' | 'expired';
  monthsUntil: number;
}

const getPassportValidityColor = (expiryDate: string | undefined): PassportValidityInfo => {
  if (!expiryDate) {
    return {
      color: 'gray',
      label: 'No expiry',
      alertLevel: 'ok',
      monthsUntil: 999,
    };
  }

  const now = new Date();
  const expiry = new Date(expiryDate);
  const monthsUntilExpiry = (expiry.getTime() - now.getTime()) / (1000 * 60 * 60 * 24 * 30);

  if (monthsUntilExpiry <= 0) {
    return {
      color: 'red',
      label: 'EXPIRED',
      alertLevel: 'expired',
      monthsUntil: monthsUntilExpiry,
    };
  } else if (monthsUntilExpiry < 9) {
    return {
      color: 'red',
      label: `${Math.floor(monthsUntilExpiry)} months`,
      alertLevel: 'critical',
      monthsUntil: monthsUntilExpiry,
    };
  } else if (monthsUntilExpiry < 14) {
    return {
      color: 'yellow',
      label: `${Math.floor(monthsUntilExpiry)} months`,
      alertLevel: 'warning',
      monthsUntil: monthsUntilExpiry,
    };
  } else {
    return {
      color: 'green',
      label: `${Math.floor(monthsUntilExpiry)} months`,
      alertLevel: 'ok',
      monthsUntil: monthsUntilExpiry,
    };
  }
};

const isBirthdayToday = (dateOfBirth: string | undefined): boolean => {
  if (!dateOfBirth) return false;
  const today = new Date();
  const dob = new Date(dateOfBirth);
  return today.getDate() === dob.getDate() && today.getMonth() === dob.getMonth();
};

import { formatDate } from '@/lib/utils/format-date';

export default function PortalDashboardPage() {
  const { error } = useToast();
  const [profile, setProfile] = useState<PortalProfile | null>(null);
  const [visaInfo, setVisaInfo] = useState<VisaInfo | null>(null);
  const [processStatus, setProcessStatus] = useState<'process' | 'electronic' | 'actual'>(
    'process'
  );
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setIsLoading(true);
      const [profileData, visaData] = await Promise.all([
        api.portal.getProfile(),
        api.portal.getVisaStatus(),
      ]);
      setProfile(profileData);
      setVisaInfo(visaData);

      // Determine which visa status to show
      if (visaData?.current) {
        setProcessStatus('actual');
      } else if (visaData?.documents?.some((d) => d.category === 'electronic_visa')) {
        setProcessStatus('electronic');
      } else {
        setProcessStatus('process');
      }
    } catch (err) {
      error('Failed to load data', 'Please try again later');
      logger.error('Failed to load dashboard data', {}, err as Error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6 animate-in fade-in duration-500">
        <section>
          <div className="h-7 w-44 rounded animate-pulse" style={{ background: 'var(--bz-border)' }} />
          <div className="h-4 w-56 rounded mt-2 animate-pulse" style={{ background: 'var(--bz-border)', opacity: 0.5 }} />
        </section>
        <div className="grid grid-cols-2 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="rounded-xl border p-4 h-24 animate-pulse" style={{ background: 'rgba(30,30,35,0.7)', borderColor: 'rgba(255,255,255,0.05)' }} />
          ))}
        </div>
        <div className="rounded-xl border p-5 space-y-3 animate-pulse" style={{ background: 'rgba(30,30,35,0.7)', borderColor: 'rgba(255,255,255,0.05)' }}>
          <div className="h-5 w-32 rounded" style={{ background: 'var(--bz-border)' }} />
          {[1, 2].map((i) => (
            <div key={i} className="h-16 rounded" style={{ background: 'var(--bz-border)', opacity: 0.4 }} />
          ))}
        </div>
      </div>
    );
  }

  if (!profile) return null;

  const passportValidity = getPassportValidityColor(profile.passportExpiry);
  const isBirthday = isBirthdayToday(profile.dateOfBirth);

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section>
        <h1 className="text-2xl font-bold tracking-tight">My Overview</h1>
        <p style={{ color: 'var(--bz-text-2)' }}>Your personal information and documents</p>
      </section>

      {/* Main Grid - 3 columns on desktop */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Column 1: Team Member + Client Data */}
        <TeamMemberCard profile={profile} isBirthday={isBirthday} />

        {/* Column 2: Passport (with OCR data) */}
        <PassportCard profile={profile} passportValidity={passportValidity} />

        {/* Column 3: Process → Electronic Visa → Actual Visa */}
        <VisaProcessCard status={processStatus} visaInfo={visaInfo} />
      </div>
    </div>
  );
}

// ============================================================================
// TEAM MEMBER CARD (Left) - Small avatar + Client Data
// ============================================================================
function TeamMemberCard({ profile, isBirthday }: { profile: PortalProfile; isBirthday: boolean }) {
  const assignedTo = profile.assignedTo;

  return (
    <div
      className="rounded-xl border overflow-hidden flex flex-col backdrop-blur-xl shadow-2xl transition-all duration-300 hover:shadow-[0_8px_30px_rgb(0,0,0,0.12)]"
      style={{
        background: 'rgba(30, 30, 35, 0.7)',
        borderColor: 'rgba(255, 255, 255, 0.05)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2 px-4 py-3 border-b"
        style={{ borderColor: 'rgba(255, 255, 255, 0.05)' }}
      >
        <User className="w-5 h-5" style={{ color: 'var(--bz-accent-warm)' }} />
        <h3 className="font-semibold">Team Member</h3>
      </div>

      {/* Content */}
      <div className="p-4 flex-1 flex flex-col space-y-4">
        {/* Team Member - Small Avatar */}
        <div
          className="flex items-center gap-3 p-3 rounded-lg"
          style={{ background: 'rgba(255, 255, 255, 0.03)' }}
        >
          {assignedTo?.avatarUrl ? (
            <img
              src={assignedTo.avatarUrl}
              alt={assignedTo.name}
              className="w-10 h-10 rounded-full object-cover flex-shrink-0"
            />
          ) : (
            <div
              className="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0"
              style={{ background: 'rgba(201,169,110,0.15)' }}
            >
              <User className="w-5 h-5" style={{ color: 'var(--bz-accent-warm)' }} />
            </div>
          )}
          <div className="min-w-0">
            <p className="font-medium text-sm truncate">{assignedTo?.name || 'Not assigned'}</p>
            <p className="text-xs" style={{ color: 'var(--bz-text-2)' }}>
              Case Manager
            </p>
          </div>
        </div>

        {/* Client Data Section */}
        <div className="space-y-3 flex-1">
          <h4
            className="text-xs font-semibold uppercase tracking-wider"
            style={{ color: 'var(--bz-text-2)' }}
          >
            Your Information
          </h4>

          {/* Client Name */}
          <div className="flex items-start gap-2">
            <User className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: 'var(--bz-text-2)' }} />
            <div className="min-w-0">
              <p className="text-xs" style={{ color: 'var(--bz-text-2)' }}>
                Full Name
              </p>
              <p className="text-sm font-medium truncate">{profile.fullName}</p>
            </div>
          </div>

          {/* Email */}
          <div className="flex items-start gap-2">
            <div
              className="w-4 h-4 mt-0.5 flex-shrink-0 text-xs"
              style={{ color: 'var(--bz-text-2)' }}
            >
              @
            </div>
            <div className="min-w-0">
              <p className="text-xs" style={{ color: 'var(--bz-text-2)' }}>
                Email
              </p>
              <p className="text-sm truncate">
                {profile.email || (
                  <span className="italic" style={{ color: 'var(--bz-text-3)' }}>
                    Not provided
                  </span>
                )}
              </p>
            </div>
          </div>

          {/* Phone */}
          <div className="flex items-start gap-2">
            <div
              className="w-4 h-4 mt-0.5 flex-shrink-0 text-xs"
              style={{ color: 'var(--bz-text-2)' }}
            >
              📞
            </div>
            <div className="min-w-0">
              <p className="text-xs" style={{ color: 'var(--bz-text-2)' }}>
                Phone
              </p>
              <p className="text-sm">
                {profile.phone || (
                  <span className="italic" style={{ color: 'var(--bz-text-3)' }}>
                    Not provided
                  </span>
                )}
              </p>
            </div>
          </div>

          {/* Nationality */}
          <div className="flex items-start gap-2">
            <div
              className="w-4 h-4 mt-0.5 flex-shrink-0 text-xs"
              style={{ color: 'var(--bz-text-2)' }}
            >
              🌍
            </div>
            <div className="min-w-0">
              <p className="text-xs" style={{ color: 'var(--bz-text-2)' }}>
                Nationality
              </p>
              <p className="text-sm">
                {profile.nationality || (
                  <span className="italic" style={{ color: 'var(--bz-text-3)' }}>
                    Not provided
                  </span>
                )}
              </p>
            </div>
          </div>

          {/* Date of Birth with Birthday Highlight */}
          {profile.dateOfBirth && (
            <div
              className={cn('flex items-start gap-2 p-2 rounded-lg', isBirthday && 'animate-pulse')}
              style={isBirthday ? { background: 'rgba(251,191,36,0.15)' } : {}}
            >
              <div
                className="w-4 h-4 mt-0.5 flex-shrink-0 text-xs"
                style={{ color: 'var(--bz-text-2)' }}
              >
                {isBirthday ? '🎂' : '📅'}
              </div>
              <div className="min-w-0">
                <p className="text-xs" style={{ color: 'var(--bz-text-2)' }}>
                  Date of Birth
                </p>
                <p className="text-sm font-medium" style={isBirthday ? { color: '#fbbf24' } : {}}>
                  {formatDate(profile.dateOfBirth)}
                  {isBirthday && ' (Today!)'}
                </p>
              </div>
            </div>
          )}

          {/* Address */}
          <div className="flex items-start gap-2">
            <div
              className="w-4 h-4 mt-0.5 flex-shrink-0 text-xs"
              style={{ color: 'var(--bz-text-2)' }}
            >
              📍
            </div>
            <div className="min-w-0">
              <p className="text-xs" style={{ color: 'var(--bz-text-2)' }}>
                Address
              </p>
              <p className="text-sm">
                {profile.address || (
                  <span className="italic" style={{ color: 'var(--bz-text-3)' }}>
                    Not provided
                  </span>
                )}
              </p>
            </div>
          </div>

          {/* Gender */}
          <div className="flex items-start gap-2">
            <div
              className={cn(
                'w-4 h-4 mt-0.5 flex-shrink-0 text-xs font-bold flex items-center justify-center rounded',
                profile.gender === 'M'
                  ? 'text-blue-400'
                  : profile.gender === 'F'
                    ? 'text-pink-400'
                    : ''
              )}
              style={
                !profile.gender || (profile.gender !== 'M' && profile.gender !== 'F')
                  ? { color: 'var(--bz-text-2)' }
                  : {}
              }
            >
              {profile.gender === 'M' ? '♂' : profile.gender === 'F' ? '♀' : '—'}
            </div>
            <div className="min-w-0">
              <p className="text-xs" style={{ color: 'var(--bz-text-2)' }}>
                Gender
              </p>
              <p className="text-sm">
                {profile.gender === 'M' ? (
                  'Male'
                ) : profile.gender === 'F' ? (
                  'Female'
                ) : (
                  <span className="italic" style={{ color: 'var(--bz-text-3)' }}>
                    Not provided
                  </span>
                )}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// PASSPORT CARD (Center) - Upload + OCR Data
// ============================================================================
function PassportCard({
  profile,
  passportValidity,
}: {
  profile: PortalProfile;
  passportValidity: PassportValidityInfo;
}) {
  const hasPassport = !!profile.passportNumber;

  return (
    <div
      className="rounded-xl border overflow-hidden flex flex-col backdrop-blur-xl shadow-2xl transition-all duration-300 hover:shadow-[0_8px_30px_rgb(0,0,0,0.12)]"
      style={{
        background: 'rgba(30, 30, 35, 0.7)',
        borderColor: 'rgba(255, 255, 255, 0.05)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2 px-4 py-3 border-b"
        style={{ borderColor: 'rgba(255, 255, 255, 0.05)' }}
      >
        <CreditCard className="w-5 h-5" style={{ color: 'var(--bz-accent-warm)' }} />
        <h3 className="font-semibold">Passport</h3>
        {profile.gender && (
          <span
            className={cn(
              'ml-auto px-2 py-0.5 rounded-full text-xs font-bold',
              profile.gender === 'M'
                ? 'bg-blue-500/20 text-blue-400'
                : 'bg-pink-500/20 text-pink-400'
            )}
          >
            {profile.gender}
          </span>
        )}
      </div>

      {/* Content */}
      <div className="p-4 flex-1 flex flex-col space-y-4">
        {/* Passport Image Preview */}
        {hasPassport ? (
          <div
            className="aspect-[3/2] rounded-lg border flex items-center justify-center overflow-hidden"
            style={{
              background: 'rgba(255, 255, 255, 0.02)',
              borderColor: 'rgba(255, 255, 255, 0.05)',
            }}
          >
            {/* TODO: Show actual passport image from Google Drive */}
            <div className="text-center">
              <CreditCard
                className="w-12 h-12 mx-auto mb-2"
                style={{ color: 'var(--bz-text-3)' }}
              />
              <p className="text-xs" style={{ color: 'var(--bz-text-2)' }}>
                Passport document
              </p>
            </div>
          </div>
        ) : (
          <div
            className="aspect-[3/2] rounded-lg border-2 border-dashed flex flex-col items-center justify-center"
            style={{
              background: 'rgba(255, 255, 255, 0.02)',
              borderColor: 'rgba(255, 255, 255, 0.05)',
            }}
          >
            <CreditCard className="w-10 h-10 mb-2" style={{ color: 'var(--bz-text-3)' }} />
            <span className="text-sm" style={{ color: 'var(--bz-text-2)' }}>
              No passport uploaded
            </span>
          </div>
        )}

        {/* Upload Button (if no passport) */}
        {!hasPassport && (
          <Button
            variant="outline"
            className="w-full gap-2"
            onClick={() => {
              window.location.href = '/portal/vault';
            }}
          >
            <Upload className="w-4 h-4" />
            Upload Passport
          </Button>
        )}

        {/* OCR Data - Automatically extracted */}
        <div className="space-y-2">
          <h4
            className="text-xs font-semibold uppercase tracking-wider flex items-center gap-1"
            style={{ color: 'var(--bz-text-2)' }}
          >
            <span>Extracted Data (OCR)</span>
          </h4>

          {/* Passport Number */}
          <div
            className="flex items-center justify-between p-2 rounded-lg"
            style={{ background: 'rgba(255, 255, 255, 0.03)' }}
          >
            <span className="text-xs" style={{ color: 'var(--bz-text-2)' }}>
              Passport No.
            </span>
            <span className="font-mono text-sm font-medium">{profile.passportNumber || '—'}</span>
          </div>

          {/* Expiry with Alert */}
          {profile.passportExpiry ? (
            <div
              className={cn(
                'rounded-lg p-2 text-sm',
                passportValidity.alertLevel === 'critical' &&
                  'border border-red-500/40 animate-pulse',
                passportValidity.alertLevel === 'warning' && 'border border-yellow-500/30'
              )}
              style={{
                background:
                  passportValidity.alertLevel === 'expired' ||
                  passportValidity.alertLevel === 'critical'
                    ? 'rgba(239,68,68,0.08)'
                    : passportValidity.alertLevel === 'warning'
                      ? 'rgba(245,158,11,0.08)'
                      : passportValidity.alertLevel === 'ok'
                        ? 'rgba(16,185,129,0.08)'
                        : 'rgba(255, 255, 255, 0.03)',
              }}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase opacity-80">Expiry Date</span>
                <span
                  className="font-semibold"
                  style={{
                    color:
                      passportValidity.alertLevel === 'ok'
                        ? '#34d399'
                        : passportValidity.alertLevel === 'warning'
                          ? '#fbbf24'
                          : '#f87171',
                  }}
                >
                  {formatDate(profile.passportExpiry)}
                </span>
              </div>
              <div className="flex items-center justify-between mt-1">
                <span className="text-xs opacity-70">Time remaining</span>
                <span
                  className="text-xs font-medium"
                  style={{
                    color:
                      passportValidity.alertLevel === 'ok'
                        ? '#34d399'
                        : passportValidity.alertLevel === 'warning'
                          ? '#fbbf24'
                          : '#f87171',
                  }}
                >
                  {passportValidity.label}
                </span>
              </div>
              {passportValidity.alertLevel === 'warning' && (
                <p className="mt-2 text-xs text-yellow-400 flex items-start gap-1">
                  <AlertCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                  <span>
                    Your passport expires in less than 14 months. Contact your embassy to begin
                    renewal process.
                  </span>
                </p>
              )}
              {passportValidity.alertLevel === 'critical' && (
                <p className="mt-2 text-xs text-red-400 font-medium flex items-start gap-1">
                  <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                  <span>
                    URGENT: Your passport expires in less than 9 months. You may not be able to
                    travel internationally. Contact your embassy immediately!
                  </span>
                </p>
              )}
              {passportValidity.alertLevel === 'expired' && (
                <p className="mt-2 text-xs text-red-400 font-bold flex items-start gap-1">
                  <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                  <span>
                    Your passport has EXPIRED! Contact your embassy immediately for emergency
                    renewal.
                  </span>
                </p>
              )}
            </div>
          ) : (
            <div
              className="p-2 rounded-lg text-center"
              style={{ background: 'rgba(255, 255, 255, 0.03)' }}
            >
              <span className="text-xs" style={{ color: 'var(--bz-text-2)' }}>
                No expiry date detected
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// VISA PROCESS CARD (Right) - Process → Electronic → Actual
// ============================================================================
function VisaProcessCard({
  status,
  visaInfo,
}: {
  status: 'process' | 'electronic' | 'actual';
  visaInfo: VisaInfo | null;
}) {
  const currentVisa = visaInfo?.current;
  const daysRemaining = currentVisa?.daysRemaining;
  const isCritical = daysRemaining != null && daysRemaining <= 60;

  // Render based on status
  if (status === 'process') {
    return <ProcessCard />;
  }

  if (status === 'electronic') {
    return <ElectronicVisaCard />;
  }

  return (
    <div
      className="rounded-xl border overflow-hidden flex flex-col backdrop-blur-xl shadow-2xl transition-all duration-300 hover:shadow-[0_8px_30px_rgb(0,0,0,0.12)]"
      style={{
        background: 'rgba(30, 30, 35, 0.7)',
        borderColor: 'rgba(255, 255, 255, 0.05)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2 px-4 py-3 border-b"
        style={{ borderColor: 'rgba(255, 255, 255, 0.05)' }}
      >
        <FileText className="w-5 h-5" style={{ color: 'var(--bz-accent-warm)' }} />
        <h3 className="font-semibold">Actual Visa</h3>
      </div>

      {/* Content */}
      <div className="p-4 flex-1 flex flex-col space-y-4">
        {/* Visa Image */}
        <div
          className="aspect-[3/2] rounded-lg border flex items-center justify-center"
          style={{
            background: 'rgba(255, 255, 255, 0.02)',
            borderColor: 'rgba(255, 255, 255, 0.05)',
          }}
        >
          {currentVisa ? (
            <div className="text-center">
              <Plane className="w-12 h-12 mx-auto mb-2" style={{ color: 'var(--bz-text-3)' }} />
              <p className="text-xs" style={{ color: 'var(--bz-text-2)' }}>
                {currentVisa.type}
              </p>
            </div>
          ) : (
            <>
              <FileText className="w-10 h-10 mb-2" style={{ color: 'var(--bz-text-3)' }} />
              <span className="text-sm" style={{ color: 'var(--bz-text-2)' }}>
                No visa
              </span>
            </>
          )}
        </div>

        {/* Visa Data */}
        {currentVisa && (
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span style={{ color: 'var(--bz-text-2)' }}>Type:</span>
              <span className="font-medium">{currentVisa.type}</span>
            </div>

            <div className="flex items-center justify-between text-sm">
              <span style={{ color: 'var(--bz-text-2)' }}>Start:</span>
              <span>{formatDate(currentVisa.issueDate)}</span>
            </div>

            {/* Expiry with Alert */}
            <div
              className={cn(
                'rounded-lg p-2 text-sm',
                isCritical && 'border-2 border-red-500/40 animate-pulse'
              )}
              style={
                isCritical
                  ? { background: 'rgba(239,68,68,0.1)' }
                  : { background: 'rgba(255, 255, 255, 0.03)' }
              }
            >
              <div className="flex items-center justify-between">
                <span className={cn('text-xs uppercase', isCritical && 'font-bold')}>
                  Exp Visa:
                </span>
                <span className="font-semibold" style={isCritical ? { color: '#f87171' } : {}}>
                  {formatDate(currentVisa.expiryDate)}
                </span>
              </div>
              {isCritical && (
                <p className="mt-1 text-xs text-red-400 font-medium flex items-start gap-1">
                  <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                  <span>
                    URGENT: Your visa expires in less than 2 months. Contact us immediately to plan
                    renewal or communicate your departure!
                  </span>
                </p>
              )}
            </div>

            {/* Days remaining indicator */}
            {daysRemaining != null && (
              <div className="flex justify-end">
                <span
                  className="text-[11px] px-2 py-1 rounded-full font-semibold tabular-nums"
                  style={{
                    background: isCritical ? 'rgba(239,68,68,0.12)' : 'rgba(16,185,129,0.10)',
                    color: isCritical ? '#f87171' : '#34d399',
                  }}
                >
                  {(daysRemaining as number) <= 0
                    ? `Expired ${Math.abs(daysRemaining as number)}d ago`
                    : (daysRemaining as number) <= 365
                      ? `⏰ ${daysRemaining}d left`
                      : `${Math.floor((daysRemaining as number) / 30)}mo left`}
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// Process Status Card (Initial state)
function ProcessCard() {
  return (
    <div
      className="rounded-xl border overflow-hidden flex flex-col backdrop-blur-xl shadow-2xl transition-all duration-300 hover:shadow-[0_8px_30px_rgb(0,0,0,0.12)]"
      style={{
        background: 'rgba(30, 30, 35, 0.7)',
        borderColor: 'rgba(255, 255, 255, 0.05)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2 px-4 py-3 border-b"
        style={{ borderColor: 'rgba(255, 255, 255, 0.05)' }}
      >
        <FolderOpen className="w-5 h-5" style={{ color: 'var(--bz-accent-warm)' }} />
        <h3 className="font-semibold">Process</h3>
      </div>

      {/* Content */}
      <div className="p-4 flex-1 flex flex-col items-center justify-center space-y-4 min-h-[300px]">
        <div className="w-20 h-20 rounded-full bg-blue-500/10 flex items-center justify-center">
          <Loader className="w-10 h-10 text-blue-400 animate-spin" />
        </div>

        <div className="text-center">
          <p className="text-lg font-semibold text-blue-400">Visa on process</p>
          <p className="text-sm mt-1" style={{ color: 'var(--bz-text-2)' }}>
            Your application is being processed
          </p>
        </div>

        <div className="w-full space-y-2 pt-4">
          <div className="flex items-center gap-2 text-sm">
            <CheckCircle className="w-4 h-4 text-green-500" />
            <span>Documents received</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <CheckCircle className="w-4 h-4 text-green-500" />
            <span>Application submitted</span>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <Loader className="w-4 h-4 text-blue-500 animate-spin" />
            <span>Under review</span>
          </div>
        </div>

        <p className="text-xs text-center pt-4" style={{ color: 'var(--bz-text-2)' }}>
          You will be notified when your visa is ready
        </p>
      </div>
    </div>
  );
}

// Electronic Visa Card (Intermediate state)
function ElectronicVisaCard() {
  return (
    <div
      className="rounded-xl border overflow-hidden flex flex-col backdrop-blur-xl shadow-2xl transition-all duration-300 hover:shadow-[0_8px_30px_rgb(0,0,0,0.12)]"
      style={{
        background: 'rgba(30, 30, 35, 0.7)',
        borderColor: 'rgba(255, 255, 255, 0.05)',
      }}
    >
      {/* Header */}
      <div
        className="flex items-center gap-2 px-4 py-3 border-b"
        style={{ borderColor: 'rgba(255, 255, 255, 0.05)' }}
      >
        <FileText className="w-5 h-5" style={{ color: 'var(--bz-accent-warm)' }} />
        <h3 className="font-semibold">Electronic Visa</h3>
      </div>

      {/* Content */}
      <div className="p-4 flex-1 flex flex-col space-y-4">
        <div
          className="aspect-[3/2] rounded-lg border flex items-center justify-center"
          style={{
            background: 'rgba(255, 255, 255, 0.02)',
            borderColor: 'rgba(255, 255, 255, 0.05)',
          }}
        >
          <div className="text-center">
            <FileText className="w-12 h-12 text-green-500/70 mx-auto mb-2" />
            <p className="text-sm" style={{ color: 'var(--bz-text-2)' }}>
              E-Visa document
            </p>
          </div>
        </div>

        <div className="p-3 rounded-lg" style={{ background: 'rgba(16,185,129,0.08)' }}>
          <p className="text-sm text-green-400 flex items-center gap-2">
            <CheckCircle className="w-4 h-4" />
            <span>Electronic visa approved</span>
          </p>
          <p className="text-xs mt-1" style={{ color: 'var(--bz-text-2)' }}>
            Your physical visa card (KITAS/IMK) will be processed next
          </p>
        </div>

        <Button
          variant="outline"
          className="w-full gap-2"
          onClick={() => {
            window.location.href = '/portal/vault';
          }}
        >
          <Upload className="w-4 h-4" />
          Download E-Visa
        </Button>
      </div>
    </div>
  );
}
