"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { ComplianceAlertItem, GateStatus } from "@/lib/api";
import { useToast } from "@/components/ui/toast";
import { logger } from "@/lib/logger";

/**
 * INTAKE Login Gate screen — mandatory pre-workspace clearance.
 *
 * Rendered by the workspace layout INSTEAD of the workspace when
 * `GET /api/intake/gate/status` reports `blocked: true`. Single scrolling
 * screen, three sections in fixed order Late → Documents → Deadlines.
 *
 * Spec: research/operations/2026-06-06-intake-login-gate-spec.md §3, §5, §11.
 * Binding fixes folded in: F6 (admin override), F8 (high-volume affordance).
 *
 * NOTE on clearing paths: Late note and Deadlines are cleared INLINE on this
 * screen (late-reason form; per-alert Acknowledge buttons). Documents deep-
 * links to /review — the ONE workspace route the layout leaves reachable
 * while blocked. Anything else would loop back into this wall (the original
 * /process and /clients deep-link bugs).
 */

interface GateScreenProps {
  status: GateStatus;
  userEmail: string;
  isAdmin: boolean;
  /** Re-fetch gate status (count probe) and update the layout. */
  onRefresh: () => Promise<void>;
  /** Bypass the gate and reveal the workspace (admin override / all-clear). */
  onEnter: () => void;
}

/** Threshold above which the gate surfaces a "request help" affordance (F8). */
const HIGH_VOLUME_THRESHOLD = 15;

/**
 * Mirror of the backend gate horizon (gate_evaluator.DEADLINE_HORIZON_DAYS):
 * only alerts with deadline <= today + N days block the gate, so only those
 * are listed for inline acknowledge.
 */
const DEADLINE_HORIZON_DAYS = 7;

/**
 * Inline clearable list for the Deadlines section. Fetches the user's
 * pending/sent compliance alerts (auto-scoped server-side to their assigned
 * clients) with the gate horizon applied before backend pagination, and
 * acknowledges them one by one via POST /api/compliance/alerts/{id}/outcome
 * — the route is on the gate-enforcement allowlist, so it works while blocked.
 */
