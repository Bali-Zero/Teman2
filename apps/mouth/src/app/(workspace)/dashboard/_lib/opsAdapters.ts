/**
 * Ops panel data adapters — WS2 slice 2 (GARUDA OS kita workspace wiring).
 *
 * Honest-data contract: every row maps a REAL backend response field; on any
 * failure the adapters degrade, never fabricate:
 *  - getSystemPulse: total fetch failure → every known service `idle` with
 *    "probe unavailable"; a service missing from a successful response →
 *    `idle` with "no probe wired"; `latencyMs` is only set when the backend
 *    actually measured one; `barPct` is never synthesized (no honest scale).
 *  - getComplianceAlerts: total fetch failure → empty list (the radar renders
 *    its defined empty element), never throws.
 *
 * Endpoints (verified in apps/backend-rag):
 *  - GET /api/admin/system-health  (routers/system_observability.py — admin
 *    only; the dashboard does not invoke this adapter for non-admin users)
 *  - GET /api/compliance/alerts    (routers/compliance_alerts.py — RBAC
 *    scopes team members to their assigned clients, same as the pipeline)
 */

import { api } from "@/lib/api";
import type { ComplianceAlert, SystemPulseService } from "@balizero/core";

// ── System Pulse ───────────────────────────────────────────

/**
 * Check keys emitted by UnifiedHealthService.run_all_checks
 * (backend/services/monitoring/unified_health_service.py). Labels use the
 * router's own documented names ("PostgreSQL (Connectivity + Latency)",
 * "API (Self-check)") — not invented.
 */
const PULSE_CHECKS = [
  { key: "Database", id: "postgres", label: "PostgreSQL" },
  { key: "Qdrant", id: "qdrant", label: "Qdrant" },
  { key: "Redis", id: "redis", label: "Redis" },
  { key: "API", id: "backend-api", label: "Backend API" },
  { key: "CRM Models", id: "crm-models", label: "CRM Models" },
  {
    key: "Collection Manager",
    id: "collection-manager",
    label: "Collection Manager",
  },
] as const;

/** Mirrors the backend HealthCheckResult dataclass (asdict). */
interface HealthCheckResultDto {
  name: string;
  status: string; // "ok" | "warning" | "error" | "skipped"
  message: string;
  latency_ms: number | null;
  metadata?: Record<string, unknown> | null;
  timestamp?: number | null;
}

interface SystemHealthDto {
  overall_status: string;
  timestamp: string;
  checks: Record<string, HealthCheckResultDto>;
  system_metrics: Record<string, unknown>;
  service_registry: unknown;
}

/** Backend check status → SystemPulse status vocabulary. */
function mapCheckStatus(status: string): SystemPulseService["status"] {
  switch (status) {
    case "ok":
      return "ok";
    case "warning":
      return "warn";
    case "error":
      return "down";
    default:
      // "skipped" and anything unrecognized — never guess health
      return "idle";
  }
}

export async function getSystemPulse(): Promise<SystemPulseService[]> {
  let dto: SystemHealthDto;
  try {
    dto = await api.get<SystemHealthDto>("/api/admin/system-health");
  } catch {
    // Total probe failure (backend down, tunnel down, 403 for non-admins):
    // every known service reports idle — the panel still renders honestly.
    return PULSE_CHECKS.map(({ id, label }) => ({
      id,
      label,
      status: "idle" as const,
      detail: "probe unavailable",
    }));
  }

  return PULSE_CHECKS.map(({ key, id, label }) => {
    const check = dto.checks?.[key];
    if (!check) {
      return {
        id,
        label,
        status: "idle" as const,
        detail: "no probe wired",
      };
    }
    return {
      id,
      label,
      status: mapCheckStatus(check.status),
      detail: check.message || undefined,
      latencyMs:
        check.latency_ms != null ? Math.round(check.latency_ms) : undefined,
    };
  });
}

// ── Compliance Radar ───────────────────────────────────────

/**
 * Row shape of the compliance_alerts table (migrations_v2/114), returned by
 * GET /api/compliance/alerts as {items, limit, offset}.
 */
interface ComplianceAlertDto {
  alert_id: string;
  client_id: number;
  category: string;
  severity: string; // DB CHECK: "info" | "warning" | "urgent" | "critical"
  status: string; // DB CHECK: "pending" | "sent" | "acknowledged" | "resolved" | "expired"
  deadline: string; // ISO date
  days_until: number;
  message_en: string | null;
  message_it: string | null;
  suggested_action: string | null;
}

interface ComplianceAlertsResponse {
  items: ComplianceAlertDto[];
  limit: number;
  offset: number;
}

/** Active = not yet closed out (dedup index uses the same status set). */
const ACTIVE_STATUSES = new Set(["pending", "sent", "acknowledged"]);

const VALID_SEVERITIES: ReadonlySet<string> = new Set([
  "critical",
  "urgent",
  "warning",
  "info",
]);

const MS_PER_DAY = 24 * 60 * 60 * 1000;

function formatTimeLeft(
  deadline: string,
  now = new Date(),
): string | undefined {
  const deadlineMs = Date.parse(`${deadline}T00:00:00Z`);
  if (Number.isNaN(deadlineMs)) return undefined;

  const todayMs = Date.UTC(
    now.getUTCFullYear(),
    now.getUTCMonth(),
    now.getUTCDate(),
  );
  const days = Math.round((deadlineMs - todayMs) / MS_PER_DAY);
  return days < 0 ? "overdue" : `${days}d`;
}

export async function getComplianceAlerts(
  limit = 6,
): Promise<ComplianceAlert[]> {
  let res: ComplianceAlertsResponse;
  try {
    res = await api.get<ComplianceAlertsResponse>(
      `/api/compliance/alerts?active_only=true&limit=${limit}`,
    );
  } catch {
    // Total failure → empty radar (defined empty element), never throws.
    return [];
  }

  return (
    (res.items ?? [])
      .filter((row) => ACTIVE_STATUSES.has(row.status))
      // Backend applies this order before LIMIT; keep it defensively stable if
      // a mock or older server returns an unsorted response.
      .sort((a, b) => a.deadline.localeCompare(b.deadline))
      .slice(0, limit)
      .map((row) => ({
        id: row.alert_id,
        title: row.message_en ?? row.category.replace(/_/g, " "),
        detail: `CLI-${row.client_id} · ${row.category.replace(/_/g, " ")}`,
        severity: (VALID_SEVERITIES.has(row.severity)
          ? row.severity
          : "info") as ComplianceAlert["severity"],
        // days_until is a creation-time snapshot. Derive the live countdown
        // from the canonical deadline so the UI cannot freeze at a stale value.
        timeLeft: formatTimeLeft(row.deadline),
      }))
  );
}
