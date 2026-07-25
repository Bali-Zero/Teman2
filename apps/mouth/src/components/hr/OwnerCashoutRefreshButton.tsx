"use client";

import React, { useState } from "react";
import { RefreshCw } from "lucide-react";
import { toast } from "sonner";
import * as api from "@/lib/api/hr/owner-cashout";

interface Props {
  onRefreshed?: () => void;
}

export function OwnerCashoutRefreshButton({ onRefreshed }: Props) {
  const [busy, setBusy] = useState(false);

  const handleClick = async () => {
    setBusy(true);
    try {
      await api.triggerSync();
      toast.success("Sync started. Refresh in ~10s.");
      setTimeout(() => {
        onRefreshed?.();
        setBusy(false);
      }, 10000);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Sync failed");
      setBusy(false);
    }
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={busy}
      className="inline-flex items-center gap-2 px-3 py-2 bg-[var(--bz-surface)] hover:bg-[var(--bz-glass-rim)] text-[var(--bz-text-1)] rounded-lg border border-[var(--bz-border)] text-sm disabled:opacity-50"
    >
      <RefreshCw size={14} className={busy ? "animate-spin" : ""} />
      {busy ? "Syncing…" : "Refresh"}
    </button>
  );
}
