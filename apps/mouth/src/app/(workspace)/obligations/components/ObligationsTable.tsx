"use client";

import { Fragment, useState } from "react";

import { cn } from "@/lib/utils";
import { FOCUS, TABULAR } from "@/components/workspace/r19";

import {
  CARD,
  INPUT_STYLE,
  type CatalogRuleOut,
  type ObligationOut,
} from "./types";

/**
 * Register status → outlined SQUARE pill, word first. Kept page-local
 * (rather than the shared `StatePill`, which is `rounded-full`) so the
 * concept's `.state{border-radius:2px}` square survives on a dense table row.
 *
 * - `proposed` is copper because the row renders the viewer's own Approve and
 *   Reject controls, so the viewer is demonstrably the next actor;
 * - `alerted` is copper by the standing ruling in `concept/DISPOSITION.md`
 *   C11 ("obligations `alerted` -> copper, `rejected` -> waiting"), recorded
 *   as a RULING and not as a derivation this row can prove.
 *
 * `approved`/`done` are forest. `rejected` is a TERMINAL failure, so law #3
 * binds it — muted, never danger, plus its own word. A due DATE is never a
 * tone here: urgency lives on the date cell in warning, and it neither grants
 * nor removes ownership.
 */
const STATUS_TONE: Record<string, string> = {
  proposed: "text-[var(--bz-copper-text)] border-[var(--bz-copper-text)]",
  approved: "text-[var(--state-success)] border-[var(--state-success)]",
  done: "text-[var(--state-success)] border-[var(--state-success)]",
  rejected: "text-[var(--tx-secondary)] border-[var(--line-control)]",
  alerted: "text-[var(--bz-copper-text)] border-[var(--bz-copper-text)]",
};

function StatusPill({ status }: { status: string }) {
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
      {status}
    </span>
  );
}

const COLUMNS = [
  "ID",
  "Client",
  "Rule",
  "Authority",
  "Period",
  "Due date",
  "Needs review",
  "Status",
  "Reviewer",
  "Actions",
] as const;

const MONTH_NAMES = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
] as const;

/**
 * "2026-10-10" -> "October 2026". Parsed from the ISO string, never through
 * `new Date(...)`: the backend sends a plain date and a Date parse would shift
 * it by the viewer's UTC offset, moving a due date into the previous month for
 * anyone west of Greenwich.
 */
export function dueMonthLabel(dueDate: string): string {
  const match = /^(\d{4})-(\d{2})/.exec(dueDate ?? "");
  if (!match) return "Unscheduled";
  const month = MONTH_NAMES[Number(match[2]) - 1];
  return month ? `${month} ${match[1]}` : "Unscheduled";
}

/**
 * True when `dueDate` (YYYY-MM-DD) is already past or due within 7 days,
 * measured against "today" in the business timezone Asia/Makassar — never
 * the runtime's, so a reviewer in another timezone sees the same urgency
 * window the Bali desk does. Urgency ONLY: this never touches a pill's tone
 * and never makes a row copper.
 */
export function isDueSoon(dueDate: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(dueDate ?? "");
  if (!match) return false;
  const due = Date.UTC(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3]),
  );

  const todayParts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Makassar",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const year = Number(todayParts.find((p) => p.type === "year")?.value);
  const month = Number(todayParts.find((p) => p.type === "month")?.value);
  const day = Number(todayParts.find((p) => p.type === "day")?.value);
  const today = Date.UTC(year, month - 1, day);

  const diffDays = Math.round((due - today) / 86400000);
  return diffDays <= 7;
}

interface Props {
  items: ObligationOut[];
  /** rule_id -> catalog rule, from `GET /obligations/catalog`. */
  catalog: Map<string, CatalogRuleOut>;
  /** client_id -> display name; an absent id renders as the id. */
  clientNames: Record<number, string>;
  /** True when a client filter is set: rows are grouped by due month. */
  groupByMonth: boolean;
  notes: Record<number, string>;
  rowError: Record<number, string>;
  busyId: number | null;
  onNoteChange: (id: number, value: string) => void;
  onApprove: (row: ObligationOut) => void;
  onReject: (row: ObligationOut) => void;
}

