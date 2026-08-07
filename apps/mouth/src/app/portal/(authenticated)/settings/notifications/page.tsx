"use client";

/**
 * Portal notification preferences — channel opt-in (email, WhatsApp).
 *
 * WS3 slice 9 (GARUDA Day Edition, 2026-07-24): masthead = copper rule +
 * Cormorant serif (--font-serif) in --tx-pure; channel rows and the phone
 * input read the warm-paper surface tokens (--bz-card / --bz-border /
 * --glass-rim) with a copper focus ring and copper-accented checkboxes
 * (slice-7 settings pattern); saved/error feedback reads the semantic
 * --state-* tokens instead of the legacy --neon-* aliases (success 4.80 /
 * danger 5.74 :1 on paper).
 */

import { FormEvent, useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { AlertTriangle, CheckCircle2 } from "lucide-react";

interface PrefsResponse {
  email_enabled: boolean;
  wa_enabled: boolean;
  wa_phone: string | null;
}

const E164_RE = /^[1-9]\d{6,14}$/;

async function fetchPrefs(): Promise<PrefsResponse> {
  return api.request<PrefsResponse>("/api/portal/notifications/prefs", {
    method: "GET",
  });
}

async function savePrefs(body: PrefsResponse): Promise<PrefsResponse> {
  return api.request<PrefsResponse>("/api/portal/notifications/prefs", {
    method: "PUT",
    body: JSON.stringify(body),
    headers: { "Content-Type": "application/json" },
  });
}

export default function NotificationsSettingsPage() {
  const qc = useQueryClient();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["portal", "notification_prefs"],
    queryFn: fetchPrefs,
  });

  const [emailEnabled, setEmailEnabled] = useState(true);
  const [waEnabled, setWaEnabled] = useState(false);
  const [waPhone, setWaPhone] = useState("");
  const [phoneError, setPhoneError] = useState<string | null>(null);

  useEffect(() => {
    if (data) {
      setEmailEnabled(data.email_enabled);
      setWaEnabled(data.wa_enabled);
      setWaPhone(data.wa_phone ?? "");
    }
  }, [data]);

  const mutation = useMutation({
    mutationFn: savePrefs,
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["portal", "notification_prefs"] }),
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setPhoneError(null);
    const phone = waPhone.trim();
    if (waEnabled) {
      if (!phone) {
        setPhoneError("WhatsApp number required when WA notifications are on");
        return;
      }
      if (!E164_RE.test(phone)) {
        setPhoneError("Enter digits only, no leading + (e.g. 628123456789)");
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
            We could not verify your saved notification choices. Your settings
            have not been changed.
          </AlertDescription>
        </Alert>
        <Button type="button" variant="outline" onClick={() => void refetch()}>
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6 max-w-xl">
      {/* Day masthead: copper rule + Cormorant serif headline per concept. */}
      <section>
        <div
          aria-hidden="true"
          className="w-14 h-[3px] rounded-sm mb-4 bg-[var(--bz-copper)]"
        />
        <h1
          className="text-2xl font-semibold tracking-tight text-[var(--tx-pure)]"
          style={{ fontFamily: "var(--font-serif)" }}
        >
          Notification preferences
        </h1>
        <p className="text-sm text-[var(--tx-secondary)] mt-1">
          Choose how we reach you about deadlines and team messages.
        </p>
      </section>

      <form onSubmit={onSubmit} className="space-y-5">
        <label
          className="flex items-center justify-between gap-4 p-4 rounded-lg border"
          style={{
            background: "var(--bz-card)",
            borderColor: "var(--bz-border)",
            boxShadow: "0 14px 34px rgba(22, 33, 58, 0.07)",
          }}
        >
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
            className="w-5 h-5 accent-[var(--bz-copper)]"
          />
        </label>

        <label
          className="flex items-center justify-between gap-4 p-4 rounded-lg border"
          style={{
            background: "var(--bz-card)",
            borderColor: "var(--bz-border)",
            boxShadow: "0 14px 34px rgba(22, 33, 58, 0.07)",
          }}
        >
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
            className="w-5 h-5 accent-[var(--bz-copper)]"
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
              className="w-full px-3 py-2 rounded-lg border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--bz-copper)]"
              style={{
                background: "var(--bz-card)",
                borderColor: "var(--bz-border)",
                color: "var(--tx-primary)",
              }}
            />
            {phoneError && (
              <p className="text-xs text-[var(--state-danger)]">{phoneError}</p>
            )}
          </div>
        )}

        <div className="flex items-center gap-3">
          <Button type="submit" disabled={mutation.isPending}>
            {mutation.isPending ? "Saving…" : "Save"}
          </Button>
          {mutation.isSuccess && (
            <span className="text-sm text-[var(--state-success)] inline-flex items-center gap-1">
              <CheckCircle2 className="w-4 h-4" /> Saved
            </span>
          )}
          {mutation.isError && (
            <span role="alert" className="text-sm text-[var(--state-danger)]">
              Could not save your preferences. Your saved choices have not been
              changed.
            </span>
          )}
        </div>
      </form>
    </div>
  );
}
