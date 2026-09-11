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
 * Auth + transport reuse the shared `api` client (httpOnly cookie + bearer),
 * same as `(workspace)/review/page.tsx`. No client join / no PII beyond what
 * the API already returns (ids only — this page never fetches client names).
 */

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { ApiError } from "@/lib/api/error-handler";
import { logger } from "@/lib/logger";

// ── API contract (local types — review/page.tsx also calls `api.get`/`api.post`
//    with plain interfaces rather than the generated `schema.d.ts` typed paths,
//    so this page follows the same convention; see PR notes for why no
//    `npm run generate:openapi` regen was needed). ─────────────────────────
type ObligationStatus =
  "proposed" | "approved" | "rejected" | "alerted" | "done";

const STATUS_FILTER_OPTIONS = [
  "proposed",
  "approved",
  "rejected",
  "alerted",
  "done",
  "all",
] as const;
type StatusFilter = (typeof STATUS_FILTER_OPTIONS)[number];

interface ObligationOut {
  id: number;
  client_id: number;
  rule_id: string;
  period_key: string;
  due_date: string;
  status: ObligationStatus;
  needs_review_reason: string | null;
  reviewer_email: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  alert_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

interface ObligationListOut {
  total: number;
  limit: number;
  offset: number;
  items: ObligationOut[];
}

interface GenerateOut {
  client_id: number;
  inserted_count: number;
  company_type: string;
  needs_manual_classification: boolean;
  warning: string | null;
  rows: ObligationOut[];
}

interface ApproveOut {
  obligation: ObligationOut;
  alert_id: string;
}

const LIMIT = 50;

const CARD = {
  borderColor: "var(--bz-border)",
  background: "var(--bz-card, var(--bz-surface))",
} as const;

const INPUT_STYLE = {
  borderColor: "var(--bz-border)",
  background: "var(--bz-surface)",
  color: "var(--bz-text-1)",
} as const;

/** Turn a thrown api error into the exact text a reviewer should see. */
function describeError(e: unknown, fallback: string): string {
  if (e instanceof ApiError) {
    if (e.statusCode === 401 || e.statusCode === 403) return "Admin only.";
    if (e.statusCode === 404) return e.message || "Not found.";
    if (e.statusCode === 409)
      return e.message || "Conflict — this row was already decided.";
    return e.message || fallback;
  }
  if (e instanceof Error) return e.message || fallback;
  return fallback;
}

export default function ObligationsPage() {
  const router = useRouter();

  // ── register list ──────────────────────────────────────────────────────
  const [items, setItems] = useState<ObligationOut[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

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
          onClick={() => void loadList()}
          disabled={loading}
          className="rounded-md border px-3 py-1.5 text-sm"
          style={{ borderColor: "var(--bz-border)", color: "var(--bz-text-2)" }}
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </section>

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
          <div className="overflow-auto rounded-xl border" style={CARD}>
            <table className="w-full text-sm">
              <thead>
                <tr
                  className="border-b text-left"
                  style={{ borderColor: "var(--bz-border)" }}
                >
                  {[
                    "ID",
                    "Client",
                    "Rule",
                    "Period",
                    "Due date",
                    "Needs review",
                    "Status",
                    "Reviewer",
                    "Actions",
                  ].map((h) => (
                    <th
                      key={h}
                      className="px-3 py-2 text-xs font-medium"
                      style={{ color: "var(--bz-text-3)" }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((row) => (
                  <tr
                    key={row.id}
                    className="border-b last:border-b-0"
                    style={{ borderColor: "var(--bz-border)" }}
                  >
                    <td
                      className="px-3 py-2"
                      style={{ color: "var(--bz-text-1)" }}
                    >
                      {row.id}
                    </td>
                    <td
                      className="px-3 py-2"
                      style={{ color: "var(--bz-text-1)" }}
                    >
                      {row.client_id}
                    </td>
                    <td
                      className="px-3 py-2"
                      style={{ color: "var(--bz-text-1)" }}
                    >
                      {row.rule_id}
                    </td>
                    <td
                      className="px-3 py-2"
                      style={{ color: "var(--bz-text-1)" }}
                    >
                      {row.period_key}
                    </td>
                    <td
                      className="px-3 py-2"
                      style={{ color: "var(--bz-text-1)" }}
                    >
                      {row.due_date}
                    </td>
                    <td
                      className="px-3 py-2 text-xs"
                      style={{ color: "var(--bz-text-3)" }}
                    >
                      {row.needs_review_reason ?? "—"}
                    </td>
                    <td
                      className="px-3 py-2"
                      style={{ color: "var(--bz-text-1)" }}
                    >
                      {row.status}
                    </td>
                    <td
                      className="px-3 py-2 text-xs"
                      style={{ color: "var(--bz-text-3)" }}
                    >
                      {row.reviewer_email ? (
                        <>
                          {row.reviewer_email}
                          {row.reviewed_at
                            ? ` · ${new Date(row.reviewed_at).toLocaleString()}`
                            : ""}
                        </>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="px-3 py-2">
                      {row.status === "proposed" ? (
                        <div className="flex flex-col gap-1">
                          <input
                            aria-label={`Note for obligation ${row.id}`}
                            className="w-40 rounded border px-2 py-1 text-xs"
                            style={INPUT_STYLE}
                            placeholder="note (required to reject)"
                            value={notes[row.id] ?? ""}
                            onChange={(e) =>
                              setNotes((prev) => ({
                                ...prev,
                                [row.id]: e.target.value,
                              }))
                            }
                          />
                          <div className="flex gap-2">
                            <button
                              type="button"
                              disabled={busyId === row.id}
                              onClick={() => void handleApprove(row)}
                              className="rounded-md px-3 py-1 text-xs font-medium text-white"
                              style={{
                                background: "var(--state-success)",
                                opacity: busyId === row.id ? 0.6 : 1,
                              }}
                            >
                              {busyId === row.id ? "…" : "Approve"}
                            </button>
                            <button
                              type="button"
                              disabled={busyId === row.id}
                              onClick={() => void handleReject(row)}
                              className="rounded-md px-3 py-1 text-xs font-medium text-white"
                              style={{
                                background: "var(--state-danger)",
                                opacity: busyId === row.id ? 0.6 : 1,
                              }}
                            >
                              {busyId === row.id ? "…" : "Reject"}
                            </button>
                          </div>
                          {rowError[row.id] && (
                            <p
                              role="alert"
                              className="text-xs"
                              style={{ color: "var(--state-danger)" }}
                            >
                              {rowError[row.id]}
                            </p>
                          )}
                        </div>
                      ) : (
                        <span
                          className="text-xs"
                          style={{ color: "var(--bz-text-3)" }}
                        >
                          {row.alert_id ? `alert ${row.alert_id}` : "—"}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