function GateDeadlinesList({
  count,
  asOf,
  onAcknowledged,
}: {
  /** Gate-probe count — used to (re)load and as a sanity cross-check. */
  count: number;
  /** Probe timestamp — changes on every refresh, triggering a reload. */
  asOf: string;
  /** Called after each successful acknowledge so the layout re-probes. */
  onAcknowledged: () => Promise<void>;
}) {
  const { success, error: toastError } = useToast();
  const [alerts, setAlerts] = useState<ComplianceAlertItem[] | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [ackInFlight, setAckInFlight] = useState<string | null>(null);

  useEffect(() => {
    if (count <= 0) return;
    let cancelled = false;
    setLoadFailed(false);
    (async () => {
      try {
        const [pending, sent] = await Promise.all([
          api.listMyComplianceAlerts({
            status: "pending",
            deadlineWithinDays: DEADLINE_HORIZON_DAYS,
            limit: 500,
          }),
          api.listMyComplianceAlerts({
            status: "sent",
            deadlineWithinDays: DEADLINE_HORIZON_DAYS,
            limit: 500,
          }),
        ]);
        if (cancelled) return;
        const seen = new Set<string>();
        const items = [...pending.items, ...sent.items]
          .filter((a) => {
            if (seen.has(a.alert_id)) return false;
            seen.add(a.alert_id);
            return true;
          })
          .sort((a, b) => a.deadline.localeCompare(b.deadline));
        setAlerts(items);
      } catch (err) {
        if (cancelled) return;
        logger.error(
          "Failed to load deadline alerts",
          { component: "GateScreen", action: "listDeadlines" },
          err instanceof Error ? err : new Error(String(err)),
        );
        setLoadFailed(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [count, asOf]);

  const handleAck = async (alertId: string) => {
    setAckInFlight(alertId);
    try {
      await api.acknowledgeComplianceAlert(alertId);
      setAlerts((prev) =>
        prev ? prev.filter((a) => a.alert_id !== alertId) : prev,
      );
      success("Deadline acknowledged");
      await onAcknowledged();
    } catch (err) {
      logger.error(
        "Failed to acknowledge deadline alert",
        { component: "GateScreen", action: "ackDeadline" },
        err instanceof Error ? err : new Error(String(err)),
      );
      toastError(
        "Could not acknowledge",
        "Please try again. If it persists, contact an admin.",
      );
    } finally {
      setAckInFlight(null);
    }
  };

  if (loadFailed) {
    return (
      <p className="text-sm" style={{ color: "var(--bz-text-3)" }} role="alert">
        Could not load the deadlines list — use “Refresh status” below to retry.
      </p>
    );
  }

  if (alerts === null) {
    return (
      <p className="text-sm" style={{ color: "var(--bz-text-3)" }}>
        Loading deadlines…
      </p>
    );
  }

  if (alerts.length === 0) {
    // Count probe and list disagree (e.g. alerts just acknowledged elsewhere)
    // — a Refresh will reconcile the gate.
    return (
      <p className="text-sm" style={{ color: "var(--bz-text-3)" }}>
        No actionable deadlines found — press “Refresh status” below.
      </p>
    );
  }

  return (
    <ul className="flex flex-col gap-2">
      {alerts.map((alert) => {
        const overdue = alert.days_until < 0;
        const message =
          alert.message_en || alert.message_it || alert.message_id || "";
        return (
          <li
            key={alert.alert_id}
            className="flex flex-col gap-2 rounded-md border p-3 sm:flex-row sm:items-center sm:justify-between"
            style={{
              borderColor: "var(--bz-border)",
              background: "var(--bz-surface)",
            }}
          >
            <div className="flex flex-col gap-0.5">
              <p
                className="text-sm font-medium"
                style={{ color: "var(--bz-text-1)" }}
              >
                <span
                  className="mr-2 inline-block rounded px-1.5 py-0.5 text-xs font-semibold uppercase"
                  style={{
                    background:
                      alert.severity === "critical" || overdue
                        ? "var(--bz-error, #b0433a)"
                        : "var(--bz-warning, #b58a2a)",
                    color: "var(--bz-base)",
                  }}
                >
                  {overdue
                    ? `overdue ${Math.abs(alert.days_until)}d`
                    : `${alert.days_until}d left`}
                </span>
                {alert.category.replace(/_/g, " ")}
              </p>
              {message && (
                <p className="text-xs" style={{ color: "var(--bz-text-3)" }}>
                  {message}
                </p>
              )}
              <p className="text-xs" style={{ color: "var(--bz-text-3)" }}>
                Deadline: {new Date(alert.deadline).toLocaleDateString()}
              </p>
            </div>
            <button
              type="button"
              onClick={() => handleAck(alert.alert_id)}
              disabled={ackInFlight !== null}
              className="self-start rounded-md px-3 py-1.5 text-sm font-medium transition-opacity disabled:opacity-50 sm:self-center"
              style={{
                background: "var(--bz-accent)",
                color: "var(--bz-base)",
              }}
            >
              {ackInFlight === alert.alert_id
                ? "Acknowledging…"
                : "Acknowledge"}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export default function GateScreen({
  status,
  userEmail,
  isAdmin,
  onRefresh,
  onEnter,
}: GateScreenProps) {
  const router = useRouter();
  const { success, error: toastError } = useToast();

  const [lateReason, setLateReason] = useState("");
  const [submittingLate, setSubmittingLate] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const { documents, late_note: lateNote, deadlines } = status.sections;
  const totalBlocking = documents.count + lateNote.count + deadlines.count;
  const allClear = totalBlocking === 0;

  const asOfLabel = (() => {
    try {
      return new Date(status.as_of).toLocaleString();
    } catch {
      return status.as_of;
    }
  })();

  const handleSubmitLate = async () => {
    const reason = lateReason.trim();
    if (!reason) {
      toastError("Reason required", "Please enter a short explanation.");
      return;
    }
    setSubmittingLate(true);
    try {
      const result = await api.resolveMyLateIncident(reason);
      success("Late note submitted", `State: ${result.state}`);
      setLateReason("");
      await onRefresh();
    } catch (err) {
      logger.error(
        "Failed to resolve late incident",
        { component: "GateScreen", action: "resolveLate" },
        err instanceof Error ? err : new Error(String(err)),
      );
      toastError(
        "Could not submit",
        "Please try again. If it persists, contact an admin.",
      );
    } finally {
      setSubmittingLate(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await onRefresh();
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <main
      id="main-content"
      aria-labelledby="gate-title"
      className="min-h-screen w-full overflow-y-auto px-4 py-10 md:px-6"
      style={{ background: "var(--bz-base, #0f1419)" }}
    >
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-6">
        {/* Header */}
        <header className="flex flex-col gap-1">
          <h1
            id="gate-title"
            className="text-2xl font-semibold"
            style={{ color: "var(--bz-text-1)" }}
          >
            Clear your queues to enter
          </h1>
          <p className="text-sm" style={{ color: "var(--bz-text-3)" }}>
            Signed in as {userEmail || "you"} · as of {asOfLabel}
          </p>
          {status.degraded && (
            <p
              className="mt-1 text-xs"
              style={{ color: "var(--bz-text-3)" }}
              role="status"
            >
              Status is degraded — counts may be approximate.
            </p>
          )}
        </header>

        {/* F8 — high-volume escalation affordance */}
        {totalBlocking > HIGH_VOLUME_THRESHOLD && (
          <div
            role="alert"
            className="rounded-lg border px-4 py-3 text-sm"
            style={{
              borderColor: "var(--bz-border)",
              background: "var(--bz-surface)",
              color: "var(--bz-text-2)",
            }}
          >
            <strong style={{ color: "var(--bz-text-1)" }}>High volume.</strong>{" "}
            You have {totalBlocking} items to clear — contact an admin for help
            if you need it.
          </div>
        )}

        {/* ⏰ Late note */}
        <section
          aria-labelledby="gate-late-heading"
          className="rounded-xl border p-4"
          style={{
            borderColor: "var(--bz-border)",
            background: "var(--bz-card)",
          }}
        >
          <h2
            id="gate-late-heading"
            className="mb-2 text-lg font-medium"
            style={{ color: "var(--bz-text-1)" }}
          >
            <span aria-hidden="true">⏰ </span>Late note
          </h2>
          {lateNote.count > 0 ? (
            <div className="flex flex-col gap-3">
              <p className="text-sm" style={{ color: "var(--bz-text-2)" }}>
                You clocked in late today and haven&apos;t explained it yet.
                Submit a short reason to continue.
              </p>
              <label
                htmlFor="gate-late-reason"
                className="text-xs"
                style={{ color: "var(--bz-text-3)" }}
              >
                Reason
              </label>
              <textarea
                id="gate-late-reason"
                value={lateReason}
                onChange={(e) => setLateReason(e.target.value)}
                rows={3}
                disabled={submittingLate}
                placeholder="e.g. Traffic on the bypass, arrived 09:20."
                className="w-full resize-y rounded-md border px-3 py-2 text-sm outline-none focus:ring-2"
                style={{
                  borderColor: "var(--bz-border)",
                  background: "var(--bz-surface)",
                  color: "var(--bz-text-1)",
                }}
              />
              <button
                type="button"
                onClick={handleSubmitLate}
                disabled={submittingLate || !lateReason.trim()}
                className="self-start rounded-md px-4 py-2 text-sm font-medium transition-opacity disabled:opacity-50"
                style={{
                  background: "var(--bz-accent)",
                  color: "var(--bz-base)",
                }}
              >
                {submittingLate ? "Submitting…" : "Submit reason"}
              </button>
            </div>
          ) : (
            <p
              className="text-sm font-medium"
              style={{ color: "var(--bz-green, #2e9e6b)" }}
            >
              <span aria-hidden="true">✓ </span>No late note
            </p>
          )}
        </section>

        {/* 📄 Documents */}
        <section
          aria-labelledby="gate-docs-heading"
          className="rounded-xl border p-4"
          style={{
            borderColor: "var(--bz-border)",
            background: "var(--bz-card)",
          }}
        >
          <h2
            id="gate-docs-heading"
            className="mb-2 text-lg font-medium"
            style={{ color: "var(--bz-text-1)" }}
          >
            <span aria-hidden="true">📄 </span>Documents
          </h2>
          {documents.count > 0 ? (
            <div className="flex flex-col gap-3">
              <p className="text-sm" style={{ color: "var(--bz-text-2)" }}>
                {documents.count} document{documents.count === 1 ? "" : "s"}{" "}
                need your review (approve / reject).
              </p>
              <button
                type="button"
                onClick={() => router.push("/review")}
                className="self-start rounded-md border px-4 py-2 text-sm font-medium"
                style={{
                  borderColor: "var(--bz-border)",
                  background: "var(--bz-surface)",
                  color: "var(--bz-text-1)",
                }}
              >
                Review documents →
              </button>
            </div>
          ) : (
            <p
              className="text-sm font-medium"
              style={{ color: "var(--bz-green, #2e9e6b)" }}
            >
              <span aria-hidden="true">✓ </span>No documents to review
            </p>
          )}
        </section>

        {/* 🚨 Deadlines */}
        <section
          aria-labelledby="gate-deadlines-heading"
          className="rounded-xl border p-4"
          style={{
            borderColor: "var(--bz-border)",
            background: "var(--bz-card)",
          }}
        >
          <h2
            id="gate-deadlines-heading"
            className="mb-2 text-lg font-medium"
            style={{ color: "var(--bz-text-1)" }}
          >
            <span aria-hidden="true">🚨 </span>Deadlines
          </h2>
          {deadlines.count > 0 ? (
            <div className="flex flex-col gap-3">
              <p className="text-sm" style={{ color: "var(--bz-text-2)" }}>
                {deadlines.count} client deadline
                {deadlines.count === 1 ? "" : "s"} within 7 days need
                acknowledging.
              </p>
              {/* Cleared inline: per-alert Acknowledge buttons (the /clients
                  deep-link looped back into this wall — the layout intercepts
                  every route except /review while blocked). */}
              <GateDeadlinesList
                count={deadlines.count}
                asOf={status.as_of}
                onAcknowledged={onRefresh}
              />
            </div>
          ) : (
            <p
              className="text-sm font-medium"
              style={{ color: "var(--bz-green, #2e9e6b)" }}
            >
              <span aria-hidden="true">✓ </span>No deadlines to acknowledge
            </p>
          )}
        </section>

        {/* Footer actions */}
        <div className="flex flex-wrap items-center gap-3">
          {allClear ? (
            <button
              type="button"
              onClick={onEnter}
              className="rounded-md px-5 py-2.5 text-sm font-semibold"
              style={{
                background: "var(--bz-accent)",
                color: "var(--bz-base)",
              }}
            >
              Enter workspace →
            </button>
          ) : (
            <button
              type="button"
              onClick={handleRefresh}
              disabled={refreshing}
              className="rounded-md border px-4 py-2 text-sm font-medium disabled:opacity-50"
              style={{
                borderColor: "var(--bz-border)",
                background: "var(--bz-surface)",
                color: "var(--bz-text-2)",
              }}
            >
              {refreshing ? "Refreshing…" : "Refresh status"}
            </button>
          )}

          {/* F6 — admin override: visible escape that bypasses the gate */}
          {isAdmin && (
            <button
              type="button"
              onClick={onEnter}
              className="rounded-md border px-4 py-2 text-sm font-medium"
              style={{
                borderColor: "var(--bz-border)",
                background: "transparent",
                color: "var(--bz-text-3)",
              }}
              title="Admins can bypass the gate into the workspace."
            >
              Admin override — enter workspace
            </button>
          )}
        </div>
      </div>
    </main>
  );
}
