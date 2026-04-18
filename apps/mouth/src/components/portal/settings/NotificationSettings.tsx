"use client";

import { useNotificationPrefs } from "@/hooks/useNotificationPrefs";

/**
 * Notification channel preferences (email + WhatsApp).
 *
 * Wires directly to `GET/PUT /api/portal/notifications/prefs`. Migration
 * 110 can be absent on the deployed DB — the hook catches the BE 503 and
 * exposes `migrationMissing`, which we render as a graceful "coming
 * soon" banner rather than a hard error. Under no circumstances do we
 * fake the toggles: when prefs cannot be read, controls are hidden.
 */
export function NotificationSettings() {
  const { data, migrationMissing, isLoading, error, updatePrefs } =
    useNotificationPrefs();

  if (isLoading) {
    return <p className="text-sm text-[#c9a96e]/60">Loading…</p>;
  }

  if (migrationMissing) {
    return (
      <section className="space-y-4">
        <p role="alert" className="text-sm text-[#c9a14a]">
          Notification preferences are temporarily unavailable. Our team is
          working on it — please check back soon.
        </p>
      </section>
    );
  }

  if (error || !data) {
    return (
      <p role="alert" className="text-sm text-[#c94a4a]">
        Unable to load preferences.
      </p>
    );
  }

  return (
    <section className="space-y-4 max-w-md">
      <Toggle
        checked={data.email_enabled}
        onChange={(v) => updatePrefs({ ...data, email_enabled: v })}
        label="Email notifications"
      />
      <Toggle
        checked={data.wa_enabled}
        onChange={(v) => updatePrefs({ ...data, wa_enabled: v })}
        label="WhatsApp notifications"
      />
      {data.wa_enabled && (
        <div>
          <label
            htmlFor="wa-phone-input"
            className="text-xs uppercase tracking-[2px] text-[#c9a96e]/50 block mb-1"
          >
            WhatsApp number
          </label>
          <input
            id="wa-phone-input"
            type="tel"
            defaultValue={data.wa_phone ?? ""}
            onBlur={(e) =>
              updatePrefs({ ...data, wa_phone: e.target.value || null })
            }
            placeholder="628123456789"
            className="w-full px-3 py-2 bg-white/5 rounded border border-white/10 text-sm text-[#f0ece4]"
          />
          <p className="text-[10px] text-[#c9a96e]/40 mt-1">
            Format: country code + number, no leading +. Example: 628123456789.
          </p>
        </div>
      )}
    </section>
  );
}

function Toggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <label className="flex items-center gap-3 cursor-pointer">
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        className="w-4 h-4 accent-[#d4845a]"
      />
      <span className="text-sm text-[#f0ece4]">{label}</span>
    </label>
  );
}