export function ObligationsTable({
  items,
  catalog,
  clientNames,
  groupByMonth,
  notes,
  rowError,
  busyId,
  onNoteChange,
  onApprove,
  onReject,
}: Props) {
  const [openDetail, setOpenDetail] = useState<number | null>(null);

  // Groups in the order the server returned the rows (due_date ascending), so
  // the flat and grouped views never disagree about sequence.
  const groups: Array<{ label: string; rows: ObligationOut[] }> = [];
  if (groupByMonth) {
    for (const row of items) {
      const label = dueMonthLabel(row.due_date);
      const last = groups[groups.length - 1];
      if (last && last.label === label) last.rows.push(row);
      else groups.push({ label, rows: [row] });
    }
  } else {
    groups.push({ label: "", rows: items });
  }

  const renderRow = (row: ObligationOut) => {
    const rule = catalog.get(row.rule_id);
    const isOpen = openDetail === row.id;
    const clientName = clientNames[row.client_id];

    return (
      <>
        <tr
          data-testid={`obligation-row-${row.id}`}
          className="border-b last:border-b-0"
          style={{ borderColor: "var(--bz-border)" }}
        >
          <td
            className="px-3 py-2"
            style={{ color: "var(--bz-text-1)", ...TABULAR }}
          >
            {row.id}
          </td>
          <td className="px-3 py-2" style={{ color: "var(--bz-text-1)" }}>
            {clientName ? (
              <>
                <span className="block">{clientName}</span>
                <span
                  className="block text-xs"
                  style={{ color: "var(--bz-text-3)" }}
                >
                  #{row.client_id}
                </span>
              </>
            ) : (
              <span>{row.client_id}</span>
            )}
          </td>
          <td className="px-3 py-2" style={{ color: "var(--bz-text-1)" }}>
            <button
              type="button"
              onClick={() => setOpenDetail(isOpen ? null : row.id)}
              aria-expanded={isOpen}
              aria-label={`Rule detail for obligation ${row.id}`}
              className="text-left underline-offset-2 hover:underline"
              style={{ color: "var(--bz-text-1)" }}
            >
              {rule?.name ?? row.rule_id}
            </button>
            <span
              className="ml-2 rounded px-1.5 py-0.5 text-xs"
              style={{
                border: `1px solid ${
                  rule?.verified
                    ? "var(--state-success)"
                    : "var(--state-warning)"
                }`,
                color: "var(--bz-text-2)",
              }}
            >
              {rule?.verified ? "verified" : "unverified"}
            </span>
            {rule?.name && (
              <span
                className="block text-xs"
                style={{ color: "var(--bz-text-3)" }}
              >
                {row.rule_id}
              </span>
            )}
          </td>
          <td
            className="px-3 py-2 text-xs"
            style={{ color: "var(--bz-text-2)" }}
          >
            {rule?.authority ?? "—"}
          </td>
          <td
            className="px-3 py-2"
            style={{ color: "var(--bz-text-1)", ...TABULAR }}
          >
            {row.period_key}
          </td>
          <td
            className="px-3 py-2"
            style={{
              color: isDueSoon(row.due_date)
                ? "var(--state-warning)"
                : "var(--bz-text-1)",
              ...TABULAR,
            }}
          >
            {row.due_date}
          </td>
          <td
            className="px-3 py-2 text-xs"
            style={{ color: "var(--bz-text-3)" }}
          >
            {row.needs_review_reason ?? "—"}
          </td>
          <td className="px-3 py-2">
            <StatusPill status={row.status} />
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
                  onChange={(e) => onNoteChange(row.id, e.target.value)}
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={busyId === row.id}
                    onClick={() => onApprove(row)}
                    className={cn(
                      "min-h-8 bg-[var(--state-success)] px-3 text-xs font-[650] text-[var(--bz-on-warm)]",
                      FOCUS,
                    )}
                    style={{ opacity: busyId === row.id ? 0.6 : 1 }}
                  >
                    {busyId === row.id ? "…" : "Approve"}
                  </button>
                  {/* Copper is never a fill: Reject is an outline "attn"
                      action, not a red/danger button. */}
                  <button
                    type="button"
                    disabled={busyId === row.id}
                    onClick={() => onReject(row)}
                    className={cn(
                      "min-h-8 border border-[var(--bz-copper)] bg-transparent px-3 text-xs font-[650] text-[var(--bz-copper-text)]",
                      FOCUS,
                    )}
                    style={{ opacity: busyId === row.id ? 0.6 : 1 }}
                  >
                    {busyId === row.id ? "…" : "Reject"}
                  </button>
                </div>
                {rowError[row.id] && (
                  // Copper: the viewer just tried to decide this row and the
                  // decision failed — they are the next actor to retry it.
                  <p
                    role="alert"
                    className="text-xs"
                    style={{ color: "var(--bz-copper-text)" }}
                  >
                    {rowError[row.id]}
                  </p>
                )}
              </div>
            ) : (
              <span className="text-xs" style={{ color: "var(--bz-text-3)" }}>
                {row.alert_id ? `alert ${row.alert_id}` : "—"}
              </span>
            )}
          </td>
        </tr>
        {isOpen && (
          <tr
            className="border-b last:border-b-0"
            style={{ borderColor: "var(--bz-border)" }}
          >
            <td colSpan={COLUMNS.length} className="px-3 py-3">
              {rule ? (
                <dl
                  className="grid gap-x-6 gap-y-1 text-xs sm:grid-cols-2"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  <div className="sm:col-span-2">
                    <dt
                      className="font-medium"
                      style={{ color: "var(--bz-text-1)" }}
                    >
                      Legal source
                    </dt>
                    <dd>{rule.legal_source}</dd>
                  </div>
                  <div>
                    <dt
                      className="font-medium"
                      style={{ color: "var(--bz-text-1)" }}
                    >
                      Schedule
                    </dt>
                    <dd>
                      {rule.frequency}, roll {rule.roll}
                    </dd>
                  </div>
                  <div>
                    <dt
                      className="font-medium"
                      style={{ color: "var(--bz-text-1)" }}
                    >
                      Trigger
                    </dt>
                    <dd>{rule.trigger ?? "—"}</dd>
                  </div>
                  {rule.needs_review_reason && (
                    <div className="sm:col-span-2">
                      <dt
                        className="font-medium"
                        style={{ color: "var(--bz-text-1)" }}
                      >
                        Catalog review note
                      </dt>
                      <dd>{rule.needs_review_reason}</dd>
                    </div>
                  )}
                  {rule.notes && (
                    <div className="sm:col-span-2">
                      <dt
                        className="font-medium"
                        style={{ color: "var(--bz-text-1)" }}
                      >
                        Notes
                      </dt>
                      <dd>{rule.notes}</dd>
                    </div>
                  )}
                </dl>
              ) : (
                <p className="text-xs" style={{ color: "var(--bz-text-3)" }}>
                  Rule {row.rule_id} is not in the catalog.
                </p>
              )}
            </td>
          </tr>
        )}
      </>
    );
  };

  return (
    <div className="overflow-auto rounded-xl border" style={CARD}>
      <table className="w-full text-sm">
        <thead>
          <tr
            className="border-b text-left"
            style={{ borderColor: "var(--bz-border)" }}
          >
            {COLUMNS.map((h) => (
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
        {groups.map((group) => (
          <tbody key={group.label || "all"}>
            {group.label && (
              <tr style={{ background: "var(--bz-surface)" }}>
                <th
                  colSpan={COLUMNS.length}
                  scope="colgroup"
                  className="px-3 py-2 text-left text-xs font-semibold"
                  style={{ color: "var(--bz-text-2)" }}
                >
                  {group.label}
                  <span
                    className="ml-2 font-normal"
                    style={{ color: "var(--bz-text-3)" }}
                  >
                    {group.rows.length} due
                  </span>
                </th>
              </tr>
            )}
            {group.rows.map((row) => (
              <Fragment key={row.id}>{renderRow(row)}</Fragment>
            ))}
          </tbody>
        ))}
      </table>
    </div>
  );
}
