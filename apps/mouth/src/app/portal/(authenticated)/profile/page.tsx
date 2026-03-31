'use client';

import React, { useEffect, useState } from 'react';
import {
  User,
  Mail,
  Phone,
  MapPin,
  Calendar,
  Globe,
  AlertTriangle,
  AlertCircle,
  CreditCard,
  Lock,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/toast';
import { cn } from '@/lib/utils';
import { logger } from '@/lib/logger';
import { Button } from '@/components/ui/button';
import type { PortalProfile } from '@/lib/api/portal/portal.types';

// ============================================================================
// ALERT UTILITIES (same as workspace)
// ============================================================================

type PassportAlertLevel = 'ok' | 'warning' | 'critical' | 'expired';

interface PassportValidityInfo {
  color: string;
  label: string;
  alertLevel: PassportAlertLevel;
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

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function ProfilePage() {
  const { error } = useToast();
  const [profile, setProfile] = useState<PortalProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [editData, setEditData] = useState({ phone: '', whatsapp: '', address: '' });

  useEffect(() => {
    loadProfile();
  }, []);

  const loadProfile = async () => {
    try {
      setIsLoading(true);
      const data = await api.portal.getProfile();
      setProfile(data);
    } catch (err) {
      error('Failed to load profile', 'Please try again later');
      logger.error('Failed to load portal profile', {}, err as Error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleEdit = () => {
    if (!profile) return;
    setEditData({
      phone: profile.phone || '',
      whatsapp: profile.whatsapp || '',
      address: profile.address || '',
    });
    setIsEditing(true);
  };

  const handleSave = async () => {
    try {
      setIsSaving(true);
      const updated = await api.portal.updateProfile({
        phone: editData.phone || undefined,
        whatsapp: editData.whatsapp || undefined,
        address: editData.address || undefined,
      });
      setProfile(updated);
      setIsEditing(false);
    } catch (err) {
      error('Failed to update profile', 'Please try again');
      logger.error('Failed to update portal profile', {}, err as Error);
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6 animate-in fade-in duration-500">
        <section>
          <div
            className="h-7 w-32 rounded animate-pulse"
            style={{ background: 'var(--bz-border)' }}
          />
          <div
            className="h-4 w-52 rounded mt-2 animate-pulse"
            style={{ background: 'var(--bz-border)', opacity: 0.5 }}
          />
        </section>
        <div
          className="rounded-xl border p-6 space-y-4 animate-pulse"
          style={{ background: 'rgba(30,30,35,0.7)', borderColor: 'rgba(255,255,255,0.05)' }}
        >
          <div className="flex items-center gap-4">
            <div
              className="w-16 h-16 rounded-full"
              style={{ background: 'var(--bz-border)' }}
            />
            <div className="space-y-2 flex-1">
              <div className="h-5 w-40 rounded" style={{ background: 'var(--bz-border)' }} />
              <div className="h-4 w-56 rounded" style={{ background: 'var(--bz-border)', opacity: 0.5 }} />
            </div>
          </div>
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-12 rounded"
              style={{ background: 'var(--bz-border)', opacity: 0.4 }}
            />
          ))}
        </div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="space-y-6 animate-in fade-in duration-500">
        <section>
          <h1 className="text-2xl font-bold tracking-tight">Your Profile</h1>
          <p style={{ color: 'var(--bz-text-2)' }}>View your personal information</p>
        </section>
        <section
          className="rounded-xl border border-dashed p-12 text-center"
          style={{
            background: 'rgba(30,30,35,0.7)',
            borderColor: 'rgba(255,255,255,0.05)',
          }}
        >
          <User className="w-16 h-16 mx-auto mb-4 opacity-30" style={{ color: 'var(--bz-text-2)' }} />
          <h2 className="text-lg font-semibold" style={{ color: 'var(--bz-text-2)' }}>
            Unable to load profile
          </h2>
          <p className="text-sm mt-1" style={{ color: 'var(--bz-text-3)' }}>
            Please refresh the page or contact support if the issue persists.
          </p>
        </section>
      </div>
    );
  }

  // Calculate alerts
  const passportValidity = getPassportValidityColor(profile.passportExpiry);
  const isBirthday = isBirthdayToday(profile.dateOfBirth);

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section>
        <h1 className="text-2xl font-bold tracking-tight">Your Profile</h1>
        <p style={{ color: 'var(--bz-text-2)' }}>View your personal information</p>
      </section>

      {/* Profile Card */}
      <section
        className="rounded-xl border p-6 space-y-6"
        style={{
          background: 'rgba(30,30,35,0.7)',
          borderColor: 'rgba(255,255,255,0.05)',
          backdropFilter: 'blur(24px)',
        }}
      >
        {/* Avatar */}
        <div className="flex flex-col items-center gap-3">
          <div className="relative">
            <div
              className={cn(
                'w-20 h-20 rounded-full flex items-center justify-center transition-all duration-500',
                isBirthday &&
                  'bg-gradient-to-br from-yellow-300 via-amber-300 to-yellow-400 animate-pulse shadow-[0_0_30px_rgba(255,215,0,0.6)]'
              )}
              style={!isBirthday ? { background: 'rgba(201,169,110,0.15)' } : {}}
            >
              <User
                className={cn('w-10 h-10 transition-colors', isBirthday ? 'text-yellow-700' : '')}
                style={!isBirthday ? { color: 'var(--bz-accent-warm)' } : {}}
              />
            </div>
            {/* Birthday Badge */}
            {isBirthday && (
              <div className="absolute -top-1 -right-1 w-8 h-8 bg-red-500 rounded-full flex items-center justify-center text-white text-lg animate-bounce">
                🎂
              </div>
            )}
            {/* Gender Badge */}
            {profile.gender && (
              <div
                className={cn(
                  'absolute -bottom-1 -right-1 w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border-2',
                  profile.gender === 'M' ? 'bg-blue-500 text-white' : 'bg-pink-500 text-white'
                )}
              >
                {profile.gender}
              </div>
            )}
          </div>
          <div className="text-center">
            <h2 className="text-xl font-bold">{profile.fullName}</h2>
            <p className="text-sm" style={{ color: 'var(--bz-text-2)' }}>
              Member since{' '}
              {new Date(profile.memberSince).toLocaleDateString('en-US', {
                month: 'long',
                year: 'numeric',
              })}
            </p>
            {isBirthday && (
              <p className="text-sm font-medium mt-1 animate-pulse" style={{ color: '#fbbf24' }}>
                🎉 Happy Birthday! 🎉
              </p>
            )}
          </div>
        </div>

        {/* Info Fields */}
        <div className="space-y-4 pt-4 border-t" style={{ borderColor: 'var(--bz-border)' }}>
          <ProfileField icon={Mail} label="Email" value={profile.email} />
          <ProfileField
            icon={Phone}
            label="Phone"
            value={profile.phone || 'Not provided'}
            muted={!profile.phone}
          />
          <ProfileField
            icon={Phone}
            label="WhatsApp"
            value={profile.whatsapp || 'Not provided'}
            muted={!profile.whatsapp}
          />
          <ProfileField
            icon={Globe}
            label="Nationality"
            value={profile.nationality || 'Not provided'}
            muted={!profile.nationality}
          />

          {/* Date of Birth with Birthday Glow */}
          {profile.dateOfBirth && (
            <div
              className="flex items-start gap-3 p-3 rounded-lg transition-all duration-500"
              style={
                isBirthday
                  ? {
                      background: 'rgba(251,191,36,0.15)',
                      boxShadow: '0 0 20px rgba(255,215,0,0.3)',
                    }
                  : {}
              }
            >
              <div
                className="p-2 rounded-md"
                style={
                  isBirthday
                    ? { background: 'rgba(251,191,36,0.25)' }
                    : { background: 'rgba(255,255,255,0.03)' }
                }
              >
                <Calendar
                  className={cn('w-4 h-4', isBirthday && 'text-yellow-400')}
                  style={!isBirthday ? { color: 'var(--bz-text-2)' } : {}}
                />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs mb-0.5" style={{ color: 'var(--bz-text-2)' }}>
                  Date of Birth
                </p>
                <p
                  className={cn('text-sm font-medium break-words', isBirthday && 'font-bold')}
                  style={isBirthday ? { color: '#fbbf24' } : {}}
                >
                  {formatDate(profile.dateOfBirth)}
                  {isBirthday && ' 🎂 (Today!)'}
                </p>
              </div>
            </div>
          )}

          {/* Passport Number */}
          {profile.passportNumber && (
            <ProfileField
              icon={CreditCard}
              label="Passport Number"
              value={profile.passportNumber}
            />
          )}

          {/* Passport Expiry with Alert */}
          {profile.passportExpiry && (
            <div
              className={cn(
                'flex items-start gap-3 p-3 rounded-lg border',
                passportValidity.alertLevel === 'critical' && 'animate-pulse'
              )}
              style={{
                background:
                  passportValidity.alertLevel === 'ok'
                    ? 'rgba(16,185,129,0.06)'
                    : passportValidity.alertLevel === 'warning'
                      ? 'rgba(245,158,11,0.06)'
                      : 'rgba(239,68,68,0.08)',
                borderColor:
                  passportValidity.alertLevel === 'ok'
                    ? 'rgba(16,185,129,0.25)'
                    : passportValidity.alertLevel === 'warning'
                      ? 'rgba(245,158,11,0.3)'
                      : 'rgba(239,68,68,0.35)',
              }}
            >
              <div
                className="p-2 rounded-md"
                style={{
                  background:
                    passportValidity.alertLevel === 'ok'
                      ? 'rgba(16,185,129,0.12)'
                      : passportValidity.alertLevel === 'warning'
                        ? 'rgba(245,158,11,0.12)'
                        : 'rgba(239,68,68,0.15)',
                }}
              >
                {passportValidity.alertLevel === 'ok' ? (
                  <Calendar className="w-4 h-4" style={{ color: '#34d399' }} />
                ) : (
                  <AlertTriangle
                    className="w-4 h-4"
                    style={{
                      color: passportValidity.alertLevel === 'warning' ? '#fbbf24' : '#f87171',
                    }}
                  />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs mb-0.5" style={{ color: 'var(--bz-text-2)' }}>
                  Passport Expiry
                </p>
                <p
                  className="text-sm font-medium break-words"
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
                  {(() => {
                    const days = Math.ceil(
                      (new Date(profile.passportExpiry).getTime() - Date.now()) / 86400000
                    );
                    const chipColor =
                      days <= 0
                        ? 'bg-red-500/15 text-red-400'
                        : days <= 270
                          ? 'bg-amber-500/10 text-amber-400'
                          : 'bg-emerald-500/10 text-emerald-400';
                    const chipText =
                      days <= 0
                        ? `Expired ${Math.abs(days)}d ago`
                        : days === 0
                          ? 'today'
                          : days <= 365
                            ? `⏰ ${days}d left`
                            : `${Math.floor(days / 30)}mo left`;
                    return (
                      <span
                        className={`ml-2 text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${chipColor}`}
                      >
                        {chipText}
                      </span>
                    );
                  })()}
                </p>
                {/* Alert Messages */}
                {passportValidity.alertLevel === 'warning' && (
                  <p className="mt-1 text-xs text-yellow-400">
                    <AlertCircle className="w-3 h-3 inline mr-1" />
                    Your passport expires in less than 14 months. Contact your embassy to begin
                    renewal process.
                  </p>
                )}
                {passportValidity.alertLevel === 'critical' && (
                  <p className="mt-1 text-xs text-red-400 font-medium">
                    <AlertCircle className="w-3 h-3 inline mr-1" />
                    URGENT: Your passport expires in less than 9 months. You may not be able to
                    travel internationally. Contact your embassy immediately!
                  </p>
                )}
                {passportValidity.alertLevel === 'expired' && (
                  <p className="mt-1 text-xs text-red-400 font-bold">
                    <AlertCircle className="w-3 h-3 inline mr-1" />
                    Your passport has EXPIRED! Contact your embassy immediately for emergency
                    renewal.
                  </p>
                )}
              </div>
            </div>
          )}

          {profile.address && (
            <ProfileField icon={MapPin} label="Address" value={profile.address} />
          )}
        </div>
      </section>

      {!isEditing ? (
        <section className="flex justify-end">
          <Button variant="outline" onClick={handleEdit}>Edit Profile</Button>
        </section>
      ) : (
        <section className="space-y-4 rounded-xl border p-6" style={{ background: 'rgba(30,30,35,0.7)', borderColor: 'rgba(255,255,255,0.05)', backdropFilter: 'blur(24px)' }}>
          <h2 className="text-lg font-semibold">Edit Profile</h2>
          <div className="space-y-3">
            <div>
              <label htmlFor="edit-phone" className="text-xs mb-1 block" style={{ color: 'var(--bz-text-2)' }}>Phone</label>
              <input id="edit-phone" type="tel" value={editData.phone} onChange={(e) => setEditData(prev => ({ ...prev, phone: e.target.value }))}
                className="w-full px-3 py-2 rounded-lg border text-sm" style={{ background: 'rgba(255,255,255,0.03)', borderColor: 'rgba(255,255,255,0.05)', color: 'var(--bz-text-1)' }} />
            </div>
            <div>
              <label htmlFor="edit-whatsapp" className="text-xs mb-1 block" style={{ color: 'var(--bz-text-2)' }}>WhatsApp</label>
              <input id="edit-whatsapp" type="tel" value={editData.whatsapp} onChange={(e) => setEditData(prev => ({ ...prev, whatsapp: e.target.value }))}
                className="w-full px-3 py-2 rounded-lg border text-sm" style={{ background: 'rgba(255,255,255,0.03)', borderColor: 'rgba(255,255,255,0.05)', color: 'var(--bz-text-1)' }} />
            </div>
            <div>
              <label htmlFor="edit-address" className="text-xs mb-1 block" style={{ color: 'var(--bz-text-2)' }}>Address</label>
              <textarea id="edit-address" value={editData.address} onChange={(e) => setEditData(prev => ({ ...prev, address: e.target.value }))}
                className="w-full px-3 py-2 rounded-lg border text-sm min-h-[80px]" style={{ background: 'rgba(255,255,255,0.03)', borderColor: 'rgba(255,255,255,0.05)', color: 'var(--bz-text-1)' }} />
            </div>
          </div>
          <div className="flex gap-2 justify-end">
            <Button variant="outline" onClick={() => setIsEditing(false)} disabled={isSaving}>Cancel</Button>
            <Button onClick={handleSave} disabled={isSaving}>{isSaving ? 'Saving...' : 'Save Changes'}</Button>
          </div>
        </section>
      )}
    </div>
  );
}

// ============================================================================
// SUB-COMPONENTS
// ============================================================================

function ProfileField({
  icon: Icon,
  label,
  value,
  muted,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  muted?: boolean;
}) {
  return (
    <div className="flex items-start gap-3 group" aria-label={`${label}: ${value} (read-only)`}>
      <div
        className="p-2 rounded-md backdrop-blur-sm shadow-sm"
        style={{ background: 'rgba(255,255,255,0.03)' }}
      >
        <Icon
          className="w-4 h-4"
          style={{ color: muted ? 'var(--bz-text-3)' : 'var(--bz-text-2)' }}
        />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1">
          <p className="text-xs mb-0.5" style={{ color: 'var(--bz-text-2)' }}>
            {label}
          </p>
          <Lock
            className="w-2.5 h-2.5 opacity-0 group-hover:opacity-30 transition-opacity"
            style={{ color: 'var(--bz-text-3)' }}
          />
        </div>
        <p
          className={cn('text-sm break-words', muted ? 'italic' : 'font-medium')}
          style={muted ? { color: 'var(--bz-text-3)' } : undefined}
        >
          {value}
        </p>
      </div>
    </div>
  );
}
