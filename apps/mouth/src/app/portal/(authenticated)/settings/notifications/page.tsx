'use client';

/**
 * Portal notification preferences — channel opt-in (email, WhatsApp).
 */

import { FormEvent, useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { AlertTriangle, CheckCircle2 } from 'lucide-react';

interface PrefsResponse {
  email_enabled: boolean;
  wa_enabled: boolean;
  wa_phone: string | null;
}

const E164_RE = /^[1-9]\d{6,14}$/;

async function fetchPrefs(): Promise<PrefsResponse> {
  return api.request<PrefsResponse>('/api/portal/notifications/prefs', {
    method: 'GET',
  });
}

async function savePrefs(body: PrefsResponse): Promise<PrefsResponse> {
  return api.request<PrefsResponse>('/api/portal/notifications/prefs', {
    method: 'PUT',
    body: JSON.stringify(body),
    headers: { 'Content-Type': 'application/json' },
  });
}

export default function NotificationsSettingsPage() {
  const qc = useQueryClient();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['portal', 'notification_prefs'],
    queryFn: fetchPrefs,
  });

  const [emailEnabled, setEmailEnabled] = useState(true);
  const [waEnabled, setWaEnabled] = useState(false);
  const [waPhone, setWaPhone] = useState('');
  const [phoneError, setPhoneError] = useState<string | null>(null);

  useEffect(() => {
    if (data) {
      setEmailEnabled(data.email_enabled);
      setWaEnabled(data.wa_enabled);
      setWaPhone(data.wa_phone ?? '');
    }
  }, [data]);

  const mutation = useMutation({
    mutationFn: savePrefs,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portal', 'notification_prefs'] }),
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setPhoneError(null);
    const phone = waPhone.trim();
    if (waEnabled) {
      if (!phone) {
        setPhoneError('WhatsApp number required when WA notifications are on');
        return;
      }
      if (!E164_RE.test(phone)) {
        setPhoneError('Enter digits only, no leading + (e.g. 628123456789)');
        return;
      }
    }
    mutation.mutate({
      email_enabled: emailEnabled,
      wa_enabled: waEnabled,
      wa_phone: phone || null,
    });
  };

  if (isLoading) {
    return (
      <div className="p-6">
        <h1 className="text-2xl font-bold">Notifications</h1>
        <p className="text-sm text-[var(--tx-secondary)]">Loading…</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="p-6 space-y-4">
        <h1 className="text-2xl font-bold">Notifications</h1>
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Unable to load preferences</AlertTitle>
          <AlertDescription>
            {error instanceof Error ? error.message : 'Unexpected error.'}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-xl">
      <section>
        <h1 className="text-2xl font-bold tracking-tight lux-text-gradient">
          Notification preferences
        </h1>
        <p className="text-sm text-[var(--tx-secondary)] mt-1">
          Choose how we reach you about deadlines and team messages.
        </p>
      </section>

      <form onSubmit={onSubmit} className="space-y-5">
        <label className="flex items-center justify-between gap-4 p-4 rounded-lg border border-[var(--glass-rim)]">
          <div>
            <div className="font-medium text-[var(--tx-primary)]">Email</div>
            <div className="text-xs text-[var(--tx-secondary)]">
              Deadline reminders and status updates.
            </div>
          </div>
          <input
            type="checkbox"
            checked={emailEnabled}
            onChange={(e) => setEmailEnabled(e.target.checked)}
            className="w-5 h-5"
          />
        </label>

        <label className="flex items-center justify-between gap-4 p-4 rounded-lg border border-[var(--glass-rim)]">
          <div>
            <div className="font-medium text-[var(--tx-primary)]">WhatsApp</div>
            <div className="text-xs text-[var(--tx-secondary)]">
              Urgent deadline reminders only (every 6h scan).
            </div>
          </div>
          <input
            type="checkbox"
            checked={waEnabled}
            onChange={(e) => setWaEnabled(e.target.checked)}
            className="w-5 h-5"
          />
        </label>

        {waEnabled && (
          <div className="space-y-1">
            <label className="text-sm font-medium" htmlFor="wa_phone">
              WhatsApp number (E.164, no +)
            </label>
            <input
              id="wa_phone"
              type="tel"
              inputMode="numeric"
              value={waPhone}
              onChange={(e) => setWaPhone(e.target.value)}
              placeholder="628123456789"
              className="w-full px-3 py-2 rounded-lg border border-[var(--glass-rim)] bg-transparent text-[var(--tx-primary)]"
            />
            {phoneError && (
              <p className="text-xs text-[var(--neon-rose)]">{phoneError}</p>
            )}
          </div>
        )}

        <div className="flex items-center gap-3">
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? 'Saving…' : 'Save'}
          </Button>
          {mutation.isSuccess && (
            <span className="text-sm text-[var(--neon-emerald)] inline-flex items-center gap-1">
              <CheckCircle2 className="w-4 h-4" /> Saved
            </span>
          )}
          {mutation.isError && (
            <span className="text-sm text-[var(--neon-rose)]">
              {mutation.error instanceof Error
                ? mutation.error.message
                : 'Could not save'}
            </span>
          )}
        </div>
      </form>
    </div>
  );
}
