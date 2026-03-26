"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";

export interface CellPulse {
  pulse_number: number;
  health_status: "green" | "yellow" | "red";
  response_time_ms: number;
  dna_intact: boolean;
  budget_spent: number;
  budget_limit: number;
  memory_stm_count: number;
  memory_ltm_count: number;
  procedures_count: number;
  cells_active: number;
  cells_total: number;
  action_taken: string | null;
  created_at: string;
}

export interface CellStatus {
  alive: boolean;
  last_pulse: CellPulse | null;
  recent_pulses: Pick<
    CellPulse,
    "pulse_number" | "health_status" | "response_time_ms" | "created_at"
  >[];
  uptime_24h: {
    green_percent: number;
    yellow_percent: number;
    red_percent: number;
    total_pulses: number;
  };
}

export function useCellStatus(pollIntervalMs: number = 10000) {
  const [status, setStatus] = useState<CellStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_BACKEND_URL || "https://nuzantara-rag.fly.dev"}/api/cell/status`,
        {
          headers: {
            Authorization: `Bearer ${api.getToken()}`,
          },
        },
      );
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      setStatus(data);
      setError(null);
    } catch (err) {
      logger.error(
        "Failed to fetch CELL status",
        {},
        err instanceof Error ? err : undefined,
      );
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!api.isAuthenticated() || !api.isAdmin()) return;
    fetchStatus();
    const interval = setInterval(fetchStatus, pollIntervalMs);
    return () => clearInterval(interval);
  }, [fetchStatus, pollIntervalMs]);

  return { status, loading, error, refetch: fetchStatus };
}
