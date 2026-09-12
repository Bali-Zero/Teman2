"use client";

/**
 * Compliance obligations register — reviewer screen (kita workspace).
 *
 * Backend: apps/backend-rag/backend/app/routers/compliance_obligations.py,
 * prefix `/api/compliance/obligations`, EVERY route (reads included) gated
 * by `is_crm_admin` — a non-admin gets a plain 403, surfaced below as
 * "Admin only." rather than a generic failure.
 *
 * Flow (see the router's module docstring): `propose()` (PR A1) fills
 * `client_obligations` with `status='proposed'` rows. This page lets the tax
 * team list them, ask for more (`POST /generate`, idempotent), and decide
 * each one. Approve is the ONLY place a row becomes client-visible: the
 * backend bridges it into `compliance_alerts` in the SAME transaction as the
 * `proposed -> approved -> alerted` status flip, so a successful approve
 * always returns an `alert_id`. Reject is terminal and never touches
 * `compliance_alerts`.
 *
 * Both decisions are compare-and-swap on `status='proposed'` server-side — a
 * stale row (already decided by someone else, or re-clicked) comes back 409
 * with the current status in the message; that message is shown verbatim.
 *
 * Reviewer usability (U1): the table labels each row through the catalog read
 * `GET /obligations/catalog` (M3) — rule name, authority, verified badge, and
 * `legal_source` in the row detail — and resolves `client_id` to a display
 * name through `GET /api/crm/clients/{id}`. The catalog is never copied into
 * the frontend and a resolved client name never leaves the browser tab: no
 * log, no storage, no other request carries it (see `useClientNames`).
 *
 * Auth + transport reuse the shared `api` client (httpOnly cookie + bearer),
 * same as `(workspace)/review/page.tsx`.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { logger } from "@/lib/logger";

import { ObligationsTable } from "./components/ObligationsTable";
import { StatusCounters } from "./components/StatusCounters";
import { describeError } from "./components/describe-error";
import {
  CARD,
  INPUT_STYLE,
  STATUS_FILTER_OPTIONS,
  type ApproveOut,
  type GenerateOut,
  type ObligationListOut,
  type ObligationOut,
  type StatusFilter,
} from "./components/types";
import { useClientNames } from "./components/useClientNames";
import { useObligationsCatalog } from "./components/useObligationsCatalog";
import { useStatusCounters } from "./components/useStatusCounters";

const LIMIT = 50;

export default function ObligationsPage() {
  const router = useRouter();

  // ── register list ──────────────────────────────────────────────────────
  const [items, setItems] = useState<ObligationOut[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  // Bumped after every write so the counter strip follows the register.
  const [refreshTick, setRefreshTick] = useState(0);

  // ── filters ─────────────────────────────────────────────────────────────
  const [filterClientId, setFilterClientId] = useState("");
  const [filterStatus, setFilterStatus] = useState<StatusFilter>("proposed");

  // ── generate proposals ─────────────────────────────────────────────────
  const [genClientId, setGenClientId] = useState("");
  const [genHorizonDays, setGenHorizonDays] = useState("90");
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [generateResult, setGenerateResult] = useState<GenerateOut | null>(
    null,
  );

  // ── per-row decision state ─────────────────────────────────────────────
  const [busyId, setBusyId] = useState<number | null>(null);
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [rowError, setRowError] = useState<Record<number, string>>({});

  // ── catalog, client names, counters ────────────────────────────────────
  const catalog = useObligationsCatalog();
  const clientIds = useMemo(() => items.map((row) => row.client_id), [items]);
  const clientNames = useClientNames(clientIds);
  const trimmedClientFilter = filterClientId.trim();
  const { counts, loading: countsLoading } = useStatusCounters(
    trimmedClientFilter,
    refreshTick,
  );
  // Grouping by due month only makes sense for one client's calendar; across
  // clients the flat, server-ordered table is what the reviewer works through.
  const groupByMonth = trimmedClientFilter !== "";

  const loadList = useCallback(async () => {
    setLoading(true);
    setListError(null);
    try {
      const params = new URLSearchParams();
      const cid = filterClientId.trim();
      if (cid) params.set("client_id", cid);
      params.set("status", filterStatus);
      params.set("limit", String(LIMIT));
      params.set("offset", String(offset));
      const res = await api.get<ObligationListOut>(
        `/api/compliance/obligations?${params.toString()}`,
      );
      setItems(res.items ?? []);
      setTotal(res.total ?? 0);
    } catch (e) {
      logger.error(
        "obligations list load failed",
        { component: "ObligationsPage", action: "loadList" },
        e instanceof Error ? e : new Error(String(e)),
      );
      setListError(
        describeError(e, "Could not load the obligations register."),
      );
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [filterClientId, filterStatus, offset]);

  useEffect(() => {
    void loadList();
  }, [loadList]);

  // A filter change starts back at the first page.
  useEffect(() => {
    setOffset(0);
  }, [filterClientId, filterStatus]);

  const handleGenerate = useCallback(async () => {
    setGenerateError(null);
    const cid = Number(genClientId);
    if (!genClientId.trim() || !Number.isInteger(cid) || cid <= 0) {
      setGenerateError("Enter a valid client id.");
      return;
    }
    const horizon = Number(genHorizonDays);
    if (!Number.isInteger(horizon) || horizon < 1 || horizon > 730) {
      setGenerateError("Horizon days must be an integer between 1 and 730.");
      return;
    }
    setGenerating(true);
    setGenerateResult(null);
    setNotice(null);
    try {
      const res = await api.post<GenerateOut>(
        "/api/compliance/obligations/generate",
        { client_id: cid, horizon_days: horizon },
      );
      setGenerateResult(res);
      setRefreshTick((t) => t + 1);
      await loadList();
    } catch (e) {
      logger.error(
        "obligations generate failed",
        { component: "ObligationsPage", action: "generate" },
        e instanceof Error ? e : new Error(String(e)),
      );
      setGenerateError(describeError(e, "Could not generate proposals."));
    } finally {
      setGenerating(false);
    }
  }, [genClientId, genHorizonDays, loadList]);

  const handleApprove = useCallback(
    async (row: ObligationOut) => {
      setBusyId(row.id);
      setRowError((prev) => ({ ...prev, [row.id]: "" }));
      setNotice(null);
      try {
        const note = (notes[row.id] ?? "").trim();
        const body: { note?: string } = {};
        if (note) body.note = note;
        const res = await api.post<ApproveOut>(
          `/api/compliance/obligations/${row.id}/approve`,
          body,
        );
        setNotice(`✓ Obligation #${row.id} approved → alert ${res.alert_id}.`);
        setRefreshTick((t) => t + 1);
        await loadList();
      } catch (e) {
        logger.error(
          "obligation approve failed",
          {
            component: "ObligationsPage",
            action: "approve",
            metadata: { id: row.id },
          },
          e instanceof Error ? e : new Error(String(e)),
        );
        setRowError((prev) => ({
          ...prev,
          [row.id]: describeError(e, "Could not approve this obligation."),
        }));
      } finally {
        setBusyId(null);
      }
    },
    [notes, loadList],
  );

  const handleReject = useCallback(
    async (row: ObligationOut) => {
      // RejectBody.reason is REQUIRED (min_length=1) server-side — unlike
      // approve's optional note — so we enforce it client-side too rather
      // than round-trip a guaranteed 422.
      const reason = (notes[row.id] ?? "").trim();
      if (!reason) {
        setRowError((prev) => ({
          ...prev,
          [row.id]: "A reason is required to reject.",
        }));
        return;
      }
      setBusyId(row.id);
      setRowError((prev) => ({ ...prev, [row.id]: "" }));
      setNotice(null);
      try {
        await api.post(`/api/compliance/obligations/${row.id}/reject`, {
          reason,
        });
        setNotice(`Obligation #${row.id} rejected.`);
        setRefreshTick((t) => t + 1);
        await loadList();
      } catch (e) {
        logger.error(
          "obligation reject failed",
          {
            component: "ObligationsPage",
            action: "reject",
            metadata: { id: row.id },
          },
          e instanceof Error ? e : new Error(String(e)),
        );
        setRowError((prev) => ({
          ...prev,
          [row.id]: describeError(e, "Could not reject this obligation."),
        }));
      } finally {
        setBusyId(null);
      }
    },
    [notes, loadList],
  );

  const handleNoteChange = useCallback((id: number, value: string) => {
    setNotes((prev) => ({ ...prev, [id]: value }));
  }, []);

  const pageStart = total === 0 ? 0 : offset + 1;
  const pageEnd = Math.min(offset + LIMIT, total);

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1
            className="text-2xl font-semibold"
            style={{ color: "var(--bz-text-1)" }}
          >
            Obligations register
          </h1>
          <p className="mt-1 text-sm" style={{ color: "var(--bz-text-3)" }}>
            Generate, review and decide compliance obligation proposals before
            they become client-visible deadline alerts.
          </p>
        </div>
        <button
          type="button"
          onClick={() => router.push("/dashboard")}
          className="rounded-md border px-3 py-1.5 text-sm"
          style={{ borderColor: "var(--bz-border)", color: "var(--bz-text-2)" }}
        >
          ← Back
        </button>
      </div>

      {notice && (
        <div
          className="mb-4 rounded-md border px-4 py-2 text-sm"
          role="status"
          style={{
            borderColor: "var(--state-success)",
            color: "var(--bz-text-1)",
          }}
        >
          {notice}
        </div>
      )}

      {/* ── Generate proposals ───────────────────────────────────────── */}
      <section className="mb-6 rounded-xl border p-4" style={CARD}>
        <h2
          className="mb-2 text-lg font-medium"
          style={{ color: "var(--bz-text-1)" }}
        >
          Generate proposals
        </h2>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs" style={{ color: "var(--bz-text-3)" }}>
            Client id
            <input
              type="number"
              min={1}
              className="mt-1 block w-32 rounded border px-2 py-1.5 text-sm"
              style={INPUT_STYLE}
              value={genClientId}
              onChange={(e) => setGenClientId(e.target.value)}
              placeholder="e.g. 42"
            />
          </label>
          <label className="text-xs" style={{ color: "var(--bz-text-3)" }}>
            Horizon days
            <input
              type="number"
              min={1}
              max={730}
              className="mt-1 block w-32 rounded border px-2 py-1.5 text-sm"
              style={INPUT_STYLE}
              value={genHorizonDays}
              onChange={(e) => setGenHorizonDays(e.target.value)}
            />
          </label>
          <button
            type="button"
            disabled={generating}
            onClick={() => void handleGenerate()}
            className="rounded-md px-4 py-2 text-sm font-medium text-white"
            style={{
              background: "var(--bz-accent)",
              opacity: generating ? 0.6 : 1,
            }}
          >
            {generating ? "Generating…" : "Generate proposals"}
          </button>
        </div>

        {generateError && (
          <p
            className="mt-2 text-sm"
            role="alert"
            style={{ color: "var(--state-danger)" }}
          >
            {generateError}
          </p>
        )}

        {generateResult && (
          <div className="mt-3 space-y-1">
            <p className="text-sm" style={{ color: "var(--bz-text-2)" }}>
              Inserted {generateResult.inserted_count} new proposal
              {generateResult.inserted_count === 1 ? "" : "s"} for client{" "}
              {generateResult.client_id} — company type{" "}
              <strong>{generateResult.company_type}</strong>.
            </p>
            {generateResult.needs_manual_classification && (
              <div
                className="rounded-md border px-3 py-2 text-sm"
                role="alert"
                style={{
                  borderColor: "var(--state-warning)",
                  color: "var(--bz-text-1)",
                }}
              >
                ⚠ {generateResult.warning}
              </div>
            )}
          </div>
        )}
      </section>

      {/* ── Status counters ──────────────────────────────────────────── */}
      <StatusCounters
        counts={counts}
        loading={countsLoading}
        clientId={trimmedClientFilter}
        activeStatus={filterStatus}
        onSelect={setFilterStatus}
      />

      {/* ── Filters ──────────────────────────────────────────────────── */}
      <section className="mb-4 flex flex-wrap items-end gap-3">
        <label className="text-xs" style={{ color: "var(--bz-text-3)" }}>
          Client id
          <input
            type="number"
            min={1}
            className="mt-1 block w-32 rounded border px-2 py-1.5 text-sm"
            style={INPUT_STYLE}
            value={filterClientId}
            onChange={(e) => setFilterClientId(e.target.value)}
            placeholder="all clients"
          />
        </label>
        <label className="text-xs" style={{ color: "var(--bz-text-3)" }}>
          Status
          <select
            className="mt-1 block w-40 rounded border px-2 py-1.5 text-sm"
            style={INPUT_STYLE}
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value as StatusFilter)}
          >
            {STATUS_FILTER_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={() => {
            setRefreshTick((t) => t + 1);
            void loadList();
          }}
          disabled={loading}
          className="rounded-md border px-3 py-1.5 text-sm"
          style={{ borderColor: "var(--bz-border)", color: "var(--bz-text-2)" }}
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </section>

      {catalog.error && (
        <p className="mb-3 text-xs" style={{ color: "var(--state-warning)" }}>
          {catalog.error}
        </p>
      )}

      {listError && (
        <div
          className="mb-4 rounded-md border px-4 py-2 text-sm"
          role="alert"
          style={{
            borderColor: "var(--state-danger)",
            color: "var(--bz-text-1)",
          }}
        >
          {listError}
        </div>
      )}

      {/* ── Table ────────────────────────────────────────────────────── */}
      {loading ? (
        <p style={{ color: "var(--bz-text-3)" }}>Loading…</p>
      ) : !listError && items.length === 0 ? (
        <p style={{ color: "var(--bz-text-3)" }}>No obligations found.</p>
      ) : (
        !listError && (
          <ObligationsTable
            items={items}
            catalog={catalog.byId}
            clientNames={clientNames}
            groupByMonth={groupByMonth}
            notes={notes}
            rowError={rowError}
            busyId={busyId}
            onNoteChange={handleNoteChange}
            onApprove={(row) => void handleApprove(row)}
            onReject={(row) => void handleReject(row)}
          />
        )
      )}

      {/* ── Pagination ───────────────────────────────────────────────── */}
      {!listError && total > 0 && (
        <div
          className="mt-3 flex items-center justify-between text-xs"
          style={{ color: "var(--bz-text-3)" }}
        >
          <span>
            Showing {pageStart}-{pageEnd} of {total}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={offset === 0 || loading}
              onClick={() => setOffset((o) => Math.max(0, o - LIMIT))}
              className="rounded-md border px-3 py-1"
              style={{
                borderColor: "var(--bz-border)",
                color: "var(--bz-text-2)",
              }}
            >
              Previous
            </button>
            <button
              type="button"
              disabled={offset + LIMIT >= total || loading}
              onClick={() => setOffset((o) => o + LIMIT)}
              className="rounded-md border px-3 py-1"
              style={{
                borderColor: "var(--bz-border)",
                color: "var(--bz-text-2)",
              }}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
