"use client";

/**
 * Notifications desk — concept-K v2 "TEPAT FORTE"
 * (R19-KITA-20260914/fusion/concept.md), SAETTA-R19K window K2c.
 *
 * A hairline ledger of automated email alerts: a Masthead, a DeskStrip
 * carrying the count/filters/search, and rows with a delivery STATUS (word +
 * outlined square pill) and a derived SEVERITY (word + pip). Neither is
 * ownership — copper never appears here, because no row's next actor is
 * derivable from an automated alert. `--state-danger` and `--state-warning`
 * stay on this page on purpose: `token-drain.residuals.guard.test.ts` pins
 * this file to `--state-success` / `--state-warning` / `--state-danger` as
 * the proof of the WS2 token drain, and `desk-no-red.guard.test.ts` exempts
 * this page BY NAME for exactly that reason. On kita `--state-danger`
 * resolves to copper, so it is not red.
 *
 * STATUS uses a page-local square pill (not the shared `StatePill`, which is
 * `rounded-full` and only carries the four ownership tones — it has no
 * `--state-warning`/`--state-danger` tone to give). SEVERITY is a second,
 * independent word-plus-pip mark derived client-side from `alert_type`: the
 * only shape the backend sends is the type string, so the four severities
 * (critical/high/medium/low) are read out of it here rather than adding a
 * field the backend does not have.
 */

import React, { useState, useEffect } from "react";
import { Loader2, Pause, RefreshCw, Search } from "lucide-react";
import { api } from "@/lib/api";
import { logger } from "@/lib/logger";
import { useToast } from "@/components/ui/toast";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
  CellStack,
  DeskStrip,
  EmptyState,
  EYEBROW,
  FOCUS,
  HairlineBody,
  HairlineGrid,
  HairlineHead,
  HairlineRow,
  Masthead,
  Notice,
  NumberedList,
  SERIF,
  SERIF_SECTION,
  StatePill,
  TABULAR,
  type NumberedItem,
} from "@/components/workspace/r19";

interface NotificationStats {
  total_alerts_24h: number;
  total_alerts_7d: number;
  total_alerts_30d: number;
  pending_count: number;
  sent_count_24h: number;
  failed_count_24h: number;
  alerts_by_type: Record<string, number>;
  alerts_by_status: Record<string, number>;
  top_clients: Array<{
    id: number;
    name: string;
    email: string;
    alert_count: number;
  }>;
}

interface Alert {
  id: number;
  client_id: number;
  client_name: string;
  client_email: string;
  alert_type: string;
  status: string;
  email_subject: string;
  created_at: string;
  sent_at: string | null;
  error_message: string | null;
}

// ── severity: word + pip, derived from `alert_type` ────────────────────────
// critical = FILLED copper pip, high = HOLLOW copper pip, medium = warning,
// low = muted. The word is always present; the pip alone never carries it.
// Copper is never a fill except this sanctioned critical pip.
type Severity = "critical" | "high" | "medium" | "low";

function severityOf(alertType: string): Severity {
  if (alertType.includes("critical")) return "critical";
  if (alertType.includes("warning")) return "high";
  if (alertType === "birthday") return "low";
  return "medium";
}

const SEVERITY_LABEL: Record<Severity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
};

const SEVERITY_TONE: Record<Severity, string> = {
  critical: "text-[var(--bz-copper-text)]",
  high: "text-[var(--bz-copper-text)]",
  medium: "text-[var(--state-warning)]",
  low: "text-[var(--tx-secondary)]",
};

function SeverityMark({ severity }: { severity: Severity }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-[10px] font-[650] uppercase tracking-[0.1em]",
        SEVERITY_TONE[severity],
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "h-1.5 w-1.5 shrink-0 rounded-full border border-current",
          severity === "critical" && "bg-current",
        )}
      />
      {SEVERITY_LABEL[severity]}
    </span>
  );
}

// ── delivery status: outlined SQUARE pill ───────────────────────────────────
// The concept's `.state{border-radius:2px}` square, not the shared
// `StatePill`'s `rounded-full` — and the one place this file is allowed (and
// required, by the sibling guard) to read the danger token by name.
const STATUS_LABEL: Record<string, string> = {
  sent: "Sent",
  pending: "Pending",
  failed: "Failed",
};

