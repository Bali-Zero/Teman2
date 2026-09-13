"use client";

import React, { useState, useEffect } from "react";
import { User, ArrowLeft, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";
import type { UserProfile } from "@/types";

// Read-only on purpose: there is no profile-update endpoint yet, and the
// previous Save button only waited 500 ms and toasted "Profile saved".
export default function ProfileSettingsPage() {
  const router = useRouter();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadProfile = async () => {
      try {
        setProfile(await api.getProfile());
      } catch (err) {
        logger.error("Failed to load profile", {}, err as Error);
      } finally {
        setIsLoading(false);
      }
    };
    loadProfile();
  }, []);

  const rows: { label: string; value: string | undefined; mono?: boolean }[] = [
    { label: "Full Name", value: profile?.name },
    { label: "Email", value: profile?.email },
    { label: "Department / Team", value: profile?.team },
    { label: "Role", value: profile?.role },
    { label: "User ID", value: profile?.id, mono: true },
  ];

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => router.push("/settings")}
        >
          <ArrowLeft className="w-4 h-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-[var(--foreground)] flex items-center gap-2">
            <User className="w-6 h-6 text-[var(--bz-accent)]" />
            Profile
          </h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            Your account information
          </p>
        </div>
      </div>

      {isLoading ? (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6 flex items-center gap-3">
          <Loader2 className="w-5 h-5 animate-spin text-[var(--foreground-muted)]" />
          <p className="text-sm text-[var(--foreground-muted)]">
            Loading profile...
          </p>
        </div>
      ) : (
        <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6">
          <div className="space-y-3 text-sm">
            {rows.map((row) => (
              <div key={row.label} className="flex justify-between gap-4">
                <span className="text-[var(--foreground-muted)]">
                  {row.label}
                </span>
                <span
                  className={`text-[var(--foreground)] text-right ${row.mono ? "font-mono" : ""}`}
                >
                  {row.value || "N/A"}
                </span>
              </div>
            ))}
          </div>
          <p className="text-xs text-[var(--foreground-muted)] mt-4">
            Changes to name, team or role are made by an administrator.
          </p>
        </div>
      )}
    </div>
  );
}
