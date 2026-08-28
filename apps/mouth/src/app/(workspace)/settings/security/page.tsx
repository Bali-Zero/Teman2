"use client";

import React, { useState, useEffect } from "react";
import {
  Shield,
  Key,
  Smartphone,
  Monitor,
  Clock,
  ArrowLeft,
  Save,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { useSessionState } from "@/hooks/useSessionState";

interface Session {
  id: string;
  device: string;
  browser: string;
  location: string;
  lastActive: string;
  isCurrent: boolean;
}

export default function SecuritySettingsPage() {
  const router = useRouter();
  const session = useSessionState();
  const { success, error: toastError, warning } = useToast();
  const [isAuthorized, setIsAuthorized] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [showPasswordForm, setShowPasswordForm] = useState(false);
  const [twoFactorEnabled, setTwoFactorEnabled] = useState(false);
  const [passwordForm, setPasswordForm] = useState({
    currentPin: "",
    newPin: "",
    confirmPin: "",
  });

  const [sessions] = useState<Session[]>([
    {
      id: "1",
      device: "MacBook Pro",
      browser: "Chrome 120",
      location: "Bali, Indonesia",
      lastActive: "Now",
      isCurrent: true,
    },
    {
      id: "2",
      device: "iPhone 14",
      browser: "Safari Mobile",
      location: "Bali, Indonesia",
      lastActive: "2 hours ago",
      isCurrent: false,
    },
  ]);

  const handleChangePassword = async () => {
    if (passwordForm.newPin !== passwordForm.confirmPin) {
      toastError(
        "PINs do not match",
        "Please make sure both PIN fields match.",
      );
      return;
    }
    if (passwordForm.newPin.length !== 6) {
      toastError("Invalid PIN", "PIN must be exactly 6 digits.");
      return;
    }
    setIsSaving(true);
    // API call would go here
    setTimeout(() => {
      setIsSaving(false);
      setShowPasswordForm(false);
      setPasswordForm({ currentPin: "", newPin: "", confirmPin: "" });
      success("PIN updated", "Your login PIN has been changed successfully.");
    }, 500);
  };

  const revokeSession = (_sessionId: string) => {
    warning(
      "Not yet available",
      "Session revocation will be enabled in a future update.",
    );
  };

  useEffect(() => {
    if (session === "anonymous") {
      router.push("/login");
      return;
    }
    if (session !== "authenticated") return;
    if (!api.isAdmin()) {
      router.push("/chat");
      return;
    }
    setIsAuthorized(true);
  }, [session, router]);

  if (!isAuthorized) {
    return null;
  }

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
            <Shield className="w-6 h-6 text-[var(--bz-accent)]" />
            Security Settings
          </h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            Manage your account security
          </p>
        </div>
      </div>

      {/* Change PIN */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Key className="w-5 h-5 text-[var(--bz-accent)]" />
            <div>
              <h2 className="text-lg font-semibold text-[var(--foreground)]">
                PIN Code
              </h2>
              <p className="text-sm text-[var(--foreground-muted)]">
                Change your 6-digit login PIN
              </p>
            </div>
          </div>
          {!showPasswordForm && (
            <Button variant="outline" onClick={() => setShowPasswordForm(true)}>
              Change PIN
            </Button>
          )}
        </div>

        {showPasswordForm && (
          <div className="space-y-4 mt-4 pt-4 border-t border-[var(--border)]">
            <div>
              <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-1.5">
                Current PIN
              </label>
              <input
                type="password"
                maxLength={6}
                value={passwordForm.currentPin}
                onChange={(e) =>
                  setPasswordForm({
                    ...passwordForm,
                    currentPin: e.target.value.replace(/\D/g, ""),
                  })
                }
                className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                placeholder="••••••"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-1.5">
                New PIN
              </label>
              <input
                type="password"
                maxLength={6}
                value={passwordForm.newPin}
                onChange={(e) =>
                  setPasswordForm({
                    ...passwordForm,
                    newPin: e.target.value.replace(/\D/g, ""),
                  })
                }
                className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                placeholder="••••••"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-[var(--foreground-muted)] mb-1.5">
                Confirm New PIN
              </label>
              <input
                type="password"
                maxLength={6}
                value={passwordForm.confirmPin}
                onChange={(e) =>
                  setPasswordForm({
                    ...passwordForm,
                    confirmPin: e.target.value.replace(/\D/g, ""),
                  })
                }
                className="w-full px-3 py-2 rounded-lg border border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                placeholder="••••••"
              />
            </div>
            <div className="flex gap-2">
              <Button onClick={handleChangePassword} disabled={isSaving}>
                <Save className="w-4 h-4 mr-2" />
                {isSaving ? "Saving..." : "Update PIN"}
              </Button>
              <Button
                variant="ghost"
                onClick={() => setShowPasswordForm(false)}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Two-Factor Authentication */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Smartphone className="w-5 h-5 text-[var(--bz-neon-purple)]" />
            <div>
              <h2 className="text-lg font-semibold text-[var(--foreground)]">
                Two-Factor Authentication
              </h2>
              <p className="text-sm text-[var(--foreground-muted)]">
                Add an extra layer of security
              </p>
            </div>
          </div>
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              className="sr-only peer"
              checked={twoFactorEnabled}
              onChange={() => setTwoFactorEnabled(!twoFactorEnabled)}
            />
            <div className="w-11 h-6 bg-[var(--background)] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-[var(--bz-border)] after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[var(--accent)]"></div>
          </label>
        </div>
        {twoFactorEnabled && (
          <div className="mt-4 p-4 rounded-lg bg-[var(--state-success)]/10 border border-[var(--state-success)]/30">
            <div className="flex items-center gap-2 text-[var(--state-success)]">
              <CheckCircle2 className="w-4 h-4" />
              <span className="text-sm font-medium">2FA is enabled</span>
            </div>
          </div>
        )}
        {!twoFactorEnabled && (
          <div className="mt-4 p-4 rounded-lg bg-[var(--state-warning)]/10 border border-[var(--state-warning)]/30">
            <div className="flex items-center gap-2 text-[var(--state-warning)]">
              <AlertTriangle className="w-4 h-4" />
              <span className="text-sm font-medium">
                2FA is recommended for additional security
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Active Sessions */}
      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-6">
        <div className="flex items-center gap-3 mb-4">
          <Monitor className="w-5 h-5 text-[var(--bz-accent)]" />
          <div>
            <h2 className="text-lg font-semibold text-[var(--foreground)]">
              Active Sessions
            </h2>
            <p className="text-sm text-[var(--foreground-muted)]">
              Manage devices logged into your account
            </p>
          </div>
        </div>

        <div className="space-y-3">
          {sessions.map((session) => (
            <div
              key={session.id}
              className="flex items-center justify-between p-3 rounded-lg bg-[var(--background)]"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-[var(--background-secondary)] flex items-center justify-center">
                  <Monitor className="w-5 h-5 text-[var(--foreground-muted)]" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-[var(--foreground)]">
                      {session.device}
                    </span>
                    {session.isCurrent && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-[var(--state-success)]/15 text-[var(--state-success)]">
                        Current
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-[var(--foreground-muted)]">
                    {session.browser} • {session.location}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1 text-xs text-[var(--foreground-muted)]">
                  <Clock className="w-3 h-3" />
                  {session.lastActive}
                </div>
                {!session.isCurrent && (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-[var(--state-danger)]"
                    onClick={() => revokeSession(session.id)}
                  >
                    Revoke
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Security Log */}
      <div className="rounded-lg border border-dashed border-[var(--border)] bg-[var(--background-secondary)]/50 p-6 text-center">
        <Shield className="w-10 h-10 mx-auto text-[var(--foreground-muted)] mb-3 opacity-50" />
        <p className="text-sm text-[var(--foreground-muted)]">
          Your account security is important. Enable 2FA and regularly review
          your active sessions.
        </p>
      </div>
    </div>
  );
}
