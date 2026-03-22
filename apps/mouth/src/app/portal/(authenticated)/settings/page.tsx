"use client";

import React, { useEffect, useState } from "react";
import { Loader2, Bell, Mail, MessageCircle, Globe, Save } from "lucide-react";
import { api } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { cn } from "@/lib/utils";
import { logger } from "@/lib/logger";
import type { PortalPreferences } from "@/lib/api/portal/portal.types";
import { Button } from "@/components/ui/button";

export default function SettingsPage() {
  const { success, error } = useToast();
  const [preferences, setPreferences] = useState<PortalPreferences | null>(
    null,
  );
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    loadPreferences();
  }, []);

  const loadPreferences = async () => {
    try {
      setIsLoading(true);
      const data = await api.portal.getPreferences();
      setPreferences(data);
    } catch (err) {
      error("Failed to load settings", "Please try again later");
      logger.error("Failed to load portal settings", {}, err as Error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleToggle = (key: keyof PortalPreferences) => {
    if (!preferences) return;

    setPreferences((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        [key]: typeof prev[key] === "boolean" ? !prev[key] : prev[key],
      };
    });
    setHasChanges(true);
  };

  const handleSave = async () => {
    if (!preferences || !hasChanges) return;

    try {
      setIsSaving(true);
      const updated = await api.portal.updatePreferences({
        emailNotifications: preferences.emailNotifications,
        whatsappNotifications: preferences.whatsappNotifications,
      });
      setPreferences(updated);
      setHasChanges(false);
      success("Settings saved", "Your preferences have been updated");
    } catch (err) {
      error("Failed to save settings", "Please try again");
      logger.error("Failed to save portal settings", {}, err as Error);
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2
          className="w-8 h-8 animate-spin"
          style={{ color: "var(--bz-accent-warm)" }}
        />
      </div>
    );
  }

  if (!preferences) return null;

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* Header */}
      <section>
        <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
        <p style={{ color: "var(--bz-text-2)" }}>
          Manage your notification preferences
        </p>
      </section>

      {/* Notifications Section */}
      <section
        className="rounded-xl border p-6 space-y-6"
        style={{
          background: "rgba(30,30,35,0.7)",
          borderColor: "rgba(255,255,255,0.05)",
          backdropFilter: "blur(24px)",
        }}
      >
        <div className="flex items-center gap-2">
          <Bell
            className="w-5 h-5"
            style={{ color: "var(--bz-accent-warm)" }}
          />
          <h2 className="text-lg font-semibold">Notifications</h2>
        </div>

        <div className="space-y-4">
          <ToggleSetting
            icon={Mail}
            label="Email Notifications"
            description="Receive updates and alerts via email"
            checked={preferences.emailNotifications}
            onChange={() => handleToggle("emailNotifications")}
          />

          <ToggleSetting
            icon={MessageCircle}
            label="WhatsApp Notifications"
            description="Get instant updates on WhatsApp"
            checked={preferences.whatsappNotifications}
            onChange={() => handleToggle("whatsappNotifications")}
          />
        </div>
      </section>

      {/* Regional Settings (Read-only) */}
      <section
        className="rounded-xl border p-6 space-y-4"
        style={{
          background: "rgba(30,30,35,0.7)",
          borderColor: "rgba(255,255,255,0.05)",
          backdropFilter: "blur(24px)",
        }}
      >
        <div className="flex items-center gap-2">
          <Globe
            className="w-5 h-5"
            style={{ color: "var(--bz-accent-warm)" }}
          />
          <h2 className="text-lg font-semibold">Regional Settings</h2>
        </div>

        <div className="space-y-3">
          <ReadOnlyField
            label="Language"
            value={preferences.language.toUpperCase()}
          />
          <ReadOnlyField label="Timezone" value={preferences.timezone} />
        </div>

        <p
          className="text-xs pt-2 border-t"
          style={{ color: "var(--bz-text-2)", borderColor: "var(--bz-border)" }}
        >
          To change language or timezone, please contact support.
        </p>
      </section>

      {/* Save Button */}
      {hasChanges && (
        <section className="sticky bottom-20 md:bottom-4">
          <Button
            onClick={handleSave}
            disabled={isSaving}
            className="w-full h-12 text-base font-semibold shadow-lg"
          >
            {isSaving ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin mr-2" />
                Saving...
              </>
            ) : (
              <>
                <Save className="w-5 h-5 mr-2" />
                Save Changes
              </>
            )}
          </Button>
        </section>
      )}
    </div>
  );
}

// Sub-components
function ToggleSetting({
  icon: Icon,
  label,
  description,
  checked,
  onChange,
}: {
  icon: React.ElementType;
  label: string;
  description: string;
  checked: boolean;
  onChange: () => void;
}) {
  return (
    <div
      className="flex items-center justify-between gap-4 p-4 rounded-lg border transition-colors"
      style={{
        background: "rgba(255,255,255,0.03)",
        borderColor: "rgba(255,255,255,0.05)",
      }}
    >
      <div className="flex items-start gap-3 flex-1 min-w-0">
        <div
          className="p-2 rounded-md mt-0.5"
          style={{ background: "rgba(201,169,110,0.1)" }}
        >
          <Icon
            className="w-4 h-4"
            style={{ color: "var(--bz-accent-warm)" }}
          />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-medium text-sm">{label}</p>
          <p className="text-xs mt-0.5" style={{ color: "var(--bz-text-2)" }}>
            {description}
          </p>
        </div>
      </div>

      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={onChange}
        className={cn(
          "relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none",
          checked ? "bg-emerald-500" : "",
        )}
        style={!checked ? { background: "var(--bz-border)" } : {}}
      >
        <span
          aria-hidden="true"
          className={cn(
            "pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-lg ring-0 transition duration-200 ease-in-out",
            checked ? "translate-x-5" : "translate-x-0",
          )}
        />
      </button>
    </div>
  );
}

function ReadOnlyField({ label, value }: { label: string; value: string }) {
  return (
    <div
      className="flex items-center justify-between p-3 rounded-lg"
      style={{ background: "rgba(255,255,255,0.03)" }}
    >
      <span className="text-sm" style={{ color: "var(--bz-text-2)" }}>
        {label}
      </span>
      <span className="text-sm font-medium">{value}</span>
    </div>
  );
}
