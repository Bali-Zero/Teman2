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
  error_message: string | null;
  created_at: string;
}

export interface CellAlert {
  id: number;
  level: "info" | "warn" | "critical";
  action: string;
  message: string;
  health_status: string;
  pulse_number: number;
  created_at: string;
}

export interface CellStatus {
  alive: boolean;
  last_pulse: CellPulse | null;
  recent_pulses: Pick<
    CellPulse,
    | "pulse_number"
    | "health_status"
    | "response_time_ms"
    | "action_taken"
    | "error_message"
    | "created_at"
  >[];
  uptime_24h: {
    green_percent: number;
    yellow_percent: number;
    red_percent: number;
    total_pulses: number;
  };
  alerts: CellAlert[];
}

const BACKEND =
  process.env.NEXT_PUBLIC_BACKEND_URL || "https://nuzantara-rag.fly.dev";

export function useCellStatus(pollIntervalMs: number = 10000) {
  const [status, setStatus] = useState<CellStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const headers = { Authorization: `Bearer ${api.getToken()}` };

      const [statusRes, alertsRes] = await Promise.all([
        fetch(`${BACKEND}/api/cell/status`, { headers }),
        fetch(`${BACKEND}/api/cell/alerts?limit=20`, { headers }),
      ]);

      if (!statusRes.ok) throw new Error(`HTTP ${statusRes.status}`);

      const statusData = await statusRes.json();
      const alertsData = alertsRes.ok ? await alertsRes.json() : { alerts: [] };

      setStatus({ ...statusData, alerts: alertsData.alerts ?? [] });
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
