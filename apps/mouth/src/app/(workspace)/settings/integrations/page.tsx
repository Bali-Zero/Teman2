"use client";

import React, { useState, useEffect } from "react";
import {
  Plug,
  Cloud,
  ArrowLeft,
  CheckCircle2,
  XCircle,
  Loader2,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";

type DriveStatus = "checking" | "connected" | "disconnected" | "error";

const GOOGLE_BLUE = "#4285F4"; // token-lint-ok: third-party brand identity color (Google), not theme chrome

// Google Drive is the one integration with a real backend behind it
// (/api/integrations/google-drive/*). The other cards this page used to show
// were constants flipped in local state, so they are gone.
export default function IntegrationsPage() {
  const router = useRouter();
  const [status, setStatus] = useState<DriveStatus>("checking");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const check = async () => {
      try {
        const s = await api.drive.getStatus();
        setStatus(s.connected ? "connected" : "disconnected");
      } catch (error) {
        logger.error("Failed to check Google Drive status", {}, error as Error);
        setStatus("error");
      }
    };

    // OAuth callback lands here with ?success=…_drive_connected.
    const params = new URLSearchParams(window.location.search);
    const success = params.get("success");
    if (
      success === "google_drive_connected" ||
      success === "system_drive_connected"
    ) {
      window.history.replaceState({}, document.title, "/settings/integrations");
    }
    check();
  }, []);

  const connect = async () => {
    setBusy(true);
    try {
      const { auth_url } = await api.drive.getAuthUrl();
      window.location.href = auth_url;
    } catch (error) {
      logger.error("Failed to get auth URL", {}, error as Error);
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true);
    try {
      await api.drive.disconnect();
      setStatus("disconnected");
    } catch (error) {
      logger.error("Failed to disconnect Google Drive", {}, error as Error);
    } finally {
      setBusy(false);
    }
  };

  const badge =
    status === "connected" ? (
      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-[var(--state-success)]/15 text-[var(--state-success)]">
        <CheckCircle2 className="w-3 h-3" />
        Connected
      </span>
    ) : status === "error" ? (
      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-[var(--state-danger)]/15 text-[var(--state-danger)]">
        <XCircle className="w-3 h-3" />
        Error
      </span>
    ) : status === "checking" ? (
      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-[var(--background)] text-[var(--foreground-muted)]">
        <Loader2 className="w-3 h-3 animate-spin" />
        Checking
      </span>
    ) : (
      <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-[var(--background)] text-[var(--foreground-muted)]">
        <XCircle className="w-3 h-3" />
        Disconnected
      </span>
    );

  return (
    <div className="space-y-6 max-w-2xl">
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
            <Plug className="w-6 h-6 text-[var(--bz-accent)]" />
            Integrations
          </h1>
          <p className="text-sm text-[var(--foreground-muted)]">
            External services connected to the workspace
          </p>
        </div>
      </div>

      <div className="rounded-lg border border-[var(--border)] bg-[var(--background-elevated)] p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div
              className="w-12 h-12 rounded-lg flex items-center justify-center"
              style={{ backgroundColor: `${GOOGLE_BLUE}20` }}
            >
              <Cloud className="w-6 h-6" style={{ color: GOOGLE_BLUE }} />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-medium text-[var(--foreground)]">
                  Google Drive
                </h3>
                {badge}
              </div>
              <p className="text-sm text-[var(--foreground-muted)]">
                Store and access client documents from Google Drive
              </p>
            </div>
          </div>
          <Button
            variant={status === "connected" ? "outline" : "default"}
            size="sm"
            onClick={status === "connected" ? disconnect : connect}
            disabled={busy || status === "checking"}
          >
            {busy ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                Working…
              </>
            ) : status === "connected" ? (
              "Disconnect"
            ) : (
              "Connect"
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
