'use client';

import React, { useEffect, useState } from 'react';
import { Loader2, User, Mail, Phone, MapPin, Calendar, Globe } from 'lucide-react';
import { api } from '@/lib/api';
import { useToast } from '@/components/ui/toast';
import { cn } from '@/lib/utils';
import type { PortalProfile } from '@/lib/api/portal/portal.types';

export default function ProfilePage() {
  const { error } = useToast();
  const [profile, setProfile] = useState<PortalProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);

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

  if (!profile) return null;

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section>
        <h1 className="text-2xl font-bold tracking-tight">Your Profile</h1>
        <p className="text-muted-foreground">View your personal information</p>
      </section>

      {/* Profile Card */}
      <section className="rounded-xl border bg-card p-6 space-y-6">
        {/* Avatar */}
        <div className="flex flex-col items-center gap-3">
          <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center">
            <User className="w-10 h-10 text-primary" />
          </div>
          <div className="text-center">
            <h2 className="text-xl font-bold">{profile.fullName}</h2>
            <p className="text-sm text-muted-foreground">
              Member since {new Date(profile.memberSince).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
            </p>
          </div>
        </div>

        {/* Info Fields */}
        <div className="space-y-4 pt-4 border-t">
          <ProfileField
            icon={Mail}
            label="Email"
            value={profile.email}
          />
          
          {profile.phone && (
            <ProfileField
              icon={Phone}
              label="Phone"
              value={profile.phone}
            />
          )}

          {profile.whatsapp && (
            <ProfileField
              icon={Phone}
              label="WhatsApp"
              value={profile.whatsapp}
            />
          )}

          {profile.nationality && (
            <ProfileField
              icon={Globe}
              label="Nationality"
              value={profile.nationality}
            />
          )}

          {profile.passportNumber && (
            <ProfileField
              icon={User}
              label="Passport Number"
              value={profile.passportNumber}
            />
          )}

          {profile.address && (
            <ProfileField
              icon={MapPin}
              label="Address"
              value={profile.address}
            />
          )}
        </div>
      </section>

      {/* Info Notice */}
      <section className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/20 p-4">
        <p className="text-sm text-amber-800 dark:text-amber-400">
          To update your profile information, please contact your account manager or send us a message through the Chat.
        </p>
      </section>
    </div>
  );
}

// Sub-component
function ProfileField({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ElementType;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <div className="p-2 rounded-md bg-neutral-100 dark:bg-neutral-800">
        <Icon className="w-4 h-4 text-neutral-600 dark:text-neutral-400" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-muted-foreground mb-0.5">{label}</p>
        <p className="text-sm font-medium break-words">{value}</p>
      </div>
    </div>
  );
}