const STATUS_TONE: Record<string, string> = {
  sent: "text-[var(--state-success)] border-[var(--state-success)]",
  pending: "text-[var(--state-warning)] border-[var(--state-warning)]",
  // `failed` is a TERMINAL failure, not an active alarm: law #3 binds it —
  // muted, never danger, plus the word "Failed" the pill already carries.
  failed: "text-[var(--tx-secondary)] border-[var(--line-control)]",
};

function StatusPill({ status }: { status: string }) {
  const label = STATUS_LABEL[status] ?? status;
  const tone =
    STATUS_TONE[status] ??
    "text-[var(--tx-secondary)] border-[var(--line-control)]";
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded-[2px] border bg-transparent px-2.5",
        "text-[10px] font-[650] uppercase tracking-[0.12em]",
        tone,
      )}
    >
      <span
        aria-hidden="true"
        className="h-1.5 w-1.5 shrink-0 rounded-full bg-current"
      />
      {label}
    </span>
  );
}

function humanizeType(type: string): string {
  return type.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const STATUS_FILTERS: Array<{ value: string; label: string }> = [
  { value: "", label: "All" },
  { value: "pending", label: "Pending" },
  { value: "sent", label: "Sent" },
  { value: "failed", label: "Failed" },
];

const TYPE_FILTERS: Array<{ value: string; label: string }> = [
  { value: "", label: "All types" },
  { value: "passport_warning", label: "Passport warning" },
  { value: "passport_critical", label: "Passport critical" },
  { value: "visa_critical", label: "Visa critical" },
  { value: "birthday", label: "Birthday" },
];

// ── system status notice ────────────────────────────────────────────────────
const SYSTEM_STATUS_COPY: Record<
  string,
  { tone: "ok" | "you" | "wait" | "warn"; sentence: string }
> = {
  healthy: { tone: "ok", sentence: "All systems operational." },
  // A fleet-wide health status is not derived from viewer + record, so it is
  // never copper — "you" would claim the signed-in viewer is the next actor,
  // which a system-wide condition can't demonstrate. Warning: urgency, not
  // ownership.
  degraded: {
    tone: "warn",
    sentence: "Multiple failures detected — attention required.",
  },
  pending: { tone: "wait", sentence: "Pending alerts backlog — processing." },
};

/**
 * The shared `Notice` has three tones — you / ok / wait — and no warning.
 * `components/workspace/r19/**` is another window's perimeter while it is being
 * upgraded to v2, so this page does NOT add a tone there. It wraps the
 * primitive and overrides its boundary and text through `className`, which
 * tailwind-merge resolves in favour of the later class. No class string is
 * copied out of the module; when v2 ships a warning tone this wrapper becomes a
 * one-line adapter and is deleted, not kept beside it.
 */
function DeskNotice({
  tone,
  role,
  className,
  children,
}: {
  tone: "you" | "ok" | "wait" | "warn";
  role?: "alert" | "status";
  className?: string;
  children: React.ReactNode;
}) {
  if (tone === "warn") {
    return (
      <Notice
        tone="wait"
        role={role}
        className={cn(
          "border-[var(--state-warning)] text-[var(--state-warning)]",
          className,
        )}
      >
        {children}
      </Notice>
    );
  }
  return (
    <Notice tone={tone} role={role} className={className}>
      {children}
    </Notice>
  );
}

function systemStatusCopy(status: string) {
  return (
    SYSTEM_STATUS_COPY[status] ?? {
      tone: "wait" as const,
      sentence: "Status unknown.",
    }
  );
}

// ── stat band ────────────────────────────────────────────────────────────
function StatCell({
  label,
  value,
  tone = "ink",
}: {
  label: string;
  value: number;
  tone?: "ink" | "warn" | "you" | "ok" | "muted";
}) {
  const toneClass =
    tone === "warn"
      ? "text-[var(--state-warning)]"
      : tone === "you"
        ? "text-[var(--bz-copper-text)]"
        : tone === "ok"
          ? "text-[var(--state-success)]"
          : tone === "muted"
            ? "text-[var(--tx-secondary)]"
            : "text-[var(--tx-pure)]";
  return (
    <div className="min-h-[72px] min-w-0 border-[var(--bz-border)] px-4 py-3 [&:not(:last-child)]:border-r">
      <span className={EYEBROW}>{label}</span>
      <span
        className={cn(
          "my-1 block text-[22px] leading-none tracking-[-0.02em]",
          toneClass,
        )}
        style={{ ...SERIF, ...TABULAR }}
      >
        {value}
      </span>
    </div>
  );
}

export default function NotificationsDashboardPage() {
  const { success, error } = useToast();
  const [isLoading, setIsLoading] = useState(true);
  const [stats, setStats] = useState<NotificationStats | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [systemStatus, setSystemStatus] = useState<string>("unknown");
  const [filterStatus, setFilterStatus] = useState<string>("");
  const [filterType, setFilterType] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedAlert, setExpandedAlert] = useState<number | null>(null);

  const loadDashboard = async () => {
    try {
      setIsLoading(true);
      const data = await api.crm.request<{
        stats: typeof stats;
        recent_alerts: typeof alerts;
        system_status: typeof systemStatus;
      }>("/api/admin/notifications/dashboard");
      setStats(data.stats);
      setAlerts(data.recent_alerts);
      setSystemStatus(data.system_status);
    } catch (err) {
      error("Failed to load dashboard", "Please try again");
      logger.error("Failed to load notifications dashboard", {}, err as Error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
    const interval = setInterval(loadDashboard, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleRetryFailed = async () => {
    try {
      const result = await api.crm.request("/api/admin/notifications/retry", {
        method: "POST",
        body: JSON.stringify({}),
      });
      success("Retry completed", (result as { message: string }).message);
      loadDashboard();
    } catch (err) {
      error("Retry failed", "Please try again");
    }
  };

  const handlePauseClient = (clientId: number) => {
    toast("Pause notifications for this client for 24 hours?", {
      action: {
        label: "Pause",
        onClick: async () => {
          try {
            await api.crm.request(
              `/api/admin/notifications/pause-client?client_id=${clientId}`,
              {
                method: "POST",
              },
            );
            success("Client paused", "Notifications paused for 24 hours");
            loadDashboard();
          } catch (err) {
            error("Failed to pause client", "Please try again");
          }
        },
      },
      cancel: { label: "Cancel", onClick: () => toast.dismiss() },
    });
  };

  const filteredAlerts = alerts.filter((alert) => {
    if (filterStatus && alert.status !== filterStatus) return false;
    if (filterType && alert.alert_type !== filterType) return false;
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      return (
        alert.client_name.toLowerCase().includes(query) ||
        alert.client_email.toLowerCase().includes(query) ||
        alert.email_subject.toLowerCase().includes(query)
      );
    }
    return true;
  });

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2
          className="h-8 w-8 animate-spin text-[var(--tx-secondary)]"
          aria-hidden="true"
        />
      </div>
    );
  }

  const filtersActive = Boolean(searchQuery || filterStatus || filterType);
  const clearFilters = () => {
    setSearchQuery("");
    setFilterStatus("");
    setFilterType("");
  };

  const statusCopy = systemStatusCopy(systemStatus);

  const topClientItems: NumberedItem[] = (stats?.top_clients ?? [])
    .slice(0, 5)
    .map((client) => ({
      id: String(client.id),
      title: client.name,
      detail: client.email,
      tone: "wait",
      right: (
        <div className="flex items-center gap-3">
          <span
            className="text-[11px] text-[var(--tx-secondary)]"
            style={TABULAR}
          >
            {client.alert_count} alerts
          </span>
          <button
            type="button"
            aria-label={`Pause notifications for ${client.name}`}
            onClick={() => handlePauseClient(client.id)}
            className={cn(
              "grid h-8 w-8 place-items-center border border-[var(--line-control)] text-[var(--tx-secondary)] hover:text-[var(--tx-pure)]",
              FOCUS,
            )}
          >
            <Pause className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        </div>
      ),
    }));

  return (
    <div className="p-4 md:p-6">
      <Masthead
        eyebrow="Ops"
        title="Notifications"
        subtitle="Monitor automated email alerts and delivery health."
        className="mb-5"
        right={
          <>
            <button
              type="button"
              onClick={loadDashboard}
              className={cn(
                "inline-flex min-h-11 items-center gap-2 border border-[var(--line-control)] bg-transparent px-3.5 text-[12px] font-[650] text-[var(--tx-pure)] hover:bg-[var(--bz-card-hover)]",
                FOCUS,
              )}
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Refresh
            </button>
            {stats?.failed_count_24h ? (
              <button
                type="button"
                onClick={handleRetryFailed}
                className={cn(
                  "inline-flex min-h-11 items-center gap-2 border border-[var(--bz-copper)] bg-transparent px-3.5 text-[12px] font-[650] text-[var(--bz-copper-text)] hover:bg-[var(--bz-card-hover)]",
                  FOCUS,
                )}
              >
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
                Retry failed ({stats.failed_count_24h})
              </button>
            ) : null}
          </>
        }
      />

      <DeskNotice
        tone={statusCopy.tone}
        role={
          statusCopy.tone === "you" || statusCopy.tone === "warn"
            ? "alert"
            : "status"
        }
        className="mb-4"
      >
        <strong className="font-[650]">
          System status:{" "}
          {systemStatus.charAt(0).toUpperCase() + systemStatus.slice(1)}.
        </strong>{" "}
        {statusCopy.sentence}
      </DeskNotice>

      {stats && (
        <div className="mb-4 grid grid-cols-2 border-y border-[var(--bz-border)] md:grid-cols-4">
          <StatCell label="24h alerts" value={stats.total_alerts_24h} />
          <StatCell label="Pending" value={stats.pending_count} tone="warn" />
          <StatCell label="Sent · 24h" value={stats.sent_count_24h} tone="ok" />
          <StatCell
            label="Failed · 24h"
            value={stats.failed_count_24h}
            // A raw fleet-wide failure count is not viewer+record derived,
            // so it is never copper — warning: urgency, not ownership.
            tone={stats.failed_count_24h > 0 ? "warn" : "muted"}
          />
        </div>
      )}

      <DeskStrip
        count={filteredAlerts.length}
        countLabel={`${filteredAlerts.length} alerts`}
        filters={STATUS_FILTERS.map((f) => (
          <StatePill
            key={f.value || "all"}
            tone="wait"
            label={f.label}
            pressed={filterStatus === f.value}
            onClick={() => setFilterStatus(f.value)}
          />
        ))}
        right={
          <>
            <div className="relative">
              <Search
                className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--tx-secondary)]"
                aria-hidden="true"
              />
              <input
                type="search"
                aria-label="Search notifications"
                placeholder="Search clients…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className={cn(
                  "h-9 w-48 border border-[var(--line-control)] bg-transparent pl-8 pr-2 text-[12px] text-[var(--tx-pure)] placeholder:text-[var(--tx-secondary)]",
                  "focus:border-[var(--bz-copper)] focus:outline-none",
                )}
              />
            </div>
            <select
              aria-label="Filter by type"
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className={cn(
                "h-9 border border-[var(--line-control)] bg-transparent px-2 text-[12px] text-[var(--tx-pure)]",
                "focus:border-[var(--bz-copper)] focus:outline-none",
              )}
            >
              {TYPE_FILTERS.map((t) => (
                <option key={t.value || "all"} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </>
        }
      />

      <HairlineGrid cols="minmax(170px,1.8fr) minmax(130px,1fr) 96px minmax(160px,1.3fr) 88px 44px">
        <HairlineHead>
          <span>Client</span>
          <span>Type</span>
          <span>Status</span>
          <span>Subject</span>
          <span>Time</span>
          <span className="sr-only">Actions</span>
        </HairlineHead>
        <HairlineBody>
          {filteredAlerts.length === 0 ? (
            <EmptyState
              action={
                filtersActive ? (
                  <button
                    type="button"
                    onClick={clearFilters}
                    className="text-[12px] font-[650] text-[var(--bz-copper-text)] underline underline-offset-2"
                  >
                    Clear filters
                  </button>
                ) : undefined
              }
            >
              {filtersActive
                ? "No notifications match your filters."
                : "No notifications yet."}
            </EmptyState>
          ) : (
            filteredAlerts.map((alert) => {
              const isOpen = expandedAlert === alert.id;
              const ageDays = Math.floor(
                (Date.now() - new Date(alert.created_at).getTime()) / 86400000,
              );
              const ageTag =
                ageDays < 1
                  ? ""
                  : ageDays >= 365
                    ? ` · ${Math.floor(ageDays / 365)}y ago`
                    : ageDays >= 30
                      ? ` · ${Math.floor(ageDays / 30)}mo ago`
                      : ageDays >= 7
                        ? ` · ${Math.floor(ageDays / 7)}w ago`
                        : ` · ${ageDays}d ago`;
              const dateLabel = new Date(alert.created_at).toLocaleDateString(
                "en-US",
                { month: "short", day: "numeric", year: "numeric" },
              );

              return (
                <React.Fragment key={alert.id}>
                  <HairlineRow
                    role="button"
                    tabIndex={0}
                    aria-expanded={isOpen}
                    aria-label={`Notification for ${alert.client_name}`}
                    onClick={() => setExpandedAlert(isOpen ? null : alert.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setExpandedAlert(isOpen ? null : alert.id);
                      }
                    }}
                    className={cn("cursor-pointer", FOCUS)}
                    touchAction={
                      <button
                        type="button"
                        aria-label={`Pause notifications for ${alert.client_name}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          handlePauseClient(alert.client_id);
                        }}
                        // The row is keyboard-activatable and its own
                        // onKeyDown calls preventDefault() on Enter/Space —
                        // without stopping propagation here that bubbles up
                        // and toggles the row instead of activating Pause.
                        onKeyDown={(e) => e.stopPropagation()}
                        className={cn(
                          "grid h-11 w-11 place-items-center",
                          FOCUS,
                        )}
                      >
                        <Pause className="h-4 w-4" aria-hidden="true" />
                      </button>
                    }
                    actions={
                      <button
                        type="button"
                        aria-label={`Pause notifications for ${alert.client_name}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          handlePauseClient(alert.client_id);
                        }}
                        // Same cure as the touchAction Pause button above.
                        onKeyDown={(e) => e.stopPropagation()}
                        className={cn(
                          "grid h-8 w-8 place-items-center border border-[var(--line-control)] text-[var(--tx-secondary)] hover:text-[var(--tx-pure)]",
                          FOCUS,
                        )}
                      >
                        <Pause className="h-3.5 w-3.5" aria-hidden="true" />
                      </button>
                    }
                  >
                    <CellStack
                      primary={alert.client_name}
                      secondary={alert.client_email}
                    />
                    <CellStack
                      primary={humanizeType(alert.alert_type)}
                      secondary={
                        <SeverityMark severity={severityOf(alert.alert_type)} />
                      }
                    />
                    <StatusPill status={alert.status} />
                    <span
                      className="truncate text-[12px] text-[var(--tx-pure)]"
                      title={alert.email_subject}
                    >
                      {alert.email_subject}
                    </span>
                    <span
                      className="truncate text-[11px] text-[var(--tx-secondary)]"
                      style={TABULAR}
                    >
                      {dateLabel}
                      {ageTag}
                    </span>
                  </HairlineRow>
                  {isOpen && (
                    <div className="border-b border-[var(--bz-border)] bg-[var(--bz-card)] px-2.5 py-3">
                      <p className="text-[11px] font-[650] uppercase tracking-[0.1em] text-[var(--tx-secondary)]">
                        Email subject
                      </p>
                      <p className="mt-1 text-[13px] text-[var(--tx-pure)]">
                        {alert.email_subject}
                      </p>
                      {alert.error_message && (
                        <>
                          <p className="mt-2 text-[11px] font-[650] uppercase tracking-[0.1em] text-[var(--state-danger)]">
                            Error
                          </p>
                          <p className="mt-1 text-[13px] text-[var(--state-danger)]">
                            {alert.error_message}
                          </p>
                        </>
                      )}
                      {alert.sent_at && (
                        <p
                          className="mt-2 text-[11px] text-[var(--tx-secondary)]"
                          style={TABULAR}
                        >
                          Sent{" "}
                          {new Date(alert.sent_at).toLocaleDateString("en-US", {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          })}{" "}
                          {new Date(alert.sent_at).toLocaleTimeString("en-US", {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </p>
                      )}
                    </div>
                  )}
                </React.Fragment>
              );
            })
          )}
        </HairlineBody>
      </HairlineGrid>

      {topClientItems.length > 0 && (
        <section className="mt-6">
          <h2
            className="mb-2 text-[19px] leading-[1.2] tracking-[-0.02em] text-[var(--tx-pure)]"
            style={SERIF_SECTION}
          >
            Top clients
          </h2>
          <p className="mb-2 text-[11px] text-[var(--tx-secondary)]">
            By alert volume, last 30 days.
          </p>
          <NumberedList items={topClientItems} />
        </section>
      )}
    </div>
  );
}
